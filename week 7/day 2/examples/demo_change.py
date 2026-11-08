"""Демо-изменение для проверки AI-ревью (week 7/day 2). Содержит намеренные проблемы."""

import os

API_KEY = "sk-demo-hardcoded-key-123456"   # секрет прямо в коде


def average_tokens(messages):
    total = 0
    for m in messages:
        total = total + m["tokens"]          # KeyError, если у сообщения нет 'tokens'
    return total / len(messages)             # ZeroDivisionError при пустом списке


def load_config(path):
    f = open(path)                           # файл не закрывается
    return f.read()


def get_key():
    return API_KEY                           # возвращает хардкод вместо os.environ
