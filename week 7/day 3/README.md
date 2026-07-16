# Week 7 / Day 3 — AI-ассистент поддержки пользователей

Мини-сервис поддержки продукта **CloudNote** (вымышленный SaaS заметок).
Ассистент отвечает на вопросы о продукте, используя **RAG** по FAQ/документации,
и **учитывает контекст тикета** (тариф пользователя, описание проблемы),
который берётся **через MCP** из JSON пользователей/тикетов.

Порт **5010**.

---

## Как работает

```
вопрос [+ тикет]
  │  1. если выбран тикет → MCP get_ticket → карточка тикета + пользователь (тариф)
  │  2. RAG: локальный поиск по документации продукта (FAQ, auth, plans, sync)
  │  3. DeepSeek: ответ с учётом документации И тарифа/проблемы из тикета
  ▼
ответ + источники (доки) + учтённый контекст тикета
```

- **`product_docs/`** — FAQ и документация продукта (auth, plans, sync, faq).
- **`data/support.json`** — пользователи и тикеты (тариф, устройства, описание).
- **`support_mcp_server.py`** — MCP-сервер над JSON: `get_ticket`, `get_user`,
  `list_tickets`.
- **`assistant.py`** — `SupportAssistant`: MCP-контекст тикета + RAG по докам +
  DeepSeek.
- **`app.py`** — Flask, выбор тикета + вопрос.

---

## Пример из задания

Тикет **T-1002**: пользователь на тарифе **Pro** спрашивает про вход через SSO.

> **Вопрос:** «Почему не работает авторизация через SSO?»
>
> **Ответ:** Вход через SSO **недоступен на вашем тарифе Pro** — эта функция
> входит только в **Business**. Отсутствие кнопки SSO — ожидаемое поведение…
> Чтобы подключить SSO, обновите тариф до Business (Настройки → Биллинг).
> *(источники: auth.md, plans.md, faq.md)*

Ассистент **соединил** документацию (SSO = Business-only) с **контекстом тикета**
(пользователь на Pro) и дал точный ответ. То же для T-1004 (Free → одно
устройство, синхронизации нет).

---

## Проверка (`test_support.py`)

- ✅ индекс документации продукта собран (12 чанков);
- ✅ `/tickets` отдаёт тикеты; MCP `get_ticket` подтягивает контекст;
- ✅ T-1002 (Pro, SSO) → ответ учёл тариф → **Business**, есть источники;
- ✅ T-1004 (Free) → ответ учёл ограничение тарифа;
- ✅ без тикета — ответ по документации (2FA).

```bash
python build_index.py
python test_support.py    # нужен DEEPSEEK_API_KEY
```

---

## Запуск

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
export DEEPSEEK_API_KEY="ваш_ключ"

python build_index.py     # индекс документации продукта
python app.py             # веб-чат на http://localhost:5010
```

В UI выберите тикет из списка (или «без тикета») и задайте вопрос — ответ
учтёт тариф и проблему из тикета.

---

## Структура

```
day 3/
├── product_docs/       # FAQ и документация продукта (auth/plans/sync/faq)
├── data/support.json   # пользователи + тикеты (для MCP)
├── doc_loader.py       # загрузка документации
├── chunking.py embedder.py index_store.py rerank.py   # RAG-пайплайн
├── build_index.py
├── support_mcp_server.py   # MCP: get_ticket / get_user / list_tickets
├── assistant.py        # SupportAssistant: MCP-тикет + RAG + DeepSeek
├── app.py              # Flask (порт 5010)
├── templates/index.html
├── test_support.py
├── requirements.txt
└── README.md
```
