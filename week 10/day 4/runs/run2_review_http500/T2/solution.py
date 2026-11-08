"""Модуль логирования HTTP-запросов."""

import json
from datetime import datetime
from pathlib import Path


def log_request(method: str, url: str, headers: dict, body: str) -> None:
    """
    Записывает информацию о HTTP-запросе в файл app.log.

    Args:
        method: HTTP метод (GET, POST, и т.д.)
        url: URL запроса
        headers: заголовки запроса (dict)
        body: тело запроса (str)
    """
    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "method": method,
        "url": url,
        "headers": headers,
        "body": body,
    }

    log_file = Path("app.log")
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
