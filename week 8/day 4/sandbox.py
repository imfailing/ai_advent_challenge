"""
Песочница для проверки результата модели: копия фикстуры во временном каталоге,
запуск python/ruff/тестов, применение файлов из ответа модели.
"""

import re
import shutil
import subprocess
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PYTHON = "/Users/asv1337/dev/ai_advent_challenge/week 7/day 5/venv/bin/python"
RUFF = "ruff"   # переопределяется через bench.py --ruff
RUFF_TOML = HERE.parent.parent / "ruff.toml"


def make(fixture: str) -> Path:
    """Скопировать fixtures/<fixture> во временный каталог и вернуть путь."""
    dst = Path(tempfile.mkdtemp(prefix=f"day4_{fixture}_")) / "proj"
    shutil.copytree(HERE / "fixtures" / fixture, dst)
    cfg = re.sub(r"^src = \[.*\]", 'src = ["."]', RUFF_TOML.read_text(), flags=re.M)
    (dst / "ruff.toml").write_text(cfg)
    return dst


def run(cmd: list[str], cwd: Path, timeout: int = 60) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)  # noqa: S603
        return p.returncode, p.stdout[-3000:] + p.stderr[-2500:]
    except subprocess.TimeoutExpired:
        return 124, "timeout"


def ruff(cwd: Path) -> tuple[bool, str]:
    rc, out = run([RUFF, "check", "."], cwd)
    return rc == 0, out


def parse_files(text: str) -> dict[str, str]:
    """Достать файлы из ответа: заголовок `### FILE: name` + блок кода ```…```."""
    files: dict[str, str] = {}
    pattern = r"(?:#+\s*)?FILE:\s*`?([\w./-]+)`?\s*\n+```[\w]*\n(.*?)```"
    for m in re.finditer(pattern, text, re.S):
        files[m.group(1).strip()] = m.group(2)
    return files


def apply(cwd: Path, files: dict[str, str]) -> None:
    for name, content in files.items():
        target = (cwd / name).resolve()
        if cwd.resolve() not in target.parents:
            continue   # не выходим за песочницу
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)


def last_json_line(out: str) -> str:
    """Последняя строка вывода, похожая на JSON-объект (stderr с трейсбеками может идти после)."""
    lines = [ln for ln in out.splitlines() if ln.startswith("{")]
    return lines[-1] if lines else ""
