"""
LLMAgent с персистентной памятью, учётом токенов/стоимости и
возможностью переключения модели на лету.
"""

import os
import time
from dataclasses import dataclass

from openai import OpenAI

import database as db
from models import DEFAULT_MODEL, ModelInfo, get_model


@dataclass
class TokenUsage:
    prompt_tokens:     int
    completion_tokens: int
    total_tokens:      int
    cost_usd:          float


@dataclass
class SessionStats:
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
    usage:       TokenUsage
    session:     SessionStats


class LLMAgent:
    DEFAULT_SYSTEM = (
        "Ты полезный ИИ-ассистент. Отвечай чётко, по существу, "
        "на том же языке, на котором задан вопрос. "
        "Помни всё, что было сказано в этом разговоре."
    )

    def __init__(
        self,
        session_id: str,
        api_key: str | None = None,
        model_id: str = DEFAULT_MODEL,
        system_prompt: str = DEFAULT_SYSTEM,
    ) -> None:
        self._session_id = session_id
        self._system_prompt = system_prompt
        self._client = OpenAI(
            api_key=api_key or os.environ["DEEPSEEK_API_KEY"],
            base_url="https://api.deepseek.com",
        )
        self._model: ModelInfo = get_model(model_id)
        db.ensure_session(session_id)
        self._history: list[dict] = db.load_history(session_id)

    # ------------------------------------------------------------------

    def set_model(self, model_id: str) -> ModelInfo:
        """Переключить модель. Возвращает новый ModelInfo."""
        self._model = get_model(model_id)
        return self._model

    @property
    def model_info(self) -> ModelInfo:
        return self._model

    def ask(self, user_message: str) -> AgentResponse:
        self._history.append({"role": "user", "content": user_message})
        db.save_user_message(self._session_id, user_message)

        context_files = db.load_context_files(self._session_id)
        extra_context = ""
        if context_files:
            blocks = [
                f"### Файл: {f['filename']}\n\n{f['content']}"
                for f in context_files
            ]
            extra_context = (
                "\n\nПользователь предоставил следующие файлы в качестве контекста:\n\n"
                + "\n\n---\n\n".join(blocks)
            )

        messages = [
            {"role": "system", "content": self._system_prompt + extra_context},
            *self._history,
        ]

        started = time.perf_counter()
        response = self._client.chat.completions.create(
            model=self._model.id,
            messages=messages,
        )
        elapsed = round(time.perf_counter() - started, 2)

        reply             = response.choices[0].message.content
        prompt_tokens     = response.usage.prompt_tokens
        completion_tokens = response.usage.completion_tokens

        self._history.append({"role": "assistant", "content": reply})
        db.save_assistant_message(
            self._session_id, reply, prompt_tokens, completion_tokens
        )

        # Стоимость считаем по тарифам активной модели
        cost = round(
            prompt_tokens     * self._model.price_input_1m  / 1_000_000
            + completion_tokens * self._model.price_output_1m / 1_000_000,
            6,
        )
        usage = TokenUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            cost_usd=cost,
        )
        totals  = db.get_session_token_totals(self._session_id)
        session = SessionStats(**totals)

        return AgentResponse(
            answer=reply,
            elapsed_sec=elapsed,
            model=self._model.id,
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
