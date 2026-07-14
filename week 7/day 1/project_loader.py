"""
Загрузчик документации ПРОЕКТА для RAG.

Собирает docs самого репозитория:
  • корневой README.md;
  • README.md всех дней (week */day */README.md) — это «project/docs»;
  • claude/*.md — дизайн/архитектура проекта (project, architecture, stack, apis);
  • results.md где есть (итоги экспериментов).

Не индексируем: venv, corpus/, node_modules, сам индекс. Пути — относительно
корня репозитория (на 2 уровня выше папки дня).
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]   # …/ai_advent_challenge

SKIP_DIRS = {"venv", "__pycache__", "corpus", "node_modules", ".git", "output"}


def _title(text: str, fallback: str) -> str:
    for line in text.splitlines():
        m = re.match(r"^#\s+(.+)", line.strip())
        if m:
            return m.group(1).strip()
    return fallback


def _read(path: Path) -> str:
    for enc in ("utf-8", "utf-8-sig", "cp1251", "latin-1"):
        try:
            return path.read_text(encoding=enc)
        except UnicodeDecodeError:
            continue
    return path.read_text(errors="ignore")


def _rel(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT))


def _collect() -> list[Path]:
    paths: list[Path] = []
    # корневой README
    root_readme = REPO_ROOT / "README.md"
    if root_readme.exists():
        paths.append(root_readme)
    # README и results всех дней
    for pat in ("week */day */README.md", "week */day */results.md"):
        paths.extend(sorted(REPO_ROOT.glob(pat)))
    # claude/*.md (дизайн-доки проекта)
    claude = REPO_ROOT / "claude"
    if claude.exists():
        paths.extend(sorted(claude.glob("*.md")))
    # отфильтровать нежелательные каталоги
    return [p for p in paths if not (SKIP_DIRS & set(p.parts))]


def load_project_docs() -> list[dict]:
    """Вернуть документы проекта: {path, filename, title, text, filetype}."""
    docs = []
    for path in _collect():
        text = _read(path).strip()
        if not text:
            continue
        rel = _rel(path)
        docs.append({
            "path":     rel,
            "filename": rel,                 # относительный путь как имя (для источников)
            "title":    _title(text, rel),
            "text":     text,
            "filetype": "md",
        })
    return docs


if __name__ == "__main__":
    d = load_project_docs()
    total = sum(len(x["text"]) for x in d)
    print(f"Документов проекта: {len(d)}, символов: {total}, ~страниц: {total/1800:.0f}")
    for x in d[:40]:
        print(f"  {x['filename']:<42} {len(x['text']):>6} симв.  «{x['title'][:34]}»")
    if len(d) > 40:
        print(f"  … и ещё {len(d)-40}")
