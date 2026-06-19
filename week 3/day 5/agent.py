"""
LLMAgent: контролируемый жизненный цикл задачи с ЯВНЫМИ переходами и гейтами.

Развитие FSM из day 3. Ключевое отличие — переходы защищены условиями:
нельзя «перепрыгнуть» этап и нельзя перейти дальше, пока не выполнены гейты.

  planning → execution    нужен plan_approved        (нет реализации без плана)
  execution → validation  нужен implementation_done
  validation → done       нужен validation_passed    (нет финала без валидации)
  validation → execution  возврат на доработку

Гарантии:
  • в промпт инжектится текущее состояние + условия + что разрешено;
  • контроллер после каждого хода может выставлять гейты и предлагать переход,
    но переход применяется ТОЛЬКО если sm.check_transition() его разрешает;
  • попытка перепрыгнуть этап отклоняется и логируется, агент объясняет отказ;
  • состояние и гейты персистентны → после паузы продолжение корректно.
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
    events:      list = field(default_factory=list)   # переходы/отказы/гейты


class LLMAgent:
    DEFAULT_SYSTEM = (
        "Ты ИИ-ассистент с контролируемым жизненным циклом задачи: "
        "planning → execution → validation → done. "
        "Переходы между этапами защищены условиями — нельзя перепрыгивать этапы "
        "и нельзя двигаться дальше, пока условие не выполнено."
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
    # Свойства / управление
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
            current_step="Сформулировать и согласовать план",
            expected_action="Агент предлагает план; пользователь утверждает (гейт plan_approved)",
        )

    def set_condition(self, gate: str, value: bool) -> dict | None:
        if gate not in sm.GATES:
            raise ValueError(f"Неизвестный гейт: {gate}")
        return db.set_condition(self._session_id, gate, value)

    def pause(self) -> dict | None:
        return db.set_task_status(self._session_id, sm.STATUS_PAUSED)

    def resume(self) -> dict | None:
        return db.set_task_status(self._session_id, sm.STATUS_ACTIVE)

    def reset_task(self) -> None:
        db.reset_task(self._session_id)

    def transition(self, to_stage: str, note: str = "ручной переход") -> dict:
        """
        Явный переход с проверкой гейтов. При недопустимом переходе
        бросает ValueError с причиной и логирует отклонённую попытку.
        """
        cur = db.get_task_state(self._session_id)
        if not cur:
            raise ValueError("Задача не начата")
        ok, reason = sm.check_transition(cur["stage"], to_stage, cur["conditions"])
        if not ok:
            db.log_rejected_transition(self._session_id, cur["stage"], to_stage, reason)
            raise ValueError(reason)
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

        events: list = []
        if self._auto_advance:
            events = self._advance_state()

        cost = round(
            prompt_tokens     * self._model.price_input_1m  / 1_000_000
            + completion_tokens * self._model.price_output_1m / 1_000_000, 6)
        usage   = TokenUsage(prompt_tokens, completion_tokens,
                             prompt_tokens + completion_tokens, cost)
        session = SessionStats(**db.get_session_token_totals(self._session_id))

        return AgentResponse(
            answer=reply, elapsed_sec=elapsed, model=self._model.id,
            turn=session.turns, usage=usage, session=session,
            task_state=db.get_task_state(self._session_id), events=events,
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
        state = db.get_task_state(self._session_id)
        if state:
            conds = state["conditions"]
            gate_lines = "\n".join(
                f"  - {sm.GATES[g]}: {'✅ выполнено' if conds.get(g) else '❌ не выполнено'}"
                for g in sm.GATES
            )
            targets = sm.allowed_targets(state["stage"])
            allowed_lines = []
            for t in targets:
                miss = sm.missing_gates(state["stage"], t, conds)
                if miss:
                    need = ", ".join(sm.GATES[g] for g in miss)
                    allowed_lines.append(
                        f"  - {sm.STAGE_LABELS[t]} — ЗАБЛОКИРОВАН (нужно: {need})")
                else:
                    allowed_lines.append(f"  - {sm.STAGE_LABELS[t]} — доступен")
            allowed_block = "\n".join(allowed_lines) or "  - (нет — терминальный этап)"
            paused = " (НА ПАУЗЕ — дождись возобновления)" \
                     if state["status"] == sm.STATUS_PAUSED else ""

            parts.append(
                "## Жизненный цикл задачи" + paused + "\n"
                f"- Задача: {state['task_name']}\n"
                f"- Текущий этап: {sm.STAGE_LABELS.get(state['stage'], state['stage'])} "
                f"({state['stage']})\n"
                f"- Текущий шаг: {state['current_step'] or '—'}\n"
                f"- Ожидаемое действие: {state['expected_action'] or '—'}\n"
                f"- Условия (гейты):\n{gate_lines}\n"
                f"- Возможные переходы:\n{allowed_block}\n\n"
                "ПРАВИЛА: нельзя перепрыгивать этапы и нельзя переходить дальше, "
                "пока не выполнено условие. Если пользователь просит сделать работу "
                "следующего этапа (например реализацию до утверждения плана или "
                "финал без валидации) — ОТКАЖИСЬ, объясни, какого условия не хватает, "
                "и скажи, что нужно сделать, чтобы разблокировать переход."
            )

        long_term = db.load_long_term(self._session_id)
        lt_blocks = []
        for cat, t in {"profile": "Профиль-факты", "decision": "Решения",
                       "knowledge": "Знания"}.items():
            items = long_term.get(cat, [])
            if items:
                lt_blocks.append(f"### {t}\n" + "\n".join(f"- {it['content']}" for it in items))
        if lt_blocks:
            parts.append("## Долговременная память\n" + "\n\n".join(lt_blocks))

        working = db.load_working(self._session_id)
        if working:
            parts.append("## Рабочая память\n" +
                         "\n".join(f"- **{k}:** {v}" for k, v in working.items()))

        return "\n\n".join(parts)

    # ------------------------------------------------------------------
    # Продвижение автомата (с проверкой гейтов)
    # ------------------------------------------------------------------

    _ADVANCE_PROMPT = (
        "Ты — контроллер жизненного цикла задачи. Этапы:\n"
        "  planning → execution → validation → done (+ validation → execution)\n"
        "Гейты (условия переходов):\n"
        "  plan_approved — пользователь явно утвердил план\n"
        "  implementation_done — реализация завершена\n"
        "  validation_passed — проверка/тесты пройдены\n\n"
        "Текущее состояние:\n  этап: {stage}\n  гейты: {conds}\n"
        "  шаг: {step}\n\n"
        "Последний обмен репликами:\n{exchange}\n\n"
        "Определи изменения. Верни ТОЛЬКО валидный JSON без markdown:\n"
        "{{\n"
        '  "set_gates": {{"plan_approved": true}},   // какие гейты выставить в true (по факту из диалога)\n'
        '  "next_stage": "<этап или тот же>",\n'
        '  "current_step": "<кратко>",\n'
        '  "expected_action": "<кратко>",\n'
        '  "note": "<пояснение или \\"\\">"\n'
        "}}\n"
        "Выставляй гейт в true ТОЛЬКО если в диалоге есть фактическое подтверждение "
        "(пользователь утвердил план / реализация показана / валидация пройдена). "
        "Не выставляй гейты «авансом»."
    )

    def _advance_state(self) -> list[dict]:
        state = db.get_task_state(self._session_id)
        if not state or state["status"] == sm.STATUS_PAUSED:
            return []

        history = db.get_messages(self._session_id)
        last    = history[-2:]
        if not last:
            return []
        exchange = "\n".join(
            f"{'Пользователь' if m['role'] == 'user' else 'Ассистент'}: {m['content']}"
            for m in last
        )
        prompt = self._ADVANCE_PROMPT.format(
            stage=state["stage"], conds=json.dumps(state["conditions"], ensure_ascii=False),
            step=state["current_step"] or "—", exchange=exchange,
        )

        events: list[dict] = []
        try:
            resp = self._client.chat.completions.create(
                model=self._model.id,
                messages=[{"role": "user", "content": prompt}])
            raw = resp.choices[0].message.content.strip()
            if "```" in raw:
                raw = raw.split("```")[1].lstrip("json").strip()
            data = json.loads(raw)

            # 1) выставить гейты
            gates = data.get("set_gates") or {}
            if isinstance(gates, dict):
                for g, v in gates.items():
                    if g in sm.GATES and bool(v) and not state["conditions"].get(g):
                        db.set_condition(self._session_id, g, True)
                        events.append({"type": "gate", "gate": g,
                                       "label": sm.GATES[g]})

            # перечитать состояние с обновлёнными гейтами
            state = db.get_task_state(self._session_id)

            # 2) обновить шаг/ожидание
            db.update_task_fields(
                self._session_id,
                current_step=data.get("current_step"),
                expected_action=data.get("expected_action"),
            )

            # 3) переход — только если допустим по гейтам
            cur_stage = state["stage"]
            nxt = (data.get("next_stage") or cur_stage).strip()
            note = data.get("note") or ""
            if sm.is_stage(nxt) and nxt != cur_stage:
                ok, reason = sm.check_transition(cur_stage, nxt, state["conditions"])
                if ok:
                    db.transition_stage(self._session_id, nxt, note)
                    events.append({"type": "transition", "from": cur_stage,
                                   "to": nxt, "note": note})
                else:
                    db.log_rejected_transition(self._session_id, cur_stage, nxt, reason)
                    events.append({"type": "rejected", "from": cur_stage,
                                   "to": nxt, "reason": reason})
        except Exception:
            pass
        return events
