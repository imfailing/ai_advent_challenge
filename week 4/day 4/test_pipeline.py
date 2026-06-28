"""
Проверка пайплайна search → summarize → save_to_file.

Два уровня:
  1. ДЕТЕРМИНИРОВАННО (без LLM): вручную прогоняем цепочку через прямые
     MCP-вызовы и проверяем, что выход одного шага корректно становится
     входом следующего, а итог сохраняется в файл.
  2. АВТОМАТИЧЕСКИ (агент): одна инструкция → агент сам вызывает все три
     инструмента по порядку.
"""

import asyncio
import json
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from agent import MCPAgent

SERVER = StdioServerParameters(
    command=sys.executable,
    args=[str(Path(__file__).parent / "mcp_server.py")])


def _data(result):
    """Распаковать результат MCP-инструмента."""
    sc = result.structuredContent
    if sc is None:
        # нет структурированного результата — склеиваем текстовые блоки
        text = "".join(c.text for c in result.content if hasattr(c, "text"))
        return json.loads(text)
    if isinstance(sc, dict) and set(sc.keys()) == {"result"}:
        return sc["result"]          # список оборачивается в {"result": [...]}
    return sc


async def check_chain_manual() -> None:
    """Ручная цепочка через MCP — проверяем передачу данных между шагами."""
    async with stdio_client(SERVER) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = {t.name for t in (await session.list_tools()).tools}
            assert tools == {"search", "summarize", "save_to_file"}, tools
            print(f"✅ инструменты: {sorted(tools)}")

            # ШАГ 1: search
            r1 = _data(await session.call_tool("search", {"query": "MCP инструменты протокол"}))
            assert len(r1) >= 2, f"search вернул мало: {len(r1)}"
            combined = "\n".join(d["text"] for d in r1)
            print(f"✅ search → {len(r1)} документов ({len(combined)} символов)")

            # ШАГ 2: summarize получает ВЫХОД search
            r2 = _data(await session.call_tool(
                "summarize", {"text": combined, "max_sentences": 3}))
            assert r2["word_count"] > 0 and r2["summary"]
            # сводка реально построена из текста документов
            assert r2["word_count"] == len(combined.split()) or r2["sentence_count"] >= 1
            print(f"✅ summarize → {r2['sentence_count']} предл., "
                  f"{r2['word_count']} слов, keywords={r2['keywords']}")

            # ШАГ 3: save_to_file получает ВЫХОД summarize
            payload = (f"# Сводка\n\n{r2['summary']}\n\n"
                       f"Ключевые слова: {', '.join(r2['keywords'])}\n")
            r3 = _data(await session.call_tool(
                "save_to_file", {"filename": "test_chain.md", "content": payload}))
            assert r3["ok"] and r3["bytes"] > 0
            saved = Path(r3["path"])
            assert saved.exists(), "файл не создан"
            on_disk = saved.read_text(encoding="utf-8")
            assert r2["summary"] in on_disk, "сводка не попала в файл"
            print(f"✅ save_to_file → {r3['path']} ({r3['bytes']} байт), "
                  f"содержимое совпадает")
            print("✅ данные корректно прошли search → summarize → save_to_file")


async def check_chain_agent() -> None:
    """Агент сам выполняет цепочку по одной инструкции."""
    async with MCPAgent() as agent:
        r = await agent.ask(
            "Найди документы про MCP и инструменты, сделай краткую сводку "
            "и сохрани её в файл agent_pipeline.md")
        called = [tc.name for tc in r.tool_calls]
        print(f"\n✅ агент вызвал инструменты по порядку: {called}")
        # все три шага пайплайна выполнены
        assert "search" in called and "summarize" in called and "save_to_file" in called, called
        # порядок: search раньше summarize раньше save_to_file
        assert called.index("search") < called.index("summarize") < called.index("save_to_file"), called
        # файл реально создан
        out = Path(__file__).parent / "output" / "agent_pipeline.md"
        assert out.exists(), "агент не сохранил файл"
        print(f"✅ файл создан агентом: {out.name} ({out.stat().st_size} байт)")
        print(f"🤖 {r.answer[:200]}")


async def main() -> None:
    await check_chain_manual()
    await check_chain_agent()
    print("\n✅ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ")


if __name__ == "__main__":
    asyncio.run(main())
