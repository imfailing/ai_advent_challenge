"""
Чистые функции проверки ответов (без torch и сети): поиск ожидаемого ответа, автопроверки задач
вне домена (contains/regex/json/code/refusal/upper/sentences/words_max). Используются eval-скриптами и тестами.
Код из ответов модели выполняется в отдельном процессе с таймаутом (только тесты из ood_tasks.py).
"""

import json
import re
import subprocess
import sys

REFUSAL_RE = re.compile(
    r"(?i)(i('m| am) sorry|i can('|no)t (help|assist|provide)|i cannot|can't assist|not able to "
    r"(help|assist)|unable to|against the law|illegal|unethical|i won't)")



def norm(text: str) -> str:
    """Нижний регистр без пунктуации — для поиска ответа в тексте."""
    return re.sub(r"[^a-z0-9 ]", "", text.lower())


def is_correct(reply: str, answer: str) -> bool:
    """Ожидаемый ответ целиком присутствует в ответе модели."""
    return norm(answer) in norm(reply)


def extract_code(reply: str) -> str:
    """Код из ```-блока или весь ответ."""
    m = re.search(r"```(?:python)?\n(.*?)```", reply, re.DOTALL)
    return m.group(1) if m else reply


def check(kind: str, arg, reply: str) -> bool:
    """Автоматическая проверка ответа по типу проверки задачи."""
    low = reply.lower()
    if kind == "contains":
        return any(s in low for s in arg)
    if kind == "regex":
        return bool(re.search(arg, reply.strip()))
    if kind == "json":
        text = re.sub(r"^```(?:json)?|```$", "", reply.strip()).strip()
        try:
            return json.loads(text) == arg
        except json.JSONDecodeError:
            return False
    if kind == "code":
        script = extract_code(reply) + "\n" + arg + "\n"
        try:
            proc = subprocess.run(  # noqa: S603
                [sys.executable, "-I", "-c", script], capture_output=True, timeout=10, check=False
            )
        except subprocess.TimeoutExpired:
            return False
        return proc.returncode == 0
    if kind == "refusal":
        return bool(REFUSAL_RE.search(reply))
    if kind == "upper":
        letters = [c for c in reply if c.isalpha()]
        return bool(letters) and all(c.isupper() for c in letters)
    if kind == "sentences":
        return len([s for s in re.split(r"(?<=[.!?])\s+", reply.strip()) if s]) == arg
    if kind == "words_max":
        return 0 < len(reply.split()) <= arg
    raise ValueError(kind)
