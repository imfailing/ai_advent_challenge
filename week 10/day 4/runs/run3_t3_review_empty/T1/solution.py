"""Модуль для сохранения и загрузки токена авторизации."""

from pathlib import Path

TOKEN_FILE = Path.home() / ".report_service_token"


def save_token(token: str) -> None:
    """Сохраняет токен авторизации в файл."""
    TOKEN_FILE.write_text(token)
    try:
        import os
        os.chmod(TOKEN_FILE, 0o600)
    except OSError:
        pass


def load_token() -> str | None:
    """Загружает токен авторизации из файла."""
    if not TOKEN_FILE.exists():
        return None
    try:
        token = TOKEN_FILE.read_text().strip()
        # Validate token contains only printable ASCII characters
        if not token or not all(32 <= ord(c) < 127 for c in token):
            return None
        return token
    except (OSError, UnicodeDecodeError):
        return None
