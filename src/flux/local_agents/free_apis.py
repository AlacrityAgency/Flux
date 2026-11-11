"""Generic and free OpenAI-compatible HTTP transports (Ollama, Groq, OpenRouter, Together)."""
from __future__ import annotations

import asyncio
import json
import os
import re
import urllib.request
import urllib.error
from pathlib import Path

import httpx

from flux.local_agents.gemini_api import get_provider_key, save_provider_key

OPENAI_PROVIDERS = {
    "ollama": {
        "name": "Ollama (محلی / رایگان)",
        "base_url": os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434"),
        "requires_key": False,
        "default_models": [
            "gemma4:latest",
            "deepseek-r1:8b",
            "qwen3-coder:30b",
            "deepseek-r1:14b",
        ],
        "default_model": "gemma4:latest",
    },
    "groq": {
        "name": "Groq (کلید رایگان / سرعت بالا)",
        "base_url": "https://api.groq.com/openai/v1",
        "requires_key": True,
        "default_models": [
            "llama-3.3-70b-versatile",
            "llama-3.1-8b-instant",
            "deepseek-r1-distill-llama-70b",
            "gemma2-9b-it",
        ],
        "default_model": "llama-3.3-70b-versatile",
    },
    "openrouter": {
        "name": "OpenRouter (مدل‌های رایگان)",
        "base_url": "https://openrouter.ai/api/v1",
        "requires_key": True,
        "default_models": [
            "google/gemma-4-26b-a4b-it:free",
            "google/gemma-4-31b-it:free",
            "cohere/north-mini-code:free",
            "nvidia/nemotron-3.5-lightning:free",
            "liquid/lfm-3-1.7b:free",
        ],
        "default_model": "google/gemma-4-26b-a4b-it:free",
    },
    "together": {
        "name": "Together AI",
        "base_url": "https://api.together.xyz/v1",
        "requires_key": True,
        "default_models": [
            "meta-llama/Llama-3.3-70B-Instruct-Turbo",
            "Qwen/Qwen2.5-Coder-32B-Instruct",
            "deepseek-ai/DeepSeek-R1",
        ],
        "default_model": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
    },
}


def get_key_for(provider: str) -> str:
    # First check environment variable (e.g. GROQ_API_KEY, OPENROUTER_API_KEY)
    env_var = f"{provider.upper()}_API_KEY"
    val = os.environ.get(env_var)
    if val:
        return val.strip()
    return get_provider_key(provider)


def save_key_for(provider: str, key: str):
    save_provider_key(provider, key)


def list_models_sync(provider: str) -> list[str]:
    cfg = OPENAI_PROVIDERS.get(provider)
    if not cfg:
        return []
    base_url = cfg["base_url"].rstrip("/")
    if provider == "ollama":
        try:
            req = urllib.request.Request(f"{base_url}/api/tags", headers={"User-Agent": "Flux/0.6.0"})
            with urllib.request.urlopen(req, timeout=2) as r:
                data = json.loads(r.read())
                names = [m["name"] for m in data.get("models", [])]
                return names or cfg["default_models"]
        except Exception:
            return cfg["default_models"]
    elif provider == "openrouter":
        try:
            req = urllib.request.Request(f"{base_url}/models", headers={"User-Agent": "Flux/0.6.0"})
            with urllib.request.urlopen(req, timeout=3) as r:
                data = json.loads(r.read())
                free = [m["id"] for m in data.get("data", []) if ":free" in m["id"]]
                return free or cfg["default_models"]
        except Exception:
            return cfg["default_models"]
    return cfg["default_models"]


def inspect_provider(provider: str) -> dict:
    cfg = OPENAI_PROVIDERS.get(provider)
    if not cfg:
        return {"id": provider, "installed": False, "authenticated": False, "version": "", "detail": "پرووایدر نامعتبر"}

    if provider == "ollama":
        base_url = cfg["base_url"].rstrip("/")
        try:
            req = urllib.request.Request(f"{base_url}/api/tags", headers={"User-Agent": "Flux/0.6.0"})
            with urllib.request.urlopen(req, timeout=2) as r:
                data = json.loads(r.read())
                models = [m["name"] for m in data.get("models", [])]
                return {
                    "id": provider,
                    "installed": True,
                    "authenticated": True,
                    "version": "Ollama (محلی)",
                    "billing": "local-free",
                    "detail": f"سرویس فعال است ({len(models)} مدل محلی آماده استفاده).",
                    "models": models or cfg["default_models"],
                }
        except Exception:
            return {
                "id": provider,
                "installed": True,
                "authenticated": False,
                "version": "Ollama (محلی)",
                "billing": "local-free",
                "detail": "سرویس Ollama در پورت ۱۱۴۳۴ در حال اجرا نیست یا پاسخی نداد.",
                "models": cfg["default_models"],
            }
    else:
        key = get_key_for(provider)
        configured = bool(key)
        return {
            "id": provider,
            "installed": True,
            "authenticated": configured,
            "version": "REST API",
            "billing": f"{provider}-key",
            "detail": f"کلید {provider.title()} تنظیم شده است." if configured else f"کلید رایگان {provider.title()} را در تنظیمات وارد کنید.",
            "models": cfg["default_models"],
        }


async def generate(provider: str, model: str, prompt: str, max_output: int = 4000) -> tuple[str, dict]:
    cfg = OPENAI_PROVIDERS.get(provider)
    if not cfg:
        raise ValueError(f"پرووایدر {provider} پشتیبانی نمی‌شود.")

    model = model or cfg["default_model"]
    base_url = cfg["base_url"].rstrip("/")
    key = get_key_for(provider)

    if cfg["requires_key"] and not key:
        raise ValueError(f"کلید اتصال {cfg['name']} وارد نشده است.")

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Flux/0.6.0",
    }
    if key:
        headers["Authorization"] = f"Bearer {key}"

    if provider == "openrouter":
        headers["HTTP-Referer"] = "https://github.com/Alacrity/Flux"
        headers["X-Title"] = "Flux"

    if provider == "ollama":
        # Native /api/chat with think=False or standard completions
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"num_predict": max_output},
        }
        url = f"{base_url}/api/chat"
        async with httpx.AsyncClient(timeout=180, follow_redirects=True) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code != 200:
                raise ValueError(f"Ollama خطای HTTP {resp.status_code} بازگرداند: {resp.text[:300]}")
            data = resp.json()
            msg = data.get("message", {})
            text = msg.get("content") or msg.get("thinking") or ""
            if not text.strip():
                # Fallback to /api/generate if message content was empty
                gen_resp = await client.post(
                    f"{base_url}/api/generate",
                    headers=headers,
                    json={"model": model, "prompt": prompt, "stream": False, "options": {"num_predict": max_output}},
                )
                if gen_resp.status_code == 200:
                    text = gen_resp.json().get("response", "")

            if not text.strip():
                raise ValueError("Ollama پاسخی تولید نکرد.")

            usage = {
                "billing": "local-free",
                "input_tokens": data.get("prompt_eval_count"),
                "output_tokens": data.get("eval_count"),
                "total_tokens": (data.get("prompt_eval_count") or 0) + (data.get("eval_count") or 0),
                "actual_cost_usd": 0.0,
                "usage_available": True,
                "physical_requests": 1,
            }
            return text, usage
    else:
        # Standard OpenAI chat completions endpoint
        url = f"{base_url}/chat/completions"
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_output,
        }
        async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code != 200:
                raise ValueError(f"{provider.title()} API خطای {resp.status_code} داد: {resp.text[:300]}")
            data = resp.json()
            choices = data.get("choices") or []
            if not choices:
                raise ValueError(f"هیچ پاسخی از {provider.title()} دریافت نشد.")
            msg = choices[0].get("message", {})
            text = msg.get("content") or msg.get("reasoning") or ""
            if not text.strip():
                raise ValueError(f"{provider.title()} متن خالی ارسال کرد.")

            raw_usage = data.get("usage") or {}
            usage = {
                "billing": f"{provider}-api",
                "input_tokens": raw_usage.get("prompt_tokens"),
                "output_tokens": raw_usage.get("completion_tokens"),
                "total_tokens": raw_usage.get("total_tokens"),
                "actual_cost_usd": 0.0 if ":free" in model or provider == "ollama" else None,
                "usage_available": bool(raw_usage),
                "physical_requests": 1,
            }
            return text, usage

