"""
RAG с ЛОКАЛЬНОЙ генерацией (Ollama) — полностью офлайн-путь.

  • retrieval — ВСЕГДА локальный: эмбеддинги fastembed (локально) + косинусный
    поиск по SQLite-индексу + реранкинг локальным cross-encoder'ом;
  • генерация — переключаемый бэкенд:
      backend="local" → локальная модель через Ollama (без облака);
      backend="cloud" → DeepSeek (для сравнения, если есть ключ).

Индекс — из недели 5 (loader/chunking/embedder/index_store, скопированы сюда).
"""

import os
import time
from dataclasses import dataclass, field

import index_store
import ollama_client as local
from embedder import Embedder
from rerank import Reranker

LOCAL_MODEL = "qwen2.5:1.5b"
CLOUD_MODEL = "deepseek-v4-flash"


@dataclass
class RagResult:
    answer:       str
    backend:      str
    model:        str
    sources:      list = field(default_factory=list)   # [{source, section, chunk_id}]
    retrieve_sec: float = 0.0
    generate_sec: float = 0.0
    eval_tokens:  int = 0


SYSTEM = (
    "Ты отвечаешь на вопросы СТРОГО по предоставленному контексту из базы "
    "документов. Используй только факты из контекста, не выдумывай. Ссылайся на "
    "источники (имя файла). Отвечай на русском, кратко и по делу."
)


class LocalRAG:
    def __init__(self, strategy: str = "structural",
                 local_model: str = LOCAL_MODEL,
                 cloud_model: str = CLOUD_MODEL) -> None:
        self._strategy = strategy
        self._local_model = local_model
        self._cloud_model = cloud_model
        self._embedder = Embedder()
        self._reranker = Reranker()
        self._cloud = None   # ленивая инициализация OpenAI-клиента

    # ------------------------------------------------------------------
    # Локальный retrieval
    # ------------------------------------------------------------------

    def retrieve(self, question: str, top_n=12, top_k=4, threshold=0.3) -> list[dict]:
        qv = self._embedder.embed_one(question)
        pool = index_store.search(qv, self._strategy, k=top_n)
        kept, _ = self._reranker.rerank(question, pool, top_k=top_k,
                                        threshold=threshold, min_keep=2)
        return kept

    @staticmethod
    def _context(chunks: list[dict]) -> str:
        return "\n\n---\n\n".join(
            f"[{c['file']} → {c['section']}]\n{c['text']}" for c in chunks)

    # ------------------------------------------------------------------
    # Генерация: local | cloud
    # ------------------------------------------------------------------

    def _gen_local(self, messages: list[dict]) -> tuple[str, int]:
        answer, tokens = "", 0
        for part in local.chat_stream(messages, model=self._local_model):
            if "token" in part:
                answer += part["token"]
            elif part.get("done"):
                tokens = part["stats"]["eval_tokens"]
        return answer, tokens

    def _gen_cloud(self, messages: list[dict]) -> tuple[str, int]:
        if self._cloud is None:
            from openai import OpenAI
            self._cloud = OpenAI(api_key=os.environ["DEEPSEEK_API_KEY"],
                                 base_url="https://api.deepseek.com")
        resp = self._cloud.chat.completions.create(
            model=self._cloud_model, messages=messages)
        return resp.choices[0].message.content or "", resp.usage.completion_tokens

    # ------------------------------------------------------------------
    # Полный ход
    # ------------------------------------------------------------------

    def ask(self, question: str, backend: str = "local") -> RagResult:
        t0 = time.perf_counter()
        chunks = self.retrieve(question)
        retrieve_sec = round(time.perf_counter() - t0, 2)

        user = (f"Контекст из базы:\n\n{self._context(chunks)}\n\n"
                f"Вопрос: {question}\n\nОтветь по контексту и укажи источники.")
        messages = [{"role": "system", "content": SYSTEM},
                    {"role": "user", "content": user}]

        t1 = time.perf_counter()
        if backend == "local":
            answer, tokens = self._gen_local(messages)
            model = self._local_model
        elif backend == "cloud":
            answer, tokens = self._gen_cloud(messages)
            model = self._cloud_model
        else:
            raise ValueError("backend должен быть 'local' или 'cloud'")
        generate_sec = round(time.perf_counter() - t1, 2)

        sources = [{"source": c["file"], "section": c["section"],
                    "chunk_id": c["chunk_id"]} for c in chunks]
        return RagResult(answer=answer, backend=backend, model=model,
                         sources=sources, retrieve_sec=retrieve_sec,
                         generate_sec=generate_sec, eval_tokens=tokens)
