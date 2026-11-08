"""Модуль для сохранения и загрузки токена авторизации."""

import json
import os
import stat
from pathlib import Path


def _get_token_file_path() -> Path:
    """Возвращает путь к файлу токена в безопасном расположении."""
    config_dir = Path.home() / ".report_service"
    config_dir.mkdir(mode=0o700, exist_ok=True)
    return config_dir / "auth_token.json"


def save_token(token: str) -> None:
    """
    Сохраняет токен авторизации в защищённый файл.

    Args:
        token: Токен авторизации.

    Raises:
        ValueError: Если токен пустой или None.
        IOError: Если не удалось записать файл.
    """
    if not token or not isinstance(token, str):
        raise ValueError("Токен должен быть непустой строкой")

    token_file = _get_token_file_path()
    data = {"token": token}

    try:
        with open(token_file, "w", encoding="utf-8") as f:
            json.dump(data, f)
        os.chmod(token_file, stat.S_IRUSR | stat.S_IWUSR)
    except OSError as e:
        raise IOError(f"Не удалось сохранить токен: {e}") from e


def load_token() -> str | None:
    """
    Загружает токен авторизации из файла.

    Returns:
        Токен авторизации или None, если файл не найден или повреждён.
    """
    token_file = _get_token_file_path()

    if not token_file.exists():
        return None

    try:
        with open(token_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        token = [REDACTED_SECRET]"token")
        if token and isinstance(token, str):
            return token
        return None
    except (json.JSONDecodeError, OSError):
        return None
