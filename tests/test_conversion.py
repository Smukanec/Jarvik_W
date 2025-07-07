import os
import sys
import runpy
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import convert_to_txt
import convert_to_md


def test_convert_txt(tmp_path):
    inp = tmp_path / "file.txt"
    out = tmp_path / "out.txt"
    inp.write_text("hello", encoding="utf-8")
    convert_to_txt.convert_txt(inp, out)
    assert out.read_text(encoding="utf-8") == "hello"


def test_convert_txt_to_md(tmp_path):
    inp = tmp_path / "file.txt"
    out = tmp_path / "file.md"
    inp.write_text("first\n\nsecond", encoding="utf-8")
    convert_to_md.convert_txt_to_md(inp, out)
    text = out.read_text(encoding="utf-8")
    assert "# File" in text
    assert "## Sekce 1" in text
    assert "first" in text
    assert "## Sekce 2" in text
    assert "second" in text


class DummyPage:
    def __init__(self, text):
        self._text = text

    def extract_text(self):
        return self._text


class DummyPdf:
    def __init__(self, texts):
        self.pages = [DummyPage(t) for t in texts]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        pass


class DummyPdfPlumber:
    def __init__(self, texts):
        self._texts = texts
    def open(self, _path):
        return DummyPdf(self._texts)


class DummyDocxDocument:
    def __init__(self, _path, texts):
        self._texts = texts
    @property
    def paragraphs(self):
        return [type("Para", (), {"text": t}) for t in self._texts]


def test_convert_pdf_and_docx_to_txt(tmp_path, monkeypatch):
    monkeypatch.setattr(convert_to_txt, "pdfplumber", DummyPdfPlumber(["p1", "p2"]))
    inp_pdf = tmp_path / "a.pdf"
    inp_pdf.write_text("dummy")
    out_pdf = tmp_path / "a.txt"
    convert_to_txt.convert_pdf(inp_pdf, out_pdf)
    assert out_pdf.read_text(encoding="utf-8") == "p1\n\np2"

    monkeypatch.setattr(convert_to_txt, "Document", lambda _p: DummyDocxDocument(_p, ["d1", "d2"]))
    inp_docx = tmp_path / "b.docx"
    inp_docx.write_text("dummy")
    out_docx = tmp_path / "b.txt"
    convert_to_txt.convert_docx(inp_docx, out_docx)
    assert out_docx.read_text(encoding="utf-8") == "d1\n\nd2"


def test_convert_pdf_and_docx_to_md(tmp_path, monkeypatch):
    monkeypatch.setattr(convert_to_md, "pdfplumber", DummyPdfPlumber(["p1", "p2"]))
    inp_pdf = tmp_path / "a.pdf"
    inp_pdf.write_text("dummy")
    out_pdf = tmp_path / "a.md"
    convert_to_md.convert_pdf_to_md(inp_pdf, out_pdf)
    text_pdf = out_pdf.read_text(encoding="utf-8")
    assert "p1" in text_pdf and "p2" in text_pdf

    monkeypatch.setattr(convert_to_md, "Document", lambda _p: DummyDocxDocument(_p, ["d1", "d2"]))
    inp_docx = tmp_path / "b.docx"
    inp_docx.write_text("dummy")
    out_docx = tmp_path / "b.md"
    convert_to_md.convert_docx_to_md(inp_docx, out_docx)
    text_docx = out_docx.read_text(encoding="utf-8")
    assert "d1" in text_docx and "d2" in text_docx


def test_unsupported_extension_skipped(tmp_path, monkeypatch):
    input_dir = tmp_path / "in"
    input_dir.mkdir()
    (input_dir / "file.xyz").write_text("dummy", encoding="utf-8")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("KNOWLEDGE_DIR", str(input_dir))
    runpy.run_module("convert_to_txt", run_name="__main__")
    out_dir = Path("knowledge_txt")
    assert out_dir.exists()
    assert not any(out_dir.iterdir())

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("KNOWLEDGE_DIR", str(input_dir))
    runpy.run_module("convert_to_md", run_name="__main__")
    out_dir_md = Path("knowledge_md")
    assert out_dir_md.exists()
    assert not any(out_dir_md.iterdir())
