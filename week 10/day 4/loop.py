"""
Execution loop с security step: промпт → генерация → линтер/тесты → security review → коммит.

Роль: цикл на одну задачу, все вызовы LLM (и генерация, и ревью) идут через LLM-шлюз (day 3).
Решение после ревью: Critical/High → назад на генерацию с фидбеком «исправь: …»; только Medium/Low →
коммит с предупреждением в логе; чисто → коммит. Ревью недоступно или не разобрано → коммита нет (fail closed).
Каждый вызов шлюза пишется в events.jsonl: решение шлюза по входу и выходу (без секретов), токены, стоимость.
Запуск: python loop.py [--tasks T1,T2] [--python PY] [--ruff RUFF] [--gateway-url URL] [--max-iter 3]
"""

import argparse
import functools
import json
import shutil
import sys
import tempfile
import time
from collections.abc import Callable
from pathlib import Path

import codegen
import gateway_client
import report
import review
import sandbox
import security_prompt
import tasks

RUNS_DIR = Path(__file__).parent / "runs"
AskFn = Callable[..., gateway_client.Reply]  # ask(messages, thinking=True)


def log_event(path: Path, event: dict) -> None:
    """Дописать событие в JSONL-лог прогона."""
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": time.strftime("%H:%M:%S"), **event}, ensure_ascii=False) + "\n")


def call(ask_fn: AskFn, messages: list[dict], *, task_id: str, iteration: int, stage: str, log_path: Path,
         thinking: bool = True) -> gateway_client.Reply:
    """Вызов LLM через шлюз с записью решения шлюза в лог (тело промпта в лог не пишется)."""
    started = time.monotonic()
    reply = ask_fn(messages, thinking=thinking)
    log_event(log_path, {
        "event": "call", "task": task_id, "iteration": iteration, "stage": stage, "thinking": thinking, "ok": reply.ok,
        "request_id": reply.request_id, "input_action": reply.input_action,
        "input_findings": [{k: f[k] for k in ("kind", "label", "length", "fingerprint", "message_index") if k in f}
                           for f in reply.input_findings],
        "output_action": reply.output_action,
        "output_findings": [{k: f.get(k) for k in ("kind", "reasons") if k in f} for f in reply.output_findings],
        "prompt_tokens": reply.prompt_tokens, "completion_tokens": reply.completion_tokens, "cost_usd": reply.cost_usd,
        "seconds": round(time.monotonic() - started, 1), "error": reply.error,
    })
    return reply


def run_task(task: tasks.Task, root: Path, ask_fn: AskFn, python: str, ruff: str | None, log_path: Path,
             max_iter: int = 3, stack: str = "python") -> dict:
    """Выполнить цикл для одной задачи; вернуть итог (outcome: committed | gave_up | blocked_by_gateway | gateway_error | review_failed)."""
    system_prompt = security_prompt.build_prompt(stack)
    result: dict = {"task": task.id, "title": task.title, "outcome": "gave_up", "iterations": 0,
                    "reviews": [], "warnings": [], "commit": None}
    previous: dict[str, str] | None = None
    feedback: str | None = None
    for i in range(1, max_iter + 1):
        result["iterations"] = i
        prompt = codegen.build_prompt(task.text, sandbox.context_files(root), previous, feedback)
        reply = call(ask_fn, [{"role": "user", "content": prompt}], task_id=task.id, iteration=i, stage="generate", log_path=log_path)
        if not reply.ok:
            result["outcome"] = "blocked_by_gateway" if reply.input_action == "blocked" else "gateway_error"
            result["error"] = reply.error
            break
        if reply.output_action == "blocked":
            feedback = f"Ответ заблокирован шлюзом (output guard): {reply.content}"
            continue
        try:
            files = codegen.parse_files(reply.content)
        except codegen.FormatError as e:
            feedback = f"Неверный формат ответа: {e}"
            log_event(log_path, {"event": "format_error", "task": task.id, "iteration": i, "error": str(e)})
            continue
        sandbox.write_solution(root, files)
        previous = files
        checks = sandbox.run_checks(root, python, ruff)
        log_event(log_path, {"event": "checks", "task": task.id, "iteration": i, "ok": checks.ok, "stage": checks.stage,
                             "output": checks.output[-600:]})
        if not checks.ok:
            feedback = f"Проверка «{checks.stage}» не прошла:\n{checks.output[-1500:]}"
            continue

        review_messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "Проведи security review файла solution.py:\n\n" + review.numbered(files[sandbox.SOLUTION])},
        ]
        rep = call(ask_fn, review_messages, task_id=task.id, iteration=i, stage="security_review", log_path=log_path)
        if rep.ok and not rep.content.strip():
            # рассуждение съело весь лимит токенов: повторяем один раз без рассуждения (короткий JSON-ответ)
            log_event(log_path, {"event": "review_retry_no_thinking", "task": task.id, "iteration": i})
            rep = call(ask_fn, review_messages, task_id=task.id, iteration=i, stage="security_review", log_path=log_path,
                       thinking=False)
        if not rep.ok or rep.output_action == "blocked":
            result["outcome"], result["error"] = "review_failed", rep.error or rep.content
            break
        try:
            findings = review.parse_review(rep.content)
        except review.ReviewParseError as e:
            result["outcome"], result["error"] = "review_failed", str(e)
            log_event(log_path, {"event": "review_parse_error", "task": task.id, "iteration": i, "error": str(e)})
            break
        decision = review.decide(findings)
        result["reviews"].append({"iteration": i, "decision": decision, "findings": [f.as_dict() for f in findings]})
        log_event(log_path, {"event": "review", "task": task.id, "iteration": i, "decision": decision,
                             "findings": [f.as_dict() for f in findings]})
        if decision == "fix":
            feedback = review.feedback(findings)
            continue
        if decision == "warn":
            result["warnings"] = [f.as_dict() for f in findings]
            log_event(log_path, {"event": "warning", "task": task.id, "findings": result["warnings"]})
        result["commit"] = sandbox.commit(root, f"{task.id}: {task.title}")
        result["outcome"] = "committed"
        log_event(log_path, {"event": "commit", "task": task.id, "sha": result["commit"], "warnings": len(result["warnings"])})
        break
    final = root / sandbox.SOLUTION
    code = final.read_text(encoding="utf-8") if final.exists() else ""
    if result["outcome"] == "committed":
        result["secrets_in_code"] = report.in_code(code)
        result["independent_scan"] = sandbox.independent_scan(root, ruff)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tasks", default="", help="id задач через запятую (по умолчанию все)")
    parser.add_argument("--python", default=sys.executable, help="python 3.13 для запуска тестов")
    parser.add_argument("--ruff", default=None, help="путь к ruff (если не задан, линт пропускается)")
    parser.add_argument("--gateway-url", default=gateway_client.DEFAULT_URL)
    parser.add_argument("--gateway-audit", default=str(RUNS_DIR / "gateway" / "audit.jsonl"), help="журнал шлюза (для проверки утечек)")
    parser.add_argument("--max-iter", type=int, default=3)
    parser.add_argument("--stack", default="python", choices=sorted(security_prompt.STACKS))
    args = parser.parse_args()

    wanted = {t for t in args.tasks.split(",") if t}
    selected = [t for t in tasks.all_tasks() if not wanted or t.id in wanted]
    run_dir = RUNS_DIR / time.strftime("%Y%m%d-%H%M%S")
    run_dir.mkdir(parents=True)
    log_path = run_dir / "events.jsonl"
    results: list[dict] = []
    with tempfile.TemporaryDirectory() as tmp:
        for task in selected:
            root = sandbox.make_sandbox(Path(tmp) / task.id)
            ask_fn: AskFn = functools.partial(gateway_client.ask, url=args.gateway_url)
            result = run_task(task, root, ask_fn, args.python, args.ruff, log_path, args.max_iter, args.stack)
            results.append(result)
            out = run_dir / task.id
            out.mkdir()
            for name in (sandbox.SOLUTION, sandbox.TESTS):
                if (root / name).exists():
                    shutil.copy(root / name, out / name)
            print(f"{task.id} {task.title}: {result['outcome']} за {result['iterations']} итераций")  # noqa: T201
    events = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    leaks = report.leak_check(Path(args.gateway_audit))
    (run_dir / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    (run_dir / "report.md").write_text(report.render(results, events, leaks), encoding="utf-8")
    print(f"Отчёт: {run_dir / 'report.md'}")  # noqa: T201


if __name__ == "__main__":
    main()
