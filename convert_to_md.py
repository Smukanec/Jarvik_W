from pathlib import Path

import pdfplumber
from docx import Document

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
        if file.suffix.lower() == ".txt":
            convert_txt_to_md(file, out_path)
        elif file.suffix.lower() == ".pdf":
            convert_pdf_to_md(file, out_path)
        elif file.suffix.lower() == ".docx":
            convert_docx_to_md(file, out_path)
        else:
            continue
        print(f"Converted: {file.name} -> {out_path.name}")
