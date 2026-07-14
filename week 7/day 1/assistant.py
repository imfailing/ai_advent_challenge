"""
Ассистент разработчика: понимает проект через RAG по его документации +
живое состояние репозитория через MCP (git).

На каждый вопрос:
  1. RAG: локально ищем релевантные фрагменты документации проекта
     (эмбеддинги fastembed + индекс + реранкер — всё локально);
  2. даём облачной модели (DeepSeek) контекст из доков + git-инструменты MCP;
  3. модель отвечает, при необходимости вызывая git-инструменты
     (ветка, файлы, diff, лог);
  4. возвращаем ответ + источники (файлы доков) + вызванные git-инструменты.

Эмбеддер/реранкер грузятся один раз; MCP-сессия открывается на запрос.
"""

import json
import os
import sys
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from openai import AsyncOpenAI

import index_store
from embedder import Embedder
from rerank import Reranker

MODEL = "deepseek-v4-flash"
STRATEGY = "structural"


@dataclass
class Answer:
    answer:     str
    sources:    list = field(default_factory=list)   # [{source, section}]
    git_calls:  list = field(default_factory=list)   # [{tool, args, result}]


class DevAssistant:
    SYSTEM = (
        "Ты — ассистент разработчика этого проекта (ai_advent_challenge). "
        "Отвечай на вопросы о проекте, опираясь на ПРЕДОСТАВЛЕННУЮ документацию "
        "(README, доки дней, дизайн-доки claude/) и на git-инструменты для живого "
        "состояния репозитория. Когда спрашивают про ветку, файлы, изменения, "
        "коммиты — ВЫЗЫВАЙ соответствующий git-инструмент, не выдумывай. "
        "Ссылайся на источники-файлы из контекста. Отвечай на русском, по делу."
    )

    def __init__(self, api_key: str | None = None) -> None:
        self._client = AsyncOpenAI(
            api_key=api_key or os.environ["DEEPSEEK_API_KEY"],
            base_url="https://api.deepseek.com",
        )
        self._embedder = Embedder()
        self._reranker = Reranker()
        self._git_params = StdioServerParameters(
            command=sys.executable,
            args=[str(Path(__file__).parent / "git_mcp_server.py")])

    # ------------------------------------------------------------------
    # RAG-поиск по докам проекта (локально)
    # ------------------------------------------------------------------

    def _retrieve(self, question: str, top_n=12, top_k=5) -> list[dict]:
        qv = self._embedder.embed_one(question)
        pool = index_store.search(qv, STRATEGY, k=top_n)
        kept, _ = self._reranker.rerank(question, pool, top_k=top_k,
                                        threshold=0.25, min_keep=3)
        return kept

    @staticmethod
    def _context(chunks: list[dict]) -> str:
        return "\n\n---\n\n".join(
            f"[{c['file']} → {c['section']}]\n{c['text']}" for c in chunks)

    # ------------------------------------------------------------------
    # Ответ: RAG-контекст + git-инструменты + DeepSeek
    # ------------------------------------------------------------------

    async def ask(self, question: str, max_steps: int = 5) -> Answer:
        chunks = self._retrieve(question)
        context = self._context(chunks)

        async with AsyncExitStack() as stack:
            read, write = await stack.enter_async_context(stdio_client(self._git_params))
            session = await stack.enter_async_context(ClientSession(read, write))
            await session.initialize()
            tools = (await session.list_tools()).tools
            oa_tools = [{
                "type": "function",
                "function": {"name": t.name, "description": t.description or "",
                             "parameters": t.inputSchema or {"type": "object", "properties": {}}},
            } for t in tools]

            user = (f"Документация проекта (контекст):\n\n{context}\n\n"
                    f"Вопрос: {question}\n\n"
                    f"Ответь по документации; для состояния репозитория используй git-инструменты.")
            messages = [{"role": "system", "content": self.SYSTEM},
                        {"role": "user", "content": user}]
            git_calls: list = []

            for _ in range(max_steps):
                resp = await self._client.chat.completions.create(
                    model=MODEL, messages=messages, tools=oa_tools)
                msg = resp.choices[0].message
                if not msg.tool_calls:
                    sources = [{"source": c["file"], "section": c["section"]} for c in chunks]
                    return Answer(answer=msg.content or "", sources=sources, git_calls=git_calls)

                messages.append({
                    "role": "assistant", "content": msg.content or "",
                    "tool_calls": [{"id": tc.id, "type": "function",
                                    "function": {"name": tc.function.name,
                                                 "arguments": tc.function.arguments}}
                                   for tc in msg.tool_calls]})
                for tc in msg.tool_calls:
                    try:
                        args = json.loads(tc.function.arguments or "{}")
                    except json.JSONDecodeError:
                        args = {}
                    result = await session.call_tool(tc.function.name, args)
                    text = "\n".join(getattr(b, "text", "") for b in result.content).strip() or "(пусто)"
                    git_calls.append({"tool": tc.function.name, "args": args, "result": text})
                    messages.append({"role": "tool", "tool_call_id": tc.id, "content": text})

            # исчерпали шаги — финальный ответ без инструментов
            final = await self._client.chat.completions.create(model=MODEL, messages=messages)
            sources = [{"source": c["file"], "section": c["section"]} for c in chunks]
            return Answer(answer=final.choices[0].message.content or "",
                          sources=sources, git_calls=git_calls)
