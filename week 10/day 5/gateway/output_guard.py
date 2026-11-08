"""
Output Guard: проверка ответа модели перед отдачей пользователю.

Роль в сервисе: второй слой LLM-шлюза. Ловит (1) секреты в ответе (модель может выдать правдоподобный
ключ или повторить увиденный), (2) утечку системного промпта шлюза (совпадение n-грамм слов),
(3) подозрительные URL (IP вместо домена, punycode, сократители, http, userinfo, длинный query,
внешние markdown-картинки) и (4) опасные команды (curl | sh, rm -rf /, fork-бомба и т.п.).
Секреты маскируются, остальное блокирует ответ. Модуль чистый: без Flask и сети.
"""

import ipaddress
import re
from dataclasses import dataclass
from urllib.parse import urlparse

import input_guard

SECRET_KINDS = frozenset({
    "api_key", "github_token", "aws_key", "aws_secret", "slack_token", "jwt", "private_key",
    "secret_assignment", "encoded_secret", "card",
})
_SHORTENERS = frozenset({"bit.ly", "tinyurl.com", "t.co", "goo.gl", "is.gd", "cutt.ly", "rb.gy", "ow.ly"})
_LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
_URL = re.compile(r"https?://[^\s)\]>\"'<]+", re.IGNORECASE)
_MD_IMAGE = re.compile(r"!\[[^\]]*\]\((https?://[^)\s]+)")
_WILDCARD_DNS_SUFFIX = re.compile(r"\.(?:nip|sslip|traefik\.me)\.io$|\.xip\.io$", re.IGNORECASE)
_HEX_OCTET = re.compile(r"^0x[0-9a-fA-F]{1,2}$")


def _is_ip_host(host: str) -> bool:
    """IP-адрес в любом виде: точечный, decimal-int, hex-octet, IPv6 (в т.ч. с bracket'ами снятыми urlparse)."""
    h = host.strip("[]")
    try:
        ipaddress.ip_address(h)
        return True
    except ValueError:
        pass
    if h.isdigit():  # decimal-int IPv4: 2130706433 == 127.0.0.1
        try:
            ipaddress.ip_address(int(h))
            return True
        except ValueError:
            pass
    octets = h.split(".")
    if len(octets) == 4 and all(_HEX_OCTET.match(o) or o.isdigit() for o in octets):  # hex-octet: 0x7f.0x0.0x0.0x1
        try:
            nums = [int(o, 16) if o.lower().startswith("0x") else int(o) for o in octets]
            ipaddress.ip_address(".".join(str(n) for n in nums))
            return True
        except ValueError:
            pass
    return False
_COMMANDS: list[tuple[str, re.Pattern[str]]] = [
    ("загрузка и запуск скрипта (curl|wget … | sh)", re.compile(r"\b(?:curl|wget)\b[^\n|]*\|\s*(?:sudo\s+)?(?:ba|z)?sh\b", re.IGNORECASE)),
    ("рекурсивное удаление корня или домашней папки", re.compile(r"\brm\s+-[a-z]*r[a-z]*f?[a-z]*\s+(?:--no-preserve-root\s+)?(?:/|~|\$HOME)(?:\s|$|\*)", re.IGNORECASE)),
    ("fork-бомба", re.compile(r":\(\)\s*\{\s*:\|:&\s*\};:")),
    ("обратная оболочка (nc -e, /dev/tcp)", re.compile(r"\bnc\b[^\n]*\s-e\s|/dev/tcp/", re.IGNORECASE)),
    ("запуск закодированной команды (base64 -d | sh, powershell -enc)", re.compile(r"base64\s+-d[^\n|]*\|\s*(?:ba)?sh|powershell[^\n]*-e(?:nc|ncodedcommand)\b", re.IGNORECASE)),
    ("опасные права (chmod 777 /)", re.compile(r"\bchmod\s+-R\s+777\s+/", re.IGNORECASE)),
    ("форматирование диска (mkfs, dd of=/dev/…)", re.compile(r"\bmkfs(?:\.\w+)?\s+/dev/|\bdd\b[^\n]*\bof=/dev/(?:sd|nvme|disk)", re.IGNORECASE)),
]


@dataclass(frozen=True)
class OutputResult:
    """Итог проверки ответа: действие, итоговый текст и находки."""

    action: str  # allowed | masked | blocked
    text: str
    findings: list[dict]


def _words(text: str) -> list[str]:
    """Слова текста в нижнем регистре без пунктуации (для сравнения n-грамм)."""
    return re.findall(r"[\w\-]+", text.lower())


def leaks_system_prompt(text: str, system_prompt: str, n: int = 6) -> bool:
    """Есть ли в ответе фрагмент системного промпта из n подряд идущих слов."""
    prompt_words = _words(system_prompt)
    if not prompt_words:
        return False
    n = min(n, len(prompt_words))
    grams = {tuple(prompt_words[i:i + n]) for i in range(len(prompt_words) - n + 1)}
    words = _words(text)
    return any(tuple(words[i:i + n]) in grams for i in range(len(words) - n + 1))


def suspicious_urls(text: str) -> list[dict]:
    """Найти подозрительные URL и описать, чем именно."""
    found: list[dict] = []
    for url in dict.fromkeys(_URL.findall(text)):
        try:
            parsed = urlparse(url.rstrip(".,;"))
            host = (parsed.hostname or "").lower()
        except ValueError:
            # битый URL (например несбалансированные скобки IPv6) — fail closed, не падать с 500
            found.append({"kind": "suspicious_url", "url": url[:60], "reasons": ["URL не разбирается (возможна обфускация)"]})
            continue
        reasons: list[str] = []
        if _is_ip_host(host) and host not in _LOCAL_HOSTS:
            reasons.append("IP-адрес вместо домена (включая decimal/hex/IPv6-формы)")
        if _WILDCARD_DNS_SUFFIX.search(host):
            reasons.append("wildcard-DNS, резолвится в произвольный (в т.ч. metadata) IP")
        if "xn--" in host:
            reasons.append("punycode-домен (возможная подмена символов)")
        if host in _SHORTENERS:
            reasons.append("сократитель ссылок")
        if parsed.scheme == "http" and host not in _LOCAL_HOSTS:
            reasons.append("незащищённый http")
        if parsed.username or "@" in parsed.netloc:
            reasons.append("логин/пароль в адресе (userinfo)")
        if len(parsed.query) > 100:
            reasons.append("очень длинный query (возможная утечка данных)")
        if reasons:
            found.append({"kind": "suspicious_url", "url": f"{parsed.scheme}://{host}{parsed.path[:40]}", "reasons": reasons})
    for url in _MD_IMAGE.findall(text):
        host = (urlparse(url).hostname or "").lower()
        if host not in _LOCAL_HOSTS:
            found.append({"kind": "external_image", "url": f"{urlparse(url).scheme}://{host}",
                          "reasons": ["внешняя markdown-картинка: канал утечки данных через URL"]})
    return found


def dangerous_commands(text: str) -> list[dict]:
    """Найти опасные shell-команды в ответе."""
    return [{"kind": "dangerous_command", "reasons": [name]} for name, rx in _COMMANDS if rx.search(text)]


def guard_output(text: str, system_prompt: str = "") -> OutputResult:
    """Проверить ответ модели: секреты маскируются, утечка промпта, URL и команды блокируют ответ."""
    norm, found = input_guard.inspect(text)
    secrets = [f for f in found if f.kind in SECRET_KINDS]
    findings: list[dict] = [{**f.public(), "kind": f.kind} for f in secrets]

    blockers: list[dict] = []
    if leaks_system_prompt(text, system_prompt):
        blockers.append({"kind": "system_prompt_leak", "reasons": ["в ответе дословный фрагмент системного промпта"]})
    blockers += suspicious_urls(text)
    blockers += dangerous_commands(text)
    findings += blockers

    if blockers:
        reasons = "; ".join(r for b in blockers for r in b["reasons"])
        return OutputResult("blocked", f"[Ответ заблокирован output guard: {reasons}]", findings)
    if secrets:
        return OutputResult("masked", input_guard.mask(norm, secrets), findings)
    return OutputResult("allowed", text, findings)
