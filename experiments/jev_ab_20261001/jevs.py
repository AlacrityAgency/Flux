"""JEVS -- Judged Evidence Selection (v0 pre-registered; v1 = changes motivated by the v0 diagnostics).

Pure-Python reference implementation of the algorithm proposed for Flux. No model calls, no embeddings.

    contract  ->  need extraction  ->  scope filter  ->  cheap lexical retrieval (BM25)
              ->  greedy marginal-coverage packing under a token budget  ->  sufficiency report
              ->  role-shaped context (head: evidence map, worker/verifier: evidence bodies, once)

v0 parameters were fixed before the first run. v1 additions (stemming, index-time sub-chunking, relevance-ordered
selection with a relative cutoff, pseudo-relevance feedback) were added after the v0 diagnostics and tuned only on
the 15 dev tasks; the 10 holdout tasks were written before v1 existed and evaluated once.
"""
from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field

TOKENS_PER_CHAR = 1 / 2.5          # same estimator the Flux budget ledger uses
ITEM_OVERHEAD = 8                  # tokens for the "[id]" header of an item
MAX_CHUNK_TOKENS = 900             # larger chunks are windowed around the query terms
CANDIDATES_K = 80
TAU = 5e-5                         # stop when best marginal gain per token falls below this
DIMINISH = 0.5                     # weight multiplier per time a query term is already covered
DEDUP_JACCARD = 0.8
GAP_COVERAGE = 0.35
SEG_LINES, SEG_STRIDE = 25, 18     # v1: large chunks are indexed as overlapping segments
THETA = 0.35                       # v1: drop candidates scoring below THETA x the best score
PRF_DOCS, PRF_TERMS, PRF_WEIGHT = 3, 6, 0.4

STOP = set("""the and for are but not you all can was were has have had how why what when which who whom does did doing
 this that these those with from into onto over under then than also only any each some such via per its it's their there
 here where while will would should could may might must shall our your his her they them are been being out off use used
 using make made need needs show shown check explain document review
 و در به از که این را با است برای کن کنید کند کنم آیا چه چرا چگونه کدام یک آن آنها ها های بر تا هم یا اگر هر همه شود
 شده شدن می بود باید نیست نمی بین چند است؟ دارد دارند""".split())

# Generic Persian->English technical glossary (query side only). Written from the vocabulary of the Flux
# README/docs, not from the benchmark tasks.
GLOSSARY = {
    "حافظه": ["memory", "memories"], "بازیابی": ["retrieve", "retrieval"], "بودجه": ["budget"],
    "توکن": ["token"], "پروژه": ["project"], "تکرار": ["retry", "attempts"], "تکراری": ["duplicate"],
    "زیرکار": ["subtask", "subtasks"], "معیار": ["criteria", "criterion", "acceptance"],
    "پذیرش": ["acceptance", "accept"], "خروجی": ["output"], "وابستگی": ["dependency", "dependencies"],
"بازبین": ["verification", "verifier", "review"],
    "بازبینی": ["verification", "review"], "هزینه": ["cost"], "ذخیره": ["save", "store"],
    "اعتبارسنجی": ["validate", "validation", "validator"], "درخواست": ["request", "prompt"],
    "برش": ["truncate", "slice"], "بریده": ["truncate", "slice"], "وگو": ["conversation"],
    "وگوی": ["conversation"], "انتقال": ["transition", "transitions"], "وضعیت": ["state", "status"],
    "چرخه": ["cycle"], "خطا": ["error"], "مصرف": ["usage"], "خلاصه": ["summary"], "ارسال": ["send", "sends"],
    "مرجع": ["reference"], "اجرا": ["run", "execute"], "فایل": ["file", "files"], "پوشه": ["folder", "directory"],
    "فیلتر": ["filter"], "اولویت": ["priority"], "انتخاب": ["select", "selection"],
    "محرمانه": ["secret"], "کلید": ["key"], "تصمیم": ["decision"], "منسوخ": ["obsolete", "old"],
    "جداسازی": ["isolation", "project_id", "scope"], "ابزار": ["tool"], "شواهد": ["evidence"],
    "آزمون": ["test"], "تست": ["test"], "سقف": ["limit", "cap"], "نسخه": ["revision", "version"],
}

_ID_SPLIT = re.compile(r"[A-Z]+(?![a-z])|[A-Z]?[a-z]+|\d+")
_WORD = re.compile(r"[A-Za-z_][A-Za-z0-9_]*|[؀-ۿ]+|\d+")


def normalize(s: str) -> str:
    s = s.replace("ي", "ی").replace("ك", "ک").replace("‏", "")
    return re.sub(r"[ً-ٰٟ]", "", s).lower()


def stem(w: str) -> str:
    """Tiny English suffix stripper so that retrieval/retrieve/retrieved/retrieves share one stem."""
    if len(w) <= 4 or not w.isascii():
        return w
    if w.endswith("ies") and len(w) > 5:
        w = w[:-3] + "y"
    elif w.endswith("es") and len(w) > 5:
        w = w[:-2]
    elif w.endswith("s") and not w.endswith("ss"):
        w = w[:-1]
    for suf in ("ing", "ion", "ed", "al", "ly"):
        if w.endswith(suf) and len(w) - len(suf) >= 4:
            w = w[: -len(suf)]
            break
    if w.endswith("e") and len(w) > 4:
        w = w[:-1]
    return w


def tokenize(text: str, glossary: bool = False, stemming: bool = False) -> list[str]:
    if stemming:
        return [stem(t) for t in tokenize(text, glossary, False)]
    out = []
    text = text.replace("‌", " ")          # ZWNJ splits words, as in Flux's own retrieve()
    for w in _WORD.findall(text):
        if w.isascii():
            low = w.lower()
            if "_" in w or any(c.isupper() for c in w[1:]) :
                if len(low) >= 3:
                    out.append(low)                       # keep the identifier itself
                parts = [x.lower() for seg in re.split(r"_+", w) for x in _ID_SPLIT.findall(seg)]
            else:
                parts = [low]
            out += [p for p in parts if len(p) >= 3 and p not in STOP]
        else:
            n = normalize(w)
            if len(n) < 3 or n in STOP:
                continue
            out.append(n)
            if glossary and n in GLOSSARY:
                out += GLOSSARY[n]
    return out


def est_tokens(text: str) -> int:
    return int(len(text) * TOKENS_PER_CHAR)


@dataclass(eq=False)
class Doc:
    id: str
    kind: str                 # code | mem
    text: str                 # rendered body
    project_id: str = "flux"
    status: str = "active"
    meta: dict = field(default_factory=dict)
    tf: Counter = field(default_factory=Counter)
    toks: frozenset = frozenset()
    n: int = 0
    lineset: frozenset = frozenset()
    cost: int = 0

    def finish(self, stemming: bool = False):
        head = self.id if self.kind == "code" else self.meta.get("title", "") + " " + self.id
        toks = tokenize(self.text, stemming=stemming) + tokenize(head, stemming=stemming) * 3   # id/path/title x3
        self.tf = Counter(toks)
        self.toks = frozenset(self.tf)
        self.n = max(1, len(toks))
        self.lineset = frozenset(l.strip() for l in self.text.splitlines() if len(l.strip()) >= 3)
        self.cost = est_tokens(self.text) + ITEM_OVERHEAD
        return self


@dataclass
class Flags:
    project_filter: bool = True
    stale_filter: bool = True
    glossary: bool = True
    greedy_coverage: bool = True      # False => plain BM25 top-k fill (ablation)
    adaptive_stop: bool = True
    dedup: bool = True
    window_large: bool = True
    # ---- v1
    stemming: bool = False
    subchunk: bool = False            # index-time (needs Index built with subchunk=True)
    selector: str = "coverage"        # "coverage" (v0) | "relevance" (v1)
    prf: bool = False
    theta: float = THETA


def v1_flags(**kw) -> "Flags":
    # Final v1 (chosen on the 15 dev tasks only): stemming and PRF were tried and removed because they lowered
    # dev recall (0.65 -> 0.62 / 0.62); they stay available as flags.
    base = dict(stemming=False, subchunk=True, selector="per_criterion", prf=False)
    base.update(kw)
    return Flags(**base)


@dataclass
class Pack:
    items: list                       # [(Doc, rendered_text, partial_bool)]
    tokens: int
    gaps: list
    trace: dict


class _LazyCosts(dict):
    """id -> token cost, computed on first use (render() may window oversized chunks)."""
    def __init__(self, fn, docs=()):
        super().__init__()
        self.fn, self.by_id = fn, {}
        for d in docs:
            self.by_id[d.id] = d

    def __missing__(self, key):
        self[key] = self.fn(self.by_id[key])
        return self[key]

    def cost(self, d):
        self.by_id.setdefault(d.id, d)
        return self[d.id]


class Index:
    def __init__(self, code_chunks, memories, subchunk: bool = False, stemming: bool = False):
        self.docs: list[Doc] = []
        self.stemming = stemming
        for c in code_chunks:
            lines = c.text.splitlines()
            if subchunk and len(lines) > SEG_LINES:
                starts = list(range(0, max(1, len(lines) - (SEG_LINES - SEG_STRIDE)), SEG_STRIDE))
                for k, a in enumerate(starts):
                    seg = lines[a:a + SEG_LINES]
                    if k > 0:
                        seg = [lines[0], "    ..."] + seg          # keep the signature visible
                    self.docs.append(Doc(id=f"{c.id}#s{k + 1}/{len(starts)}", kind="code", text="\n".join(seg),
                                         project_id=c.project_id, meta={"parent": c.id}).finish(stemming))
            else:
                self.docs.append(Doc(id=c.id, kind="code", text=c.text, project_id=c.project_id).finish(stemming))
        for m in memories:
            body = f"{m.title}\n{m.content}"
            self.docs.append(Doc(id=m.id, kind="mem", text=body, project_id=m.project_id, status=m.status,
                                 meta={"title": m.title, "revision": m.revision}).finish(stemming))
        df = Counter()
        for d in self.docs:
            df.update(d.toks)
        N = len(self.docs)
        self.N = N
        self.idf = {t: math.log(1 + (N - c + 0.5) / (c + 0.5)) for t, c in df.items()}
        self.avg_len = sum(d.n for d in self.docs) / N

    # ---- retrieval -------------------------------------------------------------------------------
    def bm25(self, q: dict, d: Doc, k1=1.2, b=0.75) -> float:
        s = 0.0
        for t, w in q.items():
            f = d.tf.get(t)
            if f:
                s += w * f * (k1 + 1) / (f + k1 * (1 - b + b * d.n / self.avg_len))
        return s

    def query(self, text: str, glossary: bool) -> dict:
        toks = tokenize(text, glossary=glossary, stemming=self.stemming)
        return {t: self.idf[t] for t in set(toks) if t in self.idf}     # terms absent from the corpus cannot retrieve

    # ---- selection -------------------------------------------------------------------------------
    def select(self, task: dict, budget: int, f: Flags) -> Pack:
        crit = task["criteria"]
        obj_q = self.query(task["objective"], f.glossary)
        crit_q = []
        for c in crit:
            q = {t: w * 0.5 for t, w in obj_q.items()}          # objective counts at half weight everywhere
            for t, w in self.query(c["text"], f.glossary).items():
                q[t] = max(q.get(t, 0), w)
            crit_q.append(q)
        union = dict(obj_q)
        for q in crit_q:
            for t, w in q.items():
                union[t] = max(union.get(t, 0), w)

        def eligible(d: Doc) -> bool:
            if f.project_filter and d.project_id not in (task["project_id"], "global"):
                return False
            if f.stale_filter and d.status != "active":
                return False
            return True

        assert f.stemming == self.stemming, "Flags.stemming must match the Index it is used with"
        elig = [d for d in self.docs if eligible(d)]
        scored = [(self.bm25(union, d), d) for d in elig]
        scored = [(s, d) for s, d in scored if s > 0]
        scored.sort(key=lambda x: -x[0])
        if f.prf and scored:
            # v1: pseudo-relevance feedback -- add the most characteristic terms of the top documents.
            fb = Counter()
            for _, d in scored[:PRF_DOCS]:
                for t, c in d.tf.items():
                    if t not in union:
                        fb[t] += c * self.idf[t]
            extra = {t: PRF_WEIGHT * self.idf[t] for t, _ in fb.most_common(PRF_TERMS)}
            union = {**union, **extra}
            scored = [(self.bm25(union, d), d) for d in elig]
            scored = [(s, d) for s, d in scored if s > 0]
            scored.sort(key=lambda x: -x[0])
        cands = [d for _, d in scored[:CANDIDATES_K]]
        base = {d.id: s for s, d in scored[:CANDIDATES_K]}

        cache = {}

        def render(d: Doc):
            """Return (text, partial). Oversized chunks are windowed around the query terms, never cut blindly."""
            if d.id in cache:
                return cache[d.id]
            text, partial = d.text, False
            if f.window_large and est_tokens(text) > MAX_CHUNK_TOKENS:
                lines = text.splitlines()
                lim = int(MAX_CHUNK_TOKENS / TOKENS_PER_CHAR)
                w = [sum(union.get(t, 0) for t in set(tokenize(l, stemming=f.stemming))) for l in lines]
                best, best_i, best_j, i, size, acc = -1, 0, 0, 0, 0, 0.0
                for j in range(len(lines)):
                    size += len(lines[j]) + 1
                    acc += w[j]
                    while size > lim and i < j:
                        size -= len(lines[i]) + 1
                        acc -= w[i]
                        i += 1
                    if acc > best:
                        best, best_i, best_j = acc, i, j
                keep = lines[best_i:best_j + 1]
                head = [lines[0]] if best_i > 0 else []
                text = "\n".join(head + (["    ..."] if head else []) + keep + (["    ..."] if best_j < len(lines) - 1 else []))
                partial = True
            if d.kind == "mem":
                text = f"[mem:{d.id} rev{d.meta.get('revision', 1)}]\n{text}"
            else:
                text = f"[{d.id}]\n{text}"
            cache[d.id] = (text, partial)
            return cache[d.id]

        costs = _LazyCosts(lambda d: est_tokens(render(d)[0]) + ITEM_OVERHEAD, cands)
        chosen: list[Doc] = []
        used = 0

        def dup(d: Doc) -> bool:
            if not f.dedup or not d.lineset:
                return False
            for s in chosen:
                inter = len(d.lineset & s.lineset)
                if inter and inter / len(d.lineset | s.lineset) >= DEDUP_JACCARD:
                    return True
            return False

        def add(d: Doc):
            nonlocal used
            chosen.append(d)
            used += costs[d.id]

        if f.selector == "per_criterion":
            # v1b: every criterion is retrieved on its own (own BM25 list, own PRF, own relative cutoff); the lists
            # are packed round-robin by depth, so each criterion gets its best evidence before any gets a second.
            lists = []
            for q in crit_q:
                qq = dict(q)
                sc = sorted(((self.bm25(qq, d), d) for d in elig), key=lambda x: -x[0])
                sc = [(x, d) for x, d in sc[:CANDIDATES_K] if x > 0]
                if f.prf and sc:
                    fb = Counter()
                    for _, d in sc[:PRF_DOCS]:
                        for t, c in d.tf.items():
                            if t not in qq:
                                fb[t] += c * self.idf[t]
                    qq.update({t: PRF_WEIGHT * self.idf[t] for t, _ in fb.most_common(PRF_TERMS)})
                    sc = sorted(((self.bm25(qq, d), d) for d in elig), key=lambda x: -x[0])
                    sc = [(x, d) for x, d in sc[:CANDIDATES_K] if x > 0]
                lists.append(sc)
            for depth in range(CANDIDATES_K):
                alive = False
                for sc in lists:
                    if depth >= len(sc):
                        continue
                    x, d = sc[depth]
                    if f.adaptive_stop and x < f.theta * sc[0][0]:
                        continue
                    alive = True
                    if d in chosen or dup(d):
                        continue
                    if used + costs.cost(d) <= budget:
                        costs.cost(d)
                        chosen.append(d)
                        used += costs[d.id]
                if not alive:
                    break
        elif f.selector == "relevance":
            # v1: guarantee each criterion its best evidence, then take candidates in relevance order until the
            # relative cutoff, skipping duplicates and candidates that add no new query term.
            for q in crit_q:
                ranked = sorted(((self.bm25(q, d), d) for d in cands if d not in chosen), key=lambda x: -x[0])
                for sc, d in ranked:
                    if sc <= 0:
                        break
                    if used + costs[d.id] <= budget and not dup(d):
                        add(d)
                        break
            covered = set()
            for d in chosen:
                covered |= {t for t in union if t in d.toks}
            top = scored[0][0] if scored else 1.0
            for sc, d in scored[:CANDIDATES_K]:
                if f.adaptive_stop and sc < f.theta * top:
                    break
                if d in chosen or used + costs[d.id] > budget or dup(d):
                    continue
                present_t = {t for t in union if t in d.toks}
                tot = sum(union[t] for t in present_t)
                new = sum(union[t] for t in present_t - covered)
                if tot and new / tot < 0.2:
                    continue
                add(d)
                covered |= present_t
        elif not f.greedy_coverage:
            for d in cands:
                if used + costs[d.id] <= budget and not dup(d):
                    add(d)
        else:
            # Phase 1: every criterion gets its best-matching evidence first (never silently dropped).
            for q in crit_q:
                ranked = sorted(((self.bm25(q, d), d) for d in cands if d not in chosen), key=lambda x: -x[0])
                for s, d in ranked:
                    if s <= 0:
                        break
                    if d in chosen:
                        continue
                    if used + costs[d.id] <= budget and not dup(d):
                        add(d)
                        break
            # Phase 2: greedy marginal coverage per token with diminishing returns.
            masses = [sum(q.values()) or 1.0 for q in crit_q]
            cnt = [Counter() for _ in crit_q]
            for d in chosen:
                for ci, q in enumerate(crit_q):
                    for t in q:
                        if t in d.toks:
                            cnt[ci][t] += 1

            def gain(d: Doc) -> float:
                g = 0.0
                for ci, q in enumerate(crit_q):
                    for t, w in q.items():
                        if t in d.toks:
                            g += w * (DIMINISH ** cnt[ci][t]) / masses[ci]
                return g / len(crit_q)

            pool = [d for d in cands if d not in chosen]
            while pool:
                scored2 = [(gain(d) / costs[d.id], d) for d in pool if used + costs[d.id] <= budget]
                if not scored2:
                    break
                r, d = max(scored2, key=lambda x: x[0])
                pool.remove(d)
                if f.adaptive_stop and r < TAU:
                    break
                if dup(d):
                    continue
                add(d)
                for ci, q in enumerate(crit_q):
                    for t in q:
                        if t in d.toks:
                            cnt[ci][t] += 1

        # Sufficiency report: which criteria are only weakly covered by what was selected.
        gaps = []
        for ci, q in enumerate(crit_q):
            mass = sum(q.values()) or 1.0
            cov = sum(w for t, w in q.items() if any(t in d.toks for d in chosen)) / mass
            if cov < GAP_COVERAGE:
                missing = sorted((t for t in q if not any(t in d.toks for d in chosen)), key=lambda t: -q[t])[:5]
                gaps.append({"criterion": crit[ci]["text"], "coverage": round(cov, 2), "missing_terms": missing})
        items = [(d, *render(d)) for d in chosen]
        return Pack(items=items, tokens=used, gaps=gaps,
                    trace={"candidates": len(cands), "eligible": len(elig), "chosen": [d.id for d in chosen]})


# ---- role-shaped context ------------------------------------------------------------------------
def head_context(pack: Pack) -> list[dict]:
    """Evidence map for routing: ids + first line only (no bodies)."""
    lines = []
    for d, text, partial in pack.items:
        first = next((l.strip() for l in d.text.splitlines() if l.strip()), "")[:110]
        lines.append(f"- {d.id}{' (partial)' if partial else ''}: {first}")
    for g in pack.gaps:
        lines.append(f"! weak evidence for: {g['criterion']} (coverage {g['coverage']})")
    return [{"ref": "jevs:evidence-map", "title": "Evidence map (bodies go to workers)", "content": "\n".join(lines)}]


def worker_context(pack: Pack) -> list[dict]:
    code = [t for d, t, _ in pack.items if d.kind == "code"]
    notes = [t for d, t, _ in pack.items if d.kind == "mem"]
    ctx = []
    if code:
        ctx.append({"ref": "jevs:evidence", "title": "Selected source evidence", "content": "\n\n".join(code)})
    if notes:
        ctx.append({"ref": "jevs:notes", "title": "Selected project notes", "content": "\n\n".join(notes)})
    if pack.gaps:
        ctx.append({"ref": "jevs:gaps", "title": "Coverage gaps (state them, do not guess)",
                    "content": "\n".join(f"{g['criterion']} (coverage {g['coverage']})" for g in pack.gaps)})
    return ctx
