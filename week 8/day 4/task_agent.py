"""
Задача 2 (как в Дне 2): агентный режим «Bug Fix».

Самописный цикл вызова инструментов поверх Ollama /api/chat (tools): модель сама читает код,
ищет причину, правит файл, запускает проверки и заканчивает ответом. Результат проверяется
скрытыми проверками. Это НЕ агент Continue в IDE — упрощённый цикл с теми же возможностями.
"""

import difflib
import json
import re
import time
import urllib.error
from pathlib import Path

import ollama_client
import sandbox

HERE = Path(__file__).resolve().parent
MAX_STEPS = 24

BUG_REPORT = (
    "БАГ-РЕПОРТ:\nПользователь вводит в веб-форме в поле «Последних коммитов» произвольный текст, жмёт "
    "«Сгенерировать» — и вместо понятного сообщения видит «Сервер вернул ошибку 500: <!doctype html>…». "
    "В консоли сервера — traceback. Нужно, чтобы пользователь получал нормальное сообщение об ошибке."
)

PROFILE = """Ты — инженер, чинящий баги (профиль Bug Fix). Работай автономно, вопросов не задавай.
Порядок: 1) найди код по симптому (grep/read_file); 2) воспроизведи баг запуском (run_python); 3) найди первопричину;
4) почини минимальным диффом в app.py (replace_in_file); 5) добавь регрессионный тест в test_stats.py;
6) запусти ВСЕ тесты (run_python test_stats.py) и ruff (run_ruff). НЕЛЬЗЯ: ослаблять/удалять существующие тесты,
глушить ошибку голым except, трогать контракт ответов. Закончи ответом в формате:
## Что нашёл / ## Что починил / ## Что проверил. Пока не прогнал проверки — вызывай инструменты, а не отвечай."""

TOOLS = [
    {"type": "function", "function": {"name": "list_files", "description": "Список файлов проекта",
     "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "read_file", "description": "Прочитать файл целиком",
     "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "grep", "description": "Поиск regex по файлам проекта",
     "parameters": {"type": "object", "properties": {"pattern": {"type": "string"}}, "required": ["pattern"]}}},
    {"type": "function", "function": {"name": "replace_in_file",
     "description": "Заменить точный фрагмент old на new в файле (old должен встречаться ровно один раз)",
     "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "old": {"type": "string"},
                    "new": {"type": "string"}}, "required": ["path", "old", "new"]}}},
    {"type": "function", "function": {"name": "write_file", "description": "Создать/перезаписать файл",
     "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
                    "required": ["path", "content"]}}},
    {"type": "function", "function": {"name": "run_python",
     "description": "Запустить python-скрипт проекта (например test_stats.py) или код через code",
     "parameters": {"type": "object", "properties": {"script": {"type": "string"}, "code": {"type": "string"}}}}},
    {"type": "function", "function": {"name": "run_ruff", "description": "Запустить линтер ruff",
     "parameters": {"type": "object", "properties": {}}}},
]


TEXT_PROTOCOL = (
    "\n\nИНСТРУМЕНТЫ (вызываются текстом). На каждом шаге отвечай РОВНО ОДНИМ JSON-объектом вида "
    '{"name": "<инструмент>", "arguments": {...}} и больше ничем — после результата получишь следующий ход. '
    "Когда всё сделано и проверено — ответь обычным текстом (без JSON) по формату отчёта.\nДоступные инструменты:\n"
    + "\n".join(f"- {t['function']['name']}: {t['function']['description']}; параметры: "
                f"{list(t['function']['parameters'].get('properties', {}))}" for t in TOOLS)
)


def extract_text_calls(content: str) -> list[dict]:
    """Достать вызовы инструментов, которые модель написала текстом (JSON в ``` или голый)."""
    calls = []
    for m in re.finditer(r"\{(?:[^{}]|\{(?:[^{}]|\{[^{}]*\})*\})*\}", content, re.S):
        try:
            obj = json.loads(m.group(0))
        except ValueError:
            continue
        if isinstance(obj, dict) and obj.get("name") in {t["function"]["name"] for t in TOOLS}:
            calls.append({"function": {"name": obj["name"], "arguments": obj.get("arguments") or {}}})
    return calls[:1]   # один вызов за ход: следующий шаг зависит от результата


def fuzzy_replace(src: str, old: str, new: str) -> str | None:
    """Заменить блок строк, сравнивая без учёта отступов; новый текст получает отступ найденного места."""
    lines, olines = src.splitlines(), [ln.strip() for ln in old.strip("\n").splitlines()]
    if not olines or not any(olines):
        return None
    hits = [i for i in range(len(lines) - len(olines) + 1)
            if [ln.strip() for ln in lines[i:i + len(olines)]] == olines]
    if len(hits) != 1:
        return None
    i = hits[0]
    indent = lines[i][:len(lines[i]) - len(lines[i].lstrip())]
    first_indent = new.split("\n")[0][:len(new.split("\n")[0]) - len(new.split("\n")[0].lstrip())] if new else ""
    new_lines = [indent + ln[len(first_indent):] if ln.startswith(first_indent) else indent + ln.lstrip()
                 for ln in new.strip("\n").splitlines()]
    return "\n".join(lines[:i] + new_lines + lines[i + len(olines):]) + ("\n" if src.endswith("\n") else "")


def normalize_args(name: str, args: object) -> dict:
    """Терпимо к кривому формату аргументов: список → по порядку параметров, строка → первый параметр."""
    params = next(list(t["function"]["parameters"].get("properties", {})) for t in TOOLS
                  if t["function"]["name"] == name)
    if isinstance(args, dict):
        return args
    if isinstance(args, list):
        return dict(zip(params, args, strict=False))
    if isinstance(args, str) and params:
        return {params[0]: args}
    return {}


def _safe(proj: Path, rel: str) -> Path | None:
    p = (proj / rel).resolve()
    return p if proj.resolve() in p.parents else None


def call_tool(proj: Path, name: str, args: dict) -> str:
    try:
        if name == "list_files":
            return "\n".join(sorted(str(p.relative_to(proj)) for p in proj.rglob("*") if p.is_file()
                                    and "__pycache__" not in p.parts and p.name != "ruff.toml"))
        if name == "read_file":
            p = _safe(proj, args["path"])
            return p.read_text() if p and p.is_file() else f"нет такого файла: {args.get('path')}"
        if name == "grep":
            rx = re.compile(args["pattern"])
            hits = [f"{p.name}:{i}: {line.strip()}" for p in sorted(proj.glob("*.py"))
                    for i, line in enumerate(p.read_text().splitlines(), 1) if rx.search(line)]
            return "\n".join(hits[:40]) or "ничего не найдено"
        if name == "replace_in_file":
            p = _safe(proj, args["path"])
            if not p or not p.is_file():
                return f"нет такого файла: {args.get('path')}"
            src = p.read_text()
            if src.count(args["old"]) == 1:
                p.write_text(src.replace(args["old"], args["new"]))
                return "ok"
            fixed = fuzzy_replace(src, args["old"], args["new"])
            if fixed is None:
                first = args["old"].strip().splitlines()[0].strip() if args["old"].strip() else ""
                near = [f"{i}: {ln}" for i, ln in enumerate(src.splitlines(), 1) if first and first in ln]
                return ("old не найден (или не единственный). Скопируй фрагмент ТОЧНО из read_file. "
                        f"Похожие строки: {near[:3]}")
            p.write_text(fixed)
            return "ok (совпадение по строкам без учёта отступов)"
        if name == "write_file":
            p = _safe(proj, args["path"])
            if not p:
                return "путь вне проекта"
            p.write_text(args["content"])
            return "ok"
        if name == "run_python":
            if args.get("code"):
                return str(sandbox.run([sandbox.PYTHON, "-c", args["code"]], proj)[1])
            script = args.get("script", "")
            if not _safe(proj, script):
                return "скрипт вне проекта"
            rc, out = sandbox.run([sandbox.PYTHON, script], proj)
            return f"exit={rc}\n{out}"
        if name == "run_ruff":
            ok, out = sandbox.ruff(proj)
            return "All checks passed!" if ok else out
    except Exception as e:   # noqa: BLE001 — ошибка инструмента возвращается модели как текст
        return f"ошибка инструмента: {e}"
    return f"неизвестный инструмент: {name}"


CHECK = r'''
import json
from unittest import mock
import app as a
C = [{"hash":"a","date":"2026-10-21","author":"Ann","subject":"x","body":""}]
cl = a.app.test_client()
out = {}
with mock.patch("github_repo.get_commits", return_value=C), mock.patch("digest.generate", return_value="# ok"):
    for bad in ("abc", "1.5", [1], {"a": 1}):
        r = cl.post("/generate", json={"repo": "o/r", "deepseek_key": "k", "last": bad})
        out[repr(bad)] = [r.status_code, r.is_json]
    r = cl.post("/generate", json={"repo": "o/r", "deepseek_key": "k", "last": "7"})
    out["valid_7"] = [r.status_code, r.is_json]
print(json.dumps(out))
'''


def evaluate(proj: Path, base: Path) -> dict:
    r: dict = {}
    rc, out = sandbox.run([sandbox.PYTHON, "-c", CHECK], proj)
    data: dict = {}
    if rc == 0:
        try:
            data = json.loads(sandbox.last_json_line(out))
        except (ValueError, IndexError):
            data = {}
    bad_keys = ("'abc'", "'1.5'", "[1]", "{'a': 1}")
    r["bug_fixed"] = bool(data) and all(data.get(k) == [400, True] for k in bad_keys)
    r["valid_last_still_works"] = data.get("valid_7") == [200, True]
    rc, out = sandbox.run([sandbox.PYTHON, "test_stats.py"], proj)
    r["existing_tests_pass"] = rc == 0
    r["tests_out"] = "" if rc == 0 else out[-300:]
    base_t = (base / "test_stats.py").read_text()
    new_t = (proj / "test_stats.py").read_text()
    r["tests_not_weakened"] = new_t.count("assert") >= base_t.count("assert")
    r["regression_test_added"] = new_t != base_t and "/generate" in new_t
    r["ruff_ok"], r["ruff_out"] = sandbox.ruff(proj)
    app_src = (proj / "app.py").read_text()
    r["no_bare_except_pass"] = not re.search(r"except\s*:\s*\n?\s*pass", app_src)
    base_app = (base / "app.py").read_text()
    r["diff_lines_app"] = sum(1 for _ in set(app_src.splitlines()) ^ set(base_app.splitlines()))
    r["checks_passed"] = sum(1 for k, v in r.items() if isinstance(v, bool) and v)
    r["checks_total"] = sum(1 for v in r.values() if isinstance(v, bool))
    return r


def run(model: str, options: dict, rules: str = "short") -> dict:
    base = sandbox.HERE / "fixtures" / "bugfix_base"
    proj = sandbox.make("bugfix_base")
    system = PROFILE + "\n\nПравила проекта:\n" + (HERE / "rules_local.md").read_text()
    if rules == "none":
        system = PROFILE
    messages = [{"role": "system", "content": system}, {"role": "user", "content": BUG_REPORT}]
    t0 = time.perf_counter()
    totals = {"prompt_tokens": 0, "gen_tokens": 0}
    steps, tool_errors, calls, nudges = 0, 0, [], 0
    final, error, mode = "", "", "native"
    edited = False
    seen: dict = {}
    for steps in range(1, MAX_STEPS + 1):  # noqa: B007 — steps нужен после цикла
        try:
            resp = ollama_client.chat(model, messages, options, tools=TOOLS if mode == "native" else None)
        except urllib.error.HTTPError as e:
            if mode == "native" and e.code == 400:   # модель без нативных tools → текстовый протокол
                mode = "text"
                messages[0]["content"] += TEXT_PROTOCOL
                continue
            error = f"HTTPError: {e}"
            break
        except Exception as e:   # noqa: BLE001
            error = f"{type(e).__name__}: {e}"
            break
        totals["prompt_tokens"] += resp["prompt_tokens"]
        totals["gen_tokens"] += resp["gen_tokens"]
        msg = resp["message"]
        messages.append(msg)
        tcs = msg.get("tool_calls") or []
        if not tcs:
            tcs = extract_text_calls(msg.get("content", ""))   # вызов написан текстом
            if tcs and mode == "native":
                mode = "native+text"
        if not tcs:
            if not edited and nudges < 2:   # закончил, не изменив код → один-два толчка
                nudges += 1
                messages.append({"role": "user", "content": (
                    "Ты ещё не изменил код и не запускал проверки. Не описывай шаги — вызывай инструменты "
                    "(grep → read_file → replace_in_file → run_python test_stats.py → run_ruff).")})
                continue
            final = msg.get("content", "")
            break
        for tc in tcs:
            fn = tc["function"]
            args = fn.get("arguments") or {}
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except ValueError:
                    args = {}
            args = normalize_args(fn["name"], args)
            key = (fn["name"], json.dumps(args, sort_keys=True, ensure_ascii=False))
            seen[key] = seen.get(key, 0) + 1
            result = call_tool(proj, fn["name"], args)
            if seen[key] >= 3:
                result += "\n[ПОДСКАЗКА: этот вызов уже выполнялся 3 раза с тем же результатом — смени шаг: переходи к правке или проверке.]"
            if result.startswith(("ошибка", "неизвестный", "нет такого", "old встречается")):
                tool_errors += 1
            if fn["name"] in ("replace_in_file", "write_file") and result == "ok":
                edited = True
            calls.append(fn["name"])
            if mode == "text":
                messages.append({"role": "user", "content": f"Результат {fn['name']}:\n{result[:3000]}"})
            else:
                messages.append({"role": "tool", "content": result[:3000], "tool_name": fn["name"]})
    wall = round(time.perf_counter() - t0, 1)
    res = evaluate(proj, base)
    diff = "".join(difflib.unified_diff(
        (base / "app.py").read_text().splitlines(True), (proj / "app.py").read_text().splitlines(True),
        "app.py (до)", "app.py (после)"))
    diff += "".join(difflib.unified_diff(
        (base / "test_stats.py").read_text().splitlines(True), (proj / "test_stats.py").read_text().splitlines(True),
        "test_stats.py (до)", "test_stats.py (после)"))
    res.update({"diff": diff})
    res.update({"task": "agent_bugfix", "model": model, "rules": rules, "options": options,
                "steps": steps, "mode": mode, "nudges": nudges, "tool_calls": len(calls), "tool_errors": tool_errors,
                "tools_used": sorted(set(calls)), "wall_s": wall, "error": error,
                "finished_with_answer": bool(final), **totals, "answer_head": final[:300]})
    return res
