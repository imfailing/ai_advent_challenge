"""
Обновление ПАМЯТИ ЗАДАЧИ по ходу диалога.

После каждого хода отдельный вызов LLM смотрит на последний обмен и текущую
память, и обновляет:
  • goal          — цель диалога (устойчивая; не меняем без явной смены темы);
  • clarifications— что пользователь уже уточнил (накопительно);
  • constraints   — зафиксированные ограничения;
  • terms         — зафиксированные термины/определения.

Это позволяет ассистенту не терять цель в длинном диалоге.
"""

import json
import os

from openai import OpenAI

MODEL = "deepseek-v4-flash"


class TaskMemoryUpdater:
    PROMPT = (
        "Ты ведёшь память задачи в диалоге. Обнови её по последнему обмену.\n\n"
        "Текущая память:\n{memory}\n\n"
        "Последний обмен:\n{exchange}\n\n"
        "Верни ТОЛЬКО JSON:\n"
        "{{\n"
        '  "goal": "цель диалога одной фразой (сохрани прежнюю, если тема та же)",\n'
        '  "clarifications": ["что пользователь уточнил"],\n'
        '  "constraints": ["зафиксированные ограничения"],\n'
        '  "terms": {{"термин": "определение"}}\n'
        "}}\n"
        "Правила:\n"
        "• goal — это цель ПОЛЬЗОВАТЕЛЯ в этом диалоге, взятая из ЕГО слов "
        "(«моя цель…», «хочу…», «нужно…»). НЕ бери цель/бюджеты/сроки из ПРИМЕРОВ "
        "в документах или из ответа ассистента — это чужие данные, не цель пользователя.\n"
        "• если пользователь явно не сменил тему — СОХРАНИ прежнюю goal без изменений.\n"
        "• constraints/terms бери из того, что зафиксировал ПОЛЬЗОВАТЕЛЬ, а не из "
        "примеров в документации.\n"
        "• не теряй ранее зафиксированное — дополняй списки, не обнуляй. "
        "Пиши кратко, по-русски."
    )

    def __init__(self, api_key: str | None = None, model: str = MODEL) -> None:
        self._client = OpenAI(
            api_key=api_key or os.environ["DEEPSEEK_API_KEY"],
            base_url="https://api.deepseek.com",
        )
        self._model = model

    def update(self, memory: dict, user_msg: str, assistant_msg: str) -> dict:
        exchange = f"Пользователь: {user_msg}\nАссистент: {assistant_msg}"
        prompt = self.PROMPT.format(
            memory=json.dumps(memory, ensure_ascii=False, indent=2),
            exchange=exchange)
        try:
            resp = self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"})
            data = json.loads(resp.choices[0].message.content or "{}")
            return self._merge(memory, data)
        except Exception:
            return memory   # сбой обновления памяти не ломает ответ

    @staticmethod
    def _merge(old: dict, new: dict) -> dict:
        def uniq(seq):
            seen, out = set(), []
            for x in seq:
                if isinstance(x, str) and x.strip() and x not in seen:
                    seen.add(x); out.append(x)
            return out

        goal = (new.get("goal") or "").strip() or old.get("goal", "")
        clar = uniq(list(old.get("clarifications", [])) + list(new.get("clarifications", []) or []))
        cons = uniq(list(old.get("constraints", []))    + list(new.get("constraints", []) or []))
        terms = {**old.get("terms", {}), **(new.get("terms", {}) if isinstance(new.get("terms"), dict) else {})}
        return {"goal": goal, "clarifications": clar, "constraints": cons, "terms": terms}


def format_for_prompt(memory: dict) -> str:
    """Компактное представление памяти задачи для системного промпта."""
    if not any([memory.get("goal"), memory.get("clarifications"),
                memory.get("constraints"), memory.get("terms")]):
        return ""
    parts = ["## Память задачи"]
    if memory.get("goal"):
        parts.append(f"- Цель диалога: {memory['goal']}")
    if memory.get("clarifications"):
        parts.append("- Уже уточнено: " + "; ".join(memory["clarifications"]))
    if memory.get("constraints"):
        parts.append("- Ограничения: " + "; ".join(memory["constraints"]))
    if memory.get("terms"):
        parts.append("- Термины: " + "; ".join(f"{k} = {v}" for k, v in memory["terms"].items()))
    return "\n".join(parts)
