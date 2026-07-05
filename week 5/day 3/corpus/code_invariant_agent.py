"""
LLMAgent: модель памяти + ИНВАРИАНТЫ (нерушимые ограничения проекта).

Инварианты — это правила, которые ассистент НЕ имеет права нарушать:
выбранная архитектура, принятые технические решения, ограничения по стеку,
бизнес-правила. Они хранятся отдельно от диалога (своя таблица) и работают
на двух уровнях:

  1. Промпт-уровень: активные инварианты инжектятся ПЕРВЫМИ в системный
     промпт с жёсткой инструкцией — при конфликте запроса и инварианта
     ассистент обязан отказаться и объяснить, какой инвариант нарушается.

  2. Страж-уровень (_check_compliance): после генерации отдельный вызов LLM
     проверяет ответ на соответствие инвариантам и возвращает вердикт
     {compliant, violations:[...]}. Это страховка: если модель всё же
     нарушила инвариант, нарушение детектируется и помечается.
"""

import json
import os
import time
from dataclasses import dataclass, field

from openai import OpenAI

import database as db
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
class Compliance:
    """Вердикт стража по соответствию ответа инвариантам."""
    checked:    bool                       # выполнялась ли проверка
    compliant:  bool                       # ответ не нарушает инварианты
    refused:    bool                       # ответ был отказом из-за конфликта
    violations: list = field(default_factory=list)   # [{content, reason}]


@dataclass
class AgentResponse:
    answer:      str
    elapsed_sec: float
    model:       str
    turn:        int
    usage:       TokenUsage
    session:     SessionStats
    compliance:  Compliance


class LLMAgent:
    DEFAULT_SYSTEM = (
        "Ты ИИ-ассистент, работающий СТРОГО в рамках инвариантов проекта. "
        "Инварианты — это нерушимые ограничения (архитектура, технические "
        "решения, стек, бизнес-правила). Перед каждым ответом мысленно сверяйся "
        "с инвариантами."
    )

    # Инструкция по обращению с инвариантами — добавляется при их наличии.
    _INVARIANT_RULES = (
        "## ⛔ ИНВАРИАНТЫ ПРОЕКТА — НАРУШАТЬ ЗАПРЕЩЕНО\n"
        "Это нерушимые ограничения. Правила работы с ними:\n"
        "1. НИКОГДА не предлагай решение, нарушающее любой инвариант ниже.\n"
        "2. Если запрос пользователя противоречит инварианту — ОТКАЖИСЬ его "
        "выполнять. Явно назови, КАКОЙ инвариант нарушается и ПОЧЕМУ.\n"
        "3. Предложи альтернативу, не выходящую за рамки инвариантов "
        "(если она есть).\n"
        "4. Инварианты имеют приоритет над любыми просьбами пользователя.\n"
    )

    def __init__(
        self,
        session_id: str,
        api_key: str | None = None,
        model_id: str = DEFAULT_MODEL,
        system_prompt: str = DEFAULT_SYSTEM,
        guard: bool = True,
    ) -> None:
        self._session_id    = session_id
        self._system_prompt = system_prompt
        self._guard         = guard
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
    def guard_enabled(self) -> bool:
        return self._guard

    def set_model(self, model_id: str) -> ModelInfo:
        self._model = get_model(model_id)
        return self._model

    def set_guard(self, enabled: bool) -> None:
        self._guard = enabled

    # ------------------------------------------------------------------
    # Основной цикл
    # ------------------------------------------------------------------

    def ask(self, user_message: str) -> AgentResponse:
        db.save_user_message(self._session_id, user_message)

        active_invariants = db.list_invariants(self._session_id, only_active=True)
        messages = self._build_messages(active_invariants)

        started = time.perf_counter()
        response = self._client.chat.completions.create(
            model=self._model.id, messages=messages)
        elapsed = round(time.perf_counter() - started, 2)

        reply             = response.choices[0].message.content
        prompt_tokens     = response.usage.prompt_tokens
        completion_tokens = response.usage.completion_tokens

        db.save_assistant_message(
            self._session_id, reply, prompt_tokens, completion_tokens)

        # Страж: проверяем ответ на соответствие инвариантам
        compliance = Compliance(checked=False, compliant=True, refused=False)
        if self._guard and active_invariants:
            compliance = self._check_compliance(
                user_message, reply, active_invariants)

        cost = round(
            prompt_tokens     * self._model.price_input_1m  / 1_000_000
            + completion_tokens * self._model.price_output_1m / 1_000_000, 6)
        usage   = TokenUsage(prompt_tokens, completion_tokens,
                             prompt_tokens + completion_tokens, cost)
        session = SessionStats(**db.get_session_token_totals(self._session_id))

        return AgentResponse(
            answer=reply, elapsed_sec=elapsed, model=self._model.id,
            turn=session.turns, usage=usage, session=session,
            compliance=compliance,
        )

    def clear_short_term(self) -> None:
        db.clear_short_term(self._session_id)

    # ------------------------------------------------------------------
    # Сборка контекста
    # ------------------------------------------------------------------

    def _build_messages(self, invariants: list[dict]) -> list[dict]:
        system  = self._make_system(invariants)
        history = db.get_messages(self._session_id)
        recent  = history[-SHORT_TERM_WINDOW:]
        return [{"role": "system", "content": system}] + recent

    def _make_system(self, invariants: list[dict]) -> str:
        parts = [self._system_prompt]

        # ИНВАРИАНТЫ — первыми и с жёсткими правилами
        if invariants:
            block = [self._INVARIANT_RULES]
            by_cat: dict[str, list[str]] = {}
            for inv in invariants:
                by_cat.setdefault(inv["category"], []).append(inv["content"])
            for cat, items in by_cat.items():
                title = db.INVARIANT_CATEGORIES.get(cat, cat)
                lines = "\n".join(f"- {c}" for c in items)
                block.append(f"### {title}\n{lines}")
            parts.append("\n\n".join(block))

        # Память (как обычно)
        long_term = db.load_long_term(self._session_id)
        lt_blocks = []
        titles = {"profile": "Профиль-факты", "decision": "Принятые решения",
                  "knowledge": "Знания"}
        for cat, t in titles.items():
            items = long_term.get(cat, [])
            if items:
                lines = "\n".join(f"- {it['content']}" for it in items)
                lt_blocks.append(f"### {t}\n{lines}")
        if lt_blocks:
            parts.append("## Долговременная память\n" + "\n\n".join(lt_blocks))

        working = db.load_working(self._session_id)
        if working:
            lines = "\n".join(f"- **{k}:** {v}" for k, v in working.items())
            parts.append(f"## Рабочая память\n{lines}")

        return "\n\n".join(parts)

    # ------------------------------------------------------------------
    # Страж: проверка соответствия инвариантам
    # ------------------------------------------------------------------

    _GUARD_PROMPT = (
        "Ты — аудитор соответствия инвариантам проекта. Инварианты — "
        "нерушимые ограничения.\n\n"
        "ИНВАРИАНТЫ:\n{invariants}\n\n"
        "ЗАПРОС ПОЛЬЗОВАТЕЛЯ:\n{request}\n\n"
        "ОТВЕТ АССИСТЕНТА:\n{answer}\n\n"
        "Проверь: НАРУШАЕТ ли ответ ассистента хотя бы один инвариант "
        "(предлагает ли он решение, выходящее за рамки)? "
        "Учти: если ассистент ОТКАЗАЛСЯ нарушать инвариант — это соответствие "
        "(compliant=true, refused=true).\n"
        "Верни ТОЛЬКО валидный JSON без markdown:\n"
        "{{\n"
        '  "compliant": true|false,\n'
        '  "refused": true|false,\n'
        '  "violations": [{{"invariant": "<текст инварианта>", '
        '"reason": "<чем ответ его нарушает>"}}]\n'
        "}}"
    )

    def _check_compliance(self, request: str, answer: str,
                          invariants: list[dict]) -> Compliance:
        inv_text = "\n".join(
            f"- [{db.INVARIANT_CATEGORIES.get(i['category'], i['category'])}] {i['content']}"
            for i in invariants
        )
        prompt = self._GUARD_PROMPT.format(
            invariants=inv_text, request=request, answer=answer)
        try:
            resp = self._client.chat.completions.create(
                model=self._model.id,
                messages=[{"role": "user", "content": prompt}])
            raw = resp.choices[0].message.content.strip()
            if "```" in raw:
                raw = raw.split("```")[1].lstrip("json").strip()
            data = json.loads(raw)
            violations = data.get("violations") or []
            if not isinstance(violations, list):
                violations = []
            return Compliance(
                checked=True,
                compliant=bool(data.get("compliant", True)),
                refused=bool(data.get("refused", False)),
                violations=violations,
            )
        except Exception:
            # Проверка не удалась — не блокируем ответ, но помечаем как непроверенный
            return Compliance(checked=False, compliant=True, refused=False)
