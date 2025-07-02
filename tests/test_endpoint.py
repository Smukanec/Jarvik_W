import os
import sys
import json
import types

class DummyResp:
    text = "ok"

    def raise_for_status(self):
        pass

sys.modules.setdefault(
    "requests", types.SimpleNamespace(post=lambda *a, **k: DummyResp())
)

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from tools import test_endpoint  # noqa: E402


def test_get_url_from_env(monkeypatch):
    monkeypatch.setenv("JARVIK_URL", "http://env")
    assert test_endpoint.get_target_url() == "http://env"


def test_get_url_from_file(tmp_path, monkeypatch):
    cfg = {"url": "http://file"}
    (tmp_path / "devlab_config.json").write_text(json.dumps(cfg))
    monkeypatch.setattr(test_endpoint, "BASE_DIR", tmp_path)
    monkeypatch.delenv("JARVIK_URL", raising=False)
    assert test_endpoint.get_target_url() == "http://file"


def test_send_request(monkeypatch):
    called = {}

    def fake_post(url, json=None):
        called["url"] = url
        called["json"] = json
        return DummyResp()

    monkeypatch.setattr(test_endpoint.requests, "post", fake_post)
    out = test_endpoint.send_test_request("http://srv", "hi")
    assert out == "ok"
    assert called["url"] == "http://srv/ask"
    assert called["json"] == {"message": "hi"}
