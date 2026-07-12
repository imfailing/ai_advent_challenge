"""
Фоновый планировщик — «сердце» 24/7-работы.

Каждый тик (раз в INTERVAL секунд):
  1. собирает измерение метрики и сохраняет в SQLite;
  2. проверяет и «зажигает» наступившие напоминания (отложенное выполнение);
  3. раз в SUMMARY_EVERY тиков сохраняет снапшот агрегированной сводки.

Работает в демоне-потоке, чтобы не блокировать MCP-сервер. Ничего не печатает
в stdout (там протокол MCP) — только пишет в БД.
"""

import threading

import collector
import store


class Scheduler(threading.Thread):
    def __init__(self, interval: float = 1.0, summary_every: int = 10,
                 summary_window_min: float = 5.0) -> None:
        super().__init__(daemon=True)
        self.interval           = interval
        self.summary_every      = summary_every
        self.summary_window_min = summary_window_min
        self._stop  = threading.Event()
        self.ticks  = 0

    def run(self) -> None:
        store.init_db()
        while not self._stop.is_set():
            # 1. сбор данных
            metric, value = collector.sample()
            store.add_sample(metric, value)
            # 2. отложенные напоминания
            store.fire_due_reminders()
            # 3. периодическая сводка
            self.ticks += 1
            if self.ticks % self.summary_every == 0:
                snap = store.summarize(self.summary_window_min, metric)
                store.add_summary_snapshot(snap)
            # ждём следующий тик (прерываемо)
            self._stop.wait(self.interval)

    def stop(self) -> None:
        self._stop.set()

    def status(self) -> dict:
        return {
            "running":            not self._stop.is_set(),
            "interval_sec":       self.interval,
            "ticks":              self.ticks,
            "summary_every":      self.summary_every,
            "ticks_to_summary":   self.summary_every - (self.ticks % self.summary_every),
            "total_samples":      store.sample_count(),
        }
