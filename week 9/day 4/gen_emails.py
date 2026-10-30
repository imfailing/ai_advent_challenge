"""
Генерация писем для дня 9. Сначала случайно выбирается «задание» (категория, тональность,
продукт, номер заказа, стиль), затем учитель пишет письмо под него. Задание — эталон по построению:
номер заказа и продукт заранее известны. Результат — data/emails_raw.jsonl.
Запуск: python gen_emails.py [число_писем]
"""

import json
import random
import sys
from pathlib import Path

import schema
import teacher

SEED = 9
ROOT = Path(__file__).parent
STYLES = [
    "формально, как в деловой переписке", "коротко, 1–2 фразы, без приветствия",
    "эмоционально, с восклицаниями", "небрежно, с опечатками и без запятых",
    "длинно, с лишними бытовыми подробностями", "вежливо, но настойчиво",
    "с вкраплениями английских слов", "сумбурно: сначала про одно, потом сразу про другое",
]
MOODS = {
    "billing": ["negative", "neutral"], "technical": ["negative", "neutral"],
    "delivery": ["negative", "neutral"], "account": ["negative", "neutral"],
    "refund": ["negative", "neutral"], "feedback": ["positive", "neutral", "negative"],
}
CATEGORY_HINT = {
    "billing": "вопрос по оплате, счёту или двойному списанию",
    "technical": "техническая проблема или ошибка в работе продукта",
    "delivery": "вопрос по доставке или срокам",
    "account": "доступ к аккаунту, пароль, смена данных",
    "refund": "просьба вернуть деньги",
    "feedback": "отзыв или пожелание по продукту",
}


def make_specs(n: int) -> list[dict]:
    """n случайных заданий; повторяемо (SEED)."""
    rng = random.Random(SEED)  # noqa: S311
    specs = []
    for _ in range(n):
        category = rng.choice(schema.CATEGORIES)
        sentiment = rng.choice(MOODS[category])
        amount = rng.choice([190, 349, 490, 790, 990, 1290, 1750, 2400, 3990, 5500, 12000])
        order_id = f"{rng.choice('ABCDEFGHKLMNPRSTVXZ')}{rng.choice('ABCDEFGHKLMNPRSTVXZ')}-{rng.randint(10000, 99999)}"
        specs.append({
            "category": category, "sentiment": sentiment,
            "product": rng.choice(schema.PRODUCTS) if rng.random() > 0.15 else None,
            "order_id": order_id if rng.random() < 0.55 else None,
            "amount_rub": amount if rng.random() < 0.4 else None,
            "action_required": not (category == "feedback" and sentiment == "positive"),
            "style": rng.choice(STYLES),
        })
    return specs


def spec_prompt(spec: dict) -> str:
    """Запрос учителю: написать письмо под задание, не называя метки прямо."""
    lines = [
        "Напиши одно письмо клиента в службу поддержки сервиса «Облачко» по-русски, 20–110 слов.",
        f"Тема: {CATEGORY_HINT[spec['category']]}.",
        f"Тональность: {spec['sentiment']} ({schema.SENTIMENT_RULES}).",
        f"Стиль: {spec['style']}.",
    ]
    lines.append(f"Продукт: {spec['product']} (назови естественно, можно в падеже)." if spec["product"]
                 else "Конкретный продукт не называй.")
    lines.append(f"Номер заказа {spec['order_id']} укажи в тексте дословно." if spec["order_id"]
                 else "Номер заказа не упоминай.")
    lines.append(f"Назови в письме сумму {spec['amount_rub']} руб. цифрами (можно «₽» или «руб.») и больше никаких сумм."
                 if spec["amount_rub"] else "Никаких денежных сумм и других чисел, кроме номера заказа, не упоминай.")
    if not spec["action_required"]:
        lines.append("Письмо — благодарность или отзыв, от поддержки ничего не требуется.")
    lines.append("Не пиши названия категорий и значения срочности. Верни только текст письма.")
    return "\n".join(lines)


def main(n: int) -> None:
    specs = make_specs(n)
    results = teacher.call_many([[{"role": "user", "content": spec_prompt(s)}] for s in specs],
                                temperature=1.0, max_tokens=300)
    rows = []
    for i, (spec, res) in enumerate(zip(specs, results, strict=True)):
        if "error" in res or not res["content"].strip():
            continue
        rows.append({"id": i, "text": res["content"].strip(), "gold": {k: spec[k] for k in schema.FIELDS},
                     "style": spec["style"], "gen_tokens": [res["prompt_tokens"], res["completion_tokens"]]})
    (ROOT / "data").mkdir(exist_ok=True)
    (ROOT / "data" / "emails_raw.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    print(f"писем: {len(rows)} из {n}")  # noqa: T201


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 760)
