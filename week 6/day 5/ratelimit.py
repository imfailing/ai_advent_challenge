"""
Простой rate-limiter со скользящим окном, потокобезопасный (in-memory).
На один процесс. Для нескольких воркеров/инстансов — вынести в Redis.
"""

import threading
import time
from collections import defaultdict, deque


class RateLimiter:
    def __init__(self, limit: int, window: int) -> None:
        self.limit  = limit
        self.window = window
        self._hits: dict[str, deque] = defaultdict(deque)
        self._lock  = threading.Lock()

    def check(self, key: str) -> tuple[bool, int, int]:
        """
        Возвращает (разрешено, осталось_в_окне, retry_after_sec).
        Регистрирует попытку, если разрешено.
        """
        now = time.time()
        with self._lock:
            dq = self._hits[key]
            while dq and dq[0] <= now - self.window:
                dq.popleft()
            if len(dq) >= self.limit:
                retry = int(self.window - (now - dq[0])) + 1
                return False, 0, retry
            dq.append(now)
            return True, self.limit - len(dq), 0
