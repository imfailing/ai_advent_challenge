"""
Независимая проверка прогона execution loop по истории git песочницы.

Для каждой задачи берётся её коммит (`Txx: …`), состояние разворачивается во временный каталог, запускаются:
скрытая проверка критерия (verify/check.py), ruff и все тесты. Затем те же проверки на HEAD (регрессии).
Метрики: серия подряд (в порядке пула) без пауз, % прошедших с первого раза, время между коммитами.

  python verify_run.py <песочница> <каталог-результатов> --python <py> --ruff <ruff>
"""

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
TASKS = [f"T{i:02d}" for i in range(1, 19)]


def sh(cmd: list[str], cwd: Path, timeout: int = 180) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)  # noqa: S603
        return p.returncode, (p.stdout + p.stderr)[-1500:]
    except subprocess.TimeoutExpired:
        return 124, "timeout"


def extract(sandbox: Path, ref: str) -> Path:
    dst = Path(tempfile.mkdtemp(prefix="verify_"))
    arc = subprocess.run(["git", "archive", ref], cwd=sandbox, capture_output=True, check=True)  # noqa: S603, S607
    subprocess.run(["tar", "-x", "-C", str(dst)], input=arc.stdout, check=True)  # noqa: S603, S607
    (dst / "check.py").write_text((HERE / "verify" / "check.py").read_text())
    return dst


def global_suite(d: Path, py: str, ruff: str) -> dict:
    rc_r, out_r = sh([ruff, "check", ".", "--exclude", "check.py"], d)
    fails = []
    for t in sorted(d.glob("test_*.py")):
        rc, _ = sh([py, t.name], d)
        if rc != 0:
            fails.append(t.name)
    return {"ruff_ok": rc_r == 0, "ruff_out": "" if rc_r == 0 else out_r[-500:], "failing_tests": fails}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("sandbox")
    ap.add_argument("out")
    ap.add_argument("--python", required=True)
    ap.add_argument("--ruff", required=True)
    a = ap.parse_args()
    sb, out = Path(a.sandbox), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    log = subprocess.run(["git", "log", "--reverse", "--format=%H|%ct|%s"], cwd=sb,  # noqa: S603, S607
                         capture_output=True, text=True, check=True).stdout.strip().splitlines()
    commits = [ln.split("|", 2) for ln in log]
    base_ts = int(commits[0][1])
    by_task: dict[str, list] = {}
    for sha, ts, subj in commits[1:]:
        m = re.match(r"\s*\[?(T\d{2})\b", subj)
        if m:
            by_task.setdefault(m.group(1), []).append((sha, int(ts), subj))
    prev_ts = base_ts
    rows = []
    for t in TASKS:
        cs = by_task.get(t)
        if not cs:
            rows.append({"task": t, "committed": False})
            continue
        sha, ts, subj = cs[0]
        d = extract(sb, sha)
        rc, out_c = sh([a.python, "check.py", t], d)
        g = global_suite(d, a.python, a.ruff)
        rows.append({"task": t, "committed": True, "commit": sha[:8], "subject": subj, "commits_for_task": len(cs),
                     "check_pass": rc == 0, "check_out": "" if rc == 0 else out_c[-300:],
                     "ruff_ok": g["ruff_ok"], "failing_tests": g["failing_tests"],
                     "ok": rc == 0 and g["ruff_ok"] and not g["failing_tests"],
                     "gap_s": ts - prev_ts})
        prev_ts = max(prev_ts, ts)
    head = extract(sb, "HEAD")
    for r in rows:
        r["still_ok_at_head"] = sh([a.python, "check.py", r["task"]], head)[0] == 0
    hg = global_suite(head, a.python, a.ruff)
    streak = 0
    for r in rows:
        if r.get("ok"):
            streak += 1
        else:
            break
    done = [r for r in rows if r.get("ok")]
    first_pass = [r for r in done if r["commits_for_task"] == 1]
    gaps = [r["gap_s"] for r in rows if r.get("committed")]
    summary = {"tasks_total": len(TASKS), "committed": sum(1 for r in rows if r["committed"]),
               "verified_done": len(done), "streak_without_break": streak,
               "first_try_pct": round(100 * len(first_pass) / len(TASKS), 1),
               "avg_minutes_per_task": round(sum(gaps) / len(gaps) / 60, 1) if gaps else None,
               "total_minutes": round((prev_ts - base_ts) / 60, 1),
               "head_ruff_ok": hg["ruff_ok"], "head_failing_tests": hg["failing_tests"],
               "head_tasks_passing": sum(1 for r in rows if r.get("still_ok_at_head"))}
    (out / "verification.json").write_text(json.dumps({"summary": summary, "tasks": rows}, ensure_ascii=False, indent=1))
    lines = ["| Задача | Коммит | Критерий | ruff+тесты | Пауза до коммита, мин | На HEAD |", "|---|---|---|---|---|---|"]
    for r in rows:
        if not r["committed"]:
            lines.append(f"| {r['task']} | — | не выполнено | — | — | — |")
            continue
        lines.append(f"| {r['task']} | {r['commit']} | {'✅' if r['check_pass'] else '❌'} | "
                     f"{'✅' if r['ruff_ok'] and not r['failing_tests'] else '❌ ' + ','.join(r['failing_tests'])} | "
                     f"{r['gap_s'] / 60:.1f} | {'✅' if r['still_ok_at_head'] else '❌'} |")
    (out / "verification.md").write_text("\n".join(lines) + "\n\n" + json.dumps(summary, ensure_ascii=False, indent=1) + "\n")
    sys.stdout.write(json.dumps(summary, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
