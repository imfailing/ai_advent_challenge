"""
AI-ревьюер PR: diff → RAG (доки + код) → структурированное ревью.

Что делает:
  1. получает diff (из файла, stdin или `git diff <base>...HEAD`);
  2. извлекает изменённые файлы;
  3. RAG: по diff + именам файлов ищет релевантный контекст (конвенции проекта,
     соседний код) в локальном индексе;
  4. просит DeepSeek выдать ревью по разделам:
     потенциальные баги · архитектурные проблемы · рекомендации.

Использование:
  python reviewer.py --diff-file changes.diff
  git diff main...HEAD | python reviewer.py
  python reviewer.py --base origin/main            # сам посчитает diff
  python reviewer.py ... --out review.md
"""

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

import index_store
from embedder import Embedder
from rerank import Reranker

MODEL = "deepseek-v4-flash"
STRATEGY = "structural"
REPO_ROOT = Path(__file__).resolve().parents[2]
MAX_DIFF_CHARS = 20000   # ограничить размер diff в промпте


# ------------------------------------------------------------------
# Получение diff и изменённых файлов
# ------------------------------------------------------------------

def get_diff(args) -> str:
    if args.diff_file:
        return Path(args.diff_file).read_text(encoding="utf-8", errors="ignore")
    if args.base:
        out = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "diff", f"{args.base}...HEAD"],
            capture_output=True, text=True, timeout=30)
        return out.stdout
    if not sys.stdin.isatty():
        return sys.stdin.read()
    raise SystemExit("Нет diff. Укажите --diff-file, --base или подайте diff в stdin.")


def changed_files(diff: str) -> list[str]:
    files = re.findall(r"^\+\+\+ b/(.+)$", diff, flags=re.MULTILINE)
    return [f for f in files if f != "/dev/null"]


# ------------------------------------------------------------------
# RAG: контекст под изменения
# ------------------------------------------------------------------

def retrieve_context(diff: str, files: list[str], embedder: Embedder,
                     reranker: Reranker, top_k=6) -> list[dict]:
    if index_store.count(STRATEGY) == 0:
        return []
    # запрос = изменённые файлы + добавленные строки diff (суть изменений)
    added = "\n".join(l[1:] for l in diff.splitlines()
                      if l.startswith("+") and not l.startswith("+++"))
    query = ("Изменённые файлы: " + ", ".join(files) + "\n" + added)[:4000]
    qv = embedder.embed_one(query)
    pool = index_store.search(qv, STRATEGY, k=top_k * 3)
    # исключим сами изменённые файлы из контекста (нам нужны конвенции/соседний код)
    pool = [c for c in pool if c["file"] not in files] or pool
    kept, _ = reranker.rerank(query, pool, top_k=top_k, threshold=0.2, min_keep=3)
    return kept


def _context(chunks: list[dict]) -> str:
    if not chunks:
        return "(релевантный контекст из индекса не найден)"
    return "\n\n---\n\n".join(f"[{c['file']} → {c['section']}]\n{c['text']}"
                             for c in chunks)


# ------------------------------------------------------------------
# Генерация ревью
# ------------------------------------------------------------------

SYSTEM = (
    "Ты — старший инженер, делающий код-ревью Pull Request этого проекта. "
    "Опирайся на конвенции и архитектуру проекта из предоставленного контекста. "
    "Будь конкретным: ссылайся на файлы/строки из diff. Не хвали ради похвалы, "
    "фокусируйся на проблемах. Отвечай на русском в формате Markdown СТРОГО по "
    "разделам:\n"
    "## 🐞 Потенциальные баги\n## 🏛 Архитектурные проблемы\n## 💡 Рекомендации\n"
    "В каждом разделе — маркированный список; если пусто, напиши «— не выявлено». "
    "В конце — строка «Вердикт: <одобрить / доработать>»."
)


def review(diff: str, files: list[str], context: str, api_key: str | None = None) -> str:
    from openai import OpenAI
    client = OpenAI(api_key=api_key or os.environ["DEEPSEEK_API_KEY"],
                    base_url="https://api.deepseek.com")
    diff_short = diff if len(diff) <= MAX_DIFF_CHARS else diff[:MAX_DIFF_CHARS] + "\n…(diff обрезан)…"
    user = (f"Контекст проекта (конвенции/архитектура/соседний код):\n\n{context}\n\n"
            f"Изменённые файлы: {', '.join(files) or '—'}\n\n"
            f"Diff Pull Request:\n```diff\n{diff_short}\n```\n\n"
            f"Сделай ревью по разделам.")
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "system", "content": SYSTEM},
                  {"role": "user", "content": user}])
    return resp.choices[0].message.content or ""


# ------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description="AI-ревью PR по diff + RAG")
    ap.add_argument("--diff-file", help="файл с diff")
    ap.add_argument("--base", help="база для git diff <base>...HEAD (напр. origin/main)")
    ap.add_argument("--out", help="куда записать ревью (по умолчанию — stdout)")
    args = ap.parse_args()

    diff = get_diff(args)
    if not diff.strip():
        print("Diff пустой — нечего ревьюить.")
        return
    files = changed_files(diff)

    embedder, reranker = Embedder(), Reranker()
    chunks = retrieve_context(diff, files, embedder, reranker)
    text = review(diff, files, _context(chunks))

    header = (f"# 🤖 AI-ревью PR\n\n"
              f"Изменённые файлы ({len(files)}): "
              f"{', '.join(f'`{f}`' for f in files) or '—'}\n\n"
              f"Контекст из проекта (RAG): "
              f"{', '.join(sorted({c['file'] for c in chunks})) or '—'}\n\n---\n\n")
    result = header + text

    if args.out:
        Path(args.out).write_text(result, encoding="utf-8")
        print(f"Ревью записано в {args.out}")
    else:
        print(result)


if __name__ == "__main__":
    main()
