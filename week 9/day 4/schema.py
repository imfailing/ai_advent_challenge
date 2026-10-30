"""
Схема задачи дня 9: письмо клиента → JSON из семи полей (шесть проверяемых + summary). Здесь же допустимые значения, промпт
извлечения (общий для учителя и ученика), разбор ответа, проверка схемы и подсчёт точности по полям.
"""

import json
import re

CATEGORIES = ["billing", "technical", "delivery", "account", "refund", "feedback"]
SENTIMENTS = ["negative", "neutral", "positive"]
PRODUCTS = ["Облачко Диск", "Облачко Почта", "Облачко Касса", "Облачко Курьер",
            "Облачко Видео", "Облачко Бэкап", "Облачко Доски", "Облачко Чат"]
FIELDS = ["category", "sentiment", "product", "order_id", "amount_rub", "action_required"]
ORDER_RE = re.compile(r"^[A-Z]{2}-\d{5}$")
MAX_SUMMARY_WORDS = 15

SENTIMENT_RULES = (
    "negative — прямо выражено недовольство или раздражение; "
    "neutral — спокойный деловой тон без эмоций и упрёков; "
    "positive — благодарность или похвала"
)

SYSTEM_PROMPT = (
    "Ты разбираешь письма клиентов сервиса «Облачко». Верни ТОЛЬКО JSON без пояснений с полями:\n"
    f"category — одно из {CATEGORIES};\n"
    f"sentiment — одно из {SENTIMENTS}: {SENTIMENT_RULES};\n"
    f"product — одно из {PRODUCTS} или null, если продукт не назван;\n"
    "order_id — номер заказа вида AA-12345 из текста или null;\n"
    "amount_rub — сумма в рублях, названная в письме, целым числом, или null, если суммы нет;\n"
    "action_required — true, если клиенту нужно что-то сделать или ответить, false для благодарности и отзыва;\n"
    f"summary — суть письма по-русски, не больше {MAX_SUMMARY_WORDS} слов."
)


def parse_reply(text: str) -> dict | None:
    """Достать JSON-объект из ответа (допускается обёртка ```json); None, если не разобрать."""
    text = text.strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if m:
        text = m.group(1).strip()
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None


def schema_errors(obj: dict | None) -> list[str]:
    """Список нарушений схемы (пусто — ответ валиден)."""
    if obj is None:
        return ["не JSON"]
    errors = [f"нет поля {k}" for k in [*FIELDS, "summary"] if k not in obj]
    if errors:
        return errors
    if obj["category"] not in CATEGORIES:
        errors.append("category")
    if obj["sentiment"] not in SENTIMENTS:
        errors.append("sentiment")
    if obj["product"] is not None and obj["product"] not in PRODUCTS:
        errors.append("product")
    if obj["order_id"] is not None and not (isinstance(obj["order_id"], str) and ORDER_RE.match(obj["order_id"])):
        errors.append("order_id")
    amount = obj["amount_rub"]
    if amount is not None and (isinstance(amount, bool) or not isinstance(amount, int) or amount < 0):
        errors.append("amount_rub")
    if not isinstance(obj["action_required"], bool):
        errors.append("action_required")
    summary = obj["summary"]
    if not isinstance(summary, str) or not summary.strip() or len(summary.split()) > MAX_SUMMARY_WORDS:
        errors.append("summary")
    return errors


def field_hits(pred: dict | None, gold: dict) -> dict[str, bool]:
    """Совпадение по каждому полю с эталоном (невалидный ответ — промах по всем полям)."""
    return {k: pred is not None and pred.get(k) == gold[k] for k in FIELDS}


def canonical(obj: dict) -> str:
    """Целевой текст для обучения: JSON с фиксированным порядком ключей."""
    ordered = {k: obj[k] for k in [*FIELDS, "summary"]}
    return json.dumps(ordered, ensure_ascii=False)
