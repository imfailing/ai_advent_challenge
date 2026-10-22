# AI Advent Challenge — правила проекта (v1)

Монорепозиторий учебного челленджа: каждая неделя/день — **самостоятельное** приложение
в `week N/day M/` (свой `venv`, свой `requirements.txt`, свой порт). Общего пакета нет:
нужный модуль копируется между днями. Подробный контекст — в `claude/` (stack.md,
architecture.md, apis.md, project.md). Актуальный (последний) код — `week 7/day 5/`.

## Стек
- Python 3.13, Flask 3 (+ gunicorn в проде), SQLite (stdlib `sqlite3`), `openai` SDK
  с `base_url=https://api.deepseek.com`, модель `deepseek-v4-flash`.
- HTTP к внешним API — stdlib `urllib` (без `requests`). Фронт — один `templates/index.html`,
  vanilla JS + CDN (`marked.js`), без сборки.
- Линтер: `ruff check "week 7/day 5"` (конфиг — `ruff.toml` в корне). Должен проходить без ошибок.

## Архитектура и структура дня (Flask-сервис)
```
day N/
├── app.py            # ТОЛЬКО маршруты: разбор запроса → вызов модулей → jsonify
├── <домен>.py        # логика (digest.py, github_repo.py, notify.py) — без Flask-импортов
├── test_<что>.py     # тест-скрипт с assert, запускается как `python test_x.py`
├── templates/index.html
├── requirements.txt  # pip freeze
└── README.md         # установка + запуск + примеры
```
Слои: `app.py` (HTTP) → доменные модули (чистые функции) → внешние API. Доменный модуль
не знает про Flask/`request`. Состояние процесса — модульный dict (`_last_digest`), не глобальные классы.

## Naming
- файлы/функции/переменные `snake_case`, константы `UPPER_SNAKE`, приватное — `_prefix`.
- Маршруты — короткие существительные/глаголы: `/generate`, `/publish`, `/health`.
- Ключи JSON-запроса/ответа — `snake_case` (`deepseek_key`, `telegram_chat_id`).

## Обязательные паттерны
1. Модуль начинается с docstring на русском: что делает и какую роль играет.
2. Типы везде: `list[dict]`, `str | None`, возвращаемые значения аннотированы.
3. Секреты (DeepSeek/GitHub/Telegram) приходят **в теле запроса** из интерфейса; из
   `os.environ` в week 7/day 5 не читаются. Нигде не хардкодятся.
4. Ошибки API — всегда JSON `{"error": "<по-русски>"}` + код 400 (ввод) / 500 (внутри).
5. Числовые параметры запроса ограничиваются: `max(1, min(int(x or 15), 100))`.
6. Проверка дня — `test_*.py` со строками `✅ …` и финальным «ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ».

## Хороший код (так хотим писать)

Валидация + JSON-ошибки + кламп параметров (`app.py`):
```python
@app.route("/generate", methods=["POST"])
def generate():
    data = request.get_json(force=True)
    deepseek_key = (data.get("deepseek_key") or "").strip()
    if not deepseek_key:
        return jsonify({"error": "Укажите ключ DeepSeek API."}), 400
    last = max(1, min(int(data.get("last") or 15), 100))
    try:
        commits = github_repo.get_commits(repo, last=last, token=github_token)
    except Exception as e:
        return jsonify({"error": str(e)}), 400
```

Доменная функция: типы, docstring, человекочитаемые ошибки (`github_repo.py`):
```python
def parse_repo(value: str) -> str:
    """Извлечь 'owner/repo' из URL или строки owner/repo."""
    value = value.strip().rstrip("/")
    m = re.search(r"github\.com[/:]([^/]+/[^/]+?)(?:\.git)?$", value)
    if m:
        return m.group(1)
    if re.fullmatch(r"[\w.-]+/[\w.-]+", value):
        return value
    raise ValueError("Ожидается 'owner/repo' или ссылка на GitHub-репозиторий")
```

Мягкая деградация вместо падения (`notify.py`):
```python
if not token or not chat_id:
    return {"status": "skipped", "reason": "не заданы токен бота и chat_id — публикация пропущена."}
```

Тест-скрипт (`test_digest.py`): `main()` с assert'ами и `print("✅ …")`, `if __name__ == "__main__": main()`.

## Антипаттерны (запрещено)
- ❌ `print()` в коде сервиса (только в CLI-блоке `__main__` и в тестах) — нужен `# noqa: T201`.
- ❌ Хардкод ключей/токенов; чтение секретов из env в week 7/day 5; ключи в логах и ответах.
- ❌ `except:` / голый `except Exception: pass` — ошибка должна дойти до пользователя.
- ❌ `raise X(...)` внутри `except` без `from e`.
- ❌ SQL через f-строки/конкатенацию — только параметры `?`.
- ❌ `requests`/новые зависимости без необходимости (есть `urllib`, `openai`).
- ❌ Бизнес-логика в `app.py`; Flask-импорты в доменных модулях.
- ❌ Ответ ошибки как HTML/plain text — только JSON.
- ❌ `Optional[X]`, `List[X]`, `Dict` из typing — только `X | None`, `list[X]`.

## Шаблон типового модуля
```python
"""
<Что делает модуль и его роль в сервисе.>
"""

import json
import re
import urllib.request

API = "https://example.com"      # константы


def public_fn(arg: str, last: int = 15) -> list[dict]:
    """<Короткий docstring по-русски.>"""
    ...


if __name__ == "__main__":       # необязательный CLI для ручной проверки
    ...
```
Порядок импортов: stdlib → сторонние → локальные (ruff `I` проверяет).

## Субагенты и скиллы
- Субагент `py-reviewer` (`.claude/agents/`) — ревью диффа по этим правилам.
- Скилл `new-endpoint` (`.claude/skills/`) — пошаговое добавление эндпоинта.

## Правила работы
- Язык: русский. Не коммитить без просьбы. Не трогать чужие дни (`week N/day M`), кроме запрошенного.
- Ничего не готово, пока не прошли `ruff check` и `python test_*.py`.
