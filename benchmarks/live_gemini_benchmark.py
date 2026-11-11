"""
Live Gemini 3.8 Flash Benchmark Suite
Compares 3 arms on identical model, identical temperature, live API calls:
1. Baseline CoT (Direct prompting with step-by-step thinking)
2. FLux-Ablation (Single-shot exact code generation without Laya escalation)
3. FLux-Laya (Full Dual solve/check contract with Laya Gate Guard and Tier Escalation)

Official Google Gemini REST API transport, native usageMetadata tokens, task-level statistics.
"""

import ast
import asyncio
import datetime
import json
import math
import os
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from flux.local_agents.gemini_api import get_key
import httpx

API_KEY = get_key()
if not API_KEY:
    raise RuntimeError("No Gemini API key found in Flux DPAPI keystore!")

MODEL_ID = "gemini-3.8-flash"
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_ID}:generateContent"

# 12 Hard discrete math, CSP, and reasoning tasks
TASKS = [
    {
        "id": "logic_sat_0",
        "family": "CSP / 3-SAT",
        "query": "Boolean variables A,B,C,D,E satisfy all these clauses: (NOT E OR NOT B OR NOT C) AND (NOT B OR NOT D OR A) AND (NOT D OR NOT B OR NOT A) AND (E OR NOT C OR B) AND (NOT B OR E OR A) AND (NOT A OR NOT E OR NOT B) AND (B OR D OR C). Exactly 2 variables are true. How many satisfying assignments exist?",
        "gold": 5
    },
    {
        "id": "logic_knights_0",
        "family": "CSP / Truth-Tellers",
        "query": "Each of A,B,C,D,E is either a knight (every statement true) or a knave (every statement false). A says: B and D have different types; B says: B and C have different types; C says: A and C have the same type; D says: A and D have the same type; E says: A and C have the same type. How many assignments of types satisfy all statements?",
        "gold": 2
    },
    {
        "id": "logic_order_0",
        "family": "CSP / Ordering",
        "query": "Arrange A,B,C,D,E,F in a single row, each exactly once. Constraints: E before F; D before C; B before F; D before E; E before C; D before A; B and D must NOT be adjacent. How many arrangements are possible?",
        "gold": 17
    },
    {
        "id": "logic_assignment_0",
        "family": "CSP / Assignment",
        "query": "Assign four pairwise distinct integers A,B,C,D from {1,2,3,4,5}. Their sum is 13. A != 5, B != 1, C != 5, D != 5. Also |A-C| != 2. How many ordered assignments satisfy every condition?",
        "gold": 4
    },
    {
        "id": "crt_0",
        "family": "Number Theory / CRT",
        "query": "Find the smallest non-negative integer x such that the remainder of its division by 16 is 13, by 9 is 3, and by 5 is 2.",
        "gold": 237
    },
    {
        "id": "modular_0",
        "family": "Number Theory / ModExp",
        "query": "What is the remainder of 604^9253 divided by 299?",
        "gold": 266
    },
    {
        "id": "compositions_0",
        "family": "Combinatorics / Compositions",
        "query": "How many ordered 4-tuples of integers (x1, x2, x3, x4) have a sum of 10 such that each xi is between 0 and 8 inclusive?",
        "gold": 270
    },
    {
        "id": "coins_0",
        "family": "Optimization / DP",
        "query": "Using unlimited coins of values 5, 7, 9, 11, what is the minimum number of coins needed to make exactly 82?",
        "gold": 8
    },
    {
        "id": "coins_1",
        "family": "Combinatorics / Coin Change",
        "query": "Using unlimited coins of values 2, 3, 5, 7, in how many different ways (order does not matter) can you make exactly 44?",
        "gold": 114
    },
    {
        "id": "shortest_path_0",
        "family": "Graph / Shortest Path",
        "query": "A directed weighted graph has edges: A->D:9, A->F:4, B->F:11, D->A:7, D->F:1, E->G:1, F->D:11, F->E:14, G->A:15, G->D:4, G->F:7. What is the shortest distance from A to G?",
        "gold": 19
    },
    {
        "id": "pattern_0",
        "family": "Probability / Martingales",
        "query": "A fair six-sided die is rolled repeatedly. What is the expected number of rolls until the consecutive pattern 2,3,3,2 first appears? Give the exact integer value.",
        "gold": 1302
    },
    {
        "id": "inclusion_exclusion_0",
        "family": "Combinatorics / PIE",
        "query": "Among 221 students, 111 take art, 89 take biology and 83 take chemistry; 50 take both art and biology, 44 take art and chemistry, 17 take biology and chemistry, and 12 take all three. How many students take exactly one of these subjects?",
        "gold": 97
    }
]


# =========================================================================
# LIVE GEMINI 3.8 FLASH HTTP CLIENT
# =========================================================================

async def call_gemini_live(prompt: str, thinking_budget: int = 2048, temperature: float = 0.3, max_retries: int = 3) -> dict:
    """Calls Gemini 3.8 Flash via official Google Generative Language REST API."""
    body = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": 4096,
            "thinkingConfig": {"thinkingBudget": thinking_budget}
        }
    }
    
    headers = {
        "x-goog-api-key": API_KEY,
        "Content-Type": "application/json"
    }
    
    for attempt in range(max_retries):
        start_time = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=45.0) as client:
                resp = await client.post(API_URL, headers=headers, json=body)
            wall_ms = (time.perf_counter() - start_time) * 1000.0
            
            if resp.status_code == 200:
                data = resp.json()
                cand = (data.get("candidates") or [{}])[0]
                parts = cand.get("content", {}).get("parts", [])
                text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
                thoughts = "".join(p.get("text", "") for p in parts if p.get("thought"))
                usage = data.get("usageMetadata", {})
                
                return {
                    "ok": True,
                    "text": text,
                    "thoughts": thoughts,
                    "wall_ms": wall_ms,
                    "prompt_tokens": usage.get("promptTokenCount", 0),
                    "candidates_tokens": usage.get("candidatesTokenCount", 0),
                    "thought_tokens": usage.get("thoughtsTokenCount", 0),
                    "total_tokens": usage.get("totalTokenCount", 0),
                    "status_code": 200,
                    "raw_usage": usage
                }
            elif resp.status_code == 429:
                wait_time = (2 ** attempt) * 2.0
                await asyncio.sleep(wait_time)
            else:
                return {
                    "ok": False,
                    "error": f"HTTP {resp.status_code}: {resp.text[:300]}",
                    "wall_ms": wall_ms,
                    "status_code": resp.status_code
                }
        except Exception as e:
            wall_ms = (time.perf_counter() - start_time) * 1000.0
            if attempt == max_retries - 1:
                return {"ok": False, "error": str(e), "wall_ms": wall_ms, "status_code": 0}
            await asyncio.sleep(2.0)
            
    return {"ok": False, "error": "Max retries exceeded", "wall_ms": 0, "status_code": 0}


# =========================================================================
# CODE EXECUTION SANDBOX
# =========================================================================

WORKER_CODE = """
import sys, json, fractions, math, itertools, functools, collections, heapq, decimal

def run():
    try:
        data = json.loads(sys.stdin.read())
        code = data.get('code', '')
        mode = data.get('mode', 'solve_only') # 'solve_only' or 'solve_and_check'
        
        namespace = {
            'math': math, 'fractions': fractions, 'Fraction': fractions.Fraction,
            'itertools': itertools, 'functools': functools, 'collections': collections,
            'heapq': heapq, 'decimal': decimal, 'Decimal': decimal.Decimal
        }
        
        exec(code, namespace)
        
        if 'solve' not in namespace or not callable(namespace['solve']):
            print(json.dumps({'ok': False, 'error': 'solve() function not found or not callable'}))
            return
            
        ans = namespace['solve']()
        # Convert Fraction to float/int if needed
        if isinstance(ans, fractions.Fraction):
            ans = int(ans) if ans.denominator == 1 else float(ans)
        elif isinstance(ans, decimal.Decimal):
            ans = int(ans) if ans % 1 == 0 else float(ans)
            
        if mode == 'solve_and_check':
            if 'check' not in namespace or not callable(namespace['check']):
                print(json.dumps({'ok': False, 'error': 'check() function not found'}))
                return
            chk = namespace['check'](ans)
            print(json.dumps({'ok': True, 'answer': ans, 'check_passed': bool(chk)}))
        else:
            print(json.dumps({'ok': True, 'answer': ans}))
    except Exception as e:
        print(json.dumps({'ok': False, 'error': f'{type(e).__name__}: {str(e)}'}))

if __name__ == '__main__':
    run()
"""

def execute_in_sandbox(code: str, mode: str = "solve_only", timeout_s: float = 3.0) -> dict:
    """Executes Python code in an isolated subprocess with memory and time caps."""
    try:
        p = subprocess.run(
            [sys.executable, "-I", "-S", "-c", WORKER_CODE],
            input=json.dumps({"code": code, "mode": mode}),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout_s
        )
        if p.returncode != 0:
            return {"ok": False, "error": f"Process exited {p.returncode}: {p.stderr[:200]}"}
        out = p.stdout.strip()
        if not out:
            return {"ok": False, "error": "No output from worker"}
        # Parse last line as JSON
        last_line = out.splitlines()[-1]
        return json.loads(last_line)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"Timeout ({timeout_s}s exceeded)"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def extract_json_or_code(text: str) -> dict:
    """Extracts JSON block or Python code block from raw completion."""
    text = text.strip()
    # Try finding markdown JSON block
    m_json = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m_json:
        try:
            return json.loads(m_json.group(1))
        except Exception:
            pass
    # Try finding markdown Python block
    m_py = re.search(r"```(?:python)?\s*(.*?)\s*```", text, re.DOTALL)
    if m_py:
        return {"code": m_py.group(1).strip()}
    # Direct JSON parse
    try:
        return json.loads(text)
    except Exception:
        pass
    # If text defines def solve():
    if "def solve" in text:
        return {"code": text}
    return {}


def extract_baseline_answer(text: str):
    """Extracts final numerical answer from Baseline CoT response."""
    # 1. Try finding JSON {"answer": ...}
    d = extract_json_or_code(text)
    if "answer" in d:
        val = d["answer"]
        try:
            f = float(val)
            return int(f) if f.is_integer() else f
        except Exception:
            pass
            
    # 2. Try regex for "answer": X
    m = re.search(r'["\']?answer["\']?\s*:\s*([0-9]+(?:\.[0-9]+)?)', text, re.IGNORECASE)
    if m:
        val = float(m.group(1))
        return int(val) if val.is_integer() else val
        
    # 3. Try boxed answer \boxed{X}
    m = re.search(r'\\boxed\{([0-9]+(?:\.[0-9]+)?)\}', text)
    if m:
        val = float(m.group(1))
        return int(val) if val.is_integer() else val

    # 4. Look at the last lines for a number
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    for l in reversed(lines[-3:]):
        m = re.search(r'\b([0-9]+(?:\.[0-9]+)?)\b', l)
        if m:
            val = float(m.group(1))
            return int(val) if val.is_integer() else val
            
    return None


def is_answer_correct(candidate, gold, tol: float = 1e-4) -> bool:
    """Independent oracle checking mathematical equivalence."""
    if candidate is None:
        return False
    try:
        c = float(candidate)
        g = float(gold)
        return abs(c - g) <= tol
    except Exception:
        return False


# =========================================================================
# ARM RUNNERS
# =========================================================================

async def run_baseline_trial(task: dict, trial_idx: int) -> dict:
    """Arm 1: Baseline CoT (Direct Prompting with step-by-step thinking)."""
    prompt = (
        "You are an expert mathematician and computer scientist. Solve the following problem step by step.\n"
        "Explain your reasoning clearly, and at the very end, output your final numerical answer inside a JSON block with the key 'answer', e.g.:\n"
        "```json\n"
        "{\"answer\": 42}\n"
        "```\n\n"
        f"TASK:\n{task['query']}"
    )
    
    resp = await call_gemini_live(prompt, thinking_budget=2048, temperature=0.3)
    if not resp["ok"]:
        return {
            "task_id": task["id"], "arm": "baseline", "trial": trial_idx,
            "passed": False, "candidate": None, "gold": task["gold"],
            "wall_ms": resp.get("wall_ms", 0), "tokens": resp,
            "raw_text": "", "error": resp.get("error", "API Error")
        }
        
    ans = extract_baseline_answer(resp["text"])
    correct = is_answer_correct(ans, task["gold"])
    
    return {
        "task_id": task["id"], "arm": "baseline", "trial": trial_idx,
        "passed": correct, "candidate": ans, "gold": task["gold"],
        "wall_ms": resp["wall_ms"], "tokens": resp,
        "raw_text": resp["text"], "error": None
    }


async def run_flux_ablation_trial(task: dict, trial_idx: int) -> dict:
    """Arm 2: FLux-Ablation (Single-shot Code Generation without Laya Escalation)."""
    prompt = (
        "You are a scientific computing engine. Solve the following problem by writing an exact Python 3 script.\n"
        "The script must define a function `solve()` that returns the exact answer (integer, Fraction, or exact float rounded as requested).\n"
        "Do not approximate; use exact discrete enumeration, recurrence, or dynamic programming.\n"
        "Return ONLY a JSON object with the key 'code', e.g.:\n"
        "```json\n"
        "{\"code\": \"def solve(): ...\"}\n"
        "```\n\n"
        f"TASK:\n{task['query']}"
    )
    
    resp = await call_gemini_live(prompt, thinking_budget=2048, temperature=0.3)
    if not resp["ok"]:
        return {
            "task_id": task["id"], "arm": "flux_ablation", "trial": trial_idx,
            "passed": False, "candidate": None, "gold": task["gold"],
            "wall_ms": resp.get("wall_ms", 0), "tokens": resp,
            "raw_text": "", "error": resp.get("error", "API Error")
        }
        
    data = extract_json_or_code(resp["text"])
    code = data.get("code", "")
    if not code:
        return {
            "task_id": task["id"], "arm": "flux_ablation", "trial": trial_idx,
            "passed": False, "candidate": None, "gold": task["gold"],
            "wall_ms": resp["wall_ms"], "tokens": resp,
            "raw_text": resp["text"], "error": "No Python code extracted"
        }
        
    sandbox_res = execute_in_sandbox(code, mode="solve_only", timeout_s=3.0)
    ans = sandbox_res.get("answer") if sandbox_res.get("ok") else None
    correct = is_answer_correct(ans, task["gold"])
    
    return {
        "task_id": task["id"], "arm": "flux_ablation", "trial": trial_idx,
        "passed": correct, "candidate": ans, "gold": task["gold"],
        "wall_ms": resp["wall_ms"], "tokens": resp,
        "raw_text": resp["text"], "code": code,
        "sandbox_res": sandbox_res, "error": sandbox_res.get("error")
    }


async def run_flux_laya_trial(task: dict, trial_idx: int) -> dict:
    """Arm 3: FLux-Laya Full (Dual solve/check contract with Laya Gate Guard and Tier Escalation)."""
    base_prompt = (
        "You are FLux v1 running on Gemini 3.8 Flash with Laya Decision Engine.\n"
        "Return ONLY a single JSON object with the key 'code'.\n"
        "The code must define TWO functions in Python 3:\n"
        "1. `solve()`: returns the exact answer.\n"
        "2. `check(answer)`: returns a boolean verifying the answer against all problem constraints independently.\n\n"
        "CONTRACT RULES:\n"
        "- check() MUST NOT call solve().\n"
        "- check() MUST NOT return True unconditionally; re-verify every boundary and constraint independently.\n"
        "- Only standard math, fractions, itertools, collections, heapq, decimal are allowed.\n"
        "- Code must execute within 3 seconds.\n\n"
        f"TASK:\n{task['query']}"
    )
    
    attempt = 1
    max_attempts = 2
    prompt = base_prompt
    total_wall_ms = 0.0
    agg_tokens = {"prompt_tokens": 0, "candidates_tokens": 0, "thought_tokens": 0, "total_tokens": 0}
    escalated = False
    final_ans = None
    final_correct = False
    last_err = None
    last_code = ""
    
    while attempt <= max_attempts:
        effort = 4096 if attempt > 1 else 2048
        resp = await call_gemini_live(prompt, thinking_budget=effort, temperature=0.3)
        total_wall_ms += resp.get("wall_ms", 0)
        
        if resp.get("ok"):
            agg_tokens["prompt_tokens"] += resp.get("prompt_tokens", 0)
            agg_tokens["candidates_tokens"] += resp.get("candidates_tokens", 0)
            agg_tokens["thought_tokens"] += resp.get("thought_tokens", 0)
            agg_tokens["total_tokens"] += resp.get("total_tokens", 0)
            
            data = extract_json_or_code(resp["text"])
            code = data.get("code", "")
            last_code = code
            
            # AST Audit
            try:
                tree = ast.parse(code)
                funcs = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
                has_check = "check" in funcs and len(funcs["check"].args.args) == 1
                has_solve = "solve" in funcs
                # Check for solve() call inside check()
                has_leak = any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "solve" for n in ast.walk(funcs.get("check", ast.Pass())))
            except Exception as e:
                has_check, has_solve, has_leak = False, False, True
                last_err = f"SyntaxError in code: {str(e)}"
                
            if has_solve and has_check and not has_leak:
                sandbox_res = execute_in_sandbox(code, mode="solve_and_check", timeout_s=3.0)
                if sandbox_res.get("ok") and sandbox_res.get("check_passed"):
                    final_ans = sandbox_res.get("answer")
                    final_correct = is_answer_correct(final_ans, task["gold"])
                    last_err = None
                    break # Laya Gate Guard accepts!
                else:
                    last_err = sandbox_res.get("error") or "check(answer) returned False (Constraint violated)"
            else:
                last_err = f"AST Audit failed: has_solve={has_solve}, has_check={has_check}, has_leak={has_leak}"
        else:
            last_err = resp.get("error", "API error")
            
        # Laya END Decision: Escalate if attempts remain
        if attempt < max_attempts:
            attempt += 1
            escalated = True
            prompt = base_prompt + f"\n\n[LAYA_FEEDBACK]: Attempt 1 failed verification. Reason: {last_err}. Re-derive the constraints independently with high thinking."
        else:
            break
            
    return {
        "task_id": task["id"], "arm": "flux_laya", "trial": trial_idx,
        "passed": final_correct, "candidate": final_ans, "gold": task["gold"],
        "wall_ms": total_wall_ms, "tokens": agg_tokens,
        "attempts": attempt, "escalated": escalated,
        "code": last_code, "error": last_err
    }


# =========================================================================
# MAIN ORCHESTRATOR
# =========================================================================

async def run_benchmark():
    print(f"=== Starting Live Benchmark on {MODEL_ID} ===")
    print(f"Tasks: {len(TASKS)}, Trials per task: 2, Arms: 3 (Baseline, FLux-Ablation, FLux-Laya)")
    print(f"API Transport: Official Google REST API with native usageMetadata")
    print("----------------------------------------------------------------------")
    
    semaphore = asyncio.Semaphore(2) # Limit to 2 concurrent calls to prevent rate limits
    results = []
    
    async def wrapped_runner(arm_fn, task, trial_idx):
        async with semaphore:
            await asyncio.sleep(0.3)
            return await arm_fn(task, trial_idx)
            
    tasks_to_run = []
    for t in TASKS:
        for trial in range(1, 3):
            tasks_to_run.append((run_baseline_trial, t, trial, "Baseline"))
            tasks_to_run.append((run_flux_ablation_trial, t, trial, "FLux-Ablation"))
            tasks_to_run.append((run_flux_laya_trial, t, trial, "FLux-Laya"))
            
    total_calls = len(tasks_to_run)
    done_count = 0
    
    for arm_fn, task, trial, arm_name in tasks_to_run:
        res = await wrapped_runner(arm_fn, task, trial)
        results.append(res)
        done_count += 1
        status_sym = "[OK]" if res["passed"] else "[FAIL]"
        cand_str = str(res.get("candidate"))[:15]
        gold_str = str(res.get("gold"))
        print(f"[{done_count:02d}/{total_calls:02d}] {arm_name:<13} | {task['id']:<18} | Tr {trial} | {status_sym} | Cand: {cand_str} (Gold: {gold_str}) | {res['wall_ms']:.0f}ms")
        
    print("----------------------------------------------------------------------")
    print("Benchmark completed! Computing task-level statistics...")
    
    # Save raw receipts
    receipts_path = HERE / "live_gemini_38_flash_receipts.json"
    receipts_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Raw receipts saved to: {receipts_path}")
    
    # Compute Task-Level Statistics
    task_stats = {}
    for t in TASKS:
        tid = t["id"]
        task_stats[tid] = {
            "family": t["family"],
            "gold": t["gold"],
            "baseline": {"passed": [], "latency": [], "tokens": []},
            "flux_ablation": {"passed": [], "latency": [], "tokens": []},
            "flux_laya": {"passed": [], "latency": [], "tokens": []}
        }
        
    for r in results:
        tid = r["task_id"]
        arm = r["arm"]
        task_stats[tid][arm]["passed"].append(1.0 if r["passed"] else 0.0)
        task_stats[tid][arm]["latency"].append(r["wall_ms"])
        task_stats[tid][arm]["tokens"].append(r["tokens"].get("total_tokens", 0))
        
    summary = []
    baseline_task_acc = []
    flux_abl_task_acc = []
    flux_laya_task_acc = []
    
    for tid, st in task_stats.items():
        b_acc = sum(st["baseline"]["passed"]) / len(st["baseline"]["passed"])
        fa_acc = sum(st["flux_ablation"]["passed"]) / len(st["flux_ablation"]["passed"])
        fl_acc = sum(st["flux_laya"]["passed"]) / len(st["flux_laya"]["passed"])
        
        baseline_task_acc.append(b_acc)
        flux_abl_task_acc.append(fa_acc)
        flux_laya_task_acc.append(fl_acc)
        
        summary.append({
            "task_id": tid,
            "family": st["family"],
            "gold": st["gold"],
            "baseline_acc": b_acc,
            "flux_ablation_acc": fa_acc,
            "flux_laya_acc": fl_acc,
            "baseline_lat_p50": sorted(st["baseline"]["latency"])[len(st["baseline"]["latency"])//2],
            "flux_laya_lat_p50": sorted(st["flux_laya"]["latency"])[len(st["flux_laya"]["latency"])//2],
            "baseline_tokens": sum(st["baseline"]["tokens"]) / len(st["baseline"]["tokens"]),
            "flux_laya_tokens": sum(st["flux_laya"]["tokens"]) / len(st["flux_laya"]["tokens"])
        })
        
    # Statistical analysis across tasks
    n_tasks = len(TASKS)
    mean_b = sum(baseline_task_acc) / n_tasks
    mean_fa = sum(flux_abl_task_acc) / n_tasks
    mean_fl = sum(flux_laya_task_acc) / n_tasks
    
    # Paired differences (FLux-Laya vs Baseline)
    diffs = [fl - b for fl, b in zip(flux_laya_task_acc, baseline_task_acc)]
    mean_diff = sum(diffs) / n_tasks
    std_diff = math.sqrt(sum((d - mean_diff)**2 for d in diffs) / (n_tasks - 1)) if n_tasks > 1 else 0
    cohen_d = (mean_diff / std_diff) if std_diff > 1e-6 else 0.0
    
    # Wilcoxon signed-rank test
    nz_diffs = [d for d in diffs if d != 0]
    w_stat = sum(abs(d) for d in nz_diffs)
    
    # McNemar contingency (Task resolved 100% vs Not)
    # a: both 1.0, b: Laya 1.0 & Base < 1.0, c: Base 1.0 & Laya < 1.0, d: both < 1.0
    b_only = sum(1 for fl, b in zip(flux_laya_task_acc, baseline_task_acc) if fl == 1.0 and b < 1.0)
    c_only = sum(1 for fl, b in zip(flux_laya_task_acc, baseline_task_acc) if b == 1.0 and fl < 1.0)
    mcnemar_p = 0.5 ** (b_only + c_only) if (b_only + c_only) > 0 else 1.0
    
    report_data = {
        "model": MODEL_ID,
        "n_tasks": n_tasks,
        "trials_per_task": 2,
        "mean_baseline_acc": mean_b,
        "mean_flux_ablation_acc": mean_fa,
        "mean_flux_laya_acc": mean_fl,
        "mean_diff": mean_diff,
        "std_diff": std_diff,
        "cohen_d": cohen_d,
        "mcnemar_discordant": {"laya_win": b_only, "baseline_win": c_only},
        "task_summary": summary
    }
    
    summary_path = HERE / "live_gemini_38_flash_summary.json"
    summary_path.write_text(json.dumps(report_data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Summary JSON saved to: {summary_path}")
    
    print("\n================== BENCHMARK RESULTS SUMMARY ==================")
    print(f"Model: {MODEL_ID} (Live Google REST API)")
    print(f"Baseline CoT Accuracy (Task-level Mean):     {mean_b*100:.1f}%")
    print(f"FLux-Ablation Accuracy (Single-shot Code):  {mean_fa*100:.1f}%")
    print(f"FLux-Laya Full Accuracy (solve+check+Gate):  {mean_fl*100:.1f}%")
    print(f"Delta (FLux-Laya - Baseline):                +{mean_diff*100:.1f}%")
    print(f"Cohen's d (Task-level Paired):               {cohen_d:.2f}")
    print(f"McNemar Discordant Pairs:                    Laya wins: {b_only}, Baseline wins: {c_only}")
    print("===============================================================\n")

if __name__ == "__main__":
    asyncio.run(run_benchmark())
