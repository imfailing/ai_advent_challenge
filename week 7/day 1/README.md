# Week 7 / Day 1 — Ассистент разработчика, понимающий проект

Веб-ассистент, который отвечает на вопросы **о самом проекте**, объединяя:
- **RAG** по документации проекта (корневой README + README всех дней + `claude/`);
- **MCP** для живого состояния репозитория (git-ветка, файлы, diff, лог);
- **облачную модель DeepSeek** для генерации;
- команду **`/help`** и веб-интерфейс.

Порт **5009**.

---

## Как работает

```
вопрос
  │  1. RAG: локальный поиск по докам проекта (fastembed + индекс + rerank)
  ▼
контекст из документации
  │  2. DeepSeek + git-инструменты MCP (branch/files/diff/log)
  │     модель отвечает по докам, вызывая git при вопросах о репозитории
  ▼
ответ + источники (файлы доков) + вызванные git-инструменты
```

- **`project_loader.py`** — собирает документацию проекта (41 файл, ~107 стр.):
  корневой README, `week */day */README.md`, `claude/*.md`.
- **`build_index.py`** — chunking + эмбеддинги (fastembed, локально) → SQLite-индекс.
- **`git_mcp_server.py`** — MCP-сервер с git-инструментами (только чтение):
  `git_branch`, `git_status`, `git_log`, `git_diff`, `git_recent_files`, `list_files`.
- **`assistant.py`** — `DevAssistant`: RAG-контекст + git-инструменты + DeepSeek
  (tool-calling).
- **`app.py`** — Flask, команда `/help`.

---

## Команда `/help`

| Ввод | Что делает |
|---|---|
| `/help` | показывает, что умеет ассистент |
| `/help <вопрос>` | отвечает на вопрос о проекте |
| `<вопрос>` | то же (префикс необязателен) |

Примеры вопросов:
- «Какие недели есть в проекте и про что неделя 5?» → ответ по докам + источники
- «На какой ветке проект?» → вызов git `git_branch` → `main`
- «Какие последние коммиты?» → git `git_log`
- «Какие файлы в week 7/day 1?» → git `list_files`

---

## Проверка (`test_assistant.py`)

- ✅ индекс документации собран (458 чанков);
- ✅ веб-интерфейс отвечает;
- ✅ `/help` показывает справку;
- ✅ вопрос о структуре — ответ **по документации** с источниками
  (`README.md`, `claude/architecture.md`, `claude/project.md`);
- ✅ вопрос про git — вызван **MCP** `git_branch`, ветка определена (`main`).

```bash
python build_index.py       # собрать индекс доков
python test_assistant.py    # проверки (нужен DEEPSEEK_API_KEY)
```

---

## Запуск

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
export DEEPSEEK_API_KEY="ваш_ключ"

python build_index.py       # индекс документации проекта
python app.py               # веб-чат на http://localhost:5009
```

Ретрив локальный (fastembed), генерация — DeepSeek; git — через локальный
MCP-сервер (только чтение репозитория).

---

## Структура

```
day 1/
├── project_loader.py   # сбор документации проекта (README + доки дней + claude/)
├── chunking.py embedder.py index_store.py rerank.py   # RAG-пайплайн (из недели 5)
├── build_index.py      # индексация документации
├── git_mcp_server.py   # MCP-сервер: git-инструменты (branch/files/diff/log)
├── assistant.py        # DevAssistant: RAG + git MCP + DeepSeek
├── app.py              # Flask + /help (порт 5009)
├── templates/index.html
├── test_assistant.py
├── requirements.txt
└── README.md
```
