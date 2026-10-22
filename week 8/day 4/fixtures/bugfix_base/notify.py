"""
Публикация результата в Telegram-канал (реальная интеграция).

Токен бота и chat_id задаются пользователем (в интерфейсе). Без них публикация
деградирует красиво — возвращает статус 'skipped', сервис не падает.
"""

import json
import urllib.request


def send_telegram(text: str, token: str = "", chat_id: str = "") -> dict:
    token = (token or "").strip()
    chat_id = (chat_id or "").strip()
    if not token or not chat_id:
        return {"status": "skipped",
                "reason": "не заданы токен бота и chat_id — публикация пропущена."}

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
