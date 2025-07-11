import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import rag_engine
from rag_engine import KnowledgeBase, load_knowledge, search_knowledge


@pytest.fixture
def knowledge_dir(tmp_path):
    """Create a temporary knowledge base with a text file."""
    folder = tmp_path / "kb"
    folder.mkdir()

    (folder / "info.txt").write_text("MD knowledge", encoding="utf-8")

    return folder


def test_search_knowledge_word_match():
    chunks = [
        "This is a hello text",
        "Another world piece",
        "Completely unrelated",
    ]
    result = search_knowledge("hello world", chunks, threshold=0.9)
    assert result == ["Another world piece"]


def test_search_knowledge_sequence_ratio():
    chunks = ["hello"]
    result = search_knowledge("helo", chunks)
    assert result == ["hello"]


def test_search_knowledge_punctuation_removed():
    chunks = ["hello world", "foo bar"]
    result = search_knowledge("Hello, world!", chunks, threshold=0.9)
    assert result == ["hello world"]


def test_load_knowledge(knowledge_dir):
    chunks = load_knowledge(knowledge_dir)

    assert "MD knowledge" in chunks


def test_knowledge_base_reload(knowledge_dir):
    kb = KnowledgeBase(str(knowledge_dir))
    assert any("MD knowledge" in c for c in kb.chunks)

    extra = knowledge_dir / "extra.txt"
    extra.write_text("Extra", encoding="utf-8")
    kb.reload()
    assert any("Extra" in c for c in kb.chunks)


def test_search_knowledge_czech_punctuation():
    chunks = [
        "N\u011bco o IPv6 protokolu.",
        "Jin\u00fd text.",
    ]
    result = search_knowledge("n\u011bco o ipv6?", chunks)
    assert result == ["N\u011bco o IPv6 protokolu."]


def test_search_knowledge_diacritics_normalization():
    chunks = ["DJ \u0160muk"]
    result = search_knowledge("dj smuk", chunks)
    assert result == ["DJ \u0160muk"]


def test_search_knowledge_word_boundary():
    chunks = ["GR8DJEYM2A", "dj smuk"]
    result = search_knowledge("dj", chunks)
    assert result == ["dj smuk"]


def test_knowledge_base_env_threshold(monkeypatch, knowledge_dir):
    kb = KnowledgeBase(str(knowledge_dir))
    # Without the environment variable there should be no match
    monkeypatch.delenv("RAG_THRESHOLD", raising=False)
    assert kb.search("nonsense") == []

    # A very low threshold returns results based on similarity ratio
    monkeypatch.setenv("RAG_THRESHOLD", "0.2")
    assert kb.search("nonsense") != []


def test_knowledge_base_multiple_folders(tmp_path):
    folder1 = tmp_path / "kb1"
    folder2 = tmp_path / "kb2"
    folder1.mkdir()
    folder2.mkdir()
    (folder1 / "a.txt").write_text("hello", encoding="utf-8")
    (folder2 / "b.txt").write_text("world", encoding="utf-8")

    kb = KnowledgeBase([str(folder1), str(folder2)])

    assert any("hello" in c for c in kb.chunks)
    assert any("world" in c for c in kb.chunks)


def test_knowledge_base_dj_smuk_search(tmp_path):
    """KnowledgeBase can search text with diacritics."""
    folder = tmp_path / "kb"
    folder.mkdir()
    text = (
        "DJ \u0160muk is a Czech DJ and producer known for high\u2011energy sets that "
        "make crowds dance. Despite the name similarity to some websites, DJ \u0160muk"
        " is a person, not an online platform."
    )
    (folder / "dj_smuk_info.txt").write_text(text, encoding="utf-8")

    kb = KnowledgeBase(str(folder))

    assert kb.search("DJ \u0160muk") == [text]


def test_knowledge_base_topics(tmp_path):
    folder = tmp_path / "kb"
    folder.mkdir()
    (folder / "root.txt").write_text("root", encoding="utf-8")
    sub1 = folder / "t1"
    sub1.mkdir()
    (sub1 / "a.txt").write_text("alpha", encoding="utf-8")
    sub2 = folder / "t2"
    sub2.mkdir()
    (sub2 / "b.txt").write_text("beta", encoding="utf-8")

    kb = KnowledgeBase(str(folder), topics=["t1"])
    assert kb.search("alpha") == ["alpha"]
    assert kb.search("beta") == []

    kb.reload(["t2"])
    assert kb.search("beta") == ["beta"]


def test_search_knowledge_threshold_fallback(monkeypatch):
    """search_knowledge should honour the provided threshold in fallback mode."""
    chunks = ["hello"]
    # Environment sets a very high threshold which would normally filter out
    # the result.
    monkeypatch.setenv("RAG_THRESHOLD", "1.0")
    result = search_knowledge("helo", chunks, threshold=0.8)
    assert result == ["hello"]


def test_search_knowledge_threshold_vector(monkeypatch):
    """search_knowledge should honour threshold in vector mode."""

    class DummyArray(list):
        def astype(self, _):
            return self

        @property
        def shape(self):
            return (len(self), len(self[0]))

    class DummyModel:
        def __init__(self, *_args, **_kwargs):
            pass

        def encode(self, data, **_kwargs):
            if len(data) == 1:
                return DummyArray([[0.6]])
            return DummyArray([[0.5], [0.1]])

    class DummyIndex:
        def __init__(self, _dim):
            pass

        def add(self, _arr):
            pass

        def search(self, _q, _top_k):
            return [[0.3, 0.06]], [[0, 1]]

    monkeypatch.setattr(rag_engine, "VECTOR_SUPPORT", True)
    monkeypatch.setattr(rag_engine, "SentenceTransformer", DummyModel, raising=False)
    monkeypatch.setattr(
        rag_engine,
        "faiss",
        type("faiss", (), {"IndexFlatIP": DummyIndex}),
        raising=False,
    )

    chunks = ["a", "b"]
    # High env threshold shouldn't matter because we pass a lower threshold
    monkeypatch.setenv("RAG_THRESHOLD", "1.0")
    result = search_knowledge("x", chunks, threshold=0.2)
    assert result == ["a"]
