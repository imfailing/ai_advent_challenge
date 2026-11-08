"""Тесты для модуля логирования HTTP-запросов."""

import json
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from solution import LOG_FILE, log_request, make_request


class TestLogRequest(unittest.TestCase):
    """Тесты функции log_request."""

    def setUp(self):
        """Настройка перед каждым тестом."""
        self.temp_dir = tempfile.mkdtemp()
        self.original_log_file = LOG_FILE
        os.chdir(self.temp_dir)
        if os.path.exists(LOG_FILE):
            os.remove(LOG_FILE)

    def tearDown(self):
        """Очистка после каждого теста."""
        os.chdir("/")
        if os.path.exists(self.temp_dir):
            for f in os.listdir(self.temp_dir):
                os.remove(os.path.join(self.temp_dir, f))
            os.rmdir(self.temp_dir)

    def test_log_request_writes_to_file(self):
        """Проверка записи в файл."""
        log_request("GET", "https://example.com", {"Content-Type": "application/json"})
        
        self.assertTrue(os.path.exists(LOG_FILE))
        
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            content = f.read()
        
        self.assertIn("GET", content)
        self.assertIn("https://example.com", content)

    def test_log_request_with_body(self):
        """Проверка записи с телом запроса."""
        body = '{"user": "test"}'
        log_request("POST", "https://api.example.com", {"Authorization": "Bearer token"}, body)
        
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            content = f.read()
        
        self.assertIn(body, content)
        self.assertIn("POST", content)

    def test_log_request_json_format(self):
        """Проверка JSON формата записи."""
        log_request("DELETE", "https://api.example.com/resource/1", {})
        
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            line = f.readline()
        
        log_entry = json.loads(line)
        
        self.assertIn("timestamp", log_entry)
        self.assertIn("method", log_entry)
        self.assertIn("url", log_entry)
        self.assertIn("headers", log_entry)
        self.assertIn("body", log_entry)
        self.assertEqual(log_entry["method"], "DELETE")
        self.assertEqual(log_entry["url"], "https://api.example.com/resource/1")

    def test_log_request_multiple_entries(self):
        """Проверка множественных записей."""
        log_request("GET", "https://example.com/1", {})
        log_request("POST", "https://example.com/2", {}, "data")
        log_request("PUT", "https://example.com/3", {})
        
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        self.assertEqual(len(lines), 3)


class TestMakeRequest(unittest.TestCase):
    """Тесты функции make_request."""

    def setUp(self):
        """Настройка перед каждым тестом."""
        self.temp_dir = tempfile.mkdtemp()
        os.chdir(self.temp_dir)
        if os.path.exists(LOG_FILE):
            os.remove(LOG_FILE)

    def tearDown(self):
        """Очистка после каждого теста."""
        os.chdir("/")
        if os.path.exists(self.temp_dir):
            for f in os.listdir(self.temp_dir):
                os.remove(os.path.join(self.temp_dir, f))
            os.rmdir(self.temp_dir)

    @patch("solution.urlopen")
    def test_make_request_logs_before_call(self, mock_urlopen):
        """Проверка логирования перед вызовом запроса."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.read.return_value = b'{"result": "ok"}'
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        make_request("GET", "https://api.example.com", {"X-Custom": "value"})
        
        self.assertTrue(os.path.exists(LOG_FILE))
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("GET", content)
        self.assertIn("https://api.example.com", content)

    @patch("solution.urlopen")
    def test_make_request_success_response(self, mock_urlopen):
        """Проверка успешного ответа."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.read.return_value = b'{"status": "success"}'
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        result = make_request("GET", "https://api.example.com")
        
        self.assertEqual(result["status"], 200)
        self.assertEqual(result["error"], None)
        self.assertIn("success", result["body"])

    @patch("solution.urlopen")
    def test_make_request_with_body(self, mock_urlopen):
        """Проверка запроса с телом."""
        mock_response = MagicMock()
        mock_response.status = 201
        mock_response.headers = {}
        mock_response.read.return_value = b'{"id": 1}'
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        result = make_request("POST", "https://api.example.com", {}, '{"name": "test"}')
        
        self.assertEqual(result["status"], 201)

    @patch("solution.urlopen")
    def test_make_request_http_error(self, mock_urlopen):
        """Проверка обработки HTTP ошибки."""
        from urllib.error import HTTPError
        
        mock_error = MagicMock(spec=HTTPError)
        mock_error.code = 404
        mock_error.headers = {}
        mock_error.fp = None
        mock_error.read.return_value = b'Not Found'
        mock_urlopen.side_effect = mock_error
        
        result = make_request("GET", "https://api.example.com/notfound")
        
        self.assertEqual(result["status"], 404)
        self.assertIsNotNone(result["error"])


def main():
    """Запуск тестов."""
    print("Запуск тестов...")
    
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    suite.addTests(loader.loadTestsFromTestCase(TestLogRequest))
    suite.addTests(loader.loadTestsFromTestCase(TestMakeRequest))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    if result.wasSuccessful():
        print("✅ Все тесты пройдены успешно")
    else:
        print("❌ Некоторые тесты не пройдены")
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
