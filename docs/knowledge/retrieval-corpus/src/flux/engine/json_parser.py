"""Robust JSON parser for LLM outputs with multi-stage recovery."""
import json
import re
from typing import Any, Dict

try:
    import json_repair
except ImportError:
    json_repair = None


def parse_llm_json(content: str) -> Dict[str, Any]:
    """Parse JSON from model response, handling markdown fences, thoughts, control chars, and truncations."""
    if not content or not content.strip():
        raise ValueError("پاسخ مدل خالی بود.")

    text = content.strip()

    # 1. Remove reasoning / thinking tags (<think>...</think>) from thinking models
    text = re.sub(r"<think>[\s\S]*?</think>", "", text).strip()

    # 2. Try direct JSON parse with strict=False (allows unescaped control chars / newlines)
    try:
        res = json.loads(text, strict=False)
        if isinstance(res, dict):
            return res
    except Exception:
        pass

    # 3. Check for markdown code fence ```json ... ``` or ``` ... ```
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if fence_match:
        candidate = fence_match.group(1).strip()
        try:
            res = json.loads(candidate, strict=False)
            if isinstance(res, dict):
                return res
        except Exception:
            pass

    # 4. Use json_repair if available (repairs unclosed strings, missing braces/brackets, bad escapes)
    if json_repair is not None:
        try:
            repaired = json_repair.repair_json(text, return_objects=True)
            if isinstance(repaired, dict):
                return repaired
            if isinstance(repaired, str) and repaired.strip():
                try:
                    res = json.loads(repaired, strict=False)
                    if isinstance(res, dict):
                        return res
                except Exception:
                    pass
        except Exception:
            pass

    # 5. Extract substring between first '{' and last '}'
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = text[start : end + 1]
        try:
            res = json.loads(candidate, strict=False)
            if isinstance(res, dict):
                return res
        except Exception:
            if json_repair is not None:
                try:
                    repaired = json_repair.repair_json(candidate, return_objects=True)
                    if isinstance(repaired, dict):
                        return repaired
                except Exception:
                    pass

    # 6. If truncated JSON (e.g. cut off at max tokens), attempt manual closure
    if start != -1:
        candidate = text[start:]
        open_braces = candidate.count("{") - candidate.count("}")
        open_brackets = candidate.count("[") - candidate.count("]")
        if open_braces > 0 or open_brackets > 0:
            repaired = candidate.rstrip()
            if repaired.endswith(","):
                repaired = repaired[:-1]
            repaired += ("]" * max(0, open_brackets)) + ("}" * max(0, open_braces))
            try:
                res = json.loads(repaired, strict=False)
                if isinstance(res, dict):
                    return res
            except Exception:
                pass

    # 7. Final fallback to json.loads to raise standardized JSONDecodeError
    return json.loads(text)
