"""Model pricing configuration per 1 million tokens in USD."""

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class ModelPrice:
    input_per_million: float
    output_per_million: float

    def calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        in_cost = (input_tokens / 1_000_000.0) * self.input_per_million
        out_cost = (output_tokens / 1_000_000.0) * self.output_per_million
        return round(in_cost + out_cost, 6)


MODEL_PRICES: Dict[str, ModelPrice] = {
    "claude-fable-5": ModelPrice(input_per_million=10.0, output_per_million=50.0),
    "claude-opus-5": ModelPrice(input_per_million=5.0, output_per_million=25.0),
    "gpt-5.6-sol": ModelPrice(input_per_million=2.5, output_per_million=15.0),
    "gpt-5.6-luna": ModelPrice(input_per_million=0.2, output_per_million=1.2),
    "gapgpt-qwen-3.6-thinking": ModelPrice(input_per_million=0.25, output_per_million=2.0),
}


def get_model_price(model_id: str) -> ModelPrice:
    if model_id not in MODEL_PRICES:
        # Fallback to high rate to prevent accidental budget overrun if unknown
        return ModelPrice(input_per_million=10.0, output_per_million=50.0)
    return MODEL_PRICES[model_id]
