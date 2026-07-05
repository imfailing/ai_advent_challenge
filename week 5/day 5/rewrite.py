"""
Query rewrite: переформулировка запроса перед поиском.

LLM превращает вопрос пользователя в 2–3 поисковых варианта: расширяет
термины, добавляет синонимы/ключевые слова, разбивает «списковые» вопросы.
Это повышает recall — особенно когда ответ разбросан по нескольким чанкам.

В чате важна КОНТЕКСТУАЛИЗАЦИЯ: уточняющие вопросы («а чем они отличаются?»,
«почему?», «расскажи про второй вариант») сами по себе не ищутся — их надо
превратить в самостоятельный вопрос по истории диалога, иначе поиск ничего
не находит. Поэтому rewrite принимает историю и сначала восстанавливает
полный вопрос, а затем даёт поисковые варианты.

Возвращает список запросов; поиск идёт по всем, результаты объединяются.
"""

import json
import os

from openai import OpenAI

MODEL = "deepseek-v4-flash"


class QueryRewriter:
    PROMPT = (
        "Ты помогаешь поиску по базе документов. Перепиши вопрос пользователя "
        "в 2–3 РАЗНЫХ поисковых запроса: раскрой термины, добавь ключевые слова "
        "и синонимы, а если вопрос про перечисление — сделай отдельные запросы "
        "под разные пункты. Верни ТОЛЬКО JSON-массив строк, без markdown.\n"
        "Вопрос: {q}"
    )

    PROMPT_CTX = (
        "Ты помогаешь поиску по базе документов в диалоге. Ниже — недавняя "
        "история диалога и новый вопрос. Если вопрос ссылается на историю "
        "(местоимения «они/это/его», «второй вариант», «почему», «а подробнее») "
        "— СНАЧАЛА восстанови полный самостоятельный вопрос, подставив нужные "
        "сущности из истории. Затем дай 2–3 поисковых запроса под этот полный "
        "вопрос (раскрой термины, синонимы). Верни ТОЛЬКО JSON-массив строк.\n\n"
        "История диалога:\n{history}\n\nНовый вопрос: {q}"
    )

    def __init__(self, api_key: str | None = None, model: str = MODEL) -> None:
        self._client = OpenAI(
            api_key=api_key or os.environ["DEEPSEEK_API_KEY"],
            base_url="https://api.deepseek.com",
        )
        self._model = model

    def rewrite(self, question: str, history: list[dict] | None = None) -> list[str]:
        """
        history — недавние сообщения [{role, content}]. Если передана, вопрос
        контекстуализируется (разрешаются ссылки на предыдущий диалог).
        """
        if history:
            hist_text = "\n".join(
                f"{'Пользователь' if m['role'] == 'user' else 'Ассистент'}: "
                f"{m['content'][:300]}" for m in history)
            content = self.PROMPT_CTX.format(history=hist_text, q=question)
        else:
            content = self.PROMPT.format(q=question)
        try:
            resp = self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": content}])
            raw = resp.choices[0].message.content.strip()
            if "```" in raw:
                raw = raw.split("```")[1].lstrip("json").strip()
            variants = json.loads(raw)
            queries = [question] + [v for v in variants if isinstance(v, str) and v.strip()]
            seen, out = set(), []
            for q in queries:
                if q not in seen:
                    seen.add(q); out.append(q)
            return out[:4]
        except Exception:
            return [question]   # сбой rewrite не ломает поиск
