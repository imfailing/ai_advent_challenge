# Week 7 / Day 5 — Веб-сервис AI-анализа GitHub-репозитория

Веб-сервис, который анализирует **удалённый GitHub-репозиторий** по коммитам и
формирует либо нейтральный **дайджест изменений**, либо 🔥 **токсичный роаст**.
Опционально публикует результат в Telegram. Готов к деплою на VPS в Docker.

Только веб-интерфейс, только удалённые репозитории (GitHub REST API) —
ни CLI, ни локального git.

> **Границы токсичного режима.** Роаст жжёт по **коду и коммитам** (жанр
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
  `GITHUB_TOKEN` для приватных и лимитов).
- **`digest.py`** — AI-дайджест / роаст.
- **`notify.py`** — публикация в Telegram (мягкая деградация без токенов).
- **`app.py`** — Flask (порт 5011): `/`, `/health`, `/generate`, `/publish`.

---

## HTTP API

| Метод | Путь | Описание |
|---|---|---|
| GET | `/` | веб-интерфейс |
| GET | `/health` | статус: наличие ключей (DeepSeek / GitHub / Telegram) |
| POST | `/generate` | `{repo, last, toxic, title}` → `{digest, commits, source, tone}` |
| POST | `/publish` | опубликовать последний результат в Telegram |

---

## Деплой на VPS (Docker)

Как на неделе 6: контейнер + `docker compose`. Монтировать ничего не нужно —
сервис ходит в GitHub по API.

```bash
# на VPS: Docker + плагин Compose (см. week 6/day 5 при проблемах с 'docker compose')
git clone <repo> && cd "week 7/day 5"

export DEEPSEEK_API_KEY="ваш_ключ"
# опц.: export GITHUB_TOKEN=...  TELEGRAM_BOT_TOKEN=...  TELEGRAM_CHAT_ID=...

docker compose up --build --detach        # http://<IP>:5011
curl http://localhost:5011/health
```

Наружу открыт только порт **5011**. Открыть доступ / TLS — reverse proxy nginx
+ certbot (гайд и грабли — в `week 6/day 5/README.md`):

```bash
sudo ufw allow 5011/tcp              # быстрый доступ по http://<IP>:5011
# или nginx + домен + certbot для https://<домен>
```

### Секреты

| Переменная | Нужна | Зачем |
|---|---|---|
| `DEEPSEEK_API_KEY` | да | генерация дайджеста/роаста |
| `GITHUB_TOKEN` | опц. | приватные репо и лимиты GitHub API |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` | опц. | публикация в Telegram |

---

## Локальный запуск (для разработки)

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
export DEEPSEEK_API_KEY="ваш_ключ"
python app.py                         # http://localhost:5011
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
├── test_digest.py
├── requirements.txt
└── README.md
```
