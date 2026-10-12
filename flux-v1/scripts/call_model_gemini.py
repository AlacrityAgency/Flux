"""
Gemini 3.8 Flash Model Adapter for FLux v1.
Implements compact prompt wrapping, thinking effort control, and normalized JSON extraction.
"""

import json
import os
import re
import time
import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def normalize(text: str) -> dict:
    """Extract and validate clean JSON from model output, handling fences and markdown."""
    value = text.strip()
    # Remove markdown json code blocks if present
    if value.startswith("```json"):
        value = re.sub(r"^```json\s*", "", value)
        value = re.sub(r"\s*```$", "", value)
    elif value.startswith("```"):
        value = re.sub(r"^```\s*", "", value)
        value = re.sub(r"\s*```$", "", value)
        
    value = value.strip()
    
    def unique_pairs(pairs):
        out = {}
        for k, v in pairs:
            if k in out:
                raise ValueError(f"Duplicate JSON key: {k}")
            out[k] = v
        return out

    return json.loads(
        value,
        object_pairs_hook=unique_pairs,
        parse_constant=lambda x: (_ for _ in ()).throw(ValueError("Non-finite JSON"))
    )


def format_compact_prompt(task_text: str, facts: dict) -> str:
    """Format prompt strictly for Gemini 3.8 Flash compact contract."""
    facts_json = json.dumps(facts, separators=(',', ':'), ensure_ascii=False)
    return (
        "TASK:\n"
        f"{task_text}\n\n"
        "FACTS:\n"
        f"{facts_json}\n\n"
        "CONTRACT:\n"
        "Return ONLY one JSON object with exact keys 'refs' and 'code'.\n"
        "- 'refs': list of all top-level keys in FACTS (no duplicates, no nested keys).\n"
        "- 'code': valid Python 3 defining solve(facts) and check(answer, facts).\n"
        "  * solve(facts) returns the exact requested solution.\n"
        "  * check(answer, facts) returns bool verifying the answer by an independent derivation.\n"
        "  * Do not call solve from check. Do not embed hardcoded facts in code.\n"
        "  * Restricted sandbox: only standard math, fractions, itertools, functools, collections, heapq, bisect, decimal.\n"
        "  * No IO, no eval/exec, no private attributes. Execution must complete in under 4 seconds.\n"
    )
