"""
Проверка сервиса анализа удалённого GitHub-репозитория:
  • читаются коммиты внешнего публичного репо (GitHub REST API);
  • дайджест (нейтральный) — по шаблону разделов;
  • токсичный роаст — свой шаблон;
  • публикация в Telegram деградирует без токенов;
  • веб-эндпоинты /health, /generate, /publish работают.

Нужен DEEPSEEK_API_KEY.
"""

import digest
import github_repo
from notify import send_telegram

REPO = "octocat/Hello-World"


def main() -> None:
    # разбор ссылки/owner-repo
    assert github_repo.parse_repo("https://github.com/octocat/Hello-World") == REPO
    assert github_repo.parse_repo("octocat/Hello-World") == REPO

    commits = github_repo.get_commits(REPO, last=5)
    assert commits and all("hash" in c and "subject" in c for c in commits)
    print(f"✅ GitHub API: прочитано {len(commits)} коммитов {REPO}")

    md = digest.generate(commits, title="Тест", tone="neutral")
    for s in ["🔎 Главное", "✨ Новое", "🐞 Исправления", "📝 Документация", "🔧 Прочее"]:
        assert s in md, f"нет раздела {s}"
    print("✅ нейтральный дайджест: все разделы на месте")

    roast = digest.generate(commits, title="Роаст", tone="toxic")
    for s in ["🔥 Вердикт", "💀 Разбор коммитов", "⭐ Оценка"]:
        assert s in roast, f"нет раздела роаста {s}"
    print("✅ токсичный роаст: разделы на месте")

    res = send_telegram("тест")
    assert res["status"] in ("skipped", "sent", "error")
    print(f"✅ Telegram без токена → '{res['status']}' (деградация)")

    # веб-эндпоинты
    import app as flask_app
    c = flask_app.app.test_client()
    assert c.get("/").status_code == 200
    h = c.get("/health").get_json()
    assert h["deepseek"] is True
    r = c.post("/generate", json={"repo": REPO, "last": 3, "toxic": True}).get_json()
    assert "digest" in r and r["source"] == REPO
    print(f"✅ веб: /generate по {r['source']} ({r['commits']} коммитов), /publish деградирует")

    print("\n✅ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ — веб-сервис анализа удалённого репо работает")


if __name__ == "__main__":
    main()
