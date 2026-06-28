# Week 4 / Day 1 — Подключение к MCP и список инструментов

Минимальный код, который устанавливает **MCP-соединение** и получает от сервера
**список доступных инструментов** (tools).

MCP (Model Context Protocol) — открытый протокол, по которому LLM-приложения
подключаются к внешним серверам инструментов/данных. Здесь используется
официальный Python SDK [`mcp`](https://pypi.org/project/mcp/).

---

## Что происходит

```
client.py ──stdio──▶ server.py (подпроцесс)
   │  1. stdio_client(params)         запуск сервера, транспорт по stdio
   │  2. session.initialize()         MCP-рукопожатие (обмен версиями)
   │  3. session.list_tools()         запрос списка инструментов
   ▼
вывод: имя, описание и параметры каждого инструмента
```

- **`server.py`** — минимальный MCP-сервер на `FastMCP` с 4 инструментами
  (`add`, `multiply`, `echo`, `reverse`). Транспорт — stdio.
- **`client.py`** — клиент: подключается, делает рукопожатие, выводит список.

Локальный сервер нужен, чтобы пример был самодостаточным и проверялся offline.

---

## Установка

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt   # ставит mcp и зависимости
```

## Запуск

```bash
source venv/bin/activate
python client.py
```

Вывод:

```
→ Запускаю MCP-сервер: …/python …/server.py
✓ Соединение установлено. Сервер: demo-server v1.28.1
  Протокол MCP: 2025-11-25

✓ Получено инструментов: 4

1. add
   описание: Сложить два числа и вернуть сумму.
   параметры: a: number, b: number
2. multiply …
3. echo …
4. reverse …
Готово ✓
```

### Подключение к другому MCP-серверу

Клиент универсален — команду запуска сервера можно передать после `--`:

```bash
# например, к официальному reference-серверу (нужен Node/npx)
python client.py -- npx -y @modelcontextprotocol/server-everything
```

---

## Проверка

```bash
python test_mcp.py
```

Тест с ассертами подтверждает:
- ✅ соединение устанавливается (рукопожатие, имя сервера `demo-server`);
- ✅ список инструментов возвращается и совпадает с ожидаемым
  (`add, echo, multiply, reverse`);
- ✅ у каждого инструмента есть описание и input-схема;
- ✅ (бонус) вызов инструмента работает: `add(2, 3) = 5.0`.

---

## Структура

```
day 1/
├── server.py          # минимальный MCP-сервер (FastMCP, 4 инструмента)
├── client.py          # MCP-клиент: connect → initialize → list_tools
├── test_mcp.py        # проверка соединения и списка инструментов
├── requirements.txt   # mcp + зависимости
└── README.md
```

## Ключевой код клиента

```python
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

params = StdioServerParameters(command=sys.executable, args=["server.py"])
async with stdio_client(params) as (read, write):
    async with ClientSession(read, write) as session:
        await session.initialize()              # рукопожатие
        result = await session.list_tools()     # список инструментов
        for tool in result.tools:
            print(tool.name, tool.description)
```
