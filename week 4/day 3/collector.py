"""
Источник данных для периодического сбора.

Имитирует метрику «активные пользователи»: медленная синусоида + шум.
В реальном проекте здесь был бы вызов внешнего API / запрос к БД / чтение
системной метрики.
"""

import math
import random
import time

_START = time.time()


def sample() -> tuple[str, float]:
    """Снять одно измерение метрики. Возвращает (имя_метрики, значение)."""
    t    = time.time() - _START
    base = 50 + 30 * math.sin(t / 30)          # медленная волна
    val  = max(0.0, base + random.gauss(0, 5))  # + шум
    return "active_users", round(val, 1)
