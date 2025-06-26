from flask import Flask, request, jsonify, send_file, after_this_request
from rag_engine import (
    KnowledgeBase,
    load_txt_file,
    load_pdf_file,
    load_docx_file,
)
import json
import os
import tempfile
import subprocess
from filelock import FileLock

# Allow custom model via environment variable
MODEL_NAME = os.getenv("MODEL_NAME", "gemma:2b")
# Allow choosing the Flask port via environment variable
FLASK_PORT = int(os.getenv("FLASK_PORT", 8010))
# Base URL for the Ollama server
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")

# Set base directory relative to this file
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
memory_path = os.path.join(BASE_DIR, "memory", "public.jsonl")
# Lock file to coordinate memory writes across processes
memory_lock = FileLock(f"{memory_path}.lock")
# Ensure memory directory and file exist
os.makedirs(os.path.dirname(memory_path), exist_ok=True)
open(memory_path, "a", encoding="utf-8").close()

# Jarvik now keeps conversation history indefinitely.
# To enforce a limit, set the ``MAX_MEMORY_ENTRIES`` environment variable
# manually before launching the application.
limit_env = os.getenv("MAX_MEMORY_ENTRIES")
MAX_MEMORY_ENTRIES = int(limit_env) if limit_env and limit_env.isdigit() else None

app = Flask(__name__)

# Načti znalosti při startu
knowledge = KnowledgeBase(os.path.join(BASE_DIR, "knowledge"))
print("✅ Znalosti načteny.")

def _read_memory_file():
    """Return memory entries loaded from disk respecting the limit."""
    if os.path.exists(memory_path):
        with open(memory_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            if MAX_MEMORY_ENTRIES:
                lines = lines[-MAX_MEMORY_ENTRIES:]
            return [json.loads(line) for line in lines if line.strip()]
    return []

# Cache memory at startup
memory_cache = _read_memory_file()

def load_memory():
    """Return the cached conversation memory."""
    return memory_cache

def reload_memory() -> list[dict]:
    """Reload conversation history from disk into the cache."""
    global memory_cache
    memory_cache = _read_memory_file()
    return memory_cache

def append_to_memory(user_msg, ai_response):
    """Append a new exchange to the in-memory cache and persist it."""
    global memory_cache
    entry = {"user": user_msg, "jarvik": ai_response}
    with memory_lock:
        memory_cache.append(entry)
        if MAX_MEMORY_ENTRIES and len(memory_cache) > MAX_MEMORY_ENTRIES:
            memory_cache = memory_cache[-MAX_MEMORY_ENTRIES:]
        _flush_memory_locked()

def flush_memory() -> None:
    """Write the cached memory to disk respecting the entry limit."""
    with memory_lock:
        _flush_memory_locked()

def _flush_memory_locked() -> None:
    """Write memory_cache to disk. Caller must hold ``memory_lock``."""
    lines = (
        memory_cache[-MAX_MEMORY_ENTRIES:] if MAX_MEMORY_ENTRIES else memory_cache
    )
    with open(memory_path, "w", encoding="utf-8") as f:
        for item in lines:
            f.write(json.dumps(item) + "\n")

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
def ask():
    debug_log = []
    data = request.get_json(silent=True)
    message = (data or {}).get("message", "")

    memory_context = load_memory()
    debug_log.append(f"🧠 Paměť: {len(memory_context)} záznamů")

    rag_context = knowledge.search(message)
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

    append_to_memory(message, output)



@app.route("/ask_file", methods=["POST"])
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

    memory_context = load_memory()
    debug_log.append(f"🧠 Paměť: {len(memory_context)} záznamů")

    rag_context = knowledge.search(message)
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

    append_to_memory(message, output)

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
def memory_add():
    data = request.get_json(silent=True) or {}
    user_msg = data.get("user")
    jarvik_msg = data.get("jarvik")
    if not user_msg or not jarvik_msg:
        return jsonify({"error": "user and jarvik required"}), 400
    append_to_memory(user_msg, jarvik_msg)
    return jsonify({"status": "ok"})

@app.route("/memory/search")
def memory_search():
    query = request.args.get("q", "")
    memory_entries = load_memory()
    if not query:
        return jsonify(memory_entries[-5:])
    return jsonify(search_memory(query, memory_entries))

@app.route("/knowledge/search")
def knowledge_search():
    query = request.args.get("q", "")
    if not query:
        return jsonify([])
    return jsonify(knowledge.search(query))


@app.route("/knowledge/reload", methods=["POST"])
def knowledge_reload():
    """Reload knowledge base files and return how many chunks were loaded."""
    knowledge.reload()
    reload_memory()
    print("✅ Znalosti načteny.")
    return jsonify({"status": "reloaded", "chunks": len(knowledge.chunks)})


@app.route("/model", methods=["GET", "POST"])
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

