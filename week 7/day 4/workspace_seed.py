"""
Пересоздаёт песочницу workspace/ с детерминированным мини-проектом.

Так результат работы агента ВОСПРОИЗВОДИМ: каждый прогон стартует с одного и
того же состояния файлов. Агент читает/ищет/пишет только внутри workspace/.
"""

import shutil
from pathlib import Path

WORKSPACE = Path(__file__).parent / "workspace"

FILES = {
    "logger.py": '''"""Компонент логирования проекта."""


class Logger:
    def __init__(self, name: str) -> None:
        self.name = name

    def info(self, msg: str) -> None:
        print(f"[INFO {self.name}] {msg}")

    def error(self, msg: str) -> None:
        print(f"[ERROR {self.name}] {msg}")
''',

    "service_a.py": '''"""Сервис A — обработка заказов."""

from logger import Logger

log = Logger("service_a")


def process_order(order_id: int) -> None:
    log.info(f"обработка заказа {order_id}")
    if order_id < 0:
        log.error("некорректный id заказа")
''',

    "service_b.py": '''"""Сервис B — уведомления."""

from logger import Logger


def notify(user: str) -> None:
    log = Logger("service_b")
    log.info(f"уведомление для {user}")
''',

    # файл БЕЗ докстринга модуля — «нарушитель» для сценария проверки правил
    "utils.py": '''from logger import Logger

_log = Logger("utils")


def retry(fn, times: int = 3):
    for i in range(times):
        try:
            return fn()
        except Exception:
            _log.error(f"попытка {i + 1} не удалась")
    return None
''',

    # файл без Logger и без докстринга
    "config.py": '''DEBUG = True
TIMEOUT = 30
''',

    "README.md": '''# Demo-проект

Небольшой сервис. Документация в процессе.
''',
}


def seed() -> Path:
    if WORKSPACE.exists():
        shutil.rmtree(WORKSPACE)
    WORKSPACE.mkdir(parents=True)
    for name, content in FILES.items():
        (WORKSPACE / name).write_text(content, encoding="utf-8")
    return WORKSPACE


if __name__ == "__main__":
    p = seed()
    print(f"Песочница пересоздана: {p}")
    for f in sorted(p.iterdir()):
        print(f"  {f.name}")
