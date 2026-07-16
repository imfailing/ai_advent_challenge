"""
Ассистент поддержки: отвечает на вопросы о продукте с учётом контекста тикета.

На запрос:
  1. если указан ticket_id — через MCP получаем карточку тикета + пользователя
     (тариф, устройства, описание проблемы);
  2. RAG: локально ищем релевантные фрагменты документации продукта (FAQ, доки);
  3. DeepSeek формирует ответ, учитывая И документацию, И контекст тикета
     (например: SSO недоступен на тарифе Pro → предложить Business);
  4. возвращаем ответ + источники (доки) + использованный контекст тикета.

Эмбеддер/реранкер грузятся один раз; MCP-сессия — на запрос.
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
class SupportAnswer:
    answer:  str
    sources: list = field(default_factory=list)   # [{source, section}]
    ticket:  dict | None = None                    # использованный контекст тикета


class SupportAssistant:
    SYSTEM = (
        "Ты — ассистент поддержки продукта CloudNote. Отвечай на вопросы "
        "пользователей ТОЛЬКО по документации продукта из контекста и с учётом "
        "данных тикета (тариф пользователя, описание проблемы), если они есть. "
        "Часто причина — в ограничениях тарифа: сверяйся с тарифом пользователя. "
        "Давай конкретное решение по шагам, вежливо, на русском. Ссылайся на "
        "разделы документации. Если данных не хватает — уточни, что нужно."
    )

    def __init__(self, api_key: str | None = None) -> None:
        self._client = AsyncOpenAI(
            api_key=api_key or os.environ["DEEPSEEK_API_KEY"],
            base_url="https://api.deepseek.com",
        )
        self._embedder = Embedder()
        self._reranker = Reranker()
        self._mcp_params = StdioServerParameters(
            command=sys.executable,
            args=[str(Path(__file__).parent / "support_mcp_server.py")])

    # ------------------------------------------------------------------
    # RAG по документации
    # ------------------------------------------------------------------

    def _retrieve(self, query: str, top_k=5) -> list[dict]:
        qv = self._embedder.embed_one(query)
        pool = index_store.search(qv, STRATEGY, k=top_k * 2)
        kept, _ = self._reranker.rerank(query, pool, top_k=top_k,
                                        threshold=0.2, min_keep=3)
        return kept

    @staticmethod
    def _context(chunks: list[dict]) -> str:
        return "\n\n---\n\n".join(f"[{c['file']} → {c['section']}]\n{c['text']}"
                                 for c in chunks)

    # ------------------------------------------------------------------
    # Основной метод
    # ------------------------------------------------------------------

    async def ask(self, question: str, ticket_id: str | None = None) -> SupportAnswer:
        # контекст тикета через MCP (если указан)
        ticket_ctx: dict | None = None
        async with AsyncExitStack() as stack:
            if ticket_id:
                read, write = await stack.enter_async_context(stdio_client(self._mcp_params))
                session = await stack.enter_async_context(ClientSession(read, write))
                await session.initialize()
                res = await session.call_tool("get_ticket", {"ticket_id": ticket_id})
                text = "\n".join(getattr(b, "text", "") for b in res.content).strip()
                try:
                    ticket_ctx = json.loads(text)
                except json.JSONDecodeError:
                    ticket_ctx = {"raw": text}

            # запрос для RAG = вопрос + суть проблемы из тикета (лучше ретрив)
            query = question
            if ticket_ctx and not ticket_ctx.get("error"):
                query = f"{question}\n{ticket_ctx.get('subject','')} {ticket_ctx.get('description','')}"
            chunks = self._retrieve(query)

            # промпт
            parts = [f"Документация продукта (контекст):\n\n{self._context(chunks)}"]
            if ticket_ctx and not ticket_ctx.get("error"):
                u = ticket_ctx.get("user", {})
                parts.append(
                    "Контекст тикета:\n"
                    f"- Тикет {ticket_ctx.get('id')}: {ticket_ctx.get('subject')}\n"
                    f"- Описание: {ticket_ctx.get('description')}\n"
                    f"- Пользователь: {u.get('name')} (тариф {u.get('plan')}, "
                    f"устройств {u.get('devices')})")
            parts.append(f"Вопрос пользователя: {question}\n\n"
                         f"Ответь с учётом документации и тарифа пользователя.")
            user_msg = "\n\n".join(parts)

            resp = await self._client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "system", "content": self.SYSTEM},
                          {"role": "user", "content": user_msg}])
            answer = resp.choices[0].message.content or ""

        sources = [{"source": c["file"], "section": c["section"]} for c in chunks]
        return SupportAnswer(answer=answer, sources=sources, ticket=ticket_ctx)
