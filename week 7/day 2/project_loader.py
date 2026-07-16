"""
Загрузчик документации И КОДА проекта для RAG (для ревью PR).

Индексируем:
  • дизайн-доки: корневой README, claude/*.md (архитектура, стек, конвенции);
  • код: .py-файлы репозитория (кроме venv/corpus/__pycache__).

Так ревьюер видит и правила проекта, и существующий код рядом с изменениями.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SKIP_DIRS = {"venv", "__pycache__", "corpus", "node_modules", ".git", "output", ".github"}


def _read(path: Path) -> str:
    for enc in ("utf-8", "utf-8-sig", "cp1251", "latin-1"):
        try:
            return path.read_text(encoding=enc)
        except UnicodeDecodeError:
            continue
    return path.read_text(errors="ignore")


def _title(text: str, fallback: str) -> str:
    for line in text.splitlines():
        m = re.match(r"^#\s+(.+)", line.strip())
        if m:
            return m.group(1).strip()
    return fallback


def _skip(path: Path) -> bool:
    return bool(SKIP_DIRS & set(path.parts))


def load_docs_and_code() -> list[dict]:
    docs: list[dict] = []

    # дизайн-доки
    md_paths = []
    root_readme = REPO_ROOT / "README.md"
    if root_readme.exists():
        md_paths.append(root_readme)
    md_paths += sorted((REPO_ROOT / "claude").glob("*.md")) if (REPO_ROOT / "claude").exists() else []

    for path in md_paths:
        if _skip(path):
            continue
        text = _read(path).strip()
        if text:
            rel = str(path.relative_to(REPO_ROOT))
            docs.append({"path": rel, "filename": rel, "title": _title(text, rel),
                         "text": text, "filetype": "md"})

    # код проекта
    for path in sorted(REPO_ROOT.rglob("*.py")):
        if _skip(path):
            continue
        text = _read(path).strip()
        if text:
            rel = str(path.relative_to(REPO_ROOT))
            docs.append({"path": rel, "filename": rel, "title": rel,
                         "text": text, "filetype": "py"})
    return docs


if __name__ == "__main__":
    d = load_docs_and_code()
    md = sum(1 for x in d if x["filetype"] == "md")
    py = sum(1 for x in d if x["filetype"] == "py")
    total = sum(len(x["text"]) for x in d)
    print(f"Документов: {len(d)} (md {md}, py {py}), символов: {total}, ~страниц: {total/1800:.0f}")
