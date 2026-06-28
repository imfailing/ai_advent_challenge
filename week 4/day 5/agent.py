"""
Мультисерверный MCP-агент.

Подключается к НЕСКОЛЬКИМ MCP-серверам одновременно, объединяет их инструменты
в один список для модели и МАРШРУТИЗИРУЕТ каждый вызов на нужный сервер.

Имена инструментов делаются уникальными через неймспейс сервера:
    crm__get_customer, knowledge__search_docs, notes__save_note, …
По префиксу до «__» агент понимает, на какой сервер направить вызов.

Модель сама выбирает инструменты и порядок вызовов; агент проводит длинный
флоу (несколько шагов с инструментами разных серверов) до финального ответа.
"""

import json
import os
import sys
from contextlib import AsyncExitStack
from dataclasses import dataclass, field

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from openai import AsyncOpenAI

NS_SEP = "__"   # разделитель неймспейса: <label>__<tool>


@dataclass
class ServerSpec:
    label:   str
    command: str
    args:    list[str]


@dataclass
class ToolCallRecord:
    server:    str
    tool:      str
    arguments: dict
    result:    str


@dataclass
class AgentResult:
    answer:     str
    tool_calls: list = field(default_factory=list)   # list[ToolCallRecord]


class MultiMCPAgent:
    SYSTEM = (
        "Ты ассистент с инструментами из НЕСКОЛЬКИХ систем (CRM, база знаний, "
        "заметки). Выбирай подходящий инструмент под каждый под-вопрос и вызывай "
        "их в логичном порядке. Для составных задач выполняй цепочку шагов: "
        "сначала собери данные (CRM, база знаний), затем при необходимости "
        "обработай (summarize) и сохрани результат (заметка). "
        "Используй только реальные данные из инструментов. Отвечай на русском."
    )

    def __init__(self, servers: list[ServerSpec],
                 api_key: str | None = None,
                 model: str = "deepseek-v4-flash") -> None:
        self._servers = servers
        self._client  = AsyncOpenAI(
            api_key=api_key or os.environ["DEEPSEEK_API_KEY"],
            base_url="https://api.deepseek.com",
        )
        self._model = model
        self._stack = AsyncExitStack()
        # маршрутизация: openai_name -> (session, real_tool, label)
        self._routes: dict[str, tuple] = {}
        self._openai_tools: list[dict] = []

    # ------------------------------------------------------------------
    # Подключение ко всем серверам
    # ------------------------------------------------------------------

    async def connect(self) -> dict[str, list[str]]:
        by_server: dict[str, list[str]] = {}
        for spec in self._servers:
            params = StdioServerParameters(command=spec.command, args=spec.args)
            read, write = await self._stack.enter_async_context(stdio_client(params))
            session = await self._stack.enter_async_context(ClientSession(read, write))
            await session.initialize()

            tools = (await session.list_tools()).tools
            by_server[spec.label] = [t.name for t in tools]
            for t in tools:
                oa_name = f"{spec.label}{NS_SEP}{t.name}"
                self._routes[oa_name] = (session, t.name, spec.label)
                self._openai_tools.append({
                    "type": "function",
                    "function": {
                        "name":        oa_name,
                        "description": f"[{spec.label}] {t.description or ''}",
                        "parameters":  t.inputSchema or {"type": "object", "properties": {}},
                    },
                })
        return by_server

    async def close(self) -> None:
        await self._stack.aclose()

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, *exc):
        await self.close()

    # ------------------------------------------------------------------
    # Маршрутизация вызова на нужный сервер
    # ------------------------------------------------------------------

    async def _route_call(self, oa_name: str, arguments: dict) -> tuple[str, str, str]:
        if oa_name not in self._routes:
            return ("?", oa_name, f"Неизвестный инструмент: {oa_name}")
        session, real_tool, label = self._routes[oa_name]
        result = await session.call_tool(real_tool, arguments)
        parts = [getattr(b, "text", "") for b in result.content]
        text  = "\n".join(p for p in parts if p) or "(пусто)"
        return (label, real_tool, text)

    # ------------------------------------------------------------------
    # Длинный флоу с инструментами разных серверов
    # ------------------------------------------------------------------

    async def ask(self, user_message: str, max_steps: int = 12) -> AgentResult:
        messages = [
            {"role": "system", "content": self.SYSTEM},
            {"role": "user",   "content": user_message},
        ]
        records: list[ToolCallRecord] = []

        for _ in range(max_steps):
            resp = await self._client.chat.completions.create(
                model=self._model, messages=messages, tools=self._openai_tools)
            msg = resp.choices[0].message

            if not msg.tool_calls:
                return AgentResult(answer=msg.content or "", tool_calls=records)

            messages.append({
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [
                    {"id": tc.id, "type": "function",
                     "function": {"name": tc.function.name,
                                  "arguments": tc.function.arguments}}
                    for tc in msg.tool_calls
                ],
            })
            for tc in msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                label, tool, result_text = await self._route_call(tc.function.name, args)
                records.append(ToolCallRecord(label, tool, args, result_text))
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result_text,
                })

        final = await self._client.chat.completions.create(
            model=self._model, messages=messages)
        return AgentResult(answer=final.choices[0].message.content or "",
                           tool_calls=records)

    @property
    def tools(self) -> list[str]:
        return list(self._routes.keys())


# ------------------------------------------------------------------
# Стандартный набор серверов этого дня
# ------------------------------------------------------------------

def default_servers() -> list[ServerSpec]:
    from pathlib import Path
    here = Path(__file__).parent
    py   = sys.executable
    return [
        ServerSpec("crm",       py, [str(here / "crm_server.py")]),
        ServerSpec("knowledge", py, [str(here / "knowledge_server.py")]),
        ServerSpec("notes",     py, [str(here / "notes_server.py")]),
    ]
