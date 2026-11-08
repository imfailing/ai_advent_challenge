"""Тесты для модуля solution."""

import json
import unittest
from unittest.mock import patch, MagicMock

import solution


class TestFetchUsers(unittest.TestCase):
    """Тесты функции fetch_users."""

    def test_fetch_users_success(self):
        """Тест успешного получения пользователей."""
        mock_data = [
            {"name": "Иван Петров", "email": "ivan@example.com"},
            {"name": "Анна Крылова", "email": "anna@example.com"},
        ]
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(mock_data).encode("utf-8")
        mock_response.__enter__ = lambda self: mock_response
        mock_response.__exit__ = lambda self, *args: None

        with patch("urllib.request.urlopen", return_value=mock_response):
            result = solution.fetch_users()

        self.assertEqual(result, mock_data)
        print("✅ Тест fetch_users_success пройден")

    def test_fetch_users_empty_response(self):
        """Тест обработки пустого ответа."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps([]).encode("utf-8")
        mock_response.__enter__ = lambda self: mock_response
        mock_response.__exit__ = lambda self, *args: None

        with patch("urllib.request.urlopen", return_value=mock_response):
            result = solution.fetch_users()

        self.assertEqual(result, [])
        print("✅ Тест fetch_users_empty_response пройден")

    def test_fetch_users_invalid_json(self):
        """Тест обработки некорректного JSON."""
        mock_response = MagicMock()
        mock_response.read.return_value = b"invalid json"
        mock_response.__enter__ = lambda self: mock_response
        mock_response.__exit__ = lambda self, *args: None

        with patch("urllib.request.urlopen", return_value=mock_response):
            with self.assertRaises(json.JSONDecodeError):
                solution.fetch_users()

        print("✅ Тест fetch_users_invalid_json пройден")


def main():
    """Запуск тестов."""
    unittest.main(verbosity=2, exit=False)


if __name__ == "__main__":
    main()
