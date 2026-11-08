"""
Разбор ответа security review и политика решения: что делать с найденным.

Роль в цикле: превращает ответ модели в список находок и решает судьбу кода.
Critical/High → вернуть на генерацию с фидбеком «исправь: …»; только Medium/Low → пропустить
с предупреждением в логе; пусто → можно коммитить. Модуль чистый: без сети.
"""

import json
from dataclasses import dataclass

SEVERITIES = ("Critical", "High", "Medium", "Low")
BLOCKING = frozenset({"Critical", "High"})


class ReviewParseError(Exception):
    """Ответ ревью нельзя разобрать как JSON со списком находок."""


@dataclass(frozen=True)
class Finding:
    """Одна находка security review."""

    severity: str
    line: int
    title: str
    fix: str

    def as_dict(self) -> dict:
        return {"severity": self.severity, "line": self.line, "title": self.title, "fix": self.fix}


def parse_review(text: str) -> list[Finding]:
    """Достать список находок из ответа модели (терпимо к тексту вокруг JSON)."""
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ReviewParseError("в ответе ревью нет JSON-объекта")
    try:
        data = json.loads(text[start:end + 1])
    except json.JSONDecodeError as e:
        raise ReviewParseError(f"JSON ревью не разбирается: {e.msg}") from e
    items = data.get("findings") if isinstance(data, dict) else None
    if not isinstance(items, list):
        raise ReviewParseError('нет списка "findings"')
    findings: list[Finding] = []
    for item in items:
        if not isinstance(item, dict):
            raise ReviewParseError("элемент findings не объект")
        severity = str(item.get("severity", "")).strip().capitalize()
        if severity not in SEVERITIES:
            raise ReviewParseError(f"неизвестная серьёзность: {item.get('severity')!r}")
        try:
            line = int(item.get("line") or 0)
        except (TypeError, ValueError):
            line = 0
        findings.append(Finding(severity, line, str(item.get("title", "")).strip(), str(item.get("fix", "")).strip()))
    return findings


def decide(findings: list[Finding]) -> str:
    """Решение по находкам: `fix` (есть Critical/High), `warn` (только Medium/Low), `clean` (пусто)."""
    if any(f.severity in BLOCKING for f in findings):
        return "fix"
    return "warn" if findings else "clean"


def feedback(findings: list[Finding]) -> str:
    """Текст фидбека для генерации: по одной строке «исправь: …» на каждую блокирующую находку."""
    lines = []
    for f in findings:
        if f.severity in BLOCKING:
            where = f"в строке {f.line}" if f.line else "в коде"
            lines.append(f"исправь: {f.title} {where} ({f.severity}). Как: {f.fix}")
    return "\n".join(lines)


def numbered(code: str) -> str:
    """Пронумеровать строки кода для ревью (`  7| текст`)."""
    return "\n".join(f"{i:3d}| {line}" for i, line in enumerate(code.splitlines(), start=1))
