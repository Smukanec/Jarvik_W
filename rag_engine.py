import os
import glob
import re
from difflib import SequenceMatcher

__all__ = [
    "load_txt_file",
    "load_pdf_file",
    "load_docx_file",
    "load_knowledge",
    "search_knowledge",
    "KnowledgeBase",
]

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
    for ext in ("*.txt", "*.pdf", "*.docx"):
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

    clean_query = re.sub(r"\W+", " ", query.lower())
    query_words = [w for w in clean_query.split() if w]

    matches = []
    for chunk in knowledge_chunks:
        chunk_lower = chunk.lower()
        ratio = SequenceMatcher(None, clean_query, chunk_lower).ratio()

        if any(word in chunk_lower for word in query_words) or ratio >= threshold:
            matches.append((ratio, chunk[:500]))  # Shorten for the prompt

    matches.sort(key=lambda x: x[0], reverse=True)
    return [m[1] for m in matches[:5]]


class KnowledgeBase:
    """Manage loading and searching local knowledge files."""

    def __init__(self, folder: str):
        self.folder = folder
        self.chunks: list[str] = []
        self.reload()

    def reload(self) -> None:
        """(Re)load all supported files from :attr:`folder`."""
        self.chunks = _load_folder(self.folder)

    def search(self, query: str, threshold: float = 0.6) -> list[str]:
        """Search loaded chunks for *query* using :func:`search_knowledge`."""
        return search_knowledge(query, self.chunks, threshold)

