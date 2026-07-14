"""
MCP-сервер, подключающий ассистента к git-проекту.

Инструменты работают с git в корне репозитория (на 2 уровня выше папки дня).
Только чтение — команды не меняют репозиторий.

  git_branch()        — текущая ветка
  git_status()        — короткий статус рабочего дерева
  git_recent_files()  — недавно изменённые файлы (по коммитам)
  git_diff(staged)    — текущий diff (рабочее дерево или staged)
  git_log(limit)      — последние коммиты
  list_files(subdir)  — отслеживаемые файлы (git ls-files)
"""

import subprocess
from pathlib import Path

from mcp.server.fastmcp import FastMCP

REPO_ROOT = Path(__file__).resolve().parents[2]

mcp = FastMCP("git-server")


def _git(*args: str) -> str:
    try:
        out = subprocess.run(["git", "-C", str(REPO_ROOT), *args],
                             capture_output=True, text=True, timeout=15)
        if out.returncode != 0:
            return f"(git error: {out.stderr.strip() or out.returncode})"
        return out.stdout.strip()
    except Exception as e:
        return f"(git недоступен: {e})"


@mcp.tool()
def git_branch() -> str:
    """Текущая git-ветка репозитория проекта."""
    return _git("rev-parse", "--abbrev-ref", "HEAD") or "(нет веток)"


@mcp.tool()
def git_status() -> str:
    """Короткий статус рабочего дерева (git status --short)."""
    return _git("status", "--short") or "(рабочее дерево чистое)"


@mcp.tool()
def git_log(limit: int = 5) -> str:
    """Последние коммиты (хеш, дата, сообщение). limit — сколько показать."""
    return _git("log", f"-{max(1, min(limit, 30))}", "--pretty=format:%h %ad %s",
                "--date=short") or "(нет коммитов)"


@mcp.tool()
def git_recent_files(limit: int = 10) -> str:
    """Файлы, изменённые в последнем коммите."""
    return _git("show", "--stat", "--oneline", f"-{1}") or "(нет данных)"


@mcp.tool()
def git_diff(staged: bool = False) -> str:
    """Текущий diff. staged=true — проиндексированные изменения, иначе рабочее дерево."""
    args = ["diff", "--stat"] + (["--cached"] if staged else [])
    d = _git(*args)
    return d or "(нет изменений)"


@mcp.tool()
def list_files(subdir: str = "") -> str:
    """
    Список отслеживаемых файлов репозитория (git ls-files).
    subdir — ограничить подкаталогом, например 'week 7/day 1'.
    """
    args = ["ls-files"]
    if subdir.strip():
        args.append(subdir.strip())
    files = _git(*args)
    if not files:
        return "(нет файлов)"
    lines = files.splitlines()
    head = "\n".join(lines[:60])
    if len(lines) > 60:
        head += f"\n… и ещё {len(lines) - 60} файлов (всего {len(lines)})"
    return head


if __name__ == "__main__":
    mcp.run()
