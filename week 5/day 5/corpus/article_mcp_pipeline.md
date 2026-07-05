# Week 4 / Day 4 — Автоматический пайплайн из MCP-инструментов

Несколько MCP-инструментов, объединённых в цепочку, которую агент выполняет
**автоматически** по одной инструкции:

```
search  ──▶  summarize  ──▶  save_to_file
(получить    (обработать)    (сохранить
 данные)                      результат)
```

---

## Инструменты

| Инструмент | Роль | Параметры | Возвращает |
|---|---|---|---|
| `search` | ШАГ 1 — получить данные | `query, limit` | список документов `{id, title, text, score}` |
| `summarize` | ШАГ 2 — обработать | `text, max_sentences` | `{summary, sentence_count, word_count, keywords}` |
| `save_to_file` | ШАГ 3 — сохранить | `filename, content` | `{path, bytes, ok}` |

- `corpus.py` — mock-корпус документов (источник для search).
- `summarizer.py` — детерминированная экстрактивная сводка (без LLM).
- `save_to_file` пишет в папку `output/`, обрезая пути в имени файла.

---

## Как работает автоматическая цепочка

Агент (`agent.py`, DeepSeek tool-calling) получает одну инструкцию и сам
проводит данные через все три инструмента:

```
search("MCP инструменты")  → 3 документа
        │ тексты документов
        ▼
summarize(text=…)          → сводка + keywords
        │ сводка
        ▼
save_to_file("mcp.md", …)  → output/mcp.md (511 байт)
```

Выход каждого шага становится входом следующего — это и есть передача данных
между инструментами.

---

## Запуск

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
export DEEPSEEK_API_KEY="ваш_ключ"

python app.py
python app.py "Найди про SQLite, сделай сводку и сохрани в sqlite.md"
```

Пример вывода:

```
Цепочка вызовов (пайплайн):
  1. 🔧 search({'query': 'MCP инструменты', 'limit': 5})
  2. 🔧 summarize({'text': 'Model Context Protocol…', 'max_sentences': 3})
  3. 🔧 save_to_file({'filename': 'mcp_summary.md', 'content': '# Сводка…'})
     → {"path": ".../output/mcp_summary.md", "bytes": 511, "ok": true}
🤖 Пайплайн выполнен: поиск → сводка → сохранение в mcp_summary.md.
```

---

## Проверка

```bash
python test_pipeline.py
```

Два уровня:
- **Детерминированно** (без LLM) — цепочка прогоняется прямыми MCP-вызовами,
  проверяется, что выход `search` корректно подаётся в `summarize`, а его
  результат — в `save_to_file`, и файл на диске содержит ту же сводку;
- **Автоматически** (агент) — по одной инструкции агент вызывает все три
  инструмента **в правильном порядке** (`search` → `summarize` → `save_to_file`)
  и создаёт файл.

---

## Структура

```
day 4/
├── corpus.py          # mock-корпус (источник для search)
├── summarizer.py      # детерминированная сводка (для summarize)
├── mcp_server.py      # MCP-сервер: search / summarize / save_to_file
├── agent.py           # MCPAgent (DeepSeek): автоматическая оркестрация цепочки
├── app.py             # приложение: одна инструкция → весь пайплайн
├── test_pipeline.py   # проверка цепочки и передачи данных
├── requirements.txt
└── README.md
# output/ — сюда save_to_file пишет результаты (в .gitignore)
```
