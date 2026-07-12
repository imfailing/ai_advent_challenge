# Week 6 / Day 5 — Приватный AI-сервис на локальной LLM (для VPS)

Локальная LLM, развёрнутая как **сетевой сервис**: HTTP API + веб-чат,
аутентификация по ключу, rate limit и ограничение контекста. Модель сервится
**сами на VPS** через Ollama — ничего не уходит в облако.

Здесь — весь код и артефакты для деплоя на VPS (Docker / systemd + nginx).

---

## Архитектура

```
интернет ──TLS──▶ nginx (reverse proxy) ──▶ API-сервис (service.py, :5008)
                                              │  auth · rate limit · лимит контекста · стриминг
                                              ▼
                                          Ollama (:11434, локально на VPS)
                                              │  веса модели, инференс
                                              ▼
                                          qwen2.5:1.5b
```

- **`service.py`** — Flask API + UI. Поверх модели: Bearer-auth, rate limit,
  ограничение контекста, стриминг NDJSON.
- **`config.py`** — настройки из env (12-factor).
- **`ratelimit.py`** — скользящее окно, потокобезопасно.
- **`ollama_client.py`** — клиент локального Ollama (stdlib).
- **`Dockerfile` / `docker-compose.yml`** — Ollama + сервис.
- **`deploy/nginx.conf`, `deploy/llm-service.service`** — reverse proxy и systemd.

---

## HTTP API

| Метод | Путь | Auth | Описание |
|---|---|---|---|
| GET | `/` | — | веб-чат |
| GET | `/v1/health` | — | статус Ollama, модель, лимиты |
| GET | `/v1/models` | ✔ | локальные модели |
| POST | `/v1/chat` | ✔ | чат со стримингом NDJSON |

```bash
# health
curl http://HOST:5008/v1/health

# чат (стриминг)
curl -N http://HOST:5008/v1/chat \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"message":"Привет!"}'
# ← {"token":"При"}\n{"token":"вет"}\n…{"done":true,"stats":{…}}
```

Принимает `{"message":"…"}` или `{"messages":[{role,content}…]}`.

---

## Проверки (`test_service.py`)

Поднимает сервис на реальном порту и ходит по HTTP (имитация сети):

- ✅ **доступ по сети** — `/v1/health` и `/v1/chat` отвечают по HTTP;
- ✅ **аутентификация** — без ключа `POST /v1/chat` → **401**;
- ✅ **стабильность** — 5 параллельных запросов → все успешны (5/5);
- ✅ **rate limit** — лимит 3/мин → `[200,200,200,429,429,429]`;
- ✅ **max context** — вход длиннее лимита → **413**.

```bash
python test_service.py
```

---

## Базовые ограничения (настраиваются в `.env`)

| Ограничение | Переменная | По умолчанию |
|---|---|---|
| Rate limit | `RATE_LIMIT` / `RATE_WINDOW` | 30 запросов / 60 с (на ключ/IP) |
| Макс. длина входа | `MAX_INPUT_CHARS` | 8000 символов → иначе 413 |
| Макс. история | `MAX_HISTORY` | 20 сообщений (обрезается) |
| Окно контекста | `NUM_CTX` | 4096 (передаётся в Ollama) |
| Макс. ответ | `NUM_PREDICT` | 512 токенов |

---

## Деплой на VPS

### Вариант A — Docker Compose (рекомендуется)

```bash
# на VPS (Ubuntu): установить Docker + compose plugin
git clone <repo> && cd "week 6/day 5"

cp .env.example .env
# отредактировать .env: задать API_KEYS (openssl rand -hex 24), MODEL

docker compose up -d --build              # поднимет ollama + api
docker compose exec ollama ollama pull qwen2.5:1.5b   # скачать модель в том

curl http://localhost:5008/v1/health      # проверить
```

Наружу открыт только порт **5008** (API). Ollama — во внутренней сети Docker,
недоступен извне.

### Вариант B — systemd (без Docker)

```bash
# Ollama как сервис
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen2.5:1.5b

# код в /opt/llm-service, свой venv
sudo useradd -r -s /usr/sbin/nologin llm
sudo cp -r . /opt/llm-service && cd /opt/llm-service
python3 -m venv venv && venv/bin/pip install -r requirements.txt
cp .env.example .env   # заполнить

sudo cp deploy/llm-service.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now llm-service
```

### Reverse proxy + TLS

```bash
sudo apt install nginx
sudo cp deploy/nginx.conf /etc/nginx/sites-available/llm && \
  sudo ln -s /etc/nginx/sites-available/llm /etc/nginx/sites-enabled/
# заменить server_name на свой домен
sudo certbot --nginx -d your-domain.example   # Let's Encrypt TLS
sudo systemctl reload nginx
```

### Firewall

```bash
sudo ufw allow 22,80,443/tcp && sudo ufw enable   # 5008 наружу НЕ открываем
```

---

## Замечания по проду

- **Аутентификация обязательна** — задать `API_KEYS`; без них auth выключен
  (только для локальной разработки).
- **Rate limit** — in-memory на процесс. Для нескольких воркеров/инстансов
  вынести в Redis (лимит должен быть общим).
- **Инференс сериализуется Ollama** — параллельные запросы к модели встают в
  очередь; воркеры gunicorn дают параллелизм ввода-вывода (стриминг, health).
  Для нагрузки — модель побольше на GPU-VPS и/или несколько Ollama.
- **TLS** — терминировать на nginx; наружу только 443.

---

## Структура

```
day 5/
├── service.py         # Flask API + UI: auth, rate limit, лимит контекста, стриминг
├── config.py          # настройки из env
├── ratelimit.py       # rate-limiter (скользящее окно)
├── ollama_client.py   # клиент локального Ollama
├── templates/index.html
├── test_service.py    # сеть / стабильность / rate limit / max context
├── Dockerfile
├── docker-compose.yml # ollama + api
├── deploy/
│   ├── nginx.conf         # reverse proxy (+TLS)
│   └── llm-service.service # systemd-юнит
├── .env.example
├── requirements.txt
└── README.md
```
