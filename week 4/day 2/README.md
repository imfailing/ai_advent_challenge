# Week 4 / Day 2 — Свой MCP-сервер вокруг API + вызов из агента

Собственный MCP-сервер, обёрнутый вокруг API (здесь — **mock CRM**), и агент
на DeepSeek, который вызывает инструменты сервера и использует их результат.

---

## Архитектура

```
app.py / test_agent.py
        │  вопрос пользователя
        ▼
   agent.py  (MCPAgent на DeepSeek, AsyncOpenAI)
        │  1. list_tools → конвертация в OpenAI tools
        │  2. модель решает вызвать инструмент
        │  3. session.call_tool(...) ──stdio──▶ mcp_server.py
        │  4. результат возвращается модели                 │
        │  5. модель формирует ответ, ИСПОЛЬЗУЯ результат    ▼
        ▼                                              crm_api.py
   ответ + список вызванных инструментов            (mock CRM, данные в памяти)
```

- **`crm_api.py`** — «внешний API»: mock CRM с данными в памяти.
- **`mcp_server.py`** — MCP-сервер: оборачивает функции CRM в инструменты.
- **`agent.py`** — агент: подключается к MCP, даёт инструменты модели,
  исполняет вызовы, собирает результат.
- **`app.py`** — приложение: задаёт вопросы, печатает вызовы и ответы.

---

## Инструменты MCP-сервера

Каждый инструмент **регистрируется** через `@mcp.tool()`, **описывает входные
параметры** аннотациями типов + docstring (FastMCP строит JSON-схему),
и **возвращает результат** (dict/list):

| Инструмент | Параметры | Возвращает |
|---|---|---|
| `list_customers` | — | список клиентов (id, name, tier, mrr) |
| `get_customer` | `customer_id: str` | полная карточка клиента |
| `search_deals` | `status: str` (open/won/lost/пусто) | список сделок |
| `create_ticket` | `customer_id, subject, priority` | карточка нового тикета |

Пример регистрации:

```python
@mcp.tool()
def create_ticket(customer_id: str, subject: str, priority: str = "normal") -> dict:
    """
    Создать тикет поддержки для клиента и вернуть его карточку.
    Параметры:
        customer_id: ID клиента, например "C-002".
        subject:     тема обращения.
        priority:    "low", "normal" или "high".
    """
    return crm_api.create_ticket(customer_id, subject, priority)
```

---

## Как агент вызывает инструмент

```python
# MCP inputSchema → формат tools для OpenAI-совместимого API
tools = [{"type": "function", "function": {
            "name": t.name, "description": t.description,
            "parameters": t.inputSchema}} for t in mcp_tools]

# модель вернула tool_calls → исполняем через MCP и возвращаем результат
result = await session.call_tool(tc.function.name, json.loads(tc.function.arguments))
messages.append({"role": "tool", "tool_call_id": tc.id, "content": result_text})
# следующий вызов модели формирует ответ, используя result_text
```

---

## Запуск

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
export DEEPSEEK_API_KEY="ваш_ключ"

python app.py                      # демо-сценарии
python app.py "Покажи gold-клиентов"   # свой вопрос
```

Пример вывода:

```
✓ Подключено к MCP. Инструменты: list_customers, get_customer, search_deals, create_ticket

❓ Какие сейчас открытые сделки и на какую сумму?
   🔧 MCP search_deals({'status': 'open'}) → {…D-101 2 520 000…D-102 90 000…}
🤖 Открытые сделки: D-101 «Расширение лицензий» 2 520 000 ₽,
   D-102 «Пилотный проект» 90 000 ₽. Итого: 2 610 000 ₽.
```

---

## Проверка

```bash
python test_agent.py
```

Подтверждает:
- ✅ MCP-сервер: 4 инструмента зарегистрированы, прямой `call_tool` работает;
- ✅ агент подключается и видит инструменты;
- ✅ агент **вызывает** `search_deals` и **использует** сумму в ответе;
- ✅ агент **вызывает** `create_ticket` (мутация) и отражает новый тикет.

---

## Структура

```
day 2/
├── crm_api.py         # «внешний API» — mock CRM (данные в памяти)
├── mcp_server.py      # MCP-сервер: регистрация инструментов вокруг CRM
├── agent.py           # MCPAgent (DeepSeek): tool-calling через MCP
├── app.py             # приложение: вопрос → вызов инструмента → ответ
├── test_agent.py      # проверка вызова инструмента и использования результата
├── requirements.txt   # mcp + openai
└── README.md
```
