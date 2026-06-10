"""
Реестр доступных моделей и их параметры.

Данные взяты из официальной документации DeepSeek (platform.deepseek.com/docs).
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
    "deepseek-chat": ModelInfo(
        id="deepseek-chat",
        name="DeepSeek V3",
        description="Основная модель общего назначения. Быстрая, недорогая, хорошо справляется с большинством задач.",
        context_window=65_536,
        max_output=8_192,
        price_input_1m=0.27,
        price_output_1m=1.10,
        supports_thinking=False,
    ),
    "deepseek-reasoner": ModelInfo(
        id="deepseek-reasoner",
        name="DeepSeek R1",
        description="Модель с цепочкой рассуждений (chain-of-thought). Медленнее и дороже, но значительно точнее на сложных логических, математических и аналитических задачах.",
        context_window=65_536,
        max_output=8_192,
        price_input_1m=0.55,
        price_output_1m=2.19,
        supports_thinking=True,
    ),
}

DEFAULT_MODEL = "deepseek-chat"


def get_model(model_id: str) -> ModelInfo:
    if model_id not in MODELS:
        raise ValueError(f"Неизвестная модель: {model_id!r}")
    return MODELS[model_id]
