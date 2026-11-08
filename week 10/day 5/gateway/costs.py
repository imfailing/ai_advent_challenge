"""
Cost tracking: подсчёт токенов и условной стоимости каждого запроса.

Роль в сервисе: учёт расходов шлюза. Модель локальная и бесплатная, поэтому стоимость считается
по условному тарифу (USD за 1 млн токенов) — так видно, сколько запрос стоил бы в облаке.
Тарифы в `PRICES` — ориентир для сравнения, а не реальный счёт. Итоги копятся в модульном dict.
"""

PRICES: dict[str, tuple[float, float]] = {  # модель -> (вход, выход) USD за 1 млн токенов
    "qwen3.5-122b": (1.0, 4.0),
}
DEFAULT_PRICE = (1.0, 4.0)

_totals: dict[str, float] = {"requests": 0, "prompt_tokens": 0, "completion_tokens": 0, "cost_usd": 0.0}


def estimate_tokens(text: str) -> int:
    """Грубая оценка токенов, если модель не вернула usage (≈ 3,5 символа на токен для русского текста)."""
    return max(1, round(len(text) / 3.5))


def cost_usd(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Условная стоимость запроса в долларах."""
    price_in, price_out = PRICES.get(model, DEFAULT_PRICE)
    return round((prompt_tokens * price_in + completion_tokens * price_out) / 1_000_000, 6)


def record(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Учесть запрос в итогах и вернуть его стоимость."""
    cost = cost_usd(model, prompt_tokens, completion_tokens)
    _totals["requests"] += 1
    _totals["prompt_tokens"] += prompt_tokens
    _totals["completion_tokens"] += completion_tokens
    _totals["cost_usd"] = round(_totals["cost_usd"] + cost, 6)
    return cost


def totals() -> dict[str, float]:
    """Копия накопленных итогов."""
    return dict(_totals)


def reset() -> None:
    """Обнулить итоги (для тестов)."""
    _totals.update(requests=0, prompt_tokens=0, completion_tokens=0, cost_usd=0.0)
