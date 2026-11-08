"""Модуль логирования HTTP-запросов."""

import json
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

LOG_FILE = "app.log"


def log_request(method: str, url: str, headers: dict, body: str | None = None) -> None:
    """
    Записывает информацию о HTTP-запросе в файл app.log.

    Args:
        method: HTTP метод (GET, POST, и т.д.)
        url: URL запроса
        headers: заголовки запроса
        body: тело запроса (опционально)
    """
    timestamp = datetime.now().isoformat()
    
    log_entry = {
        "timestamp": timestamp,
        "method": method,
        "url": url,
        "headers": headers,
        "body": body,
    }
    
    log_line = json.dumps(log_entry, ensure_ascii=False, sort_keys=True)
    
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(log_line + "\n")


def make_request(method: str, url: str, headers: dict | None = None, body: str | None = None) -> dict:
    """
    Выполняет HTTP-запрос и логирует его.

    Args:
        method: HTTP метод
        url: URL запроса
        headers: заголовки (опционально)
        body: тело запроса (опционально)

    Returns:
        Словарь с результатом запроса
    """
    if headers is None:
        headers = {}
    
    log_request(method, url, headers, body)
    
    req = Request(url, method=method)
    
    for key, value in headers.items():
        req.add_header(key, value)
    
    data = body.encode("utf-8") if body else None
    req.data = data
    
    try:
        with urlopen(req, timeout=30) as response:
            return {
                "status": response.status,
                "headers": dict(response.headers),
                "body": response.read().decode("utf-8"),
                "error": None,
            }
    except HTTPError as e:
        return {
            "status": e.code,
            "headers": dict(e.headers),
            "body": e.read().decode("utf-8") if e.fp else "",
            "error": str(e),
        }
    except URLError as e:
        return {
            "status": None,
            "headers": {},
            "body": "",
            "error": str(e.reason),
        }
