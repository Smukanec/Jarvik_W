import os
import glob
import re
import unicodedata
import difflib
import logging
from typing import List

# Optional dependency --------------------------------------------------------
VECTOR_SUPPORT = False

try:  # pragma: no cover - environment specific
    import faiss  # type: ignore
    from sentence_transformers import SentenceTransformer  # type: ignore
    VECTOR_SUPPORT = True
except Exception:  # pragma: no cover - missing packages
    VECTOR_SUPPORT = False

__all__ = [
    "load_txt_file",
    "load_knowledge",
    "search_knowledge",
    "KnowledgeBase",
    "get_relevant_chunks",
    "_strip_diacritics",
]


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _strip_diacritics(text: str) -> str:
    """Return *text* without any diacritical marks."""
    normalized = unicodedata.normalize("NFD", text)
    return "".join(c for c in normalized if not unicodedata.combining(c))


def _normalize(text: str) -> str:
    """Return lowercased *text* without punctuation or diacritics."""
    text = _strip_diacritics(text)
    text = re.sub(r"[^\w\s]", " ", text)
    text = text.lower()
    return " ".join(text.split())


def _similarity(a: str, b: str) -> float:
    """Return an ad-hoc similarity score between *a* and *b*."""
    norm_a = _normalize(a)
    norm_b = _normalize(b)
    if norm_a:
        if " " in norm_a:
            if norm_a in norm_b:
                return 1.0
        elif norm_a in norm_b.split():
            return 1.0
    ratio = difflib.SequenceMatcher(None, norm_a, norm_b).ratio()
    if set(norm_a.split()) & set(norm_b.split()):
        ratio += 0.5
    return min(ratio, 1.0)


def load_txt_file(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()





def _split_paragraphs(text: str) -> List[str]:
    paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
    return paragraphs


def _load_folder(folder: str) -> List[str]:
    """Return a list of non-empty knowledge paragraphs from *folder*."""
    chunks: List[str] = []
    for path in glob.glob(os.path.join(folder, "*.txt")):
        try:
            content = load_txt_file(path)
            for para in _split_paragraphs(content):
                chunks.append(para)
        except Exception as e:  # pragma: no cover - just log errors
            logging.error("❌ Nelze načíst %s: %s", path, e)
    return chunks


def load_knowledge(folder: str) -> List[str]:
    """Backward compatible helper returning paragraphs from *folder*."""
    return _load_folder(folder)


# ---------------------------------------------------------------------------
# Vector search implementation
# ---------------------------------------------------------------------------

class KnowledgeBase:
    """Manage loading and searching local knowledge files using FAISS."""

    def __init__(
        self,
        folder: str | List[str],
        model_name: str | None = None,
        topics: List[str] | None = None,
    ):
        self.folders = [folder] if isinstance(folder, str) else list(folder)
        self.model_name = model_name or os.getenv(
            "RAG_MODEL", "paraphrase-multilingual-MiniLM-L12-v2"
        )
        if VECTOR_SUPPORT:
            self.model = SentenceTransformer(self.model_name)
        else:  # pragma: no cover - fallback mode
            self.model = None
        self.chunks: List[str] = []
        self.index: faiss.Index | None = None
        self.topics: List[str] | None = topics
        self.reload(topics)

    # ------------------------------------------------------------------
    def reload(self, topics: List[str] | None = None) -> None:
        """(Re)load knowledge files and rebuild the vector index.

        If *topics* is provided, only subdirectories matching those topics
        are loaded. Otherwise, only files directly in the folders are used.
        """
        if topics is not None:
            self.topics = topics
        topics = self.topics

        chunks: List[str] = []
        for folder in self.folders:
            if topics:
                for topic in topics:
                    sub = os.path.join(folder, topic)
                    if os.path.isdir(sub):
                        chunks.extend(_load_folder(sub))
            else:
                chunks.extend(_load_folder(folder))
        self.chunks = chunks
        if not VECTOR_SUPPORT or not chunks or self.model is None:
            self.index = None
            return
        embeddings = self.model.encode(
            chunks, show_progress_bar=False, normalize_embeddings=True
        )
        dim = embeddings.shape[1]
        self.index = faiss.IndexFlatIP(dim)
        self.index.add(embeddings.astype("float32"))

    # ------------------------------------------------------------------
    def search(
        self,
        query: str,
        threshold: float | None = None,
        top_k: int = 5,
    ) -> List[str]:
        """Return up to *top_k* relevant paragraphs for *query*."""
        if not self.chunks:
            return []

        def _env_threshold() -> float:
            env = os.getenv("RAG_THRESHOLD")
            try:
                return float(env) if env is not None else 0.7
            except ValueError:  # pragma: no cover - environment may be invalid
                return 0.7

        if VECTOR_SUPPORT and self.index is not None and self.model is not None:
            if threshold is None:
                threshold = _env_threshold()
            query_vec = self.model.encode(
                [query], show_progress_bar=False, normalize_embeddings=True
            )
            scores, idx = self.index.search(query_vec.astype("float32"), top_k)
            results = []
            for score, i in zip(scores[0], idx[0]):
                if score >= threshold:
                    results.append(self.chunks[i])
            return results

        # Fallback string matching
        threshold = _env_threshold()
        scored = [
            (_similarity(query, chunk), chunk) for chunk in self.chunks
        ]
        scored = [c for c in scored if c[0] >= threshold]
        scored.sort(key=lambda x: x[0], reverse=True)
        return [c[1] for c in scored[:top_k]]


# ---------------------------------------------------------------------------
# Convenience API
# ---------------------------------------------------------------------------

_DEFAULT_FOLDER = os.getenv(
    "KNOWLEDGE_DIR",
    os.path.join(os.path.dirname(__file__), "knowledge"),
)
_default_kb: KnowledgeBase | None = None


def _get_default_kb() -> KnowledgeBase:
    global _default_kb
    if _default_kb is None:
        _default_kb = KnowledgeBase(_DEFAULT_FOLDER)
    return _default_kb


def search_knowledge(
    query: str, knowledge_chunks: List[str], threshold: float | None = None
) -> List[str]:
    """Search a list of paragraphs without creating a persistent instance."""

    def _env_threshold() -> float:
        env = os.getenv("RAG_THRESHOLD")
        try:
            return float(env) if env is not None else 0.7
        except ValueError:  # pragma: no cover - environment may be invalid
            return 0.7

    if VECTOR_SUPPORT:
        if threshold is None:
            threshold = _env_threshold()
        model = SentenceTransformer(
            os.getenv("RAG_MODEL", "paraphrase-multilingual-MiniLM-L12-v2")
        )
        embeddings = model.encode(
            knowledge_chunks, show_progress_bar=False, normalize_embeddings=True
        )
        index = faiss.IndexFlatIP(embeddings.shape[1])
        index.add(embeddings.astype("float32"))
        q_vec = model.encode(
            [query], show_progress_bar=False, normalize_embeddings=True
        )
        scores, idx = index.search(
            q_vec.astype("float32"), min(5, len(knowledge_chunks))
        )
        results = []
        for score, i in zip(scores[0], idx[0]):
            if score >= threshold:
                results.append(knowledge_chunks[i])
        return results

    # Fallback string matching honoring the threshold argument
    if threshold is None:
        threshold = _env_threshold()
    scored = [(_similarity(query, c), c) for c in knowledge_chunks]
    scored = [c for c in scored if c[0] >= threshold]
    scored.sort(key=lambda x: x[0], reverse=True)
    return [c[1] for c in scored]


def get_relevant_chunks(query: str, threshold: float = 0.7, top_k: int = 5) -> List[str]:
    """Search the default knowledge base for *query*."""
    kb = _get_default_kb()
    return kb.search(query, threshold=threshold, top_k=top_k)


