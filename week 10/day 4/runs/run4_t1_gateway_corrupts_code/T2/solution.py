"""Модуль логирования HTTP-запросов."""

import json
from datetime import datetime
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError


LOG_FILE = "app.log"
SENSITIVE_FIELDS = {"authorization", "x-api-key", "cookie", "password", "token"}


def _mask_sensitive_headers(headers: dict) -> dict:
    """Маскирует чувствительные заголовки."""
    masked = {}
    for key, value in headers.items():
        if key.lower() in SENSITIVE_FIELDS:
            masked[key] = "[REDACTED]"
        else:
            masked[key] = value
    return masked


def _mask_sensitive_body(body: str) -> str:
    """Маскирует чувствительные данные в теле запроса."""
    try:
        data = json.loads(body) if body else {}
        for key in list(data.keys()):
            if key.lower() in SENSITIVE_FIELDS:
                data[key] = "[REDACTED]"
        return json.dumps(data, ensure_ascii=False)
    except (json.JSONDecodeError, TypeError):
        return body if body else ""


def log_request(method: str, url: str, headers: dict, body: str) -> None:
    """
    Записывает информацию о HTTP-запросе в файл app.log.

    Args:
        method: HTTP метод (GET, POST, и т.д.)
        url: URL запроса
        headers: заголовки запроса
        body: тело запроса
    """
    timestamp = datetime.utcnow().isoformat() + "Z"
    masked_headers = _mask_sensitive_headers(headers or {})
    masked_body = _mask_sensitive_body(body or "")

    log_entry = {
        "timestamp": timestamp,
        "method": method,
        "url": url,
        "headers": masked_headers,
        "body": masked_body,
    }

    log_line = json.dumps(log_entry, ensure_ascii=False) + "\n"

    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(log_line)


def make_request(method: str, url: str, headers: dict = None, body: str = None) -> dict:
    """
    Выполняет HTTP-запрос и логирует его.

    Args:
        method: HTTP метод
        url: URL запроса
        headers: заголовки запроса
        body: тело запроса

    Returns:
        Словарь с результатом запроса
    """
    log_request(method, url, headers, body)

    req = Request(url, data=body.encode() if body else None, method=method)
    if headers:
        for key, value in headers.items():
            req.add_header(key, value)

    try:
        with urlopen(req, timeout=30) as response:
            return {
                "status": response.status,
                "headers": dict(response.headers),
                "body": response.read().decode("utf-8"),
                "success": True,
            }
    except HTTPError as e:
        return {
            "status": e.code,
            "headers": dict(e.headers),
            "body": e.read().decode("utf-8") if e.fp else "",
            "success": False,
        }
    except URLError as e:
        return {
            "status": None,
            "headers": {},
            "body": str(e.reason),
            "success": False,
        }
