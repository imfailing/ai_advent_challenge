"""
Улучшенный RAG: поиск → (query rewrite) → (реранкинг + фильтр по порогу) → LLM.

Режимы (флаги в RagConfig):
  • use_rewrite — переформулировать запрос в несколько вариантов (recall↑);
  • use_rerank  — переоценить кандидатов cross-encoder'ом и отсечь по порогу.

Конвейер:
  retrieve top-N (широко)  →  [rerank + threshold]  →  top-K  →  контекст  →  LLM
"""

import os
from dataclasses import dataclass, field

from openai import OpenAI

import index_store
from embedder import Embedder
from rerank import Reranker
from rewrite import QueryRewriter

MODEL = "deepseek-v4-flash"


@dataclass
class RagConfig:
    use_rewrite: bool  = False
    use_rerank:  bool  = False
    top_n:       int   = 12     # сколько достаём поиском ДО фильтрации
    top_k:       int   = 4      # сколько оставляем ПОСЛЕ
    threshold:   float = 0.3    # порог реранкера (0..1)
    min_keep:    int   = 2      # гарантированный минимум (не возвращать пусто)


@dataclass
class RagResult:
    answer:       str
    mode:         str
    queries:      list = field(default_factory=list)   # запросы после rewrite
    retrieved_n:  int  = 0                               # найдено до фильтра
    kept:         list = field(default_factory=list)     # чанки после фильтра
    dropped:      list = field(default_factory=list)     # отсеянные
    sources:      list = field(default_factory=list)


class RagAgent:
    SYSTEM_RAG = (
        "Ты отвечаешь на вопросы СТРОГО по предоставленному контексту из базы "
        "документов. Используй только факты из контекста. Если ответа нет — так и "
        "скажи. Ссылайся на источники (имя файла). Отвечай на русском, кратко."
    )
    SYSTEM_PLAIN = (
        "Ты отвечаешь на вопросы пользователя. Отвечай на русском, кратко. "
        "Если не знаешь точного ответа — скажи об этом, не выдумывай."
    )

    def __init__(self, api_key: str | None = None, strategy: str = "structural",
                 model: str = MODEL) -> None:
        self._client = OpenAI(
            api_key=api_key or os.environ["DEEPSEEK_API_KEY"],
            base_url="https://api.deepseek.com",
        )
        self._strategy = strategy
        self._model    = model
        self._embedder = Embedder()
        self._reranker = Reranker()
        self._rewriter = QueryRewriter(api_key=api_key, model=model)

    # ------------------------------------------------------------------
    # Поиск (с опциональным rewrite): объединение результатов по вариантам
    # ------------------------------------------------------------------

    def _retrieve(self, question: str, cfg: RagConfig) -> tuple[list[dict], list[str]]:
        queries = self._rewriter.rewrite(question) if cfg.use_rewrite else [question]
        seen: dict[str, dict] = {}
        for q in queries:
            qv = self._embedder.embed_one(q)
            for hit in index_store.search(qv, self._strategy, k=cfg.top_n):
                cid = hit["chunk_id"]
                # оставляем лучший bi-encoder score среди вариантов
                if cid not in seen or hit["score"] > seen[cid]["score"]:
                    seen[cid] = hit
        pool = sorted(seen.values(), key=lambda c: c["score"], reverse=True)
        return pool, queries

    # ------------------------------------------------------------------
    # Формирование контекста и вызов LLM
    # ------------------------------------------------------------------

    @staticmethod
    def _context(chunks: list[dict]) -> str:
        return "\n\n---\n\n".join(
            f"[Источник {i}: {c['file']} → {c['section']}]\n{c['text']}"
            for i, c in enumerate(chunks, 1))

    def _generate(self, question: str, chunks: list[dict]) -> str:
        user = (f"Контекст:\n\n{self._context(chunks)}\n\n"
                f"Вопрос: {question}\n\nОтветь по контексту, укажи источники.")
        resp = self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "system", "content": self.SYSTEM_RAG},
                      {"role": "user", "content": user}])
        return resp.choices[0].message.content or ""

    # ------------------------------------------------------------------
    # Публичные режимы
    # ------------------------------------------------------------------

    def ask(self, question: str, cfg: RagConfig) -> RagResult:
        pool, queries = self._retrieve(question, cfg)

        if cfg.use_rerank:
            kept, dropped = self._reranker.rerank(
                question, pool, top_k=cfg.top_k, threshold=cfg.threshold,
                min_keep=cfg.min_keep)
        else:
            kept, dropped = pool[:cfg.top_k], pool[cfg.top_k:]

        answer = self._generate(question, kept) if kept else \
            "В базе не нашлось релевантной информации для ответа."

        mode = ("rewrite+" if cfg.use_rewrite else "") + \
               ("rerank" if cfg.use_rerank else "plain")
        sources = [{"file": c["file"], "section": c["section"],
                    "score": round(c.get("score", 0), 3),
                    "rerank": round(c["rerank"], 3) if "rerank" in c else None}
                   for c in kept]
        return RagResult(answer=answer, mode=mode, queries=queries,
                         retrieved_n=len(pool), kept=kept, dropped=dropped,
                         sources=sources)

    def ask_plain_llm(self, question: str) -> str:
        """Ответ вообще без RAG — для базового сравнения."""
        resp = self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "system", "content": self.SYSTEM_PLAIN},
                      {"role": "user", "content": question}])
        return resp.choices[0].message.content or ""
