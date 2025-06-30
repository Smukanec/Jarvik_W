from pathlib import Path

try:
    import pdfplumber
except ImportError:  # pragma: no cover - simple import guard
    pdfplumber = None

try:
    from docx import Document
except ImportError:  # pragma: no cover - simple import guard
    Document = None

INPUT_DIR = Path("knowledge")
OUTPUT_DIR = Path("knowledge_md")
OUTPUT_DIR.mkdir(exist_ok=True)


def convert_txt_to_md(input_path: Path, output_path: Path) -> None:
    with input_path.open("r", encoding="utf-8") as f:
        text = f.read()

    # Split paragraphs on blank lines
    blocks = [b.strip() for b in text.split("\n\n") if b.strip()]
    md_lines = ["# " + input_path.stem.replace("_", " ").title(), ""]

    for i, block in enumerate(blocks, start=1):
        md_lines.append(f"## Sekce {i}")
        md_lines.append(block)
        md_lines.append("")

    with output_path.open("w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))


def convert_pdf_to_md(input_path: Path, output_path: Path) -> None:
    if pdfplumber is None:
        print(
            "pdfplumber is required for PDF conversion. Install it with 'pip install pdfplumber'."
        )
        return

    md_lines = ["# " + input_path.stem.replace("_", " ").title(), ""]
    with pdfplumber.open(str(input_path)) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            md_lines.append(f"## Sekce {i}")
            text = page.extract_text() or ""
            md_lines.append(text.strip())
            md_lines.append("")

    with output_path.open("w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))


def convert_docx_to_md(input_path: Path, output_path: Path) -> None:
    if Document is None:
        print(
            "python-docx is required for DOCX conversion. Install it with 'pip install python-docx'."
        )
        return

    doc = Document(str(input_path))
    md_lines = ["# " + input_path.stem.replace("_", " ").title(), ""]
    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    for i, para in enumerate(paragraphs, start=1):
        md_lines.append(f"## Sekce {i}")
        md_lines.append(para)
        md_lines.append("")

    with output_path.open("w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))


if __name__ == "__main__":
    for file in INPUT_DIR.iterdir():
        out_path = OUTPUT_DIR / f"{file.stem}.md"
        ext = file.suffix.lower()

        if ext == ".txt":
            convert_txt_to_md(file, out_path)
        elif ext == ".pdf":
            if pdfplumber is None:
                print(
                    f"Skipping {file.name}: install pdfplumber with 'pip install pdfplumber' to enable PDF conversion."
                )
                continue
            convert_pdf_to_md(file, out_path)
        elif ext == ".docx":
            if Document is None:
                print(
                    f"Skipping {file.name}: install python-docx with 'pip install python-docx' to enable DOCX conversion."
                )
                continue
            convert_docx_to_md(file, out_path)
        else:
            continue
        print(f"Converted: {file.name} -> {out_path.name}")
