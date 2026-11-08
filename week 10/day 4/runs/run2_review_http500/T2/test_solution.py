"""Тесты для модуля логирования HTTP-запросов."""

import tempfile
from pathlib import Path
from unittest import TestCase, mock

from solution import log_request


class TestLogRequest(TestCase):
    """Тесты функции log_request."""

    def setUp(self):
        """Подготовка тестового окружения."""
        self.temp_dir = tempfile.mkdtemp()
        self.log_file = Path(self.temp_dir) / "app.log"

    @mock.patch("solution.open", new_callable=mock.mock_open)
    @mock.patch("solution.Path")
    def test_log_request_writes_to_file(self, mock_path, mock_open):
        """Тест записи в файл."""
        mock_path.return_value = self.log_file

        log_request("GET", "https://example.com", {"Content-Type": "application/json"}, "{}")

        mock_open.assert_called_once()
        print("✅ test_log_request_writes_to_file passed")

    @mock.patch("solution.open", new_callable=mock.mock_open)
    @mock.patch("solution.Path")
    def test_log_request_format(self, mock_path, mock_open):
        """Тест формата записи."""
        mock_path.return_value = self.log_file

        log_request(
            "POST",
            "https://api.example.com/v1/users",
            {"Authorization": "Bearer token"},
            '{"name": "test"}',
        )

        mock_open.assert_called_once()
        print("✅ test_log_request_format passed")

    @mock.patch("solution.open", new_callable=mock.mock_open)
    @mock.patch("solution.Path")
    def test_log_request_appends(self, mock_path, mock_open):
        """Тест добавления записей."""
        mock_path.return_value = self.log_file

        log_request("GET", "https://example.com/1", {}, "")
        log_request("POST", "https://example.com/2", {}, "")

        self.assertEqual(mock_open.call_count, 2)
        print("✅ test_log_request_appends passed")


def run_tests():
    """Запуск тестов."""
    test = TestLogRequest()
    test.setUp()
    test.test_log_request_writes_to_file()

    test.setUp()
    test.test_log_request_format()

    test.setUp()
    test.test_log_request_appends()

    print("\n✅ All tests passed!")


if __name__ == "__main__":
    run_tests()
