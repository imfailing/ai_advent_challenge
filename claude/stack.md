# Стек, паттерны и предпочтения

---

## Окружение

- **Python:** 3.13 (Homebrew: `/opt/homebrew/bin/python3.13`)
- **venv:** `python3.13 -m venv venv` — отдельный для каждого дня
- **Git:** репо в `/Users/asv1337/dev/ai_advent_challenge`, ветка `main`
- **gh CLI:** установлен и авторизован

---

## Предпочтения

| Тема | Правило |
|---|---|
| Язык общения | Русский |
| Стиль кода | Python 3.13, строгая типизация (`str \| None`, dataclasses, frozen) |
| API-ключи | Только через `os.environ["KEY"]`, никогда не хардкодить |
| Результаты экспериментов | Сохранять в `results.md` рядом с кодом |
| Коммиты | После каждого завершённого дня/фичи + push |

---

## Создание нового дня

```bash
mkdir -p "week N/day N"
cd "week N/day N"
/opt/homebrew/bin/python3.13 -m venv venv
./venv/bin/pip install -q --upgrade pip <deps>
# ... написать код, запустить, сохранить вывод
pip freeze > requirements.txt
git add <конкретные файлы>   # не venv/, не индексы/БД (index.db, chat.db)
git commit -m "week N/day N: описание"
git push
```

> `claude/` теперь **в git** (контекст-доки). Секреты в них — только плейсхолдеры;
> реальные ключи — в окружении. Перед коммитом проверять отсутствие ключей:
> `grep -rnE "sk-[a-z0-9]{20}" .`

### .gitignore (стандартный для каждого дня)

```
__pycache__/
*.pyc
.env
venv/
```

### Структура каждого дня (Week 1)

```
day N/
├── script.py         # основной скрипт
├── output_raw.txt    # реальный вывод при запуске
├── results.md        # сравнение / выводы
└── README.md         # установка + запуск
```

### Структура каждого дня (Week 2 — Flask)

```
day N/
├── app.py            # Flask: маршруты
├── agent.py          # LLMAgent
├── database.py       # SQLite-хелперы
├── models.py         # реестр моделей (с day 3)
├── file_parser.py    # парсинг файлов (с day 3)
├── templates/
│   └── index.html
├── requirements.txt
└── README.md
```

---

## Flask-приложения

- `debug=True, port=5000`
- Сессии: `flask.session` → UUID → `session["id"]`
- Per-session агенты: `_agents: dict[str, LLMAgent]` в памяти процесса
- Ошибки: `@app.errorhandler(413/500)` всегда возвращают JSON
- `app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024`

## Frontend

- Markdown: `marked.js` + `highlight.js` через CDN (без сборки)
- Fetch API: проверять `Content-Type: application/json` перед `.json()` — использовать хелпер `safeJson(res)`:

```js
async function safeJson(res) {
    const ct = res.headers.get("content-type") || "";
    if (!ct.includes("application/json")) {
        return { error: `Сервер вернул ошибку ${res.status}: ${await res.text()}` };
    }
    return res.json();
}
```

## SQLite

- WAL-режим (`PRAGMA journal_mode=WAL`) для надёжности
- Таблицы: `sessions`, `messages` (с `prompt_tokens`, `completion_tokens`), `context_files`
- История подгружается при `LLMAgent.__init__()` как контекст LLM, но НЕ отображается в UI при перезагрузке страницы

## Модельный реестр (с week 2 / day 3)

```python
@dataclass(frozen=True)
class ModelInfo:
    id: str
    name: str
    description: str
    context_window: int
    max_output: int
    price_input_1m: float
    price_output_1m: float
    supports_thinking: bool

MODELS: dict[str, ModelInfo] = { ... }
DEFAULT_MODEL = "deepseek-v4-flash"   # deepseek-chat/-reasoner — устаревшие алиасы
```

---

## Порты Flask-приложений (важно — у каждого свой)

| Приложение | Порт |
|---|---|
| week 2 (day 1–5) | 5000 |
| week 3 day 1 (память) | 5001 |
| week 3 day 2 (профиль) | 5002 |
| week 3 day 3 (FSM) | 5003 |
| week 3 day 4 (инварианты) | 5004 |
| week 3 day 5 (жизненный цикл) | 5005 |
| week 5 day 5 (RAG-чат) | 5006 |
| week 6 day 2 (локальный LLM-чат) | 5007 |
| week 6 day 5 (приватный AI-сервис) | 5008 |
| week 7 day 1 (ассистент разработчика) | 5009 |
| week 7 day 3 (ассистент поддержки) | 5010 |
| week 7 day 5 (анализ GitHub-репо) | 5011 |

Разные порты — чтобы запускать параллельно. week 4 (MCP) и week 6 day 1 — CLI.

## Week 6 — локальные LLM (Ollama)

- Ollama на машине (`/usr/local/bin/ollama`, 0.31.2), сервер `localhost:11434`.
  Модель: `qwen2.5:1.5b` (986 MB). Скачать: `ollama pull <model>`.
- Нативный API: `/api/chat` (stream=true → JSONL по токенам), `/api/tags`
  (модели), `/api/version`. Клиент — только stdlib `urllib`, без облачных SDK.
- Есть и OpenAI-совместимый `/v1/chat/completions` — можно openai-SDK со сменой
  base_url на `http://localhost:11434/v1`.
- Flask-стриминг: `Response(stream_with_context(gen), mimetype="application/x-ndjson")`,
  генератор копит токены и сохраняет полный ответ в finally.
- Маленькая 1.5B модель ошибается на логических задачах — для рассуждений нужна 7b+.
- Параметры инференса — поле `options` в /api/chat: temperature, num_predict
  (макс токенов ответа), num_ctx (окно; меньше = меньше RAM под KV-кэш), top_p,
  repeat_penalty. Квантование: `qwen2.5:1.5b` (Q4_K_M) vs `…-instruct-q8_0` (Q8).
  Ресурсы: `ollama ps` (RAM), `ollama list` (диск).
- RAG локально (day 3): retrieval на локальных моделях (fastembed + rerank),
  генерация local|cloud — локальная 1.5B быстрее облака (нет сети).
- day 1 БЕЗ venv (stdlib) → запуск `python3 …`, не `python` (на macOS нет `python`).

### Деплой сервиса на VPS (day 5) — частые грабли

- `docker-compose.yml`: наружу только порт API (5008), Ollama во внутренней
  сети. Прод-запуск gunicorn (gthread, чтобы стрим не блокировал воркер).
- «unknown shorthand flag: 'd' in -d» / «unknown command: docker compose» →
  нет плагина Compose V2. Ставить: `apt install docker-compose` (V1, команда
  `docker-compose up -d`) ИЛИ бинарь плагина
  `docker-compose-linux-$(uname -m)` в `/usr/local/lib/docker/cli-plugins/`
  (lowercase `linux`!). Флаг `-d` — ПОСЛЕ `up`.
- «Unable to locate package docker-compose-plugin» → нет офиц. apt-репо Docker.
- «permission denied /var/run/docker.sock» → `usermod -aG docker $USER` +
  релогин/`newgrp docker`, либо `sudo docker …`.
- Без Docker — systemd-юнит `deploy/llm-service.service` + `ollama serve`.

---

## Week 4 — MCP (Model Context Protocol)

- SDK: `pip install mcp` (v1.28.1). Не нужен API-ключ для клиента/сервера,
  ключ нужен только агенту (tool-calling).
- Сервер: `FastMCP("name")` + `@mcp.tool()` (типы+docstring → JSON-схема), `mcp.run()` (stdio).
- Клиент: `stdio_client(StdioServerParameters)` → `ClientSession` → `initialize()` → `list_tools()`.
- Агент async (`AsyncOpenAI`), `AsyncExitStack` для вложенных контекстов.
- Грабли: FastMCP оборачивает list-результат в `structuredContent={"result":[...]}`,
  dict-результат → `structuredContent=None` (парсить `content[i].text`). MCP-подпроцесс
  НЕ наследует кастомные env (нужен `StdioServerParameters(env=...)`).
- Мультисервер: неймспейс `label__tool` + таблица маршрутов `name→(session,tool,label)`.

## Week 5 — RAG (эмбеддинги, индекс, реранкинг)

- Эмбеддинги: `pip install fastembed` (ONNX, без torch). Мультиязычная модель
  `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (384-dim, RU+код).
  **DeepSeek embeddings НЕТ (404)** — считаем локально.
- Реранкер: `fastembed.rerank.cross_encoder.TextCrossEncoder`,
  `jinaai/jina-reranker-v2-base-multilingual` (сырые скоры → сигмоида → 0..1).
- Индекс: SQLite (эмбеддинги BLOB) + JSON-манифест, косинус на numpy (векторы L2-норм).
- Пайплайн переиспользуется между днями (loader/chunking/embedder/index_store копируются).
- JSON-ответ модели: `response_format={"type":"json_object"}` (DeepSeek поддерживает).
- PDF: чтение `pypdf`, генерация тестового — `reportlab`.

---

## Проверка дня (общий подход)

- Каждый день — тест-скрипт с ассертами (`test_*.py`), гоняется реально
  (с `DEEPSEEK_API_KEY` где нужен LLM).
- Flask-роуты удобно проверять через `app.test_client()` — dev-сервер с
  debug-reloader медленно стартует в фоне.
- Прогоны с LLM недетерминированы (особенно query rewrite) — возможна
  вариативность метрик между запусками; отчёты честные, без подгонки.
