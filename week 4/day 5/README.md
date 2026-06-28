# Week 4 / Day 5 — Несколько MCP-серверов и маршрутизация

Агент подключается к **трём независимым MCP-серверам** одновременно, объединяет
их инструменты и **маршрутизирует** каждый вызов на нужный сервер, выполняя
длинный составной флоу.

---

## Три сервера

| Сервер | Файл | Инструменты |
|---|---|---|
| **crm** | `crm_server.py` | `get_customer`, `search_deals` |
| **knowledge** | `knowledge_server.py` | `search_docs`, `summarize` |
| **notes** | `notes_server.py` | `save_note`, `list_notes` |

Каждый сервер самодостаточен и запускается отдельным процессом по stdio.

---

## Маршрутизация

Имена инструментов делаются уникальными через **неймспейс сервера**:

```
crm__get_customer   knowledge__search_docs   notes__save_note   …
└─ сервер ─┘         └─ сервер ─┘             └─ сервер ─┘
```

Агент строит таблицу маршрутов `openai_name → (session, real_tool, label)`.
Когда модель вызывает `knowledge__search_docs`, агент по префиксу до `__`
направляет вызов в сессию нужного сервера с настоящим именем инструмента.

```
MultiMCPAgent
  ├── stdio ──▶ crm-server        (get_customer, search_deals)
  ├── stdio ──▶ knowledge-server  (search_docs, summarize)
  └── stdio ──▶ notes-server      (save_note, list_notes)
        ▲
    маршрут по префиксу label__tool
```

---

## Длинный флоу (проверенный сценарий)

Запрос: *«Подними клиента C-003 и его открытые сделки, найди в базе знаний про
лицензирование, сделай сводку и сохрани заметку "Бриф C-003"»*.

Агент сам выбрал инструменты и порядок, задействовав **все три сервера**:

```
1. [crm]       get_customer(C-003)               → карточка клиента
2. [crm]       search_deals(C-003, open)         → 2 открытые сделки
3. [knowledge] search_docs("лицензирование")     → документ из базы знаний
4. [knowledge] summarize(text=…)                 → краткая сводка
5. [notes]     save_note("Бриф C-003", …)        → заметка сохранена
```

Сбор данных (crm, knowledge) идёт **раньше** сохранения результата (notes) —
порядок корректен.

---

## Запуск

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
export DEEPSEEK_API_KEY="ваш_ключ"

python app.py                      # длинный демо-сценарий
python app.py "ваш составной запрос"
```

---

## Проверка

```bash
python test_multi.py
```

Подтверждает:
- ✅ агент подключился к 3 серверам, видит 6 инструментов с неймспейсами;
- ✅ в длинном сценарии задействованы инструменты с **разных** серверов;
- ✅ выбор и **порядок** корректны (сбор данных → сохранение заметки);
- ✅ заметка реально записана в `notes.json`.

---

## Структура

```
day 5/
├── crm_server.py        # MCP-сервер 1: CRM
├── knowledge_server.py  # MCP-сервер 2: база знаний (поиск + сводка)
├── notes_server.py      # MCP-сервер 3: заметки (JSON)
├── agent.py             # MultiMCPAgent: подключение + маршрутизация + флоу
├── app.py               # приложение: длинный составной сценарий
├── test_multi.py        # проверка мультисерверного флоу
├── requirements.txt
└── README.md
# notes.json — хранилище заметок (в .gitignore)
```
