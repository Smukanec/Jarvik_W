import os
import glob
import re
import unicodedata
from difflib import SequenceMatcher

# Flags indicating whether optional dependencies are available
PDF_SUPPORT = False
DOCX_SUPPORT = False


def _check_optional_dependencies() -> None:
    """Set :data:`PDF_SUPPORT` and :data:`DOCX_SUPPORT` globals."""
    global PDF_SUPPORT, DOCX_SUPPORT
    try:  # pragma: no cover - availability is system dependent
        import PyPDF2  # noqa: F401

        PDF_SUPPORT = True
    except Exception:
        PDF_SUPPORT = False
    try:  # pragma: no cover - availability is system dependent
        import docx  # noqa: F401

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
    "dependency_status",
]


def _strip_diacritics(text: str) -> str:
    """Return *text* without any diacritical marks."""
    normalized = unicodedata.normalize("NFD", text)
    return "".join(c for c in normalized if not unicodedata.combining(c))

def load_txt_file(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def load_pdf_file(path):
    try:
        import PyPDF2
    except ImportError:
        raise ImportError("PyPDF2 is required to load PDF files")

    text = ""
    with open(path, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        for page in reader.pages:
            text += page.extract_text() or ""
    return text

def load_docx_file(path):
    try:
        import docx
    except ImportError:
        raise ImportError("python-docx is required to load DOCX files")

    doc = docx.Document(path)
    return "\n".join([p.text for p in doc.paragraphs])

def _load_folder(folder: str) -> list[str]:
    """Return a list of non-empty knowledge chunks from *folder*."""
    chunks: list[str] = []
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
                else:
                    continue
                content = content.strip()
                if content:
                    chunks.append(content)
            except Exception as e:  # pragma: no cover - just log errors
                print(f"❌ Nelze načíst {path}: {e}")
    return chunks


def load_knowledge(folder: str) -> list[str]:
    """Backward compatible wrapper returning knowledge chunks."""
    return _load_folder(folder)

def search_knowledge(query, knowledge_chunks, threshold=0.6):
    """Return up to five knowledge chunks relevant to *query*.

    A chunk is included when any word from the cleaned query appears in it or
    when the similarity ratio computed via :class:`difflib.SequenceMatcher`
    exceeds the given *threshold*.
    """

    normalized_query = _strip_diacritics(query.lower())
    clean_query = re.sub(r"\W+", " ", normalized_query)
    query_words = [w for w in clean_query.split() if w]

    matches = []
    for chunk in knowledge_chunks:
        chunk_lower = _strip_diacritics(chunk.lower())
        ratio = SequenceMatcher(None, clean_query, chunk_lower).ratio()

        if any(
            re.search(r"\b" + re.escape(word) + r"\b", chunk_lower)
            for word in query_words
        ) or ratio >= threshold:
            matches.append((ratio, chunk[:500]))  # Shorten for the prompt

    matches.sort(key=lambda x: x[0], reverse=True)
    return [m[1] for m in matches[:5]]


class KnowledgeBase:
    """Manage loading and searching local knowledge files from one or more folders."""

    def __init__(self, folder: str | list[str]):
        if isinstance(folder, str):
            self.folders = [folder]
        else:
            self.folders = list(folder)
        self.chunks: list[str] = []
        self.reload()

    def reload(self) -> None:
        """(Re)load all supported files from :attr:`folders`."""
        chunks: list[str] = []
        for folder in self.folders:
            chunks.extend(_load_folder(folder))
        self.chunks = chunks

    def search(self, query: str, threshold: float | None = None) -> list[str]:
        """Search loaded chunks for *query* using :func:`search_knowledge`.

        When ``threshold`` is ``None`` the value is read from the
        ``RAG_THRESHOLD`` environment variable. If that variable is missing or
        invalid the default ``0.6`` is used.
        """

        if threshold is None:
            env = os.getenv("RAG_THRESHOLD")
            try:
                threshold = float(env) if env is not None else 0.6
            except ValueError:  # pragma: no cover - environment may be invalid
                threshold = 0.6

        return search_knowledge(query, self.chunks, threshold)


def dependency_status() -> dict[str, bool]:
    """Return which optional dependencies are available."""

    return {"pdf": PDF_SUPPORT, "docx": DOCX_SUPPORT}

