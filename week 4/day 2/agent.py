"""
Агент на DeepSeek, который умеет вызывать инструменты MCP-сервера.

Поток:
  1. подключиться к MCP-серверу по stdio, получить список инструментов;
  2. конвертировать MCP-инструменты в формат tools для OpenAI-совместимого API;
  3. в диалоге модель сама решает вызвать инструмент → агент исполняет его
     через MCP (session.call_tool) → результат возвращается модели;
  4. модель формирует финальный ответ, ИСПОЛЬЗУЯ результат инструмента.

Всё асинхронно: MCP-клиент async, поэтому используем openai.AsyncOpenAI.
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


@dataclass
class ToolCallRecord:
    name:      str
    arguments: dict
    result:    str


@dataclass
class AgentResult:
    answer:     str
    tool_calls: list = field(default_factory=list)   # list[ToolCallRecord]


class MCPAgent:
    SYSTEM = (
        "Ты ассистент по работе с CRM. У тебя есть инструменты MCP для доступа "
        "к данным CRM. Когда нужны реальные данные (клиенты, сделки, тикеты) — "
        "ВЫЗЫВАЙ инструмент, не выдумывай. Ответ давай на русском, по существу."
    )

    def __init__(
        self,
        server_command: str | None = None,
        server_args: list[str] | None = None,
        api_key: str | None = None,
        model: str = "deepseek-v4-flash",
    ) -> None:
        self._params = StdioServerParameters(
            command=server_command or sys.executable,
            args=server_args or [str(Path(__file__).parent / "mcp_server.py")],
        )
        self._client = AsyncOpenAI(
            api_key=api_key or os.environ["DEEPSEEK_API_KEY"],
            base_url="https://api.deepseek.com",
        )
        self._model       = model
        self._stack       = AsyncExitStack()
        self._session: ClientSession | None = None
        self._openai_tools: list[dict] = []
        self._tool_names:   list[str]  = []

    # ------------------------------------------------------------------
    # Подключение к MCP
    # ------------------------------------------------------------------

    async def connect(self) -> list[str]:
        """Установить MCP-соединение и загрузить список инструментов."""
        read, write = await self._stack.enter_async_context(stdio_client(self._params))
        self._session = await self._stack.enter_async_context(ClientSession(read, write))
        await self._session.initialize()

        tools = (await self._session.list_tools()).tools
        self._tool_names = [t.name for t in tools]
        # MCP inputSchema — это уже JSON Schema, годная для OpenAI tools
        self._openai_tools = [
            {
                "type": "function",
                "function": {
                    "name":        t.name,
                    "description": t.description or "",
                    "parameters":  t.inputSchema or {"type": "object", "properties": {}},
                },
            }
            for t in tools
        ]
        return self._tool_names

    async def close(self) -> None:
        await self._stack.aclose()

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, *exc):
        await self.close()

    # ------------------------------------------------------------------
    # Исполнение MCP-инструмента
    # ------------------------------------------------------------------

    async def _call_tool(self, name: str, arguments: dict) -> str:
        result = await self._session.call_tool(name, arguments)
        # Собираем текстовое содержимое ответа инструмента
        parts = []
        for block in result.content:
            text = getattr(block, "text", None)
            if text is not None:
                parts.append(text)
        return "\n".join(parts) if parts else "(пустой результат)"

    # ------------------------------------------------------------------
    # Диалог с моделью + вызов инструментов
    # ------------------------------------------------------------------

    async def ask(self, user_message: str, max_steps: int = 5) -> AgentResult:
        messages = [
            {"role": "system", "content": self.SYSTEM},
            {"role": "user",   "content": user_message},
        ]
        tool_calls: list[ToolCallRecord] = []

        for _ in range(max_steps):
            resp = await self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                tools=self._openai_tools,
            )
            msg = resp.choices[0].message

            if not msg.tool_calls:
                return AgentResult(answer=msg.content or "", tool_calls=tool_calls)

            # модель попросила вызвать инструмент(ы)
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
                result_text = await self._call_tool(tc.function.name, args)
                tool_calls.append(ToolCallRecord(tc.function.name, args, result_text))
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result_text,
                })

        # исчерпали шаги — последний ответ модели без инструментов
        final = await self._client.chat.completions.create(
            model=self._model, messages=messages)
        return AgentResult(answer=final.choices[0].message.content or "",
                           tool_calls=tool_calls)

    @property
    def tool_names(self) -> list[str]:
        return self._tool_names
