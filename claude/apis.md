# API-ключи и сервисы

> Ключи используются только при запуске через env-переменные.
> В коде всегда `os.environ["KEY_NAME"]`, никогда не хардкодить.

---

## DeepSeek

```
DEEPSEEK_API_KEY = <задаётся в окружении, не хранить в репозитории>
base_url         = https://api.deepseek.com
```

Клиент:
```python
from openai import OpenAI
client = OpenAI(api_key=os.environ["DEEPSEEK_API_KEY"], base_url="https://api.deepseek.com")
```

### Модели (актуально на июнь 2026)

| ID | Название | Характер | Контекст | Макс. ответ | Вход / 1M | Выход / 1M |
|---|---|---|---|---|---|---|
| `deepseek-v4-flash` | DeepSeek V4 Flash | быстрая, универсальная | 1M | 384K | $0.14 | $0.28 |
| `deepseek-v4-pro` | DeepSeek V4 Pro | точная, CoT | 1M | 384K | $0.435 | $0.87 |

Тарифы — cache miss. При cache hit значительно дешевле ($0.0028 и $0.003625 вход).

> **Устаревшие алиасы:** `deepseek-chat` → non-thinking режим V4 Flash,
> `deepseek-reasoner` → thinking режим V4 Flash. Удаляются 24.07.2026.

### Особенности

- `deepseek-v4-pro` поддерживает chain-of-thought (thinking-режим)
- `stop=["СЛОВО"]` и `max_tokens` работают ожидаемо
- `temperature` принимает 0–2; при 0 ответы почти идентичны
- **Embeddings НЕТ** — `client.embeddings.create(...)` → 404. Для эмбеддингов
  (week 5, RAG) используем локальный `fastembed` (ONNX): мультиязычная модель
  `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`, 384-dim.
  Ставится `pip install fastembed`, модель качается в кэш при первом embed.
- Нет официальной «слабой» модели — для градации используем GigaChat

---

## GigaChat (Sber)

```
GIGACHAT_AUTH_KEY = <задаётся в окружении, не хранить в репозитории>
Scope            = GIGACHAT_API_PERS
OAuth URL        = https://ngw.devices.sberbank.ru:9443/api/v2/oauth
API URL          = https://gigachat.devices.sberbank.ru/api/v1/chat/completions
Модель           = GigaChat   (Lite, бесплатная квота)
```

### Паттерн получения токена

```python
import requests, urllib3
urllib3.disable_warnings()

def get_gigachat_token(auth_key: str) -> str:
    resp = requests.post(
        "https://ngw.devices.sberbank.ru:9443/api/v2/oauth",
        headers={
            "Authorization": f"Basic {auth_key}",
            "RqUID": str(uuid.uuid4()),
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={"scope": "GIGACHAT_API_PERS"},
        verify=False,
    )
    return resp.json()["access_token"]
```

### Особенности

- SSL-сертификат Сбера не проходит проверку → `verify=False` обязательно
- Токен живёт ~30 минут; нужно обновлять при истечении
- Использовалась как «слабая» модель в day 5 week 1
