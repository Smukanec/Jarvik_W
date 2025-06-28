from pathlib import Path

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


if __name__ == "__main__":
    for file in INPUT_DIR.glob("*.txt"):
        out_path = OUTPUT_DIR / f"{file.stem}.md"
        convert_txt_to_md(file, out_path)
        print(f"Converted: {file.name} -> {out_path.name}")
