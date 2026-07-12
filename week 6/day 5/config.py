"""
Конфигурация сервиса — из переменных окружения (12-factor, удобно для VPS).
Значения по умолчанию безопасны для локального теста; на проде задаются в .env.
"""

import os


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


# Аутентификация: список API-ключей через запятую. Пусто → auth выключен (dev).
API_KEYS = {k.strip() for k in os.environ.get("API_KEYS", "").split(",") if k.strip()}
REQUIRE_AUTH = bool(API_KEYS)

# Rate limit: сколько запросов за окно на один ключ/IP.
RATE_LIMIT  = _int("RATE_LIMIT", 30)      # запросов
RATE_WINDOW = _int("RATE_WINDOW", 60)     # секунд

# Ограничения контекста.
MAX_INPUT_CHARS = _int("MAX_INPUT_CHARS", 8000)   # макс. длина входа (символы)
MAX_HISTORY     = _int("MAX_HISTORY", 20)         # макс. сообщений истории
NUM_CTX         = _int("NUM_CTX", 4096)           # окно контекста модели (Ollama)
NUM_PREDICT     = _int("NUM_PREDICT", 512)        # макс. токенов ответа

# Модель и локальный Ollama.
MODEL      = os.environ.get("MODEL", "qwen2.5:1.5b")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")

# Порт сервиса.
PORT = _int("PORT", 5008)
