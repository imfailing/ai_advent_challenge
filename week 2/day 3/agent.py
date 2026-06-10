"""
LLMAgent с персистентной памятью и детальным учётом токенов и стоимости.

Считает токены и стоимость:
  - для текущего запроса (prompt + completion отдельно)
  - для ответа модели (completion_tokens)
  - накопленным итогом по всей истории сессии
"""

import os
import time
from dataclasses import dataclass

from openai import OpenAI

import database as db


@dataclass
class TokenUsage:
    """Статистика токенов и стоимости одного запроса."""
    prompt_tokens:     int      # входные токены (запрос + вся история)
    completion_tokens: int      # выходные токены (только ответ модели)
    total_tokens:      int      # сумма
    cost_usd:          float    # стоимость этого запроса в USD


@dataclass
class SessionStats:
    """Накопленная статистика по всей истории сессии."""
    turns:            int
    total_prompt:     int
    total_completion: int
    total_tokens:     int
    total_cost_usd:   float


@dataclass
class AgentResponse:
    answer:      str
    elapsed_sec: float
    model:       str
    turn:        int
    usage:       TokenUsage    # метрики текущего запроса
    session:     SessionStats  # накопленные метрики сессии


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
        db.ensure_session(session_id)
        self._history: list[dict] = db.load_history(session_id)

    # ------------------------------------------------------------------

    def ask(self, user_message: str) -> AgentResponse:
        # 1. Сохраняем сообщение пользователя
        self._history.append({"role": "user", "content": user_message})
        db.save_user_message(self._session_id, user_message)

        # 2. Формируем запрос с полной историей
        messages = [
            {"role": "system", "content": self._system_prompt},
            *self._history,
        ]

        started = time.perf_counter()
        response = self._client.chat.completions.create(
            model=self._model,
            messages=messages,
        )
        elapsed = round(time.perf_counter() - started, 2)

        # 3. Разбираем ответ и токены
        reply             = response.choices[0].message.content
        prompt_tokens     = response.usage.prompt_tokens
        completion_tokens = response.usage.completion_tokens

        # 4. Сохраняем ответ вместе с токенами
        self._history.append({"role": "assistant", "content": reply})
        db.save_assistant_message(
            self._session_id, reply, prompt_tokens, completion_tokens
        )

        # 5. Собираем метрики
        usage = TokenUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            cost_usd=db.cost_usd(prompt_tokens, completion_tokens),
        )
        totals  = db.get_session_token_totals(self._session_id)
        session = SessionStats(**totals)

        return AgentResponse(
            answer=reply,
            elapsed_sec=elapsed,
            model=response.model,
            turn=session.turns,
            usage=usage,
            session=session,
        )

    def clear_history(self) -> None:
        self._history.clear()
        db.clear_history(self._session_id)

    @property
    def session_id(self) -> str:
        return self._session_id

    @property
    def turn_count(self) -> int:
        return sum(1 for m in self._history if m["role"] == "assistant")
