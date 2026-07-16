"""Загрузчик документации продукта (FAQ + доки) для RAG."""

import re
from pathlib import Path

DOCS_DIR = Path(__file__).parent / "product_docs"


def _title(text: str, fallback: str) -> str:
    for line in text.splitlines():
        m = re.match(r"^#\s+(.+)", line.strip())
        if m:
            return m.group(1).strip()
    return fallback


def load_docs() -> list[dict]:
    docs = []
    for path in sorted(DOCS_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8").strip()
        if text:
            docs.append({"path": path.name, "filename": path.name,
                         "title": _title(text, path.name), "text": text, "filetype": "md"})
    return docs


if __name__ == "__main__":
    d = load_docs()
    print(f"Документов продукта: {len(d)}")
    for x in d:
        print(f"  {x['filename']:<14} {len(x['text']):>5} симв.  «{x['title']}»")
