"""
Agent — самостоятельная сущность, инкапсулирующая всю логику работы с LLM.

Принимает запрос пользователя, отправляет его через DeepSeek API и
возвращает структурированный результат (ответ + метаданные).
Flask-приложение ничего не знает о деталях API — оно работает только
с интерфейсом агента.
"""

import os
import time
from dataclasses import dataclass

from openai import OpenAI


@dataclass
class AgentResponse:
    """Структурированный ответ агента."""
    answer: str
    prompt_tokens: int
    completion_tokens: int
    elapsed_sec: float
    model: str


class LLMAgent:
    """
    Агент, который принимает запрос пользователя и возвращает ответ LLM.

    Вся логика работы с API (инициализация клиента, формирование запроса,
    обработка ответа) инкапсулирована здесь — снаружи виден только
    метод ask().
    """

    DEFAULT_MODEL = "deepseek-chat"
    DEFAULT_SYSTEM = (
        "Ты полезный ИИ-ассистент. Отвечай чётко, по существу, "
        "на том же языке, на котором задан вопрос."
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

    def ask(self, user_message: str) -> AgentResponse:
        """
        Отправить запрос в LLM и вернуть AgentResponse.

        Параметры
        ---------
        user_message : str
            Текст запроса от пользователя.

        Возвращает
        ----------
        AgentResponse
            Ответ модели и сопутствующие метаданные.
        """
        started = time.perf_counter()
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": self._system_prompt},
                {"role": "user", "content": user_message},
            ],
        )
        elapsed = time.perf_counter() - started

        return AgentResponse(
            answer=response.choices[0].message.content,
            prompt_tokens=response.usage.prompt_tokens,
            completion_tokens=response.usage.completion_tokens,
            elapsed_sec=round(elapsed, 2),
            model=response.model,
        )
