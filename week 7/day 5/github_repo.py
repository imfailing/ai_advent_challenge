"""
Чтение коммитов из ВНЕШНЕГО GitHub-репозитория через REST API (только чтение).

Публичные репозитории работают без токена (с лимитом ~60 запросов/час).
Для приватных / повышенного лимита — GITHUB_TOKEN в окружении.

Сервис только ЧИТАЕТ внешние репо. Автопостинг комментариев в чужие репозитории
не делается (это был бы харассмент мейнтейнеров) — роаст можно опубликовать
только в свой Telegram-канал.
"""

import json
import os
import re
import urllib.error
import urllib.request

API = "https://api.github.com"


def parse_repo(value: str) -> str:
    """Извлечь 'owner/repo' из URL или строки owner/repo."""
    value = value.strip().rstrip("/")
    m = re.search(r"github\.com[/:]([^/]+/[^/]+?)(?:\.git)?$", value)
    if m:
        return m.group(1)
    if re.fullmatch(r"[\w.-]+/[\w.-]+", value):
        return value
    raise ValueError("Ожидается 'owner/repo' или ссылка на GitHub-репозиторий")


def _get(url: str) -> list | dict:
    headers = {"Accept": "application/vnd.github+json",
               "User-Agent": "ai-advent-digest"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def get_commits(repo: str, last: int = 15) -> list[dict]:
    """
    Последние коммиты внешнего репо. repo — 'owner/repo' или ссылка.
    Формат совпадает с gitlog: {hash, date, author, subject, body}.
    """
    owner_repo = parse_repo(repo)
    n = max(1, min(last, 100))
    try:
        data = _get(f"{API}/repos/{owner_repo}/commits?per_page={n}")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise RuntimeError(f"Репозиторий {owner_repo} не найден или приватный "
                               f"(нужен GITHUB_TOKEN).")
        if e.code == 403:
            raise RuntimeError("Лимит GitHub API исчерпан — задайте GITHUB_TOKEN.")
        raise RuntimeError(f"GitHub API: {e.code} {e.reason}")

    commits = []
    for c in data:
        msg = (c.get("commit", {}).get("message") or "").strip()
        subject, _, body = msg.partition("\n")
        author = c.get("commit", {}).get("author", {})
        commits.append({
            "hash":    (c.get("sha") or "")[:7],
            "date":    (author.get("date") or "")[:10],
            "author":  author.get("name", "?"),
            "subject": subject.strip(),
            "body":    body.strip(),
        })
    return commits


def repo_label(repo: str) -> str:
    return parse_repo(repo)


if __name__ == "__main__":
    import sys
    r = sys.argv[1] if len(sys.argv) > 1 else "octocat/Hello-World"
    for c in get_commits(r, last=5):
        print(f"  {c['hash']} {c['date']} {c['subject'][:70]}")
