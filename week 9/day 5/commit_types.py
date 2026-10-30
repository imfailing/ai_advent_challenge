"""
Классификация git-коммита в тип Conventional Commits (feat/fix/docs/...). Роль в сервисе: промпты для разных
режимов моделей, разбор ответа модели (JSON `{"type": ...}`), метрики качества. Без Flask и без сети.
Режимы: `plain` — вход как при обучении тюна («Commit message:\n<текст>»), `prompt` — тот же вход плюс
подробная инструкция с примерами (для моделей без тюна).
"""

import json
import re

TYPES = ["feat", "fix", "docs", "refactor", "test", "chore", "perf", "ci"]
MAX_NEW_TOKENS = 40
SYSTEM_PROMPT = """You classify git commit messages into Conventional Commit types.
Allowed types: feat, fix, docs, refactor, test, chore, perf, ci.
- feat: a new feature or capability for users.
- fix: a bug fix.
- docs: documentation-only changes.
- refactor: code restructuring with no behavior change.
- test: adding or changing tests only.
- chore: maintenance, dependency updates, releases, tooling, housekeeping.
- perf: a change that improves performance.
- ci: changes to CI/CD configuration or pipelines.
Answer with ONLY a JSON object of the form {"type": "<type>"} and nothing else.

Examples:
Commit message:
add support for custom headers in the client
-> {"type": "feat"}
Commit message:
prevent crash when the config file is empty
-> {"type": "fix"}
Commit message:
clarify installation steps in the README
-> {"type": "docs"}
Commit message:
extract validation into a separate helper
-> {"type": "refactor"}
Commit message:
add unit tests for the date parser
-> {"type": "test"}
Commit message:
update dependency eslint to v9.1.0
-> {"type": "chore"}
Commit message:
cache compiled templates to speed up rendering
-> {"type": "perf"}
Commit message:
run lint job on pull requests in GitHub Actions
-> {"type": "ci"}"""


def build_messages(message: str, mode: str) -> list[dict]:
    """Сообщения чата для коммита: mode 'plain' (как в обучении) или 'prompt' (с инструкцией)."""
    user = {"role": "user", "content": f"Commit message:\n{message.strip()}"}
    if mode == "prompt":
        return [{"role": "system", "content": SYSTEM_PROMPT}, user]
    if mode == "plain":
        return [user]
    raise ValueError(f"Неизвестный режим промпта: {mode}")


def parse_type(text: str) -> tuple[str | None, bool]:
    """Достать тип из ответа; второй элемент — строгий формат (весь ответ — один JSON)."""
    stripped = text.strip()
    try:
        obj = json.loads(stripped)
        if isinstance(obj, dict) and list(obj) == ["type"] and obj["type"] in TYPES:
            return obj["type"], True
    except json.JSONDecodeError:
        pass
    m = re.search(r'"type"\s*:\s*"([a-z]+)"', text)
    return (m.group(1) if m and m.group(1) in TYPES else None), False


def metrics(rows: list[dict]) -> dict:
    """Accuracy, доля строгого формата, macro-F1 и accuracy по классам."""
    n = len(rows)
    f1s, per_class = [], {}
    for t in TYPES:
        tp = sum(r["pred"] == t and r["gold"] == t for r in rows)
        fp = sum(r["pred"] == t and r["gold"] != t for r in rows)
        fn = sum(r["pred"] != t and r["gold"] == t for r in rows)
        f1s.append(2 * tp / (2 * tp + fp + fn) if tp else 0.0)
        support = sum(r["gold"] == t for r in rows)
        per_class[t] = round(tp / support, 3) if support else None
    return {
        "n": n,
        "accuracy": round(sum(r["pred"] == r["gold"] for r in rows) / n, 3),
        "strict_format": round(sum(r["strict"] for r in rows) / n, 3),
        "macro_f1": round(sum(f1s) / len(TYPES), 3),
        "per_class_accuracy": per_class,
    }
