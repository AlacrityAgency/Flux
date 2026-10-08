"""Token and cost estimation utility."""

from flux.budget.pricing import get_model_price, ModelPrice


def estimate_tokens_from_text(text: str) -> int:
    """Conservative token estimator for mixed Persian/English text.
    Persian UTF-8 text typically takes 1 token per 2-3 characters in subword tokenizers.
    We conservatively estimate tokens = ceil(len(text) / 2.5) + 20 to avoid underestimating.
    """
    if not text:
        return 0
    # Conservative estimate
    return int(len(text) / 2.5) + 20


def estimate_call_cost(
    model_id: str,
    prompt_text: str,
    max_output_tokens: int
) -> tuple[int, float]:
    """Returns (estimated_input_tokens, estimated_total_cost_usd)."""
    in_tokens = estimate_tokens_from_text(prompt_text)
    pricing = get_model_price(model_id)
    cost = pricing.calculate_cost(in_tokens, max_output_tokens)
    return in_tokens, cost
