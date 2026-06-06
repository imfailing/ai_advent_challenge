import os

from openai import OpenAI

API_KEY = os.environ["DEEPSEEK_API_KEY"]
BASE_URL = "https://api.deepseek.com"
MODEL = "deepseek-chat"

BASE_PROMPT = "Расскажи, что такое нейронная сеть."

CONSTRAINED_PROMPT = (
    f"{BASE_PROMPT}\n\n"
    "Формат ответа: ровно три пронумерованных пункта (1, 2, 3), "
    "каждый — одно короткое предложение.\n"
    "Ограничение длины: не более 60 слов суммарно.\n"
    "Условие завершения: после третьего пункта поставь строку 'КОНЕЦ' "
    "и не добавляй больше никакого текста."
)


def ask(prompt: str, max_tokens: int | None = None, stop: list[str] | None = None) -> str:
    client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
        stop=stop,
    )
    return response.choices[0].message.content


if __name__ == "__main__":
    print("=== Без ограничений ===")
    unconstrained = ask(BASE_PROMPT)
    print(unconstrained)

    print("\n=== С ограничениями (формат, длина, стоп-условие) ===")
    constrained = ask(CONSTRAINED_PROMPT, max_tokens=120, stop=["КОНЕЦ"])
    print(constrained)
