# Week 2 / Day 1 — LLM Agent с веб-интерфейсом

Простой агент, инкапсулирующий логику работы с LLM, и Flask-приложение
с мини-чатом в браузере.

## Структура

```
day 1/
├── agent.py          # LLMAgent — самостоятельная сущность, всё API внутри
├── app.py            # Flask: только маршруты и рендеринг
├── templates/
│   └── index.html    # Веб-интерфейс (чат)
├── requirements.txt
└── README.md
```

**`agent.py`** содержит класс `LLMAgent` с единственным публичным методом
`ask(user_message) → AgentResponse`. Flask-приложение не знает ничего о
деталях API — оно просто вызывает агента и передаёт результат на фронт.

## Установка

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Настройка

```bash
export DEEPSEEK_API_KEY="ваш_ключ"
```

## Запуск

```bash
source venv/bin/activate
python app.py
```

Затем откройте в браузере: [http://localhost:5000](http://localhost:5000)

Введите любой запрос — агент ответит, и под ответом появятся метаданные:
модель, токены (вход → выход) и время ответа.
