# DeepSeek Chat Service

Простой сервис на Python, который отправляет запрос к DeepSeek LLM через API,
получает ответ и выводит его в консоль.

## Установка

Создайте виртуальное окружение и установите зависимости:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Настройка

Установите переменную окружения с ключом API:

```bash
export DEEPSEEK_API_KEY="ваш_ключ"
```

## Запуск

```bash
source venv/bin/activate
python deepseek_chat.py
```

## Как это работает

DeepSeek API совместим с OpenAI API, поэтому используется официальный
SDK `openai` с указанием `base_url="https://api.deepseek.com"` и
модели `deepseek-chat`.
