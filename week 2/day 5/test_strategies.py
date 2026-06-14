"""
Автоматизированный сравнительный тест трёх стратегий управления контекстом.

Сценарий: сбор ТЗ для мобильного приложения (10–12 сообщений).
Каждая стратегия тестируется в отдельной сессии через HTTP.
"""

import json
import os
import time
import sys
import requests

BASE = "http://127.0.0.1:5000"

# ------------------------------------------------------------------
# Сценарий: ТЗ для мобильного приложения (12 ходов пользователя)
# ------------------------------------------------------------------
MESSAGES = [
    "Привет! Нам нужно составить ТЗ на мобильное приложение. Я буду описывать задачу, ты — помогать уточнять и структурировать. Готов?",
    "Приложение для доставки еды из ресторанов. Аудитория — городские жители 20–40 лет, Москва и Питер.",
    "Платформы: iOS и Android. Нативная разработка нецелесообразна, выбираем Flutter.",
    "Ключевые функции: каталог ресторанов, корзина, оплата картой и СБП, трекинг заказа в реальном времени.",
    "Ещё важно: система отзывов для ресторанов и курьеров, программа лояльности с баллами.",
    "По нефункциональным требованиям: время загрузки экрана < 2с, поддержка офлайн-режима для меню.",
    "Бэкенд — REST API на Python/FastAPI, БД PostgreSQL. Нужно API для ресторанов, чтобы они сами обновляли меню.",
    "Авторизация через номер телефона (SMS OTP). Соцсети пока не нужны.",
    "MVP срок — 4 месяца. Команда: 2 Flutter-разработчика, 1 бэкендер, 1 дизайнер.",
    "Вопрос: что мы могли забыть? Какие риски видишь в этом ТЗ?",
    "Хорошо, добавим пуш-уведомления как обязательный элемент MVP. Про GDPR — данные только в РФ, 152-ФЗ достаточно.",
    "Сформируй финальное краткое ТЗ: платформа, стек, функции MVP, нефункциональные требования, команда, сроки.",
]

# ------------------------------------------------------------------
# Вспомогательные функции
# ------------------------------------------------------------------

def new_session(strategy: str) -> dict:
    """Создать сессию с заданной стратегией. Возвращает cookies."""
    s = requests.Session()
    # GET / — получить cookie сессии
    r = s.get(BASE + "/")
    assert r.status_code == 200, f"GET / failed: {r.status_code}"
    # Установить стратегию
    r = s.post(BASE + "/strategy", json={"strategy": strategy})
    assert r.status_code == 200, f"POST /strategy failed: {r.status_code} {r.text}"
    return s


def send_message(session: requests.Session, message: str) -> dict:
    r = session.post(BASE + "/ask", json={"message": message})
    if r.status_code != 200:
        return {"error": r.text}
    return r.json()


def get_facts(session: requests.Session) -> dict:
    r = session.get(BASE + "/facts")
    return r.json() if r.status_code == 200 else {}


# ------------------------------------------------------------------
# Запуск теста одной стратегии
# ------------------------------------------------------------------

def run_strategy(strategy: str) -> dict:
    print(f"\n{'='*60}")
    print(f"  СТРАТЕГИЯ: {strategy.upper()}")
    print(f"{'='*60}")

    s = new_session(strategy)
    turns = []

    for i, msg in enumerate(MESSAGES, 1):
        print(f"\n--- Ход {i}/{len(MESSAGES)} ---")
        print(f"Пользователь: {msg[:80]}{'…' if len(msg) > 80 else ''}")

        result = send_message(s, msg)
        if "error" in result and "answer" not in result:
            print(f"ОШИБКА: {result['error']}")
            turns.append({"error": result["error"]})
            continue

        ctx  = result.get("context", {})
        usage = result.get("usage", {})

        print(f"Агент: {result['answer'][:200]}{'…' if len(result['answer']) > 200 else ''}")
        print(f"  Токены: {usage.get('prompt_tokens',0)} in + {usage.get('completion_tokens',0)} out  |  ${usage.get('cost_usd',0):.5f}")
        print(f"  Контекст: {ctx}")

        turns.append({
            "turn": i,
            "user": msg,
            "answer": result["answer"],
            "usage": usage,
            "context": ctx,
            "elapsed": result.get("elapsed_sec"),
        })

        time.sleep(0.5)  # небольшая пауза между запросами

    # Финальные факты (для sticky_facts)
    facts = get_facts(s)

    return {
        "strategy": strategy,
        "turns":    turns,
        "facts":    facts,
    }


# ------------------------------------------------------------------
# Агрегация метрик
# ------------------------------------------------------------------

def aggregate(data: dict) -> dict:
    turns = [t for t in data["turns"] if "error" not in t]
    total_prompt     = sum(t["usage"].get("prompt_tokens", 0)     for t in turns)
    total_completion = sum(t["usage"].get("completion_tokens", 0) for t in turns)
    total_cost       = sum(t["usage"].get("cost_usd", 0)          for t in turns)
    avg_prompt       = total_prompt / len(turns) if turns else 0
    last_ctx         = turns[-1]["context"] if turns else {}
    return {
        "total_prompt":     total_prompt,
        "total_completion": total_completion,
        "total_cost_usd":   round(total_cost, 5),
        "avg_prompt_per_turn": round(avg_prompt),
        "last_ctx":         last_ctx,
        "turns_ok":         len(turns),
    }


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------

def main():
    strategies = ["sliding_window", "sticky_facts", "branching"]
    results = {}

    for strategy in strategies:
        results[strategy] = run_strategy(strategy)
        time.sleep(1)

    # ------------------------------------------------------------------
    # Сводная таблица
    # ------------------------------------------------------------------
    print("\n\n" + "="*70)
    print("  СВОДНАЯ ТАБЛИЦА")
    print("="*70)
    print(f"{'Метрика':<35} {'Sliding':>10} {'Sticky':>10} {'Branching':>10}")
    print("-"*70)

    agg = {s: aggregate(results[s]) for s in strategies}

    rows = [
        ("Токенов в промпте (итого)", "total_prompt"),
        ("Токенов в ответах (итого)", "total_completion"),
        ("Стоимость, USD",            "total_cost_usd"),
        ("Средний промпт / ход",      "avg_prompt_per_turn"),
    ]
    for label, key in rows:
        vals = [agg[s][key] for s in strategies]
        print(f"{label:<35} {vals[0]:>10} {vals[1]:>10} {vals[2]:>10}")

    print("\n--- Контекст последнего хода ---")
    for s in strategies:
        ctx = agg[s]["last_ctx"]
        print(f"  {s}: {ctx}")

    # Факты sticky_facts
    facts = results["sticky_facts"].get("facts", {})
    print(f"\n--- Извлечённые факты (Sticky Facts) ---")
    for k, v in facts.items():
        print(f"  {k}: {v}")

    # Финальный ответ каждой стратегии (последний ход — генерация ТЗ)
    print("\n" + "="*70)
    print("  ФИНАЛЬНЫЙ ОТВЕТ (Ход 12: 'Сформируй финальное краткое ТЗ')")
    print("="*70)
    for s in strategies:
        turns = [t for t in results[s]["turns"] if "error" not in t]
        if turns:
            last = turns[-1]
            print(f"\n### {s.upper()}")
            print(last["answer"])
            print()

    # Сохраняем raw results
    out = "/tmp/strategy_test_results.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n[raw результаты сохранены в {out}]")


if __name__ == "__main__":
    main()
