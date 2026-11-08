"""Модуль для получения данных пользователей из API."""

import json
import urllib.error
import urllib.request

from config import API_BASE, API_KEY


def fetch_users():
    """
    Выполняет GET-запрос к API и возвращает список пользователей.

    Returns:
        list: Список словарей с данными пользователей.

    Raises:
        RuntimeError: При ошибках API или сети.
    """
    url = f"{API_BASE}/users"
    headers = {"Authorization": f"Bearer {API_KEY}"}
    req = urllib.request.Request(url, headers=headers)

    try:
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode("utf-8"))
            return data.get("users", [])
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"API Error: {e.code}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Network Error: {e.reason}") from e
