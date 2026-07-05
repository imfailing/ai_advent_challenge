"""
Обёртка над локальным эмбеддером fastembed (ONNX, без torch).

Модель — мультиязычная (корпус на русском + код), поэтому берём
paraphrase-multilingual-MiniLM-L12-v2 (384-мерные векторы). Модель кэшируется
в экземпляре и подгружается лениво при первом embed().
"""

import numpy as np

MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
DIM = 384


class Embedder:
    def __init__(self, model_name: str = MODEL_NAME) -> None:
        self._model_name = model_name
        self._model = None

    def _ensure(self):
        if self._model is None:
            from fastembed import TextEmbedding
            self._model = TextEmbedding(self._model_name)
        return self._model

    def embed(self, texts: list[str]) -> np.ndarray:
        """Вернуть матрицу эмбеддингов (n, DIM), L2-нормированную."""
        model = self._ensure()
        vecs = np.array(list(model.embed(list(texts))), dtype=np.float32)
        norms = np.linalg.norm(vecs, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return vecs / norms

    def embed_one(self, text: str) -> np.ndarray:
        return self.embed([text])[0]

    @property
    def dim(self) -> int:
        return DIM
