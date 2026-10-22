# AI Advent Challenge — правила проекта (v2)

Монорепозиторий учебного челленджа: каждая неделя/день — **самостоятельное** приложение
в `week N/day M/` (свой `venv`, свой `requirements.txt`, свой порт). Общего пакета нет:
нужный модуль копируется между днями. Подробный контекст — в `claude/` (stack.md,
architecture.md, apis.md, project.md). `week 8/day 1/` — копия сервиса week 7/day 5 + `/stats`, на ней отрабатывались эти правила (результаты — `week 8/day 1/rules-experiment/`).

## Стек
- Python 3.13, Flask 3 (+ gunicorn в проде), SQLite (stdlib `sqlite3`), `openai` SDK
  с `base_url=https://api.deepseek.com`, модель `deepseek-v4-flash`.
- HTTP к внешним API — stdlib `urllib` (без `requests`). Фронт — один `templates/index.html`,
  vanilla JS + CDN (`marked.js`), без сборки.
- Линтер: `ruff check "week 8/day 1"` (конфиг — `ruff.toml` в корне). Должен проходить без ошибок.

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
   `os.environ` в этом сервисе не читаются. Нигде не хардкодятся.
4. Ошибки API — всегда JSON `{"error": "<по-русски>"}` + код 400 (ввод) / 500 (внутри).
5. Числовые параметры запроса ограничиваются: `max(1, min(int(x or 15), 100))`.
   Дефолт `last` — **15** (как в `/generate`), `int()` оборачивать в `try/except (TypeError, ValueError)` → 400.
6. Проверка дня — `test_*.py` со строками `✅ …` и финальным `✅ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ — <что именно>`.
7. Тесты не ходят в сеть и не требуют ключей, если это не интеграционный `test_digest.py`:
   внешние вызовы подменяются через `unittest.mock.patch(...)` (контекст-менеджер),
   **никогда не присваивать `module.func = lambda ...`** — подмена протекает в другие тесты.
8. Новый маршрут делает то же, что соседние: `request.get_json(force=True) or {}`, `.strip()` строк,
   тот же текст ошибки про репозиторий, `github_repo.repo_label(repo)` для поля `source`.

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

## Definition of Done (для любой фичи — выполнить ВСЕ пункты, иначе не «готово»)
1. Код: логика в доменном модуле, в `app.py` только маршрут.
2. Тест `test_<что>.py` рядом, в стиле `✅`, запущен — вывод показан.
3. `ruff check "week 8/day 1"` (из корня) — `All checks passed!`.
4. `README.md` дня: (а) строка в списке модулей для **каждого нового файла**, (б) строка в таблице
   эндпоинтов, (в) пример `curl` с реальным телом запроса и примером ответа.
5. Документы `claude/`: `apis.md` (новый эндпоинт), `architecture.md` (новый модуль), `project.md`
   (прогресс) — по одной строке; секреты — только плейсхолдеры.
6. Самопроверка по списку «Антипаттерны» ниже: пройтись по каждому пункту `grep`-ом по дифу.
7. В финальном отчёте: список файлов, вывод ruff и теста, что НЕ проверено (сеть/LLM).

## Антипаттерны (запрещено)
- ❌ `print()` в коде сервиса (только в CLI-блоке `__main__` и в тестах) — нужен `# noqa: T201`.
- ❌ Хардкод ключей/токенов; чтение секретов из env в этом сервисе; ключи в логах и ответах.
- ❌ `except:` / голый `except Exception: pass` — ошибка должна дойти до пользователя.
- ❌ `raise X(...)` внутри `except` без `from e`.
- ❌ SQL через f-строки/конкатенацию — только параметры `?`.
- ❌ `requests`/новые зависимости без необходимости (есть `urllib`, `openai`).
- ❌ Бизнес-логика в `app.py`; Flask-импорты в доменных модулях.
- ❌ Ответ ошибки как HTML/plain text — только JSON.
- ❌ Подмена функций присваиванием в тестах (`mod.f = lambda …`) — только `mock.patch`.
- ❌ Новая функция-обёртка над уже существующей (`github_repo.get_commits`, `repo_label`, `parse_repo`) — переиспользуй.
- ❌ Отдельный путь ошибок с другим форматом/кодом, чем у соседних маршрутов.
- ❌ `Optional[X]`, `List[X]`, `Dict` из typing — только `X | None`, `list[X]`.

## Шаблон нового маршрута (копируй структуру `/generate`)
```python
@app.route("/stats", methods=["POST"])
def stats():
    data = request.get_json(force=True) or {}
    repo = (data.get("repo") or "").strip()
    if not repo:
        return jsonify({"error": "Укажите GitHub-репозиторий (owner/repo или ссылку)."}), 400
    try:
        last = max(1, min(int(data.get("last") or 15), 100))
    except (TypeError, ValueError):
        return jsonify({"error": "Параметр last должен быть числом."}), 400
    try:
        commits = github_repo.get_commits(repo, last=last, token=(data.get("github_token") or "").strip())
        label = github_repo.repo_label(repo)
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    return jsonify({"source": label, **activity.compute_stats(commits)})
```

## Шаблон теста
```python
"""Проверка <что> (без сети)."""
from unittest import mock

import app as app_module


def main() -> None:
    with mock.patch("github_repo.get_commits", return_value=COMMITS):
        r = app_module.app.test_client().post("/x", json={"repo": "o/r"})
    assert r.status_code == 200
    print("✅ /x: успех")
    print("\n✅ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ — <что>")


if __name__ == "__main__":
    main()
```

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
- Скилл `new-endpoint` (`.claude/skills/`) — пошаговое добавление эндпоинта (включает DoD).
- Если инструмент запуска субагентов недоступен — выполни чек-лист `py-reviewer` сам и приведи его в отчёте.

## Правила работы
- Язык: русский. Не коммитить без просьбы. Не трогать чужие дни (`week N/day M`), кроме запрошенного.
- Ничего не готово, пока не выполнен Definition of Done целиком.
- Линтер: `ruff check "week 8/day 1"` из корня (`src` в `ruff.toml` указывает на этот день; для другого — поправить).

## Локальные правила сервиса (week 8/day 1, копия week 7/day 5)
- Порт 5011 (`PORT` из env), запуск: `./venv/bin/python app.py`; прод — gunicorn в Docker.
- Файлы: `app.py` (маршруты), `digest.py` (AI), `github_repo.py` (GitHub REST, только чтение),
  `notify.py` (Telegram), `activity.py` (статистика), `test_digest.py`, `test_stats.py`.
- Все токены — из тела запроса; `os.environ` читает только `PORT` и тест (`DEEPSEEK_API_KEY`).
- Только чтение внешних репозиториев; никаких комментариев/записи в чужие репо.
- `get_commits` отдаёт `{hash, date, author, subject, body}` — переиспользуй, не пиши второй клиент GitHub.
