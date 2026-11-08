"""Модуль логирования HTTP-запросов."""

import logging
import os
from datetime import datetime

# Настройка логирования
LOG_FILE = "app.log"
logger = logging.getLogger("http_logger")
logger.setLevel(logging.INFO)

# Файловый обработчик
file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
file_handler.setLevel(logging.INFO)
formatter = logging.Formatter(
    "%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# Чувствительные поля для маскирования
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
    if not body:
        return body
    sensitive_keys = ["password", "token", "api_key", "card", "secret"]
    masked_body = body
    for key in sensitive_keys:
        masked_body = masked_body.replace(key, "[REDACTED]")
    return masked_body


def log_request(method: str, url: str, headers: dict, body: str = None) -> None:
    """
    Записывает информацию о HTTP-запросе в файл app.log.
    
    Args:
        method: HTTP метод (GET, POST, и т.д.)
        url: URL запроса
        headers: словарь заголовков
        body: тело запроса (опционально)
    """
    # Валидация
    if not method or not url:
        logger.warning("Некорректные параметры запроса")
        return
    
    # Маскируем чувствительные данные
    masked_headers = _mask_sensitive_headers(headers or {})
    masked_body = _mask_sensitive_body(body)
    
    # Формируем запись
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = (
        f"[{timestamp}] {method} {url} | "
        f"Headers: {masked_headers} | "
        f"Body: {masked_body}"
    )
    
    logger.info(log_entry)


def get_log_entries() -> list:
    """Возвращает все записи из файла логов."""
    if not os.path.exists(LOG_FILE):
        return []
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        return f.readlines()


def clear_log_file() -> None:
    """Очищает файл логов."""
    if os.path.exists(LOG_FILE):
        os.remove(LOG_FILE)
