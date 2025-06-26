import os
import sys
import importlib
import pytest

pytest.importorskip("flask")

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import rag_engine


class DummyKB:
    def __init__(self, folder=None):
        self.folder = folder
        self.chunks = ["dummy"]

    def reload(self):
        pass

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

    # Isolate memory handling
    mem = tmp_path / "mem.jsonl"
    monkeypatch.setattr(main, "memory_path", str(mem))
    monkeypatch.setattr(main, "memory_lock", main.FileLock(str(mem) + ".lock"))
    main.memory_cache = [
        {"user": "hello", "jarvik": "there"},
        {"user": "foo", "jarvik": "bar"},
    ]

    def dummy_append(user_msg, ai_response):
        main.memory_cache.append({"user": user_msg, "jarvik": ai_response})

    monkeypatch.setattr(main, "append_to_memory", dummy_append)
    monkeypatch.setattr(main, "_flush_memory_locked", lambda: None)

    # Stub network call to Ollama
    import requests

    monkeypatch.setattr(requests, "post", lambda *a, **k: DummyResp())

    main.app.config["TESTING"] = True
    return main.app.test_client()


def test_ask_endpoint(client):
    res = client.post("/ask", json={"message": "hi"})
    data = res.get_json()
    assert res.status_code == 200
    assert data["response"] == "dummy"


def test_memory_search(client):
    res = client.get("/memory/search")
    assert res.status_code == 200
    assert len(res.get_json()) == 2

    res = client.get("/memory/search", query_string={"q": "foo"})
    assert res.status_code == 200
    assert res.get_json()[0]["user"] == "foo"


def test_knowledge_search(client):
    res = client.get("/knowledge/search", query_string={"q": "test"})
    assert res.status_code == 200
    assert res.get_json() == ["kb:test"]

    res = client.get("/knowledge/search")
    assert res.status_code == 200
    assert res.get_json() == []
