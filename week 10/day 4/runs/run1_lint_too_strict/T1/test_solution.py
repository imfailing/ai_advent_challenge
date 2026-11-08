"""Тесты для модуля сохранения и загрузки токена."""

import json
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestTokenStorage(unittest.TestCase):
    """Тесты функций save_token и load_token."""

    def setUp(self):
        """Создаёт временную директорию для тестов."""
        self.temp_dir = tempfile.mkdtemp()
        self.token_file = Path(self.temp_dir) / "auth_token.json"

    def tearDown(self):
        """Очищает временную директорию."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch("solution._get_token_file_path")
    def test_save_token_success(self, mock_path):
        """Тест успешного сохранения токена."""
        mock_path.return_value = self.token_file

        from solution import save_token

        save_token("test_token_123")

        self.assertTrue(self.token_file.exists())
        with open(self.token_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertEqual(data["token"], "test_token_123")

    @patch("solution._get_token_file_path")
    def test_save_token_empty_raises(self, mock_path):
        """Тест что пустой токен вызывает ValueError."""
        mock_path.return_value = self.token_file

        from solution import save_token

        with self.assertRaises(ValueError):
            save_token("")

        with self.assertRaises(ValueError):
            save_token(None)

    @patch("solution._get_token_file_path")
    def test_load_token_success(self, mock_path):
        """Тест успешной загрузки токена."""
        mock_path.return_value = self.token_file
        self.token_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.token_file, "w", encoding="utf-8") as f:
            json.dump({"token": "loaded_token_456"}, f)

        from solution import load_token

        token = [REDACTED_SECRET]
        self.assertEqual(token, "loaded_token_456")

    @patch("solution._get_token_file_path")
    def test_load_token_file_not_found(self, mock_path):
        """Тест что load_token возвращает None если файл не найден."""
        mock_path.return_value = self.token_file

        from solution import load_token

        token = [REDACTED_SECRET]
        self.assertIsNone(token)

    @patch("solution._get_token_file_path")
    def test_load_token_invalid_json(self, mock_path):
        """Тест что load_token возвращает None при повреждённом JSON."""
        mock_path.return_value = self.token_file
        self.token_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.token_file, "w", encoding="utf-8") as f:
            f.write("invalid json {")

        from solution import load_token

        token = [REDACTED_SECRET]
        self.assertIsNone(token)

    @patch("solution._get_token_file_path")
    def test_load_token_missing_key(self, mock_path):
        """Тест что load_token возвращает None если нет ключа token."""
        mock_path.return_value = self.token_file
        self.token_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.token_file, "w", encoding="utf-8") as f:
            json.dump({"other": "value"}, f)

        from solution import load_token

        token = [REDACTED_SECRET]
        self.assertIsNone(token)

    @patch("solution._get_token_file_path")
    def test_save_token_sets_permissions(self, mock_path):
        """Тест что файл токена имеет правильные права доступа."""
        mock_path.return_value = self.token_file

        from solution import save_token

        save_token("test_token")

        file_stat = os.stat(self.token_file)
        mode = file_stat.st_mode & 0o777
        self.assertEqual(mode, stat.S_IRUSR | stat.S_IWUSR)


def main():
    """Запуск тестов с выводом результатов."""
    suite = unittest.TestLoader().loadTestsFromTestCase(TestTokenStorage)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    if result.wasSuccessful():
        print("✅ Все тесты пройдены")
    else:
        print("❌ Некоторые тесты не пройдены")

    return result.wasSuccessful()


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
