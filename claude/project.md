# Проект ai_advent_challenge

**GitHub:** https://github.com/imfailing/ai_advent_challenge  
**Владелец:** Сергей (GitHub: imfailing)  
**Цель:** Учебный AI-адвент — каждый день новая задача по работе с LLM через API.

Задачи усложняются постепенно: Week 1 — консольные скрипты,
Week 2+ — Flask-приложения с агентами.

---

## Структура папок

```
ai_advent_challenge/
├── README.md            # корневой обзор всего проекта (все 5 недель, порты, стек)
├── claude/              # контекст для Claude, не попадает в git
├── week 1/
│   ├── day 1/           # базовый вызов DeepSeek API, вывод в консоль
│   ├── day 2/           # контроль формата: format + max_tokens + stop
│   ├── day 3/           # 4 способа решения задачи (прямой / step-by-step / meta-prompt / experts)
│   ├── day 4/           # сравнение temperature = 0 / 0.7 / 1.2
│   └── day 5/           # сравнение слабой/средней/сильной модели
├── week 2/
│   ├── day 1/           # Flask-чат: агент + сессия + Markdown-рендеринг
│   ├── day 2/           # + персистентность истории в SQLite
│   ├── day 3/           # + токены/стоимость + файлы контекста + выбор модели
│   ├── day 4/           # + сжатие контекста: суммаризация старых сообщений
│   └── day 5/           # + три стратегии контекста: Sliding Window / Sticky Facts / Branching
├── week 3/
│   ├── day 1/           # модель памяти: 3 слоя (краткосрочная/рабочая/долговременная) + LLM-маршрутизатор
│   ├── day 2/           # персонализация: профиль пользователя (стиль/формат/ограничения) + авто-детект prefs
│   ├── day 3/           # состояние задачи как FSM: planning→execution→validation→done + пауза/продолжение
│   ├── day 4/           # инварианты проекта: нерушимые ограничения + страж-проверка отказа
│   └── day 5/           # контролируемый жизненный цикл: явные переходы + гейты (нельзя перепрыгнуть этап)
├── week 4/             # MCP (Model Context Protocol)
│   ├── day 1/           # MCP SDK: клиент подключается к серверу по stdio и получает список инструментов
│   ├── day 2/           # свой MCP-сервер вокруг mock CRM + агент (DeepSeek tool-calling) вызывает инструмент
│   ├── day 3/           # MCP-инструмент с периодическим выполнением: фоновый планировщик 24/7 + сводки/напоминания
│   ├── day 4/           # автоматический пайплайн из MCP-инструментов: search→summarize→save_to_file
│   └── day 5/           # несколько MCP-серверов + маршрутизация + длинный флоу (CRM/knowledge/notes)
├── week 5/             # RAG (индексация и поиск по документам)
│   ├── day 1/           # локальный индекс: chunking (2 стратегии) + эмбеддинги (fastembed) + SQLite/JSON + сравнение
│   ├── day 2/           # RAG-агент (с RAG / без RAG) + 10 контрольных вопросов + сравнение качества
│   ├── day 3/           # улучшенный RAG: реранкинг (cross-encoder) + фильтр по порогу + query rewrite
│   ├── day 4/           # обязательные источники+цитаты (JSON) + grounding + режим «не знаю» при слабом контексте
│   └── day 5/           # мини-чат на Flask: RAG + источники + память задачи (goal/уточнения/ограничения/термины)
├── week 6/             # Локальные LLM
    ├── day 1/           # Ollama: локальная модель qwen2.5:1.5b, CLI + HTTP API, 3 запроса разной сложности
    ├── day 2/           # веб-приложение (Flask) на локальной LLM: стриминг ответов, офлайн, порт 5007
    ├── day 3/           # RAG полностью локально (retrieval + генерация) + сравнение local vs cloud
    ├── day 4/           # оптимизация локальной модели: параметры + prompt + квантование, до/после
│   └── day 5/           # приватный AI-сервис на локальной LLM для VPS: HTTP API + auth + rate limit + Docker/systemd/nginx
└── week 7/             # Ассистент разработчика (RAG по докам + MCP git + DeepSeek)
    └── day 1/           # /help: RAG по README/docs/claude + git через MCP + веб-интерфейс, порт 5009
```

Каждый день — отдельная папка со своим `venv/`.

---

## Прогресс

### Week 1 — консольные скрипты

| День | Задача | Ключевые концепции |
|---|---|---|
| 1 | Базовый вызов DeepSeek | `openai` SDK, `base_url`, env-переменные |
| 2 | Контроль формата ответа | `max_tokens`, `stop`, сравнение с/без ограничений |
| 3 | 4 способа решения задачи | прямой / step-by-step / meta-prompt / experts |
| 4 | Влияние temperature | 0 / 0.7 / 1.2 — точность vs креативность |
| 5 | Сравнение моделей | GigaChat (слабая) / deepseek-chat (средняя) / deepseek-reasoner (сильная) |

### Week 2 — Flask-приложение с агентом

| День | Добавленный функционал |
|---|---|
| 1 | Flask-чат, LLMAgent, история в памяти, Markdown (`marked.js` + `highlight.js`) |
| 2 | Персистентная история в SQLite; история загружается как контекст, но не отображается в UI при перезагрузке |
| 3 | Подсчёт токенов и стоимости; загрузка файлов контекста (PDF + текст, до 5 MB); выбор модели с отображением параметров |
| 4 | Сжатие контекста: при длинном диалоге старые сообщения суммаризируются отдельным вызовом LLM и хранятся в таблице summaries |
| 5 | Три стратегии управления контекстом с переключателем в UI: Sliding Window, Sticky Facts (KV-память), Branching (независимые ветки) |

### Week 3 — память и состояние агента

| День | Добавленный функционал |
|---|---|
| 1 | Явная модель памяти из 3 слоёв (краткосрочная=диалог, рабочая=данные задачи, долговременная=профиль/решения/знания), хранятся в разных таблицах; LLM-маршрутизатор раскладывает новую инфу по слоям + ручное управление. Порт 5001 |
| 2 | Персонализация поверх памяти: структурированный профиль (name/role/expertise/tone/verbosity/answer_format/language/constraints), несколько профилей с переключением, профиль инжектится в каждый запрос; роутер авто-обновляет prefs из явных просьб пользователя. Порт 5002 |
| 3 | Состояние задачи как конечный автомат (statemachine.py): planning→execution→validation→done с валидацией переходов; тройка stage/current_step/expected_action + status active/paused; пауза на любом этапе, продолжение из БД без повторных объяснений; контроллер-LLM продвигает автомат, недопустимые переходы отклоняются. Порт 5003 |
| 4 | Инварианты проекта (таблица invariants, 4 категории: architecture/tech_decision/stack/business_rule), хранятся отдельно от диалога; инжектятся первыми в промпт с запретом нарушать; страж-LLM (_check_compliance) проверяет ответ и возвращает вердикт {compliant, refused, violations}. На конфликте агент отказывается и объясняет какой инвариант и почему + предлагает альтернативу. Порт 5004 |
| 5 | Контролируемый жизненный цикл задачи: явные переходы с ГЕЙТАМИ (statemachine.check_transition). planning→execution нужен plan_approved, execution→validation нужен implementation_done, validation→done нужен validation_passed. Нельзя перепрыгнуть этап (ребра нет в TRANSITIONS). Гейты в task_state.conditions (JSON), отклонённые переходы логируются (accepted=0). Enforcement и для ручных, и для авто-переходов. Порт 5005 |

### Week 4 — MCP (Model Context Protocol)

Новый тип задач: не Flask-приложения, а работа с MCP. Используется официальный
Python SDK `mcp` (на момент задачи — v1.28.1). DeepSeek/API-ключ не нужен.

| День | Добавленный функционал |
|---|---|
| 1 | Установка MCP SDK; минимальный клиент (client.py): подключение к серверу по stdio (StdioServerParameters + stdio_client), ClientSession.initialize() рукопожатие, list_tools() — список инструментов. Локальный демо-сервер server.py на FastMCP (4 инструмента: add/multiply/echo/reverse). client.py универсален: `python client.py -- npx ... server` для внешних серверов. Без портов (CLI). |
| 2 | Свой MCP-сервер вокруг API (mock CRM в crm_api.py): mcp_server.py регистрирует 4 инструмента (list_customers/get_customer/search_deals/create_ticket) через @mcp.tool() с описанием параметров. Агент MCPAgent (agent.py) на DeepSeek (AsyncOpenAI, tool-calling): list_tools→OpenAI tools формат, модель сама вызывает инструмент→session.call_tool→результат возвращается модели→финальный ответ использует результат. app.py — CLI. Нужен DEEPSEEK_API_KEY. |
| 3 | MCP-инструмент с периодическим выполнением: фоновый поток Scheduler (scheduler.py) 24/7 собирает метрику (collector.py) в SQLite (store.py), зажигает отложенные напоминания, каждые N тиков сохраняет снапшот сводки. Инструменты: summary(minutes)/recent_summaries/add_reminder/due_reminders/pending_reminders/scheduler_status. Планировщик стартует при импорте mcp_server.py. Env: SCHED_INTERVAL, SCHED_SUMMARY_EVERY (не наследуются подпроцессом MCP — дефолты). agent.py скопирован из day 2. |
| 4 | Автоматический пайплайн из 3 MCP-инструментов: search (corpus.py, mock-корпус) → summarize (summarizer.py, детерминированная экстрактивная сводка) → save_to_file (пишет в output/). Агент по одной инструкции сам вызывает цепочку по порядку, передавая выход в вход. test_pipeline.py: ручная цепочка (передача данных) + агентная (порядок вызовов). ВАЖНО: FastMCP оборачивает list-результат в structuredContent={"result":[...]} и кладёт каждый элемент отдельным content-блоком; dict-результат → structuredContent=None, парсить content-текст. |
| 5 | Несколько MCP-серверов сразу: 3 независимых сервера (crm_server/knowledge_server/notes_server). MultiMCPAgent (agent.py) подключается ко всем через AsyncExitStack, неймспейсит инструменты как label__tool, маршрутизирует вызов по префиксу до '__' в нужную сессию (routes: openai_name→(session,real_tool,label)). Длинный флоу: get_customer→search_deals→search_docs→summarize→save_note (5 вызовов, 3 сервера). test_multi.py проверяет разные серверы + порядок + сохранение. |

### Week 5 — RAG (индексация и поиск)

Новый стек: DeepSeek НЕ даёт embeddings (404) → локальный эмбеддер `fastembed`
(ONNX, без torch), мультиязычная модель `paraphrase-multilingual-MiniLM-L12-v2`
(384-dim, т.к. корпус на русском + код). Модель качается в кэш fastembed при
первом embed (~120MB). API-ключ не нужен.

| День | Добавленный функционал |
|---|---|
| 1 | Локальный индекс документов. corpus/ — 14 реальных файлов репо (md/py/pdf, ~40 стр.). loader.py (pdf через pypdf, PDF сгенерён reportlab). chunking.py — 2 стратегии: fixed_size(800/overlap150) и structural (md по заголовкам, py по def/class, txt/pdf по абзацам; structural режется до 1600 симв). Метаданные чанка: chunk_id/strategy/source/file/title/section/n_chars. embedder.py (fastembed 384-dim, L2-норм). index_store.py — SQLite (index.db, эмбеддинги BLOB) + index_<strategy>.json, косинусный поиск на numpy. compare_chunking.py сравнивает: fixed 118 чанков/std168, structural 132/std463, ретрив близкий (top-3 0.574 vs 0.567), structural даёт осмысленные section. |
| 2 | RAG-агент. rag.py: RagAgent.ask_with_rag (embed→index_store.search top-k→контекст с метками источников→DeepSeek «отвечай по контексту, цитируй») и ask_plain (без контекста). eval_set.py — 10 контрольных вопросов по corpus с полями expected (ключевые факты) + expected_sources (файлы). evaluate.py — оба режима, метрики keyword-hit/pass/source-recall; выводит в консоль сами ответы (без RAG / с RAG) + источники. Результат: без RAG 6/10, с RAG 9/10, source recall 10/10. Пайплайн (loader/chunking/embedder/index_store) скопирован из day 1. Честный промах Q1: structural разнёс 3 стратегии по секциям, ретрив не поднял все в top-k → RAG зависит от гранулярности чанков и k. |
| 3 | Улучшенный RAG — второй этап после поиска. rerank.py: cross-encoder jinaai/jina-reranker-v2-base-multilingual (fastembed TextCrossEncoder), сигмоида→0..1, фильтр по threshold + min_keep=2 (не возвращать пусто). rewrite.py: QueryRewriter — LLM даёт 2-4 варианта запроса (мульти-запрос, recall↑). rag.py: RagConfig(use_rewrite/use_rerank, top_n=12/top_k=4/threshold=0.3/min_keep=2), _retrieve объединяет по вариантам. Конвейер: retrieve N→rerank→порог→top-K. evaluate.py: A plain 9/10, B rerank 10/10, C rewrite+rerank 10/10, все source recall 10/10, контекст ужимается 4.0→3.0, выводит ответы по каждой конфигурации в консоль. Q1 чинится реранкером (bi-encoder ставил нужный чанк 5-м, cross-encoder — 1-м). |
| 4 | Обязательные источники+цитаты + режим «не знаю». rag.py: Answer{know, answer, sources[{source,section,chunk_id}], quotes[{chunk_id,text,grounded}], clarification, top_score}. JSON-режим DeepSeek (response_format json_object) — работает. Контекст помечает блоки [Источник N | chunk_id=…]. _ground_quotes: цитата заземлена если дословная подстрока ИЛИ ≥85% слов в чанке (иначе grounded=false). Gate «не знаю»: 2 уровня — top rerank < know_threshold=0.25 (короткое замыкание без LLM) + LLM ставит know=false. evaluate.py на 10 вопросах: источники 9/10, цитаты 9/10, заземлены 9/10, смысл↔цитаты 8/10, «не знаю» на out-of-domain 3/3; выводит в консоль ответ+источники+цитаты(с отметкой grounded) по каждому вопросу. Вариативность из-за rewrite. |
| 5 | Мини-чат на Flask (порт 5006). database.py: sessions/messages(sources JSON)/task_memory(goal, clarifications, constraints, terms). task_memory.py: TaskMemoryUpdater обновляет память после хода (LLM, JSON, merge накопительно) + format_for_prompt. agent.py ChatAgent.ask: save user→RAG retrieve (rewrite→rerank→фильтр)→ответ с историей+памятью задачи+контекстом+источниками→обновить память→save. app.py: /ask /memory /history /clear. ChatAgent.session_id — property (у app.py было обращение к нему). ВАЖНАЯ ловушка: корпус содержит пример «цель: мобильное приложение для доставки» — обновлятель памяти подменял реальную цель; фикс: промпт «goal из слов ПОЛЬЗОВАТЕЛЯ, не из примеров в доках» + системный промпт «на напомни-цель отвечай из памяти задачи». test_scenarios.py: 2 диалога ×10, цель сохранена (не подменена), источники в каждом ответе. ФИКС: уточняющие вопросы («а чем они отличаются?», «почему?», «второй вариант») ищутся как есть → top_score падал ниже порога → «не нашёл» уже на 2-м вопросе. Решение: rewrite.py принимает history и контекстуализирует вопрос (разрешает ссылки по диалогу); _retrieve передаёт prior историю, реранк по max(queries,key=len). После фикса follow-up top 0.65-0.76 (было 0.13-0.19). |

### Week 6 — Локальные LLM

Новый стек: локальный инференс без API-ключей. На машине уже стоял Ollama
(0.31.2, `/usr/local/bin/ollama`, сервис Ollama.app), сервер на
`http://localhost:11434`. `brew` есть.

| День | Добавленный функционал |
|---|---|
| 1 | Установка/запуск локальной LLM. Ollama + модель qwen2.5:1.5b (986 MB, `ollama pull`). query_local.py — обращение через нативный HTTP `/api/chat` (только stdlib urllib), 3 запроса разной сложности. Проверки: сервер отвечает на /api/version; CLI `ollama run`; HTTP API. Результаты: простой факт (Париж) ✅, генерация кода ✅, логическая задача-ловушка ⚠️ (1.5B ошиблась — 4 вместо 3, честно отражено). Ollama даёт и OpenAI-совместимый /v1/chat/completions (можно openai-SDK со сменой base_url). Без портов Flask (CLI). |
| 2 | Веб-приложение (Flask, порт 5007) на локальной LLM — офлайн, без облака. ollama_client.py (только stdlib urllib): is_up/list_models/chat_stream (генератор токенов из /api/chat stream=true, JSONL)/chat. app.py: /ask стримит NDJSON ({token}…{done,stats}) через Response(stream_with_context), сохраняет ответ ассистента после стрима; /health (ollama_up+models), /history, /clear. database.py — SQLite история. index.html — стрим с курсором, индикатор «офлайн», выбор локальной модели. test_app.py через test_client (нужен запущенный Ollama). Единственный внешний вызов — localhost:11434. |
| 3 | RAG полностью локально. Пайплайн недели 5 (retrieval: fastembed + index_store + rerank — всё локальные модели) + генерация переключаемая: rag.py LocalRAG.ask(backend="local"|"cloud"). local=qwen2.5:1.5b (Ollama), cloud=deepseek-v4-flash. compare.py на 10 вопросах: local 9/10 pass ~1.48с/ген, cloud 10/10 ~3.56с. ЛОКАЛЬНАЯ БЫСТРЕЕ (крошечная модель без сети). Обе 0 пустых. Полностью локальный путь без ключа/сети. |
| 4 | Оптимизация локальной модели под RAG-кейс. 3 рычага: (1) параметры Ollama options (temperature 0.8→0.1, num_predict→200, num_ctx 32768→4096, top_p/repeat_penalty); (2) prompt-шаблон общий→специализированный (строго по контексту, формат «ответ + Источник:», без вступлений); (3) квантование Q4_K_M (986MB) vs Q8_0 (1.6GB, ollama pull qwen2.5:1.5b-instruct-q8_0). ollama_client.py + options и chat_full. optimize.py: ДО 10/10 1.47с/167ток → ПОСЛЕ 10/10 1.01с/82ток (−31% время, −50% токены). Q8 не улучшил (9/10, медленнее, 1.8GB RAM vs 1.2GB). Вывод: Q4 оптимален; выигрыш от промпта+параметров, не от кванта. Ресурсы: ollama ps (RAM), ollama list (диск). |
| 5 | Приватный AI-сервис на локальной LLM для деплоя на VPS (порт 5008). service.py (Flask): /v1/chat (стрим NDJSON, auth+ratelimit+лимит контекста), /v1/health (без auth: ollama_up/model/limits), /v1/models. config.py — из env (API_KEYS, RATE_LIMIT/WINDOW, MAX_INPUT_CHARS, MAX_HISTORY, NUM_CTX). ratelimit.py — скользящее окно, потокобезопасно. Bearer-auth (пусто=выкл, dev). Ограничения: >MAX_HISTORY обрезка, >MAX_INPUT_CHARS→413, rate→429+Retry-After. Артефакты деплоя: Dockerfile (gunicorn gthread 2w/8t), docker-compose.yml (ollama+api, наружу только 5008), deploy/nginx.conf (proxy_buffering off для стрима, TLS certbot), deploy/llm-service.service (systemd), .env.example. test_service.py поднимает сервис в потоке и проверяет по HTTP: health, 401 без ключа, чат «Рим», 413 max context, 5/5 параллельных, rate limit 3→429. |

### Week 7 — Ассистент разработчика (проект-aware)

Объединяет RAG (week 5) + MCP (week 4) + Flask (week 2) + облачный DeepSeek.

| День | Добавленный функционал |
|---|---|
| 1 | Ассистент, понимающий проект. project_loader.py собирает документацию репо (корневой README + week*/day*/README.md + claude/*.md = 41 файл ~107стр). build_index.py → chunking(structural)+fastembed+index_store (458 чанков). git_mcp_server.py — MCP-сервер с git-инструментами (только чтение, cwd=REPO_ROOT parents[2]): git_branch/git_status/git_log/git_diff/git_recent_files/list_files. assistant.py DevAssistant: RAG-retrieve локально → DeepSeek (AsyncOpenAI) tool-calling с git-инструментами (AsyncExitStack, MCP-сессия на запрос; embedder/reranker persistent) → Answer{answer, sources, git_calls}. app.py (Flask, порт 5009): команда /help (bare=справка, /help <q>=вопрос), asyncio.run(assistant.ask). test_assistant.py: индекс, /help, вопрос о структуре с источниками (README/claude), вопрос про git → вызван git_branch (main). corpus самого проекта индексируется локально; index.db в gitignore. |

- `venv/` — виртуальное окружение
- `claude/` — этот контекст
- `.env`, `__pycache__/`, `*.pyc`
