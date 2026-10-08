"""GapGPT Adapter using OpenAI SDK."""

import os
import time
from typing import Any, Dict, Optional
from openai import AsyncOpenAI, APIConnectionError, RateLimitError, APIStatusError
from flux.providers.base import LLMProvider, LLMResponse, ProviderError


class GapGPTAdapter(LLMProvider):
    def __init__(self, base_url: str = "https://api.gapgpt.app/v1", api_key: Optional[str] = None):
        self.base_url = base_url
        self._api_key = api_key or os.environ.get("GAPGPT_API_KEY", "")

    def _get_client(self) -> AsyncOpenAI:
        key = self._api_key or os.environ.get("GAPGPT_API_KEY", "")
        if not key:
            raise ProviderError(
                "GAPGPT_API_KEY environment variable is not set. Live API calls require GAPGPT_API_KEY.",
                is_transient=False,
                status_code=401
            )
        proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY") or os.environ.get("ALL_PROXY")
        http_client = None
        if proxy:
            import httpx
            http_client = httpx.AsyncClient(proxy=proxy, timeout=120.0)
        return AsyncOpenAI(
            base_url=self.base_url,
            api_key=key,
            http_client=http_client,
            max_retries=0,  # Retries are managed deterministically by Flux engine
            timeout=120.0
        )

    async def generate(
        self,
        model_id: str,
        messages: list[Dict[str, str]],
        max_output_tokens: int = 2000,
        response_schema: Optional[Dict[str, Any]] = None
    ) -> LLMResponse:
        client = self._get_client()
        start_time = time.perf_counter()

        kwargs: Dict[str, Any] = {
            "model": model_id,
            "messages": messages,
            "max_tokens": max_output_tokens,
            "temperature": 0.2,
        }

        # Request JSON mode where applicable
        kwargs["response_format"] = {"type": "json_object"}
        if any(rm in model_id.lower() for rm in ("luna", "sol", "o1", "o3", "thinking")):
            kwargs["reasoning_effort"] = "low"

        try:
            try:
                response = await client.chat.completions.create(**kwargs)
            except APIStatusError as err:
                err_msg = str(err).lower()
                modified = False
                if err.status_code == 400 and "response_format" in err_msg:
                    kwargs.pop("response_format", None)
                    modified = True
                if err.status_code == 400 and "reasoning_effort" in err_msg:
                    kwargs.pop("reasoning_effort", None)
                    modified = True
                if modified:
                    response = await client.chat.completions.create(**kwargs)
                else:
                    raise
            latency_ms = int((time.perf_counter() - start_time) * 1000)

            choice = response.choices[0]
            refusal = getattr(choice.message, "refusal", None)
            content = choice.message.content or ""

            # One provider request per ledger reservation. Never silently increase
            # the budget or switch models; retries belong to the engine.
            if choice.finish_reason == "content_filter" or refusal:
                raise ProviderError("مدل درخواست را نپذیرفت.", is_transient=False, status_code=400)
            if not content:
                raise ProviderError("پاسخ مدل خالی است؛ سطح مصرف بالاتر را انتخاب کنید.", is_transient=False)

            usage = response.usage
            input_tokens = usage.prompt_tokens if usage else 0
            output_tokens = usage.completion_tokens if usage else 0
            cached_input_tokens = 0
            if usage and hasattr(usage, "prompt_tokens_details") and usage.prompt_tokens_details:
                cached_input_tokens = getattr(usage.prompt_tokens_details, "cached_tokens", 0) or 0

            return LLMResponse(
                content=content,
                input_tokens=input_tokens,
                cached_input_tokens=cached_input_tokens,
                output_tokens=output_tokens,
                latency_ms=latency_ms,
                usage_available=usage is not None,
                model_id=model_id
            )
        except ProviderError:
            raise
        except (RateLimitError, APIConnectionError) as e:
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            raise ProviderError(f"Transient provider error: {e}", is_transient=True, status_code=429)
        except APIStatusError as e:
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            is_transient = e.status_code in (429, 500, 502, 503, 504)
            raise ProviderError(f"Provider status error: {e}", is_transient=is_transient, status_code=e.status_code)
        except Exception as e:
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            raise ProviderError(f"Unexpected provider error: {e}", is_transient=False)
        finally:
            await client.close()
