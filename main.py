from flask import Flask, request, jsonify, send_file, after_this_request, g
from werkzeug.utils import secure_filename
from memory import vymazat_memory_range
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
from datetime import datetime

# Allow custom model via environment variable
MODEL_NAME = os.getenv("MODEL_NAME", "gemma:2b")
# Allow choosing the Flask port via environment variable
FLASK_PORT = int(os.getenv("FLASK_PORT", 8010))
# Base URL for the Ollama server
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")

# API mode configuration
MODEL_MODE = os.getenv("MODEL_MODE", "local")
API_URL = os.getenv("API_URL", "https://api.openai.com/v1/chat/completions")
API_MODEL = os.getenv("API_MODEL", os.getenv("OPENAI_MODEL", "gpt-3.5-turbo"))
API_KEY = os.getenv("API_KEY")
OPENAI_MODEL = API_MODEL  # backward compatibility


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
TOKENS: dict[str, str] = {}


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
MEMORY_DIR = os.path.join(BASE_DIR, "memory")
DEFAULT_MEMORY_FOLDER = "public"
memory_caches: dict[str, list[dict]] = {}
memory_locks: dict[str, FileLock] = {}

# Jarvik now keeps conversation history indefinitely.
# To enforce a limit, set the ``MAX_MEMORY_ENTRIES`` environment variable
# manually before launching the application.
limit_env = os.getenv("MAX_MEMORY_ENTRIES")
MAX_MEMORY_ENTRIES = int(limit_env) if limit_env and limit_env.isdigit() else None

app = Flask(__name__)

# Načti znalosti při startu
PUBLIC_KNOWLEDGE_FOLDER = os.path.join(BASE_DIR, "knowledge")
knowledge = KnowledgeBase(PUBLIC_KNOWLEDGE_FOLDER)
user_knowledge: dict[str, KnowledgeBase] = {}
print("✅ Znalosti načteny.")


def get_knowledge_base(user: User | None) -> KnowledgeBase:
    if not user:
        return knowledge
    kb = user_knowledge.get(user.nick)
    if kb is None:
        folders = [PUBLIC_KNOWLEDGE_FOLDER]
        for sub in user.knowledge_folders:
            folders.append(os.path.join(PUBLIC_KNOWLEDGE_FOLDER, sub))
        kb = KnowledgeBase(folders)
        user_knowledge[user.nick] = kb
    return kb


def _ensure_memory(folder: str) -> tuple[str, FileLock]:
    """Return the memory log path and lock for *folder*.

    The ``public`` folder maps to ``memory/public.jsonl`` while any other
    name creates ``memory/<name>/private.jsonl``. This keeps user history
    separate from the shared public memory.
    """

    if folder == DEFAULT_MEMORY_FOLDER:
        path = os.path.join(MEMORY_DIR, "public.jsonl")
        lock_key = DEFAULT_MEMORY_FOLDER
    else:
        path = os.path.join(MEMORY_DIR, folder, "private.jsonl")
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
        # Keep the entire history by default. Only slice when a limit is set.
        # if MAX_MEMORY_ENTRIES:
        #     lines = lines[-MAX_MEMORY_ENTRIES:]

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


def append_to_memory(user_msg: str, ai_response: str, folder: str = DEFAULT_MEMORY_FOLDER) -> None:
    entry = {"user": user_msg, "jarvik": ai_response}
    path, lock = _ensure_memory(folder)
    cache = memory_caches.setdefault(folder, _read_memory_file(folder))
    now_iso = datetime.utcnow().isoformat()
    entry_user = {"timestamp": now_iso, "role": "user", "message": user_msg}
    entry_assist = {"timestamp": now_iso, "role": "assistant", "message": ai_response}
    with lock:
        cache.append(entry)
        # Do not truncate the cache unless a limit is explicitly set.
        # if MAX_MEMORY_ENTRIES and len(cache) > MAX_MEMORY_ENTRIES:
        #     cache[:] = cache[-MAX_MEMORY_ENTRIES:]
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry_user) + "\n")
            f.write(json.dumps(entry_assist) + "\n")


def flush_memory(folders: list[str] | None = None) -> None:
    for folder in [DEFAULT_MEMORY_FOLDER] + (folders or []):
        path, lock = _ensure_memory(folder)
        with lock:
            _flush_memory_locked(folder)


def _flush_memory_locked(folder: str) -> None:
    path, _ = _ensure_memory(folder)
    cache = memory_caches.get(folder, [])
    # When a limit is specified, slicing happens during flushing.
    # lines = cache[-MAX_MEMORY_ENTRIES:] if MAX_MEMORY_ENTRIES else cache
    lines = cache
    with open(path, "w", encoding="utf-8") as f:
        for item in lines:
            now_iso = datetime.utcnow().isoformat()
            f.write(json.dumps({"timestamp": now_iso, "role": "user", "message": item.get("user", "")}) + "\n")
            f.write(json.dumps({"timestamp": now_iso, "role": "assistant", "message": item.get("jarvik", "")}) + "\n")


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
    path = os.path.join(MEMORY_DIR, nick, "private.jsonl")
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

    # Vytvoření promptu pro model
    prompt = f"Uživatel: {message}\n"
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
            )
            response.raise_for_status()
            result = response.json()
            output = result.get("response", "").strip()
    except Exception as e:
        debug_log.append(str(e))
        return jsonify({"error": "❌ Chyba při komunikaci s Ollamou", "debug": debug_log}), 500

    private = str(data.get("private", "true")).lower() in {"1", "true", "yes"}
    target_folder = user.nick if (private and user) else DEFAULT_MEMORY_FOLDER
    append_to_memory(message, output, folder=target_folder)



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
            )
            response.raise_for_status()
            result = response.json()
            output = result.get("response", "").strip()
    except Exception as e:
        debug_log.append(str(e))
        return jsonify({"error": "❌ Chyba při komunikaci s Ollamou", "debug": debug_log}), 500

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

    prompt = f"Uživatel: {message}\n"
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
            )
            response.raise_for_status()
            result = response.json()
            output = result.get("response", "").strip()
    except Exception as e:
        debug_log.append(str(e))
        return (
            jsonify({"error": "❌ Chyba při komunikaci s Ollamou", "debug": debug_log}),
            500,
        )

    private = request.form.get("private", "true").lower() in {"1", "true", "yes"}
    target_folder = user.nick if (private and user) else DEFAULT_MEMORY_FOLDER
    append_to_memory(message, output, folder=target_folder)

    if ext == ".txt":
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp_out:
            out_path = tmp_out.name
        try:
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(output)
        except Exception as e:
            debug_log.append(f"Chyba při vytváření souboru: {e}")
            os.unlink(out_path)
            return jsonify({"response": output, "debug": debug_log})

        @after_this_request
        def cleanup(resp):
            try:
                os.unlink(out_path)
            except Exception:
                pass
            return resp

        try:
            resp = send_file(
                out_path, as_attachment=True, download_name=f"odpoved{ext}"
            )
        except TypeError:  # Flask < 2.0 uses attachment_filename
            resp = send_file(
                out_path, as_attachment=True, attachment_filename=f"odpoved{ext}"
            )
        resp.headers["X-Answer"] = output
        resp.headers["X-Debug"] = json.dumps(debug_log)
        return resp

    return jsonify({"response": output, "debug": debug_log})

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
    append_to_memory(user_msg, jarvik_msg, folder=folder)
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
    thresh_param = request.args.get("threshold") or request.args.get("t")
    try:
        thresh = float(thresh_param) if thresh_param is not None else RAG_THRESHOLD
    except ValueError:
        thresh = RAG_THRESHOLD
    if not query:
        return jsonify([])
    user: User | None = getattr(g, "current_user", None)
    kb = get_knowledge_base(user)
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
    print("✅ Znalosti načteny.")
    return jsonify({"status": "reloaded", "chunks": len(kb.chunks)})


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

    target = PUBLIC_KNOWLEDGE_FOLDER
    if private and user:
        target = os.path.join(target, user.nick)
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
    append_to_memory("", msg, folder=folder)

    return jsonify({"status": "saved", "file": name})


@app.route("/model", methods=["GET", "POST"])
@require_auth
def model_route():
    """Get or switch the active model."""
    if request.method == "GET":
        return jsonify({"model": MODEL_NAME})

    data = request.get_json(silent=True) or {}
    new_model = data.get("model")
    if not new_model:
        return jsonify({"error": "model required"}), 400

    script = os.path.join(BASE_DIR, "switch_model.sh")
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
    return app.send_static_file("index.html")

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
            path = os.path.join(folder, "private.jsonl")
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
    app.run(host="0.0.0.0", port=FLASK_PORT)

