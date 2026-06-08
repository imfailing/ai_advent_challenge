"""
Agent — самостоятельная сущность, инкапсулирующая всю логику работы с LLM.

Принимает запрос пользователя, отправляет его через DeepSeek API и
возвращает структурированный результат (ответ + метаданные).

Поддерживает память в рамках сессии: вся история диалога хранится внутри
объекта и автоматически передаётся в каждый последующий запрос.
Flask-приложение ничего не знает о деталях API — оно работает только
с интерфейсом агента.
"""

import os
import time
from dataclasses import dataclass, field

from openai import OpenAI


@dataclass
class AgentResponse:
    """Структурированный ответ агента."""
    answer: str
    prompt_tokens: int
    completion_tokens: int
    elapsed_sec: float
    model: str
    turn: int                  # номер хода в текущей сессии


class LLMAgent:
    """
    Агент, который принимает запрос пользователя и возвращает ответ LLM.

    Вся логика работы с API (инициализация клиента, формирование запроса,
    обработка ответа, хранение истории диалога) инкапсулирована здесь —
    снаружи видны только методы ask() и clear_history().

    История диалога хранится в self._history и передаётся в каждый новый
    запрос, так что модель «помнит» контекст всей текущей сессии.
    """

    DEFAULT_MODEL = "deepseek-chat"
    DEFAULT_SYSTEM = (
        "Ты полезный ИИ-ассистент. Отвечай чётко, по существу, "
        "на том же языке, на котором задан вопрос. "
        "Помни всё, что было сказано в этом разговоре."
    )

    def __init__(
        self,
        api_key: str | None = None,
        model: str = DEFAULT_MODEL,
        system_prompt: str = DEFAULT_SYSTEM,
    ) -> None:
        self._model = model
        self._system_prompt = system_prompt
        self._client = OpenAI(
            api_key=api_key or os.environ["DEEPSEEK_API_KEY"],
            base_url="https://api.deepseek.com",
        )
        # Список сообщений диалога (без системного — он добавляется при вызове)
        self._history: list[dict] = []

    # ------------------------------------------------------------------
    # Публичный интерфейс
    # ------------------------------------------------------------------

    def ask(self, user_message: str) -> AgentResponse:
        """
        Отправить запрос в LLM с учётом всей накопленной истории диалога.

        Параметры
        ---------
        user_message : str
            Текст запроса от пользователя.

        Возвращает
        ----------
        AgentResponse
            Ответ модели и сопутствующие метаданные (включая номер хода).
        """
        # Добавляем новый запрос пользователя в историю
        self._history.append({"role": "user", "content": user_message})

        # Системное сообщение + вся история диалога
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

        assistant_reply = response.choices[0].message.content

        # Сохраняем ответ ассистента, чтобы передать его в следующий запрос
        self._history.append({"role": "assistant", "content": assistant_reply})

        return AgentResponse(
            answer=assistant_reply,
            prompt_tokens=response.usage.prompt_tokens,
            completion_tokens=response.usage.completion_tokens,
            elapsed_sec=round(elapsed, 2),
            model=response.model,
            turn=self.turn_count,
        )

    def clear_history(self) -> None:
        """Сбросить историю диалога (начать новую сессию)."""
        self._history.clear()

    @property
    def turn_count(self) -> int:
        """Количество завершённых ходов (пар user + assistant) в истории."""
        return sum(1 for m in self._history if m["role"] == "assistant")
