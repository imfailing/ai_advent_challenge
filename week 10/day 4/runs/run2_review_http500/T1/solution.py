"""Module for saving and loading authorization tokens."""
from pathlib import Path

TOKEN_FILE_PATH = Path.home() / ".service_token"


def save_token(token: str) -> None:
    """Save the authorization token to the local file system."""
    TOKEN_FILE_PATH.write_text(token, encoding="utf-8")


def load_token() -> str | None:
    """Load the authorization token from the local file system.

    Returns:
        The token string if the file exists, otherwise None.
    """
    if not TOKEN_FILE_PATH.exists():
        return None
    return TOKEN_FILE_PATH.read_text(encoding="utf-8")
