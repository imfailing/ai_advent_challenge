# Week 6 / Day 2 — Веб-приложение на локальной LLM

Flask-чат, работающий поверх **локальной** модели (Ollama). Приложение
отправляет запросы в локальный сервер, стримит ответы токен за токеном и
отображает их. **Полностью офлайн — никаких облачных API и ключей.**

Порт **5007** · модель по умолчанию `qwen2.5:1.5b` (из day 1).

---

## Как это работает

```
браузер ──POST /ask──▶ Flask (app.py)
   ▲                      │  история из SQLite → messages
   │  стрим NDJSON        ▼
   │  {token}…{done,stats} ollama_client.chat_stream()
   │                      │  POST http://localhost:11434/api/chat (stream)
   └──────────────────────┘  ← токены от ЛОКАЛЬНОЙ модели
```

- **`ollama_client.py`** — клиент Ollama (только stdlib): `is_up()`,
  `list_models()`, `chat_stream()` (генератор токенов), `chat()`.
- **`app.py`** — Flask: `/ask` стримит ответ (NDJSON), `/health` показывает
  статус локального сервера и модели, `/history`, `/clear`.
- **`database.py`** — SQLite-история диалога (переживает перезагрузку).
- **`templates/index.html`** — чат: стриминг с «печатающимся» курсором,
  индикатор «🔒 офлайн · без облака», выбор локальной модели, Markdown.

Ничего не уходит в облако: единственный внешний вызов — на `localhost:11434`.

---

## Запуск

```bash
# нужен запущенный Ollama с моделью (см. week 6 / day 1):
ollama pull qwen2.5:1.5b

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt   # только Flask
python app.py                     # http://localhost:5007
```

API-ключи **не нужны** — приложение обращается только к локальному Ollama.

---

## Проверка

```bash
python test_app.py
```

Подтверждает (при запущенном Ollama):
- ✅ `/health` — локальный сервер запущен, есть модели;
- ✅ `/ask` — ответ приходит **по стриму** (токен за токеном), непустой,
  с метриками (токены, время);
- ✅ история сохраняется и очищается.

Пример прогона:
```
✅ /health: Ollama запущен локально, модели: ['qwen2.5:1.5b']
✅ /ask: стрим 16 чанков, ответ «Столица Японии — это Токio (Tokyo).», 17 токенов за 263мс
✅ /history: диалог сохранён
✅ /clear: история очищена
```

---

## Структура

```
day 2/
├── ollama_client.py   # клиент локального Ollama (stdlib), стриминг
├── database.py        # SQLite-история
├── app.py             # Flask (порт 5007), стриминг /ask
├── templates/
│   └── index.html     # чат-UI: стрим + индикатор офлайн + выбор модели
├── test_app.py        # проверка через test_client
├── requirements.txt   # только Flask
└── README.md
```
