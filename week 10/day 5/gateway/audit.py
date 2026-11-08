"""
Аудит-журнал шлюза: каждое решение (пропущен, замаскирован, заблокирован, лимит) пишется в JSONL.

Роль в сервисе: след для расследований. В журнал не попадают сами секреты: только типы находок,
длины, солёные отпечатки (HMAC) и укороченные превью; для замаскированных запросов — текст уже после
маскирования. Заблокированные запросы пишутся без тела. Модуль чистый: без Flask и сети.
"""

import json
import time
from pathlib import Path

LOG_DIR = Path(__file__).parent / "logs"
AUDIT_FILE = "audit.jsonl"
SECRETS_FILE = "secrets_intercepted.jsonl"


def write(entry: dict, log_dir: Path | None = None) -> None:
    """Дописать запись в audit.jsonl; перехваты секретов дублируются в secrets_intercepted.jsonl."""
    directory = log_dir or LOG_DIR
    directory.mkdir(parents=True, exist_ok=True)
    record = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), **entry}
    line = json.dumps(record, ensure_ascii=False) + "\n"
    with (directory / AUDIT_FILE).open("a", encoding="utf-8") as f:
        f.write(line)
    if entry.get("input_findings") or entry.get("output_findings"):
        with (directory / SECRETS_FILE).open("a", encoding="utf-8") as f:
            f.write(line)


def tail(last: int = 15, log_dir: Path | None = None) -> list[dict]:
    """Последние `last` записей журнала (новые в конце)."""
    path = (log_dir or LOG_DIR) / AUDIT_FILE
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()[-last:]
    return [json.loads(line) for line in lines]
