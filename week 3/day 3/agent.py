"""
LLMAgent: модель памяти + ФОРМАЛИЗОВАННОЕ СОСТОЯНИЕ ЗАДАЧИ (FSM).

Состояние задачи (см. statemachine.py) — конечный автомат:
    planning → execution → validation → done

Что делает агент:
  • держит состояние (этап / текущий шаг / ожидаемое действие) в БД;
  • инжектит состояние в системный промпт — агент всегда «знает», где он;
  • после каждого хода продвигает автомат: предлагает переход, и переход
    применяется ТОЛЬКО если он допустим (валидация по TRANSITIONS);
  • на паузе продвижение этапа запрещено — состояние замораживается.

Пауза/возобновление: состояние полностью персистентно, поэтому после паузы
(и даже перезапуска процесса) агент продолжает с того же места без повторных
объяснений — этап, шаг и ожидаемое действие восстанавливаются из БД.
"""

import json
import os
import time
from dataclasses import dataclass, field

from openai import OpenAI

import database as db
import statemachine as sm
from models import DEFAULT_MODEL, ModelInfo, get_model

SHORT_TERM_WINDOW = 10


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
    task_state:  dict | None
    last_writes: list = field(default_factory=list)


class LLMAgent:
    DEFAULT_SYSTEM = (
        "Ты ИИ-ассистент, ведущий задачу по этапам конечного автомата: "
        "planning → execution → validation → done. "
        "Всегда учитывай ТЕКУЩЕЕ состояние задачи (этап, шаг, ожидаемое действие) "
        "и память. Не начинай объяснять задачу заново — продолжай с текущего шага."
    )

    def __init__(
        self,
        session_id: str,
        api_key: str | None = None,
        model_id: str = DEFAULT_MODEL,
        system_prompt: str = DEFAULT_SYSTEM,
        auto_advance: bool = True,
    ) -> None:
        self._session_id    = session_id
        self._system_prompt = system_prompt
        self._auto_advance  = auto_advance
        self._client = OpenAI(
            api_key=api_key or os.environ["DEEPSEEK_API_KEY"],
            base_url="https://api.deepseek.com",
        )
        self._model: ModelInfo = get_model(model_id)
        db.ensure_session(session_id)

    # ------------------------------------------------------------------
    # Свойства / управление состоянием
    # ------------------------------------------------------------------

    @property
    def session_id(self) -> str:
        return self._session_id

    @property
    def model_info(self) -> ModelInfo:
        return self._model

    @property
    def auto_advance(self) -> bool:
        return self._auto_advance

    def set_model(self, model_id: str) -> ModelInfo:
        self._model = get_model(model_id)
        return self._model

    def set_auto_advance(self, enabled: bool) -> None:
        self._auto_advance = enabled

    def task_state(self) -> dict | None:
        return db.get_task_state(self._session_id)

    def start_task(self, task_name: str) -> dict:
        db.set_active_task(self._session_id, task_name)
        return db.start_task(
            self._session_id, task_name,
            current_step="Сформулировать план решения",
            expected_action="Агент предлагает план, пользователь подтверждает",
        )

    def pause(self) -> dict | None:
        return db.set_task_status(self._session_id, sm.STATUS_PAUSED)

    def resume(self) -> dict | None:
        return db.set_task_status(self._session_id, sm.STATUS_ACTIVE)

    def reset_task(self) -> None:
        db.reset_task(self._session_id)

    def advance_manual(self, to_stage: str, note: str = "ручной переход") -> dict:
        """Ручной переход с проверкой допустимости."""
        cur = db.get_task_state(self._session_id)
        if not cur:
            raise ValueError("Задача не начата")
        if not sm.can_transition(cur["stage"], to_stage):
            raise ValueError(
                f"Недопустимый переход {cur['stage']} → {to_stage}")
        return db.transition_stage(self._session_id, to_stage, note)

    # ------------------------------------------------------------------
    # Основной цикл
    # ------------------------------------------------------------------

    def ask(self, user_message: str) -> AgentResponse:
        db.save_user_message(self._session_id, user_message)

        messages = self._build_messages()

        started = time.perf_counter()
        response = self._client.chat.completions.create(
            model=self._model.id, messages=messages)
        elapsed = round(time.perf_counter() - started, 2)

        reply             = response.choices[0].message.content
        prompt_tokens     = response.usage.prompt_tokens
        completion_tokens = response.usage.completion_tokens

        db.save_assistant_message(
            self._session_id, reply, prompt_tokens, completion_tokens)

        last_writes: list = []
        if self._auto_advance:
            last_writes = self._advance_state()

        cost = round(
            prompt_tokens     * self._model.price_input_1m  / 1_000_000
            + completion_tokens * self._model.price_output_1m / 1_000_000, 6)
        usage   = TokenUsage(prompt_tokens, completion_tokens,
                             prompt_tokens + completion_tokens, cost)
        session = SessionStats(**db.get_session_token_totals(self._session_id))

        return AgentResponse(
            answer=reply, elapsed_sec=elapsed, model=self._model.id,
            turn=session.turns, usage=usage, session=session,
            task_state=db.get_task_state(self._session_id),
            last_writes=last_writes,
        )

    def clear_short_term(self) -> None:
        db.clear_short_term(self._session_id)

    # ------------------------------------------------------------------
    # Сборка контекста
    # ------------------------------------------------------------------

    def _build_messages(self) -> list[dict]:
        system  = self._make_system()
        history = db.get_messages(self._session_id)
        recent  = history[-SHORT_TERM_WINDOW:]
        return [{"role": "system", "content": system}] + recent

    def _make_system(self) -> str:
        parts = [self._system_prompt]

        # СОСТОЯНИЕ ЗАДАЧИ — идёт первым, агент всегда знает, где он
        state = db.get_task_state(self._session_id)
        if state:
            paused = " (НА ПАУЗЕ — дождись возобновления)" \
                     if state["status"] == sm.STATUS_PAUSED else ""
            parts.append(
                "## Состояние задачи" + paused + "\n"
                f"- Задача: {state['task_name']}\n"
                f"- Этап: {sm.STAGE_LABELS.get(state['stage'], state['stage'])} "
                f"({state['stage']})\n"
                f"- Текущий шаг: {state['current_step'] or '—'}\n"
                f"- Ожидаемое действие: {state['expected_action'] or '—'}\n"
                f"- Маршрут: planning → execution → validation → done"
            )

        # Память
        long_term = db.load_long_term(self._session_id)
        lt_blocks = []
        titles = {"profile": "Профиль-факты", "decision": "Принятые решения",
                  "knowledge": "Знания"}
        for cat, title in titles.items():
            items = long_term.get(cat, [])
            if items:
                lines = "\n".join(f"- {it['content']}" for it in items)
                lt_blocks.append(f"### {title}\n{lines}")
        if lt_blocks:
            parts.append("## Долговременная память\n" + "\n\n".join(lt_blocks))

        working = db.load_working(self._session_id)
        if working:
            lines = "\n".join(f"- **{k}:** {v}" for k, v in working.items())
            parts.append(f"## Рабочая память\n{lines}")

        return "\n\n".join(parts)

    # ------------------------------------------------------------------
    # Продвижение автомата
    # ------------------------------------------------------------------

    _ADVANCE_PROMPT = (
        "Ты — контроллер конечного автомата задачи. Этапы и переходы:\n"
        "  planning → execution → validation → done\n"
        "  validation → execution (если найдены проблемы)\n\n"
        "Текущее состояние:\n"
        "  этап: {stage}\n  шаг: {step}\n  ожидалось: {expected}\n\n"
        "Последний обмен репликами:\n{exchange}\n\n"
        "Реши, как изменилось состояние задачи ПОСЛЕ этого обмена. "
        "Верни ТОЛЬКО валидный JSON без markdown:\n"
        "{{\n"
        '  "next_stage": "<этап из planning|execution|validation|done; '
        'тот же, если переход не нужен>",\n'
        '  "current_step": "<что делается сейчас, кратко>",\n'
        '  "expected_action": "<какое действие ожидается следующим>",\n'
        '  "working": {{"ключ": "значение"}},\n'
        '  "note": "<короткое пояснение перехода или \\"\\">"\n'
        "}}\n"
        "Переходи на следующий этап ТОЛЬКО когда текущий действительно завершён."
    )

    def _advance_state(self) -> list[dict]:
        state = db.get_task_state(self._session_id)
        if not state:
            return []  # задача не начата — нечего продвигать
        if state["status"] == sm.STATUS_PAUSED:
            return []  # ПАУЗА: состояние заморожено

        history = db.get_messages(self._session_id)
        last    = history[-2:]
        if not last:
            return []
        exchange = "\n".join(
            f"{'Пользователь' if m['role'] == 'user' else 'Ассистент'}: {m['content']}"
            for m in last
        )
        prompt = self._ADVANCE_PROMPT.format(
            stage=state["stage"], step=state["current_step"] or "—",
            expected=state["expected_action"] or "—", exchange=exchange,
        )

        writes: list[dict] = []
        try:
            resp = self._client.chat.completions.create(
                model=self._model.id,
                messages=[{"role": "user", "content": prompt}])
            raw = resp.choices[0].message.content.strip()
            if "```" in raw:
                raw = raw.split("```")[1].lstrip("json").strip()
            data = json.loads(raw)

            cur_stage = state["stage"]
            nxt       = (data.get("next_stage") or cur_stage).strip()
            step      = data.get("current_step")
            expected  = data.get("expected_action")
            note      = data.get("note") or ""

            # обновляем шаг/ожидаемое действие
            db.update_task_fields(
                self._session_id,
                current_step=step if step is not None else None,
                expected_action=expected if expected is not None else None,
            )

            # переход этапа — только если валиден и реально меняется
            if sm.is_stage(nxt) and nxt != cur_stage:
                if sm.can_transition(cur_stage, nxt):
                    db.transition_stage(self._session_id, nxt, note)
                    writes.append({"type": "transition",
                                   "from": cur_stage, "to": nxt, "note": note})
                else:
                    writes.append({"type": "rejected",
                                   "from": cur_stage, "to": nxt,
                                   "note": "недопустимый переход — отклонён"})

            # рабочая память
            working = data.get("working") or {}
            if isinstance(working, dict):
                for k, v in working.items():
                    db.upsert_working(self._session_id, str(k), str(v),
                                      task=state["task_name"])
                    writes.append({"type": "working", "key": str(k),
                                   "content": str(v)})
        except Exception:
            pass
        return writes
