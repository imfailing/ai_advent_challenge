"""Тесты для модуля solution."""

import json
import unittest
from unittest.mock import patch, MagicMock
from urllib.error import HTTPError, URLError

from solution import fetch_users


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
            result = fetch_users()

        self.assertEqual(result, mock_data)
        self.assertIsInstance(result, list)

    def test_fetch_users_empty_response(self):
        """Тест обработки пустого ответа."""
        mock_response = MagicMock()
        mock_response.read.return_value = b"[]"
        mock_response.__enter__ = lambda self: mock_response
        mock_response.__exit__ = lambda self, *args: None

        with patch("urllib.request.urlopen", return_value=mock_response):
            result = fetch_users()

        self.assertEqual(result, [])

    def test_fetch_users_http_error(self):
        """Тест обработки HTTP ошибки."""
        with patch("urllib.request.urlopen", side_effect=HTTPError(
            url="https://api.example.com/v1/users",
            code=401,
            msg="Unauthorized",
            hdrs={},
            fp=None
        )):
            with self.assertRaises(HTTPError):
                fetch_users()

    def test_fetch_users_url_error(self):
        """Тест обработки ошибки сети."""
        with patch("urllib.request.urlopen", side_effect=URLError("Connection failed")):
            with self.assertRaises(URLError):
                fetch_users()


def main():
    """Запуск тестов с выводом результатов."""
    suite = unittest.TestLoader().loadTestsFromTestCase(TestFetchUsers)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    if result.wasSuccessful():
        print("✅ Все тесты пройдены успешно")
    else:
        print("❌ Некоторые тесты не пройдены")

    return result.wasSuccessful()


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
