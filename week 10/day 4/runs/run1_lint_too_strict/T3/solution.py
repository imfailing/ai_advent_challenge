"""Модуль для получения пользователей из API."""

import json
import urllib.error
import urllib.request

from config import API_BASE, API_KEY


def fetch_users():
    """
    Выполняет запрос к API и возвращает список пользователей.

    Returns:
        list: Список словарей с данными пользователей.

    Raises:
        urllib.error.HTTPError: При ошибке HTTP.
        urllib.error.URLError: При ошибке сети.
        ValueError: При некорректном ответе API.
    """
    url = f"{API_BASE}/users"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Accept": "application/json",
    }

    req = urllib.request.Request(url, headers=headers)

    with urllib.request.urlopen(req, timeout=30) as response:
        data = response.read().decode("utf-8")
        result = json.loads(data)

    if isinstance(result, list):
        return result
    elif isinstance(result, dict) and "users" in result:
        return result["users"]
    else:
        raise ValueError("Некорректный формат ответа API")
