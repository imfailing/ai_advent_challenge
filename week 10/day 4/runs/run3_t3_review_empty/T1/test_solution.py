"""Тесты для модуля токенов."""

from pathlib import Path
from unittest.mock import patch
import tempfile

import solution


def test_save_token():
    """Тест сохранения токена."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / ".test_token"
        with patch.object(solution, "TOKEN_FILE", test_file):
            solution.save_token("test_token_123")
            assert test_file.exists(), "Файл токена должен быть создан"
            assert test_file.read_text() == "test_token_123", "Токен должен быть сохранён"
    print("✅ save_token работает корректно")


def test_load_token_exists():
    """Тест загрузки существующего токена."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / ".test_token"
        test_file.write_text("loaded_token")
        with patch.object(solution, "TOKEN_FILE", test_file):
            result = solution.load_token()
            assert result == "loaded_token", "Токен должен быть загружен"
    print("✅ load_token возвращает токен при наличии файла")


def test_load_token_not_exists():
    """Тест загрузки при отсутствии файла."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / ".test_token"
        with patch.object(solution, "TOKEN_FILE", test_file):
            result = solution.load_token()
            assert result is None, "Должен вернуть None при отсутствии файла"
    print("✅ load_token возвращает None при отсутствии файла")


def test_load_token_error():
    """Тест обработки ошибок при чтении."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / ".test_token"
        test_file.write_bytes(b"\x00\x01\x02")
        with patch.object(solution, "TOKEN_FILE", test_file):
            result = solution.load_token()
            assert result is None, "Должен вернуть None при ошибке чтения"
    print("✅ load_token обрабатывает ошибки чтения")


def main():
    """Запуск всех тестов."""
    test_save_token()
    test_load_token_exists()
    test_load_token_not_exists()
    test_load_token_error()


if __name__ == "__main__":
    main()
