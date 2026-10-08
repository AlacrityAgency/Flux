"""Offline A/B/C experiment: no algorithm vs current Flux vs JEVS.   No model calls, no API credits.

What is measured (per task, per workflow):
  * input tokens of every call in the run, built with Flux's own prompt builders and estimator
  * evidence recall: how many of the pre-declared needed evidence units are actually inside the context
  * safety: foreign-project notes injected (leakage) and obsolete notes injected (stale)
What is NOT measured: answer quality of a real model. Evidence presence is a necessary condition for a grounded
answer, not a sufficient one.

Usage:  python experiments/jevs/run_experiment.py            (from the Flux root, PYTHONPATH=src)
"""
from __future__ import annotations

import json
import random
import re
import statistics
import sys
import time
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE / "snapshot" if (HERE / "snapshot").exists() else HERE.parents[1]   # frozen copy when present
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(HERE))
sys.stdout.reconfigure(encoding="utf-8")
# flux.api.app builds an app (and opens its DB) at import time: never let that touch the user's var/flux.db.
import os, tempfile
os.environ["FLUX_DB_PATH"] = str(Path(tempfile.mkdtemp(prefix="jevs_")) / "flux.db")

from flux.api.app import build_project_context                      # real snapshot builder
from flux.agents.execution import build_execution_prompt
from flux.agents.head import build_head_prompt
from flux.agents.planning import build_planning_prompt
from flux.agents.technical import build_technical_prompt
from flux.agents.verification import build_verification_prompt
from flux.budget.estimator import estimate_tokens_from_text         # the ledger's estimator
from flux.budget.pricing import get_model_price
from flux.contracts.envelope import ArtifactSpec, CheckSpec
from flux.contracts.head import SubtaskSpec
from flux.contracts.task import TaskInput
from flux.engine.orchestrator import FluxEngine
from flux.engine.profiles import PROFILES
from flux.storage.database import init_db
from flux.storage.repository import Repository
from flux.storage.workspace import Workspace

import corpus as C
import jevs as J
import jevs2 as J2
from tasks import TASKS

WORKER_BUDGET = 6000          # JEVS evidence budget (tokens): parity with Flux's current worst case, fixed a priori
NAIVE_WINDOW = 100_000        # A0 token cap for the "dump everything" baseline
DEP_OUTPUT = "x" * 4000       # identical dummy output of an upstream worker, for every strategy
STAMP = f"Flux role: head. Actual model_id: m. Be concise; return complete valid JSON within 3500 tokens."

norm = lambda s: re.sub(r"\s+", " ", s)


# ------------------------------------------------------------------ pipeline (real Flux builders)
def mk_task(t: dict, context: list[dict], workflow: str) -> TaskInput:
    return TaskInput(task_id=t["id"], root_id=t["id"], project_id=t["project_id"], human_owner="owner",
                     objective=t["objective"], acceptance_criteria=[c["text"] for c in t["criteria"]],
                     budget_cap_usd=1.0, workflow=workflow, context=context)


def subtasks(t: dict, workflow: str) -> list[SubtaskSpec]:
    crit = [c["text"] for c in t["criteria"]]
    if workflow == "low":
        return [SubtaskSpec(subtask_id="s1", objective=t["objective"], assigned_agent="luna", acceptance_criteria=crit)]
    return [SubtaskSpec(subtask_id="s1", objective=t["objective"], assigned_agent="opus", acceptance_criteria=crit),
            SubtaskSpec(subtask_id="s2", objective=t["objective"], assigned_agent="sol", acceptance_criteria=crit, dependencies=["s1"]),
            SubtaskSpec(subtask_id="s3", objective=t["objective"], assigned_agent="luna", acceptance_criteria=crit, dependencies=["s2"])]


BUILDERS = {"opus": build_planning_prompt, "sol": build_technical_prompt, "luna": build_execution_prompt}
ctx_method = lambda msgs, task: FluxEngine._context(None, msgs, task)   # _context does not use self


def build_calls(t: dict, ctx: dict, workflow: str, head_dup: bool) -> list[tuple[str, list[dict]]]:
    """Messages for every call of one run. ctx = {'head': [...], 'work': [...], 'verify': [...]}.
    head_dup=True reproduces the engine as it is today: the head prompt embeds task.context AND _context appends it."""
    prof = PROFILES[workflow]
    calls = []
    head_task = mk_task(t, ctx["head"], workflow)
    if head_dup:
        calls.append(("head", ctx_method(build_head_prompt(head_task), head_task)))
    else:
        calls.append(("head", ctx_method(build_head_prompt(mk_task(t, [], workflow)), head_task)))
    work_task = mk_task(t, ctx["work"], workflow)
    for s in subtasks(t, workflow):
        msgs = ctx_method(BUILDERS[s.assigned_agent](work_task, s), work_task)
        deps = [{"subtask_id": d, "output": {"output": {"content": DEP_OUTPUT}}} for d in s.dependencies]
        msgs.append({"role": "user", "content": json.dumps({"dependency_outputs": deps}, ensure_ascii=False)})
        calls.append((s.assigned_agent, msgs))
    arts = [ArtifactSpec(type="report", ref=f"a{i}", description="d") for i in range(len(subtasks(t, workflow)))]
    checks = [CheckSpec(name=f"c{i}", status="passed", evidence="e") for i in range(2 * len(arts))]
    summaries = [{"subtask_id": s.subtask_id, "summary": "s" * 300} for s in subtasks(t, workflow)]
    ver_task = mk_task(t, ctx["verify"], workflow)
    calls.append(("verification", ctx_method(build_verification_prompt(ver_task, arts, checks, summaries), ver_task)))
    return calls


def model_for(role: str, workflow: str) -> str:
    return PROFILES[workflow].models[role]


def run_cost(calls, workflow):
    toks, usd = 0, 0.0
    for role, msgs in calls:
        text = json.dumps(msgs, ensure_ascii=False) + STAMP          # what the ledger estimates on reserve
        n = estimate_tokens_from_text(text)
        toks += n
        usd += n / 1e6 * get_model_price(model_for(role, workflow)).input_per_million
    return toks, usd


# ------------------------------------------------------------------ strategies -> contexts
def flux_workspace(store: list[C.Memory]) -> Workspace:
    """The real current Flux memory table: no project_id, no status; every record enabled."""
    repo = Repository(init_db(":memory:"))
    ws = Workspace(repo)
    with repo.conn:
        for m in store:
            repo.conn.execute("INSERT INTO memories VALUES (?,?,?,?,?,?,?)",
                              (m.id, m.title, m.content, 1, m.revision, "2026-01-01", "2026-01-01"))
    return ws


def ctx_floor(t, env):
    return {"head": [], "work": [], "verify": []}, True


def _naive_text(env):
    if "naive_all" not in env:
        parts = [f"[mem:{m.id}]\n{m.title}\n{m.content}" for m in env["store"]]
        parts += [f"--- {c.path} ---\n{c.text}" for c in env["files_in_order"]]
        env["naive_all"] = "\n\n".join(parts)
    return env["naive_all"]


def make_naive(window):
    def f(t, env):
        """No algorithm: all memories (every project, every status), then every project file in path order.
        window=None => no cap (theoretical ceiling: does not fit any real context window)."""
        text = _naive_text(env)
        if window:
            text = text[: int(window / J.TOKENS_PER_CHAR)]
        ctx = [{"ref": "all:everything", "title": "Everything", "content": text}]
        return {"head": ctx, "work": ctx, "verify": ctx}, True
    return f


_SNAP = []


def ctx_flux(t, env):
    """Current Flux: real snapshot builder + real Workspace.retrieve; same list goes to every call.
    The snapshot does not depend on the task, so it is built once (it walks the whole folder)."""
    ctx = []
    if not _SNAP:
        _SNAP.append(build_project_context({"name": "Flux", "path": str(ROOT)}))
    if _SNAP[0]:
        ctx.append(_SNAP[0])
    ctx.extend(env["ws"].retrieve(t["objective"]))
    return {"head": ctx, "work": ctx, "verify": ctx}, True


def ctx_dedup(t, env):
    """Variant B: current retrieval, but the head prompt no longer embeds context a second time."""
    c, _ = ctx_flux(t, env)
    return c, False


def get_index(env, flags: J.Flags) -> J.Index:
    key = (flags.subchunk, flags.stemming)
    cache = env.setdefault("idx", {})
    if key not in cache:
        cache[key] = J.Index(env["code"], env["store"], subchunk=flags.subchunk, stemming=flags.stemming)
    return cache[key]


def make_jevs(flags: J.Flags, budget=WORKER_BUDGET):
    def f(t, env):
        pack = get_index(env, flags).select(t, budget, flags)
        return {"head": J.head_context(pack), "work": J.worker_context(pack), "verify": J.worker_context(pack)}, False
    return f


def get_index2(env, cfg: "J2.Cfg") -> "J2.Index2":
    key = ("v2",) + cfg.index_key() + (cfg.lexicon,)
    cache = env.setdefault("idx", {})
    if key not in cache:
        cache[key] = J2.Index2(env["code"], env["store"], cfg)
    return cache[key]


def make_jevs2(cfg=None):
    cfg = cfg or J2.Cfg()

    def f(t, env):
        pack = J2.select(get_index2(env, cfg), t, cfg)
        return {"head": J2.head_context(pack), "work": J2.worker_context(pack), "verify": J2.worker_context(pack)}, False
    return f


STRATEGIES = {
    "S0 بدون Context": ctx_floor,
    "A0a ریختن همه‌چیز، سقف ۱۰۰k توکن": make_naive(NAIVE_WINDOW),
    "A0b ریختن همه‌چیز، بدون سقف (نشدنی)": make_naive(None),
    "A1 الگوریتم فعلی Flux": ctx_flux,
    "B1 Flux + حذف تکرار Head": ctx_dedup,
    "JEVS v0": make_jevs(J.Flags()),
    "JEVS v1": make_jevs(J.v1_flags()),
    "JEVS v2": make_jevs2(J2.v2_cfg()),
    "JEVS v2 دقیق": make_jevs2(J2.v2_cfg("accurate")),
}
V1 = dict(stemming=False, subchunk=True, selector="per_criterion", prf=False)
ABLATIONS = {
    "v2 − گراف کد": make_jevs2(J2.v2_cfg(graph=False)),
    "v2 − وزن‌دهی فارسی": make_jevs2(J2.v2_cfg(fa_stop=False, fa_translated=1.0)),
    "v2 − اولویت مسیر": make_jevs2(J2.v2_cfg(path_prior=False)),
    "v2 − حذف خط تکراری": make_jevs2(J2.v2_cfg(dedup_lines=False)),
    "v2 − واژه‌نامه فارسی": make_jevs2(J2.v2_cfg(glossary=False)),
    "v2 − فیلتر پروژه": make_jevs2(J2.v2_cfg(project_filter=False)),
    "v2 − فیلتر منسوخ": make_jevs2(J2.v2_cfg(stale_filter=False)),
    "v2 با بودجهٔ ثابت ۳۰۰۰": make_jevs2(J2.v2_cfg(per_crit=0, budget=3000)),
    "v2 با پنجرهٔ ۲۵خطی (بدون برش خطی)": make_jevs2(J2.v2_cfg(win=25, stride=18, expand=0)),
    "v2 + LSA پروژه": make_jevs2(J2.v2_cfg(lsa=0.35)),
    "v2 + گسترش صرفی": make_jevs2(J2.v2_cfg(morph=0.7)),
    "v1 − فیلتر پروژه": make_jevs(J.Flags(**V1, project_filter=False)),
    "v1 − فیلتر منسوخ": make_jevs(J.Flags(**V1, stale_filter=False)),
    "v1 − واژه‌نامه فارسی": make_jevs(J.Flags(**V1, glossary=False)),
    "v1 + PRF": make_jevs(J.Flags(**{**V1, "prf": True})),
    "v1 + ریشه‌یابی": make_jevs(J.Flags(**{**V1, "stemming": True})),
    "v1 + PRF + ریشه‌یابی": make_jevs(J.Flags(**{**V1, "prf": True, "stemming": True})),
    "v1 − قطعه‌بندی ریز": make_jevs(J.Flags(**{**V1, "subchunk": False})),
    "v1 − توقف تطبیقی": make_jevs(J.Flags(**V1, adaptive_stop=False)),
    "v1 با انتخاب پوشش حریصانه (v0)": make_jevs(J.Flags(**{**V1, "selector": "coverage"})),
    "v1 با رتبهٔ کل به‌جای هر معیار (v1a)": make_jevs(J.Flags(**{**V1, "selector": "relevance"})),
    "JEVS − فیلتر پروژه": make_jevs(J.Flags(project_filter=False)),
    "JEVS − فیلتر منسوخ": make_jevs(J.Flags(stale_filter=False)),
    "JEVS − واژه‌نامه فارسی": make_jevs(J.Flags(glossary=False)),
    "JEVS − پوشش حریصانه (BM25 ساده)": make_jevs(J.Flags(greedy_coverage=False)),
    "JEVS − توقف تطبیقی": make_jevs(J.Flags(adaptive_stop=False)),
}


# ------------------------------------------------------------------ scoring
FOREIGN = re.compile(r"mem_other\d+_[A-Za-z0-9]+_\d+")


def present(need, text_norm: str) -> bool:
    kind, val = need
    if kind == "mem":
        return val in text_norm
    return all(norm(a) in text_norm for a in val)


def ctx_text(ctx: list[dict]) -> str:
    return norm(json.dumps(ctx, ensure_ascii=False).encode().decode("unicode_escape", errors="ignore")
                if False else "\n".join(f"{c.get('ref','')} {c.get('title','')} {c.get('content','')}" for c in ctx))


_SIGS = {}


def _signatures(anchor: str) -> list[str]:
    """Signature lines of every chunk that contains the anchor (empty list = module level, no signature needed)."""
    if not _SIGS:
        for ch in C.load_code_corpus():
            _SIGS.setdefault("__chunks__", []).append((norm(ch.text), next((l.strip() for l in ch.text.splitlines() if J2.SIG_RE.match(l)), None)))
    key = norm(anchor)
    if key not in _SIGS:
        _SIGS[key] = [sig for txt, sig in _SIGS["__chunks__"] if key in txt]
    return _SIGS[key]


def present_ctx(need, text_norm: str) -> bool:
    """Stricter: the anchor AND the signature of its enclosing function/class must be in the context."""
    if not present(need, text_norm):
        return False
    kind, val = need
    if kind == "mem":
        return True
    for a in val:
        sigs = _signatures(a)
        if sigs and None not in sigs and not any(norm(s) in text_norm for s in sigs):
            return False
    return True


def score_task(t: dict, work_ctx: list[dict], store_by_id: dict) -> dict:
    text = ctx_text(work_ctx)
    needs = [(ci, n) for ci, c in enumerate(t["criteria"]) for n in c["needs"]]
    hit = [present(n, text) for _, n in needs]
    hit_ctx = [present_ctx(n, text) for _, n in needs]
    crit_ok = []
    for ci, c in enumerate(t["criteria"]):
        crit_ok.append(all(h for (cj, _), h in zip(needs, hit) if cj == ci))
    foreign = sorted(set(FOREIGN.findall(text)))
    stale = [i for i in t["forbid"] if i in text]
    return dict(recall=sum(hit) / len(hit), recall_ctx=sum(hit_ctx) / len(hit_ctx), complete_ctx=all(hit_ctx),
                crit=sum(crit_ok) / len(crit_ok), complete=all(hit),
                foreign=len(foreign), stale=len(stale), safe=all(hit) and not foreign and not stale,
                chars=len(text))


# ------------------------------------------------------------------ main experiment
_ENVS = {}


def build_env(store, code_chunks, files_in_order, key=None):
    if key is not None and key in _ENVS:
        return _ENVS[key]
    env = dict(store=store, ws=flux_workspace(store), code=code_chunks, files_in_order=files_in_order)
    if key is not None:
        _ENVS[key] = env
    return env


def validate_ground_truth(code_chunks, store, tasks=None):
    allcode = norm("\n".join(c.text for c in code_chunks))
    allsrc = norm("\n".join(p.read_text(encoding="utf-8", errors="replace") for p in C.project_files()))
    ids = {m.id for m in store}
    bad = []
    for t in (tasks or TASKS):
        for ci, c in enumerate(t["criteria"]):
            for kind, val in c["needs"]:
                if kind == "mem" and val not in ids:
                    bad.append((t["id"], "mem", val))
                if kind == "code":
                    for a in val:
                        if norm(a) not in allsrc:
                            bad.append((t["id"], "anchor", a))
    return bad


def run_strategy(name, fn, env, workflows=("low", "high"), tasks=None):
    store_by_id = {m.id: m for m in env["store"]}
    rows = {w: [] for w in workflows}
    for t in (tasks or TASKS):
        ctx, head_dup = fn(t, env)
        sc = score_task(t, ctx["work"], store_by_id)
        for w in workflows:
            calls = build_calls(t, ctx, w, head_dup)
            toks, usd = run_cost(calls, w)
            rows[w].append(dict(task=t["id"], tokens=toks, usd=usd, **sc))
    return rows


def summarize(rows):
    n = len(rows)
    tot = sum(r["tokens"] for r in rows)
    ok = sum(r["complete"] for r in rows)
    safe = sum(r["safe"] for r in rows)
    return dict(tokens=statistics.mean(r["tokens"] for r in rows), usd=statistics.mean(r["usd"] for r in rows),
                recall=statistics.mean(r["recall"] for r in rows), crit=statistics.mean(r["crit"] for r in rows),
                recall_ctx=statistics.mean(r["recall_ctx"] for r in rows),
                complete_ctx=sum(r["complete_ctx"] for r in rows) / n,
                complete=ok / n, safe=safe / n, foreign=statistics.mean(r["foreign"] for r in rows),
                foreign_tasks=sum(r["foreign"] > 0 for r in rows) / n, stale_tasks=sum(r["stale"] > 0 for r in rows) / n,
                tok_per_safe=(tot / safe) if safe else float("inf"), tok_per_complete=(tot / ok) if ok else float("inf"),
                ctx_chars=statistics.mean(r["chars"] for r in rows))


def bootstrap(rows, key, iters=2000, seed=7):
    rnd = random.Random(seed)
    vals = [float(r[key]) for r in rows]
    means = sorted(statistics.mean(rnd.choices(vals, k=len(vals))) for _ in range(iters))
    return means[int(.025 * iters)], means[int(.975 * iters)]


CORE = ["S0 بدون Context", "A0a ریختن همه‌چیز، سقف ۱۰۰k توکن", "A0b ریختن همه‌چیز، بدون سقف (نشدنی)",
        "A1 الگوریتم فعلی Flux", "B1 Flux + حذف تکرار Head", "JEVS v0", "JEVS v1", "JEVS v2", "JEVS v2 دقیق"]


def load_all():
    code_chunks = C.load_code_corpus()
    files_in_order = []
    for p in C.project_files():
        rel = p.relative_to(ROOT).as_posix()
        if p.stat().st_size > 400_000:
            continue
        try:
            files_in_order.append(C.Chunk(rel, rel, p.read_text(encoding="utf-8", errors="replace")))
        except OSError:
            pass
    return code_chunks, files_in_order


def merge_seeds(per_seed, n_tasks):
    merged = []
    for ti in range(n_tasks):
        rs = [per_seed[s][ti] for s in range(len(per_seed))]
        row = {k: (statistics.mean(r[k] for r in rs) if not isinstance(rs[0][k], bool) else all(r[k] for r in rs))
               for k in rs[0] if k != "task"}
        row["task"] = rs[0]["task"]
        merged.append(row)
    return merged


def compare(strategies, tasks, code_chunks, files_in_order, seeds, main_cfg, label):
    res = {w: {} for w in ("low", "high")}
    per_task = {}
    t0 = time.time()
    for name, fn in strategies.items():
        agg = {w: [] for w in res}
        for seed in seeds:
            env = build_env(C.build_memory_store(main_cfg["n_other"], main_cfg["per"], seed), code_chunks, files_in_order,
                            key=("main", seed))
            out = run_strategy(name, fn, env, tasks=tasks)
            for w in agg:
                agg[w].append(out[w])
        for w in agg:
            merged = merge_seeds(agg[w], len(tasks))
            s = summarize(merged)
            s["recall_ci"] = bootstrap(merged, "recall")
            s["safe_ci"] = bootstrap(merged, "safe")
            res[w][name] = s
            per_task[(w, name)] = merged
        print(f"  [{label}] {name}  ({time.time() - t0:.0f}s)", flush=True)
    return res, {name: [dict(task=r["task"], tokens=r["tokens"], recall=r["recall"], crit=r["crit"], safe=r["safe"])
                        for r in rows] for (w, name), rows in per_task.items() if w == "low"}


def main(mode="dev"):
    t0 = time.time()
    code_chunks, files_in_order = load_all()
    SEEDS = (0, 1, 2)
    MAIN = dict(n_other=3, per=60)
    if mode == "holdout":
        from tasks_holdout import HOLDOUT
        tasks = HOLDOUT
    elif mode == "holdout2":
        from tasks_holdout2 import HOLDOUT2
        tasks = HOLDOUT2
    else:
        tasks = TASKS
    out = dict(mode=mode, config=dict(worker_budget=WORKER_BUDGET, naive_window=NAIVE_WINDOW, seeds=SEEDS, main=MAIN,
                                      n_tasks=len(tasks), n_chunks=len(code_chunks),
                                      n_needs=sum(len(c["needs"]) for t in tasks for c in t["criteria"]),
                                      corpus_tokens=sum(J.est_tokens(c.text) for c in code_chunks)))

    bad = validate_ground_truth(code_chunks, C.build_memory_store(MAIN["n_other"], MAIN["per"], 0), tasks)
    if bad:
        print("GROUND TRUTH ERRORS:", *bad, sep="\n  ")
        sys.exit(1)
    print(f"[{mode}] ground truth ok: {len(tasks)} tasks, {out['config']['n_needs']} needs", flush=True)

    allstrat = {**STRATEGIES, **ABLATIONS}
    strategies = allstrat if mode == "dev" else {k: allstrat[k] for k in CORE}
    out["main"], out["per_task_low"] = compare(strategies, tasks, code_chunks, files_in_order, SEEDS, MAIN, mode)

    if mode == "dev":
        scale = []
        for n_other, per in ((1, 10), (3, 60), (10, 300), (20, 1000)):
            for name in ("A1 الگوریتم فعلی Flux", "JEVS v0", "JEVS v1", "JEVS v2"):
                rs = []
                for seed in SEEDS[:2]:
                    store = C.build_memory_store(n_other, per, seed)
                    env = build_env(store, code_chunks, files_in_order)
                    rs.append(run_strategy(name, allstrat[name], env, workflows=("low",), tasks=tasks)["low"])
                s = summarize([r for run in rs for r in run])
                s.update(n_other=n_other, per=per, store=len(store), strategy=name)
                scale.append(s)
                print(f"  scale {n_other}x{per} {name} store={len(store)} ({time.time() - t0:.0f}s)", flush=True)
        out["scale"] = scale

        curve = []
        env = build_env(C.build_memory_store(MAIN["n_other"], MAIN["per"], 0), code_chunks, files_in_order, key=("main", 0))
        for label, flags in (("v0", J.Flags()), ("v1", J.v1_flags())):
            for b in (500, 1000, 2000, 3000, 4000, 6000, 8000, 12000):
                res = run_strategy("jevs", make_jevs(flags, budget=b), env, workflows=("low",), tasks=tasks)["low"]
                s = summarize(res)
                s.update(budget=b, version=label)
                curve.append(s)
        for pc in (300, 500, 700, 1000, 1400, 2000):
            res = run_strategy("jevs2", make_jevs2(J2.v2_cfg(per_crit=pc, budget=99999)), env, workflows=("low",), tasks=tasks)["low"]
            s = summarize(res)
            s.update(budget=pc, version="v2 per-criterion")
            curve.append(s)
        out["curve"] = curve

        # latency of the algorithm itself (local CPU, no model): index build and per-task selection
        timing = []
        for n_other, per in ((3, 60), (20, 1000)):
            store = C.build_memory_store(n_other, per, 0)
            t1 = time.perf_counter()
            idx2 = J2.Index2(code_chunks, store, J2.v2_cfg())
            build = time.perf_counter() - t1
            t1 = time.perf_counter()
            for t in tasks:
                J2.select(idx2, t, J2.v2_cfg())
            per_task_ms = (time.perf_counter() - t1) / len(tasks) * 1000
            timing.append(dict(store=len(store), windows=len(idx2.passages), build_s=round(build, 2),
                               select_ms=round(per_task_ms, 1)))
            print(f"  timing store={len(store)} build={build:.2f}s select={per_task_ms:.1f}ms/task", flush=True)
        out["timing"] = timing

        diag = []
        for t in tasks:
            pack = get_index(env, J.v1_flags()).select(t, WORKER_BUDGET, J.v1_flags())
            diag.append(dict(task=t["id"], lang=t["lang"], pack_tokens=pack.tokens, chosen=len(pack.items),
                             gaps=len(pack.gaps), candidates=pack.trace["candidates"]))
        out["diag"] = diag
    out["elapsed_s"] = round(time.time() - t0, 1)
    name = {"dev": "results.json", "holdout": "results_holdout.json", "holdout2": "results_holdout2.json"}[mode]
    (HERE / name).write_text(json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print("wrote", name, out["elapsed_s"], "s", flush=True)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "dev")
