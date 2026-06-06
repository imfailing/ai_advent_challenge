# DeepSeek Chat Service

Простой сервис на Python, который отправляет запрос к DeepSeek LLM через API,
получает ответ и выводит его в консоль.

## Установка

```bash
pip install openai
```

## Настройка

Установите переменную окружения с ключом API:

```bash
export DEEPSEEK_API_KEY="ваш_ключ"
```

## Запуск

```bash
python deepseek_chat.py
```

## Как это работает

DeepSeek API совместим с OpenAI API, поэтому используется официальный
SDK `openai` с указанием `base_url="https://api.deepseek.com"` и
модели `deepseek-chat`.
