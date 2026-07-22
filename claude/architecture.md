# Архитектура приложений — ai_advent_challenge

Проект развивается линейно: каждый день добавляет новый слой поверх предыдущего.
Week 1 — изолированные консольные скрипты. Week 2 — один Flask-сервис, который
растёт от сессии в памяти до полноценного агента с БД, файлами и реестром моделей.

---

## Обзор эволюции

```
Week 1 / Day 1   ask(prompt) → str                          один файл, один вызов API
Week 1 / Day 2   ask(prompt, max_tokens, stop) → str        + контроль формата
Week 1 / Day 3   direct / step_by_step / meta / experts     + 4 стратегии промптинга
Week 1 / Day 4   ask(prompt, temperature) × 3 temp × 3 run  + влияние temperature
Week 1 / Day 5   ask_gigachat + ask_deepseek × 2 models     + второй API, сравнение

Week 2 / Day 1   Flask + LLMAgent (история в памяти)        + веб-интерфейс, сессии
Week 2 / Day 2   + database.py (SQLite)                     + персистентность истории
Week 2 / Day 3   + models.py + file_parser.py               + токены/стоимость, файлы, выбор модели
Week 2 / Day 4   + summaries table + _maybe_summarize()     + компрессия: старое → суммари
Week 2 / Day 5   + branches + facts tables + 3 стратегии    + Sliding Window / Sticky Facts / Branching

Week 3 / Day 1   3 таблицы памяти + LLM-маршрутизатор        + явная модель памяти (memory layers)
Week 3 / Day 2   + таблица profiles + инжект в промпт        + персонализация (профиль → стиль ответа)
Week 3 / Day 3   + statemachine.py + task_state + переходы   + формализованное состояние задачи (FSM)
Week 3 / Day 4   + таблица invariants + страж-проверка       + работа в рамках инвариантов (отказ при конфликте)
Week 3 / Day 5   + гейты на переходах + check_transition     + контролируемый жизненный цикл (нельзя перепрыгнуть)

Week 4 / Day 1   mcp SDK: stdio_client + ClientSession       + подключение к MCP, list_tools
Week 4 / Day 2   свой MCP-сервер (FastMCP) + tool-calling    + агент вызывает MCP-инструмент CRM
Week 4 / Day 3   фоновый Scheduler-поток + SQLite + сводки    + MCP-инструмент с периодическим выполнением (24/7)
Week 4 / Day 4   3 инструмента + агент-оркестратор цепочки    + автоматический пайплайн search→summarize→save
Week 4 / Day 5   3 MCP-сервера + неймспейс + маршрутизация    + длинный флоу с несколькими серверами

Week 5 / Day 1   loader+chunking+embedder+index_store        + локальный RAG-индекс + сравнение 2 chunking
Week 5 / Day 2   rag.py (retrieve→context→LLM) + eval-набор   + RAG vs без-RAG + 10 контрольных вопросов
Week 5 / Day 3   rerank (cross-encoder) + threshold + rewrite + улучшенный RAG: 2-й этап после поиска
Week 5 / Day 4   JSON-ответ + grounding цитат + know-gate     + обязательные источники/цитаты + «не знаю»
Week 5 / Day 5   Flask-чат + history + task_memory + RAG      + мини-чат: RAG + источники + память задачи

Week 6 / Day 1   Ollama + qwen2.5:1.5b (CLI + HTTP /api/chat) + локальная LLM запущена, 3 запроса
Week 6 / Day 2   Flask + стриминг из Ollama (порт 5007)       + веб-приложение на локальной LLM (офлайн)
Week 6 / Day 3   локальный retrieval + local|cloud генерация  + RAG полностью локально + сравнение с облаком
Week 6 / Day 4   Ollama options + prompt + Q4/Q8 квант        + оптимизация локальной модели под задачу
Week 6 / Day 5   Flask service + auth/ratelimit + Docker/nginx+ приватный AI-сервис для VPS (порт 5008)

Week 7 / Day 1   RAG по докам + git MCP + DeepSeek + /help    + ассистент разработчика (проект-aware, 5009)
Week 7 / Day 2   diff → RAG (доки+код) → ревью + Action        + авто-AI-ревью PR (GitHub Action)
Week 7 / Day 3   RAG по FAQ + тикеты через MCP (JSON)          + ассистент поддержки (контекст тикета, 5010)
Week 7 / Day 4   MCP fs (read/search/write) + работа по цели   + файловый ассистент (реальные операции)
Week 7 / Day 5   GitHub REST API + дайджест/роаст + Docker     + веб-сервис анализа удалённого репо (5011)
```

---

## Week 1 — Консольные скрипты

Каждый день — один автономный `.py`-файл. Нет сессий, нет персистентности,
нет классов (кроме day 5). Всё запускается как `python script.py`.

### Day 1 — `deepseek_chat.py`

```
env: DEEPSEEK_API_KEY
         │
         ▼
    OpenAI(base_url)
         │
    ask(prompt) ──► completions.create(model, messages)
         │
         ▼
      print(answer)
```

**Ключевые решения:** `openai` SDK с `base_url` для DeepSeek-совместимого API.
API-ключ только через `os.environ`. Один вызов — один ответ.

---

### Day 2 — `compare_responses.py`

```
BASE_PROMPT ──────────────────────────────► ask(prompt)           → print
                                                │
CONSTRAINED_PROMPT ──► ask(prompt,             │
  max_tokens=120,          max_tokens,          │
  stop=["КОНЕЦ"])          stop)      ──────────┘
```

Добавлены параметры `max_tokens` и `stop` в `completions.create`. Два запроса
с одним промптом — сравнение свободного и ограниченного ответа.

---

### Day 3 — `solve_task.py`

```
TASK (константа)
    │
    ├── direct_answer()       ask(TASK)
    │
    ├── step_by_step()        ask(TASK + "решай пошагово")
    │
    ├── generated_prompt()    ask(meta_prompt) → generated
    │                         ask(generated)   → solution
    │                         (два последовательных вызова API)
    │
    └── expert_panel()        ask(TASK + роли: Аналитик / Инженер / Критик)
```

Единственный клиент `OpenAI` инициализируется один раз на уровне модуля.
`generated_prompt()` делает **два последовательных** вызова: сначала генерирует
оптимальный промпт, затем использует его для решения.

---

### Day 4 — `temperature_compare.py`

```
TEMPERATURES = [0, 0.7, 1.2]
RUNS_PER_TEMPERATURE = 3

run_section(title, prompt):
    for temperature in TEMPERATURES:
        for i in range(RUNS_PER_TEMPERATURE):
            ask(prompt, temperature)   ─► print

запускается для двух промптов:
  CREATIVE_PROMPT  (слоган для кофейни — нет правильного ответа)
  FACTUAL_PROMPT   (17 × 24 = 408 — единственный правильный ответ)
```

Итого: **2 промпта × 3 температуры × 3 запуска = 18 вызовов API** за один run.
Клиент на уровне модуля, общий для всех вызовов.

---

### Day 5 — `compare_models.py`

```
env: DEEPSEEK_API_KEY, GIGACHAT_AUTH_KEY, GIGACHAT_SCOPE

MODELS = [
    ("Слабая",   ask_gigachat),       # requests + OAuth2 токен
    ("Средняя",  ask_deepseek(chat)), # openai SDK
    ("Сильная",  ask_deepseek(R1)),   # openai SDK
]

ask_gigachat(prompt):
    get_gigachat_token()          ──► POST oauth (Basic auth, verify=False)
    requests.post(API_URL, ...)   ──► возвращает {answer, elapsed, tokens, cost_usd=0}

ask_deepseek(prompt, model):
    client.completions.create()   ──► возвращает {answer, elapsed, tokens, cost_usd}

for title, runner in MODELS:
    result = runner(PROMPT)
    print(время, токены, стоимость, ответ)
```

**Ключевое:** два разных API с разной аутентификацией. GigaChat требует
предварительного получения OAuth2-токена через Basic auth. `verify=False` +
`urllib3.disable_warnings()` для обхода проблем с SSL-сертификатом Сбера.

---

## Week 2 — Flask-приложение

Один сервис, который эволюционирует три дня. Каждый день — новый слой поверх
предыдущего без слома существующего интерфейса.

### Общая схема (Day 3 — финальная)

```
Browser
  │  GET /
  │  POST /ask
  │  POST /clear
  │  GET /models, GET /model, POST /model
  │  POST /upload, GET /context, DELETE /context/<id>
  │  GET /sessions
  ▼
app.py  ──  get_agent()  ──►  _agents: dict[str, LLMAgent]
  │                                │
  │                         agent.py (LLMAgent)
  │                                │
  │                    ┌───────────┴───────────────┐
  │                    │                           │
  │              models.py                   database.py
  │          (ModelInfo, MODELS)          (SQLite, WAL)
  │                                             │
  │                                    sessions / messages
  │                                     / context_files
  │
  └──  file_parser.py  (extract_text, PDF + text)
```

---

### Day 1 — `agent.py` + `app.py`

**Новое:** веб-интерфейс, сессии, история в памяти процесса.

```
app.py:
  _agents: dict[str, LLMAgent]   # session_id → агент

  get_agent():
    session["id"] = uuid4()      # flask.session cookie
    _agents[sid] = LLMAgent()    # история только в памяти

  POST /ask  →  agent.ask(msg)  →  {answer, model, tokens, elapsed, turn}
  POST /clear →  agent.clear_history()

agent.py:
  LLMAgent.__init__(api_key, model, system_prompt):
    self._history = []           # только в памяти

  ask(user_message) → AgentResponse:
    _history.append(user)
    completions.create(system + history)
    _history.append(assistant)
    return AgentResponse(answer, tokens, elapsed, turn)
```

**Ограничение:** перезапуск сервера = потеря истории всех сессий.

---

### Day 2 — добавлен `database.py`

**Новое:** персистентная история в SQLite. `LLMAgent` теперь принимает `session_id`.

```
database.py:
  Схема: sessions(id, created_at, updated_at)
         messages(id, session_id, role, content, created_at)

  init_db()           — создать таблицы
  ensure_session(id)  — INSERT OR IGNORE
  save_message(id, role, content)
  load_history(id) → [{role, content}, ...]
  clear_history(id)
  list_sessions() → [{id, created_at, updated_at, message_count}]

agent.py (изменения):
  __init__(session_id, ...):
    db.ensure_session(session_id)
    self._history = db.load_history(session_id)   # ← загружаем из БД

  ask():
    db.save_message(session_id, "user", ...)      # ← сохраняем оба конца
    db.save_message(session_id, "assistant", ...)

  clear_history():
    db.clear_history(session_id)                  # ← удаляем из БД тоже
```

**Важное UX-решение:** история при перезагрузке страницы **не отображается
в чате** (пользователь явно попросил), но передаётся модели как контекст.

---

### Day 3 — добавлены `models.py` и `file_parser.py`

**Новое:** подсчёт токенов/стоимости, загрузка файлов контекста, выбор модели.

#### `models.py` — реестр моделей

```python
@dataclass(frozen=True)
class ModelInfo:
    id, name, description
    context_window, max_output    # int, токены
    price_input_1m, price_output_1m  # float, USD
    supports_thinking             # bool (CoT)
    to_dict() → dict

MODELS = {
    "deepseek-v4-flash": ModelInfo(ctx=1_000_000, out=384_000, in=0.14,   out=0.28,  cot=False),
    "deepseek-v4-pro":   ModelInfo(ctx=1_000_000, out=384_000, in=0.435,  out=0.87,  cot=True),
}
DEFAULT_MODEL = "deepseek-v4-flash"
# Алиасы deepseek-chat / deepseek-reasoner удаляются 24.07.2026
get_model(id) → ModelInfo   # ValueError если неизвестный
```

#### `file_parser.py` — извлечение текста

```
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB
SUPPORTED_TEXT_EXTENSIONS = {
    ".txt", ".md", ".py", ".js", ".ts", ".json",
    ".csv", ".yaml", ".yml", ".html", ".xml", ".sql"
}

extract_text(filename, data: bytes) → str
    │
    ├── len(data) > 5MB → ValueError
    │
    ├── ext == ".pdf"  → _extract_pdf()   pypdf.PdfReader(BytesIO)
    │
    ├── ext in TEXT_EXTS → _extract_text()
    │                       пробуем: utf-8 → utf-8-sig → cp1251 → latin-1
    │
    └── иначе → ValueError (формат не поддерживается)
```

#### `database.py` (расширения)

```
Новые таблицы/колонки:
  messages.prompt_tokens, messages.completion_tokens  (только для assistant-строк)
  context_files(id, session_id, filename, content, size_chars, created_at)

Новые функции:
  save_user_message(session_id, content)
  save_assistant_message(session_id, content, prompt_tokens, completion_tokens)
  get_session_token_totals(session_id) → {turns, total_prompt, total_completion, total_tokens, total_cost_usd}
  save_context_file(session_id, filename, content) → int   # возвращает id
  load_context_files(session_id) → [{id, filename, content, size_chars, created_at}]
  delete_context_file(file_id, session_id) → bool
  clear_context_files(session_id)
```

> Стоимость в `database.py` — только агрегат для `list_sessions()`.  
> Стоимость текущего запроса считается в `agent.py` по тарифам активной модели.

#### `agent.py` (расширения)

```python
# Новые dataclass-ы
TokenUsage:   prompt_tokens, completion_tokens, total_tokens, cost_usd
SessionStats: turns, total_prompt, total_completion, total_tokens, total_cost_usd

# LLMAgent
set_model(model_id) → ModelInfo      # переключение на лету
model_info property → ModelInfo

ask():
    # Инжекция файлов в системный промпт
    files = db.load_context_files(session_id)
    extra = "### Файл: {filename}\n\n{content}" для каждого файла
    messages = [system + extra, *history]

    # Стоимость по тарифам активной модели
    cost = (prompt * model.price_input_1m + completion * model.price_output_1m) / 1_000_000

    return AgentResponse(answer, elapsed, model, turn,
                         usage=TokenUsage(...), session=SessionStats(...))
```

#### Маршруты `app.py`

```
GET  /           → index.html
POST /ask        → agent.ask() → {answer, model, elapsed, turn, usage{…}, session{…}}
POST /clear      → agent.clear_history()
GET  /models     → [ModelInfo.to_dict(), ...]
GET  /model      → agent.model_info.to_dict()
POST /model      → agent.set_model(model_id) → ModelInfo.to_dict()
POST /upload     → file_parser.extract_text() → db.save_context_file() → {id, filename, size_chars, preview}
GET  /context    → db.load_context_files() (без content)
DEL  /context/id → db.delete_context_file()
GET  /sessions   → db.list_sessions()
```

#### Важные детали Day 3

- История при перезагрузке страницы **не показывается в UI** — только используется как контекст LLM (явное требование пользователя)
- Входные токены растут с каждым ходом: запрос = системный промпт + вся история + все файлы
- Стоимость одного запроса считается в `agent.py`, суммарная по сессии — агрегируется из `messages` в `database.py`

---

## Зависимости между модулями (Day 3)

```
app.py
  ├── agent.py
  │     ├── models.py        (ModelInfo, get_model)
  │     └── database.py      (load_history, save_*, get_session_token_totals, load_context_files)
  ├── database.py            (init_db, save_context_file, load_context_files, delete_context_file)
  ├── file_parser.py         (extract_text)
  └── models.py              (MODELS — для GET /models)
```

`models.py` и `file_parser.py` — листья без зависимостей.  
`database.py` зависит только от stdlib (`sqlite3`, `pathlib`, `datetime`).  
`agent.py` зависит от `models.py` и `database.py`.  
`app.py` — точка входа, зависит от всего.

---

## Frontend (Week 2 / Day 3)

```
index.html (один файл, без сборки)

CDN:  marked.js (Markdown → HTML)
      highlight.js (подсветка синтаксиса)

Панели:
  ┌─────────────────────┬─────────────────────┐
  │       Чат           │  🧠 Модель           │
  │                     │  • select + описание │
  │  [сообщения]        │  • параметры         │
  │                     │  • тарифы, CoT-бейдж │
  │  [input + send]     ├─────────────────────┤
  │                     │  Текущий запрос      │
  │                     │  • tokens in/out     │
  │                     │  • стоимость, время  │
  │                     ├─────────────────────┤
  │                     │  📎 Файлы контекста  │
  │                     │  • чипы файлов       │
  │                     │  • кнопка загрузки   │
  │                     ├─────────────────────┤
  │                     │  Сессия накопленно   │
  │                     │  • tokens, стоимость │
  └─────────────────────┴─────────────────────┘

Ключевые JS-функции:
  safeJson(res)        — проверяет Content-Type перед .json()
  switchModel(id)      — POST /model → renderModelInfo()
  uploadFiles(files)   — POST /upload для каждого файла
  deleteFile(id, btn)  — DELETE /context/{id}

При загрузке:
  Promise.all([fetch("/models"), fetch("/model")])  → populate selector
  fetch("/context")                                 → restore file chips
```

---

---

## Week 2 / Day 4 — Компрессия контекста (суммаризация)

**Новое:** вместо бесконечного роста истории — суммаризация старых сообщений.

### Алгоритм

```
Constants:
  RECENT_KEEP = 10    # всегда держать последние N сообщений сырыми
  SUMMARY_BATCH = 10  # суммаризировать батчами по N

_maybe_summarize():
  while unsummarized_count > RECENT_KEEP + SUMMARY_BATCH:
      batch = get_messages_after(last_summarized_id)[:SUMMARY_BATCH]
      summary_text = _create_summary(batch)   # отдельный вызов LLM
      save_summary(from_id, to_id, summary_text)

_build_messages():
  summaries = load_summaries(session_id)
  # Вставляем в системный промпт:
  # "## Краткое содержание предыдущего диалога\n<summary1>\n<summary2>..."
  recent = get_recent_messages(session_id, RECENT_KEEP)
  return [system_with_summaries] + recent
```

### Новые таблицы / функции database.py

```
summaries(id, session_id, content, from_message_id, to_message_id, message_count, created_at)

get_messages_after(session_id, after_id) → messages with id > after_id
get_recent_messages(session_id, limit)   → последние N (хронологически)
get_last_summarized_message_id(session_id) → MAX(to_message_id) или 0
save_summary(session_id, content, from_id, to_id, message_count) → int
load_summaries(session_id) → list[dict]
get_total_message_count(session_id) → int
save_user_message()         → возвращает lastrowid (int)
```

### Поле `context` в ответе `/ask` (Day 4)

```json
{
  "total_messages": 35,
  "summaries_count": 2,
  "summarized_messages": 25,
  "raw_in_context": 10
}
```

### UI (Day 4)

Новая карточка "🗜 Компрессия контекста":
- Прогресс-бар: суммаризованные vs сырые сообщения
- Фиолетовый пузырь в чате при появлении нового суммари
- Бейдж "🗜 N суммари" в шапке

---

## Week 2 / Day 5 — Три стратегии управления контекстом

**Новое:** переключатель между тремя принципиально разными способами управлять
тем, что попадает в LLM при длинном диалоге.

### Стратегии

```
STRATEGY_SLIDING_WINDOW = "sliding_window"
  → только последние WINDOW_SIZE=10 сообщений; остальное отбрасывается

STRATEGY_STICKY_FACTS = "sticky_facts"
  → после каждого хода отдельный LLM-вызов извлекает ключевые факты (KV-dict)
  → в запрос: факты в system prompt + последние WINDOW_SIZE сообщений

STRATEGY_BRANCHING = "branching"
  → диалог разветвляется от точки основной ветки
  → в запрос: полная история ветки (main до fork + branch сообщения), без обрезки
```

### Схема БД (расширения относительно Day 3)

```sql
sessions: + strategy TEXT DEFAULT 'sliding_window'
          + current_branch_id INTEGER

messages: + branch_id INTEGER  (NULL = основная ветка)

branches(id, session_id, name, forked_at_message_id, created_at)

facts(id, session_id, key, value, updated_at, UNIQUE(session_id, key))
```

### История ветки (ключевой SQL)

```sql
-- Основная ветка:
SELECT role, content FROM messages
 WHERE session_id=? AND branch_id IS NULL ORDER BY id

-- Дочерняя ветка X:
SELECT id, role, content FROM messages
 WHERE session_id=? AND branch_id IS NULL AND id <= forked_at_message_id
UNION ALL
SELECT id, role, content FROM messages
 WHERE session_id=? AND branch_id=?
ORDER BY id
```

### Новые маршруты app.py (Day 5)

```
GET  /strategy          → {strategy, branch_id}
POST /strategy          → {strategy: "sliding_window|sticky_facts|branching"}
GET  /branches          → [{id, name, forked_at_message_id, created_at}, ...]
POST /branches          → {name} → создать ветку (только из основной)
POST /branches/switch   → {branch_id: int|null} → переключить ветку
GET  /facts             → {key: value, ...}
```

### Поле `context` в ответе `/ask` (Day 5)

```json
{
  "strategy": "sticky_facts",
  "total_messages": 14,
  "messages_in_context": 10,
  "dropped_messages": 4,
  "facts": {"цель проекта": "...", "бюджет": "500K"},
  "branch_id": null,
  "branch_name": "Основная ветка"
}
```

### UI (Day 5)

3 кнопки-переключателя стратегии. Карточка меняется при переключении:
- **Sliding Window card:** total / in-context / dropped + прогресс-бар
- **Sticky Facts card:** таблица извлечённых фактов (обновляется после каждого хода)
- **Branching card:** список веток, кнопка создания, клик для переключения

Стратегия и текущая ветка сохраняются в БД → восстанавливаются при перезагрузке страницы.

### Зависимости (Day 5)

```
app.py
  ├── agent.py
  │     ├── models.py
  │     └── database.py   (branches, facts, get_history с UNION ALL)
  ├── database.py
  ├── file_parser.py
  └── models.py
```

### Извлечение фактов (_extract_facts)

```python
# Вызывается после каждого хода в режиме sticky_facts
# Берёт последние 6 сообщений + текущие факты JSON
# Промпт: "Верни ТОЛЬКО валидный JSON, без markdown"
# Strips ```json blocks → json.loads() → db.save_facts()
# Весь вызов обёрнут в try/except — ошибка не прерывает основной ответ
```

### Инвариант ContextStats (важно!)

```
total_messages = messages_in_context + dropped_messages   — всегда
```

Все три поля пересчитываются **после** `save_assistant_message()` из одного `get_history()`.
До этого фикса `total_messages` и `dropped_messages` считались в разные моменты → инвариант нарушался.

### Сравнительный тест (12 ходов, сценарий «сбор ТЗ»)

```
Метрика                    Sliding    Sticky   Branching
Токенов в промптах (итого)  28 618    29 787     48 448
Стоимость, USD              $0.007    $0.007     $0.011
Средний промпт / ход         2 385     2 482      4 037
Сообщений в посл. запросе       10        10         24
Потеря фактов                   ⚠️        ✅         ✅
```

Отчёт: week 2/day 5/STRATEGY_COMPARISON.md  
Тест-скрипт: week 2/day 5/test_strategies.py

**Когда использовать:**
- Sliding Window → чат-поддержка, FAQ, короткие диалоги без накопления знаний
- Sticky Facts   → сбор требований, брифы, длинные структурированные сессии
- Branching      → исследование вариантов решений, A/B диалоги

---

## Week 3 / Day 1 — Явная модель памяти (memory layers)

**Новое:** информация разделена на 3 типа, каждый — в отдельной таблице.
Порт 5001 (не 5000). Нет file_parser — приложение сфокусировано на памяти.

### Три слоя (database.py)

```
🔵 КРАТКОСРОЧНАЯ  messages(id, session_id, role, content, ...)
    окно последних SHORT_TERM_WINDOW=10 сообщений → уходит как reply-сообщения
    clear_short_term() — очистка ТОЛЬКО диалога

🟡 РАБОЧАЯ        working_memory(session_id, task, key, value, UNIQUE(session_id,key))
    key-value данные текущей задачи → инжект в system prompt
    upsert_working / clear_working / set_active_task

🟢 ДОЛГОВРЕМЕННАЯ long_term_memory(session_id, category, content,
                                   UNIQUE(session_id, category, content))
    category ∈ {profile, decision, knowledge} → инжект в system prompt
    add_long_term (с дедупликацией) / переживает очистку диалога
```

### Сборка запроса (agent.py _make_system + _build_messages)

```
system: базовая роль
      + ## Долговременная память (### Профиль / ### Решения / ### Знания)
      + ## Рабочая память (текущая задача: X)
messages: последние 10 сообщений диалога
```

### Маршрутизация _route_memory() — «что и куда»

```
После каждого хода отдельный вызов LLM классифицирует обмен репликами:
  → JSON {task, working:{k:v}, long_term:[{category, content}]}
  → пишет в соответствующие таблицы
  → возвращает last_writes для отображения в UI (блок «🧭 Маршрутизация»)
auto_route можно выключить тумблером; есть и ручное API на каждый слой.
```

### Ключевая проверка влияния

```
После clear_short_term() (диалог=0) агент всё равно отвечает корректно,
т.к. имя/стек/решения лежат в long_term + working. Доказывает разделение слоёв.
```

### Маршруты app.py

```
POST /ask · POST /clear (только 🔵)
GET  /memory (снимок всех слоёв) · POST /memory/auto-route
POST /memory/task · POST/DELETE /memory/working[/<key>]
POST /memory/long-term · DELETE /memory/long-term/<id>
```

---

## Week 3 / Day 2 — Персонализация (профиль пользователя)

**Новое:** персонализация поверх памяти day 1. Порт 5002.

### Профиль (database.py)

```
profiles(id, session_id, name, role, expertise, tone, verbosity,
         answer_format, language, constraints, created_at, updated_at)
sessions.active_profile_id — подключённый профиль

enum-поля: EXPERTISE_LEVELS, TONES, VERBOSITY_LEVELS, LANGUAGES
PROFILE_FIELDS — словарь полей со значениями по умолчанию
Несколько профилей на сессию → переключение для сравнения персон.
```

### Подключение к запросу (agent._format_profile → _make_system)

```
Профиль кладётся ПЕРВЫМ в system prompt (до памяти), как явные инструкции:
  expertise → глубина/пояснение терминов
  verbosity → длина ответа
  tone      → тональность
  answer_format, constraints → формат и ограничения
Один вопрос + разные профили = разные ответы (test_profiles.py:
  новичок ≈300 токенов с аналогией; эксперт ≈1447 токенов с HATEOAS/RFC).
```

### Авто-учёт предпочтений

```
_route_memory получил поле prefs: роутер ловит ЯВНЫЕ просьбы пользователя
("отвечай кратко и дружелюбно") → db.update_profile(active) → tone/verbosity.
last_writes с layer='profile' показываются в UI плашкой автонастройки.
```

### Маршруты

```
GET/POST /profiles · PUT/DELETE /profiles/<id> · POST /profiles/activate
/ask возвращает поле profile (активный профиль на момент запроса)
```

### Исправленный баг (fix 6bc9ec2)

```
name входит в PROFILE_FIELDS И передаётся в create_profile() позиционно.
В app.py **fields содержал name → "multiple values for argument 'name'"
→ 500 → профиль не сохранялся/не выбирался.
Фикс: исключать name из **fields (k in PROFILE_FIELDS and k != "name").
Урок: при позиционном аргументе + **kwargs из словаря-источника
исключай дубль ключа.
```

---

## Week 3 / Day 3 — Состояние задачи как FSM

**Новое:** формализованное состояние задачи. Порт 5003. Построено на памяти day 1.

### Автомат (statemachine.py)

```
planning → execution → validation → done
validation → execution (доработка)
TRANSITIONS — словарь разрешённых переходов; can_transition() валидирует.
Любой недопустимый переход отклоняется, даже если LLM его предложит.
```

### Состояние (database.py: task_state, task_transitions)

```
task_state(session_id PK, task_name, stage, current_step,
           expected_action, status, ...)
  тройка: stage / current_step / expected_action
  status: active | paused  (ортогонально этапу)
task_transitions — лог всех переходов (from→to, note)
```

### Поведение (agent.py)

```
_make_system: состояние кладётся ПЕРВЫМ в промпт — агент всегда знает, где он
_advance_state: после хода LLM-контроллер предлагает next_stage/step/expected;
  переход применяется только если can_transition(); на паузе — заморожено
pause/resume/start_task/advance_manual/reset_task
```

### Ключевая проверка (test_fsm.py)

```
старт→planning→execution→ПАУЗА→[новый экземпляр агента, пустой RAM]→
восстановление из БД→resume→продолжение БЕЗ переспрашивания задачи.
Гард: на resume LLM прыгнула в done — контроллер разрешил только
валидный execution→validation.
```

---

## Week 3 / Day 4 — Инварианты проекта

**Новое:** нерушимые ограничения, которые агент не имеет права нарушать. Порт 5004.

### Хранение (database.py)

```
invariants(id, session_id, category, content, active, created_at)
INVARIANT_CATEGORIES = {architecture, tech_decision, stack, business_rule}
Хранятся ОТДЕЛЬНО от диалога, не очищаются с историей, можно вкл/выкл.
```

### Двухуровневая защита (agent.py)

```
1. Промпт: активные инварианты инжектятся ПЕРВЫМИ с жёсткими правилами
   (_INVARIANT_RULES): запрет нарушать, отказ при конфликте + объяснение
   + альтернатива; приоритет над просьбами пользователя.
2. Страж _check_compliance: после ответа LLM-аудитор проверяет ответ против
   инвариантов → Compliance{checked, compliant, refused, violations}.
   Отказ от нарушения = compliant=true, refused=true.
```

### Проверка (test_invariants.py)

```
4 инварианта (монолит / только Python / только PostgreSQL / данные в РФ).
Конфликт ("перепиши на Go+микросервисы+MongoDB+AWS") → агент отказывается,
перечисляет ВСЕ 4 нарушения + альтернатива (Yandex/VK Cloud). refused=true.
Совместимый ("ускорь SQL") → compliant=true, refused=false.
```

### Маршруты

```
GET/POST /invariants · POST /invariants/<id>/active · DELETE /invariants/<id>
POST /guard · /ask возвращает compliance
```

---

## Week 3 / Day 5 — Контролируемый жизненный цикл (явные переходы + гейты)

**Новое:** развитие FSM day 3 — переходы защищены условиями. Порт 5005.

### Гейты (statemachine.py)

```
GATES = {plan_approved, implementation_done, validation_passed}
TRANSITIONS: dict[(from,to)] -> [required gates]
  (planning, execution):  [plan_approved]        # нет реализации без плана
  (execution, validation):[implementation_done]
  (validation, done):     [validation_passed]    # нет финала без валидации
  (validation, execution):[]                      # возврат на доработку
check_transition(from, to, conditions) -> (ok, reason)
  ребра нет → «нельзя перепрыгивать этапы»; гейт не выполнен → «не выполнены условия»
```

### Хранение (database.py)

```
task_state.conditions — JSON булевых гейтов
task_transitions.accepted — 0 для отклонённых попыток (лог перепрыгиваний)
set_condition / log_rejected_transition
```

### Enforcement (agent.py)

```
transition(): ручной переход → ValueError(reason) при отказе + log_rejected
_advance_state(): авто-контроллер ставит гейты (set_gates) по факту из диалога,
  переход применяется только если check_transition() разрешает, иначе rejected-событие
_make_system: в промпт идёт статус каждого гейта (✅/❌) + что заблокировано и почему
```

### Проверки (test_lifecycle.py)

```
planning→done / planning→validation → отклонены (перепрыгивание)
planning→execution без plan_approved → отклонён (гейт)
«сразу пиши код без плана» → агент остаётся на planning, ссылается на гейт
валидный путь через гейты до done; пауза→новый экземпляр→гейты восстановлены из БД
```

---

## Week 4 / Day 1 — Подключение к MCP

**Новое:** другой класс задач — MCP (Model Context Protocol), не Flask.
Официальный Python SDK `mcp` (v1.28.1). API-ключ не нужен, это CLI.

### Файлы

```
server.py — минимальный MCP-сервер на FastMCP, транспорт stdio
  @mcp.tool() add/multiply/echo/reverse; mcp.run() (stdio по умолчанию)
client.py — клиент: подключение + список инструментов
test_mcp.py — ассерты на соединение и список
```

### Паттерн клиента (важно для будущих дней недели 4)

```python
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

params = StdioServerParameters(command=sys.executable, args=["server.py"])
async with stdio_client(params) as (read, write):
    async with ClientSession(read, write) as session:
        init = await session.initialize()      # рукопожатие; init.serverInfo.name/version
        result = await session.list_tools()    # result.tools: name/description/inputSchema
        await session.call_tool("add", {"a":2,"b":3})  # .content[0].text
```

Заметки:
- сервер логирует "Processing request..." в stderr — это нормально.
- client.py поддерживает внешние серверы: `python client.py -- <cmd> <args>`
  (например `npx -y @modelcontextprotocol/server-everything`, нужен Node).
- inputSchema — JSON Schema; параметры в .properties; float-аргументы
  возвращаются как "5.0".

---

## Week 4 / Day 2 — Свой MCP-сервер вокруг API + агент

**Новое:** собственный MCP-сервер (FastMCP) вокруг mock CRM + агент на DeepSeek
с tool-calling, который вызывает MCP-инструменты. Нужен DEEPSEEK_API_KEY.

### Файлы

```
crm_api.py    — «внешний API»: mock CRM, данные в памяти (customers/deals/tickets)
mcp_server.py — FastMCP: 4 инструмента @mcp.tool() вокруг crm_api
                list_customers / get_customer / search_deals / create_ticket
agent.py      — MCPAgent: AsyncExitStack(stdio_client+ClientSession), async
app.py        — CLI: вопрос → агент → вызов инструмента → ответ
```

### Паттерн tool-calling через MCP (важно для недели 4)

```python
# 1. MCP inputSchema → OpenAI tools формат (схема уже совместима)
tools = [{"type":"function","function":{
    "name":t.name,"description":t.description,"parameters":t.inputSchema}} for t in mcp_tools]

# 2. цикл: модель возвращает tool_calls → исполняем через MCP → возвращаем результат
resp = await client.chat.completions.create(model, messages, tools=tools)
msg = resp.choices[0].message
if msg.tool_calls:
    messages.append({"role":"assistant","content":msg.content or "","tool_calls":[...]})
    for tc in msg.tool_calls:
        result = await session.call_tool(tc.function.name, json.loads(tc.function.arguments))
        text = result.content[0].text
        messages.append({"role":"tool","tool_call_id":tc.id,"content":text})
    # повторный вызов модели → финальный ответ использует результат
```

Заметки:
- агент async (AsyncOpenAI), т.к. MCP-клиент async. AsyncExitStack для
  управления вложенными async-контекстами (stdio_client → ClientSession).
- assistant-сообщение с tool_calls добавляем как dict (не pydantic-объект).
- call_tool возвращает .content[i].text (строки).

---

## Week 4 / Day 3 — MCP-инструмент с периодическим выполнением (24/7)

**Новое:** фоновый планировщик внутри MCP-сервера, периодический сбор + сводки.

### Файлы

```
collector.py — источник данных (mock-метрика active_users: синусоида+шум)
store.py     — SQLite: samples / reminders / summaries (каждая операция — своё соединение)
scheduler.py — Scheduler(threading.Thread, daemon): тик каждые interval сек:
                 collect→store, fire_due_reminders, каждые N тиков snapshot сводки
mcp_server.py— стартует Scheduler при импорте + 6 инструментов
agent.py     — копия day 2 (DeepSeek tool-calling), системный промпт под мониторинг
```

### Ключевые моменты

```
- Планировщик — daemon-поток, НИЧЕГО не пишет в stdout (там протокол MCP), только в БД.
- summary(minutes) — агрегат: count/avg/min/max/last + границы окна.
- add_reminder(text, in_seconds) — отложенное; fire_due_reminders помечает сработавшие.
- 3 требования задачи: данные в SQLite + по расписанию (поток) + агрегат (summary).
- ВАЖНО: MCP stdio_client НЕ наследует кастомные env подпроцессу-серверу
  (get_default_environment отдаёт только PATH и т.п.). SCHED_INTERVAL у сервера
  будет дефолтным; чтобы передать — StdioServerParameters(env={...}).
```

---

## Week 4 / Day 4 — Автоматический пайплайн из MCP-инструментов

**Новое:** цепочка search→summarize→save_to_file, агент проводит её автоматически.

### Файлы

```
corpus.py     — mock-корпус + search() (ранжирование по совпадению слов)
summarizer.py — детерминированная экстрактивная сводка (без LLM)
mcp_server.py — 3 инструмента: search / summarize / save_to_file (output/)
agent.py      — копия day 2, системный промпт «оркестратор пайплайна»
app.py        — одна инструкция → агент сам вызывает 3 инструмента по порядку
```

### Передача данных в цепочке

```
search(query) → [{id,title,text}]   агент склеивает тексты
  → summarize(text) → {summary, keywords, ...}   агент берёт summary
  → save_to_file(filename, content) → {path, bytes}
Выход шага = вход следующего. Порядок гарантируется промптом + проверяется тестом.
```

### Важно: формат результата FastMCP (грабли)

```
- Инструмент возвращает list → result.structuredContent = {"result": [...]}
  И каждый элемент кладётся ОТДЕЛЬНЫМ content-блоком (content[0]=item0, ...).
- Инструмент возвращает dict → structuredContent = None, данные в content[0].text.
- Надёжный парсинг: если structuredContent None → json.loads(склейка content.text);
  если {"result"} → разворачивать. Агент (day 2) склеивает все content.text —
  поэтому для list передаёт модели все элементы, работает само.
```

---

## Week 4 / Day 5 — Несколько MCP-серверов + маршрутизация

**Новое:** агент подключается к 3 серверам сразу и роутит вызовы между ними.

### Файлы

```
crm_server.py       — get_customer / search_deals
knowledge_server.py — search_docs / summarize
notes_server.py     — save_note / list_notes (JSON-хранилище notes.json)
agent.py            — MultiMCPAgent + ServerSpec + default_servers()
app.py / test_multi.py
```

### Паттерн мультисервера (важно)

```python
# подключение ко всем серверам через один AsyncExitStack
for spec in servers:
    read,write = await stack.enter_async_context(stdio_client(params))
    session    = await stack.enter_async_context(ClientSession(read,write))
    await session.initialize()
    for t in (await session.list_tools()).tools:
        oa_name = f"{spec.label}__{t.name}"            # неймспейс
        routes[oa_name] = (session, t.name, spec.label) # таблица маршрутов
        openai_tools.append({...name: oa_name...})

# при вызове модель шлёт label__tool → маршрутизируем по префиксу
session, real_tool, label = routes[oa_name]
await session.call_tool(real_tool, args)
```

Зачем неймспейс: избегает коллизий имён между серверами (напр. summarize мог бы
быть на нескольких) и явно показывает маршрутизацию. Имена OpenAI-функций —
`^[a-zA-Z0-9_-]+$`, поэтому разделитель `__`, не точка.

### Проверенный длинный флоу (test_multi.py)

```
get_customer(C-003) → search_deals(C-003,open) → search_docs(лицензир.)
→ summarize → save_note("Бриф C-003")   = 5 вызовов через 3 сервера, порядок ок
```

---

## Week 5 / Day 1 — Локальный RAG-индекс + сравнение chunking

**Новое:** класс задач RAG. Индексация документов, эмбеддинги, 2 стратегии chunking.

### Стек эмбеддингов (важно)

```
DeepSeek без embeddings (404) → fastembed (ONNX, без torch)
модель paraphrase-multilingual-MiniLM-L12-v2 (384-dim, мультиязычная для RU+код)
fastembed НЕ поддерживает intfloat/multilingual-e5-small под этим именем —
проверять TextEmbedding.list_supported_models(). Векторы L2-нормируем →
косинус = скалярное произведение.
```

### Файлы

```
loader.py      — обход corpus/, извлечение текста (.md/.txt/.py читать, .pdf pypdf)
                 doc = {path, filename, title, text, filetype}; title = первый md-заголовок
chunking.py    — fixed_size(800, overlap150) и structural (md→заголовки,
                 py→top-level def/class, txt/pdf→абзацы); _split_oversized до 1600
                 метаданные чанка: chunk_id/strategy/source/file/title/section/text/n_chars
embedder.py    — Embedder.embed(texts)->np(n,384) L2-норм; ленивая загрузка модели
index_store.py — SQLite index.db (chunks + embedding BLOB); init_db через
                 executescript (НЕ execute — «only one statement»);
                 build() пишет + дампит index_<strategy>.json; search() косинус numpy
build_index.py / compare_chunking.py / test_index.py
corpus/        — 14 файлов репо (~40 стр.), PDF сгенерён reportlab; коммитится
```

### Результат сравнения (корпус ~40 стр.)

```
fixed:      118 чанков, ср.737, std168, top-3 cos 0.574, метки fixed[i]
structural: 132 чанков, ср.543, std463, top-3 cos 0.567, метки — заголовки/имена функций
Вывод: ретрив близкий; structural выигрывает читаемостью section (навигация/цитирование).
```

---

## Week 5 / Day 2 — RAG-агент (с RAG / без RAG) + eval

**Новое:** RAG-функция и сравнение качества на 10 контрольных вопросах.
Пайплайн day 1 (loader/chunking/embedder/index_store + corpus) скопирован сюда.

### Файлы

```
rag.py       — RagAgent: ask_with_rag (embed→search top-k→context с [Источник N: file→section]
               →DeepSeek system «только по контексту, цитируй») и ask_plain (без контекста)
eval_set.py  — EVAL: 10 dict {question, expected[], expected_sources[], note}
evaluate.py  — оба режима × 10 Q; keyword_hit=доля expected в ответе (pass≥0.5),
               source_recall=есть ли expected_source среди найденных
app.py       — один вопрос в двух режимах
```

### Результат (честный)

```
без RAG 6/10, с RAG 9/10, source recall 10/10.
Там где модель НЕ знает специфику (save_to_file/инварианты/Scheduler) — 0%→100%.
Q1 «три стратегии» промах даже с RAG: structural разбил README по секциям,
каждая стратегия в своём чанке, ретрив не поднял все три в top-k (даже k=6).
Урок: RAG зависит от гранулярности чанков и k; для «списковых» вопросов
крупные/перекрывающиеся чанки (fixed) или больший k могут быть лучше.
```

---

## Week 5 / Day 3 — Улучшенный RAG (реранкинг + фильтр + rewrite)

**Новое:** второй этап после поиска. Строится на day 1/2.

### Файлы

```
rerank.py  — Reranker: fastembed TextCrossEncoder(jinaai/jina-reranker-v2-base-multilingual)
             .rerank(query, chunks, top_k, threshold, min_keep) → (kept, dropped)
             сигмоида скоров→0..1; порог + min_keep (fallback чтобы не вернуть пусто)
rewrite.py — QueryRewriter.rewrite(q)→[q, вариант1..3] через LLM (JSON-массив)
rag.py     — RagConfig(use_rewrite, use_rerank, top_n=12, top_k=4, threshold=0.3, min_keep=2)
             _retrieve: по каждому варианту запроса search top_n, объединить по chunk_id
evaluate.py/app.py
```

### Результат (важно)

```
A plain 9/10 → B rerank 10/10 → C rewrite+rerank 10/10, source recall 10/10.
Фильтр УЖИМАЕТ контекст (4.0→3.0 чанка) — меньше шума, точнее.
Ключевой кейс Q1 «три стратегии»: bi-encoder держал вводные секции, нужный
чанк (со списком стратегий) был 5-м (sim 0.476, отсеян); cross-encoder поднял
его в топ (rerank 0.702) → ответ верный. Демонстрирует ценность 2-го этапа.
Грабли: фикс. threshold может отсечь всё (Q8 → 0 чанков) — спасает min_keep.
Возможна вариативность прогонов (LLM-недетерминизм в rewrite).
```

### fastembed reranker

```
from fastembed.rerank.cross_encoder import TextCrossEncoder
мультиязычный: jinaai/jina-reranker-v2-base-multilingual
.rerank(query, docs) → сырые скоры (не 0..1), применяем сигмоиду
```

---

## Week 5 / Day 4 — Обязательные источники/цитаты + режим «не знаю»

**Новое:** структурированный JSON-ответ с источниками и заземлёнными цитатами.

### rag.py

```
Answer{know, answer, sources[{source,section,chunk_id}],
       quotes[{chunk_id,text,grounded}], clarification, top_score, mode}
JSON-режим: response_format={"type":"json_object"} (DeepSeek поддерживает)
контекст: блоки [Источник N | chunk_id=… | file → section]
_ground_quotes: grounded если норм. подстрока чанка ИЛИ ≥85% слов в чанке
know-gate (2 уровня):
  1) top rerank score < know_threshold=0.25 → сразу «не знаю» БЕЗ вызова LLM
  2) LLM ставит know=false если контекст не отвечает
если know=false → answer пустой + clarification (просьба уточнить)
```

### Проверка (evaluate.py, 10 Q + 3 out-of-domain)

```
источники 9/10, цитаты 9/10, заземлены 9/10, смысл↔цитаты 8/10, «не знаю» 3/3.
meaning_match строгая: факт и в answer, И в заземлённой цитате.
Вариативность: rewrite недетерминирован → изредка 1 вопрос уходит в know=false.
Урок: JSON-режим + grounding цитат ловит галлюцинации-«цитаты»; порог+LLM-флаг
дают надёжный «не знаю» на out-of-domain.
```

---

## Week 5 / Day 5 — Мини-чат (Flask) с RAG + память задачи

**Новое:** веб-чат, объединяющий RAG (week 5) + память задачи (week 3) + Flask (week 2).
Порт 5006.

### Файлы

```
database.py    — sessions / messages(sources JSON) / task_memory(goal,
                 clarifications, constraints, terms)
task_memory.py — TaskMemoryUpdater.update (LLM, JSON, _merge накопительно,
                 uniq списки, goal сохраняется) + format_for_prompt
agent.py       — ChatAgent: session_id property; ask() = save→retrieve
                 (rewrite→rerank→фильтр, KNOW_THRESHOLD=0.22)→генерация с
                 историей(HISTORY_TURNS=6)+памятью+контекстом→источники→обновить память
app.py         — Flask /ask /memory /history /clear (порт 5006)
templates/index.html — чат + панель памяти задачи + источники под ответами
```

### Ловушка «потеря цели» (важно)

```
Корпус (пример Sticky Facts в article_context_strategies.md) содержит
«цель проекта: мобильное приложение для доставки, бюджет 500K, дедлайн …».
Баг: TaskMemoryUpdater видел это в RAG-ответе и ПОДМЕНЯЛ реальную цель.
Фикс 2 места:
  1) task_memory prompt: «goal — из слов ПОЛЬЗОВАТЕЛЯ, НЕ из примеров в доках»
  2) agent SYSTEM: «на вопросы о цели отвечай из ПАМЯТИ ЗАДАЧИ, не из документов»
После фикса ассистент на «напомни цель» явно говорит «пример из доков ≠ ваша цель».
```

### Контекстуализация уточняющих вопросов (ФИКС)

```
Баг: follow-up вопросы («а чем они отличаются?», «почему?», «второй вариант»)
ищутся как есть → эмбеддинг бессмысленный → top_score 0.13-0.19 < KNOW_THRESHOLD
0.22 → «не нашёл» уже на 2-м вопросе диалога.
Фикс: rewrite.py — метод rewrite(question, history) с PROMPT_CTX: сначала
восстановить полный самостоятельный вопрос по истории (разрешить «они»/«второй
вариант»), потом дать поисковые варианты. agent._retrieve(question, history):
передаёт prior=get_messages()[:-1][-HISTORY_TURNS:]; реранк по самому длинному
(контекстуализированному) запросу max(queries,key=len), иначе короткий «Почему?»
отсекает чанки. После фикса follow-up top 0.65-0.76.
```

### Проверка (test_scenarios.py, 2×10 сообщений)

```
Сценарий 1 (выбор стратегии): 10/10 с источниками, goal стабилен.
Сценарий 2 (MCP-интеграция): 9/9 внутрибазовых с источниками (после фикса
контекстуализации; было 8/8), goal стабилен. Ассерты: goal не пуст, не содержит
«достав», содержит ключевые слова темы; constraints≥1; источники в каждом ответе.
Flask-роуты — через test_client (dev-сервер с debug reloader медленно стартует).
```

---

## Week 6 — Локальные LLM (Ollama)

**Новый стек:** локальный инференс без API-ключей. Ollama 0.31.2 (`localhost:11434`),
модель qwen2.5:1.5b. brew есть. Порты Flask: day2=5007, day5=5008.

### Ключевые паттерны

```
ollama_client.py (только stdlib urllib, копируется между днями):
  is_up() /api/version · list_models() /api/tags
  chat_stream(messages, model, options) — /api/chat stream=true → JSONL,
    yield {token} … {done, stats{prompt_tokens,eval_tokens,total_duration_ms}}
  chat / chat_full(→answer, stats)
  options: temperature, num_predict (макс токенов), num_ctx (окно), top_p, repeat_penalty
Flask-стриминг: Response(stream_with_context(gen), mimetype="application/x-ndjson"),
  собираем токены и сохраняем полный ответ в finally.
OpenAI-совместимый путь: base_url=http://localhost:11434/v1 (openai-SDK как в W1-5).
```

### День 3 — RAG локально

```
retrieval ВСЕГДА локальный (fastembed embed + index_store + rerank — локальные модели);
генерация переключаемая: LocalRAG.ask(backend="local"|"cloud").
compare.py: local 9/10 ~1.48с, cloud 10/10 ~3.56с — ЛОКАЛЬНАЯ БЫСТРЕЕ (1.5B без сети).
```

### День 4 — оптимизация

```
3 рычага: параметры (temp 0.8→0.1, num_predict→200, num_ctx 32768→4096),
prompt (общий→строгий «ответ + Источник:»), квант (Q4_K_M 986MB vs Q8_0 1.6GB).
optimize.py: ДО 10/10 1.47с/167ток → ПОСЛЕ 10/10 1.01с/82ток (−31%/−50%).
Q8 не улучшил → Q4 оптимален. Ресурсы: ollama ps (RAM 1.2 vs 1.8GB), ollama list (диск).
```

### День 5 — приватный сервис для VPS

```
service.py (Flask, 5008): /v1/chat (стрим+auth+ratelimit+лимит контекста),
  /v1/health (открыт), /v1/models. config.py из env, ratelimit.py скользящее окно.
Bearer-auth (пусто=выкл dev); >MAX_HISTORY обрезка, >MAX_INPUT_CHARS→413, rate→429.
Артефакты: Dockerfile (gunicorn gthread), docker-compose.yml (ollama+api, наружу 5008),
  deploy/nginx.conf (proxy_buffering off), deploy/llm-service.service (systemd), .env.example.
test_service.py: HTTP-проверки — health, 401, чат, 413, 5/5 параллельных, rate 3→429.
```

### Грабли деплоя на VPS (важно — реальные вопросы пользователя)

```
- day 1 без venv (stdlib) → команда python3, НЕ python (на macOS нет `python`).
- «unknown shorthand flag: 'd' in -d» И «unknown command: docker compose» =
  плагин Compose V2 не установлен → docker парсит `-d` как свой флаг.
  Фикс: apt install docker-compose (V1, команда docker-compose up -d) ИЛИ
  плагин бинарём: curl …/docker-compose-linux-$(uname -m) → /usr/local/lib/docker/cli-plugins/
  (ВАЖНО: lowercase `linux`, uname -s даёт `Linux` → 404). Флаг -d идёт ПОСЛЕ up.
- «Unable to locate package docker-compose-plugin» = нет офиц. apt-репо Docker
  (ставили docker.io из Ubuntu-репо) → см. варианты выше.
- «permission denied /var/run/docker.sock» = юзер не в группе docker →
  sudo docker … ИЛИ usermod -aG docker $USER + newgrp docker/релогин.
- Без Docker вообще → Вариант B (systemd + ollama serve).
```

---

## Week 7 — Ассистент разработчика (проект-aware)

**Новое:** ассистент, понимающий САМ проект — RAG по его докам + git через MCP +
DeepSeek. Объединяет week 5 (RAG) + week 4 (MCP) + week 2 (Flask). Порт 5009.

### Файлы

```
project_loader.py — собирает документацию репо: корневой README +
  week*/day*/README.md + claude/*.md (41 файл ~107стр). REPO_ROOT=parents[2].
build_index.py    — chunking(structural) + fastembed → index_store (458 чанков)
git_mcp_server.py — MCP-сервер, git-инструменты только на чтение (cwd=REPO_ROOT):
  git_branch/git_status/git_log/git_diff/git_recent_files/list_files
assistant.py      — DevAssistant: RAG-retrieve локально → DeepSeek tool-calling
  с git-инструментами → Answer{answer, sources, git_calls}
app.py            — Flask (5009), команда /help; templates/index.html
```

### Ключевые решения

```
- Ретрив локальный (fastembed+rerank), генерация облачная (DeepSeek) — гибрид.
- embedder/reranker persistent (грузятся раз), MCP git-сессия — на каждый запрос
  (AsyncExitStack: stdio_client → ClientSession). Flask вызывает asyncio.run(ask).
- О проекте отвечает ТОЛЬКО по /help: bare /help=справка, /help <q>=вопрос,
  сообщение без /help → просит команду (RAG/git/DeepSeek не вызываются).
- Модель сама выбирает git-инструмент (вопрос про ветку/файлы/коммиты → вызов),
  ответ по докам с источниками-файлами.
```

### Проверка (test_assistant.py)

```
индекс≥50 чанков; /help справка; БЕЗ /help → отказ (нет sources/git_calls);
/help <структура> → ответ по докам + источники (README/claude/*);
/help <git> → вызван git_branch → main.
```

### День 2 — AI-ревью PR (GitHub Action)

```
project_loader.py — доки + КОД (README+claude/*.md+все .py, 181 файл) → индекс 1328 чанков
reviewer.py: get_diff(--diff-file/--base <ref>...HEAD/stdin) → changed_files
  (regex ^\+\+\+ b/) → retrieve_context (RAG по diff+файлам, исключая изменённые)
  → DeepSeek ревью строго по разделам (🐞 баги / 🏛 архитектура / 💡 рекомендации + Вердикт)
.github/workflows/pr-review.yml (в КОРНЕ репо): on pull_request → checkout fetch-depth 0
  → cache fastembed → build_index → reviewer --base origin/<base> → gh pr comment
  permissions pull-requests:write; секрет DEEPSEEK_API_KEY.
Ловит на тесте: ZeroDivision, KeyError, хардкод ключа, неверный вызов клиента.
Проверено вживую (PR #1): Action отработал ~2мин, оставил комментарий с ревью,
сославшись на конвенции проекта (claude/architecture.md, week1/day3).
```

### День 3 — Ассистент поддержки (5010)

```
product_docs/ (FAQ+доки CloudNote) → RAG-индекс. data/support.json — users+tickets.
support_mcp_server.py — MCP над JSON: get_ticket/get_user/list_tickets.
assistant.py SupportAssistant.ask(question, ticket_id): MCP get_ticket → контекст
  (тариф) → RAG по докам (query=вопрос+описание) → DeepSeek учитывает тариф.
Пример: T-1002 (Pro, про SSO) → «SSO только на Business». app.py Flask 5010.
```

### День 4 — Файловый ассистент (реальные операции)

```
fs_mcp_server.py — MCP в песочнице workspace/ (_safe: путь внутри WORKSPACE):
  list_files/read_file/search(regex)/write_file. agent.py FileAgent — DeepSeek
  tool-calling, по ЦЕЛИ сам решает что читать/искать/писать. workspace_seed.py —
  детерминированная песочница (воспроизводимость). run.py: seed→снимок→агент→
  показ вызовов + unified diff (difflib). Сценарии: (1) найти использования Logger
  → docs/logger_usage.md; (2) проверка правила докстринга → compliance_report.md.
```

### День 5 — Веб-сервис анализа удалённого GitHub-репо (5011)

```
Только веб + удалённые репо (CLI/локальный git убраны по просьбе).
ТОКЕНЫ — В ИНТЕРФЕЙСЕ (⚙ Токены), не из окружения: DeepSeek ключ (обяз.),
  GitHub токен (опц.), Telegram bot token + chat_id (опц.); хранятся в localStorage,
  уходят на сервер только в теле запроса.
github_repo.get_commits(repo, last, token) — коммиты через GitHub REST API
  (parse_repo из URL/owner-repo; токен опц.). digest.generate(tone, api_key):
  'neutral' дайджест vs 'toxic' 🔥 роаст (SYSTEM_TOXIC savage code review, temp 0.9;
  жжём по КОДУ не по авторам). В UI toxic = «🐓 rooster режим», вкл. по умолчанию
  (только переименование+дефолт; логика/промпты не менялись). Поле «Заголовок» убрано.
notify.send_telegram(text, token, chat_id) — Telegram (без токена/chat_id → skipped).
app.py Flask 5011: /health ({status:ok}), /generate {repo,last,toxic,deepseek_key,
  github_token}, /publish {telegram_token,telegram_chat_id}.
Docker для VPS: Dockerfile (python-slim+gunicorn, БЕЗ git), docker-compose.yml
  (без монтирования и БЕЗ env-секретов — только PORT; наружу 5011).
  deploy/nginx.conf (proxy на 5011 + TLS certbot). Граница: не автопостит в чужие репо.
```

---

## Паттерны, которые повторяются

### Per-session агенты

```python
_agents: dict[str, LLMAgent] = {}

def get_agent() -> LLMAgent:
    sid = session.get("id") or str(uuid.uuid4())
    session["id"] = sid
    if sid not in _agents:
        _agents[sid] = LLMAgent(session_id=sid)
    return _agents[sid]
```

### Безопасный fetch в JS

```js
async function safeJson(res) {
    const ct = res.headers.get("content-type") || "";
    if (!ct.includes("application/json"))
        return { error: `Сервер вернул ошибку ${res.status}` };
    return res.json();
}
```

### Стоимость запроса

```python
cost = (prompt_tokens * model.price_input_1m
      + completion_tokens * model.price_output_1m) / 1_000_000
```

### Инжекция файлов в системный промпт

```python
blocks = [f"### Файл: {f['filename']}\n\n{f['content']}" for f in files]
extra = "\n\n---\n\n".join(blocks)
system = base_system_prompt + "\n\n" + extra
```
