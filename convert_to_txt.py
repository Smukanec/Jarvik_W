from pathlib import Path
import os

try:
    import pdfplumber
except ImportError:  # pragma: no cover - simple import guard
    pdfplumber = None

try:
    from docx import Document
except ImportError:  # pragma: no cover - simple import guard
    Document = None

INPUT_DIR = Path(os.getenv("KNOWLEDGE_DIR", "knowledge"))
OUTPUT_DIR = Path("knowledge_txt")
OUTPUT_DIR.mkdir(exist_ok=True)


def convert_txt(input_path: Path, output_path: Path) -> None:
    text = input_path.read_text(encoding="utf-8")
    output_path.write_text(text, encoding="utf-8")


def convert_pdf(input_path: Path, output_path: Path) -> None:
    if pdfplumber is None:
        print("pdfplumber is required for PDF conversion. Install it with 'pip install pdfplumber'.")
        return
    lines = []
    with pdfplumber.open(str(input_path)) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            lines.append(text.strip())
    output_path.write_text("\n\n".join(lines), encoding="utf-8")


def convert_docx(input_path: Path, output_path: Path) -> None:
    if Document is None:
        print("python-docx is required for DOCX conversion. Install it with 'pip install python-docx'.")
        return
    doc = Document(str(input_path))
    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    output_path.write_text("\n\n".join(paragraphs), encoding="utf-8")


if __name__ == "__main__":
    for file in INPUT_DIR.iterdir():
        out_path = OUTPUT_DIR / f"{file.stem}.txt"
        ext = file.suffix.lower()

        if ext == ".txt":
            convert_txt(file, out_path)
        elif ext == ".pdf":
            convert_pdf(file, out_path)
        elif ext == ".docx":
            convert_docx(file, out_path)
        else:
            continue
        print(f"Converted: {file.name} -> {out_path.name}")

