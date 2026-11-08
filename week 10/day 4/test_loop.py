"""Проверка execution loop с security step (без сети и без модели: шлюз подменяется функцией)."""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import codegen
import gateway_client
import report
import review
import sandbox
import security_prompt
import tasks
from loop import run_task

PY = sys.executable
GOOD_SOL = "def add(a, b):\n    return a + b\n"
GOOD_TEST = 'from solution import add\n\n\ndef main() -> None:\n    assert add(1, 2) == 3\n    print("ok")\n\n\nif __name__ == "__main__":\n    main()\n'
BAD_TEST = GOOD_TEST.replace("== 3", "== 4")
TOKEN_SOL = GOOD_SOL + '\n\ndef save_token(t):\n    open("token.txt", "w").write(t)\n'
TASK = tasks.Task("T9", "тестовая задача", "Сделай add(a, b).")


def files_reply(sol: str, test: str) -> str:
    return f"=== FILE: solution.py ===\n{sol}=== END ===\n=== FILE: test_solution.py ===\n{test}=== END ==="


def ok(content: str, **kw) -> gateway_client.Reply:
    return gateway_client.Reply(True, content=content, input_action=kw.pop("input_action", "masked"),
                                input_findings=kw.pop("input_findings", [{"kind": "api_key", "label": "REDACTED_API_KEY",
                                                                          "length": 35, "fingerprint": "ab12", "message_index": 0}]),
                                output_action=kw.pop("output_action", "allowed"), prompt_tokens=100, completion_tokens=50, cost_usd=0.001, **kw)


def review_json(*items: tuple[str, int, str]) -> str:
    return json.dumps({"findings": [{"severity": s, "line": ln, "title": t, "fix": "см. замечание"} for s, ln, t in items]})


def run(replies: list[gateway_client.Reply], max_iter: int = 3) -> tuple[dict, list[list[dict]], Path, str]:
    """Прогнать задачу с заранее заданными ответами шлюза; вернуть итог, запросы, лог и git log."""
    queue = list(replies)
    seen: list[list[dict]] = []
    thinking_flags: list[bool] = []
    run.thinking_flags = thinking_flags  # type: ignore[attr-defined]

    def ask_fn(messages: list[dict], thinking: bool = True) -> gateway_client.Reply:
        seen.append(messages)
        thinking_flags.append(thinking)
        return queue.pop(0)

    tmp = Path(tempfile.mkdtemp())
    root = sandbox.make_sandbox(tmp / "repo")
    log = tmp / "events.jsonl"
    result = run_task(TASK, root, ask_fn, PY, None, log, max_iter)
    history = subprocess.run(["git", "log", "--format=%s"], cwd=root, capture_output=True, text=True, check=True).stdout  # noqa: S603, S607
    return result, seen, log, history


def main() -> None:
    # --- чистый путь
    result, seen, log, history = run([ok(files_reply(GOOD_SOL, GOOD_TEST)), ok(review_json())])
    assert result["outcome"] == "committed" and result["iterations"] == 1 and "T9: тестовая задача" in history
    assert [m[0]["role"] for m in seen] == ["user", "system"], "ревью идёт вторым вызовом со своим security-промптом"
    print("✅ чисто: генерация → тесты → ревью → коммит, ревью — отдельный вызов с security-промптом")

    # --- High → возврат на генерацию с фидбеком «исправь: …»
    result, seen, log, history = run([
        ok(files_reply(TOKEN_SOL, GOOD_TEST)), ok(review_json(("High", 2, "токен хранится в открытом файле"))),
        ok(files_reply(GOOD_SOL, GOOD_TEST)), ok(review_json()),
    ])
    assert result["outcome"] == "committed" and result["iterations"] == 2 and len(result["reviews"]) == 2
    assert "исправь: токен хранится в открытом файле в строке 2 (High)" in seen[2][0]["content"]
    assert result["reviews"][0]["decision"] == "fix" and result["reviews"][1]["decision"] == "clean"
    print("✅ High: цикл вернулся на генерацию с «исправь: … в строке 2», вторая версия принята")

    # --- Medium/Low: коммит с предупреждением
    result, seen, log, history = run([ok(files_reply(GOOD_SOL, GOOD_TEST)),
                                      ok(review_json(("Medium", 1, "нет таймаута"), ("Low", 1, "стиль")))])
    events = [json.loads(line) for line in log.read_text().splitlines()]
    assert result["outcome"] == "committed" and len(result["warnings"]) == 2
    assert any(e["event"] == "warning" for e in events) and "T9" in history
    print("✅ Medium/Low: коммит выполнен, предупреждение записано в лог")

    # --- тесты упали → фидбек с выводом тестов
    result, seen, log, history = run([ok(files_reply(GOOD_SOL, BAD_TEST)), ok(files_reply(GOOD_SOL, GOOD_TEST)), ok(review_json())])
    assert result["outcome"] == "committed" and result["iterations"] == 2
    assert "Проверка «tests» не прошла" in seen[1][0]["content"] and "AssertionError" in seen[1][0]["content"]
    print("✅ тесты упали: вывод тестов вернулся в генерацию, следующая итерация зелёная")

    # --- output guard заблокировал ответ → перегенерация
    blocked = ok("[Ответ заблокирован output guard: IP-адрес вместо домена]", output_action="blocked")
    result, seen, log, history = run([blocked, ok(files_reply(GOOD_SOL, GOOD_TEST)), ok(review_json())])
    assert result["outcome"] == "committed" and "Ответ заблокирован шлюзом" in seen[1][0]["content"]
    print("✅ output guard: заблокированный ответ превращён в фидбек, генерация повторена")

    # --- input guard заблокировал запрос → стоп без коммита
    denied = gateway_client.Reply(False, error="Запрос заблокирован", input_action="blocked", input_findings=[{"kind": "api_key"}])
    result, seen, log, history = run([denied])
    assert result["outcome"] == "blocked_by_gateway" and "T9" not in history
    print("✅ input guard заблокировал запрос: цикл остановлен, коммита нет")

    # --- пустой ответ ревью (рассуждение съело лимит) → один повтор без рассуждения
    result, seen, log, history = run([ok(files_reply(GOOD_SOL, GOOD_TEST)), ok(""), ok(review_json())])
    assert result["outcome"] == "committed" and run.thinking_flags == [True, True, False]  # type: ignore[attr-defined]
    result, seen, log, history = run([ok(files_reply(GOOD_SOL, GOOD_TEST)), ok(""), ok("")])
    assert result["outcome"] == "review_failed" and "T9" not in history
    print("✅ пустое ревью: один повтор без рассуждения; второй пустой ответ — fail closed")

    # --- fail closed: ревью не разобрано
    result, seen, log, history = run([ok(files_reply(GOOD_SOL, GOOD_TEST)), ok("всё выглядит нормально, уязвимостей нет")])
    assert result["outcome"] == "review_failed" and "T9" not in history
    unavailable = gateway_client.Reply(False, error="шлюз недоступен")
    result, seen, log, history = run([ok(files_reply(GOOD_SOL, GOOD_TEST)), unavailable])
    assert result["outcome"] == "review_failed" and "T9" not in history
    print("✅ fail closed: ревью не разобрано или недоступно — коммита нет")

    # --- Critical не уходит: лимит итераций
    always = [ok(files_reply(TOKEN_SOL, GOOD_TEST)), ok(review_json(("Critical", 2, "секрет в коде")))] * 2
    result, seen, log, history = run(always, max_iter=2)
    assert result["outcome"] == "gave_up" and result["iterations"] == 2 and "T9" not in history
    print("✅ Critical не исправлен за лимит итераций: gave_up, коммита нет")

    # --- лог не содержит тела промптов и секретов
    text = log.read_text()
    assert sandbox.fake_api_key() not in text and "Файлы проекта" not in text
    events = [json.loads(line) for line in text.splitlines()]
    call = next(e for e in events if e["event"] == "call")
    assert call["input_action"] == "masked" and call["input_findings"][0]["kind"] == "api_key"
    print("✅ лог: решения шлюза записаны, тел промптов и секретов нет")

    # --- отчёт: утечка мимо шлюза определяется по его журналу
    with tempfile.TemporaryDirectory() as d:
        audit_file = Path(d) / "audit.jsonl"
        leaked = "S3cr3t-" + "Pa55w0rd!"
        audit_file.write_text(json.dumps({"prompt": [{"role": "user", "content": f"DB_PASSWORD = \"{leaked}\"; ключ [REDACTED_API_KEY]"}]}) + "\n")
        leaks = report.leak_check(audit_file)
        assert leaks["DB_PASSWORD (config.py)"] is True and leaks["API_KEY (config.py и задача T3)"] is False
        assert report.leak_check(Path(d) / "нет.jsonl")["DB_PASSWORD (config.py)"] is False
    assert report.in_code(f'PASSWORD = "{leaked}"') == ["DB_PASSWORD (config.py)"]
    print("✅ отчёт: пароль, прошедший мимо шлюза, находится по журналу шлюза и в итоговом коде")

    # --- разбор ревью и ответа генерации
    assert review.decide([]) == "clean"
    parsed = review.parse_review('Вот результат: ```json\n' + review_json(("high", 3, "SQL injection")) + '\n```')
    assert parsed[0].severity == "High" and review.decide(parsed) == "fix" and "исправь: SQL injection в строке 3" in review.feedback(parsed)
    for bad in ("нет json", '{"findings": 5}', review_json(("Fatal", 1, "x"))):
        try:
            review.parse_review(bad)
            raise AssertionError("ожидали ReviewParseError")
        except review.ReviewParseError:
            pass
    assert review.numbered("a\nb") == "  1| a\n  2| b"
    evil = files_reply(GOOD_SOL, GOOD_TEST) + "\n=== FILE: ../evil.py ===\nimport os\n=== END ==="
    assert set(codegen.parse_files(evil)) == {"solution.py", "test_solution.py"}
    try:
        codegen.parse_files("=== FILE: solution.py ===\nx = 1\n=== END ===")
        raise AssertionError("ожидали FormatError")
    except codegen.FormatError:
        pass
    print("✅ разбор: терпимый к тексту вокруг JSON, плохие ответы отклоняются, чужие имена файлов игнорируются")

    # --- security-промпты и задачи
    assert set(security_prompt.STACKS) == {"python", "ios", "android"}
    assert "Keychain" in security_prompt.build_prompt("ios") and "EncryptedSharedPreferences" in security_prompt.build_prompt("android")
    assert "Critical" in security_prompt.build_prompt() and "Authorization" in security_prompt.build_prompt("python")
    t3 = tasks.all_tasks()[2]
    assert sandbox.fake_api_key() in t3.text and len(tasks.all_tasks()) == 3
    print("✅ security-промпты: python, ios, android; три задачи, ключ в T3 — для проверки шлюза")

    print("\n✅ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ — execution loop с security step: High → назад, Medium/Low → предупреждение, fail closed")


if __name__ == "__main__":
    main()
