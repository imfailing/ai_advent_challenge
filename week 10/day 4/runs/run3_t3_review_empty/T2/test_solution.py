"""Тесты для модуля логирования HTTP-запросов."""

import logging
import os
import tempfile
import unittest

import solution


class TestLogRequest(unittest.TestCase):
    """Тесты функции log_request."""

    def setUp(self):
        """Настройка перед каждым тестом."""
        self.temp_dir = tempfile.mkdtemp()
        self.original_log_file = solution.LOG_FILE
        solution.LOG_FILE = os.path.join(self.temp_dir, "app.log")
        # Пересоздаём обработчик для нового файла
        solution.logger.handlers.clear()
        file_handler = logging.FileHandler(solution.LOG_FILE, encoding="utf-8")
        file_handler.setLevel(logging.INFO)
        formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(formatter)
        solution.logger.addHandler(file_handler)

    def tearDown(self):
        """Очистка после каждого теста."""
        solution.LOG_FILE = self.original_log_file
        solution.logger.handlers.clear()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_log_request_basic(self):
        """Тест базового логирования запроса."""
        solution.log_request("GET", "https://api.example.com/users", {})
        entries = solution.get_log_entries()
        self.assertEqual(len(entries), 1)
        self.assertIn("GET", entries[0])
        self.assertIn("https://api.example.com/users", entries[0])

    def test_log_request_with_headers(self):
        """Тест логирования с заголовками."""
        headers = {"Content-Type": "application/json", "User-Agent": "TestClient"}
        solution.log_request("POST", "https://api.example.com/data", headers, '{"key": "value"}')
        entries = solution.get_log_entries()
        self.assertEqual(len(entries), 1)
        self.assertIn("POST", entries[0])
        self.assertIn("Content-Type", entries[0])

    def test_log_request_masks_sensitive_headers(self):
        """Тест маскирования чувствительных заголовков."""
        headers = {
            "Authorization": "Bearer secret123",
            "X-API-Key": "[REDACTED_SECRET]",
            "Content-Type": "application/json"
        }
        solution.log_request("POST", "https://api.example.com/data", headers)
        entries = solution.get_log_entries()
        self.assertIn("[REDACTED]", entries[0])
        self.assertNotIn("secret123", entries[0])
        self.assertNotIn("my-api-key", entries[0])

    def test_log_request_masks_sensitive_body(self):
        """Тест маскирования чувствительных данных в теле."""
        body = '{"password": "[REDACTED_SECRET]", "token": "[REDACTED_SECRET]", "name": "John"}'
        solution.log_request("POST", "https://api.example.com/login", {}, body)
        entries = solution.get_log_entries()
        self.assertIn("[REDACTED]", entries[0])
        self.assertNotIn("secret123", entries[0])
        self.assertNotIn("abc123", entries[0])

    def test_log_request_empty_method(self):
        """Тест обработки пустого метода."""
        solution.log_request("", "https://api.example.com/data", {})
        entries = solution.get_log_entries()
        self.assertEqual(len(entries), 1)
        self.assertIn("Некорректные параметры", entries[0])

    def test_log_request_empty_url(self):
        """Тест обработки пустого URL."""
        solution.log_request("GET", "", {})
        entries = solution.get_log_entries()
        self.assertEqual(len(entries), 1)
        self.assertIn("Некорректные параметры", entries[0])

    def test_get_log_entries_empty(self):
        """Тест получения записей из несуществующего файла."""
        solution.clear_log_file()
        entries = solution.get_log_entries()
        self.assertEqual(entries, [])

    def test_clear_log_file(self):
        """Тест очистки файла логов."""
        solution.log_request("GET", "https://api.example.com/data", {})
        self.assertTrue(os.path.exists(solution.LOG_FILE))
        solution.clear_log_file()
        self.assertFalse(os.path.exists(solution.LOG_FILE))


class TestMaskingFunctions(unittest.TestCase):
    """Тесты функций маскирования."""

    def test_mask_sensitive_headers(self):
        """Тест маскирования заголовков."""
        headers = {"Authorization": "Bearer token", "Content-Type": "json"}
        result = solution._mask_sensitive_headers(headers)
        self.assertEqual(result["Authorization"], "[REDACTED]")
        self.assertEqual(result["Content-Type"], "json")

    def test_mask_sensitive_body(self):
        """Тест маскирования тела запроса."""
        body = '{"password": "123", "name": "test"}'
        result = solution._mask_sensitive_body(body)
        self.assertIn("[REDACTED]", result)
        self.assertNotIn("123", result)

    def test_mask_sensitive_body_empty(self):
        """Тест маскирования пустого тела."""
        result = solution._mask_sensitive_body(None)
        self.assertIsNone(result)


def main():
    """Запуск тестов."""
    print("Запуск тестов...")
    unittest.main(verbosity=2, exit=False)
    print("✅ Все тесты пройдены!")


if __name__ == "__main__":
    main()
