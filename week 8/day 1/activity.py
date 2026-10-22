"""
Статистика активности репозитория по списку коммитов (без AI и без сети).

Роль в сервисе: чистая функция поверх `github_repo.get_commits` — топ авторов,
число коммитов по дням и самый активный день.
"""

from collections import Counter

TOP_AUTHORS = 5


def compute_stats(commits: list[dict]) -> dict:
    """Посчитать статистику по коммитам {hash, date, author, ...}."""
    authors = Counter(c.get("author") or "?" for c in commits)
    days = Counter(c["date"] for c in commits if c.get("date"))
    top_authors = sorted(authors.items(), key=lambda kv: (-kv[1], kv[0]))[:TOP_AUTHORS]
    by_day = [{"date": d, "commits": n} for d, n in sorted(days.items())]
    busiest = max(by_day, key=lambda x: (x["commits"], x["date"]), default=None)
    return {
        "total_commits": len(commits),
        "top_authors": [{"author": a, "commits": n} for a, n in top_authors],
        "commits_by_day": by_day,
        "busiest_day": busiest,
    }
