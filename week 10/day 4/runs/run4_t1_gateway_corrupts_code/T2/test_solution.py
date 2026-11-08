"""Тесты для модуля логирования HTTP-запросов."""

import json
import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from solution import log_request, make_request, LOG_FILE


class TestLogRequest(unittest.TestCase):
    """Тесты функции log_request."""

    def setUp(self):
        """Подготовка тестового окружения."""
        self.temp_dir = tempfile.mkdtemp()
        self.log_file = os.path.join(self.temp_dir, "app.log")
        self.original_log_file = LOG_FILE

    def tearDown(self):
        """Очистка после тестов."""
        if os.path.exists(self.log_file):
            os.remove(self.log_file)
        os.rmdir(self.temp_dir)

    @patch("solution.LOG_FILE")
    def test_log_request_basic(self, mock_log_file):
        """Тест базового логирования запроса."""
        mock_log_file.return_value = self.log_file

        log_request("GET", "https://api.example.com/users", {}, "")

        self.assertTrue(os.path.exists(self.log_file))
        with open(self.log_file, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn('"method": "GET"', content)
        self.assertIn('"url": "https://api.example.com/users"', content)

    @patch("solution.LOG_FILE")
    def test_log_request_sensitive_headers(self, mock_log_file):
        """Тест маскировки чувствительных заголовков."""
        mock_log_file.return_value = self.log_file

        headers = {
            "Authorization": "Bearer secret123",
            "X-API-Key": "[REDACTED_SECRET]",
            "Content-Type": "application/json",
        }
        log_request("POST", "https://api.example.com/data", headers, "")

        with open(self.log_file, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn('"Authorization": "[REDACTED]"', content)
        self.assertIn('"X-API-Key": "[REDACTED_SECRET]"', content)
        self.assertIn('"Content-Type": "application/json"', content)

    @patch("solution.LOG_FILE")
    def test_log_request_sensitive_body(self, mock_log_file):
        """Тест маскировки чувствительных данных в теле."""
        mock_log_file.return_value = self.log_file

        body = json.dumps({"password": "[REDACTED_SECRET]", "username": "user1"})
        log_request("POST", "https://api.example.com/login", {}, body)

        with open(self.log_file, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn('"password": "[REDACTED_SECRET]"', content)
        self.assertIn('"username": "user1"', content)

    @patch("solution.LOG_FILE")
    def test_log_request_none_values(self, mock_log_file):
        """Тест обработки None значений."""
        mock_log_file.return_value = self.log_file

        log_request("GET", "https://api.example.com", None, None)

        with open(self.log_file, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn('"headers": {}', content)
        self.assertIn('"body": ""', content)


class TestMakeRequest(unittest.TestCase):
    """Тесты функции make_request."""

    @patch("solution.log_request")
    @patch("solution.urlopen")
    def test_make_request_success(self, mock_urlopen, mock_log_request):
        """Тест успешного запроса."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.read.return_value = b'{"result": "ok"}'
        mock_urlopen.return_value.__enter__.return_value = mock_response

        result = make_request("GET", "https://api.example.com/test", {}, "")

        mock_log_request.assert_called_once()
        self.assertTrue(result["success"])
        self.assertEqual(result["status"], 200)

    @patch("solution.log_request")
    @patch("solution.urlopen")
    def test_make_request_http_error(self, mock_urlopen, mock_log_request):
        """Тест обработки HTTP ошибки."""
        mock_error = MagicMock()
        mock_error.code = 404
        mock_error.headers = {"Content-Type": "text/html"}
        mock_error.read.return_value = b"Not Found"
        mock_error.fp = True
        mock_urlopen.side_effect = mock_error

        result = make_request("GET", "https://api.example.com/notfound", {}, "")

        mock_log_request.assert_called_once()
        self.assertFalse(result["success"])
        self.assertEqual(result["status"], 404)

    @patch("solution.log_request")
    @patch("solution.urlopen")
    def test_make_request_url_error(self, mock_urlopen, mock_log_request):
        """Тест обработки ошибки соединения."""
        from urllib.error import URLError
        mock_urlopen.side_effect = URLError("Connection refused")

        result = make_request("GET", "https://invalid.url/test", {}, "")

        mock_log_request.assert_called_once()
        self.assertFalse(result["success"])
        self.assertIsNone(result["status"])


def main():
    """Запуск тестов с проверками."""
    print("Запуск тестов...")

    # Тест 1: Проверка существования функции log_request
    from solution import log_request
    assert callable(log_request), "Функция log_request должна быть вызываемой"
    print("✅ Функция log_request существует и вызываема")

    # Тест 2: Проверка маскировки заголовков
    with tempfile.TemporaryDirectory() as tmpdir:
        test_log = os.path.join(tmpdir, "test.log")
        with patch("solution.LOG_FILE", test_log):
            log_request("POST", "https://test.com", {"Authorization": "secret"}, "")
            with open(test_log, "r", encoding="utf-8") as f:
                content = f.read()
            assert "[REDACTED]" in content, "Чувствительные данные должны быть замаскированы"
            assert "secret" not in content, "Чувствительные данные не должны быть в логе"
    print("✅ Чувствительные заголовки корректно маскируются")

    # Тест 3: Проверка маскировки тела запроса
    with tempfile.TemporaryDirectory() as tmpdir:
        test_log = os.path.join(tmpdir, "test.log")
        with patch("solution.LOG_FILE", test_log):
            body = json.dumps({"password": "[REDACTED_SECRET]", "data": "public"})
            log_request("POST", "https://test.com", {}, body)
            with open(test_log, "r", encoding="utf-8") as f:
                content = f.read()
            assert "[REDACTED]" in content, "Чувствительные данные в теле должны быть замаскированы"
            assert "secret123" not in content, "Пароль не должен быть в логе"
            assert "public" in content, "Публичные данные должны быть в логе"
    print("✅ Чувствительные данные в теле запроса корректно маскируются")

    # Тест 4: Проверка формата лога
    with tempfile.TemporaryDirectory() as tmpdir:
        test_log = os.path.join(tmpdir, "test.log")
        with patch("solution.LOG_FILE", test_log):
            log_request("GET", "https://test.com", {}, "")
            with open(test_log, "r", encoding="utf-8") as f:
                line = f.readline()
            log_data = json.loads(line)
            assert "timestamp" in log_data, "Лог должен содержать timestamp"
            assert "method" in log_data, "Лог должен содержать method"
            assert "url" in log_data, "Лог должен содержать url"
            assert "headers" in log_data, "Лог должен содержать headers"
            assert "body" in log_data, "Лог должен содержать body"
    print("✅ Формат лога соответствует требованиям")

    print("\n✅ Все тесты пройдены успешно!")


if __name__ == "__main__":
    main()
