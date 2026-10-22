"""
Задача 1 (как в Дне 1): сгенерировать фичу одним промптом, без уточнений.

Модель получает правила (системный промпт) + файлы проекта и должна вернуть файлы целиком.
Результат применяется в песочнице и проверяется: компиляция, ruff, собственный тест модели,
скрытая приёмочная проверка и чек-лист стиля (тот же, что сравнивали у облачного ассистента).
"""

import json
import re
from pathlib import Path

import ollama_client
import sandbox

HERE = Path(__file__).resolve().parent
ROOT_RULES = HERE.parent.parent / "CLAUDE.md"

TASK = (
    "Добавь в сервис новый эндпоинт со статистикой активности GitHub-репозитория: по owner/repo "
    "(или ссылке) вернуть топ авторов по числу коммитов, число коммитов по дням и самый активный "
    "день. Без AI.\n\n"
    "Верни ТОЛЬКО файлы целиком, каждый в формате:\n"
    "FILE: <имя файла>\n```python\n<содержимое>\n```\n"
    "Нужны файлы: activity.py (новая логика), app.py (с новым маршрутом), test_stats.py (новый тест). "
    "Пояснений не пиши."
)

ACCEPT = r'''
import json
from unittest import mock
import app as a
C = [{"hash":"a","date":"2026-10-21","author":"Ann","subject":"x","body":""},
     {"hash":"b","date":"2026-10-21","author":"Ann","subject":"x","body":""},
     {"hash":"c","date":"2026-10-20","author":"Bob","subject":"x","body":""}]
cl = a.app.test_client()
res = {}
with mock.patch("github_repo.get_commits", return_value=C):
    for path in ("/stats", "/activity", "/repo-stats"):
        r = cl.post(path, json={"repo": "https://github.com/o/r"})
        if r.status_code == 200:
            res["path"] = path; res["json"] = r.get_json(); break
    else:
        res["json"] = None
    if res.get("path"):
        e = cl.post(res["path"], json={})
        res["empty_status"] = e.status_code; res["empty_is_json"] = e.is_json
print(json.dumps(res, ensure_ascii=False))
'''


def system_prompt(rules: str) -> str:
    if rules == "full":
        return ROOT_RULES.read_text()
    if rules == "short":
        return (HERE / "rules_local.md").read_text()
    return "Ты — код-ассистент. Отвечай по-русски."


def user_prompt(base: Path) -> str:
    parts = [TASK, "\n\nФайлы проекта:\n"]
    for name in ("app.py", "github_repo.py", "test_digest.py"):
        parts.append(f"\nFILE: {name}\n```python\n{(base / name).read_text()}\n```\n")
    return "".join(parts)


def evaluate(proj: Path, files: dict[str, str]) -> dict:
    """Применить ответ модели и посчитать чек-лист."""
    sandbox.apply(proj, files)
    r: dict = {"files": sorted(files)}
    r["parsed_3_files"] = {"activity.py", "app.py", "test_stats.py"} <= set(files)
    rc, out = sandbox.run([sandbox.PYTHON, "-m", "py_compile", "app.py", "activity.py", "test_stats.py"], proj)
    r["compiles"] = rc == 0
    r["compile_err"] = "" if rc == 0 else out[-300:]
    r["ruff_ok"], r["ruff_out"] = sandbox.ruff(proj)
    rc, out = sandbox.run([sandbox.PYTHON, "test_stats.py"], proj)
    r["own_test_passes"] = rc == 0
    r["own_test_out"] = "" if rc == 0 else out[-400:]
    rc, out = sandbox.run([sandbox.PYTHON, "-c", ACCEPT], proj)
    acc: dict = {}
    if rc == 0:
        try:
            acc = json.loads(sandbox.last_json_line(out))
        except (ValueError, IndexError):
            acc = {}
    blob = json.dumps(acc.get("json"), ensure_ascii=False) if acc.get("json") else ""
    r["acceptance_200"] = bool(acc.get("json"))
    r["acceptance_content"] = bool(blob) and "Ann" in blob and "2026-10-21" in blob and "Bob" in blob
    r["empty_body_400_json"] = acc.get("empty_status") == 400 and acc.get("empty_is_json") is True
    app_src, act_src = files.get("app.py", ""), files.get("activity.py", "")
    test_src = files.get("test_stats.py", "")
    r["style_last_default_15"] = bool(re.search(r"or 15\)", app_src))
    r["style_mock_patch"] = "mock.patch" in test_src and not re.search(r"\w+\.\w+\s*=\s*lambda", test_src)
    r["style_module_docstring_ru"] = bool(re.match(r'\s*"""[^"]*[А-Яа-я]', act_src))
    r["style_no_print_in_service"] = "print(" not in act_src and "print(" not in app_src
    r["style_typed"] = "->" in act_src and "Optional" not in act_src and "List[" not in act_src
    r["checks_passed"] = sum(1 for k, v in r.items() if isinstance(v, bool) and v)
    r["checks_total"] = sum(1 for v in r.values() if isinstance(v, bool))
    return r


def run(model: str, options: dict, rules: str = "short") -> dict:
    base = sandbox.HERE / "fixtures" / "feature_base"
    proj = sandbox.make("feature_base")
    messages = [{"role": "system", "content": system_prompt(rules)},
                {"role": "user", "content": user_prompt(base)}]
    resp = ollama_client.chat(model, messages, options)
    text = resp["message"].get("content", "")
    files = sandbox.parse_files(text)
    res = evaluate(proj, files)
    res.update({"task": "feature", "model": model, "rules": rules, "options": options,
                **{k: resp[k] for k in ("wall_s", "prompt_tokens", "gen_tokens", "gen_tps",
                                        "prefill_tps", "ttft_s", "load_s")},
                "answer_head": text[:300]})
    return res
