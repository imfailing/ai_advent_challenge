# Подключение к серверу (llm-server)

Сервер: Minisforum, AMD Ryzen AI Max+ 395 (Radeon 8060S), 122 ГБ общей памяти, Ubuntu.
Сеть: локальная, есть адрес в Tailscale. IP-адреса в репозиторий не вписываем: они лежат в `CLAUDE.local.md` и в SSH-алиасе `llm-server` (`~/.ssh/config`).

## LLM API (OpenAI-совместимый)

- Базовый адрес: `$LLAMA_BASE_URL` (вида `http://<адрес сервера>:8080/v1`, значение — в `CLAUDE.local.md`)
- Авторизация: заголовок `Authorization: Bearer $LLAMA_API_KEY`. Ключ лежит в переменной окружения `LLAMA_API_KEY`; в код и репозитории его не вписывать, в ответах и логах не показывать.
- Модель сейчас: `qwen3.5-122b` (Qwen3.5-122B-A10B, Q4). Список моделей: `GET /v1/models`.
- Контекст 65536 токенов, один слот: запросы идут по очереди.
- Это reasoning-модель, часть токенов уходит на рассуждение. Ставьте `max_tokens` не меньше 4000, иначе `content` может прийти пустым (смотрите также `reasoning_content`).
- Скорость: ~21 токен/с на генерацию, ~60 токенов/с на промпт.
- `GET /health` работает без ключа, остальное без ключа вернёт 401.

```bash
curl -s $LLAMA_BASE_URL/chat/completions \
  -H "Authorization: Bearer $LLAMA_API_KEY" -H "Content-Type: application/json" \
  -d '{"model":"qwen3.5-122b","messages":[{"role":"user","content":"Привет"}],"max_tokens":4000}'
```

```python
from openai import OpenAI
import os

client = OpenAI(base_url=os.environ["LLAMA_BASE_URL"], api_key=os.environ["LLAMA_API_KEY"])
```

## Другая модель

На сервере есть вторая: `gpt-oss-120b` (быстрее, ~55 токенов/с). Две модели сразу не помещаются в память, поэтому работает одна. Переключение требует `sudo` и делается человеком:

```bash
ssh -t llm-server 'sudo systemctl start llama-gptoss'   # gpt-oss-120b
ssh -t llm-server 'sudo systemctl start llama-qwen'     # Qwen3.5-122B (по умолчанию после загрузки)
```

После смены модели меняйте значение `model` в запросах. Агент без `sudo` переключать модели не должен.

## SSH

- Пользователь `asv1337`, вход только по ключу, пароль отключён: `ssh llm-server`.
- Модели лежат в `~/models`, сборки llama.cpp: `~/llm/llama` (ROCm) и `~/llm/llama-vulkan` (Vulkan), Python-окружение `~/llm-env`.
- Логи сервиса: `journalctl -u llama-qwen -n 50 --no-pager`.

## Мониторинг (Glances)

- Веб: `http://<адрес сервера>:61208`, API: `…:61208/api/4/quicklook`, `/api/4/mem`, `/api/4/cpu`.
- MCP-сервер Glances: порт `61209`.
- Без авторизации, только чтение.

## Чего не делать

- Не запускать вторую модель рядом с работающей: памяти не хватит, сервис может упасть.
- Не останавливать `llama-qwen` / `llama-gptoss` и не убивать `llama-server` без просьбы владельца.
- Не удалять файлы в `~/models`, это 230+ ГБ скачанных моделей.
- Не выводить `LLAMA_API_KEY` и не отправлять его никуда, кроме этого сервера.
