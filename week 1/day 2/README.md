# Day 2 — Контроль формата и объёма ответа

Скрипт отправляет к DeepSeek **один и тот же базовый запрос** дважды:

- без каких-либо ограничений;
- с явным описанием формата ответа, ограничением длины и условием
  завершения (стоп-словом).

Результаты сравнения и выводы — в [results.md](results.md).
Сырой вывод обоих запусков — в [output_raw.txt](output_raw.txt).

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
python compare_responses.py
```
