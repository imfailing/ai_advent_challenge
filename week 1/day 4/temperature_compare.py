import os

from openai import OpenAI

API_KEY = os.environ["DEEPSEEK_API_KEY"]
BASE_URL = "https://api.deepseek.com"
MODEL = "deepseek-chat"

TEMPERATURES = [0, 0.7, 1.2]
RUNS_PER_TEMPERATURE = 3

# Творческая задача — на ней хорошо видно разнообразие и креативность
# (или их отсутствие) при разных температурах.
CREATIVE_PROMPT = "Придумай короткий слоган для новой кофейни на углу улицы."

# Фактологическая задача с единственным правильным ответом — на ней хорошо
# видно, как температура влияет на точность.
FACTUAL_PROMPT = "Сколько будет 17 умножить на 24? Ответь только числом."

client = OpenAI(api_key=API_KEY, base_url=BASE_URL)


def ask(prompt: str, temperature: float) -> str:
    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
    )
    return response.choices[0].message.content.strip()


def run_section(title: str, prompt: str) -> None:
    print("=" * 70)
    print(title)
    print(f"Промпт: {prompt}")
    print("=" * 70)
    for temperature in TEMPERATURES:
        print(f"\n--- temperature = {temperature} ---")
        for i in range(1, RUNS_PER_TEMPERATURE + 1):
            answer = ask(prompt, temperature)
            print(f"[{i}] {answer}")


if __name__ == "__main__":
    run_section("ТВОРЧЕСКАЯ ЗАДАЧА (слоган для кофейни)", CREATIVE_PROMPT)
    print()
    run_section("ФАКТОЛОГИЧЕСКАЯ ЗАДАЧА (17 × 24 = 408)", FACTUAL_PROMPT)
