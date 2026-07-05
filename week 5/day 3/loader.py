"""
Загрузчик корпуса: обходит папку и извлекает текст из документов.

Поддержка:
  .md / .txt / .py  — чтение как текст;
  .pdf              — извлечение через pypdf.

Возвращает документы вида:
  {path, filename, title, text, filetype}
где title — первый заголовок markdown или имя файла.
"""

import re
from pathlib import Path

TEXT_EXT = {".md", ".txt", ".py"}
PDF_EXT  = {".pdf"}


def _title(text: str, filename: str, filetype: str) -> str:
    if filetype == "md":
        for line in text.splitlines():
            m = re.match(r"^#\s+(.+)", line.strip())
            if m:
                return m.group(1).strip()
    return filename


def _read_text(path: Path) -> str:
    for enc in ("utf-8", "utf-8-sig", "cp1251", "latin-1"):
        try:
            return path.read_text(encoding=enc)
        except UnicodeDecodeError:
            continue
    return path.read_text(errors="ignore")


def _read_pdf(path: Path) -> str:
    from pypdf import PdfReader
    reader = PdfReader(str(path))
    return "\n\n".join((p.extract_text() or "").strip() for p in reader.pages)


def load_document(path: Path) -> dict | None:
    ext = path.suffix.lower()
    if ext in TEXT_EXT:
        text, ftype = _read_text(path), ext.lstrip(".")
    elif ext in PDF_EXT:
        text, ftype = _read_pdf(path), "pdf"
    else:
        return None
    text = text.strip()
    if not text:
        return None
    return {
        "path":     str(path),
        "filename": path.name,
        "title":    _title(text, path.name, ftype),
        "text":     text,
        "filetype": ftype,
    }


def load_corpus(corpus_dir: str | Path) -> list[dict]:
    """Загрузить все поддерживаемые документы из папки (рекурсивно)."""
    corpus_dir = Path(corpus_dir)
    docs = []
    for path in sorted(corpus_dir.rglob("*")):
        if path.is_file():
            doc = load_document(path)
            if doc:
                docs.append(doc)
    return docs


if __name__ == "__main__":
    import sys
    d = load_corpus(sys.argv[1] if len(sys.argv) > 1 else "corpus")
    total = sum(len(x["text"]) for x in d)
    print(f"Документов: {len(d)}, символов: {total}, ~страниц: {total/1800:.1f}")
    for x in d:
        print(f"  [{x['filetype']:>3}] {x['filename']:<32} {len(x['text']):>6} симв.  «{x['title'][:40]}»")
