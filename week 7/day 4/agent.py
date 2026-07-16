"""
FileAgent — ассистент, который САМ работает с файлами через MCP.

Вы задаёте ЦЕЛЬ (например «найди все места использования Logger и собери
отчёт»), а агент сам решает, какие файлы прочитать/искать/проанализировать и
что создать/изменить, вызывая файловые инструменты MCP.

Модель — DeepSeek (tool-calling). MCP-сессия открывается на задачу.
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

MODEL = "deepseek-v4-flash"


@dataclass
class ToolCall:
    tool:   str
    args:   dict
    result: str


@dataclass
class AgentRun:
    summary:    str
    tool_calls: list = field(default_factory=list)   # list[ToolCall]

    @property
    def files_written(self) -> list[str]:
        out = []
        for tc in self.tool_calls:
            if tc.tool == "write_file":
                out.append(tc.args.get("path", "?"))
        return out


class FileAgent:
    SYSTEM = (
        "Ты — инженер-ассистент, который РЕАЛЬНО работает с файлами проекта "
        "через инструменты (list_files, read_file, search, write_file). "
        "Тебе дают ЦЕЛЬ — сам реши, какие файлы посмотреть, что найти и "
        "проанализировать, и создай/измени нужные файлы через write_file. "
        "Действуй самостоятельно: не проси пользователя открывать файлы. "
        "Сначала собери данные (search/read_file по нескольким файлам), потом "
        "запиши результат (write_file). В финале кратко отчитайся на русском: "
        "что сделал и какие файлы затронул."
    )

    def __init__(self, api_key: str | None = None) -> None:
        self._client = AsyncOpenAI(
            api_key=api_key or os.environ["DEEPSEEK_API_KEY"],
            base_url="https://api.deepseek.com",
        )
        self._params = StdioServerParameters(
            command=sys.executable,
            args=[str(Path(__file__).parent / "fs_mcp_server.py")])

    async def run(self, goal: str, max_steps: int = 12) -> AgentRun:
        async with AsyncExitStack() as stack:
            read, write = await stack.enter_async_context(stdio_client(self._params))
            session = await stack.enter_async_context(ClientSession(read, write))
            await session.initialize()
            tools = (await session.list_tools()).tools
            oa_tools = [{
                "type": "function",
                "function": {"name": t.name, "description": t.description or "",
                             "parameters": t.inputSchema or {"type": "object", "properties": {}}},
            } for t in tools]

            messages = [{"role": "system", "content": self.SYSTEM},
                        {"role": "user", "content": f"Цель: {goal}"}]
            calls: list[ToolCall] = []

            for _ in range(max_steps):
                resp = await self._client.chat.completions.create(
                    model=MODEL, messages=messages, tools=oa_tools)
                msg = resp.choices[0].message
                if not msg.tool_calls:
                    return AgentRun(summary=msg.content or "", tool_calls=calls)

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
                    res = await session.call_tool(tc.function.name, args)
                    text = "\n".join(getattr(b, "text", "") for b in res.content).strip() or "(пусто)"
                    calls.append(ToolCall(tc.function.name, args, text))
                    messages.append({"role": "tool", "tool_call_id": tc.id, "content": text})

            final = await self._client.chat.completions.create(model=MODEL, messages=messages)
            return AgentRun(summary=final.choices[0].message.content or "", tool_calls=calls)
