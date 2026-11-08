"""
Песочница цикла: отдельный git-репозиторий с «кодовой базой», проверки и коммит.

Роль в цикле: здесь лежит контекст для модели (файлы проекта с подмешанными тестовыми секретами и PII,
чтобы проверить шлюз), сюда записывается сгенерированный код, здесь запускаются линтер и тесты и делается
коммит. Репозиторий создаётся во временной папке и не касается основного. Тестовые секреты собираются из
кусков на лету, в исходниках готовых ключей нет. Генерируемый код запускается с урезанным окружением
(без ключей) и таймаутом, но НЕ в изоляции от сети и диска. Модуль без Flask и LLM.
"""

import subprocess
from dataclasses import dataclass
from pathlib import Path

SOLUTION = "solution.py"
TESTS = "test_solution.py"
RUN_ENV = {"PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin", "LANG": "en_US.UTF-8"}


def fake_api_key() -> str:
    """Тестовый ключ в формате OpenAI (собирается на лету, не настоящий)."""
    return "sk-" + "proj-" + "Ab3dE6gH9jK2mN5pQ8sT1vW4yZ7"


def seed_files() -> dict[str, str]:
    """Файлы «кодовой базы» с секретами и PII: их увидит модель в контексте (через шлюз)."""
    password = "S3cr3t-" + "Pa55w0rd!"
    return {
        "README.md": "# Сервис отчётов\n\nМаленький Flask-сервис. Конфигурация — в config.py, примеры данных — в sample_users.csv.\n",
        "config.py": (
            '"""Конфигурация сервиса."""\n\n'
            f'API_KEY = "{fake_api_key()}"\n'
            f'DB_PASSWORD = "{password}"\n'
            'ADMIN_EMAIL = "ivan.petrov@example.com"\n'
            'API_BASE = "https://api.example.com/v1"\n'
        ),
        "sample_users.csv": (
            "name,email,phone,card\n"
            "Иван Петров,ivan.petrov@example.com,+7 (916) 123-45-67,4111 1111 1111 1111\n"
            "Анна Крылова,anna.krylova@example.com,+7 (903) 765-43-21,5500 0000 0000 0004\n"
        ),
    }


@dataclass(frozen=True)
class CheckResult:
    """Итог проверок сгенерированного кода."""

    ok: bool
    stage: str  # lint | tests | ok
    output: str


def _git(path: Path, *args: str) -> str:
    done = subprocess.run(["git", *args], cwd=path, capture_output=True, text=True, check=True, timeout=60)  # noqa: S603, S607
    return done.stdout.strip()


MAX_CONTEXT_FILE = 50_000  # байт: большие файлы в контекст не берутся


def context_from_dir(source: Path) -> dict[str, str]:
    """Прочитать файлы каталога как контекст проекта (без вложенных папок, скрытых и больших файлов, только UTF-8)."""
    files: dict[str, str] = {}
    for path in sorted(source.iterdir()):
        if not path.is_file() or path.name.startswith(".") or path.stat().st_size > MAX_CONTEXT_FILE:
            continue
        try:
            files[path.name] = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
    return files


def make_sandbox(root: Path, context_dir: Path | None = None) -> Path:
    """Создать репозиторий-песочницу с контекстом и стартовым коммитом.

    Контекст — файлы из `context_dir` (если задан) или подмешанные тестовые секреты и PII.
    """
    root.mkdir(parents=True, exist_ok=True)
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "loop@example.invalid")
    _git(root, "config", "user.name", "execution-loop")
    for name, text in (context_from_dir(context_dir) if context_dir else seed_files()).items():
        (root / name).write_text(text, encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-q", "-m", "seed: контекст проекта")
    return root


def context_files(root: Path) -> dict[str, str]:
    """Файлы-контекст, которые уйдут в промпт генерации (всё, кроме решения и тестов)."""
    skip = {SOLUTION, TESTS}
    return {p.name: p.read_text(encoding="utf-8") for p in sorted(root.iterdir())
            if p.is_file() and p.name not in skip and not p.name.startswith(".")}


def write_solution(root: Path, files: dict[str, str]) -> None:
    """Записать сгенерированные файлы решения."""
    for name, text in files.items():
        (root / name).write_text(text, encoding="utf-8")


def run_checks(root: Path, python: str, ruff: str | None, timeout: int = 60) -> CheckResult:
    """Линтер (ruff E9,F: синтаксис и неопределённые имена, без стиля) и тесты в урезанном окружении."""
    if ruff:
        lint = subprocess.run([ruff, "check", "--isolated", "--select", "E9,F", SOLUTION, TESTS], cwd=root,  # noqa: S603
                              capture_output=True, text=True, timeout=timeout)
        if lint.returncode != 0:
            return CheckResult(False, "lint", (lint.stdout + lint.stderr).strip())
    try:
        tests = subprocess.run([python, "-E", "-s", TESTS], cwd=root, capture_output=True, text=True,  # noqa: S603
                               timeout=timeout, env=RUN_ENV)
    except subprocess.TimeoutExpired:
        return CheckResult(False, "tests", f"тесты не завершились за {timeout} с")
    if tests.returncode != 0:
        return CheckResult(False, "tests", (tests.stdout + tests.stderr).strip())
    return CheckResult(True, "ok", (tests.stdout + tests.stderr).strip())


def independent_scan(root: Path, ruff: str | None) -> list[str]:
    """Независимый сканер (ruff, правила S — bandit): что осталось в решении. Пусто, если ruff не задан."""
    if not ruff:
        return []
    done = subprocess.run([ruff, "check", "--isolated", "--select", "S", "--ignore", "S101", "--output-format", "concise",  # noqa: S603
                           SOLUTION], cwd=root, capture_output=True, text=True, timeout=60)
    return [line for line in done.stdout.splitlines() if line.strip() and not line.startswith(("Found", "All checks", "No fixes"))]


def commit(root: Path, message: str) -> str:
    """Закоммитить решение и тесты; вернуть короткий хэш."""
    _git(root, "add", SOLUTION, TESTS)
    _git(root, "commit", "-q", "-m", message)
    return _git(root, "rev-parse", "--short", "HEAD")
