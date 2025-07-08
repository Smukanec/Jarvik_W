# Knowledge Folder

This directory contains the text sources used by Jarvik's retrieval engine. Files are organised into topic specific subfolders. The mapping of folders to topics is stored in `_index.json`.

```
knowledge/
  ai_strojove_uceni/    # AI and machine learning
  biologie_zdravi/      # Biology and health
  ekonomika_finance/    # Economy and finance
  historie/             # History and archival material
  navody_postupy/       # How‑to guides
  pravo_etika/          # Law and ethics
  programovani/         # Programming
  spolecnost/           # Society and social topics
  technologie/          # Technology news and docs
  umeni_kultura/        # Arts and culture
  veda_vyzkum/          # Science and research
  vzdelavani/           # Education
```

Only plain text files (`.txt`) are loaded. Convert any PDFs or DOCX documents before adding them here. Use `python convert_to_txt.py` from the repository root. The script relies on `pdfplumber` and `python-docx`, so install them manually if they are not present.

Recommended workflow for new material:

1. Place PDFs or DOCX files in the `knowledge/` folder.
2. Run `python convert_to_txt.py` to create text versions in `knowledge_txt/`.
3. Move the generated `.txt` files into the appropriate subfolder listed above.
4. After verifying the text files, delete the original PDF/DOCX sources.

This keeps the repository lightweight and ensures that Jarvik indexes only clean text files.
