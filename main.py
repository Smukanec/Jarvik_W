from flask import Flask, request, jsonify, send_file, after_this_request, g
import rag_engine
from rag_engine import (
    KnowledgeBase,
    dependency_status,
    load_txt_file,
    load_pdf_file,
    load_docx_file,
)
from auth import load_users, User
import base64
import secrets
import json
import os
import tempfile
import subprocess
from filelock import FileLock


class MultiKnowledgeBase:
    """Combine knowledge from the public folder and optional subfolders."""

    def __init__(self, root: str):
        self.root = root
        self.bases: dict[str, KnowledgeBase | None] = {"": KnowledgeBase(root)}

    def _get_base(self, sub: str) -> KnowledgeBase | None:
        kb = self.bases.get(sub)
        if kb is None:
            path = os.path.join(self.root, sub)
            if os.path.isdir(path):
                kb = KnowledgeBase(path)
            else:
                kb = None
            self.bases[sub] = kb
        return kb

    def search(self, query: str, folders: list[str] | None = None, threshold: float | None = None) -> list[str]:
        chunks = []
        for sub in [""] + (folders or []):
            kb = self._get_base(sub)
            if kb:
                chunks.extend(kb.chunks)
        return rag_engine.search_knowledge(query, chunks, threshold or RAG_THRESHOLD)

    def reload(self) -> None:
        for kb in self.bases.values():
            if kb:
                kb.reload()

# Allow custom model via environment variable
MODEL_NAME = os.getenv("MODEL_NAME", "gemma:2b")
# Allow choosing the Flask port via environment variable
FLASK_PORT = int(os.getenv("FLASK_PORT", 8010))
# Base URL for the Ollama server
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")

# Threshold for knowledge base search
threshold_env = os.getenv("RAG_THRESHOLD")
try:
    RAG_THRESHOLD = float(threshold_env) if threshold_env is not None else None
except ValueError:
    RAG_THRESHOLD = None

# Set base directory relative to this file
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

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
knowledge = MultiKnowledgeBase(os.path.join(BASE_DIR, "knowledge"))
print("✅ Znalosti načteny.")
deps = dependency_status()
if not deps["pdf"]:
    print("⚠️  PDF soubory se nenačtou – nainstalujte balíček PyPDF2")
if not deps["docx"]:
    print("⚠️  DOCX soubory se nenačtou – nainstalujte balíček python-docx")


def _ensure_memory(folder: str) -> tuple[str, FileLock]:
    """Return the memory log path and lock for *folder*.

    The ``public`` folder maps to ``memory/public.jsonl`` while any other
    name creates ``memory/<name>/log.jsonl``. This supports per-user logs
    without breaking the existing public memory file.
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
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            if MAX_MEMORY_ENTRIES:
                lines = lines[-MAX_MEMORY_ENTRIES:]
            return [json.loads(line) for line in lines if line.strip()]
    return []


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
    with lock:
        cache.append(entry)
        if MAX_MEMORY_ENTRIES and len(cache) > MAX_MEMORY_ENTRIES:
            cache[:] = cache[-MAX_MEMORY_ENTRIES:]
        _flush_memory_locked(folder)


def flush_memory(folders: list[str] | None = None) -> None:
    for folder in [DEFAULT_MEMORY_FOLDER] + (folders or []):
        path, lock = _ensure_memory(folder)
        with lock:
            _flush_memory_locked(folder)


def _flush_memory_locked(folder: str) -> None:
    path, _ = _ensure_memory(folder)
    cache = memory_caches.get(folder, [])
    lines = cache[-MAX_MEMORY_ENTRIES:] if MAX_MEMORY_ENTRIES else cache
    with open(path, "w", encoding="utf-8") as f:
        for item in lines:
            f.write(json.dumps(item) + "\n")


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
    results = []
    q = query.lower()
    for entry in reversed(memory_entries):
        if q in entry.get("user", "").lower() or q in entry.get("jarvik", "").lower():
            results.append(entry)
        if len(results) >= 5:
            break
    return results

@app.route("/ask", methods=["POST"])
@require_auth
def ask():
    debug_log = []
    data = request.get_json(silent=True)
    message = (data or {}).get("message", "")

    user: User | None = getattr(g, "current_user", None)
    folders = [user.nick] + user.memory_folders if user else None
    memory_context = load_memory(folders)
    debug_log.append(f"🧠 Paměť: {len(memory_context)} záznamů")

    rag_context = knowledge.search(message, folders=user.knowledge_folders if user else None, threshold=RAG_THRESHOLD)
    debug_log.append(f"📚 Kontext z RAG: {len(rag_context)} výsledků")

    # Vytvoření promptu pro model
    prompt = f"Uživatel: {message}\n"
    if rag_context:
        prompt += "\n".join([f"Znalost: {chunk}" for chunk in rag_context])
    if memory_context:
        prompt += "\n" + "\n".join([f"Minulý dotaz: {m['user']} -> {m['jarvik']}" for m in memory_context[-5:]])

    try:
        import requests
        response = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={"model": MODEL_NAME, "prompt": prompt, "stream": False}
        )
        response.raise_for_status()
        result = response.json()
        output = result.get("response", "").strip()
    except Exception as e:
        debug_log.append(str(e))
        return jsonify({"error": "❌ Chyba při komunikaci s Ollamou", "debug": debug_log}), 500

    target_folder = user.nick if user else DEFAULT_MEMORY_FOLDER
    append_to_memory(message, output, folder=target_folder)



@app.route("/ask_file", methods=["POST"])
@require_auth
def ask_file():
    debug_log = []
    message = request.form.get("message", "")

    uploaded = request.files.get("file")
    file_text = ""
    ext = None
    if uploaded and uploaded.filename:
        ext = os.path.splitext(uploaded.filename)[1].lower()
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            uploaded.save(tmp.name)
            tmp_path = tmp.name
        try:
            if ext == ".txt":
                file_text = load_txt_file(tmp_path)
            elif ext == ".pdf":
                file_text = load_pdf_file(tmp_path)
            elif ext == ".docx":
                file_text = load_docx_file(tmp_path)
            else:
                debug_log.append(f"Nepodporovaný typ souboru: {uploaded.filename}")
        except Exception as e:
            debug_log.append(f"Chyba při čtení souboru: {e}")
        finally:
            os.unlink(tmp_path)

    user: User | None = getattr(g, "current_user", None)
    folders = [user.nick] + user.memory_folders if user else None
    memory_context = load_memory(folders)
    debug_log.append(f"🧠 Paměť: {len(memory_context)} záznamů")

    rag_context = knowledge.search(message, folders=user.knowledge_folders if user else None, threshold=RAG_THRESHOLD)
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

    try:
        import requests
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

    target_folder = user.nick if user else DEFAULT_MEMORY_FOLDER
    append_to_memory(message, output, folder=target_folder)

    if ext in {".txt", ".pdf", ".docx"}:
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp_out:
            out_path = tmp_out.name
        try:
            if ext == ".txt":
                with open(out_path, "w", encoding="utf-8") as f:
                    f.write(output)
            elif ext == ".docx":
                from docx import Document
                doc = Document()
                doc.add_paragraph(output)
                doc.save(out_path)
            elif ext == ".pdf":
                from fpdf import FPDF
                pdf = FPDF()
                pdf.add_page()
                pdf.set_auto_page_break(auto=True, margin=15)
                pdf.set_font("Arial", size=12)
                for line in output.split("\n"):
                    pdf.cell(0, 10, txt=line, ln=1)
                pdf.output(out_path)
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

        resp = send_file(out_path, as_attachment=True, download_name=f"odpoved{ext}")
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
    folder = user.nick if user else DEFAULT_MEMORY_FOLDER
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
    return jsonify(
        knowledge.search(
            query,
            folders=user.knowledge_folders if user else None,
            threshold=thresh,
        )
    )


@app.route("/knowledge/reload", methods=["POST"])
@require_auth
def knowledge_reload():
    """Reload knowledge base files and return how many chunks were loaded."""
    knowledge.reload()
    user: User | None = getattr(g, "current_user", None)
    folders = [user.nick] + user.memory_folders if user else None
    reload_memory(folders)
    print("✅ Znalosti načteny.")
    deps = dependency_status()
    if not deps["pdf"]:
        print("⚠️  PDF soubory se nenačtou – nainstalujte balíček PyPDF2")
    if not deps["docx"]:
        print("⚠️  DOCX soubory se nenačtou – nainstalujte balíček python-docx")
    return jsonify({"status": "reloaded", "chunks": len(knowledge.chunks)})


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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=FLASK_PORT)

