"""
Реестр доступных моделей и их параметры.

Данные взяты из официальной документации DeepSeek (api-docs.deepseek.com).
Актуально на июнь 2026. Тарифы — cache miss.

Устаревшие алиасы deepseek-chat и deepseek-reasoner будут удалены 24.07.2026
и соответствуют режимам (non-thinking / thinking) модели deepseek-v4-flash.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelInfo:
    id:                str
    name:              str          # человекочитаемое название
    description:       str
    context_window:    int          # максимум токенов в контексте
    max_output:        int          # максимум токенов в ответе
    price_input_1m:    float        # USD за 1M входных токенов (cache miss)
    price_output_1m:   float        # USD за 1M выходных токенов
    supports_thinking: bool = False # есть ли режим рассуждений (chain-of-thought)

    def to_dict(self) -> dict:
        return {
            "id":                self.id,
            "name":              self.name,
            "description":       self.description,
            "context_window":    self.context_window,
            "max_output":        self.max_output,
            "price_input_1m":    self.price_input_1m,
            "price_output_1m":   self.price_output_1m,
            "supports_thinking": self.supports_thinking,
        }


MODELS: dict[str, ModelInfo] = {
    "deepseek-v4-flash": ModelInfo(
        id="deepseek-v4-flash",
        name="DeepSeek V4 Flash",
        description="Основная модель общего назначения. Быстрая, недорогая, поддерживает thinking-режим. Контекст до 1M токенов.",
        context_window=1_000_000,
        max_output=384_000,
        price_input_1m=0.14,
        price_output_1m=0.28,
        supports_thinking=False,
    ),
    "deepseek-v4-pro": ModelInfo(
        id="deepseek-v4-pro",
        name="DeepSeek V4 Pro",
        description="Продвинутая модель с цепочкой рассуждений (chain-of-thought). Точнее на сложных логических, математических и аналитических задачах. Контекст до 1M токенов.",
        context_window=1_000_000,
        max_output=384_000,
        price_input_1m=0.435,
        price_output_1m=0.87,
        supports_thinking=True,
    ),
}

DEFAULT_MODEL = "deepseek-v4-flash"


def get_model(model_id: str) -> ModelInfo:
    if model_id not in MODELS:
        raise ValueError(f"Неизвестная модель: {model_id!r}")
    return MODELS[model_id]
