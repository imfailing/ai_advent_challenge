"""
Проверка автокомплита (fill-in-the-middle) через Ollama /api/generate с suffix — как это делает Continue.
Берёт реальные фрагменты проекта, вырезает кусок, просит модель вставить его и сравнивает с оригиналом.
Замеры: задержка (мс) и точность (точное совпадение / похожесть).
"""

import difflib
import json
import sys
import time
import urllib.request

CASES = {
    "clamp last": ('    last = max(1, min(int(data.get("last") or ',
                   '), 100))\n    github_token = (data.get("github_token") or "").strip()\n', "15"),
    "return jsonify error": ('    if not repo:\n        return jsonify(', '), 400\n',
                             '{"error": "Укажите GitHub-репозиторий (owner/repo или ссылку)."}'),
    "counter": ('from collections import Counter\n\n\ndef top_authors(commits: list[dict], top: int = 5) -> list[tuple[str, int]]:\n    authors = Counter(',
                '\n    return authors.most_common(top)\n', 'c["author"] for c in commits'),
    "test assert": ('def main() -> None:\n    s = compute_stats(COMMITS)\n    assert s["total_commits"] == ',
                    '\n    print("✅ compute_stats")\n', "4"),
    "docstring": ('def parse_repo(value: str) -> str:\n    """', '"""\n    value = value.strip().rstrip("/")\n', "Извлечь 'owner/repo' из URL или строки owner/repo."),
}


def fim(model: str, prefix: str, suffix: str) -> tuple[str, float]:
    body = {"model": model, "prompt": prefix, "suffix": suffix, "stream": False, "keep_alive": "10m",
            "options": {"temperature": 0.1, "top_p": 0.9, "num_predict": 64, "stop": ["\n\n"]}}
    req = urllib.request.Request("http://localhost:11434/api/generate", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=120) as r:
        out = json.load(r)["response"]
    return out, (time.perf_counter() - t0) * 1000


def main() -> None:
    models = sys.argv[1:] or ["qwen2.5-coder:1.5b", "qwen2.5-coder:7b"]
    results = []
    for m in models:
        fim(m, "def f():\n    ", "\n")   # прогрев: загрузка модели не входит в замер
        for name, (pre, suf, expected) in CASES.items():
            out, ms = fim(m, pre, suf)
            sim = difflib.SequenceMatcher(None, out.strip(), (expected or "").strip()).ratio() if expected else None
            results.append({"model": m, "case": name, "ms": round(ms), "output": out.strip()[:90],
                            "expected": expected, "exact": (out.strip() == expected) if expected else None,
                            "similarity": round(sim, 2) if sim is not None else None})
    sys.stdout.write(json.dumps(results, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
