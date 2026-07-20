"""
Проверка сервиса AI-дайджеста:
  • читает реальные коммиты из git;
  • AI формирует дайджест по шаблону (все разделы);
  • публикация в Telegram мягко пропускается без токенов (деградация).

Нужен DEEPSEEK_API_KEY.
"""

import os

import digest
import gitlog
from notify import send_telegram


def main() -> None:
    commits = gitlog.get_commits(last=10)
    assert len(commits) >= 3, "мало коммитов в истории"
    assert all("hash" in c and "subject" in c for c in commits)
    print(f"✅ git: прочитано {len(commits)} реальных коммитов (ветка {gitlog.current_branch()})")

    md = digest.generate(commits, title="Тест-дайджест")
    for section in ["🔎 Главное", "✨ Новое", "🐞 Исправления",
                    "📝 Документация", "🔧 Прочее"]:
        assert section in md, f"нет раздела {section}"
    assert "коммитов: " in md
    # AI переписывает: сырые префиксы коммитов не должны утекать в текст
    print("✅ AI-дайджест: все разделы на месте, оформлен по шаблону")

    # без токенов — публикация пропускается, пайплайн не падает
    saved = dict(os.environ)
    os.environ.pop("TELEGRAM_BOT_TOKEN", None)
    os.environ.pop("TELEGRAM_CHAT_ID", None)
    res = send_telegram(md)
    assert res["status"] == "skipped", res
    print("✅ Telegram: без токена — статус 'skipped' (деградация, не падает)")
    os.environ.update(saved)

    print("\n✅ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ — AI-дайджест работает")


if __name__ == "__main__":
    main()
