"""Проверка эндпоинта /stats и activity.compute_stats (без сети)."""
from unittest import mock

import activity
import app as app_module

COMMITS = [
    {"hash": "a", "date": "2024-01-02", "author": "Bob", "subject": "x", "body": ""},
    {"hash": "b", "date": "2024-01-02", "author": "Ann", "subject": "x", "body": ""},
    {"hash": "c", "date": "2024-01-02", "author": "Ann", "subject": "x", "body": ""},
    {"hash": "d", "date": "2024-01-01", "author": "Ann", "subject": "x", "body": ""},
]


def main() -> None:
    s = activity.compute_stats(COMMITS)
    assert s["total_commits"] == 4
    assert s["top_authors"][0] == {"author": "Ann", "commits": 3}
    assert s["busiest_day"] == {"date": "2024-01-02", "commits": 3}
    assert [d["date"] for d in s["commits_by_day"]] == ["2024-01-01", "2024-01-02"]
    print("✅ compute_stats: авторы, дни, самый активный день")

    assert activity.compute_stats([])["busiest_day"] is None
    print("✅ пустой список коммитов")

    client = app_module.app.test_client()
    with mock.patch("github_repo.get_commits", return_value=COMMITS):
        r = client.post("/stats", json={"repo": "https://github.com/o/r"})
    assert r.status_code == 200
    assert r.get_json()["source"] == "o/r"
    assert r.get_json()["busiest_day"]["date"] == "2024-01-02"
    print("✅ /stats: успех")

    assert client.post("/stats", json={}).status_code == 400
    assert client.post("/stats", json={"repo": "o/r", "last": "abc"}).status_code == 400
    print("✅ /stats: пустой repo и нечисловой last -> 400")

    for bad in ("abc", "1.5", [1], {"a": 1}):
        r = client.post("/generate", json={"deepseek_key": "k", "repo": "o/r", "last": bad})
        assert r.status_code == 400 and r.is_json, bad
        assert r.get_json()["error"] == "Параметр last должен быть числом."
    print("✅ /generate: нечисловой last -> JSON 400 (не HTML 500)")

    with mock.patch("github_repo.get_commits", side_effect=RuntimeError("нет репо")):
        r = client.post("/stats", json={"repo": "o/r"})
    assert r.status_code == 400 and r.get_json()["error"] == "нет репо"
    print("✅ /stats: ошибка GitHub -> JSON 400")

    print("\n✅ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ — статистика активности /stats")


if __name__ == "__main__":
    main()
