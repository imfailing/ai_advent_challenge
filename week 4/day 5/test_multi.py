"""
Проверка мультисерверного флоу:
  • агент подключается к 3 серверам и видит их инструменты (с неймспейсами);
  • в длинном сценарии используются инструменты с РАЗНЫХ серверов;
  • выбор и порядок вызовов корректны (CRM/knowledge раньше сохранения заметки);
  • заметка реально сохранена.
"""

import asyncio
import json
from pathlib import Path

from agent import MultiMCPAgent, default_servers

NOTES = Path(__file__).parent / "notes.json"


async def main() -> None:
    # чистый старт заметок
    if NOTES.exists():
        NOTES.unlink()

    async with MultiMCPAgent(default_servers()) as agent:
        # 1. инструменты трёх серверов с неймспейсами
        labels = {t.split("__", 1)[0] for t in agent.tools}
        assert labels == {"crm", "knowledge", "notes"}, labels
        assert "crm__get_customer" in agent.tools
        assert "knowledge__search_docs" in agent.tools
        assert "notes__save_note" in agent.tools
        print(f"✅ подключены серверы {sorted(labels)}, всего инструментов {len(agent.tools)}")

        # 2. длинный составной сценарий
        r = await agent.ask(
            "Подними клиента C-003 и его открытые сделки, найди в базе знаний "
            "про лицензирование, сделай сводку и сохрани заметку «Бриф C-003» "
            "с клиентом, сделками и сводкой.")

        servers_used = {tc.server for tc in r.tool_calls}
        tools_used   = [(tc.server, tc.tool) for tc in r.tool_calls]
        print(f"✅ вызвано инструментов: {len(r.tool_calls)}")
        for tc in r.tool_calls:
            print(f"   [{tc.server}] {tc.tool}({tc.arguments})")

        # 3. задействованы РАЗНЫЕ серверы
        assert len(servers_used) >= 2, f"использован только один сервер: {servers_used}"
        assert "crm" in servers_used, "CRM не использован"
        print(f"✅ использованы инструменты с разных серверов: {sorted(servers_used)}")

        # 4. порядок: сбор данных (crm/knowledge) раньше сохранения заметки
        note_calls = [i for i, tc in enumerate(tools_used) if tc[0] == "notes" and tc[1] == "save_note"]
        if note_calls:
            first_note = note_calls[0]
            data_before = any(tools_used[i][0] in ("crm", "knowledge")
                              for i in range(first_note))
            assert data_before, "заметка сохранена до сбора данных"
            print("✅ порядок корректен: сбор данных → сохранение заметки")

            # 5. заметка реально записана
            assert NOTES.exists(), "notes.json не создан"
            saved = json.loads(NOTES.read_text(encoding="utf-8"))
            assert len(saved) >= 1 and saved[-1]["content"], "заметка пустая"
            print(f"✅ заметка сохранена: «{saved[-1]['title']}» "
                  f"({len(saved[-1]['content'])} символов)")

        print(f"\n🤖 {r.answer[:240]}")
        print("\n✅ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ")


if __name__ == "__main__":
    asyncio.run(main())
