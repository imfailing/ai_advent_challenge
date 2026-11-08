"""Тесты для модуля solution."""

import json
import sys
from unittest.mock import MagicMock, patch

# Подменяем config до импорта solution
mock_config = MagicMock()
mock_config.API_KEY = "[REDACTED_SECRET]"
mock_config.API_BASE = "https://api.example.com/v1"
sys.modules["config"] = mock_config

import solution


def test_fetch_users():
    """Тест функции fetch_users с подменой urllib.request.urlopen."""
    mock_data = {"users": [{"id": 1, "name": "Test"}]}
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps(mock_data).encode("utf-8")
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = lambda s, *args: None

    with patch.object(solution.urllib.request, "urlopen", return_value=mock_response):
        result = solution.fetch_users()

    assert result == [{"id": 1, "name": "Test"}], "Users list mismatch"


def test_fetch_users_empty():
    """Тест функции fetch_users с пустым списком пользователей."""
    mock_data = {"users": []}
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps(mock_data).encode("utf-8")
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = lambda s, *args: None

    with patch.object(solution.urllib.request, "urlopen", return_value=mock_response):
        result = solution.fetch_users()

    assert result == [], "Empty users list mismatch"


def test_fetch_users_no_key():
    """Тест функции fetch_users при отсутствии ключа users в ответе."""
    mock_data = {"data": [{"id": 1}]}
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps(mock_data).encode("utf-8")
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = lambda s, *args: None

    with patch.object(solution.urllib.request, "urlopen", return_value=mock_response):
        result = solution.fetch_users()

    assert result == [], "Default empty list should be returned"


def main():
    """Запуск всех тестов."""
    try:
        test_fetch_users()
        test_fetch_users_empty()
        test_fetch_users_no_key()
        print("✅ All tests passed")
    except AssertionError as e:
        print(f"❌ Test failed: {e}")
        raise


if __name__ == "__main__":
    main()
