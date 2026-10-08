"""Execution budgets; legacy workflow values remain readable."""
from dataclasses import dataclass


@dataclass(frozen=True)
class ExecutionProfile:
    models: dict[str, str]
    head_tokens: int
    worker_tokens: int
    review_tokens: int


LEGACY_MODELS = {
    "head": "claude-fable-5", "opus": "claude-opus-5",
    "sol": "gpt-5.6-sol", "luna": "gpt-5.6-luna",
    "verification": "gapgpt-qwen-3.6-thinking",
}
LOW_MODELS = dict.fromkeys(LEGACY_MODELS, "gpt-5.6-luna")
PROFILES = {
    "low": ExecutionProfile(LOW_MODELS, 2500, 8000, 4000),
    "medium": ExecutionProfile({**LOW_MODELS, "sol": "gpt-5.6-sol"}, 2500, 8000, 5000),
    "high": ExecutionProfile(LEGACY_MODELS, 3500, 8000, 8000),
    "auto": ExecutionProfile(LEGACY_MODELS, 3500, 8000, 6000),
    "team": ExecutionProfile(LEGACY_MODELS, 3500, 8000, 6000),
}
