"""
Оптимизация локальной модели под КОНКРЕТНУЮ задачу: RAG-ответ строго по
контексту (кратко, по-русски, со ссылкой на источник).

Три рычага оптимизации:
  1. ПАРАМЕТРЫ инференса — temperature, num_predict (макс токенов), num_ctx (окно);
  2. PROMPT-ШАБЛОН — общий → специализированный под RAG-кейс;
  3. КВАНТОВАНИЕ — Q4_K_M (по умолчанию, 986 MB) vs Q8_0 (1.6 GB, точнее).

Retrieval локальный и общий для всех конфигов. Сравниваем на 10 вопросах:
  качество (keyword hit / pass), скорость (генерация), потребление (токены/размер).
"""

import statistics
import time

import index_store
import ollama_client as local
from embedder import Embedder
from eval_set import EVAL
from rerank import Reranker

MODEL_Q4 = "qwen2.5:1.5b"                    # квант по умолчанию
MODEL_Q8 = "qwen2.5:1.5b-instruct-q8_0"      # более точный квант

MODEL_SIZE = {MODEL_Q4: "986 MB (Q4_K_M)", MODEL_Q8: "1.6 GB (Q8_0)"}

# --- ДО оптимизации: общий промпт, дефолтные параметры ---
BASELINE_SYSTEM = (
    "Ты отвечаешь на вопросы по предоставленному контексту. Отвечай на русском."
)
BASELINE_OPTS = None   # дефолты Ollama (temperature ~0.8, без ограничений)

# --- ПОСЛЕ оптимизации: специализированный промпт + настроенные параметры ---
TUNED_SYSTEM = (
    "Ты — точный ассистент по документации. Отвечай СТРОГО по контексту ниже, "
    "не добавляй ничего от себя. Формат ответа:\n"
    "1) короткий прямой ответ (1–3 предложения, только факты из контекста);\n"
    "2) строка «Источник: <имя файла>».\n"
    "Если ответа в контексте нет — напиши «В контексте нет ответа». "
    "Без вступлений и рассуждений."
)
TUNED_OPTS = {
    "temperature": 0.1,     # точность/детерминизм для фактологии
    "num_predict": 200,     # ограничить многословность
    "num_ctx":     4096,    # окна хватает под контекст+вопрос, меньше памяти
    "top_p":       0.9,
    "repeat_penalty": 1.1,
}

_embedder = Embedder()
_reranker = Reranker()


def retrieve(question: str) -> list[dict]:
    qv = _embedder.embed_one(question)
    pool = index_store.search(qv, "structural", k=12)
    kept, _ = _reranker.rerank(question, pool, top_k=4, threshold=0.3, min_keep=2)
    return kept


def context(chunks: list[dict]) -> str:
    return "\n\n---\n\n".join(f"[{c['file']} → {c['section']}]\n{c['text']}"
                             for c in chunks)


def keyword_hit(answer: str, expected: list[str]) -> float:
    low = answer.lower()
    return sum(1 for kw in expected if kw.lower() in low) / len(expected)


def run_config(name: str, model: str, system: str, options: dict | None) -> dict:
    print(f"\n{'='*74}\n  {name}\n  модель: {MODEL_SIZE.get(model, model)} · "
          f"параметры: {options or 'по умолчанию'}\n{'='*74}")
    passes, hits, gens, toks = 0, [], [], []
    for i, item in enumerate(EVAL, 1):
        chunks = retrieve(item["question"])
        user = (f"Контекст:\n\n{context(chunks)}\n\n"
                f"Вопрос: {item['question']}")
        msgs = [{"role": "system", "content": system},
                {"role": "user", "content": user}]
        t = time.perf_counter()
        answer, stats = local.chat_full(msgs, model=model, options=options)
        gen = round(time.perf_counter() - t, 2)
        hit = keyword_hit(answer, item["expected"])
        passed = hit >= 0.5
        passes += passed; hits.append(hit); gens.append(gen)
        toks.append(stats.get("eval_tokens", 0))
        print(f"  [{i:>2}] hit={hit:.0%} {'✓' if passed else '✗'}  "
              f"{gen:>5.2f}с  {stats.get('eval_tokens',0):>4}ток | "
              f"{answer.strip()[:60].replace(chr(10),' ')}…")
    return {
        "name": name, "pass": passes,
        "avg_hit": round(statistics.mean(hits), 2),
        "avg_gen": round(statistics.mean(gens), 2),
        "avg_tok": round(statistics.mean(toks)),
        "std_gen": round(statistics.pstdev(gens), 2),
    }


def main() -> None:
    configs = [
        ("ДО (общий промпт, дефолтные параметры, Q4)", MODEL_Q4, BASELINE_SYSTEM, BASELINE_OPTS),
        ("ПОСЛЕ (спец. промпт + настроенные параметры, Q4)", MODEL_Q4, TUNED_SYSTEM, TUNED_OPTS),
        ("ПОСЛЕ + квант Q8 (точнее, крупнее)", MODEL_Q8, TUNED_SYSTEM, TUNED_OPTS),
    ]
    results = [run_config(*c) for c in configs]

    print("\n" + "=" * 74)
    print("  СРАВНЕНИЕ")
    print("=" * 74)
    print(f"{'Конфигурация':<48}{'верных':>8}{'ср.ген':>8}{'ток':>6}")
    print("-" * 74)
    for r in results:
        print(f"{r['name'][:47]:<48}{r['pass']:>6}/10{r['avg_gen']:>8.2f}{r['avg_tok']:>6}")

    before, after, q8 = results
    print("\n" + "=" * 74)
    print("  ОЦЕНКА")
    print("=" * 74)
    print(f"• Качество:  ДО {before['pass']}/10 → ПОСЛЕ {after['pass']}/10 "
          f"(hit {before['avg_hit']:.0%} → {after['avg_hit']:.0%}).")
    print(f"• Скорость:  ДО ~{before['avg_gen']}с → ПОСЛЕ ~{after['avg_gen']}с "
          f"(num_predict ограничивает многословность: {before['avg_tok']}→{after['avg_tok']} ток).")
    print(f"• Квант Q8:  {q8['pass']}/10, ~{q8['avg_gen']}с — точнее, но 1.6 GB против 986 MB "
          f"и медленнее.")
    print("• Ресурсы:   меньше токенов = меньше времени и памяти на генерацию; "
          "num_ctx=4096 вместо 32768 экономит RAM под KV-кэш.")


if __name__ == "__main__":
    main()
