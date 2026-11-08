"""
Input Guard: поиск и маскирование секретов и персональных данных во входящем промпте.

Роль в сервисе: первый слой LLM-шлюза. Ищет API-ключи (sk-, ghp_, AKIA, xoxb-, JWT, приватные ключи),
email, номера карт (с проверкой Луна), телефоны, пары «password: …» и секреты, спрятанные кодированием
base64 или разбитые на части (`"sk-" + "proj-abc"`, соседние сообщения). Режим `block` отклоняет
запрос, `mask` заменяет находки метками `[REDACTED_…]`. В находках никогда не хранится сам секрет:
только тип, длина, короткий солёный отпечаток (HMAC-SHA256) и укороченный превью. Модуль чистый: без Flask и сети.
"""

import base64
import binascii
import hmac
import re
import secrets
import unicodedata
from dataclasses import dataclass

# (тип, метка, регулярка, номер группы со значением)
_PATTERNS: list[tuple[str, str, re.Pattern[str], int]] = [
    ("private_key", "REDACTED_PRIVATE_KEY", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), 0),
    ("api_key", "REDACTED_API_KEY", re.compile(r"\bsk-[A-Za-z0-9_\-]{6,}"), 0),
    ("api_key", "REDACTED_API_KEY", re.compile(r"\b[sr]k_(?:live|test)_[A-Za-z0-9]{10,}"), 0),
    ("github_token", "REDACTED_GITHUB_TOKEN", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})"), 0),
    ("aws_key", "REDACTED_AWS_KEY", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"), 0),
    ("aws_secret", "REDACTED_AWS_SECRET", re.compile(r"(?i)(?:aws_secret_access_key|secret_access_key)\W{0,3}([A-Za-z0-9/+=]{40})\b"), 1),
    ("slack_token", "REDACTED_SLACK_TOKEN", re.compile(r"\bxox[abprs]-[A-Za-z0-9\-]{10,}"), 0),
    ("jwt", "REDACTED_JWT", re.compile(r"\beyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}"), 0),
    # значение в кавычках — секрет целиком; без кавычек — до разделителя (иначе в коде `{"token": token}, f)` захватывается хвост)
    ("secret_assignment", "REDACTED_SECRET",
     re.compile(r"(?i)(?<![A-Za-z])(?:password|passwd|pwd|пароль|secret|api[_-]?key|token)\w*[\"\']?\s*[:=]\s*[\"\']([^\"\'\s]{6,})[\"\']"), 1),
    ("secret_assignment", "REDACTED_SECRET",
     re.compile(r"(?i)(?<![A-Za-z])(?:password|passwd|pwd|пароль|secret|api[_-]?key|token)\w*[\"\']?\s*[:=]\s*([^\s\"\',;)\]}]{6,})"), 1),
    ("email", "REDACTED_EMAIL", re.compile(r"\b[\w.+\-]+@[\w\-]+(?:\.[\w\-]+)+\b"), 0),
    ("card", "REDACTED_CARD", re.compile(r"(?<![\w\-])(?:\d[ \-]?){12,18}\d(?![\w\-])"), 0),
    ("phone", "REDACTED_PHONE", re.compile(r"(?<!\w)(?:\+7|8|7)[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}(?!\d)"), 0),
    ("phone", "REDACTED_PHONE", re.compile(r"(?<!\w)\+\d{1,3}[\s\-]?\(?\d{2,4}\)?[\s\-]?\d{3,4}[\s\-]?\d{3,4}(?!\d)"), 0),
]
_BASE64 = re.compile(r"(?<![A-Za-z0-9+/=])[A-Za-z0-9+/]{24,}={0,2}(?![A-Za-z0-9+/=])")
_CONCAT = re.compile(r"[\"'`]\s*\+\s*[\"'`]")
_ZERO_WIDTH = re.compile("[​-‏⁠﻿­]")
_MAX_ENCODING_DEPTH = 2
_SALT = secrets.token_bytes(16)  # соль отпечатков: живёт только в памяти процесса и нигде не пишется
_CODE_REFERENCE = re.compile(r"[A-Za-z_][\w.\[\]]*(?:\(.*)?|\d+")  # идентификатор, вызов или число — не секрет, если без кавычек
_PII_KINDS = frozenset({"email", "phone", "card"})  # при пересечении уступают более специфичным секретам


@dataclass(frozen=True)
class Finding:
    """Одна находка. Сам секрет не хранится: только тип, длина, отпечаток и превью."""

    kind: str
    label: str
    start: int
    end: int
    length: int
    fingerprint: str
    preview: str
    via: str = "direct"  # direct | base64

    def public(self, message_index: int | None = None) -> dict:
        """Безопасное для логов и ответа представление находки."""
        data = {
            "kind": self.kind, "label": self.label, "length": self.length,
            "fingerprint": self.fingerprint, "preview": self.preview, "via": self.via,
        }
        if message_index is not None:
            data["message_index"] = message_index
        return data


@dataclass(frozen=True)
class GuardResult:
    """Итог проверки сообщений: действие, (возможно замаскированные) сообщения и находки."""

    action: str  # allowed | masked | blocked
    messages: list[dict]
    findings: list[dict]
    reason: str = ""


def normalize(text: str) -> str:
    """Нормализация: NFKC (полноширинные символы), zero-width, конкатенацию строковых литералов."""
    text = unicodedata.normalize("NFKC", text)
    text = _ZERO_WIDTH.sub("", text)
    return _CONCAT.sub("", text)


def luhn_valid(digits: str) -> bool:
    """Проверка контрольной суммы номера карты по алгоритму Луна."""
    if not 13 <= len(digits) <= 19 or not digits.isdigit():
        return False
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2 == 1:
            d = d * 2 - 9 if d > 4 else d * 2
        total += d
    return total % 10 == 0


def _describe(value: str) -> tuple[str, str]:
    """Отпечаток (HMAC-SHA256 с солью процесса, не подбирается перебором) и безопасное превью значения."""
    fingerprint = hmac.new(_SALT, value.encode(), "sha256").hexdigest()[:8]
    preview = f"{value[:3]}…(len {len(value)})" if len(value) >= 16 else f"…(len {len(value)})"
    return fingerprint, preview


def _find_direct(text: str) -> list[Finding]:
    """Найти секреты прямо в тексте по регулярным выражениям."""
    found: list[Finding] = []
    for kind, label, pattern, group in _PATTERNS:
        for m in pattern.finditer(text):
            value = m.group(group)
            if not value:
                continue
            if kind == "card" and not luhn_valid(re.sub(r"\D", "", value)):
                continue
            quoted = m.start(group) > 0 and text[m.start(group) - 1] in "\"'"
            if kind == "secret_assignment" and not quoted and _CODE_REFERENCE.fullmatch(value):
                continue  # `token = get_token()`, `password = request.args`: код, а не секрет
            fingerprint, preview = _describe(value)
            found.append(Finding(kind, label, m.start(group), m.end(group), len(value), fingerprint, preview))
    return found


def _find_encoded(text: str, depth: int) -> list[Finding]:
    """Найти base64-блоки, внутри которых после декодирования лежит секрет."""
    found: list[Finding] = []
    if depth >= _MAX_ENCODING_DEPTH:
        return found
    for m in _BASE64.finditer(text):
        token = m.group(0)
        try:
            decoded = base64.b64decode(token + "=" * (-len(token) % 4), validate=True).decode("utf-8")
        except (binascii.Error, UnicodeDecodeError, ValueError):
            continue
        if not decoded.isprintable() and "\n" not in decoded:
            continue
        inner = _find_direct(normalize(decoded)) or _find_encoded(decoded, depth + 1)
        if inner:
            fingerprint, preview = _describe(token)
            found.append(Finding("encoded_secret", "REDACTED_ENCODED_SECRET", m.start(), m.end(),
                                 len(token), fingerprint, preview, via="base64"))
    return found


def inspect(text: str) -> tuple[str, list[Finding]]:
    """Нормализовать текст и найти секреты; вернуть (нормализованный текст, находки без пересечений).

    Позиции находок относятся к нормализованному тексту.
    """
    norm = normalize(text)
    candidates = _find_direct(norm) + _find_encoded(norm, 0)
    candidates.sort(key=lambda f: (f.start, f.kind in _PII_KINDS, -(f.end - f.start)))
    result: list[Finding] = []
    last_end = -1
    for f in candidates:
        if f.start >= last_end:
            result.append(f)
            last_end = f.end
    return norm, result


def mask(norm_text: str, findings: list[Finding]) -> str:
    """Заменить находки метками [REDACTED_…] в нормализованном тексте."""
    out: list[str] = []
    pos = 0
    for f in findings:
        out.append(norm_text[pos:f.start])
        out.append(f"[{f.label}]")
        pos = f.end
    out.append(norm_text[pos:])
    return "".join(out)


def guard_messages(messages: list[dict], mode: str = "block") -> GuardResult:
    """Проверить сообщения чата: заблокировать или замаскировать секреты (mode: block | mask)."""
    all_findings: list[dict] = []
    new_messages: list[dict] = []
    seen: set[str] = set()
    for i, msg in enumerate(messages):
        norm, found = inspect(str(msg.get("content") or ""))
        if found:
            all_findings += [f.public(i) for f in found]
            seen.update(f.fingerprint for f in found)
            new_messages.append({**msg, "content": mask(norm, found)})
        else:
            new_messages.append(msg)

    # секрет, разбитый на части между соседними сообщениями: ищем в склейке всех содержимых
    joined = "".join(str(m.get("content") or "") for m in messages)
    _, joined_found = inspect(joined)
    split = [f for f in joined_found if f.fingerprint not in seen]
    if split:
        all_findings += [{**f.public(), "via": "split_across_messages"} for f in split]

    if not all_findings:
        return GuardResult("allowed", messages, [])
    if mode == "block" or split:
        reason = (
            "секрет разбит на части между сообщениями, замаскировать нельзя" if split and mode == "mask"
            else "во входящем промпте найдены секреты или персональные данные"
        )
        return GuardResult("blocked", messages, all_findings, reason)
    return GuardResult("masked", new_messages, all_findings, "секреты заменены метками")
