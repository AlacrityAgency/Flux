import sys
sys.path.insert(0, 'src')
import asyncio
from flux.settings import get_settings
from flux.storage.database import init_db
from flux.storage.repository import Repository
from flux.storage.workspace import Workspace
from flux.providers.gapgpt import GapGPTAdapter
from openai import AsyncOpenAI
import json

settings = get_settings()
print("Live enabled:", settings.enable_live)
print("Key:", settings.gapgpt_api_key[:10] + "...")

client = AsyncOpenAI(base_url="https://api.gapgpt.app/v1", api_key=settings.gapgpt_api_key)

async def test_sol():
    # Let's inspect call to gpt-5.6-sol with a sample prompt like technical analysis
    messages = [
        {"role": "system", "content": 'You are Technical Agent (GPT-5.6 Sol).\nCRITICAL CONSTRAINTS:\n- Output ONLY valid JSON matching this Envelope schema:\n{"agent": "sol", "model_id": "gpt-5.6-sol", "subtask_id": "st2", "status": "completed", "summary": "string", "output": {"content": "string"}}\nWrite user-facing content in Persian.'},
        {"role": "user", "content": 'تحلیل فنی پروژهٔ Ageis در مسیر D:\\project\\Ageis-2-main و بررسی اشکالات.'}
    ]
    print("\n--- Testing gpt-5.6-sol with response_format=json_object ---")
    try:
        resp = await client.chat.completions.create(
            model="gpt-5.6-sol",
            messages=messages,
            max_tokens=3500,
            temperature=0.2,
            response_format={"type": "json_object"}
        )
        choice = resp.choices[0]
        print("Finish reason:", choice.finish_reason)
        print("Message content:", repr(choice.message.content))
        print("Message refusal:", getattr(choice.message, "refusal", None))
        for attr in dir(choice.message):
            if not attr.startswith("_") and attr not in ("content", "role"):
                val = getattr(choice.message, attr, None)
                if val:
                    print(f"  {attr}: {repr(val)[:150]}")
    except Exception as e:
        print("Error with response_format:", type(e), e)

    print("\n--- Testing gpt-5.6-sol WITHOUT response_format ---")
    try:
        resp2 = await client.chat.completions.create(
            model="gpt-5.6-sol",
            messages=messages,
            max_tokens=3500,
            temperature=0.2,
        )
        choice2 = resp2.choices[0]
        print("Finish reason:", choice2.finish_reason)
        print("Message content:", repr(choice2.message.content)[:200])
    except Exception as e:
        print("Error without response_format:", type(e), e)

asyncio.run(test_sol())
