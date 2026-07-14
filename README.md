# AI Advent Challenge

Учебный AI-адвент: каждый день — новая задача по работе с LLM. Задачи
усложняются от простых консольных вызовов до агентов с памятью, MCP-серверов,
RAG-чата и приватного AI-сервиса на **локальной** модели (для деплоя на VPS).

**Стек:** Python 3.13 · DeepSeek API (OpenAI-совместимый) · Flask · SQLite ·
MCP SDK · fastembed · Ollama (локальные LLM) · Docker/nginx.
У каждого дня — свой `venv/` и `README.md` с деталями.

---

## Недели

### Week 1 — Консольные скрипты (основы LLM API)

| День | Тема |
|---|---|
| 1 | Базовый вызов DeepSeek API |
| 2 | Контроль формата ответа (`max_tokens`, `stop`) |
| 3 | 4 способа решения задачи (прямой / пошагово / meta-prompt / эксперты) |
| 4 | Влияние `temperature` (0 / 0.7 / 1.2) |
| 5 | Сравнение моделей (GigaChat / DeepSeek) |

### Week 2 — Flask-приложение с агентом

| День | Тема | Порт |
|---|---|---|
| 1 | Flask-чат: агент + сессии + Markdown | 5000 |
| 2 | Персистентная история в SQLite | 5000 |
| 3 | Токены/стоимость + файлы контекста + выбор модели | 5000 |
| 4 | Сжатие контекста (суммаризация) | 5000 |
| 5 | Три стратегии контекста: Sliding Window / Sticky Facts / Branching | 5000 |

### Week 3 — Память и состояние агента

| День | Тема | Порт |
|---|---|---|
| 1 | Модель памяти: 3 слоя (краткосрочная/рабочая/долговременная) | 5001 |
| 2 | Персонализация: профиль пользователя | 5002 |
| 3 | Состояние задачи как FSM (planning→execution→validation→done) | 5003 |
| 4 | Инварианты проекта + страж-проверка | 5004 |
| 5 | Контролируемый жизненный цикл: явные переходы + гейты | 5005 |

### Week 4 — MCP (Model Context Protocol)

| День | Тема |
|---|---|
| 1 | MCP-клиент: подключение + список инструментов |
| 2 | Свой MCP-сервер вокруг API (CRM) + агент вызывает инструмент |
| 3 | MCP-инструмент с периодическим выполнением (планировщик 24/7) |
| 4 | Автоматический пайплайн: search → summarize → save_to_file |
| 5 | Несколько MCP-серверов + маршрутизация + длинный флоу |

### Week 5 — RAG (индексация и поиск по документам)

| День | Тема | Порт |
|---|---|---|
| 1 | Локальный индекс: chunking (2 стратегии) + эмбеддинги + сравнение | — |
| 2 | RAG-агент (с RAG / без RAG) + 10 контрольных вопросов | — |
| 3 | Улучшенный RAG: реранкинг + фильтр по порогу + query rewrite | — |
| 4 | Обязательные источники+цитаты + режим «не знаю» | — |
| 5 | Мини-чат на Flask: RAG + источники + память задачи | 5006 |

### Week 6 — Локальные LLM

| День | Тема | Порт |
|---|---|---|
| 1 | Ollama + qwen2.5:1.5b: локальный запуск, CLI + HTTP API, 3 запроса | — |
| 2 | Веб-приложение (Flask) на локальной LLM: стриминг ответов, офлайн | 5007 |
| 3 | RAG полностью локально (retrieval + генерация) + сравнение с облаком | — |
| 4 | Оптимизация локальной модели: параметры + prompt + квантование | — |
| 5 | Приватный AI-сервис на локальной LLM для VPS: HTTP API + auth + rate limit + Docker/nginx | 5008 |

### Week 7 — Ассистент разработчика

| День | Тема | Порт |
|---|---|---|
| 1 | Ассистент, понимающий проект: RAG по докам (README/docs/claude) + git через MCP + `/help` | 5009 |

---

## Технологии по неделям

- **Weeks 1–3:** DeepSeek API (`deepseek-v4-flash` / `deepseek-v4-pro`),
  Flask, SQLite (WAL), `marked.js` для Markdown.
- **Week 4:** MCP Python SDK (`mcp`), FastMCP-серверы (stdio), tool-calling
  через `AsyncOpenAI`.
- **Week 5:** локальные эмбеддинги `fastembed` (ONNX, мультиязычная модель),
  cross-encoder reranker, SQLite/JSON-индекс. DeepSeek не даёт embeddings —
  эмбеддинги считаются локально.
- **Week 6:** локальные LLM через **Ollama** (`qwen2.5:1.5b`), полностью
  офлайн; веб-чат со стримингом, локальный RAG, оптимизация (параметры/квант),
  приватный сервис для VPS (Flask + auth + rate limit + Docker/nginx/systemd).

---

## Запуск любого дня

Дни на **DeepSeek** (weeks 1–5, week 6 / day 3 для облачного сравнения) — нужен ключ:

```bash
cd "week N/day M"
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
export DEEPSEEK_API_KEY="ваш_ключ"

python app.py         # Flask-приложения (week 2/3/5) — порт см. в таблицах
python client.py      # CLI (week 4 MCP)
```

Дни на **локальной LLM** (week 6) — нужен запущенный [Ollama](https://ollama.com):

```bash
ollama pull qwen2.5:1.5b               # один раз
cd "week 6/day M" && python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt        # без DEEPSEEK_API_KEY
python app.py                          # или query_local.py / compare.py — см. README дня
```

> week 6 / day 1 — на чистом stdlib, без venv: `python3 query_local.py`.
> Деплой приватного сервиса на VPS — гайд в `week 6/day 5/README.md`.

Детали, проверки и результаты — в `README.md` каждого дня.

---

## Замечания

- API-ключи **не хранятся** в коде — только через `os.environ`.
- Каждый день изолирован в своём `venv/` (не коммитится).
- Индексы, БД и модели fastembed генерируются локально (в `.gitignore`);
  корпус документов для RAG (week 5) — в репозитории как входные данные.
