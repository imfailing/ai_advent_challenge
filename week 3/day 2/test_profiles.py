"""
Сравнительный тест персонализации.

Один и тот же вопрос задаётся от лица РАЗНЫХ профилей.
Демонстрирует, что ассистент автоматически адаптирует стиль, формат
и глубину ответа под активный профиль — без подсказок в самом вопросе.
"""

import os
import database as db
from agent import LLMAgent

QUESTION = "Что такое REST API?"

PROFILES = [
    {
        "name": "Новичок",
        "role": "студент, который только учится программировать",
        "expertise": "новичок", "tone": "дружелюбный", "verbosity": "кратко",
        "answer_format": "простыми словами, с бытовой аналогией",
        "constraints": "без технического жаргона; не длиннее 5 предложений",
    },
    {
        "name": "Backend-эксперт",
        "role": "senior backend-разработчик",
        "expertise": "эксперт", "tone": "формальный", "verbosity": "подробно",
        "answer_format": "с техническими деталями и примерами",
        "constraints": "не объяснять базовые вещи; фокус на нюансах и best practices",
    },
]


def run():
    db.init_db()
    print(f"ВОПРОС (одинаковый для всех): «{QUESTION}»")
    print("=" * 70)

    for spec in PROFILES:
        sid = f"prof-test-{spec['name']}"
        db.ensure_session(sid)
        # каждый профиль — в своей чистой сессии, чтобы не мешалась история
        db.clear_short_term(sid)
        prof = db.create_profile(sid, **spec)
        db.set_active_profile_id(sid, prof["id"])

        agent = LLMAgent(session_id=sid, auto_route=False)  # роутер не нужен для теста
        r = agent.ask(QUESTION)

        print(f"\n### Профиль: {spec['name']} "
              f"({spec['expertise']}, {spec['tone']}, {spec['verbosity']})")
        print(f"Ограничения: {spec['constraints']}")
        print("-" * 70)
        print(r.answer)
        print(f"\n[токенов ответа: {r.usage.completion_tokens} · {r.elapsed_sec} с]")
        print("=" * 70)


if __name__ == "__main__":
    run()
