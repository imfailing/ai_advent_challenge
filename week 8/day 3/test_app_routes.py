"""Проверка маршрутов /, /health, /generate, /publish (без сети, всё подменено)."""
from unittest import mock

import app as app_module

COMMITS = [{"hash": "a", "date": "2024-01-01", "author": "Ann", "subject": "x", "body": ""}]


def main() -> None:
    c = app_module.app.test_client()
    assert c.get("/").status_code == 200
    assert c.get("/health").get_json() == {"status": "ok"}
    print("✅ / и /health")

    body = {"deepseek_key": "k", "repo": "o/r"}
    r = c.post("/generate", json={"repo": "o/r"})
    assert r.status_code == 400 and "DeepSeek" in r.get_json()["error"]
    r = c.post("/generate", json={"deepseek_key": "  ", "repo": "o/r"})
    assert r.status_code == 400
    r = c.post("/generate", json={"deepseek_key": "k", "repo": "  "})
    assert r.status_code == 400 and "репозиторий" in r.get_json()["error"]
    print("✅ /generate: нет ключа / пустой repo -> JSON 400")

    with mock.patch("github_repo.get_commits", return_value=[]):
        r = c.post("/generate", json=body)
    assert r.status_code == 400 and r.get_json()["error"] == "Коммитов не найдено."
    with mock.patch("github_repo.get_commits", side_effect=RuntimeError("упало")):
        r = c.post("/generate", json=body)
    assert r.status_code == 400 and r.get_json()["error"] == "упало"
    r = c.post("/generate", json={**body, "repo": "плохо"})
    assert r.status_code == 400 and "owner/repo" in r.get_json()["error"]
    print("✅ /generate: пусто, ошибка GitHub, неверный repo -> 400")

    with mock.patch.dict(app_module._last_digest, {"md": ""}), \
         mock.patch("github_repo.get_commits", return_value=COMMITS) as gc, \
         mock.patch("digest.generate", return_value="MD") as gen:
        r = c.post("/generate", json={**body, "last": 999, "toxic": True,
                                      "github_token": " gh ", "repo": " o/r "})
        assert r.status_code == 200
        assert r.get_json() == {"digest": "MD", "commits": 1, "source": "o/r", "tone": "toxic"}
        assert gc.call_args.kwargs == {"last": 100, "token": "gh"}
        assert gen.call_args.kwargs["tone"] == "toxic"
        assert gen.call_args.kwargs["title"] == "Роаст коммитов o/r"
        assert app_module._last_digest["md"] == "MD"
        r = c.post("/generate", json={**body, "last": 0})
        assert gc.call_args.kwargs["last"] == 15 and r.get_json()["tone"] == "neutral"
        assert gen.call_args.kwargs["title"] == "Дайджест изменений o/r"
    print("✅ /generate: успех, кламп last (999->100, 0->15), токен, тон, _last_digest")

    with mock.patch.dict(app_module._last_digest, {"md": ""}), \
         mock.patch("github_repo.get_commits", return_value=COMMITS), \
         mock.patch("digest.generate", side_effect=ValueError("ключ плох")):
        r = c.post("/generate", json=body)
        assert r.status_code == 500 and r.get_json()["error"] == "AI: ключ плох"
        assert app_module._last_digest["md"] == ""
    print("✅ /generate: сбой AI -> JSON 500 'AI: …', состояние не затронуто")

    with mock.patch.dict(app_module._last_digest, {"md": ""}):
        r = c.post("/publish", json={})
    assert r.status_code == 400 and "Сначала" in r.get_json()["error"]
    with mock.patch.dict(app_module._last_digest, {"md": "TXT"}), \
         mock.patch("app.send_telegram", return_value={"status": "sent"}) as st:
        r = c.post("/publish", json={"telegram_token": " t ", "telegram_chat_id": " 1 "})
        assert r.get_json() == {"status": "sent"}
        st.assert_called_once_with("TXT", token="t", chat_id="1")
        r = c.post("/publish", json={})
        assert st.call_args.kwargs == {"token": "", "chat_id": ""}
    print("✅ /publish: без результата -> 400; с результатом — strip токенов и вызов")

    print("\n✅ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ — маршруты app.py (/generate, /publish, /health)")


if __name__ == "__main__":
    main()
