import os
import sys
import pytest

pytest.importorskip("ddgs")

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from tools import web_search


def test_search_and_scrape(monkeypatch):
    class DummyDDGS:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            pass

        def text(self, q, max_results=1, **kwargs):
            for _ in range(max_results):
                yield {"href": "http://example.com"}

    class Resp:
        text = "<html><body>Hello</body></html>"

    def fake_get(url, timeout=5, headers=None):
        return Resp()

    monkeypatch.setattr(web_search, "DDGS", DummyDDGS)
    monkeypatch.setattr(web_search.requests, "get", fake_get)

    out = web_search.search_and_scrape("hello")
    assert "http://example.com" in out
    assert "Hello" in out


def test_search_and_scrape_handles_exception(monkeypatch):
    class DummyDDGS:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            pass

        def text(self, q, max_results=1, **kwargs):
            raise web_search.DDGSearchException("ratelimit")

    monkeypatch.setattr(web_search, "DDGS", DummyDDGS)

    out = web_search.search_and_scrape("boom")
    assert "\u26a0" in out
