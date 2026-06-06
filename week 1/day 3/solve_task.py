import os

from openai import OpenAI

API_KEY = os.environ["DEEPSEEK_API_KEY"]
BASE_URL = "https://api.deepseek.com"
MODEL = "deepseek-chat"

# Классическая алгебраическая задача-головоломка с однозначным правильным
# ответом (куры — 23, кролики — 12), удобная для проверки точности решения:
# 23 + 12 = 35 голов; 23*2 + 12*4 = 46 + 48 = 94 ноги.
TASK = (
    "На ферме живут куры и кролики. Всего у них 35 голов и 94 ноги. "
    "Сколько на ферме кур и сколько кроликов?"
)

client = OpenAI(api_key=API_KEY, base_url=BASE_URL)


def ask(prompt: str) -> str:
    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content


def direct_answer() -> str:
    return ask(TASK)


def step_by_step() -> str:
    return ask(f"{TASK}\n\nРешай пошагово, показывая все рассуждения и вычисления.")


def generated_prompt() -> tuple[str, str]:
    meta_prompt = (
        "Сформулируй наилучший промпт (инструкцию) для языковой модели, "
        "который поможет точно и без ошибок решить следующую задачу:\n\n"
        f"{TASK}\n\n"
        "Выведи только текст этого промпта, без решения самой задачи."
    )
    generated = ask(meta_prompt)
    solution = ask(generated)
    return generated, solution


def expert_panel() -> str:
    prompt = (
        f"Задача: {TASK}\n\n"
        "Реши эту задачу, последовательно собрав мнение группы экспертов:\n"
        "1. Аналитик — формализует условие задачи и предлагает математическую модель (систему уравнений).\n"
        "2. Инженер — выполняет вычисления по этой модели и получает числовой ответ.\n"
        "3. Критик — проверяет результат на корректность (подставляет числа обратно в условие) "
        "и указывает на ошибки, если они есть, либо подтверждает правильность ответа.\n\n"
        "Выведи рассуждения каждого эксперта по отдельности (с подзаголовками 'Аналитик', "
        "'Инженер', 'Критик') и в конце дай итоговый согласованный ответ."
    )
    return ask(prompt)


if __name__ == "__main__":
    print("ЗАДАЧА:", TASK)
    print("Правильный ответ: куры — 23, кролики — 12\n")

    print("=" * 70)
    print("1) ПРЯМОЙ ОТВЕТ БЕЗ ДОПОЛНИТЕЛЬНЫХ ИНСТРУКЦИЙ")
    print("=" * 70)
    print(direct_answer())

    print("\n" + "=" * 70)
    print("2) ИНСТРУКЦИЯ «РЕШАЙ ПОШАГОВО»")
    print("=" * 70)
    print(step_by_step())

    print("\n" + "=" * 70)
    print("3) СНАЧАЛА СГЕНЕРИРОВАН ПРОМПТ, ЗАТЕМ ОН ИСПОЛЬЗОВАН ДЛЯ РЕШЕНИЯ")
    print("=" * 70)
    gen_prompt, gen_solution = generated_prompt()
    print("--- Сгенерированный промпт ---")
    print(gen_prompt)
    print("\n--- Решение по сгенерированному промпту ---")
    print(gen_solution)

    print("\n" + "=" * 70)
    print("4) ГРУППА ЭКСПЕРТОВ (АНАЛИТИК, ИНЖЕНЕР, КРИТИК)")
    print("=" * 70)
    print(expert_panel())
