"""
LLMAgent: модель памяти (day 1) + ПЕРСОНАЛИЗАЦИЯ через профиль (day 2).

Профиль пользователя описывает:
  • идентичность — имя, роль, уровень экспертизы
  • стиль        — тон, развёрнутость (verbosity)
  • формат       — предпочтения по формату ответа, язык
  • ограничения  — что нельзя / на что обращать внимание

Профиль подключается к КАЖДОМУ запросу: формируется блок «Профиль пользователя»
с явными инструкциями, как адаптировать ответ, и кладётся в начало системного
промпта (до памяти). Так ассистент учитывает предпочтения автоматически,
без напоминаний в каждом сообщении.
"""

import json
import os
import time
from dataclasses import dataclass, field

from openai import OpenAI

import database as db
from models import DEFAULT_MODEL, ModelInfo, get_model

SHORT_TERM_WINDOW = 10


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
    short_term_total:      int
    short_term_in_context: int
    working_task:          str | None
    working:               dict = field(default_factory=dict)
    long_term:             dict = field(default_factory=dict)
    last_writes:           list = field(default_factory=list)


@dataclass
class AgentResponse:
    answer:      str
    elapsed_sec: float
    model:       str
    turn:        int
    usage:       TokenUsage
    session:     SessionStats
    memory:      MemorySnapshot
    profile:     dict | None        # активный профиль на момент запроса


# ------------------------------------------------------------------
# Агент
# ------------------------------------------------------------------

class LLMAgent:
    DEFAULT_SYSTEM = (
        "Ты полезный ИИ-ассистент с явной моделью памяти и персонализацией. "
        "Строго следуй профилю пользователя (стиль, формат, ограничения) и "
        "используй память (профиль-факты, решения, знания, данные задачи), "
        "чтобы отвечать точно и в нужной пользователю манере."
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

    def active_profile(self) -> dict | None:
        pid = db.get_active_profile_id(self._session_id)
        return db.get_profile(pid) if pid else None

    # ------------------------------------------------------------------
    # Основной цикл
    # ------------------------------------------------------------------

    def ask(self, user_message: str) -> AgentResponse:
        db.save_user_message(self._session_id, user_message)

        profile             = self.active_profile()
        messages, in_context = self._build_messages(profile)

        started = time.perf_counter()
        response = self._client.chat.completions.create(
            model=self._model.id,
            messages=messages,
        )
        elapsed = round(time.perf_counter() - started, 2)

        reply             = response.choices[0].message.content
        prompt_tokens     = response.usage.prompt_tokens
        completion_tokens = response.usage.completion_tokens

        db.save_assistant_message(
            self._session_id, reply, prompt_tokens, completion_tokens)

        last_writes: list = []
        if self._auto_route:
            last_writes = self._route_memory(profile)

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
            profile=profile,
        )

    def clear_short_term(self) -> None:
        db.clear_short_term(self._session_id)

    # ------------------------------------------------------------------
    # Сборка контекста: ПРОФИЛЬ + память + диалог
    # ------------------------------------------------------------------

    def _build_messages(self, profile: dict | None) -> tuple[list[dict], int]:
        system   = self._make_system(profile)
        history  = db.get_messages(self._session_id)
        recent   = history[-SHORT_TERM_WINDOW:]
        messages = [{"role": "system", "content": system}] + recent
        return messages, len(recent)

    def _make_system(self, profile: dict | None) -> str:
        parts = [self._system_prompt]

        # 1) ПРОФИЛЬ — идёт первым, чтобы максимально влиять на стиль ответа
        if profile:
            parts.append(self._format_profile(profile))

        # 2) Долговременная память
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

        # 3) Рабочая память
        working = db.load_working(self._session_id)
        if working:
            task  = db.get_active_task(self._session_id)
            head  = f"## Рабочая память (текущая задача: {task})" if task \
                    else "## Рабочая память"
            lines = "\n".join(f"- **{k}:** {v}" for k, v in working.items())
            parts.append(f"{head}\n{lines}")

        return "\n\n".join(parts)

    @staticmethod
    def _format_profile(p: dict) -> str:
        """Превратить структурированный профиль в явные инструкции для LLM."""
        lang_name = {"ru": "русском", "en": "английском"}.get(p.get("language", "ru"), "русском")
        verb = {
            "кратко":   "Отвечай максимально кратко, только суть, без воды.",
            "средне":   "Отвечай умеренно подробно.",
            "подробно": "Отвечай развёрнуто, с деталями и пояснениями.",
        }.get(p.get("verbosity", "средне"), "")
        exp = {
            "новичок": "Пользователь — новичок: объясняй простым языком, "
                       "избегай жаргона, поясняй термины.",
            "средний": "Пользователь среднего уровня: можно использовать "
                       "профессиональную терминологию с краткими пояснениями.",
            "эксперт": "Пользователь — эксперт: используй точную терминологию, "
                       "не объясняй базовые вещи, фокусируйся на нюансах.",
        }.get(p.get("expertise", "средний"), "")
        tone = {
            "дружелюбный": "Тон — дружелюбный и неформальный.",
            "нейтральный": "Тон — нейтральный, деловой.",
            "формальный":  "Тон — строго формальный, официальный.",
        }.get(p.get("tone", "нейтральный"), "")

        lines = [f"## Профиль пользователя — адаптируй ответ под него"]
        if p.get("name"):
            lines.append(f"- Имя: {p['name']}")
        if p.get("role"):
            lines.append(f"- Роль: {p['role']}")
        lines.append(f"- Язык ответа: {lang_name}")
        if exp:  lines.append(f"- {exp}")
        if verb: lines.append(f"- {verb}")
        if tone: lines.append(f"- {tone}")
        if p.get("answer_format"):
            lines.append(f"- Формат ответа: {p['answer_format']}")
        if p.get("constraints"):
            lines.append(f"- Ограничения: {p['constraints']}")
        return "\n".join(lines)

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
    # Маршрутизация памяти + авто-детект предпочтений профиля
    # ------------------------------------------------------------------

    _ROUTER_PROMPT = (
        "Ты — маршрутизатор памяти ассистента. Проанализируй последний обмен "
        "репликами и реши, что СТОИТ запомнить и куда.\n\n"
        "Слои памяти:\n"
        "• working — данные ТЕКУЩЕЙ задачи (параметры, переменные, статус). key-value.\n"
        "• long_term:\n"
        "    - profile: устойчивые факты о пользователе (имя, роль, стек, контекст)\n"
        "    - decision: принятые решения\n"
        "    - knowledge: общие факты/знания\n"
        "• prefs — ЯВНО высказанные пользователем ПРЕДПОЧТЕНИЯ по тому, КАК отвечать.\n"
        "    Поля (заполняй ТОЛЬКО при явном указании пользователя):\n"
        "      tone: дружелюбный|нейтральный|формальный\n"
        "      verbosity: кратко|средне|подробно\n"
        "      expertise: новичок|средний|эксперт\n"
        "      answer_format: свободный текст (например 'с примерами кода', 'списками')\n"
        "      constraints: свободный текст (например 'без жаргона')\n\n"
        "Активная задача: {task}\nТекущая рабочая память: {working}\n\n"
        "Обмен репликами:\n{exchange}\n\n"
        "Верни ТОЛЬКО валидный JSON без markdown:\n"
        "{{\n"
        '  "task": "<имя задачи или null>",\n'
        '  "working": {{"ключ": "значение"}},\n'
        '  "long_term": [{{"category": "profile|decision|knowledge", "content": "..."}}],\n'
        '  "prefs": {{}}\n'
        "}}\n"
        "Сохраняй ТОЛЬКО важное. prefs заполняй ТОЛЬКО если пользователь явно "
        "попросил отвечать определённым образом."
    )

    def _route_memory(self, profile: dict | None) -> list[dict]:
        history = db.get_messages(self._session_id)
        last    = history[-2:]
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

            task = data.get("task")
            if isinstance(task, str) and task.strip() and task.strip() != "—":
                db.set_active_task(self._session_id, task.strip())

            working = data.get("working") or {}
            if isinstance(working, dict):
                cur_task = db.get_active_task(self._session_id)
                for k, v in working.items():
                    db.upsert_working(self._session_id, str(k), str(v), task=cur_task)
                    writes.append({"layer": "working", "category": "",
                                   "key": str(k), "content": str(v)})

            lt = data.get("long_term") or []
            if isinstance(lt, list):
                for entry in lt:
                    if not isinstance(entry, dict):
                        continue
                    cat = entry.get("category", "")
                    content = (entry.get("content") or "").strip()
                    if cat in db.LONG_TERM_CATEGORIES and content:
                        if db.add_long_term(self._session_id, cat, content):
                            writes.append({"layer": "long_term", "category": cat,
                                           "key": "", "content": content})

            # Авто-обновление профиля из явно высказанных предпочтений
            prefs = data.get("prefs") or {}
            if isinstance(prefs, dict) and prefs and profile:
                clean = {k: v for k, v in prefs.items()
                         if k in db.PROFILE_FIELDS and v}
                if clean:
                    db.update_profile(profile["id"], self._session_id, **clean)
                    for k, v in clean.items():
                        writes.append({"layer": "profile", "category": k,
                                       "key": k, "content": str(v)})
        except Exception:
            pass
        return writes
