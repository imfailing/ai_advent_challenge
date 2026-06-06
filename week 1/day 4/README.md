# Day 4 — Сравнение temperature = 0 / 0.7 / 1.2

Скрипт отправляет к DeepSeek один и тот же запрос несколько раз с разными
значениями `temperature` (0, 0.7, 1.2) — на творческой задаче (слоган для
кофейни) и на фактологической (простое умножение) — и позволяет сравнить
ответы по точности, креативности и разнообразию.

Сравнение и выводы — в [results.md](results.md).
Сырой вывод всех запусков — в [output_raw.txt](output_raw.txt).

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
python temperature_compare.py
```
