# Week 7 / Day 5 — Веб-сервис AI-анализа GitHub-репозитория

Веб-сервис, который анализирует **удалённый GitHub-репозиторий** по коммитам и
формирует либо нейтральный **дайджест изменений**, либо 🐓 **rooster-роаст**
(включён по умолчанию). Опционально публикует результат в Telegram. Готов к
деплою на VPS в Docker.

Только веб-интерфейс, только удалённые репозитории (GitHub REST API) —
ни CLI, ни локального git.

**Токены задаются в интерфейсе** (⚙ Токены), а не через переменные окружения:
ключ DeepSeek (обязателен), GitHub-токен (опц.), Telegram bot token + chat_id
(опц.). Токены хранятся в localStorage браузера и уходят на сервер только в
момент запроса — сервер их не хранит и не читает из окружения.

> **Границы rooster-режима.** Роаст жжёт по **коду и коммитам** (жанр
> savage code review), а не по авторам как людям: без оскорблений по признакам
> личности, угроз и травли. Сервис только **читает** внешние репо и публикует
> роаст только в **свой** Telegram — он не автопостит комментарии в чужие
> репозитории (это был бы харассмент мейнтейнеров).

---

## Как работает

```
GitHub-репо (owner/repo или ссылка)
  │  github_repo.py → GitHub REST API → последние N коммитов
  ▼
digest.py → DeepSeek:
  tone=neutral → 📰 дайджест (Главное / Новое / Исправления / Документация / Прочее)
  tone=toxic   → 🔥 роаст   (Вердикт / Разбор коммитов / Советы / Оценка)
  ▼
рендер в вебе  →  (опц.) публикация в свой Telegram
```

- **`github_repo.py`** — чтение коммитов внешнего репо (публичные — без токена;
  GitHub-токен из интерфейса для приватных и лимитов).
- **`digest.py`** — AI-дайджест / роаст (ключ DeepSeek передаётся параметром).
- **`notify.py`** — публикация в Telegram (токен/chat_id из запроса; мягкая
  деградация без них).
- **`app.py`** — Flask (порт 5011): `/`, `/health`, `/generate`, `/publish`.

---

## HTTP API

| Метод | Путь | Описание |
|---|---|---|
| GET | `/` | веб-интерфейс |
| GET | `/health` | статус сервиса (`{status: "ok"}`) |
| POST | `/generate` | `{repo, last, toxic, deepseek_key, github_token}` → `{digest, commits, source, tone}` |
| POST | `/publish` | `{telegram_token, telegram_chat_id}` — опубликовать последний результат в Telegram |

---

## Деплой на VPS (Docker)

Как на неделе 6: контейнер + `docker compose`. Монтировать ничего не нужно —
сервис ходит в GitHub по API.

```bash
# на VPS: Docker + плагин Compose (см. week 6/day 5 при проблемах с 'docker compose')
git clone <repo> && cd "week 7/day 5"

docker compose up --build --detach        # http://<IP>:5011
curl http://localhost:5011/health         # {"status":"ok"}
# токены (DeepSeek / GitHub / Telegram) вводятся в интерфейсе (⚙ Токены)
```

Наружу открыт только порт **5011**. Быстрый доступ для теста:

```bash
sudo ufw allow 5011/tcp              # http://<IP>:5011
```

### Reverse proxy nginx + TLS (как на неделе 6)

Готовый конфиг — `deploy/nginx.conf` (проксирует на `127.0.0.1:5011`). Порядок:

```bash
sudo apt install -y nginx

# положить конфиг и включить сайт
sudo cp deploy/nginx.conf /etc/nginx/sites-available/digest
sudo sed -i 's/your-domain.example/ваш-домен/' /etc/nginx/sites-available/digest
sudo ln -s /etc/nginx/sites-available/digest /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx      # проверка + перезагрузка

# HTTPS через Let's Encrypt (нужен плагин nginx для certbot)
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d ваш-домен                 # добавит 443 + редирект с 80
```

Теперь сервис открывается по `https://ваш-домен` — порт 5011 наружу открывать
не нужно (проксирует nginx). Требования: домен с A-записью на VPS (Let's Encrypt
не выдаёт сертификат на голый IP).

> Грабли деплоя (нет `docker compose`, права на docker.sock, «unable to locate
> package docker-compose-plugin», certbot без nginx-плагина) разобраны в
> `week 6/day 5/README.md`.

### Токены (вводятся в интерфейсе, ⚙ Токены)

| Токен | Нужен | Зачем |
|---|---|---|
| DeepSeek ключ | да | генерация дайджеста/роаста |
| GitHub токен | опц. | приватные репо и лимиты GitHub API |
| Telegram bot token + chat_id | опц. | публикация в Telegram |

Сервер не читает токены из окружения и не хранит их: они приходят в теле
запроса и живут только в localStorage браузера пользователя.

---

## Локальный запуск (для разработки)

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python app.py                         # http://localhost:5011
# ключ DeepSeek и остальные токены — в интерфейсе (⚙ Токены)
```

Для прогона теста ключ берётся из окружения:

```bash
export DEEPSEEK_API_KEY="ваш_ключ"
python test_digest.py
```

---

## Проверка (`test_digest.py`)

- ✅ чтение коммитов внешнего репо (`octocat/Hello-World`);
- ✅ нейтральный дайджест — все разделы;
- ✅ токсичный роаст — свои разделы;
- ✅ Telegram без токена → `skipped`;
- ✅ веб `/generate` / `/publish`.

---

## Структура

```
day 5/
├── github_repo.py   # коммиты удалённого GitHub-репо (REST API)
├── digest.py        # AI: дайджест (neutral) или роаст (toxic) — DeepSeek
├── notify.py        # публикация в Telegram (мягкая деградация)
├── app.py           # Flask веб-сервис (порт 5011)
├── templates/index.html
├── Dockerfile · docker-compose.yml   # деплой на VPS
├── deploy/nginx.conf                 # reverse proxy (порт 5011, +TLS через certbot)
├── test_digest.py
├── requirements.txt
└── README.md
```
