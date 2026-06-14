"""
LLMAgent с тремя стратегиями управления контекстом.

Стратегия 1 — Sliding Window
  Передаём только последние WINDOW_SIZE сообщений.
  Старые сообщения просто отбрасываются.

Стратегия 2 — Sticky Facts
  LLM извлекает ключевые факты из диалога и хранит их в БД.
  В запрос уходят: факты (в системном промпте) + последние WINDOW_SIZE сообщений.
  Факты обновляются после каждого хода.

Стратегия 3 — Branching
  Диалог можно «разветвить» от любой точки основной ветки.
  В каждой ветке своя независимая история.
  В запрос уходит полная история текущей ветки (без обрезки).
"""

import json
import os
import time
from dataclasses import dataclass, field

from openai import OpenAI

import database as db
from models import DEFAULT_MODEL, ModelInfo, get_model

# ------------------------------------------------------------------
# Стратегии
# ------------------------------------------------------------------
STRATEGY_SLIDING_WINDOW = "sliding_window"
STRATEGY_STICKY_FACTS   = "sticky_facts"
STRATEGY_BRANCHING      = "branching"

STRATEGIES = [STRATEGY_SLIDING_WINDOW, STRATEGY_STICKY_FACTS, STRATEGY_BRANCHING]

WINDOW_SIZE = 10   # для sliding_window и sticky_facts


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
    strategy:            str
    total_messages:      int    # всего в истории ветки
    messages_in_context: int    # передано в LLM
    dropped_messages:    int = 0
    facts:               dict = field(default_factory=dict)
    branch_id:           int | None = None
    branch_name:         str = "Основная ветка"


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
        # Восстановить стратегию и ветку из БД
        self._strategy  = db.get_strategy(session_id)
        self._branch_id = db.get_current_branch_id(session_id)

    # ------------------------------------------------------------------
    # Публичный интерфейс
    # ------------------------------------------------------------------

    @property
    def session_id(self) -> str:
        return self._session_id

    @property
    def model_info(self) -> ModelInfo:
        return self._model

    @property
    def strategy(self) -> str:
        return self._strategy

    @property
    def branch_id(self) -> int | None:
        return self._branch_id

    def set_model(self, model_id: str) -> ModelInfo:
        self._model = get_model(model_id)
        return self._model

    def set_strategy(self, strategy: str) -> None:
        if strategy not in STRATEGIES:
            raise ValueError(f"Неизвестная стратегия: {strategy!r}")
        self._strategy = strategy
        db.set_strategy(self._session_id, strategy)

    def switch_branch(self, branch_id: int | None) -> dict:
        """Переключиться на ветку (None = основная)."""
        if branch_id is not None:
            branch = db.get_branch(branch_id)
            if not branch or branch["session_id"] != self._session_id:
                raise ValueError(f"Ветка {branch_id} не найдена")
        self._branch_id = branch_id
        db.set_current_branch_id(self._session_id, branch_id)
        if branch_id is None:
            return {"id": None, "name": "Основная ветка"}
        return db.get_branch(branch_id)

    def create_branch(self, name: str) -> dict:
        """
        Создать ветку от текущей позиции в основной ветке.
        Ветки создаются только из основной ветки (branch_id=None).
        """
        if self._branch_id is not None:
            raise ValueError(
                "Ветки можно создавать только из основной ветки. "
                "Переключитесь на основную ветку и попробуйте снова."
            )
        last_id = db.get_last_message_id(self._session_id, branch_id=None)
        branch = db.create_branch(self._session_id, name, last_id)
        self._branch_id = branch["id"]
        db.set_current_branch_id(self._session_id, branch["id"])
        return branch

    def list_branches(self) -> list[dict]:
        return db.list_branches(self._session_id)

    def ask(self, user_message: str) -> AgentResponse:
        # 1. Сохранить сообщение в текущую ветку
        db.save_user_message(self._session_id, user_message,
                             branch_id=self._branch_id)

        # 2. Построить контекст по стратегии
        messages, ctx_stats = self._build_messages()

        # 3. Вызов LLM
        started = time.perf_counter()
        response = self._client.chat.completions.create(
            model=self._model.id,
            messages=messages,
        )
        elapsed = round(time.perf_counter() - started, 2)

        reply             = response.choices[0].message.content
        prompt_tokens     = response.usage.prompt_tokens
        completion_tokens = response.usage.completion_tokens

        # 4. Сохранить ответ
        db.save_assistant_message(
            self._session_id, reply, prompt_tokens, completion_tokens,
            branch_id=self._branch_id,
        )

        # 5. Обновить факты после сохранения ответа
        if self._strategy == STRATEGY_STICKY_FACTS:
            self._extract_facts()
            ctx_stats.facts = db.load_facts(self._session_id)

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
        self._branch_id = None
        db.clear_history(self._session_id)

    # ------------------------------------------------------------------
    # Построение контекста по стратегии
    # ------------------------------------------------------------------

    def _build_messages(self) -> tuple[list[dict], ContextStats]:
        if self._strategy == STRATEGY_SLIDING_WINDOW:
            return self._build_sliding_window()
        elif self._strategy == STRATEGY_STICKY_FACTS:
            return self._build_sticky_facts()
        else:
            return self._build_branching()

    def _build_sliding_window(self) -> tuple[list[dict], ContextStats]:
        """Только последние WINDOW_SIZE сообщений — остальное отбрасывается."""
        history = db.get_history(self._session_id, self._branch_id)
        recent  = history[-WINDOW_SIZE:]
        ctx = ContextStats(
            strategy=STRATEGY_SLIDING_WINDOW,
            total_messages=len(history),
            messages_in_context=len(recent),
            dropped_messages=len(history) - len(recent),
        )
        return [{"role": "system", "content": self._make_system()}] + recent, ctx

    def _build_sticky_facts(self) -> tuple[list[dict], ContextStats]:
        """Факты + последние WINDOW_SIZE сообщений."""
        facts   = db.load_facts(self._session_id)
        history = db.get_history(self._session_id, self._branch_id)
        recent  = history[-WINDOW_SIZE:]
        system  = self._make_system()
        if facts:
            lines  = "\n".join(f"- **{k}:** {v}" for k, v in facts.items())
            system += f"\n\n## Важные факты о пользователе и диалоге\n{lines}"
        ctx = ContextStats(
            strategy=STRATEGY_STICKY_FACTS,
            total_messages=len(history),
            messages_in_context=len(recent),
            dropped_messages=len(history) - len(recent),
            facts=facts,
        )
        return [{"role": "system", "content": system}] + recent, ctx

    def _build_branching(self) -> tuple[list[dict], ContextStats]:
        """Полная история текущей ветки без обрезки."""
        history     = db.get_history(self._session_id, self._branch_id)
        branch_name = "Основная ветка"
        if self._branch_id:
            info = db.get_branch(self._branch_id)
            if info:
                branch_name = info["name"]
        ctx = ContextStats(
            strategy=STRATEGY_BRANCHING,
            total_messages=len(history),
            messages_in_context=len(history),
            branch_id=self._branch_id,
            branch_name=branch_name,
        )
        return [{"role": "system", "content": self._make_system()}] + history, ctx

    def _make_system(self) -> str:
        """Системный промпт + инжекция файлов контекста."""
        system = self._system_prompt
        files  = db.load_context_files(self._session_id)
        if files:
            blocks = [f"### Файл: {f['filename']}\n\n{f['content']}" for f in files]
            system += (
                "\n\nПользователь предоставил следующие файлы в качестве контекста:\n\n"
                + "\n\n---\n\n".join(blocks)
            )
        return system

    # ------------------------------------------------------------------
    # Извлечение фактов (Sticky Facts)
    # ------------------------------------------------------------------

    def _extract_facts(self) -> None:
        """Обновить словарь фактов на основе последних сообщений."""
        history       = db.get_history(self._session_id, self._branch_id)
        recent        = history[-6:]
        current_facts = db.load_facts(self._session_id)
        current_json  = json.dumps(current_facts, ensure_ascii=False, indent=2)
        recent_text   = "\n".join(
            f"{'Пользователь' if m['role'] == 'user' else 'Ассистент'}: {m['content']}"
            for m in recent
        )
        prompt = (
            "Ты — система извлечения фактов из диалога.\n\n"
            f"Текущие сохранённые факты (JSON):\n{current_json}\n\n"
            f"Последние сообщения:\n{recent_text}\n\n"
            "Обнови словарь: добавь новые важные сведения "
            "(цели, ограничения, решения, предпочтения, договорённости), "
            "обнови изменившиеся, удали устаревшие.\n"
            "Ключи — 2–4 слова на русском. Значения — конкретные и краткие.\n"
            "Верни ТОЛЬКО валидный JSON, без markdown, без пояснений."
        )
        try:
            resp = self._client.chat.completions.create(
                model=self._model.id,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = resp.choices[0].message.content.strip()
            if "```" in raw:
                parts = raw.split("```")
                raw = parts[1].lstrip("json").strip()
            new_facts = json.loads(raw)
            if isinstance(new_facts, dict):
                db.save_facts(self._session_id, new_facts)
        except Exception:
            pass   # ошибка извлечения не прерывает основной ответ

    @property
    def turn_count(self) -> int:
        return db.get_session_token_totals(self._session_id)["turns"]
