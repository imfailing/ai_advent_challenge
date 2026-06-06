# Day 5 — Слабая, средняя и сильная модель

Скрипт отправляет один и тот же запрос («объясни рекурсию») трём моделям
разного уровня и замеряет время ответа, количество токенов и стоимость:

| Уровень   | Модель                 | Провайдер |
|-----------|------------------------|-----------|
| Слабая    | GigaChat (Lite)        | Sber      |
| Средняя   | deepseek-chat (V3)     | DeepSeek  |
| Сильная   | deepseek-reasoner (R1) | DeepSeek  |

Сравнение по качеству, скорости и ресурсоёмкости — в [results.md](results.md).
Сырой вывод запуска — в [output_raw.txt](output_raw.txt).

## Установка

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Настройка

Нужны два ключа:

```bash
export DEEPSEEK_API_KEY="ваш_ключ_DeepSeek"
export GIGACHAT_AUTH_KEY="ваш_authorization_key_GigaChat_в_base64"
export GIGACHAT_SCOPE="GIGACHAT_API_PERS"   # необязательно, это значение по умолчанию
```

`GIGACHAT_AUTH_KEY` — это Authorization key (Client ID:Client Secret в
base64) из личного кабинета Sber для GigaChat API.

## Запуск

```bash
source venv/bin/activate
python compare_models.py
```
