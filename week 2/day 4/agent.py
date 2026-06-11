"""
LLMAgent с компрессией истории.

Стратегия управления контекстом:
  1. Храним последние RECENT_KEEP сообщений «как есть».
  2. Всё более старое сжимается в суммари пачками по SUMMARY_BATCH.
  3. В каждый запрос к LLM уходят:
       system_prompt [+ файлы контекста]
       + блок суммари (сжатая история)
       + последние RECENT_KEEP сообщений (сырые)
  4. Сжатие запускается автоматически перед каждым запросом.

Это позволяет вести бесконечно длинный диалог без роста стоимости запросов.
"""

import os
import time
from dataclasses import dataclass

from openai import OpenAI

import database as db
from models import DEFAULT_MODEL, ModelInfo, get_model

# ------------------------------------------------------------------
# Параметры компрессии
# ------------------------------------------------------------------
RECENT_KEEP   = 10   # сколько последних сообщений передавать без сжатия
SUMMARY_BATCH = 10   # сколько сообщений объединять в одно суммари


# ------------------------------------------------------------------
# Dataclass-ы ответа
# ------------------------------------------------------------------

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
class ContextStats:
    """Статистика того, что попало в контекст запроса."""
    total_messages:      int   # всего сообщений в истории
    summaries_count:     int   # количество блоков суммари
    summarized_messages: int   # сколько сообщений заменено суммари
    raw_in_context:      int   # сырых сообщений в текущем запросе


@dataclass
class AgentResponse:
    answer:      str
    elapsed_sec: float
    model:       str
    turn:        int
    usage:       TokenUsage
    session:     SessionStats
    context:     ContextStats


# ------------------------------------------------------------------
# Агент
# ------------------------------------------------------------------

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
        self._session_id    = session_id
        self._system_prompt = system_prompt
        self._client = OpenAI(
            api_key=api_key or os.environ["DEEPSEEK_API_KEY"],
            base_url="https://api.deepseek.com",
        )
        self._model: ModelInfo = get_model(model_id)
        db.ensure_session(session_id)

    # ------------------------------------------------------------------
    # Публичный интерфейс
    # ------------------------------------------------------------------

    @property
    def session_id(self) -> str:
        return self._session_id

    @property
    def model_info(self) -> ModelInfo:
        return self._model

    def set_model(self, model_id: str) -> ModelInfo:
        self._model = get_model(model_id)
        return self._model

    def ask(self, user_message: str) -> AgentResponse:
        # 1. Сохранить сообщение пользователя
        db.save_user_message(self._session_id, user_message)

        # 2. Сжать историю, если накопилось достаточно
        self._maybe_summarize()

        # 3. Построить список сообщений для API
        messages, ctx_stats = self._build_messages()

        # 4. Вызов API
        started = time.perf_counter()
        response = self._client.chat.completions.create(
            model=self._model.id,
            messages=messages,
        )
        elapsed = round(time.perf_counter() - started, 2)

        reply             = response.choices[0].message.content
        prompt_tokens     = response.usage.prompt_tokens
        completion_tokens = response.usage.completion_tokens

        # 5. Сохранить ответ ассистента
        db.save_assistant_message(
            self._session_id, reply, prompt_tokens, completion_tokens
        )

        cost = round(
            prompt_tokens     * self._model.price_input_1m  / 1_000_000
            + completion_tokens * self._model.price_output_1m / 1_000_000,
            6,
        )
        usage   = TokenUsage(prompt_tokens, completion_tokens,
                             prompt_tokens + completion_tokens, cost)
        totals  = db.get_session_token_totals(self._session_id)
        session = SessionStats(**totals)

        return AgentResponse(
            answer=reply,
            elapsed_sec=elapsed,
            model=self._model.id,
            turn=session.turns,
            usage=usage,
            session=session,
            context=ctx_stats,
        )

    def clear_history(self) -> None:
        """Удалить историю и все суммари сессии."""
        db.clear_history(self._session_id)

    @property
    def turn_count(self) -> int:
        return db.get_session_token_totals(self._session_id)["turns"]

    # ------------------------------------------------------------------
    # Компрессия истории
    # ------------------------------------------------------------------

    def _maybe_summarize(self) -> None:
        """
        Сжать старые сообщения в суммари, если их накопилось слишком много.

        Условие сжатия: несжатых сообщений > RECENT_KEEP + SUMMARY_BATCH.
        Тогда берём самую старую пачку SUMMARY_BATCH и заменяем её суммари.
        Повторяем, пока условие выполняется.
        """
        last_id      = db.get_last_summarized_message_id(self._session_id)
        unsummarized = db.get_messages_after(self._session_id, after_id=last_id)

        while len(unsummarized) > RECENT_KEEP + SUMMARY_BATCH:
            batch        = unsummarized[:SUMMARY_BATCH]
            summary_text = self._create_summary(batch)
            db.save_summary(
                self._session_id,
                content=summary_text,
                from_id=batch[0]["id"],
                to_id=batch[-1]["id"],
                message_count=len(batch),
            )
            unsummarized = unsummarized[SUMMARY_BATCH:]

    def _create_summary(self, messages: list[dict]) -> str:
        """Попросить LLM сжать пачку сообщений в краткое резюме."""
        dialogue = "\n".join(
            f"{'Пользователь' if m['role'] == 'user' else 'Ассистент'}: {m['content']}"
            for m in messages
        )
        prompt = (
            "Сожми следующий фрагмент диалога в краткое резюме на русском языке.\n"
            "Сохрани все важные факты, решения, имена и договорённости.\n"
            "Объём: 3–7 предложений. Отвечай только текстом резюме, без заголовков.\n\n"
            f"{dialogue}"
        )
        response = self._client.chat.completions.create(
            model=self._model.id,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content.strip()

    # ------------------------------------------------------------------
    # Построение контекста запроса
    # ------------------------------------------------------------------

    def _build_messages(self) -> tuple[list[dict], ContextStats]:
        """
        Вернуть список сообщений для API и статистику контекста.

        Структура:
          [system: base_prompt + файлы + блок суммари]
          [последние RECENT_KEEP сырых сообщений]
        """
        summaries = db.load_summaries(self._session_id)
        recent    = db.get_recent_messages(self._session_id, limit=RECENT_KEEP)
        total     = db.get_total_message_count(self._session_id)
        summarized_count = sum(s["message_count"] for s in summaries)

        # Системный промпт + файлы контекста
        context_files = db.load_context_files(self._session_id)
        system = self._system_prompt
        if context_files:
            blocks = [
                f"### Файл: {f['filename']}\n\n{f['content']}"
                for f in context_files
            ]
            system += (
                "\n\nПользователь предоставил следующие файлы в качестве контекста:\n\n"
                + "\n\n---\n\n".join(blocks)
            )

        # Блок суммари в системный промпт
        if summaries:
            summaries_text = "\n\n---\n\n".join(s["content"] for s in summaries)
            system += (
                "\n\n## Краткое содержание предыдущего диалога\n\n"
                + summaries_text
            )

        messages = [{"role": "system", "content": system}] + [
            {"role": m["role"], "content": m["content"]} for m in recent
        ]

        ctx_stats = ContextStats(
            total_messages=total,
            summaries_count=len(summaries),
            summarized_messages=summarized_count,
            raw_in_context=len(recent),
        )
        return messages, ctx_stats
