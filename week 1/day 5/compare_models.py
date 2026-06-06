import time
import uuid
import warnings

import requests
import urllib3
from openai import OpenAI

warnings.filterwarnings("ignore")
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

import os

DEEPSEEK_API_KEY = os.environ["DEEPSEEK_API_KEY"]
DEEPSEEK_BASE_URL = "https://api.deepseek.com"

GIGACHAT_AUTH_KEY = os.environ["GIGACHAT_AUTH_KEY"]
GIGACHAT_SCOPE = os.environ.get("GIGACHAT_SCOPE", "GIGACHAT_API_PERS")
GIGACHAT_OAUTH_URL = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
GIGACHAT_API_URL = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"

PROMPT = "Объясни простыми словами, что такое рекурсия в программировании, и приведи короткий пример."

# Ориентировочные тарифы (сравнительные, по данным официальных страниц цен на
# момент подготовки задания). GigaChat Lite в персональном API доступен в
# рамках бесплатной квоты, поэтому для него стоимость запроса принимаем за 0.
PRICING_PER_1M_TOKENS = {
    # (вход, выход), USD за 1 млн токенов, тариф "cache miss"
    "deepseek-chat": (0.27, 1.10),
    "deepseek-reasoner": (0.55, 2.19),
}


def get_gigachat_token() -> str:
    response = requests.post(
        GIGACHAT_OAUTH_URL,
        headers={
            "Authorization": f"Basic {GIGACHAT_AUTH_KEY}",
            "RqUID": str(uuid.uuid4()),
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={"scope": GIGACHAT_SCOPE},
        verify=False,
    )
    response.raise_for_status()
    return response.json()["access_token"]


def ask_gigachat(prompt: str) -> dict:
    token = get_gigachat_token()
    started = time.perf_counter()
    response = requests.post(
        GIGACHAT_API_URL,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json={
            "model": "GigaChat",
            "messages": [{"role": "user", "content": prompt}],
        },
        verify=False,
    )
    elapsed = time.perf_counter() - started
    response.raise_for_status()
    data = response.json()
    return {
        "answer": data["choices"][0]["message"]["content"].strip(),
        "elapsed": elapsed,
        "prompt_tokens": data["usage"]["prompt_tokens"],
        "completion_tokens": data["usage"]["completion_tokens"],
        "total_tokens": data["usage"]["total_tokens"],
        "cost_usd": 0.0,
        "cost_note": "входит в бесплатную квоту персонального API GigaChat",
    }


def ask_deepseek(prompt: str, model: str) -> dict:
    client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url=DEEPSEEK_BASE_URL)
    started = time.perf_counter()
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
    )
    elapsed = time.perf_counter() - started
    usage = response.usage
    price_in, price_out = PRICING_PER_1M_TOKENS[model]
    cost = (usage.prompt_tokens * price_in + usage.completion_tokens * price_out) / 1_000_000
    return {
        "answer": response.choices[0].message.content.strip(),
        "elapsed": elapsed,
        "prompt_tokens": usage.prompt_tokens,
        "completion_tokens": usage.completion_tokens,
        "total_tokens": usage.total_tokens,
        "cost_usd": cost,
        "cost_note": f"по тарифу ${price_in}/1M вход, ${price_out}/1M выход",
    }


MODELS = [
    ("Слабая — GigaChat (Lite)", lambda: ask_gigachat(PROMPT)),
    ("Средняя — DeepSeek deepseek-chat (V3)", lambda: ask_deepseek(PROMPT, "deepseek-chat")),
    ("Сильная — DeepSeek deepseek-reasoner (R1)", lambda: ask_deepseek(PROMPT, "deepseek-reasoner")),
]


if __name__ == "__main__":
    print("ЗАПРОС:", PROMPT)
    print()
    for title, runner in MODELS:
        print("=" * 70)
        print(title)
        print("=" * 70)
        result = runner()
        print(f"Время ответа:        {result['elapsed']:.2f} с")
        print(f"Токены (запрос):     {result['prompt_tokens']}")
        print(f"Токены (ответ):      {result['completion_tokens']}")
        print(f"Токены (всего):      {result['total_tokens']}")
        print(f"Стоимость:           ${result['cost_usd']:.6f} ({result['cost_note']})")
        print("\nОтвет модели:")
        print(result["answer"])
        print()
