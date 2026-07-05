"""
ChatAgent: мини-чат с RAG + источниками + памятью задачи.

На каждый вопрос:
  1. сохранить сообщение пользователя;
  2. найти контекст в базе через RAG (rewrite → retrieve → rerank → фильтр);
  3. сгенерировать ответ с учётом: памяти задачи + истории диалога + контекста;
     ответ всегда сопровождается источниками;
  4. обновить память задачи (цель / уточнения / ограничения / термины);
  5. сохранить ответ ассистента.
"""

import json
import os
from dataclasses import dataclass, field

from openai import OpenAI

import database as db
import index_store
from embedder import Embedder
from rerank import Reranker
from rewrite import QueryRewriter
from task_memory import TaskMemoryUpdater, format_for_prompt

MODEL = "deepseek-v4-flash"
HISTORY_TURNS = 6          # сколько последних сообщений истории даём модели
KNOW_THRESHOLD = 0.22      # ниже — «не нашёл в базе»


@dataclass
class ChatResult:
    answer:      str
    sources:     list = field(default_factory=list)   # [{source, section, chunk_id}]
    found:       bool = True
    top_score:   float = 0.0
    task_memory: dict = field(default_factory=dict)


class ChatAgent:
    SYSTEM = (
        "Ты ассистент по документации проекта. Отвечай ТОЛЬКО по найденному "
        "контексту из базы; не выдумывай. Учитывай ПАМЯТЬ ЗАДАЧИ (цель, уже "
        "уточнённое, ограничения, термины) — не теряй цель диалога и не "
        "переспрашивай уже известное. Всегда ссылайся на источники (имя файла). "
        "Если в контексте нет ответа — скажи об этом и предложи уточнить. "
        "ВАЖНО: на вопросы о цели диалога, уточнениях и ограничениях "
        "(«напомни цель», «что мы зафиксировали») отвечай из ПАМЯТИ ЗАДАЧИ выше, "
        "а НЕ из документов — примеры целей/бюджетов в документах не относятся к "
        "пользователю. Отвечай на русском, кратко."
    )

    def __init__(self, session_id: str, api_key: str | None = None,
                 strategy: str = "structural", model: str = MODEL) -> None:
        self._sid   = session_id
        self._model = model
        self._strategy = strategy
        self._client = OpenAI(
            api_key=api_key or os.environ["DEEPSEEK_API_KEY"],
            base_url="https://api.deepseek.com",
        )
        self._embedder = Embedder()
        self._reranker = Reranker()
        self._rewriter = QueryRewriter(api_key=api_key, model=model)
        self._mem_updater = TaskMemoryUpdater(api_key=api_key, model=model)
        db.ensure_session(session_id)

    @property
    def session_id(self) -> str:
        return self._sid

    # ------------------------------------------------------------------
    # RAG-поиск (rewrite → retrieve → rerank → фильтр)
    # ------------------------------------------------------------------

    def _retrieve(self, question: str, history: list[dict] | None = None,
                  top_n=12, top_k=4, threshold=0.3) -> list[dict]:
        # контекстуализируем вопрос по истории (уточняющие «а почему?», «они»…)
        queries = self._rewriter.rewrite(question, history=history)
        seen: dict[str, dict] = {}
        for q in queries:
            qv = self._embedder.embed_one(q)
            for hit in index_store.search(qv, self._strategy, k=top_n):
                cid = hit["chunk_id"]
                if cid not in seen or hit["score"] > seen[cid]["score"]:
                    seen[cid] = hit
        pool = sorted(seen.values(), key=lambda c: c["score"], reverse=True)
        # реранк по самому информативному (контекстуализированному) запросу,
        # иначе короткий «Почему?» отсекает релевантные чанки
        rerank_query = max(queries, key=len) if history else question
        kept, _ = self._reranker.rerank(rerank_query, pool, top_k=top_k,
                                        threshold=threshold, min_keep=2)
        return kept

    @staticmethod
    def _context(chunks: list[dict]) -> str:
        return "\n\n---\n\n".join(
            f"[{c['file']} → {c['section']}]\n{c['text']}" for c in chunks)

    # ------------------------------------------------------------------
    # Основной ход
    # ------------------------------------------------------------------

    def ask(self, question: str) -> ChatResult:
        db.add_message(self._sid, "user", question)
        memory = db.get_task_memory(self._sid)

        # недавняя история (до текущего вопроса) — для контекстуализации поиска
        prior = db.get_messages(self._sid)[:-1][-HISTORY_TURNS:]
        chunks = self._retrieve(question, history=prior)
        top = (chunks[0].get("rerank", chunks[0].get("score", 0)) if chunks else 0.0)
        found = bool(chunks) and top >= KNOW_THRESHOLD

        if not found:
            answer = ("Не нашёл в базе релевантной информации по этому вопросу. "
                      "Уточните, пожалуйста, что именно интересует "
                      + (f"(в рамках цели: {memory['goal']})" if memory.get("goal") else "") + ".")
            db.add_message(self._sid, "assistant", answer, sources=[])
            memory = self._mem_updater.update(memory, question, answer)
            db.set_task_memory(self._sid, memory)
            return ChatResult(answer=answer, sources=[], found=False,
                              top_score=round(top, 3), task_memory=memory)

        # системный промпт: роль + память задачи
        system = self.SYSTEM
        mem_block = format_for_prompt(memory)
        if mem_block:
            system += "\n\n" + mem_block

        # последние сообщения истории (без текущего user-вопроса — он уйдёт отдельно)
        history = db.get_messages(self._sid)[:-1][-HISTORY_TURNS:]
        msgs = [{"role": "system", "content": system}]
        for m in history:
            msgs.append({"role": m["role"], "content": m["content"]})

        user = (f"Контекст из базы:\n\n{self._context(chunks)}\n\n"
                f"Вопрос: {question}\n\nОтветь по контексту и укажи источники.")
        msgs.append({"role": "user", "content": user})

        resp = self._client.chat.completions.create(model=self._model, messages=msgs)
        answer = resp.choices[0].message.content or ""

        sources = [{"source": c["file"], "section": c["section"],
                    "chunk_id": c["chunk_id"],
                    "score": round(c.get("rerank", c.get("score", 0)), 3)}
                   for c in chunks]
        db.add_message(self._sid, "assistant", answer, sources=sources)

        # обновить память задачи
        memory = self._mem_updater.update(memory, question, answer)
        db.set_task_memory(self._sid, memory)

        return ChatResult(answer=answer, sources=sources, found=True,
                          top_score=round(top, 3), task_memory=memory)
