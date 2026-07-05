"""
RAG-функция: вопрос → поиск релевантных чанков → объединение с вопросом →
запрос к LLM. Плюс базовый режим без RAG для сравнения.

Поток RAG:
    embed(question) → index_store.search(top-k) → собрать контекст с метками
    источников → системный промпт «отвечай только по контексту, цитируй
    источники» → DeepSeek → ответ + список использованных источников.
"""

import os
from dataclasses import dataclass, field

from openai import OpenAI

import index_store
from embedder import Embedder

MODEL = "deepseek-v4-flash"


@dataclass
class RagResult:
    answer:    str
    mode:      str                 # "rag" | "plain"
    sources:   list = field(default_factory=list)   # [{file, section, score}]
    prompt_tokens:     int = 0
    completion_tokens: int = 0


class RagAgent:
    SYSTEM_RAG = (
        "Ты отвечаешь на вопросы СТРОГО по предоставленному контексту из базы "
        "документов. Используй только факты из контекста. Если ответа в контексте "
        "нет — честно скажи, что информации недостаточно. Ссылайся на источники "
        "(имя файла) в ответе. Отвечай на русском, кратко и по делу."
    )
    SYSTEM_PLAIN = (
        "Ты отвечаешь на вопросы пользователя. Отвечай на русском, кратко. "
        "Если не знаешь точного ответа — скажи об этом, не выдумывай."
    )

    def __init__(self, api_key: str | None = None,
                 strategy: str = "structural", model: str = MODEL) -> None:
        self._client = OpenAI(
            api_key=api_key or os.environ["DEEPSEEK_API_KEY"],
            base_url="https://api.deepseek.com",
        )
        self._strategy = strategy
        self._model    = model
        self._embedder = Embedder()

    # ------------------------------------------------------------------
    # Поиск релевантных чанков
    # ------------------------------------------------------------------

    def retrieve(self, question: str, k: int = 4) -> list[dict]:
        qv = self._embedder.embed_one(question)
        return index_store.search(qv, self._strategy, k=k)

    @staticmethod
    def _build_context(chunks: list[dict]) -> str:
        blocks = []
        for i, c in enumerate(chunks, 1):
            blocks.append(f"[Источник {i}: {c['file']} → {c['section']}]\n{c['text']}")
        return "\n\n---\n\n".join(blocks)

    # ------------------------------------------------------------------
    # Режим с RAG
    # ------------------------------------------------------------------

    def ask_with_rag(self, question: str, k: int = 4) -> RagResult:
        chunks  = self.retrieve(question, k)
        context = self._build_context(chunks)
        user = (f"Контекст из базы документов:\n\n{context}\n\n"
                f"Вопрос: {question}\n\n"
                f"Ответь по контексту и укажи, из каких файлов взят ответ.")
        resp = self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "system", "content": self.SYSTEM_RAG},
                      {"role": "user", "content": user}],
        )
        msg = resp.choices[0].message
        sources = [{"file": c["file"], "section": c["section"],
                    "score": round(c["score"], 3)} for c in chunks]
        return RagResult(answer=msg.content or "", mode="rag", sources=sources,
                         prompt_tokens=resp.usage.prompt_tokens,
                         completion_tokens=resp.usage.completion_tokens)

    # ------------------------------------------------------------------
    # Режим без RAG
    # ------------------------------------------------------------------

    def ask_plain(self, question: str) -> RagResult:
        resp = self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "system", "content": self.SYSTEM_PLAIN},
                      {"role": "user", "content": question}],
        )
        msg = resp.choices[0].message
        return RagResult(answer=msg.content or "", mode="plain",
                         prompt_tokens=resp.usage.prompt_tokens,
                         completion_tokens=resp.usage.completion_tokens)
