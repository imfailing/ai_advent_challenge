"""Модуль для получения данных пользователей из API."""

import json
import urllib.request
import urllib.error

from config import API_KEY, API_BASE


def fetch_users():
    """
    Выполняет запрос к API и возвращает список пользователей.

    Returns:
        list: Список словарей с данными пользователей.

    Raises:
        urllib.error.HTTPError: При ошибке HTTP запроса.
        urllib.error.URLError: При ошибке соединения.
        json.JSONDecodeError: При ошибке парсинга JSON.
    """
    url = f"{API_BASE}/users"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Accept": "application/json",
    }

    request = urllib.request.Request(url, headers=headers)

    with urllib.request.urlopen(request, timeout=30) as response:
        data = response.read().decode("utf-8")
        return json.loads(data)
