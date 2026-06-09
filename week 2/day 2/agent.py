"""
LLMAgent с персистентной памятью через SQLite.

Отличие от week 2 / day 1:
  - история диалога хранится в БД, а не только в памяти процесса;
  - при создании агента (или перезапуске сервера) история загружается
    из БД — диалог продолжается с того места, где остановился;
  - save/load/clear инкапсулированы внутри агента, Flask и LLM
    по-прежнему ничего не знают о деталях хранения.
"""

import os
import time
from dataclasses import dataclass

from openai import OpenAI

import database as db


@dataclass
class AgentResponse:
    answer: str
    prompt_tokens: int
    completion_tokens: int
    elapsed_sec: float
    model: str
    turn: int


class LLMAgent:
    DEFAULT_MODEL = "deepseek-chat"
    DEFAULT_SYSTEM = (
        "Ты полезный ИИ-ассистент. Отвечай чётко, по существу, "
        "на том же языке, на котором задан вопрос. "
        "Помни всё, что было сказано в этом разговоре."
    )

    def __init__(
        self,
        session_id: str,
        api_key: str | None = None,
        model: str = DEFAULT_MODEL,
        system_prompt: str = DEFAULT_SYSTEM,
    ) -> None:
        self._session_id = session_id
        self._model = model
        self._system_prompt = system_prompt
        self._client = OpenAI(
            api_key=api_key or os.environ["DEEPSEEK_API_KEY"],
            base_url="https://api.deepseek.com",
        )

        # Создать запись сессии в БД (если новая) и загрузить историю
        db.ensure_session(session_id)
        self._history: list[dict] = db.load_history(session_id)

    # ------------------------------------------------------------------
    # Публичный интерфейс
    # ------------------------------------------------------------------

    def ask(self, user_message: str) -> AgentResponse:
        """Отправить запрос в LLM, сохранить оба сообщения в БД."""
        # 1. Сохраняем сообщение пользователя
        self._history.append({"role": "user", "content": user_message})
        db.save_message(self._session_id, "user", user_message)

        # 2. Отправляем запрос с полной историей
        messages = [
            {"role": "system", "content": self._system_prompt},
            *self._history,
        ]
        started = time.perf_counter()
        response = self._client.chat.completions.create(
            model=self._model,
            messages=messages,
        )
        elapsed = time.perf_counter() - started

        # 3. Сохраняем ответ ассистента
        reply = response.choices[0].message.content
        self._history.append({"role": "assistant", "content": reply})
        db.save_message(self._session_id, "assistant", reply)

        return AgentResponse(
            answer=reply,
            prompt_tokens=response.usage.prompt_tokens,
            completion_tokens=response.usage.completion_tokens,
            elapsed_sec=round(elapsed, 2),
            model=response.model,
            turn=self.turn_count,
        )

    def clear_history(self) -> None:
        """Сбросить историю в памяти и в БД."""
        self._history.clear()
        db.clear_history(self._session_id)

    @property
    def turn_count(self) -> int:
        return sum(1 for m in self._history if m["role"] == "assistant")

    @property
    def session_id(self) -> str:
        return self._session_id
