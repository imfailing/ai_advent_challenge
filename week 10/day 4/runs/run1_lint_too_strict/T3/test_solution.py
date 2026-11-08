"""Тесты для модуля solution.py."""

import json
import unittest
import urllib.error

from unittest.mock import MagicMock, patch

import solution


class TestFetchUsers(unittest.TestCase):
    """Тесты функции fetch_users."""

    def test_fetch_users_success(self):
        """Тест успешного получения пользователей."""
        mock_users = [
            {"id": 1, "name": "Иван Петров", "email": "[REDACTED_EMAIL]"},
            {"id": 2, "name": "Анна Крылова", "email": "[REDACTED_EMAIL]"},
        ]
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(mock_users).encode("utf-8")

        with patch("urllib.request.urlopen", return_value=mock_response):
            result = solution.fetch_users()

        self.assertEqual(result, mock_users)
        print("✅ test_fetch_users_success")

    def test_fetch_users_dict_response(self):
        """Тест ответа в формате dict с ключом users."""
        mock_users = [{"id": 1, "name": "Иван Петров"}]
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"users": mock_users}).encode("utf-8")

        with patch("urllib.request.urlopen", return_value=mock_response):
            result = solution.fetch_users()

        self.assertEqual(result, mock_users)
        print("✅ test_fetch_users_dict_response")

    def test_fetch_users_invalid_response(self):
        """Тест обработки некорректного ответа API."""
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"invalid": "data"}).encode("utf-8")

        with patch("urllib.request.urlopen", return_value=mock_response), self.assertRaises(ValueError):
            solution.fetch_users()

        print("✅ test_fetch_users_invalid_response")

    def test_fetch_users_network_error(self):
        """Тест обработки ошибки сети."""
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Network error")), self.assertRaises(urllib.error.URLError):
            solution.fetch_users()

        print("✅ test_fetch_users_network_error")


def main():
    """Запуск тестов."""
    suite = unittest.TestLoader().loadTestsFromTestCase(TestFetchUsers)
    runner = unittest.TextTestRunner(verbosity=0)
    result = runner.run(suite)

    if result.wasSuccessful():
        print("✅ Все тесты пройдены")
    else:
        print("❌ Некоторые тесты не пройдены")


if __name__ == "__main__":
    main()
