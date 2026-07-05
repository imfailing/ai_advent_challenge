"""
RAG со СТРУКТУРИРОВАННЫМ ответом: модель обязана вернуть

  • answer   — сам ответ;
  • sources  — источники [{source, section, chunk_id}];
  • quotes   — цитаты [{chunk_id, text}] — фрагменты из найденных чанков.

Плюс режим «не знаю»: если релевантность лучшего чанка ниже порога
(know_threshold), ассистент НЕ отвечает по существу, а честно говорит
«не знаю» и просит уточнение.

Конвейер (из day 3): retrieve top-N → [rewrite] → rerank → порог → top-K.
Ответ вытягивается через JSON-режим модели; цитаты дополнительно проверяются
на «заземление» (grounding) — реально ли они содержатся в найденных чанках.
"""

import json
import os
import re
from dataclasses import dataclass, field

from openai import OpenAI

import index_store
from embedder import Embedder
from rerank import Reranker
from rewrite import QueryRewriter

MODEL = "deepseek-v4-flash"


@dataclass
class RagConfig:
    use_rewrite:    bool  = True
    use_rerank:     bool  = True
    top_n:          int   = 12
    top_k:          int   = 4
    threshold:      float = 0.3    # порог отсечения чанков реранкером
    min_keep:       int   = 2
    know_threshold: float = 0.25   # ниже — режим «не знаю»


@dataclass
class Answer:
    know:          bool
    answer:        str
    sources:       list = field(default_factory=list)   # [{source, section, chunk_id}]
    quotes:        list = field(default_factory=list)    # [{chunk_id, text, grounded}]
    clarification: str  = ""
    top_score:     float = 0.0
    mode:          str  = ""


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


class RagAgent:
    SYSTEM = (
        "Ты отвечаешь на вопросы СТРОГО по предоставленному контексту. "
        "Верни ТОЛЬКО JSON со схемой:\n"
        '{\n'
        '  "know": true|false,\n'
        '  "answer": "краткий ответ по контексту (или пусто, если know=false)",\n'
        '  "sources": [{"source": "имя файла", "section": "раздел", "chunk_id": "id"}],\n'
        '  "quotes": [{"chunk_id": "id", "text": "дословный фрагмент из контекста"}],\n'
        '  "clarification": "если know=false — какой уточняющий вопрос задать"\n'
        '}\n'
        "Правила: используй только факты из контекста. Цитаты (quotes) — это "
        "фрагменты, СКОПИРОВАННЫЕ ДОСЛОВНО (слово в слово) из блоков контекста, "
        "подтверждающие ответ; НЕ перефразируй их. Приводи минимум одну цитату. "
        "Каждому источнику и цитате указывай chunk_id из заголовка блока "
        "[Источник N | chunk_id=...]. Если контекст не отвечает на вопрос — "
        'ставь know=false, answer оставь пустым и задай уточняющий вопрос.'
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
    # Поиск + фильтрация (как в day 3)
    # ------------------------------------------------------------------

    def _retrieve(self, question: str, cfg: RagConfig) -> list[dict]:
        queries = self._rewriter.rewrite(question) if cfg.use_rewrite else [question]
        seen: dict[str, dict] = {}
        for q in queries:
            qv = self._embedder.embed_one(q)
            for hit in index_store.search(qv, self._strategy, k=cfg.top_n):
                cid = hit["chunk_id"]
                if cid not in seen or hit["score"] > seen[cid]["score"]:
                    seen[cid] = hit
        pool = sorted(seen.values(), key=lambda c: c["score"], reverse=True)
        if cfg.use_rerank:
            kept, _ = self._reranker.rerank(
                question, pool, top_k=cfg.top_k, threshold=cfg.threshold,
                min_keep=cfg.min_keep)
            return kept
        return pool[:cfg.top_k]

    @staticmethod
    def _relevance(chunk: dict) -> float:
        return chunk.get("rerank", chunk.get("score", 0.0))

    @staticmethod
    def _context(chunks: list[dict]) -> str:
        return "\n\n---\n\n".join(
            f"[Источник {i} | chunk_id={c['chunk_id']} | {c['file']} → {c['section']}]\n{c['text']}"
            for i, c in enumerate(chunks, 1))

    # ------------------------------------------------------------------
    # Заземление цитат: реально ли они есть в найденных чанках
    # ------------------------------------------------------------------

    @staticmethod
    def _ground_quotes(quotes: list, chunks: list[dict]) -> list[dict]:
        """
        Цитата заземлена, если её нормализованный текст — подстрока чанка
        (дословно) ИЛИ ≥85% её слов присутствуют в одном чанке (лёгкая
        переформатировка). Выдуманные фрагменты не проходят.
        """
        by_id   = {c["chunk_id"]: _norm(c["text"]) for c in chunks}
        alltxt  = " ".join(by_id.values())
        tok_sets = {cid: set(t.split()) for cid, t in by_id.items()}
        all_toks = set(alltxt.split())
        out = []
        for q in quotes:
            if not isinstance(q, dict):
                continue
            text = (q.get("text") or "").strip()
            if not text:
                continue
            n   = _norm(text)
            cid = q.get("chunk_id", "")
            # 1) дословное вхождение
            grounded = (cid in by_id and n in by_id[cid]) or (n in alltxt)
            # 2) fallback: перекрытие слов ≥85%
            if not grounded:
                words = [w for w in n.split() if len(w) > 2]
                if words:
                    target = tok_sets.get(cid, all_toks)
                    overlap = sum(1 for w in words if w in target) / len(words)
                    grounded = overlap >= 0.85
            out.append({"chunk_id": cid, "text": text, "grounded": grounded})
        return out

    # ------------------------------------------------------------------
    # Основной метод
    # ------------------------------------------------------------------

    def ask(self, question: str, cfg: RagConfig | None = None) -> Answer:
        cfg = cfg or RagConfig()
        chunks = self._retrieve(question, cfg)
        top = self._relevance(chunks[0]) if chunks else 0.0
        mode = ("rewrite+" if cfg.use_rewrite else "") + \
               ("rerank" if cfg.use_rerank else "plain")

        # Gate «не знаю»: релевантность ниже порога → не выдумываем
        if not chunks or top < cfg.know_threshold:
            return Answer(
                know=False, answer="",
                clarification=("Не нашёл в базе достаточно релевантной информации. "
                               "Уточните вопрос или переформулируйте — "
                               "например, укажите модуль/тему из проекта."),
                top_score=round(top, 3), mode=mode)

        user = (f"Контекст:\n\n{self._context(chunks)}\n\n"
                f"Вопрос: {question}\n\nВерни JSON по схеме.")
        resp = self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "system", "content": self.SYSTEM},
                      {"role": "user", "content": user}],
            response_format={"type": "json_object"})
        try:
            data = json.loads(resp.choices[0].message.content or "{}")
        except json.JSONDecodeError:
            data = {}

        know = bool(data.get("know", True))
        if not know:
            return Answer(
                know=False, answer="",
                clarification=data.get("clarification")
                or "Уточните вопрос, пожалуйста.",
                top_score=round(top, 3), mode=mode)

        # источники: дополняем из реально найденных чанков (гарантия непустоты)
        sources = data.get("sources") or []
        if not sources:
            sources = [{"source": c["file"], "section": c["section"],
                        "chunk_id": c["chunk_id"]} for c in chunks]
        quotes = self._ground_quotes(data.get("quotes") or [], chunks)

        return Answer(
            know=True, answer=data.get("answer", ""),
            sources=sources, quotes=quotes,
            top_score=round(top, 3), mode=mode)
