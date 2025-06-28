import os
import sys
import pytest

pytest.importorskip("duckduckgo_search")

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from tools import web_search


def test_search_and_scrape(monkeypatch):
    def fake_ddg(q, max_results=1):
        return [{"href": "http://example.com"}]

    class Resp:
        text = "<html><body>Hello</body></html>"

    def fake_get(url, timeout=5, headers=None):
        return Resp()

    monkeypatch.setattr(web_search, "ddg", fake_ddg)
    monkeypatch.setattr(web_search.requests, "get", fake_get)

    out = web_search.search_and_scrape("hello")
    assert "http://example.com" in out
    assert "Hello" in out
