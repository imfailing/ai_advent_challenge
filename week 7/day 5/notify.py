"""
Публикация дайджеста в Telegram-канал (реальная интеграция).

Это «может быть не полностью рабочим» место: нужны TELEGRAM_BOT_TOKEN и
TELEGRAM_CHAT_ID. Без них сервис деградирует красиво — возвращает статус
'skipped', пайплайн не падает (дайджест уже сохранён в файл).
"""

import json
import os
import urllib.request


def send_telegram(text: str) -> dict:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return {"status": "skipped",
                "reason": "нет TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID — "
                          "публикация пропущена (дайджест сохранён в файл)."}

    # Telegram ограничивает сообщение 4096 символами
    payload = json.dumps({
        "chat_id": chat_id,
        "text": text[:4096],
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.load(r)
        return {"status": "sent" if data.get("ok") else "error", "response": data}
    except Exception as e:
        return {"status": "error", "reason": str(e)}
