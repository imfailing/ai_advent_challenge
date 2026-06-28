"""
Проверка планировщика и хранилища (без LLM):
  • периодический сбор накапливает данные в SQLite;
  • summary() возвращает корректный агрегат;
  • отложенное напоминание срабатывает по расписанию;
  • периодические снапшоты сводок сохраняются.
"""

import time

import store
from scheduler import Scheduler


def run() -> None:
    # чистый старт
    if store.DB_PATH.exists():
        store.DB_PATH.unlink()
    store.init_db()

    # быстрый планировщик: тик 0.2с, снапшот сводки каждые 3 тика
    sched = Scheduler(interval=0.2, summary_every=3, summary_window_min=5.0)

    # отложенное напоминание — сработает через ~0.6с
    store.add_reminder("собрать отчёт", in_seconds=0.6)
    assert len(store.list_reminders("pending")) == 1
    print("✅ напоминание поставлено (отложенное выполнение)")

    sched.start()
    time.sleep(2.0)   # даём поработать ~10 тиков
    sched.stop()
    time.sleep(0.3)

    # 1. данные накопились
    n = store.sample_count()
    assert n >= 5, f"ожидалось ≥5 измерений, собрано {n}"
    print(f"✅ периодический сбор: накоплено {n} измерений в SQLite")

    # 2. агрегированная сводка
    s = store.summarize(minutes=5)
    assert s["count"] == n and s["avg"] is not None
    assert s["min"] <= s["avg"] <= s["max"]
    print(f"✅ сводка: count={s['count']} avg={s['avg']} "
          f"min={s['min']} max={s['max']} last={s['last']}")

    # 3. напоминание сработало по расписанию
    fired = store.list_reminders("fired")
    assert len(fired) == 1 and fired[0]["fired_at"], "напоминание не сработало"
    assert len(store.list_reminders("pending")) == 0
    print(f"✅ напоминание сработало в {fired[0]['fired_at']}")

    # 4. периодические снапшоты сводок сохранены
    snaps = store.recent_summaries(limit=10)
    assert len(snaps) >= 2, f"ожидалось ≥2 снапшота, есть {len(snaps)}"
    print(f"✅ периодические снапшоты сводок: {len(snaps)} шт.")

    print("\n✅ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ")


if __name__ == "__main__":
    run()
