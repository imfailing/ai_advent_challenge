"""
MCP-сервер файловых операций (в песочнице workspace/).

Даёт ассистенту РЕАЛЬНЫЕ операции с файлами: список, чтение, поиск по многим
файлам, анализ, создание/изменение. Все пути ограничены каталогом workspace/ —
агент не может выйти за песочницу.

  list_files(subdir)          — список файлов
  read_file(path)             — содержимое файла
  search(pattern, glob)       — поиск (regex) по файлам → file:line:текст
  write_file(path, content)   — создать/перезаписать файл (внутри workspace)
"""

import re
from pathlib import Path

from mcp.server.fastmcp import FastMCP

WORKSPACE = (Path(__file__).parent / "workspace").resolve()

mcp = FastMCP("fs-server")


def _safe(path: str) -> Path:
    """Путь внутри песочницы; иначе исключение."""
    p = (WORKSPACE / path).resolve()
    if not str(p).startswith(str(WORKSPACE)):
        raise ValueError(f"Путь вне песочницы: {path}")
    return p


@mcp.tool()
def list_files(subdir: str = "") -> list[str]:
    """Список файлов в песочнице (рекурсивно). subdir — ограничить подкаталогом."""
    base = _safe(subdir) if subdir else WORKSPACE
    if not base.exists():
        return []
    return sorted(str(p.relative_to(WORKSPACE)) for p in base.rglob("*") if p.is_file())


@mcp.tool()
def read_file(path: str) -> str:
    """Прочитать файл по относительному пути (например 'service_a.py')."""
    p = _safe(path)
    if not p.exists():
        return f"(файл не найден: {path})"
    return p.read_text(encoding="utf-8", errors="ignore")


@mcp.tool()
def search(pattern: str, glob: str = "*") -> list[dict]:
    """
    Найти строки по regex-паттерну во всех файлах песочницы.
    glob — маска файлов (например '*.py'). Возвращает [{file, line, text}].
    """
    try:
        rx = re.compile(pattern)
    except re.error as e:
        return [{"error": f"неверный regex: {e}"}]
    hits = []
    for p in sorted(WORKSPACE.rglob(glob)):
        if not p.is_file():
            continue
        for i, line in enumerate(p.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
            if rx.search(line):
                hits.append({"file": str(p.relative_to(WORKSPACE)),
                             "line": i, "text": line.strip()[:200]})
    return hits or [{"info": "совпадений не найдено"}]


@mcp.tool()
def write_file(path: str, content: str) -> dict:
    """
    Создать или перезаписать файл в песочнице. Родительские папки создаются.
    Возвращает {path, bytes, action}.
    """
    p = _safe(path)
    existed = p.exists()
    p.parent.mkdir(parents=True, exist_ok=True)
    data = content if content.endswith("\n") else content + "\n"
    p.write_text(data, encoding="utf-8")
    return {"path": path, "bytes": len(data.encode("utf-8")),
            "action": "updated" if existed else "created"}


if __name__ == "__main__":
    mcp.run()
