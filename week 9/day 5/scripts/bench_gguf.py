"""
Замер GGUF-модели под llama-server (запускать на сервере): время загрузки до /health, память процесса (RSS)
и память GPU (VRAM+GTT), размер файла, скорость и качество на data/eval.jsonl (104 коммита, temperature 0).
Запуск: python scripts/bench_gguf.py <имя> <файл.gguf> <plain|prompt> [порт] → out/bench_<имя>.json
"""

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import commit_types  # noqa: E402
import llm_client  # noqa: E402

SERVER = os.path.expanduser("~/llm/llama/llama-server")


def gpu_mem_mb() -> float | None:
    """Память GPU (VRAM + GTT: у встроенной графики веса лежат в GTT), занятая сейчас, МБ; None без sysfs."""
    base = Path("/sys/class/drm/card1/device")
    files = [base / "mem_info_vram_used", base / "mem_info_gtt_used"]
    return round(sum(int(f.read_text()) for f in files) / 2**20, 1) if all(f.exists() for f in files) else None


def gpu_mem_mb_delta(before: float | None) -> float | None:
    """Прирост занятой памяти GPU относительно замера до старта сервера."""
    now = gpu_mem_mb()
    return None if before is None or now is None else round(now - before, 1)


def rss_mb(pid: int) -> float:
    """Резидентная память процесса, МБ."""
    m = re.search(r"VmRSS:\s+(\d+) kB", Path(f"/proc/{pid}/status").read_text())
    return round(int(m.group(1)) / 1024, 1) if m else 0.0


def main(name: str, gguf: str, mode: str, port: int) -> None:
    rows = [json.loads(line) for line in (ROOT / "data" / "eval.jsonl").read_text("utf-8").splitlines()]
    vram_before = gpu_mem_mb()
    start = time.time()
    proc = subprocess.Popen([SERVER, "-m", gguf, "--port", str(port), "-ngl", "99", "-c", "4096", "--no-webui"],  # noqa: S603
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=os.environ)
    url = f"http://127.0.0.1:{port}/v1"
    try:
        while not llm_client.is_healthy(url):
            if proc.poll() is not None:
                raise RuntimeError("llama-server завершился при старте")
            time.sleep(0.2)
        load_s = round(time.time() - start, 2)
        llm_client.chat(url, commit_types.build_messages("fix typo", mode))  # прогрев
        preds, times, tokens = [], [], []
        for r in rows:
            res = llm_client.chat(url, commit_types.build_messages(r["messages"][0]["content"].split("\n", 1)[1], mode),
                                  max_tokens=commit_types.MAX_NEW_TOKENS)
            pred, strict = commit_types.parse_type(res["content"])
            preds.append({"pred": pred, "gold": r["type"], "strict": strict, "reply": res["content"]})
            times.append(res["seconds"])
            tokens.append(res["completion_tokens"])
        result = {
            "name": name, "gguf": gguf, "mode": mode, "file_mb": round(Path(gguf).stat().st_size / 2**20),
            "load_seconds": load_s, "rss_mb": rss_mb(proc.pid), "gpu_mem_mb": gpu_mem_mb_delta(vram_before),
            "latency_mean_s": round(sum(times) / len(times), 3), "latency_p95_s": sorted(times)[int(0.95 * (len(times) - 1))],
            "tokens_per_s": round(sum(tokens) / sum(times), 1), "avg_new_tokens": round(sum(tokens) / len(tokens), 1),
            **commit_types.metrics(preds), "rows": preds,
        }
    finally:
        proc.terminate()
        proc.wait(timeout=30)
    (ROOT / "out").mkdir(exist_ok=True)
    (ROOT / "out" / f"bench_{name}.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k not in ("rows", "per_class_accuracy")}, ensure_ascii=False))  # noqa: T201


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]) if len(sys.argv) > 4 else 8090)
