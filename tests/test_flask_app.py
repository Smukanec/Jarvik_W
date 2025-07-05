import os
import sys
import importlib
import base64
import io
import pytest

pytest.importorskip("flask")

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import rag_engine


class DummyKB:
    last_topics = None

    def __init__(self, folder=None, model_name=None, topics=None):
        self.folder = folder
        self.model_name = model_name
        self.folders = [folder] if folder and not isinstance(folder, list) else folder
        self.chunks = ["dummy"]
        self.topics = topics
        DummyKB.last_topics = topics

    def reload(self, topics=None):
        DummyKB.last_topics = topics
        if topics is not None:
            self.topics = topics

    def search(self, query, threshold=None):
        return [f"kb:{query}"]


class DummyResp:
    def raise_for_status(self):
        pass

    def json(self):
        return {"response": "dummy"}


@pytest.fixture()
def client(monkeypatch, tmp_path):
    # Use the dummy knowledge base during import
    monkeypatch.setattr(rag_engine, "KnowledgeBase", DummyKB)
    main = importlib.import_module("main")
    importlib.reload(main)

    # Replace the global knowledge instance
    main.knowledge = DummyKB()
    main.user_knowledge = {}

    # Enable authentication with a dummy user
    import auth
    user = auth.User(
        nick="bob",
        password_hash=auth.hash_password("pw"),
        knowledge_folders=["private"],
        memory_folders=["shared"],
    )
    main.users = {"bob": user}
    main.AUTH_ENABLED = True
    main.TOKENS = {}

    # Isolate memory handling
    monkeypatch.setattr(main, "MEMORY_DIR", str(tmp_path))
    main.memory_caches = {
        main.DEFAULT_MEMORY_FOLDER: [
            {"user": "hello", "jarvik": "there"},
            {"user": "foo", "jarvik": "bar"},
        ]
    }
    main.memory_locks = {}
    main.memory_caches["shared"] = [
        {"user": "shared question", "jarvik": "shared answer"}
    ]

    monkeypatch.setattr(main, "ANSWER_DIR", str(tmp_path / "answers"))
    os.makedirs(main.ANSWER_DIR, exist_ok=True)

    def dummy_append(
        user_msg,
        ai_response,
        folder=main.DEFAULT_MEMORY_FOLDER,
        *,
        context=None,
        date=None,
        time=None,
        attachments=None,
    ):
        cache = main.memory_caches.setdefault(folder, [])
        entry = {"user": user_msg, "jarvik": ai_response}
        if context:
            entry["context"] = context
        if date:
            entry["date"] = date
        if time:
            entry["time"] = time
        if attachments:
            entry["attachments"] = attachments
        cache.append(entry)

    monkeypatch.setattr(main, "append_to_memory", dummy_append)
    monkeypatch.setattr(main, "_flush_memory_locked", lambda folder: None)

    # Stub network call to Ollama
    import requests

    post_calls = []

    def fake_post(url, *a, **k):
        post_calls.append((url, k))
        return DummyResp()

    monkeypatch.setattr(requests, "post", fake_post)
    main._post_calls = post_calls

    main.app.config["TESTING"] = True
    return main.app.test_client()


def _auth():
    cred = base64.b64encode(b"bob:pw").decode()
    return {"Authorization": f"Basic {cred}"}


def test_ask_endpoint(client):
    res = client.post("/ask", json={"message": "hi"}, headers=_auth())
    data = res.get_json()
    assert res.status_code == 200
    assert data["response"] == "dummy"


def test_ask_openai(client):
    import main
    headers = _auth()
    headers["X-API-Key"] = "key"
    res = client.post("/ask", json={"message": "hi"}, headers=headers)
    assert res.status_code == 200
    assert main._post_calls[-1][0] == main.API_URL


def test_memory_search(client):
    res = client.get("/memory/search", headers=_auth())
    assert res.status_code == 200
    assert len(res.get_json()) == 2

    res = client.get("/memory/search", query_string={"q": "foo"}, headers=_auth())
    assert res.status_code == 200
    assert res.get_json()[0]["user"] == "foo"


def test_memory_search_diacritics(client):
    import main
    main.memory_caches[main.DEFAULT_MEMORY_FOLDER].append({
        "user": "DJ \u0160muk",
        "jarvik": "bio"
    })

    res = client.get("/memory/search", query_string={"q": "dj smuk"}, headers=_auth())
    assert res.status_code == 200
    assert any("\u0160muk" in e["user"] for e in res.get_json())


def test_memory_search_with_invalid_line(client):
    import main
    import os
    import json

    from datetime import datetime
    path = os.path.join(main.MEMORY_DIR, "public.jsonl")
    ts = datetime.utcnow().isoformat()
    with open(path, "w", encoding="utf-8") as f:
        f.write(json.dumps({"timestamp": ts, "role": "user", "message": "ok"}) + "\n")
        f.write(json.dumps({"timestamp": ts, "role": "assistant", "message": "good"}) + "\n")
        f.write("{bad json}\n")
        f.write(json.dumps({"timestamp": ts, "role": "user", "message": "fine"}) + "\n")
        f.write(json.dumps({"timestamp": ts, "role": "assistant", "message": "yes"}) + "\n")

    main.reload_memory()

    res = client.get("/memory/search", headers=_auth())
    assert res.status_code == 200
    assert len(res.get_json()) == 3


def test_knowledge_search(client):
    res = client.get("/knowledge/search", query_string={"q": "test"}, headers=_auth())
    assert res.status_code == 200
    assert res.get_json() == ["kb:test"]

    res = client.get("/knowledge/search", headers=_auth())
    assert res.status_code == 200
    assert res.get_json() == []


def test_knowledge_search_topics(client):
    DummyKB.last_topics = None
    res = client.get(
        "/knowledge/search",
        query_string={"q": "x", "topics": "t1,t2"},
        headers=_auth(),
    )
    assert res.status_code == 200
    assert DummyKB.last_topics == ["t1", "t2"]


def test_login_and_token(client):
    import main
    res = client.post("/login", json={"nick": "bob", "password": "pw"})
    assert res.status_code == 200
    token = res.get_json()["token"]
    assert main.TOKENS[token] == "bob"


def test_per_user_memory(client):
    import main
    client.post("/ask", json={"message": "hi"}, headers=_auth())
    assert "bob" in main.memory_caches
    assert main.memory_caches["bob"][-1]["user"] == "hi"


def test_public_memory_when_flag_false(client):
    import main
    client.post("/ask", json={"message": "pub", "private": False}, headers=_auth())
    assert main.memory_caches[main.DEFAULT_MEMORY_FOLDER][-1]["user"] == "pub"


def test_public_memory_when_flag_false_web(client, monkeypatch):
    import main
    monkeypatch.setattr(main, "search_and_scrape", lambda q: "web")
    client.post(
        "/ask_web",
        json={"message": "pub2", "private": False},
        headers=_auth(),
    )
    assert main.memory_caches[main.DEFAULT_MEMORY_FOLDER][-1]["user"] == "pub2"


def test_public_memory_when_flag_false_file(client):
    import main
    res = client.post(
        "/ask_file",
        data={"message": "pubf", "private": "0"},
        headers=_auth(),
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data["response"] == "dummy"
    assert main.memory_caches[main.DEFAULT_MEMORY_FOLDER][-1]["user"] == "pubf"


def test_ask_file_save_creates_file(client):
    import main
    import os
    res = client.post(
        "/ask_file",
        data={"message": "save this", "save": "1"},
        headers=_auth(),
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data["response"] == "dummy"
    assert "download_url" in data
    fname = data["download_url"].split("/")[-1]
    assert os.path.exists(os.path.join(main.ANSWER_DIR, fname))
    entry = main.memory_caches["bob"][-1]
    assert entry["user"] == "save this"
    assert "odpověď uložena" in entry["jarvik"]
    assert "attachments" not in entry


def test_per_user_knowledge_folders(client):
    import main
    client.get("/knowledge/search", query_string={"q": "hello"}, headers=_auth())
    kb = main.user_knowledge["bob"]
    assert main.PUBLIC_KNOWLEDGE_FOLDER in kb.folder[0]
    assert os.path.join(main.PUBLIC_KNOWLEDGE_FOLDER, "private") in kb.folder[1]
    assert os.path.join(main.MEMORY_DIR, "bob", "private_knowledge") in kb.folder[2]


def test_ask_web_endpoint(client, monkeypatch):
    import main
    monkeypatch.setattr(main, "search_and_scrape", lambda q: "web")
    res = client.post("/ask_web", json={"message": "hi"}, headers=_auth())
    assert res.status_code == 200
    assert res.get_json()["response"] == "dummy"


def test_ask_auto_web_search(client, monkeypatch):
    import main
    calls = []

    def fake_search(q):
        calls.append(q)
        return "web"

    monkeypatch.setattr(main, "search_and_scrape", fake_search)
    monkeypatch.setattr(main, "should_use_web_search", lambda m: True)

    res = client.post("/ask", json={"message": "hi"}, headers=_auth())
    assert res.status_code == 200
    assert calls
    call = main._post_calls[-1][1]["json"]
    prompt = call.get("prompt") or call["messages"][0]["content"]
    assert "web" in prompt


def test_memory_add(client):
    import main
    res = client.post(
        "/memory/add",
        json={
            "user": "q",
            "jarvik": "a",
            "context": "ctx",
            "attachments": ["f.txt"],
        },
        headers=_auth(),
    )
    assert res.status_code == 200
    entry = main.memory_caches["bob"][-1]
    assert entry["user"] == "q"
    assert entry["jarvik"] == "a"
    assert entry.get("context") == "ctx"
    assert entry.get("attachments") == ["f.txt"]


def test_memory_add_public(client):
    import main
    client.post(
        "/memory/add",
        json={"user": "qp", "jarvik": "ap", "private": False},
        headers=_auth(),
    )
    assert main.memory_caches[main.DEFAULT_MEMORY_FOLDER][-1]["user"] == "qp"


def test_knowledge_reload(client, monkeypatch):
    import main
    called = []

    def fake_reload():
        called.append(True)

    main.knowledge.reload = fake_reload
    res = client.post("/knowledge/reload", headers=_auth())
    assert res.status_code == 200
    assert called


def test_model_switch(client, monkeypatch):
    import main
    called = []

    def fake_popen(args):
        called.append(args)
        class D:
            pass
        return D()

    monkeypatch.setattr(main.subprocess, "Popen", fake_popen)
    res = client.post("/model", json={"model": "foo"}, headers=_auth())
    assert res.status_code == 200
    assert called


def test_feedback_endpoint(client):
    import main
    import os
    import json

    fb_path = os.path.join(main.MEMORY_DIR, "bob", "log.jsonl")
    if os.path.exists(fb_path):
        os.unlink(fb_path)

    res = client.post(
        "/feedback",
        json={"agree": True, "question": "q", "answer": "a", "correction": "c"},
        headers=_auth(),
    )
    assert res.status_code == 200
    assert not os.path.exists(fb_path)

    res = client.post(
        "/feedback",
        json={"agree": False, "question": "q", "answer": "a", "correction": "c"},
        headers=_auth(),
    )
    assert res.status_code == 200
    assert os.path.exists(fb_path)
    with open(fb_path, "r", encoding="utf-8") as f:
        lines = [json.loads(line) for line in f if line.strip()]
    assert len(lines) == 1
    entry = lines[0]
    assert entry["type"] == "feedback"
    assert entry["agree"] is False
    assert entry["question"] == "q"
    assert entry["answer"] == "a"
    assert entry["correction"] == "c"


def test_feedback_entry_written(client):
    """POSTing disagreeing feedback should create a private entry."""
    import main
    import os
    import json

    fb_path = os.path.join(main.MEMORY_DIR, "bob", "log.jsonl")
    if os.path.exists(fb_path):
        os.unlink(fb_path)

    res = client.post(
        "/feedback",
        json={"agree": False, "question": "q", "answer": "a", "correction": "c"},
        headers=_auth(),
    )
    assert res.status_code == 200
    assert os.path.exists(fb_path)
    with open(fb_path, "r", encoding="utf-8") as f:
        data = [json.loads(line) for line in f if line.strip()]
    assert data == [
        {
            "type": "feedback",
            "agree": False,
            "question": "q",
            "answer": "a",
            "correction": "c",
        }
    ]


def test_get_corrections_and_prompt_notes(client):
    import main
    import os
    import json

    fb_path = os.path.join(main.MEMORY_DIR, "bob", "log.jsonl")
    os.makedirs(os.path.dirname(fb_path), exist_ok=True)
    with open(fb_path, "w", encoding="utf-8") as f:
        f.write(json.dumps({"original_question": "hi", "correction": "answer"}) + "\n")

    res = client.post("/ask", json={"message": "hi"}, headers=_auth())
    assert res.status_code == 200

    call = main._post_calls[-1][1]["json"]
    if "prompt" in call:
        prompt = call["prompt"]
    else:
        prompt = call["messages"][0]["content"]
    assert "Poznámka: answer" in prompt


def test_prompt_notes_with_mocked_file_and_similarity(client, monkeypatch):
    """Corrections are appended to the prompt when similarity matches."""
    import main
    import builtins
    import io
    import json
    import os

    file_data = json.dumps({"original_question": "hi", "correction": "note"}) + "\n"
    open_calls = []
    real_open = builtins.open

    def fake_open(path, mode="r", *args, **kwargs):
        if path.endswith("log.jsonl") and "r" in mode:
            open_calls.append(path)
            return io.StringIO(file_data)
        return real_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", fake_open)
    monkeypatch.setattr(main.os.path, "exists", lambda p: True if p.endswith("log.jsonl") else os.path.exists(p))

    class DummyMatcher:
        def __init__(self, *args, **kwargs):
            pass

        def ratio(self):
            return 1.0

    monkeypatch.setattr(main.difflib, "SequenceMatcher", DummyMatcher)

    res = client.post("/ask", json={"message": "hi"}, headers=_auth())
    assert res.status_code == 200

    call = main._post_calls[-1][1]["json"]
    prompt = call.get("prompt") or call["messages"][0]["content"]
    assert "Poznámka: note" in prompt
    assert open_calls


def test_knowledge_upload(client, monkeypatch, tmp_path):
    import main
    monkeypatch.setattr(main, "PUBLIC_KNOWLEDGE_FOLDER", str(tmp_path))
    called = []
    main.knowledge.folder = str(tmp_path)
    def fake_reload():
        called.append(True)
    main.knowledge.reload = fake_reload
    data = {
        "file": (io.BytesIO(b"hello"), "info.txt"),
        "private": "0",
    }
    res = client.post(
        "/knowledge/upload",
        data=data,
        headers=_auth(),
        content_type="multipart/form-data",
    )
    assert res.status_code == 200
    assert called
    assert os.path.exists(os.path.join(tmp_path, "info.txt"))


def test_knowledge_upload_sanitizes_filename(client, monkeypatch, tmp_path):
    import main
    monkeypatch.setattr(main, "PUBLIC_KNOWLEDGE_FOLDER", str(tmp_path))
    called = []
    main.knowledge.folder = str(tmp_path)

    def fake_reload():
        called.append(True)

    main.knowledge.reload = fake_reload
    data = {
        "file": (io.BytesIO(b"hello"), "../evil.txt"),
        "private": "0",
    }
    res = client.post(
        "/knowledge/upload",
        data=data,
        headers=_auth(),
        content_type="multipart/form-data",
    )
    assert res.status_code == 200
    assert called
    fname = res.get_json()["file"]
    # ensure filename is sanitized and file saved inside target folder
    assert os.path.sep not in fname
    assert os.path.exists(os.path.join(tmp_path, fname))


def test_knowledge_upload_records_description(client, monkeypatch, tmp_path):
    import main
    monkeypatch.setattr(main, "PUBLIC_KNOWLEDGE_FOLDER", str(tmp_path))
    called = []
    main.knowledge.folder = str(tmp_path)

    def fake_reload():
        called.append(True)

    main.knowledge.reload = fake_reload
    data = {
        "file": (io.BytesIO(b"hello"), "note.txt"),
        "private": "0",
        "description": "some info",
    }
    res = client.post(
        "/knowledge/upload",
        data=data,
        headers=_auth(),
        content_type="multipart/form-data",
    )
    assert res.status_code == 200
    assert called
    entry = main.memory_caches["bob"][-1]
    assert "Byl vložen znalostní soubor" in entry["jarvik"]
    assert "some info" in entry["jarvik"]
    assert entry.get("attachments") == ["note.txt"]


def test_knowledge_upload_creates_meta(client, monkeypatch, tmp_path):
    import main
    import os
    import json

    monkeypatch.setattr(main, "PUBLIC_KNOWLEDGE_FOLDER", str(tmp_path))
    called = []
    main.knowledge.folder = str(tmp_path)

    def fake_reload():
        called.append(True)

    main.knowledge.reload = fake_reload
    data = {
        "file": (io.BytesIO(b"hello"), "meta.txt"),
        "private": "0",
        "topic": "technologie",
    }
    res = client.post(
        "/knowledge/upload",
        data=data,
        headers=_auth(),
        content_type="multipart/form-data",
    )
    assert res.status_code == 200
    assert called
    fname = res.get_json()["file"]
    meta_path = os.path.join(
        tmp_path, os.path.splitext(fname)[0] + ".meta.json"
    )
    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)
    assert meta["uploader"] == "bob"
    assert meta["proposed_topic"] == "technologie"
    assert meta["topic"] == "technologie"
    assert meta["status"] == "pending_approval"
    assert meta["public"] is True


def test_knowledge_upload_suggests_topic(client, monkeypatch, tmp_path):
    import main
    import os
    import json

    index = {"dogs": "d", "cats": "c"}
    os.makedirs(tmp_path, exist_ok=True)
    with open(os.path.join(tmp_path, "_index.json"), "w", encoding="utf-8") as f:
        json.dump(index, f)

    monkeypatch.setattr(main, "PUBLIC_KNOWLEDGE_FOLDER", str(tmp_path))
    called = []
    main.knowledge.folder = str(tmp_path)

    def fake_reload():
        called.append(True)

    main.knowledge.reload = fake_reload
    data = {
        "file": (io.BytesIO(b"dogs are great"), "info.txt"),
        "private": "0",
    }
    res = client.post(
        "/knowledge/upload",
        data=data,
        headers=_auth(),
        content_type="multipart/form-data",
    )
    assert res.status_code == 200
    assert called
    fname = res.get_json()["file"]
    meta_path = os.path.join(
        tmp_path, os.path.splitext(fname)[0] + ".meta.json"
    )
    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)
    assert meta["proposed_topic"] == "dogs"
    assert meta["topic"] == ""


def test_private_knowledge_upload_saves_to_memory(client, monkeypatch, tmp_path):
    import main
    import json

    pub = tmp_path / "pub"
    pub.mkdir()
    mem = tmp_path / "mem"
    monkeypatch.setattr(main, "PUBLIC_KNOWLEDGE_FOLDER", str(pub))
    monkeypatch.setattr(main, "MEMORY_DIR", str(mem))
    main.knowledge.folder = str(pub)
    main.knowledge.reload = lambda: None

    data = {"file": (io.BytesIO(b"hello"), "priv.txt"), "private": "1"}
    res = client.post(
        "/knowledge/upload",
        data=data,
        headers=_auth(),
        content_type="multipart/form-data",
    )
    assert res.status_code == 200
    fname = res.get_json()["file"]

    dest_file = mem / "bob" / "private_knowledge" / fname
    dest_meta = dest_file.with_suffix(".meta.json")
    assert dest_file.exists()
    assert dest_meta.exists()
    with open(dest_meta, "r", encoding="utf-8") as f:
        meta = json.load(f)
    assert meta["status"] == "private"


def test_knowledge_topics(client, monkeypatch, tmp_path):
    import main
    import os
    import json

    data = {"a": "b"}
    os.makedirs(tmp_path, exist_ok=True)
    with open(os.path.join(tmp_path, "_index.json"), "w", encoding="utf-8") as f:
        json.dump(data, f)

    monkeypatch.setattr(main, "PUBLIC_KNOWLEDGE_FOLDER", str(tmp_path))

    res = client.get("/knowledge/topics", headers=_auth())
    assert res.status_code == 200
    assert res.get_json() == data


def test_memory_delete_by_keyword(client, tmp_path):
    import main
    import json

    path, _ = main._ensure_memory(main.DEFAULT_MEMORY_FOLDER)
    with open(path, "w", encoding="utf-8") as f:
        f.write(json.dumps({"user": "remove", "jarvik": "x"}) + "\n")
        f.write(json.dumps({"user": "keep", "jarvik": "y"}) + "\n")
    main.reload_memory()

    res = client.post(
        "/memory/delete",
        json={"keyword": "remove"},
        headers=_auth(),
    )
    assert res.status_code == 200
    assert "1" in res.get_json()["message"]
    entries = main.load_memory()
    assert all("remove" not in e["user"] for e in entries)


def test_read_memory_file_new_format(monkeypatch, tmp_path):
    import main
    import os
    import json
    from datetime import datetime

    monkeypatch.setattr(main, "MEMORY_DIR", str(tmp_path))
    path = os.path.join(main.MEMORY_DIR, "public.jsonl")
    ts = datetime.utcnow().isoformat()
    with open(path, "w", encoding="utf-8") as f:
        f.write(json.dumps({"timestamp": ts, "role": "user", "message": "q"}) + "\n")
        f.write(json.dumps({"timestamp": ts, "role": "assistant", "message": "a"}) + "\n")

    entries = main._read_memory_file(main.DEFAULT_MEMORY_FOLDER)
    assert entries == [{"user": "q", "jarvik": "a"}]


def test_knowledge_pending_and_approve(client, monkeypatch, tmp_path):
    import main
    import os
    import json

    monkeypatch.setattr(main, "PUBLIC_KNOWLEDGE_FOLDER", str(tmp_path))
    main.knowledge.folder = str(tmp_path)
    main.knowledge.reload = lambda: None

    data = {"file": (io.BytesIO(b"x"), "pend.txt"), "private": "0"}
    res = client.post(
        "/knowledge/upload",
        data=data,
        headers=_auth(),
        content_type="multipart/form-data",
    )
    assert res.status_code == 200
    fname = res.get_json()["file"]

    res = client.get("/knowledge/pending", headers=_auth())
    assert res.status_code == 200
    pending = res.get_json()
    assert len(pending) == 1
    assert pending[0]["file"] == fname

    res = client.post("/knowledge/approve", json={"file": fname}, headers=_auth())
    assert res.status_code == 200

    meta_path = os.path.join(tmp_path, os.path.splitext(fname)[0] + ".meta.json")
    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)
    assert meta["status"] == "approved"

    res = client.get("/knowledge/pending", headers=_auth())
    assert res.status_code == 200
    assert res.get_json() == []


def test_knowledge_reject_moves_file(client, monkeypatch, tmp_path):
    import main
    import json

    pub = tmp_path / "pub"
    pub.mkdir()
    monkeypatch.setattr(main, "PUBLIC_KNOWLEDGE_FOLDER", str(pub))
    monkeypatch.setattr(main, "MEMORY_DIR", str(tmp_path / "mem"))
    main.knowledge.folder = str(pub)
    main.knowledge.reload = lambda: None

    data = {"file": (io.BytesIO(b"x"), "rej.txt"), "private": "0"}
    res = client.post(
        "/knowledge/upload",
        data=data,
        headers=_auth(),
        content_type="multipart/form-data",
    )
    assert res.status_code == 200
    fname = res.get_json()["file"]

    res = client.post("/knowledge/reject", json={"file": fname}, headers=_auth())
    assert res.status_code == 200

    dest_file = tmp_path / "mem" / "bob" / "private_knowledge" / fname
    dest_meta = dest_file.with_suffix(".meta.json")
    assert dest_file.exists()
    assert dest_meta.exists()
    with open(dest_meta, "r", encoding="utf-8") as f:
        meta = json.load(f)
    assert meta["status"] == "rejected"


def test_knowledge_invalid_path_rejected_and_approved(client):
    """Invalid relative paths should return a 400 response."""
    invalid = "../evil.txt"

    res = client.post("/knowledge/approve", json={"file": invalid}, headers=_auth())
    assert res.status_code == 400

    res = client.post("/knowledge/reject", json={"file": invalid}, headers=_auth())
    assert res.status_code == 400



def test_mobile_page(client):
    res = client.get("/mobile")
    assert res.status_code == 200
    assert "text/html" in res.content_type
    assert "<!DOCTYPE html>" in res.get_data(as_text=True)

