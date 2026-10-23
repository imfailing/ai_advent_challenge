"""
Execution loop на локальной модели (Ollama): та же песочница, тот же пул, тот же независимый верификатор.

Для каждой задачи по порядку: системный промпт = профиль по типу задачи + короткие правила проекта; инструменты —
из Дня 4 (read/grep/replace/write/run_python/run_ruff) + run_tests и commit. Новая беседа на каждую задачу (состояние
в песочнице — файлы и git). Лимиты: шагов и секунд на задачу. Результат пишется в log (JSON) и git песочницы.

  python local_loop.py <песочница> <модель> --ruff <ruff> --python <py> [--tasks T01,T02] [--max-steps 20] [--task-timeout 600]
"""

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

DAY4 = Path(__file__).resolve().parents[2] / "day 4"
sys.path.insert(0, str(DAY4))

import ollama_client  # noqa: E402
import sandbox  # noqa: E402
import task_agent  # noqa: E402

TYPE_PROFILE = {"bug": "bug-fix.md", "feature": "tester.md", "refactor": None, "test": "tester.md", "docs": "docs-sync.md"}

EXTRA_TOOLS = [
    {"type": "function", "function": {"name": "run_tests", "description": "Запустить ruff и все тесты проекта (./run_tests.sh)",
     "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {"name": "commit", "description": "Закоммитить все изменения одним коммитом; сообщение вида 'Txx: кратко'",
     "parameters": {"type": "object", "properties": {"message": {"type": "string"}}, "required": ["message"]}}},
]


def parse_tasks(text: str) -> list[dict]:
    tasks = []
    for m in re.finditer(r"^## (T\d{2}) \[(\w+)\] (.+?)\n(.*?)(?=^## T\d{2} |\Z)", text, re.S | re.M):
        tasks.append({"id": m.group(1), "type": m.group(2), "title": m.group(3), "body": m.group(4).strip(),
                      "text": f"{m.group(1)} [{m.group(2)}] {m.group(3)}\n{m.group(4).strip()}"})
    return tasks


def profile_text(proj: Path, ttype: str) -> str:
    name = TYPE_PROFILE.get(ttype)
    if not name:
        return "Профиль Refactor: меняй структуру кода, не меняя поведение; все тесты должны остаться зелёными."
    body = (proj / ".claude" / "agents" / name).read_text()
    body = re.sub(r"^---.*?---\s*", "", body, flags=re.S)
    return body[:2500]


def run_task(proj: Path, model: str, options: dict, task: dict, py: str, ruff: str, max_steps: int, timeout: int,
             protocol: str = "v1") -> dict:
    rules = (DAY4 / "rules_local.md").read_text()
    system = (f"Ты — ассистент в режиме execution loop (автономно, без вопросов). Рабочий каталог — проект.\n\n"
              f"{profile_text(proj, task['type'])}\n\nПравила проекта:\n{rules}\n\n"
              "ПОРЯДОК: прочитай нужные файлы (list_files/read_file/grep) → внеси изменения (replace_in_file/write_file) → "
              "запусти run_tests (ruff + все тесты должны быть зелёными) → вызови commit с сообщением 'Txx: кратко'. "
              "Закончи ответом одной строкой, когда закоммитил. Пока не закоммитил — вызывай инструменты, а не описывай шаги.")
    if protocol == "v2":
        system += (
            "\n\nЖЁСТКИЕ ПРАВИЛА ЦИКЛА (v2):\n"
            "1. СНАЧАЛА убедись, что критерий задачи ЕЩЁ НЕ выполнен: напиши короткий проверочный код и запусти его через run_python(code=…). "
            "Зелёные существующие тесты НЕ означают, что задача решена — они не знают про новую задачу.\n"
            "2. Задача выполнена только если ты ИЗМЕНИЛ файлы (replace_in_file/write_file). Не изменил ничего — значит НЕ сделал; "
            "никогда не пиши «уже решено» без проверки кода из шага 1.\n"
            "3. После правки снова запусти свою проверку из шага 1 (она должна пройти), затем run_tests (должен быть зелёным).\n"
            "4. Только после этого commit. commit без правок или с красными тестами будет отклонён.\n"
            "5. replace_in_file: old копируй ТОЧНО из read_file. Для новых файлов — write_file с полным содержимым.\n"
            "Образец для [bug]: grep → read_file → run_python(code=воспроизведение) → replace_in_file → run_python(code=повтор) → run_tests → commit.")
    messages = [{"role": "system", "content": system}, {"role": "user", "content": task["text"]}]
    tools = task_agent.TOOLS + EXTRA_TOOLS
    t0 = time.perf_counter()
    steps, committed, seen, err, final = 0, False, {}, "", ""
    tool_calls = 0
    trace: list[str] = []
    edited = False
    green_since_edit = False
    for steps in range(1, max_steps + 1):  # noqa: B007
        if time.perf_counter() - t0 > timeout:
            err = "timeout"
            break
        try:
            resp = ollama_client.chat(model, messages, options, tools=tools)
        except Exception as e:  # noqa: BLE001
            err = f"{type(e).__name__}: {e}"
            break
        msg = resp["message"]
        messages.append(msg)
        tcs = msg.get("tool_calls") or task_agent.extract_text_calls(msg.get("content", ""))
        if not tcs:
            final = msg.get("content", "")
            if committed:
                break
            messages.append({"role": "user", "content": "Ты ещё не закоммитил. Вызови инструменты: run_tests, затем commit."})
            continue
        for tc in tcs:
            fn = tc["function"]
            args = task_agent.normalize_args(fn["name"], fn.get("arguments") or {}) if fn["name"] in {
                t["function"]["name"] for t in task_agent.TOOLS} else (fn.get("arguments") or {})
            key = (fn["name"], json.dumps(args, sort_keys=True, ensure_ascii=False, default=str))
            seen[key] = seen.get(key, 0) + 1
            tool_calls += 1
            trace.append(f"{fn['name']}({json.dumps(args, ensure_ascii=False, default=str)[:90]})")
            if fn["name"] == "run_tests":
                p = subprocess.run(["./run_tests.sh"], cwd=proj, capture_output=True, text=True, timeout=240,  # noqa: S603
                                   env={"PYTHON": py, "RUFF": ruff, "PATH": "/usr/bin:/bin"})
                result = f"exit={p.returncode}\n{(p.stdout + p.stderr)[-2500:]}"
                green_since_edit = p.returncode == 0
            elif fn["name"] == "commit" and protocol == "v2" and not edited:
                result = ("ОТКЛОНЕНО: нечего коммитить — ты не изменил ни одного файла, значит задача НЕ выполнена. "
                          "Внеси изменения (replace_in_file/write_file), проверь критерий из шага 1.")
            elif fn["name"] == "commit" and protocol == "v2" and not green_since_edit:
                result = "ОТКЛОНЕНО: после последней правки run_tests не был зелёным. Запусти run_tests и исправь ошибки."
            elif fn["name"] == "commit":
                subprocess.run(["git", "add", "-A"], cwd=proj, check=True)  # noqa: S603, S607
                p = subprocess.run(["git", "-c", "user.email=local@x", "-c", "user.name=local", "commit", "-qm",  # noqa: S603, S607
                                    str(args.get("message") or task["id"])], cwd=proj, capture_output=True, text=True)
                committed = p.returncode == 0
                result = "committed" if committed else f"commit не удался: {p.stdout}{p.stderr}"[:300]
            else:
                result = task_agent.call_tool(proj, fn["name"], args)
                if fn["name"] in ("replace_in_file", "write_file") and result.startswith("ok"):
                    edited, green_since_edit = True, False
            if seen[key] >= 3:
                result += "\n[ПОДСКАЗКА: этот вызов уже был 3 раза — смени шаг.]"
            messages.append({"role": "tool", "content": result[:3000], "tool_name": fn["name"]})
    reverted = ""
    if protocol == "v2":   # шлюз цикла: задача засчитана только при зелёных тестах, иначе откат к последнему хорошему состоянию
        g = subprocess.run(["./run_tests.sh"], cwd=proj, capture_output=True, text=True, timeout=240,  # noqa: S603
                           env={"PYTHON": py, "RUFF": ruff, "PATH": "/usr/bin:/bin"})
        if g.returncode != 0:
            if committed:
                subprocess.run(["git", "reset", "-q", "--hard", "HEAD~1"], cwd=proj, check=True)  # noqa: S603, S607
                reverted = "коммит откатан (тесты красные)"
            else:
                subprocess.run(["git", "checkout", "-q", "--", "."], cwd=proj, check=True)  # noqa: S603, S607
                subprocess.run(["git", "clean", "-qfd"], cwd=proj, check=True)  # noqa: S603, S607
                reverted = "изменения отброшены"
            committed = False
        elif not committed:
            subprocess.run(["git", "checkout", "-q", "--", "."], cwd=proj, check=True)  # noqa: S603, S607
            subprocess.run(["git", "clean", "-qfd"], cwd=proj, check=True)  # noqa: S603, S607
            reverted = "не закоммичено — изменения отброшены"
    return {"task": task["id"], "reverted": reverted, "steps": steps, "tool_calls": tool_calls, "committed": committed, "error": err,
            "wall_s": round(time.perf_counter() - t0, 1), "final": final[:200], "trace": trace}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("sandbox")
    ap.add_argument("model")
    ap.add_argument("--python", required=True)
    ap.add_argument("--ruff", required=True)
    ap.add_argument("--tasks", default="")
    ap.add_argument("--max-steps", type=int, default=20)
    ap.add_argument("--task-timeout", type=int, default=600)
    ap.add_argument("--protocol", default="v1", choices=["v1", "v2"])
    ap.add_argument("--stop-after-fails", type=int, default=0, help="0 — не останавливаться")
    a = ap.parse_args()
    proj = Path(a.sandbox)
    sandbox.PYTHON, sandbox.RUFF = a.python, a.ruff
    options = {"temperature": 0.2, "top_p": 0.9, "num_ctx": 16384, "num_predict": 3072}
    tasks = parse_tasks((proj / "TASKS.md").read_text())
    if a.tasks:
        tasks = [t for t in tasks if t["id"] in a.tasks.split(",")]
    log, fails = [], 0
    for t in tasks:
        r = run_task(proj, a.model, options, t, a.python, a.ruff, a.max_steps, a.task_timeout, a.protocol)
        log.append(r)
        sys.stdout.write(json.dumps(r, ensure_ascii=False) + "\n")
        sys.stdout.flush()
        (proj.parent / f"{proj.name}_local_log.json").write_text(json.dumps(log, ensure_ascii=False, indent=1))
        fails = 0 if r["committed"] else fails + 1
        if a.stop_after_fails and fails >= a.stop_after_fails:
            break


if __name__ == "__main__":
    main()
