"""
LLMAgent с явной трёхслойной моделью памяти.

Слои (хранятся в РАЗНЫХ таблицах, см. database.py):

  1. КРАТКОСРОЧНАЯ (short-term) — текущий диалог.
       Последние SHORT_TERM_WINDOW сообщений уходят в запрос напрямую.
       Очищается при «Очистить диалог».

  2. РАБОЧАЯ (working) — данные текущей задачи.
       Key-value, привязаны к активной задаче. Инжектятся в системный промпт.
       Очищаются при смене/завершении задачи.

  3. ДОЛГОВРЕМЕННАЯ (long-term) — профиль / решения / знания.
       Переживает очистку диалога. Инжектится в системный промпт.

Маршрутизация («что и куда сохранять»):
  • Автоматически — после каждого хода _route_memory() делает отдельный
    вызов LLM, который ЯВНО классифицирует новую информацию по слоям
    и возвращает структурированный JSON.
  • Вручную — через API (см. app.py): можно дописать/удалить запись
    в любом слое напрямую.
"""

import json
import os
import time
from dataclasses import dataclass, field

from openai import OpenAI

import database as db
from models import DEFAULT_MODEL, ModelInfo, get_model

SHORT_TERM_WINDOW = 10   # сколько последних сообщений диалога уходит в запрос


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
class MemorySnapshot:
    """Состояние всех трёх слоёв + что записано на этом ходу."""
    short_term_total:      int
    short_term_in_context: int
    working_task:          str | None
    working:               dict          = field(default_factory=dict)
    long_term:             dict          = field(default_factory=dict)
    last_writes:           list          = field(default_factory=list)


@dataclass
class AgentResponse:
    answer:      str
    elapsed_sec: float
    model:       str
    turn:        int
    usage:       TokenUsage
    session:     SessionStats
    memory:      MemorySnapshot


# ------------------------------------------------------------------
# Агент
# ------------------------------------------------------------------

class LLMAgent:
    DEFAULT_SYSTEM = (
        "Ты полезный ИИ-ассистент с явной моделью памяти. "
        "Используй предоставленную память (профиль пользователя, принятые решения, "
        "знания и данные текущей задачи), чтобы отвечать точно и персонализированно. "
        "Не переспрашивай то, что уже есть в памяти."
    )

    def __init__(
        self,
        session_id: str,
        api_key: str | None = None,
        model_id: str = DEFAULT_MODEL,
        system_prompt: str = DEFAULT_SYSTEM,
        auto_route: bool = True,
    ) -> None:
        self._session_id    = session_id
        self._system_prompt = system_prompt
        self._auto_route    = auto_route
        self._client = OpenAI(
            api_key=api_key or os.environ["DEEPSEEK_API_KEY"],
            base_url="https://api.deepseek.com",
        )
        self._model: ModelInfo = get_model(model_id)
        db.ensure_session(session_id)

    # ------------------------------------------------------------------
    # Свойства
    # ------------------------------------------------------------------

    @property
    def session_id(self) -> str:
        return self._session_id

    @property
    def model_info(self) -> ModelInfo:
        return self._model

    @property
    def auto_route(self) -> bool:
        return self._auto_route

    def set_model(self, model_id: str) -> ModelInfo:
        self._model = get_model(model_id)
        return self._model

    def set_auto_route(self, enabled: bool) -> None:
        self._auto_route = enabled

    # ------------------------------------------------------------------
    # Основной цикл
    # ------------------------------------------------------------------

    def ask(self, user_message: str) -> AgentResponse:
        # 1. КРАТКОСРОЧНАЯ память: сохранить реплику пользователя
        db.save_user_message(self._session_id, user_message)

        # 2. Собрать запрос из всех трёх слоёв
        messages, in_context = self._build_messages()

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

        # 4. КРАТКОСРОЧНАЯ память: сохранить ответ
        db.save_assistant_message(
            self._session_id, reply, prompt_tokens, completion_tokens)

        # 5. Маршрутизация: разложить новую информацию по слоям
        last_writes: list = []
        if self._auto_route:
            last_writes = self._route_memory()

        # 6. Снимок памяти
        memory = self._snapshot(in_context, last_writes)

        cost = round(
            prompt_tokens     * self._model.price_input_1m  / 1_000_000
            + completion_tokens * self._model.price_output_1m / 1_000_000,
            6,
        )
        usage   = TokenUsage(prompt_tokens, completion_tokens,
                             prompt_tokens + completion_tokens, cost)
        session = SessionStats(**db.get_session_token_totals(self._session_id))

        return AgentResponse(
            answer=reply,
            elapsed_sec=elapsed,
            model=self._model.id,
            turn=session.turns,
            usage=usage,
            session=session,
            memory=memory,
        )

    def clear_short_term(self) -> None:
        """Очистить только диалог. Рабочая и долговременная память сохраняются."""
        db.clear_short_term(self._session_id)

    # ------------------------------------------------------------------
    # Сборка контекста из трёх слоёв
    # ------------------------------------------------------------------

    def _build_messages(self) -> tuple[list[dict], int]:
        system   = self._make_system()
        history  = db.get_messages(self._session_id)
        recent   = history[-SHORT_TERM_WINDOW:]
        messages = [{"role": "system", "content": system}] + recent
        return messages, len(recent)

    def _make_system(self) -> str:
        """Базовый промпт + ДОЛГОВРЕМЕННАЯ и РАБОЧАЯ память."""
        parts = [self._system_prompt]

        long_term = db.load_long_term(self._session_id)
        lt_blocks = []
        titles = {
            "profile":   "Профиль пользователя",
            "decision":  "Принятые решения",
            "knowledge": "Знания",
        }
        for cat, title in titles.items():
            items = long_term.get(cat, [])
            if items:
                lines = "\n".join(f"- {it['content']}" for it in items)
                lt_blocks.append(f"### {title}\n{lines}")
        if lt_blocks:
            parts.append("## Долговременная память\n" + "\n\n".join(lt_blocks))

        working = db.load_working(self._session_id)
        if working:
            task  = db.get_active_task(self._session_id)
            head  = f"## Рабочая память (текущая задача: {task})" if task \
                    else "## Рабочая память"
            lines = "\n".join(f"- **{k}:** {v}" for k, v in working.items())
            parts.append(f"{head}\n{lines}")

        return "\n\n".join(parts)

    def _snapshot(self, in_context: int, last_writes: list) -> MemorySnapshot:
        history = db.get_messages(self._session_id)
        return MemorySnapshot(
            short_term_total=len(history),
            short_term_in_context=in_context,
            working_task=db.get_active_task(self._session_id),
            working=db.load_working(self._session_id),
            long_term=db.load_long_term(self._session_id),
            last_writes=last_writes,
        )

    # ------------------------------------------------------------------
    # Маршрутизация памяти (явное «что и куда»)
    # ------------------------------------------------------------------

    _ROUTER_PROMPT = (
        "Ты — маршрутизатор памяти ассистента. Проанализируй последний обмен "
        "репликами и реши, что СТОИТ запомнить и в КАКОЙ слой памяти.\n\n"
        "Слои:\n"
        "• working — данные ТЕКУЩЕЙ задачи: параметры, переменные, промежуточные "
        "результаты, статус. Формат key-value. Эфемерны (живут пока идёт задача).\n"
        "• long_term — то, что полезно надолго:\n"
        "    - profile: устойчивые сведения о пользователе (имя, роль, стек, "
        "предпочтения, часовой пояс)\n"
        "    - decision: принятые проектные/архитектурные решения с обоснованием\n"
        "    - knowledge: общие факты или знания, которые стоит сохранить\n\n"
        "Текущая активная задача: {task}\n"
        "Текущая рабочая память: {working}\n\n"
        "Обмен репликами:\n{exchange}\n\n"
        "Верни ТОЛЬКО валидный JSON без markdown:\n"
        "{{\n"
        '  "task": "<краткое имя текущей задачи, либо null если не изменилась/нет>",\n'
        '  "working": {{"ключ": "значение"}},\n'
        '  "long_term": [{{"category": "profile|decision|knowledge", "content": "..."}}]\n'
        "}}\n"
        "Сохраняй ТОЛЬКО действительно важное. Если сохранять нечего — "
        'верни пустые "working" и "long_term".'
    )

    def _route_memory(self) -> list[dict]:
        """
        Отдельный вызов LLM, который явно классифицирует новую информацию
        по слоям и пишет её в соответствующие таблицы.
        Возвращает список выполненных записей (для отображения в UI).
        """
        history = db.get_messages(self._session_id)
        last    = history[-2:]   # последняя пара user/assistant
        if not last:
            return []
        exchange = "\n".join(
            f"{'Пользователь' if m['role'] == 'user' else 'Ассистент'}: {m['content']}"
            for m in last
        )
        prompt = self._ROUTER_PROMPT.format(
            task=db.get_active_task(self._session_id) or "—",
            working=json.dumps(db.load_working(self._session_id), ensure_ascii=False),
            exchange=exchange,
        )

        writes: list[dict] = []
        try:
            resp = self._client.chat.completions.create(
                model=self._model.id,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = resp.choices[0].message.content.strip()
            if "```" in raw:
                raw = raw.split("```")[1].lstrip("json").strip()
            data = json.loads(raw)

            # task
            task = data.get("task")
            if isinstance(task, str) and task.strip() and task.strip() != "—":
                db.set_active_task(self._session_id, task.strip())

            # working
            working = data.get("working") or {}
            if isinstance(working, dict):
                cur_task = db.get_active_task(self._session_id)
                for k, v in working.items():
                    db.upsert_working(self._session_id, str(k), str(v), task=cur_task)
                    writes.append({"layer": "working", "category": "",
                                   "key": str(k), "content": str(v)})

            # long_term
            lt = data.get("long_term") or []
            if isinstance(lt, list):
                for entry in lt:
                    if not isinstance(entry, dict):
                        continue
                    cat = entry.get("category", "")
                    content = (entry.get("content") or "").strip()
                    if cat in db.LONG_TERM_CATEGORIES and content:
                        is_new = db.add_long_term(self._session_id, cat, content)
                        if is_new:
                            writes.append({"layer": "long_term", "category": cat,
                                           "key": "", "content": content})
        except Exception:
            pass   # сбой маршрутизатора не должен ломать основной ответ
        return writes
