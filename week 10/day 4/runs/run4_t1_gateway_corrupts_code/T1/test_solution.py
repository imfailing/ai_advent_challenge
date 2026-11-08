"""Тесты для модуля токенов авторизации."""

import json
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import solution


class TestTokenFunctions(unittest.TestCase):
    """Тесты для save_token и load_token."""

    def setUp(self):
        """Подготовка тестового окружения."""
        self.temp_dir = tempfile.mkdtemp()
        self.token_file = Path(self.temp_dir) / ".app_token.json"
        self.original_token_file = solution._TOKEN_FILE
        solution._TOKEN_FILE = self.token_file

    def tearDown(self):
        """Очистка после теста."""
        solution._TOKEN_FILE = self.original_token_file
        if self.token_file.exists():
            self.token_file.unlink()
        os.rmdir(self.temp_dir)

    def test_save_token_valid(self):
        """Тест сохранения валидного токена."""
        token = "[REDACTED_SECRET]"
        solution.save_token(token)
        
        self.assertTrue(self.token_file.exists())
        with open(self.token_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["token"], token)

    def test_save_token_empty_raises(self):
        """Тест что пустой токен вызывает ошибку."""
        with self.assertRaises(ValueError):
            solution.save_token("")

    def test_save_token_none_raises(self):
        """Тест что None вызывает ошибку."""
        with self.assertRaises(ValueError):
            solution.save_token(None)

    def test_load_token_exists(self):
        """Тест загрузки существующего токена."""
        token = "[REDACTED_SECRET]"
        self.token_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.token_file, "w", encoding="utf-8") as f:
            json.dump({"token": [REDACTED_SECRET] f)
        
        result = solution.load_token()
        self.assertEqual(result, token)

    def test_load_token_not_exists(self):
        """Тест загрузки несуществующего токена."""
        result = solution.load_token()
        self.assertIsNone(result)

    def test_load_token_invalid_json(self):
        """Тест обработки невалидного JSON."""
        self.token_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.token_file, "w", encoding="utf-8") as f:
            f.write("invalid json")
        
        result = solution.load_token()
        self.assertIsNone(result)

    def test_file_permissions(self):
        """Тест что файл имеет правильные права доступа."""
        token = "[REDACTED_SECRET]"
        solution.save_token(token)
        
        mode = os.stat(self.token_file).st_mode
        self.assertEqual(mode & 0o777, stat.S_IRUSR | stat.S_IWUSR)


def main():
    """Запуск тестов."""
    suite = unittest.TestLoader().loadTestsFromTestCase(TestTokenFunctions)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    if result.wasSuccessful():
        print("✅ Все тесты пройдены")
    else:
        print("❌ Некоторые тесты не пройдены")
    
    return result.wasSuccessful()


if __name__ == "__main__":
    import sys
    success = main()
    sys.exit(0 if success else 1)
