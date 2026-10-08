"""Abstract LLM Provider interface and response types."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class LLMResponse:
    content: str
    input_tokens: int
    cached_input_tokens: int
    output_tokens: int
    latency_ms: int
    usage_available: bool = True
    model_id: str = ""


class ProviderError(Exception):
    """Base exception for provider errors."""
    def __init__(self, message: str, is_transient: bool = False, status_code: Optional[int] = None):
        super().__init__(message)
        self.is_transient = is_transient
        self.status_code = status_code


class LLMProvider(ABC):
    @abstractmethod
    async def generate(
        self,
        model_id: str,
        messages: list[Dict[str, str]],
        max_output_tokens: int = 2000,
        response_schema: Optional[Dict[str, Any]] = None
    ) -> LLMResponse:
        """Asynchronously calls LLM and returns LLMResponse."""
        pass
