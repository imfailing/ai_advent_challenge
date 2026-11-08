# Пайплайн к бою: LLM-шлюз + execution loop + security step

Самодостаточная копия для обмена в Red Team Challenge (день 15, подготовка). Внутри всё, что нужно запустить:
**шлюз** с Input/Output Guard, **цикл** «генерация → линтер/тесты → security review → коммит» и
security-промпт. Внешних зависимостей, кроме Flask, нет. Апстрим — любой OpenAI-совместимый сервер
(проверено на llama.cpp с `qwen3.5-122b`).

```
   клиент
        │  POST /chat  (или loop.py --task-text / --context-dir)
        ▼
 ┌───────────────┐   маскирует секреты и PII, лимит 20 запросов/мин на IP, аудит-журнал, учёт токенов
 │  gateway/     │ ─► Input Guard ─► апстрим LLM ─► Output Guard (секреты, утечка промпта, URL, команды)
 └───────────────┘
        ▲  все вызовы LLM из цикла идут только сюда
 ┌───────────────┐   задача + файлы проекта ─► генерация ─► ruff (E9,F) + тесты ─► security review (2-й вызов)
 │  loop/        │   Critical/High ─► назад с фидбеком «исправь: …» · Medium/Low ─► коммит + предупреждение
 └───────────────┘   чисто ─► коммит · ревью недоступно или не разобрано ─► коммита нет
```

## Требования и установка

Python 3.13, `bash`, доступ к OpenAI-совместимому серверу LLM. Линтер ruff необязателен.

```bash
cp .env.example .env           # впишите LLAMA_API_KEY, LLAMA_BASE_URL (…/v1), при необходимости LLAMA_MODEL и PORT
./pipeline.sh setup            # создаёт venv и ставит Flask (PYTHON=python3.13 ./pipeline.sh setup, если python3.13 не по умолчанию)
./pipeline.sh test             # офлайн-тесты шлюза и цикла, сеть и ключи не нужны
```

## Запуск

```bash
./pipeline.sh gateway          # терминал 1: шлюз на http://127.0.0.1:5013 (PORT в .env меняет порт)
./pipeline.sh smoke            # терминал 2: health и блокировка секрета, модель не вызывается
RUFF=/путь/к/ruff ./pipeline.sh loop --tasks T1,T2,T3                   # три готовые задачи про небезопасный код
./pipeline.sh loop --task-text "Сделай функцию slugify(title)…"          # своя задача
./pipeline.sh loop --task-text "…" --context-dir /путь/к/папке_с_файлами # файлы, которые агент прочитает как «репозиторий»
```

Один вызов reasoning-модели занимает от десятков секунд до нескольких минут, цикл на задачу — 5–30 минут.

## Endpoint: `POST /chat` (шлюз)

Вход (JSON), одно из двух: `prompt` (строка) **или** `messages`.

| Поле | Значение |
|---|---|
| `prompt` | текст запроса пользователя |
| `messages` | список `{"role": "system"\|"user"\|"assistant", "content": "…"}`, до 50 сообщений, всего до 20 000 символов |
| `mode` | `block` (по умолчанию: секрет в запросе → отказ) или `mask` (секрет → метка `[REDACTED_…]`, запрос идёт дальше) |
| `profile` | `assistant` (по умолчанию: ассистент компании «Рубеж») или `code` (ассистент-программист) |
| `max_tokens` | 1–12000, по умолчанию 4000 |
| `thinking` | `true` (по умолчанию) или `false` (отключить рассуждение модели) |

```bash
curl -s localhost:5013/chat -H 'Content-Type: application/json' \
  -d '{"prompt": "Мой ключ sk-proj-abc123, помоги", "mode": "mask", "max_tokens": 2000}'
```

Выход `200` (числа в примере условные):

```json
{"content": "…ответ модели после Output Guard…", "model": "qwen3.5-122b", "request_id": "9e6f…",
 "usage": {"prompt_tokens": 106, "completion_tokens": 2408}, "cost_usd": 0.009738,
 "guard": {"input": "masked", "input_findings": [{"kind": "api_key", "label": "REDACTED_API_KEY", "length": 14,
                                                   "fingerprint": "e16ecd97", "preview": "…(len 14)", "via": "direct", "message_index": 0}],
           "output": "allowed", "output_findings": []}}
```

| Код | Когда |
|---|---|
| `400` | ошибка ввода или запрос заблокирован Input Guard (в теле `error`, `warning` и `findings` без самих секретов; в модель ничего не отправлено) |
| `429` | больше 20 запросов в минуту с IP (заголовок `Retry-After`) |
| `502` | апстрим недоступен или вернул ошибку |

Решения guard'ов: `guard.input` — `allowed` / `masked` (при `blocked` приходит `400`); `guard.output` — `allowed` / `masked` (секрет в
ответе заменён меткой) / `blocked` (вместо ответа текст `[Ответ заблокирован output guard: причина]`).

Остальные: `GET /health`, `GET /stats` (счётчики решений, токены, условная стоимость), `GET /audit?last=15` (хвост
журнала, 1–100). Аутентификации у шлюза нет, он слушает только `127.0.0.1`.

## Цикл: `loop/loop.py`

Вход: задача (`--tasks T1,T2,T3` или `--task-text "…"`), необязательный `--context-dir`, `--max-iter` (по умолчанию 3),
`--stack python|ios|android` (профиль security-промпта). Выход — папка `loop/runs/<время>/`:
`report.md` (что поймало ревью, что сделал шлюз, что прошло мимо), `events.jsonl` (каждый вызов шлюза: решения по входу
и выходу, токены, стоимость; тел промптов и секретов нет), `results.json`, `T*/solution.py` и `T*/test_solution.py`.
Итог по задаче: `committed` / `gave_up` / `blocked_by_gateway` / `gateway_error` / `review_failed`. Коммиты идут в
одноразовый git-репозиторий во временной папке, ваш репозиторий не меняется.

Внимание: **код, сгенерированный моделью, выполняется на вашей машине** (урезанное окружение
и таймаут 60 с, но без изоляции сети и диска): запускайте на отдельной машине или в контейнере.

## Проверено перед отправкой

С нуля из копии папки вне репозитория: `setup`, `test` (4 набора тестов проходят), запуск шлюза, `smoke` (health и
блокировка секрета с HTTP 400), понятная ошибка без `LLAMA_API_KEY`, и живой запуск
`loop --task-text … --context-dir …` на реальной модели: генерация → ruff и тесты → ревью `clean` → коммит (2 вызова шлюза).

## Как передать партнёру

Отправьте папку целиком без `venv/`, `.env`, `loop/runs/` и `gateway/logs/` (они в `.gitignore`):

```bash
cd "week 10" && zip -r pipeline_day15.zip "day 5" -x "*/venv/*" "*/.env" "*/loop/runs/*" "*/gateway/logs/*" "*/__pycache__/*"
```

В архиве нет ваших ключей: `.env.example` содержит только плейсхолдеры. Ключ и адрес своей модели партнёр
подставляет сам.
