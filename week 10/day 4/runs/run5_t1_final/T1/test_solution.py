"""Тесты для модуля сохранения токена авторизации."""

import base64
import os
import tempfile
import unittest
from pathlib import Path

import solution


class TestTokenStorage(unittest.TestCase):
    """Тесты для функций save_token и load_token."""

    def setUp(self):
        """Подготовка тестового окружения."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_token = "[REDACTED_SECRET]"
        self._original_token_file = solution.TOKEN_FILE
        self._original_salt_file = solution.SALT_FILE

        solution.TOKEN_FILE = Path(self.temp_dir) / "token"
        solution.SALT_FILE = Path(self.temp_dir) / "salt"

    def tearDown(self):
        """Очистка после теста."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)
        solution.TOKEN_FILE = self._original_token_file
        solution.SALT_FILE = self._original_salt_file

    def test_save_token(self):
        """Тест сохранения токена."""
        solution.save_token(self.test_token)

        self.assertTrue(solution.TOKEN_FILE.exists())
        self.assertTrue(solution.SALT_FILE.exists())

        with open(solution.TOKEN_FILE, "rb") as f:
            encrypted = f.read()

        self.assertNotEqual(encrypted, self.test_token.encode("utf-8"))

        print("✅ test_save_token passed")

    def test_load_token(self):
        """Тест загрузки токена."""
        solution.save_token(self.test_token)

        token = solution.load_token()
        self.assertEqual(token, self.test_token)

        print("✅ test_load_token passed")

    def test_load_token_not_found(self):
        """Тест загрузки несуществующего токена."""
        token = solution.load_token()
        self.assertIsNone(token)

        print("✅ test_load_token_not_found passed")

    def test_save_token_empty(self):
        """Тест сохранения пустого токена."""
        with self.assertRaises(ValueError):
            solution.save_token("")

        print("✅ test_save_token_empty passed")

    def test_save_token_none(self):
        """Тест сохранения None токена."""
        with self.assertRaises(ValueError):
            solution.save_token(None)

        print("✅ test_save_token_none passed")

    def test_load_token_invalid_data(self):
        """Тест загрузки повреждённого файла."""
        solution.SALT_FILE.parent.mkdir(parents=True, exist_ok=True)

        fd = os.open(str(solution.TOKEN_FILE), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            os.write(fd, b"invalid json")
        finally:
            os.close(fd)

        token = solution.load_token()
        self.assertIsNone(token)

        print("✅ test_load_token_invalid_data passed")

    def test_load_token_corrupted_encryption(self):
        """Тест загрузки токена с повреждённым шифрованием."""
        solution.SALT_FILE.parent.mkdir(parents=True, exist_ok=True)

        fd = os.open(str(solution.TOKEN_FILE), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            os.write(fd, b"not_base64!@#$%")
        finally:
            os.close(fd)

        token = solution.load_token()
        self.assertIsNone(token)

        print("✅ test_load_token_corrupted_encryption passed")

    def test_encryption_changes_token(self):
        """Тест что шифрование меняет токен."""
        key, hmac_key = solution._get_encryption_key()
        encrypted = solution._encrypt_token(self.test_token, key, hmac_key)

        self.assertNotEqual(encrypted, self.test_token)
        self.assertNotEqual(encrypted, base64.b64encode(self.test_token.encode("utf-8")).decode("ascii"))

        print("✅ test_encryption_changes_token passed")

    def test_roundtrip_encryption(self):
        """Тест что шифрование/расшифрование работают корректно."""
        key, hmac_key = solution._get_encryption_key()
        encrypted = solution._encrypt_token(self.test_token, key, hmac_key)
        decrypted = solution._decrypt_token(encrypted, key, hmac_key)

        self.assertEqual(decrypted, self.test_token)

        print("✅ test_roundtrip_encryption passed")


def main():
    """Запуск тестов."""
    suite = unittest.TestLoader().loadTestsFromTestCase(TestTokenStorage)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    if result.wasSuccessful():
        print("\n✅ All tests passed!")
    else:
        print("\n❌ Some tests failed!")


if __name__ == "__main__":
    main()
