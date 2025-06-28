import os
import glob
import re
import unicodedata
from typing import List

# Optional dependencies -------------------------------------------------------
PDF_SUPPORT = False
DOCX_SUPPORT = False
VECTOR_SUPPORT = False

try:  # pragma: no cover - environment specific
    import faiss  # type: ignore
    from sentence_transformers import SentenceTransformer  # type: ignore
    VECTOR_SUPPORT = True
except Exception:  # pragma: no cover - missing packages
    VECTOR_SUPPORT = False


def _check_optional_dependencies() -> None:
    """Set :data:`PDF_SUPPORT` and :data:`DOCX_SUPPORT` globals."""
    global PDF_SUPPORT, DOCX_SUPPORT
    try:  # pragma: no cover - availability is system dependent
        import PyPDF2  # type: ignore

        PDF_SUPPORT = True
    except Exception:
        PDF_SUPPORT = False
    try:  # pragma: no cover - availability is system dependent
        import docx  # type: ignore

        DOCX_SUPPORT = True
    except Exception:
        DOCX_SUPPORT = False


_check_optional_dependencies()

__all__ = [
    "load_txt_file",
    "load_pdf_file",
    "load_docx_file",
    "load_knowledge",
    "search_knowledge",
    "KnowledgeBase",
    "get_relevant_chunks",
    "dependency_status",
    "_strip_diacritics",
]


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _strip_diacritics(text: str) -> str:
    """Return *text* without any diacritical marks."""
    normalized = unicodedata.normalize("NFD", text)
    return "".join(c for c in normalized if not unicodedata.combining(c))


def load_txt_file(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def load_pdf_file(path: str) -> str:
    if not PDF_SUPPORT:
        raise ImportError("PyPDF2 is required to load PDF files")

    import PyPDF2  # type: ignore

    text = ""
    with open(path, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        for page in reader.pages:
            text += page.extract_text() or ""
    return text


def load_docx_file(path: str) -> str:
    if not DOCX_SUPPORT:
        raise ImportError("python-docx is required to load DOCX files")

    import docx  # type: ignore

    doc = docx.Document(path)
    return "\n".join(p.text for p in doc.paragraphs)


def _split_paragraphs(text: str) -> List[str]:
    paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
    return paragraphs


def _load_folder(folder: str) -> List[str]:
    """Return a list of non-empty knowledge paragraphs from *folder*."""
    chunks: List[str] = []
    warned_pdf = False
    warned_docx = False
    for ext in ("*.txt", "*.pdf", "*.docx"):
        if ext == "*.pdf" and not PDF_SUPPORT:
            if not warned_pdf:
                print("⚠️  PDF support disabled – install PyPDF2 to enable")
                warned_pdf = True
            continue
        if ext == "*.docx" and not DOCX_SUPPORT:
            if not warned_docx:
                print("⚠️  DOCX support disabled – install python-docx to enable")
                warned_docx = True
            continue
        for path in glob.glob(os.path.join(folder, ext)):
            try:
                if ext == "*.txt":
                    content = load_txt_file(path)
                elif ext == "*.pdf":
                    content = load_pdf_file(path)
                elif ext == "*.docx":
                    content = load_docx_file(path)
                else:  # pragma: no cover - not reachable
                    continue
                for para in _split_paragraphs(content):
                    chunks.append(para)
            except Exception as e:  # pragma: no cover - just log errors
                print(f"❌ Nelze načíst {path}: {e}")
    return chunks


def load_knowledge(folder: str) -> List[str]:
    """Backward compatible helper returning paragraphs from *folder*."""
    return _load_folder(folder)


# ---------------------------------------------------------------------------
# Vector search implementation
# ---------------------------------------------------------------------------

class KnowledgeBase:
    """Manage loading and searching local knowledge files using FAISS."""

    def __init__(self, folder: str | List[str], model_name: str | None = None):
        if not VECTOR_SUPPORT:
            raise ImportError("sentence-transformers and faiss are required")
        self.folders = [folder] if isinstance(folder, str) else list(folder)
        self.model_name = model_name or os.getenv(
            "RAG_MODEL", "paraphrase-multilingual-MiniLM-L12-v2"
        )
        self.model = SentenceTransformer(self.model_name)
        self.chunks: List[str] = []
        self.index: faiss.Index | None = None
        self.reload()

    # ------------------------------------------------------------------
    def reload(self) -> None:
        """(Re)load knowledge files and rebuild the vector index."""
        chunks: List[str] = []
        for folder in self.folders:
            chunks.extend(_load_folder(folder))
        self.chunks = chunks
        if not chunks:
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
        if self.index is None or not self.chunks:
            return []
        if threshold is None:
            env = os.getenv("RAG_THRESHOLD")
            try:
                threshold = float(env) if env is not None else 0.7
            except ValueError:  # pragma: no cover - environment may be invalid
                threshold = 0.7
        query_vec = self.model.encode(
            [query], show_progress_bar=False, normalize_embeddings=True
        )
        scores, idx = self.index.search(query_vec.astype("float32"), top_k)
        results = []
        for score, i in zip(scores[0], idx[0]):
            if score >= threshold:
                results.append(self.chunks[i])
        return results


# ---------------------------------------------------------------------------
# Convenience API
# ---------------------------------------------------------------------------

_DEFAULT_FOLDER = os.path.join(os.path.dirname(__file__), "knowledge")
_default_kb: KnowledgeBase | None = None


def _get_default_kb() -> KnowledgeBase:
    global _default_kb
    if _default_kb is None:
        _default_kb = KnowledgeBase(_DEFAULT_FOLDER)
    return _default_kb


def search_knowledge(query: str, knowledge_chunks: List[str], threshold: float = 0.7) -> List[str]:
    """Search a list of paragraphs without creating a persistent instance."""
    if not VECTOR_SUPPORT:
        raise ImportError("sentence-transformers and faiss are required")
    model = SentenceTransformer(os.getenv("RAG_MODEL", "paraphrase-multilingual-MiniLM-L12-v2"))
    embeddings = model.encode(knowledge_chunks, show_progress_bar=False, normalize_embeddings=True)
    index = faiss.IndexFlatIP(embeddings.shape[1])
    index.add(embeddings.astype("float32"))
    q_vec = model.encode([query], show_progress_bar=False, normalize_embeddings=True)
    scores, idx = index.search(q_vec.astype("float32"), min(5, len(knowledge_chunks)))
    results = []
    for score, i in zip(scores[0], idx[0]):
        if score >= threshold:
            results.append(knowledge_chunks[i])
    return results


def get_relevant_chunks(query: str, threshold: float = 0.7, top_k: int = 5) -> List[str]:
    """Search the default knowledge base for *query*."""
    kb = _get_default_kb()
    return kb.search(query, threshold=threshold, top_k=top_k)


def dependency_status() -> dict[str, bool]:
    """Return which optional dependencies are available."""

    return {
        "pdf": PDF_SUPPORT,
        "docx": DOCX_SUPPORT,
        "vector": VECTOR_SUPPORT,
    }
