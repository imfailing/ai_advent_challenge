"""
Query rewrite: переформулировка запроса перед поиском.

LLM превращает вопрос пользователя в 2–3 поисковых варианта: расширяет
термины, добавляет синонимы/ключевые слова, разбивает «списковые» вопросы.
Это повышает recall — особенно когда ответ разбросан по нескольким чанкам
(как вопрос «какие три стратегии…», где каждая стратегия в своей секции).

Возвращает список запросов (включая исходный); поиск идёт по всем,
результаты объединяются.
"""

import json
import os

from openai import OpenAI

MODEL = "deepseek-v4-flash"


class QueryRewriter:
    PROMPT = (
        "Ты помогаешь поиску по базе документов. Перепиши вопрос пользователя "
        "в 2–3 РАЗНЫХ поисковых запроса: раскрой термины, добавь ключевые слова "
        "и синонимы, а если вопрос про перечисление (несколько пунктов) — сделай "
        "отдельные запросы под разные пункты. Верни ТОЛЬКО JSON-массив строк, "
        "без markdown. Вопрос: {q}"
    )

    def __init__(self, api_key: str | None = None, model: str = MODEL) -> None:
        self._client = OpenAI(
            api_key=api_key or os.environ["DEEPSEEK_API_KEY"],
            base_url="https://api.deepseek.com",
        )
        self._model = model

    def rewrite(self, question: str) -> list[str]:
        try:
            resp = self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": self.PROMPT.format(q=question)}],
            )
            raw = resp.choices[0].message.content.strip()
            if "```" in raw:
                raw = raw.split("```")[1].lstrip("json").strip()
            variants = json.loads(raw)
            queries = [question] + [v for v in variants if isinstance(v, str) and v.strip()]
            # уникализируем, сохраняя порядок
            seen, out = set(), []
            for q in queries:
                if q not in seen:
                    seen.add(q); out.append(q)
            return out[:4]
        except Exception:
            return [question]   # сбой rewrite не ломает поиск
