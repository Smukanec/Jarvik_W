from flask import (
    Flask,
    request,
    jsonify,
    send_file,
    after_this_request,
    g,
    url_for,
    render_template,
)
from werkzeug.utils import secure_filename
from memory import vymazat_memory_range, _parse_dt
from rag_engine import (
    KnowledgeBase,
    load_txt_file,
    _strip_diacritics,
)
import difflib
from auth import load_users, User
from tools.web_search import search_and_scrape
import base64
import secrets
import json
import os
import tempfile
import subprocess
from filelock import FileLock
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from datetime import datetime, timedelta, UTC
from typing import Any

# Allow custom model via environment variable
MODEL_NAME = os.getenv("MODEL_NAME", "openchat")
# Allow choosing the Flask port via environment variable
FLASK_PORT = int(os.getenv("FLASK_PORT", 8000))
# Allow choosing the Flask host via environment variable
FLASK_HOST = os.getenv("FLASK_HOST", "0.0.0.0")
# Allow toggling Flask debug mode via environment variable
FLASK_DEBUG = os.getenv("FLASK_DEBUG", "true").lower() in {"1", "true", "yes"}
# Base URL for the Ollama server
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")

# API mode configuration
MODEL_MODE = os.getenv("MODEL_MODE", "local")
API_URL = os.getenv("API_URL", "https://api.openai.com/v1/chat/completions")
API_MODEL = os.getenv("API_MODEL", os.getenv("OPENAI_MODEL", "gpt-3.5-turbo"))
API_KEY = os.getenv("API_KEY")
OPENAI_MODEL = API_MODEL  # backward compatibility
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", 10))

# Extended information about supported models. Each entry contains a label shown
# in the UI, whether web search should be enabled and a short description.
MODEL_INFO: dict[str, dict] = {
    "openchat": {
        "label": "OpenChat – chytrý AI asistent",
        "web_search": True,
        "description": (
            "Vhodný pro běžné otázky, dialog a porozumění pokynům."
        ),
    },
    "nous-hermes2": {
        "label": "Nous Hermes 2 – jemně doladěný Mistral",
        "web_search": True,
        "description": (
            "Dobře zvládá otázky, formální texty i instrukce, vhodný i pro "
            "složitější dotazy s doplněním z internetu."
        ),
    },
    "llama3:8b": {
        "label": "LLaMA 3 8B – velký jazykový model",
        "web_search": True,
        "description": (
            "Vysoká přesnost, vhodný pro složitější dotazy, rozumí webovému "
            "obsahu i dokumentům."
        ),
    },
    "command-r": {
        "label": "Command R – model pro RAG",
        "web_search": True,
        "description": (
            "Optimalizovaný pro spojení s pamětí a znalostmi, ideální pro "
            "dotazy nad databázemi a webovým kontextem."
        ),
    },
}

# Precompute a list of model names that should automatically gather information
# from the internet.
ENABLE_WEB_SEARCH_MODELS = [
    name for name, info in MODEL_INFO.items() if info.get("web_search")
]


def should_use_web_search(model_name: str) -> bool:
    """Return ``True`` if ``model_name`` should trigger web.search()."""
    return model_name in ENABLE_WEB_SEARCH_MODELS


def call_api(prompt: str, key: str | None = None) -> str:
    """Send *prompt* to an external API and return the response."""
    import requests

    headers = {}
    if key:
        headers["Authorization"] = f"Bearer {key}"

    resp = requests.post(
        API_URL,
        headers=headers,
        json={"model": API_MODEL, "messages": [{"role": "user", "content": prompt}]},
        timeout=REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()
    if isinstance(data, dict):
        if "choices" in data:
            return data["choices"][0]["message"]["content"].strip()
        if "response" in data:
            return data.get("response", "").strip()
    return ""


def convert_file_to_txt(path: str) -> str:
    ext = Path(path).suffix.lower()
    if ext in {".txt", ".md"}:
        return load_txt_file(path)
    if ext == ".pdf":
        try:
            import pdfplumber
        except Exception:
            raise RuntimeError("pdfplumber required for PDF conversion")
        lines = []
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                lines.append(text.strip())
        return "\n\n".join(lines)
    if ext == ".docx":
        try:
            from docx import Document  # type: ignore
        except Exception:
            raise RuntimeError("python-docx required for DOCX conversion")
        doc = Document(path)
        paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
        return "\n\n".join(paragraphs)
    raise RuntimeError(f"Unsupported file type: {ext}")

# Threshold for knowledge base search
threshold_env = os.getenv("RAG_THRESHOLD")
try:
    RAG_THRESHOLD = float(threshold_env) if threshold_env is not None else None
except ValueError:
    RAG_THRESHOLD = None

# Set base directory relative to this file
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


# --- App logging setup ----------------------------------------------------
MAX_LOG_BYTES = int(os.getenv("MAX_LOG_BYTES", str(1024 * 1024)))
LOG_BACKUPS = int(os.getenv("LOG_BACKUPS", "3"))
APP_LOG_PATH = os.path.join(BASE_DIR, "jarvik.log")
_app_handler = RotatingFileHandler(
    APP_LOG_PATH,
    maxBytes=MAX_LOG_BYTES,
    backupCount=LOG_BACKUPS,
    encoding="utf-8",
    errors="replace",
)
_app_handler.setFormatter(
    logging.Formatter("%(asctime)s %(levelname)s: %(message)s")
)
_root_logger = logging.getLogger()
_root_logger.setLevel(logging.INFO)
if not any(
    isinstance(h, RotatingFileHandler) and getattr(h, "baseFilename", None) == APP_LOG_PATH
    for h in _root_logger.handlers
):
    _root_logger.addHandler(_app_handler)

# --- Prompt logging setup -------------------------------------------------
# Limit prompt log size and enable rotation
MAX_PROMPT_LOG_BYTES = int(os.getenv("MAX_PROMPT_LOG_BYTES", str(1024 * 1024)))
PROMPT_LOG_BACKUPS = int(os.getenv("PROMPT_LOG_BACKUPS", "3"))
_prompt_log_path = os.path.join(BASE_DIR, "final_prompt.txt")
_prompt_logger = logging.getLogger("prompt_log")
_prompt_logger.setLevel(logging.INFO)
_prompt_handler = RotatingFileHandler(
    _prompt_log_path,
    maxBytes=MAX_PROMPT_LOG_BYTES,
    backupCount=PROMPT_LOG_BACKUPS,
    encoding="utf-8",
    errors="replace",
)
_prompt_handler.setFormatter(logging.Formatter("%(asctime)s\n%(message)s"))
_prompt_logger.addHandler(_prompt_handler)
_prompt_logger.propagate = False


def log_prompt(prompt: str) -> None:
    """Write *prompt* to the rotating prompt log."""
    _prompt_logger.info(prompt)

# --- Authentication setup -------------------------------------------------
USERS_FILE = os.path.join(BASE_DIR, "users.json")
users = load_users(USERS_FILE)
AUTH_ENABLED = bool(users)

TOKEN_LIFETIME_DAYS = int(os.getenv("TOKEN_LIFETIME_DAYS", "7"))
TOKEN_FILE = os.path.join(
    os.getenv("MEMORY_DIR", os.path.join(BASE_DIR, "memory")), "tokens.json"
)
TOKENS: dict[str, str] = {}
_TOKEN_INFO: dict[str, dict] = {}


def _load_tokens() -> None:
    """Load persisted authentication tokens from disk."""
    global TOKENS, _TOKEN_INFO
    if not os.path.exists(TOKEN_FILE):
        TOKENS = {}
        _TOKEN_INFO = {}
        return
    try:
        with open(TOKEN_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = {}

    now = datetime.now(UTC)
    TOKENS = {}
    _TOKEN_INFO = {}
    changed = False
    for token, info in list(data.items()):
        created = _parse_dt(info.get("created"))
        nick = info.get("nick")
        if (
            created
            and nick
            and (
                TOKEN_LIFETIME_DAYS <= 0
                or now - created <= timedelta(days=TOKEN_LIFETIME_DAYS)
            )
        ):
            TOKENS[token] = nick
            _TOKEN_INFO[token] = {"nick": nick, "created": created.isoformat()}
        else:
            changed = True
    if changed:
        _save_tokens()


def _save_tokens() -> None:
    """Persist authentication tokens to disk."""
    if not _TOKEN_INFO:
        if os.path.exists(TOKEN_FILE):
            os.unlink(TOKEN_FILE)
        return
    os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)
    with open(TOKEN_FILE, "w", encoding="utf-8") as f:
        json.dump(_TOKEN_INFO, f)


_load_tokens()


def _user_from_basic(auth_header: str) -> User | None:
    try:
        encoded = auth_header.split(None, 1)[1]
        nick, pwd = base64.b64decode(encoded).decode("utf-8").split(":", 1)
    except Exception:
        return None
    user = users.get(nick)
    if user and user.verify(pwd):
        return user
    return None


def _user_from_token(token: str) -> User | None:
    nick = TOKENS.get(token)
    if nick:
        return users.get(nick)
    return None


def get_authenticated_user() -> User | None:
    if not AUTH_ENABLED:
        return None
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Basic "):
        return _user_from_basic(auth_header)
    if auth_header.startswith("Bearer "):
        return _user_from_token(auth_header.split(None, 1)[1])
    token = request.headers.get("X-Token")
    if token:
        return _user_from_token(token)
    return None


def require_auth(f):
    from functools import wraps

    @wraps(f)
    def wrapper(*args, **kwargs):
        if not AUTH_ENABLED:
            return f(*args, **kwargs)
        user = get_authenticated_user()
        if not user:
            return jsonify({"error": "unauthorized"}), 401
        g.current_user = user
        return f(*args, **kwargs)

    return wrapper

# --- Memory handling ------------------------------------------------------
MEMORY_DIR = os.getenv("MEMORY_DIR", os.path.join(BASE_DIR, "memory"))
DEFAULT_MEMORY_FOLDER = "public"
memory_caches: dict[str, list[dict]] = {}
memory_locks: dict[str, FileLock] = {}
ANSWER_DIR = os.getenv("ANSWER_DIR", os.path.join(BASE_DIR, "answers"))
MEMORY_RETENTION_DAYS = int(os.getenv("MEMORY_RETENTION_DAYS", "7"))

# Jarvik keeps conversation history for a limited time.

app = Flask(__name__, static_folder="static", template_folder="static")

# Načti znalosti při startu
KNOWLEDGE_DIR = os.getenv("KNOWLEDGE_DIR", os.path.join(BASE_DIR, "knowledge"))
PUBLIC_KNOWLEDGE_FOLDER = KNOWLEDGE_DIR
knowledge = KnowledgeBase(PUBLIC_KNOWLEDGE_FOLDER)
user_knowledge: dict[str, KnowledgeBase] = {}
logging.info("✅ Znalosti načteny.")


def get_knowledge_base(user: User | None) -> KnowledgeBase:
    if not user:
        return knowledge
    kb = user_knowledge.get(user.nick)
    if kb is None:
        folders = [PUBLIC_KNOWLEDGE_FOLDER]
        for sub in user.knowledge_folders:
            folders.append(os.path.join(PUBLIC_KNOWLEDGE_FOLDER, sub))
        folders.append(os.path.join(MEMORY_DIR, user.nick, "private_knowledge"))
        kb = KnowledgeBase(folders)
        user_knowledge[user.nick] = kb
    return kb


def _ensure_memory(folder: str) -> tuple[str, FileLock]:
    """Return the memory log path and lock for *folder*.

    The ``public`` folder maps to ``memory/public.jsonl`` while any other
    name creates ``memory/<name>/log.jsonl``. This keeps user history
    separate from the shared public memory.
    """

    if folder == DEFAULT_MEMORY_FOLDER:
        path = os.path.join(MEMORY_DIR, "public.jsonl")
        lock_key = DEFAULT_MEMORY_FOLDER
    else:
        path = os.path.join(MEMORY_DIR, folder, "log.jsonl")
        lock_key = folder

    if lock_key not in memory_locks:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, "a", encoding="utf-8").close()
        memory_locks[lock_key] = FileLock(f"{path}.lock")
    return path, memory_locks[lock_key]


def _read_memory_file(folder: str) -> list[dict]:
    path, _ = _ensure_memory(folder)
    entries: list[dict] = []
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        cutoff = None
        if MEMORY_RETENTION_DAYS > 0:
            cutoff = datetime.now(UTC) - timedelta(days=MEMORY_RETENTION_DAYS)
        pending_user: str | None = None
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                logging.warning("Skipping invalid memory line in %s: %s", path, line)
                continue

            ts_str = obj.get("timestamp")
            if ts_str:
                try:
                    ts = datetime.fromisoformat(ts_str)
                except ValueError:
                    ts = None
            else:
                dt = obj.get("date")
                tm = obj.get("time")
                ts = None
                if dt and tm:
                    try:
                        ts = datetime.fromisoformat(f"{dt}T{tm}")
                    except ValueError:
                        ts = None
                elif dt:
                    try:
                        ts = datetime.fromisoformat(f"{dt}T00:00:00")
                    except ValueError:
                        ts = None
            if cutoff and ts and ts < cutoff:
                pending_user = None
                continue

            if "role" in obj and "message" in obj:
                role = obj.get("role")
                msg = obj.get("message", "")
                if role == "user":
                    pending_user = msg
                elif role == "assistant" and pending_user is not None:
                    entries.append({"user": pending_user, "jarvik": msg})
                    pending_user = None
                # ignore assistant line without preceding user
            elif "user" in obj and "jarvik" in obj:
                entries.append({"user": obj.get("user", ""), "jarvik": obj.get("jarvik", "")})
            # ignore unrelated objects (e.g. feedback)
    # Keep the entire cache unchanged.
    return entries


# Cache default memory at startup
memory_caches[DEFAULT_MEMORY_FOLDER] = _read_memory_file(DEFAULT_MEMORY_FOLDER)


def load_memory(folders: list[str] | None = None) -> list[dict]:
    """Return cached conversation memory from the given folders."""
    folders = [DEFAULT_MEMORY_FOLDER] + (folders or [])
    entries: list[dict] = []
    for folder in folders:
        cache = memory_caches.get(folder)
        if cache is None:
            cache = _read_memory_file(folder)
            memory_caches[folder] = cache
        entries.extend(cache)
    return entries


def reload_memory(folders: list[str] | None = None) -> None:
    for folder in [DEFAULT_MEMORY_FOLDER] + (folders or []):
        memory_caches[folder] = _read_memory_file(folder)


def append_to_memory(
    user_msg: str,
    ai_response: str,
    folder: str = DEFAULT_MEMORY_FOLDER,
    *,
    context: str | None = None,
    date: str | None = None,
    time: str | None = None,
    attachments: list[str] | None = None,
) -> None:
    """Append a conversation entry to the memory log."""

    now = datetime.now(UTC)
    now_date = date or now.date().isoformat()
    now_time = time or now.time().isoformat(timespec="seconds")
    now_iso = f"{now_date}T{now_time}"

    entry = {"user": user_msg, "jarvik": ai_response}
    if context:
        entry["context"] = context
    if attachments:
        entry["attachments"] = attachments

    path, lock = _ensure_memory(folder)
    cache = memory_caches.setdefault(folder, _read_memory_file(folder))

    entry_user = {
        "timestamp": now_iso,
        "role": "user",
        "message": user_msg,
        "context": context,
        "date": now_date,
        "time": now_time,
    }
    if attachments:
        entry_user["attachments"] = attachments

    entry_assist = {
        "timestamp": now_iso,
        "role": "assistant",
        "message": ai_response,
        "context": context,
        "date": now_date,
        "time": now_time,
    }
    if attachments:
        entry_assist["attachments"] = attachments

    with lock:
        cache.append(entry)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry_user) + "\n")
            f.write(json.dumps(entry_assist) + "\n")
        if MEMORY_RETENTION_DAYS > 0:
            cutoff = (datetime.now(UTC) - timedelta(days=MEMORY_RETENTION_DAYS)).isoformat()
            if vymazat_memory_range(path, do=cutoff):
                memory_caches[folder] = _read_memory_file(folder)


def flush_memory(folders: list[str] | None = None) -> None:
    for folder in [DEFAULT_MEMORY_FOLDER] + (folders or []):
        path, lock = _ensure_memory(folder)
        with lock:
            _flush_memory_locked(folder)


def _flush_memory_locked(folder: str) -> None:
    path, _ = _ensure_memory(folder)
    cache = memory_caches.get(folder, [])
    lines = cache
    with open(path, "w", encoding="utf-8") as f:
        for item in lines:
            now = datetime.now(UTC)
            now_date = now.date().isoformat()
            now_time = now.time().isoformat(timespec="seconds")
            now_iso = f"{now_date}T{now_time}"
            extra: dict[str, Any] = {}
            if "context" in item and item["context"]:
                extra["context"] = item["context"]
            if "attachments" in item and item["attachments"]:
                extra["attachments"] = item["attachments"]
            f.write(json.dumps({
                "timestamp": now_iso,
                "role": "user",
                "message": item.get("user", ""),
                "date": now_date,
                "time": now_time,
                **extra,
            }) + "\n")
            f.write(json.dumps({
                "timestamp": now_iso,
                "role": "assistant",
                "message": item.get("jarvik", ""),
                "date": now_date,
                "time": now_time,
                **extra,
            }) + "\n")


@app.route("/login", methods=["POST"])
def login():
    if not AUTH_ENABLED:
        return jsonify({"error": "auth disabled"}), 400
    data = request.get_json(silent=True) or {}
    nick = data.get("nick") or data.get("username")
    password = data.get("password", "")
    user = users.get(nick)
    if not user or not user.verify(password):
        return jsonify({"error": "invalid credentials"}), 401
    token = secrets.token_hex(16)
    TOKENS[token] = nick
    _TOKEN_INFO[token] = {
        "nick": nick,
        "created": datetime.now(UTC).isoformat(),
    }
    _save_tokens()
    return jsonify({"token": token})

def search_memory(query, memory_entries):
    """Return up to five memory entries containing *query* in any form."""
    results = []
    q = _strip_diacritics(query.lower())
    for entry in reversed(memory_entries):
        user_text = _strip_diacritics(entry.get("user", "").lower())
        jarvik_text = _strip_diacritics(entry.get("jarvik", "").lower())
        if q in user_text or q in jarvik_text:
            results.append(entry)
        if len(results) >= 5:
            break
    return results


def get_corrections(nick: str, query: str, threshold: float = 0.7) -> list[str]:
    """Return feedback corrections for *nick* similar to *query*."""
    path = os.path.join(MEMORY_DIR, nick, "log.jsonl")
    if not os.path.exists(path):
        return []

    notes: list[str] = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except Exception:
                    continue
                original = entry.get("original_question") or entry.get("question")
                correction = entry.get("correction")
                if not original or not correction:
                    continue
                ratio = difflib.SequenceMatcher(None, original, query).ratio()
                if ratio >= threshold:
                    notes.append(correction)
    except Exception:
        return []
    return notes

@app.route("/ask", methods=["POST"])
@require_auth
def ask():
    debug_log = []
    data = request.get_json(silent=True)
    data = data or {}
    message = data.get("message", "")
    api_key = request.headers.get("X-API-Key") or data.get("api_key")
    if not api_key and MODEL_MODE == "api":
        api_key = API_KEY
    use_api = MODEL_MODE == "api" or api_key

    user: User | None = getattr(g, "current_user", None)
    folders = [user.nick] + user.memory_folders if user else None
    memory_context = load_memory(folders)
    debug_log.append(f"🧠 Paměť: {len(memory_context)} záznamů")
    corrections = get_corrections(user.nick, message) if user else []
    if corrections:
        debug_log.append(f"✏️ Opravy: {len(corrections)}")

    kb = get_knowledge_base(user)
    rag_context = kb.search(message, threshold=RAG_THRESHOLD)
    debug_log.append(f"📚 Kontext z RAG: {len(rag_context)} výsledků")

    web_info = ""
    if should_use_web_search(MODEL_NAME) and message:
        web_info = search_and_scrape(message)
        debug_log.append("🌐 Vyhledáno na webu")

    # Vytvoření promptu pro model
    prompt = ""
    if web_info:
        prompt += f"{web_info}\n\n"
    prompt += f"Uživatel: {message}\n"
    if rag_context:
        prompt += "\n".join([f"Znalost: {chunk}" for chunk in rag_context])
    if memory_context:
        prompt += "\n" + "\n".join([f"Minulý dotaz: {m['user']} -> {m['jarvik']}" for m in memory_context[-5:]])
    if corrections:
        prompt += "\n" + "\n".join([f"Poznámka: {c}" for c in corrections])

    log_prompt(prompt)

    try:
        import requests
        if use_api:
            output = call_api(prompt, key=api_key)
        else:
            response = requests.post(
                f"{OLLAMA_URL}/api/generate",
                json={"model": MODEL_NAME, "prompt": prompt, "stream": False},
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            result = response.json()
            output = result.get("response", "").strip()
    except Exception as e:
        debug_log.append(str(e))
        return jsonify({"error": f"❌ Chyba při komunikaci s Ollamou: {e}", "debug": debug_log}), 500

    private = str(data.get("private", "true")).lower() in {"1", "true", "yes"}
    target_folder = user.nick if (private and user) else DEFAULT_MEMORY_FOLDER
    append_to_memory(message, output, folder=target_folder)

    return jsonify({"response": output, "debug": debug_log})


@app.route("/ask_web", methods=["POST"])
@require_auth
def ask_web():
    debug_log = []
    data = request.get_json(silent=True) or {}
    query = data.get("message", "")
    if not query:
        return jsonify({"error": "message required"}), 400
    api_key = request.headers.get("X-API-Key") or data.get("api_key")
    if not api_key and MODEL_MODE == "api":
        api_key = API_KEY
    use_api = MODEL_MODE == "api" or api_key

    user: User | None = getattr(g, "current_user", None)
    folders = [user.nick] + user.memory_folders if user else None
    memory_context = load_memory(folders)
    debug_log.append(f"🧠 Paměť: {len(memory_context)} záznamů")

    corrections = get_corrections(user.nick, query) if user else []
    if corrections:
        debug_log.append(f"✏️ Opravy: {len(corrections)}")

    kb = get_knowledge_base(user)
    rag_context = kb.search(query, threshold=RAG_THRESHOLD)
    debug_log.append(f"📚 Kontext z RAG: {len(rag_context)} výsledků")

    web_info = search_and_scrape(query)
    prompt = f"{web_info}\n\nOtázka: {query}\n"
    if rag_context:
        prompt += "\n".join([f"Znalost: {chunk}" for chunk in rag_context])
    if memory_context:
        prompt += "\n" + "\n".join(
            [f"Minulý dotaz: {m['user']} -> {m['jarvik']}" for m in memory_context[-5:]]
        )
    if corrections:
        prompt += "\n" + "\n".join([f"Poznámka: {c}" for c in corrections])

    log_prompt(prompt)

    try:
        import requests
        if use_api:
            output = call_api(prompt, key=api_key)
        else:
            response = requests.post(
                f"{OLLAMA_URL}/api/generate",
                json={"model": MODEL_NAME, "prompt": prompt, "stream": False},
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            result = response.json()
            output = result.get("response", "").strip()
    except Exception as e:
        debug_log.append(str(e))
        return jsonify({"error": f"❌ Chyba při komunikaci s Ollamou: {e}", "debug": debug_log}), 500

    private = str(data.get("private", "true")).lower() in {"1", "true", "yes"}
    target_folder = user.nick if (private and user) else DEFAULT_MEMORY_FOLDER
    append_to_memory(query, output, folder=target_folder)

    return jsonify({"response": output, "debug": debug_log})


@app.route("/ask_file", methods=["POST"])
@require_auth
def ask_file():
    debug_log = []
    message = request.form.get("message", "")
    api_key = request.headers.get("X-API-Key") or request.form.get("api_key")
    if not api_key and MODEL_MODE == "api":
        api_key = API_KEY
    use_api = MODEL_MODE == "api" or api_key

    uploaded = request.files.get("file")
    file_text = ""
    ext = None
    if uploaded and uploaded.filename:
        ext = os.path.splitext(uploaded.filename)[1].lower()
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            uploaded.save(tmp.name)
            tmp_path = tmp.name
        try:
            file_text = convert_file_to_txt(tmp_path)
        except Exception as e:
            debug_log.append(f"Chyba při čtení souboru: {e}")
            ext = None
        finally:
            os.unlink(tmp_path)

    user: User | None = getattr(g, "current_user", None)
    folders = [user.nick] + user.memory_folders if user else None
    memory_context = load_memory(folders)
    debug_log.append(f"🧠 Paměť: {len(memory_context)} záznamů")
    corrections = get_corrections(user.nick, message) if user else []
    if corrections:
        debug_log.append(f"✏️ Opravy: {len(corrections)}")

    kb = get_knowledge_base(user)
    rag_context = kb.search(message, threshold=RAG_THRESHOLD)
    if file_text:
        rag_context = [file_text] + rag_context
    debug_log.append(f"📚 Kontext z RAG: {len(rag_context)} výsledků")

    web_info = ""
    if should_use_web_search(MODEL_NAME) and message:
        web_info = search_and_scrape(message)
        debug_log.append("🌐 Vyhledáno na webu")

    prompt = ""
    if web_info:
        prompt += f"{web_info}\n\n"
    prompt += f"Uživatel: {message}\n"
    if rag_context:
        prompt += "\n".join([f"Znalost: {chunk}" for chunk in rag_context])
    if memory_context:
        prompt += "\n" + "\n".join([
            f"Minulý dotaz: {m['user']} -> {m['jarvik']}" for m in memory_context[-5:]
        ])
    if corrections:
        prompt += "\n" + "\n".join([f"Poznámka: {c}" for c in corrections])

    log_prompt(prompt)

    try:
        import requests
        if use_api:
            output = call_api(prompt, key=api_key)
        else:
            response = requests.post(
                f"{OLLAMA_URL}/api/generate",
                json={"model": MODEL_NAME, "prompt": prompt, "stream": False},
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            result = response.json()
            output = result.get("response", "").strip()
    except Exception as e:
        debug_log.append(str(e))
        return (
            jsonify({"error": f"❌ Chyba při komunikaci s Ollamou: {e}", "debug": debug_log}),
            500,
        )

    private = request.form.get("private", "true").lower() in {"1", "true", "yes"}
    target_folder = user.nick if (private and user) else DEFAULT_MEMORY_FOLDER

    save = request.form.get("save")
    download_url = None
    attachments = [uploaded.filename] if uploaded and uploaded.filename else None
    if save:
        os.makedirs(ANSWER_DIR, exist_ok=True)
        out_name = f"{secrets.token_hex(8)}.txt"
        out_path = os.path.join(ANSWER_DIR, out_name)
        try:
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(output)
            download_url = url_for("download_answer", filename=out_name)
            note = (
                f"Odpověď uložena jako {out_name}"
                + (
                    f" (soubor {uploaded.filename})" if uploaded and uploaded.filename else ""
                )
            )
            append_to_memory(
                message,
                note,
                folder=target_folder,
                attachments=attachments,
            )
        except Exception as e:
            debug_log.append(f"Chyba při vytváření souboru: {e}")
            append_to_memory(
                message,
                output,
                folder=target_folder,
                attachments=attachments,
            )
    else:
        append_to_memory(
            message,
            output,
            folder=target_folder,
            attachments=attachments,
        )

    resp = {"response": output, "debug": debug_log}
    if download_url:
        resp["download_url"] = download_url
    return jsonify(resp)


@app.route("/answers/<path:filename>")
@require_auth
def download_answer(filename: str):
    """Serve generated answer files."""
    path = os.path.join(ANSWER_DIR, filename)
    if not os.path.exists(path):
        return jsonify({"error": "not found"}), 404
    return send_file(path, as_attachment=True, download_name=filename)

@app.route("/memory/add", methods=["POST"])
@require_auth
def memory_add():
    data = request.get_json(silent=True) or {}
    user_msg = data.get("user")
    jarvik_msg = data.get("jarvik")
    if not user_msg or not jarvik_msg:
        return jsonify({"error": "user and jarvik required"}), 400
    user: User | None = getattr(g, "current_user", None)
    private = str(data.get("private", "true")).lower() in {"1", "true", "yes"}
    folder = user.nick if (private and user) else DEFAULT_MEMORY_FOLDER
    append_to_memory(
        user_msg,
        jarvik_msg,
        folder=folder,
        context=data.get("context"),
        date=data.get("date"),
        time=data.get("time"),
        attachments=data.get("attachments"),
    )
    return jsonify({"status": "ok"})

@app.route("/memory/search")
@require_auth
def memory_search():
    query = request.args.get("q", "")
    user: User | None = getattr(g, "current_user", None)
    folders = [user.nick] + user.memory_folders if user else None
    memory_entries = load_memory(folders)
    if not query:
        return jsonify(memory_entries[-5:])
    return jsonify(search_memory(query, memory_entries))


@app.route("/memory/delete", methods=["POST"])
@require_auth
def delete_memory_entries():
    """Remove memory entries for the current user."""
    data = request.get_json(silent=True) or {}
    t_from = data.get("from") or data.get("od")
    t_to = data.get("to") or data.get("do")
    keyword = data.get("keyword") or data.get("hledat_podle")
    user: User | None = getattr(g, "current_user", None)
    folder = user.nick if user else DEFAULT_MEMORY_FOLDER
    path, lock = _ensure_memory(folder)
    with lock:
        removed = vymazat_memory_range(path, od=t_from, do=t_to, hledat_podle=keyword)
        memory_caches[folder] = _read_memory_file(folder)
    return jsonify({"message": f"{removed} entries deleted"})

@app.route("/knowledge/search")
@require_auth
def knowledge_search():
    query = request.args.get("q", "")
    topics_param = request.args.get("topics")
    topics = [t.strip() for t in topics_param.split(",") if t.strip()] if topics_param else None
    thresh_param = request.args.get("threshold") or request.args.get("t")
    try:
        thresh = float(thresh_param) if thresh_param is not None else RAG_THRESHOLD
    except ValueError:
        thresh = RAG_THRESHOLD
    if not query:
        return jsonify([])
    user: User | None = getattr(g, "current_user", None)
    kb = get_knowledge_base(user)
    if topics:
        kb = KnowledgeBase(kb.folders, model_name=kb.model_name, topics=topics)
    return jsonify(kb.search(query, threshold=thresh))


@app.route("/knowledge/reload", methods=["POST"])
@require_auth
def knowledge_reload():
    """Reload knowledge base files and return how many chunks were loaded."""
    user: User | None = getattr(g, "current_user", None)
    kb = get_knowledge_base(user)
    kb.reload()
    folders = [user.nick] + user.memory_folders if user else None
    reload_memory(folders)
    logging.info("✅ Znalosti načteny.")
    return jsonify({"status": "reloaded", "chunks": len(kb.chunks)})


@app.route("/knowledge/topics")
@require_auth
def knowledge_topics():
    """Return the topic index from the knowledge folder."""
    index_path = os.path.join(PUBLIC_KNOWLEDGE_FOLDER, "_index.json")
    if not os.path.exists(index_path):
        return jsonify({})
    with open(index_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return jsonify(data)


@app.route("/knowledge/upload", methods=["POST"])
@require_auth
def knowledge_upload():
    user: User | None = getattr(g, "current_user", None)
    uploaded = request.files.get("file")
    if not uploaded or not uploaded.filename:
        return jsonify({"error": "file required"}), 400
    filename = secure_filename(uploaded.filename)
    if not filename:
        return jsonify({"error": "invalid filename"}), 400
    private = request.form.get("private") in {"1", "true", "yes"}
    description = request.form.get("description", "")
    topic = request.form.get("topic", "")
    ext = os.path.splitext(filename)[1].lower()
    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        uploaded.save(tmp.name)
        tmp_path = tmp.name
    try:
        text = convert_file_to_txt(tmp_path)
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

    # Suggest a topic based on the uploaded text when none was provided
    proposed_topic = topic
    if not topic:
        index_path = os.path.join(PUBLIC_KNOWLEDGE_FOLDER, "_index.json")
        topics: list[str] = []
        if os.path.exists(index_path):
            try:
                with open(index_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        topics = list(data.keys())
                    elif isinstance(data, list):  # pragma: no cover - alternate format
                        topics = [str(t) for t in data]
            except Exception:  # pragma: no cover - ignore invalid index
                topics = []

        text_norm = _strip_diacritics(text.lower())
        best_topic = None
        best_score = 0
        for t in topics:
            words = t.replace("_", " ").split()
            score = sum(text_norm.count(w) for w in words)
            if score > best_score:
                best_score = score
                best_topic = t
        if best_topic:
            proposed_topic = best_topic

    target = PUBLIC_KNOWLEDGE_FOLDER
    if private and user:
        target = os.path.join(MEMORY_DIR, user.nick, "private_knowledge")
    os.makedirs(target, exist_ok=True)
    base = os.path.splitext(filename)[0]
    name = f"{base}.txt"
    path = os.path.join(target, name)
    counter = 1
    while os.path.exists(path):
        name = f"{base}_{counter}.txt"
        path = os.path.join(target, name)
        counter += 1
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)

    meta = {
        "uploader": user.nick if user else "anonymous",
        "proposed_topic": proposed_topic,
        "topic": topic,
        "status": "pending_approval" if not private else "private",
        "public": not private,
    }
    meta_path = os.path.join(target, f"{os.path.splitext(name)[0]}.meta.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f)

    kb = get_knowledge_base(user)
    kb.reload()
    if not private:
        knowledge.reload()

    folder = user.nick if user else DEFAULT_MEMORY_FOLDER
    msg = (
        f'Byl vložen znalostní soubor: "{name}"\n'
        f'Popis: {description}\n'
        'Tento záznam pomůže Jarvikovi při budoucím vyhledávání.'
    )
    append_to_memory("", msg, folder=folder, attachments=[name])

    return jsonify({"status": "saved", "file": name})


@app.route("/knowledge/pending")
@require_auth
def knowledge_pending():
    """Return metadata for knowledge files awaiting approval."""
    pending: list[dict] = []
    base = os.path.abspath(PUBLIC_KNOWLEDGE_FOLDER)
    for root, _dirs, files in os.walk(base):
        for fname in files:
            if not fname.endswith(".meta.json"):
                continue
            path = os.path.join(root, fname)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    meta = json.load(f)
            except Exception:
                continue
            if meta.get("status") == "pending_approval":
                rel = os.path.relpath(os.path.splitext(path)[0] + ".txt", base)
                rel = rel.replace(os.sep, "/")
                meta = dict(meta)
                meta["file"] = rel
                pending.append(meta)
    return jsonify(pending)


def _resolve_public_path(rel: str) -> str:
    rel = rel.lstrip("/\\")
    rel = rel.replace("/", os.sep)
    full = os.path.abspath(os.path.join(PUBLIC_KNOWLEDGE_FOLDER, rel))
    base = os.path.abspath(PUBLIC_KNOWLEDGE_FOLDER)
    if os.path.commonpath([full, base]) != base:
        raise ValueError("invalid path")
    return os.path.normpath(full)


@app.route("/knowledge/approve", methods=["POST"])
@require_auth
def knowledge_approve():
    data = request.get_json(silent=True) or {}
    rel = data.get("file")
    if not rel:
        return jsonify({"error": "file required"}), 400
    try:
        file_path = _resolve_public_path(rel)
    except ValueError:
        return jsonify({"error": "invalid file"}), 400
    meta_path = os.path.splitext(file_path)[0] + ".meta.json"
    if not os.path.exists(meta_path):
        return jsonify({"error": "not found"}), 404
    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
    except Exception:
        meta = {}
    meta["status"] = "approved"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f)
    knowledge.reload()
    return jsonify({"status": "approved"})


@app.route("/knowledge/reject", methods=["POST"])
@require_auth
def knowledge_reject():
    data = request.get_json(silent=True) or {}
    rel = data.get("file")
    if not rel:
        return jsonify({"error": "file required"}), 400
    try:
        file_path = _resolve_public_path(rel)
    except ValueError:
        return jsonify({"error": "invalid file"}), 400
    meta_path = os.path.splitext(file_path)[0] + ".meta.json"
    if not os.path.exists(meta_path):
        return jsonify({"error": "not found"}), 404
    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
    except Exception:
        meta = {}
    uploader = meta.get("uploader", "unknown")
    meta["status"] = "rejected"
    target = os.path.join(MEMORY_DIR, uploader, "private_knowledge")
    os.makedirs(target, exist_ok=True)
    dest_file = os.path.join(target, os.path.basename(file_path))
    dest_meta = os.path.join(target, os.path.basename(meta_path))
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f)
    os.replace(file_path, dest_file)
    os.replace(meta_path, dest_meta)
    knowledge.reload()
    return jsonify({"status": "rejected"})


@app.route("/model", methods=["GET", "POST"])
@require_auth
def model_route():
    """Get or switch the active model."""
    if request.method == "GET":
        status = "unknown"
        status_file = os.path.join(BASE_DIR, "startup_status")
        try:
            with open(status_file, "r", encoding="utf-8") as f:
                status = f.read().strip()
        except OSError:
            pass
        success = status == "running"
        return jsonify({"model": MODEL_NAME, "status": status, "success": success})

    data = request.get_json(silent=True) or {}
    new_model = data.get("model")
    if not new_model:
        return jsonify({"error": "model required"}), 400

    script = os.path.join(BASE_DIR, "switch_model.sh")
    # mark startup status while switching
    try:
        with open(os.path.join(BASE_DIR, "startup_status"), "w", encoding="utf-8") as f:
            f.write("starting")
    except OSError:
        pass
    try:
        subprocess.Popen(["bash", script, new_model])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    @after_this_request
    def shutdown(resp):
        func = request.environ.get("werkzeug.server.shutdown")
        if func:
            func()
        return resp

    return jsonify({"status": "restarting", "model": new_model})



@app.route("/")
def index():
    return render_template("index.html")

@app.route("/mobile")
def mobile_index():
    return render_template("mobile.html")

@app.route("/static/<path:path>")
def static_files(path):
    return app.send_static_file(path)


@app.route("/feedback", methods=["POST"])
@require_auth
def feedback():
    """Record user feedback when they disagree with an answer."""
    data = request.get_json(silent=True) or {}
    agree = data.get("agree")
    question = data.get("question")
    answer = data.get("answer")
    correction = data.get("correction")

    if not agree:
        user: User | None = getattr(g, "current_user", None)
        if user:
            folder = os.path.join(MEMORY_DIR, user.nick)
            os.makedirs(folder, exist_ok=True)
            path = os.path.join(folder, "log.jsonl")
            entry = {
                "type": "feedback",
                "agree": agree,
                "question": question,
                "answer": answer,
                "correction": correction,
            }
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")

    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(debug=FLASK_DEBUG, host=FLASK_HOST, port=FLASK_PORT)

