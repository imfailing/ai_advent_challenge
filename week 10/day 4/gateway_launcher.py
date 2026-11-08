"""
Запуск LLM-шлюза из day 3 с журналами в runs/gateway/ этого дня.

Роль: шлюз из `week 10/day 3` пишет аудит в свою папку `logs/`, а нам нужен отдельный журнал на время
прогона цикла, чтобы по нему проверить, что реально ушло в модель. Лаунчер подставляет каталог журнала
и поднимает тот же Flask-приложение. Запускать интерпретатором venv из day 3 (там стоит Flask):
  "../day 3/venv/bin/python" gateway_launcher.py   # порт из PORT, по умолчанию 5013
Ключ и адрес модели — из LLAMA_API_KEY и LLAMA_BASE_URL (как у самого шлюза).
"""

import os
import sys
from pathlib import Path

GATEWAY_DIR = Path(__file__).resolve().parent.parent / "day 3"
sys.path.insert(0, str(GATEWAY_DIR))

import app as gateway_app  # noqa: E402
import audit  # noqa: E402

if __name__ == "__main__":
    audit.LOG_DIR = Path(__file__).parent / "runs" / "gateway"
    gateway_app.app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5013")))
