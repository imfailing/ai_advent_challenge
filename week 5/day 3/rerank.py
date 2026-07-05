"""
Второй этап после поиска: реранкинг + фильтр релевантности.

Схема: retrieve top-N (широко) → rerank cross-encoder'ом → отсечь по порогу
→ оставить top-K.

Реранкер — мультиязычный cross-encoder jina-reranker-v2-base-multilingual
(fastembed). В отличие от bi-encoder поиска (эмбеддинги по отдельности),
cross-encoder видит пару (запрос, чанк) целиком и точнее оценивает
релевантность.

Порог задаётся на нормированном скоре реранкера (сигмоида, 0..1).
"""

import numpy as np

RERANK_MODEL = "jinaai/jina-reranker-v2-base-multilingual"


def _sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-x))


class Reranker:
    def __init__(self, model_name: str = RERANK_MODEL) -> None:
        self._model_name = model_name
        self._model = None

    def _ensure(self):
        if self._model is None:
            from fastembed.rerank.cross_encoder import TextCrossEncoder
            self._model = TextCrossEncoder(self._model_name)
        return self._model

    def rerank(self, query: str, chunks: list[dict], top_k: int = 4,
               threshold: float = 0.3, min_keep: int = 2
               ) -> tuple[list[dict], list[dict]]:
        """
        Переоценить чанки cross-encoder'ом, отсечь по порогу, вернуть top_k.

        Возвращает (kept, dropped):
          kept    — прошедшие порог, отсортированные по rerank-скору, ≤ top_k;
          dropped — отсеянные — для отчёта/сравнения.
        Каждому чанку добавляется поле 'rerank' (0..1).

        min_keep — гарантированный минимум: если порог отсёк всё (или почти),
        оставляем хотя бы top-min_keep лучших, чтобы не вернуть пустой контекст.
        """
        if not chunks:
            return [], []
        model  = self._ensure()
        scores = np.array(list(model.rerank(query, [c["text"] for c in chunks])),
                          dtype=np.float32)
        probs  = _sigmoid(scores)
        ranked = [{**c, "rerank": float(p)} for c, p in zip(chunks, probs)]
        ranked.sort(key=lambda c: c["rerank"], reverse=True)

        above = [c for c in ranked if c["rerank"] >= threshold]
        if len(above) < min_keep:               # порог отсёк слишком много —
            kept = ranked[:min(min_keep, top_k)]  # берём топ по реранку
        else:
            kept = above[:top_k]
        kept_ids = {c["chunk_id"] for c in kept}
        dropped  = [c for c in ranked if c["chunk_id"] not in kept_ids]
        return kept, dropped
