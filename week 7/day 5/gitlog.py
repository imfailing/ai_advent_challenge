"""
Сбор коммитов из git-истории репозитория (реальное окружение).

Диапазон задаётся: --last N, --since "1 week ago" или --range base..head.
Возвращает список коммитов {hash, date, author, subject, body}.
"""

import os
import subprocess
from pathlib import Path

# Корень репозитория. По умолчанию — на 2 уровня выше файла; в Docker
# монтируется отдельно и задаётся через REPO_DIR.
REPO_ROOT = Path(os.environ.get("REPO_DIR") or Path(__file__).resolve().parents[2])

# уникальные разделители, чтобы надёжно распарсить вывод git
_SEP_FIELD = "\x1f"
_SEP_REC = "\x1e"


def _git(*args: str) -> str:
    out = subprocess.run(["git", "-C", str(REPO_ROOT), *args],
                         capture_output=True, text=True, timeout=30)
    if out.returncode != 0:
        raise RuntimeError(f"git error: {out.stderr.strip()}")
    return out.stdout


def get_commits(last: int | None = None, since: str | None = None,
                rev_range: str | None = None) -> list[dict]:
    fmt = _SEP_FIELD.join(["%h", "%ad", "%an", "%s", "%b"]) + _SEP_REC
    args = ["log", f"--pretty=format:{fmt}", "--date=short"]
    if rev_range:
        args.append(rev_range)
    if since:
        args.append(f"--since={since}")
    if last:
        args.append(f"-{last}")

    raw = _git(*args)
    commits = []
    for rec in raw.split(_SEP_REC):
        rec = rec.strip("\n")
        if not rec.strip():
            continue
        parts = rec.split(_SEP_FIELD)
        if len(parts) < 4:
            continue
        h, date, author, subject = parts[0], parts[1], parts[2], parts[3]
        body = parts[4].strip() if len(parts) > 4 else ""
        commits.append({"hash": h, "date": date, "author": author,
                        "subject": subject, "body": body})
    return commits


def current_branch() -> str:
    return _git("rev-parse", "--abbrev-ref", "HEAD").strip()


if __name__ == "__main__":
    import sys
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 15
    cs = get_commits(last=n)
    print(f"Ветка {current_branch()}, коммитов: {len(cs)}")
    for c in cs:
        print(f"  {c['hash']} {c['date']} {c['subject'][:70]}")
