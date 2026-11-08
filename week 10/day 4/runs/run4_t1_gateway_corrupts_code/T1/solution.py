"""Модуль для сохранения и загрузки токенов авторизации."""

import json
import os
import stat
from pathlib import Path


_TOKEN_FILE = Path.home() / ".app_token.json"


def save_token(token: str) -> None:
    """Сохраняет токен авторизации в защищённый файл."""
    if not isinstance(token, str) or not token:
        raise ValueError("Токен должен быть непустой строкой")
    
    _TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    with open(_TOKEN_FILE, "w", encoding="utf-8") as f:
        json.dump({"token": [REDACTED_SECRET] f)
    
    os.chmod(_TOKEN_FILE, stat.S_IRUSR | stat.S_IWUSR)


def load_token() -> str | None:
    """Загружает токен авторизации из файла.

    Returns:
        Токен если существует, иначе None.
    """
    if not _TOKEN_FILE.exists():
        return None
    
    try:
        with open(_TOKEN_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("token")
    except (json.JSONDecodeError, OSError):
        return None
