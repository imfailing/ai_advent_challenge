"""
Rate limiting: не больше N запросов в минуту с одного IP (скользящее окно).

Роль в сервисе: защита шлюза от перебора и от перерасхода токенов. Состояние процесса —
модульный dict `_hits` (в памяти, сбрасывается при перезапуске; для нескольких воркеров
нужен общий стор, см. README). Модуль чистый: время можно передать явно для тестов.
"""

import time
from collections import deque

LIMIT_PER_MINUTE = 20
WINDOW_SECONDS = 60.0

_hits: dict[str, deque[float]] = {}


def check(ip: str, now: float | None = None, limit: int = LIMIT_PER_MINUTE,
          window: float = WINDOW_SECONDS) -> tuple[bool, int]:
    """Учесть запрос с адреса `ip`; вернуть (разрешён, секунд до освобождения слота)."""
    now = time.monotonic() if now is None else now
    hits = _hits.setdefault(ip, deque())
    while hits and now - hits[0] >= window:
        hits.popleft()
    if len(hits) >= limit:
        return False, max(1, int(window - (now - hits[0])) + 1)
    hits.append(now)
    return True, 0


def reset() -> None:
    """Сбросить счётчики (для тестов)."""
    _hits.clear()
