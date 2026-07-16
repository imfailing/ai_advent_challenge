# Week 7 / Day 2 — Автоматическое AI-ревью кода (PR)

Пайплайн, в котором ассистент анализирует Pull Request: получает **diff** и
изменённые файлы, использует **RAG** по документации и коду проекта и выдаёт
структурированное **ревью** (баги · архитектура · рекомендации). Запускается
как **GitHub Action** на каждый PR и оставляет ревью комментарием.

---

## Пайплайн

```
Pull Request
  │  GitHub Action (.github/workflows/pr-review.yml)
  ▼
git diff origin/<base>...HEAD                    ← diff + изменённые файлы
  │
reviewer.py:
  ├─ RAG: по diff ищем контекст в индексе (конвенции проекта + соседний код)
  ├─ DeepSeek: ревью по разделам
  ▼
review.md  ──▶  gh pr comment  ──▶  комментарий в PR
```

- **`project_loader.py`** — собирает **доки + код** проекта (README, `claude/*.md`,
  все `.py`, кроме venv/corpus).
- **`build_index.py`** — chunking + локальные эмбеддинги (fastembed) → SQLite-индекс.
- **`reviewer.py`** — diff → изменённые файлы → RAG-контекст → DeepSeek → ревью.
- **`.github/workflows/pr-review.yml`** — Action: строит индекс, считает diff,
  запускает ревьюер, постит комментарий.

---

## Что возвращает ревью

Строго по разделам (Markdown):

```
## 🐞 Потенциальные баги
## 🏛 Архитектурные проблемы
## 💡 Рекомендации
Вердикт: <одобрить / доработать>
```

Пример (на diff с намеренными багами) — ревьюер поймал:
- `KeyError` при отсутствии поля `tokens`;
- `ZeroDivisionError` при пустой истории;
- неверный вызов клиента (`self._client.chat` вместо `.chat.completions.create`);
- хардкод API-ключа в коде;

и сослался на конвенции проекта (`AgentResponse`, `_build_messages`,
`save_user_message`) из RAG-контекста. Вердикт: **доработать**.

---

## Локальный запуск

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
export DEEPSEEK_API_KEY="ваш_ключ"

python build_index.py                          # индекс доков+кода
git diff main...HEAD | python reviewer.py      # ревью текущих изменений
python reviewer.py --diff-file changes.diff    # ревью diff из файла
python reviewer.py --base origin/main --out review.md
```

---

## Подключение GitHub Action

Файл `.github/workflows/pr-review.yml` (в корне репозитория) уже готов.
Нужно один раз задать секрет:

```
Settings → Secrets and variables → Actions → New secret
  DEEPSEEK_API_KEY = <ваш ключ>
```

Дальше на каждый PR (`opened`/`synchronize`/`reopened`) Action:
1. чекаутит репо с историей;
2. кэширует модель fastembed, ставит зависимости;
3. строит индекс доков+кода;
4. считает `git diff origin/<base>...HEAD`;
5. запускает `reviewer.py` → `review.md`;
6. постит ревью комментарием (`gh pr comment`, через `GITHUB_TOKEN`).

Права: `pull-requests: write` (в workflow) — чтобы оставить комментарий.

---

## Проверка (`test_reviewer.py`)

- ✅ индекс доков+кода собран (1328 чанков);
- ✅ из diff извлекаются изменённые файлы;
- ✅ RAG возвращает релевантный контекст;
- ✅ ревью содержит все 3 раздела;
- ✅ ревьюер ловит деление на ноль и хардкод ключа.

---

## Структура

```
day 2/
├── project_loader.py   # доки + код проекта
├── chunking.py embedder.py index_store.py rerank.py   # RAG-пайплайн
├── build_index.py      # индексация
├── reviewer.py         # diff → RAG → ревью (CLI)
├── test_reviewer.py
├── requirements.txt
└── README.md
# .github/workflows/pr-review.yml — GitHub Action (в корне репо)
```
