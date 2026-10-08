"""JEVS v2 -- line-level evidence retrieval and packing (rewrite of v1).

What changed versus v1, and why (all from the v0/v1 diagnostics on the dev set):
  * Unit of retrieval = a small window of lines inside a function/section, not the whole function or a
    25-line segment. Long functions no longer cost their full length when only 3 lines matter.
  * Unit of payment = new lines only. Overlapping or adjacent windows of the same function are merged, and
    the function signature is paid once, so several criteria can share one function cheaply.
  * Every kept line keeps its context: signature + matched lines + `expand` neighbours, gaps shown as "...".
  * Per-criterion ranked lists, packed round-robin (the v1 component that gave the largest gain).
  * Inverted index: scoring touches only postings of the query terms (fast with 20k+ notes).
  * Memory notes are still sent whole (never truncated) so a "memory present" check stays honest.
Tuned only on the 15 dev tasks; both holdout sets are evaluated once.
"""
from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field

import jevs as J

SIG_RE = re.compile(r"^\s*(async\s+def|def|class)\s+\w+")


@dataclass
class Cfg:
    budget: int = 3000            # evidence tokens for one worker call
    win: int = 6                  # lines per retrieval window
    stride: int = 3
    expand: int = 1               # neighbour lines kept around every selected window
    theta: float = 0.3            # per-criterion relative cutoff
    k_per_crit: int = 40
    glossary: bool = True
    project_filter: bool = True
    stale_filter: bool = True
    id_weight: int = 2            # path/qualname tokens repeated into every window of the unit
    symbol_boost: float = 1.0     # query terms that are defined symbols in the project get this multiplier
    file_prior: bool = False      # down-weight logs/dumps/debug scripts
    lexicon: bool = False         # project-mined Persian->English expansions
    lexicon_weight: float = 0.5
    mem_whole: bool = True
    k1: float = 1.2
    b: float = 0.75
    # --- v2 ranking/packing options (dev-tuned)
    maxp: bool = False            # rank functions by their best window (+ whole-function score), one per turn
    unit_beta: float = 0.0        # weight of the whole-function BM25 in the MaxP score
    win_keep: float = 0.7         # also keep other windows of the same function scoring >= win_keep x its best
    max_win_per_unit: int = 2
    max_notes: int = 99           # cap on whole memory notes per task
    note_share: float = 1.0       # max share of the budget that notes may take

    def index_key(self):
        return (self.win, self.stride, self.id_weight, self.file_prior)


@dataclass(eq=False)
class Unit:
    id: str
    kind: str                     # code | mem
    path: str
    lines: list
    project_id: str = "flux"
    status: str = "active"
    sig: int | None = None        # index of the signature line
    meta: dict = field(default_factory=dict)
    prior: float = 1.0


@dataclass(eq=False)
class Passage:
    unit: Unit
    a: int
    b: int
    tf: Counter
    n: int


LOW_VALUE = re.compile(r"(^|/)(var|build|dist)/|_debug|debug_|dump|inspect_|_output|\.txt$|\.css$|\.json$")


class Index2:
    def __init__(self, code_chunks, memories, cfg: Cfg):
        self.cfg = cfg
        self.units: list[Unit] = []
        self.passages: list[Passage] = []
        self.symbols: set[str] = set()
        for c in code_chunks:
            lines = c.text.splitlines()
            sig = next((i for i, l in enumerate(lines) if SIG_RE.match(l)), None)
            prior = 0.5 if (cfg.file_prior and LOW_VALUE.search(c.path)) else 1.0
            u = Unit(c.id, "code", c.path, lines, c.project_id, sig=sig, prior=prior)
            self.units.append(u)
            q = c.id.split("::")[-1]
            for name in q.split("."):
                if name and not name.startswith("<"):
                    self.symbols.add(name.lower())
            id_toks = J.tokenize(c.id) * cfg.id_weight
            sig_toks = J.tokenize(lines[sig]) if sig is not None else []
            starts = range(0, max(1, len(lines) - cfg.win + cfg.stride), cfg.stride) if len(lines) > cfg.win else [0]
            for a in starts:
                b = min(len(lines), a + cfg.win)
                toks = J.tokenize("\n".join(lines[a:b])) + id_toks + sig_toks
                if toks:
                    self.passages.append(Passage(u, a, b, Counter(toks), len(toks)))
        for m in memories:
            lines = [m.title] + m.content.splitlines()
            u = Unit(m.id, "mem", m.id, lines, m.project_id, m.status, meta={"revision": m.revision, "title": m.title})
            self.units.append(u)
            toks = J.tokenize(m.title) * 3 + J.tokenize(m.content)
            self.passages.append(Passage(u, 0, len(lines), Counter(toks), max(1, len(toks))))
        # whole-unit postings (function / note level) for the MaxP blend
        udf = Counter()
        self.upost = defaultdict(list)
        self.utf = []
        for ui, u in enumerate(self.units):
            if u.kind == "code":
                toks = J.tokenize("\n".join(u.lines)) + J.tokenize(u.id) * cfg.id_weight
            else:
                toks = J.tokenize(u.meta["title"]) * 3 + J.tokenize("\n".join(u.lines[1:]))
            tf = Counter(toks)
            self.utf.append(max(1, len(toks)))
            for t, f in tf.items():
                udf[t] += 1
                self.upost[t].append((ui, f))
        self.uavg = sum(self.utf) / max(1, len(self.utf))
        self.uidx = {id(u): i for i, u in enumerate(self.units)}
        df = Counter()
        self.post = defaultdict(list)
        for pid, p in enumerate(self.passages):
            for t, f in p.tf.items():
                df[t] += 1
                self.post[t].append((pid, f))
        N = len(self.passages)
        self.idf = {t: math.log(1 + (N - c + 0.5) / (c + 0.5)) for t, c in df.items()}
        self.avg = sum(p.n for p in self.passages) / N
        self.lexicon = self._mine_lexicon(memories) if cfg.lexicon else {}

    # -- project-mined bilingual lexicon: English tokens that co-occur with a Persian word in the same line
    def _mine_lexicon(self, memories):
        co, fa_n, en_n = Counter(), Counter(), Counter()
        lines = [l for m in memories if m.project_id == "flux" for l in m.content.splitlines()]
        for u in self.units:
            if u.kind == "code":
                lines += [l for l in u.lines if re.search(r"[؀-ۿ]", l)]
        for l in lines:
            toks = set(J.tokenize(l))
            fa = {t for t in toks if not t.isascii()}
            en = {t for t in toks if t.isascii()}
            for f in fa:
                fa_n[f] += 1
                for e in en:
                    co[(f, e)] += 1
            for e in en:
                en_n[e] += 1
        total = max(1, len(lines))
        lex = defaultdict(list)
        for (f, e), c in co.items():
            if c < 2:
                continue
            pmi = math.log(c * total / (fa_n[f] * en_n[e]))
            if pmi > 1.5:
                lex[f].append((pmi, e))
        return {f: [e for _, e in sorted(v, reverse=True)[:3]] for f, v in lex.items()}

    # -- query
    def query(self, text: str) -> dict:
        toks = J.tokenize(text, glossary=self.cfg.glossary)
        q = {}
        for t in set(toks):
            if t in self.idf:
                w = self.idf[t] * (self.cfg.symbol_boost if t in self.symbols else 1.0)
                q[t] = max(q.get(t, 0), w)
        if self.lexicon:
            for t in set(toks):
                for e in self.lexicon.get(t, []):
                    if e in self.idf and e not in q:
                        q[e] = self.cfg.lexicon_weight * self.idf[e]
        return q

    def score_units(self, q: dict) -> dict:
        k1, b, avg = self.cfg.k1, self.cfg.b, self.uavg
        s = defaultdict(float)
        for t, w in q.items():
            for ui, f in self.upost.get(t, ()):
                n = self.utf[ui]
                s[ui] += w * f * (k1 + 1) / (f + k1 * (1 - b + b * n / avg))
        return s

    def score(self, q: dict, ok) -> list:
        k1, b, avg = self.cfg.k1, self.cfg.b, self.avg
        s = defaultdict(float)
        for t, w in q.items():
            for pid, f in self.post.get(t, ()):
                n = self.passages[pid].n
                s[pid] += w * f * (k1 + 1) / (f + k1 * (1 - b + b * n / avg))
        out = []
        for pid, v in s.items():
            p = self.passages[pid]
            if ok(p.unit):
                out.append((v * p.unit.prior, p))
        out.sort(key=lambda x: -x[0])
        return out


# ------------------------------------------------------------------ packing
def render_unit(u: Unit, keep: set) -> str:
    if u.kind == "mem":
        return f"[mem:{u.id} rev{u.meta.get('revision', 1)}]\n" + "\n".join(u.lines)
    idx = sorted(keep | ({u.sig} if u.sig is not None else set()))
    out, prev = [f"[{u.id} L{idx[0] + 1}-{idx[-1] + 1}]"], None
    for i in idx:
        if prev is not None and i > prev + 1:
            out.append("    ...")
        out.append(u.lines[i])
        prev = i
    return "\n".join(out)


@dataclass
class Pack2:
    keep: dict                    # Unit -> set(line idx)
    order: list                   # units in selection order
    tokens: int
    gaps: list
    trace: dict


def select(index: Index2, task: dict, cfg: Cfg | None = None) -> Pack2:
    cfg = cfg or index.cfg
    obj = index.query(task["objective"])
    crit_q = []
    for c in task["criteria"]:
        q = {t: w * 0.5 for t, w in obj.items()}
        for t, w in index.query(c["text"]).items():
            q[t] = max(q.get(t, 0), w)
        crit_q.append(q)

    def ok(u: Unit) -> bool:
        if cfg.project_filter and u.project_id not in (task["project_id"], "global"):
            return False
        if cfg.stale_filter and u.status != "active":
            return False
        return True

    keep: dict = {}
    order: list = []
    cost: dict = {}
    used = 0
    notes_used = [0, 0]           # count, tokens

    def unit_cost(u, lines):
        return J.est_tokens(render_unit(u, lines)) + J.ITEM_OVERHEAD

    def add_note(u):
        nonlocal used
        if u in keep or notes_used[0] >= cfg.max_notes:
            return
        c = unit_cost(u, set())
        if used + c <= cfg.budget and notes_used[1] + c <= cfg.note_share * cfg.budget:
            keep[u], cost[u] = set(), c
            order.append(u)
            used += c
            notes_used[0] += 1
            notes_used[1] += c

    def add_lines(u, new_lines):
        nonlocal used
        new = set(new_lines) - keep.get(u, set())
        if not new:
            return
        merged = keep.get(u, set()) | new
        c = unit_cost(u, merged)
        delta = c - cost.get(u, 0)
        if used + delta > cfg.budget:
            return
        if u not in keep:
            order.append(u)
        keep[u], cost[u] = merged, c
        used += delta

    def window_lines(u, p):
        lo, hi = max(0, p.a - cfg.expand), min(len(u.lines), p.b + cfg.expand)
        return range(lo, hi)

    if cfg.maxp:
        ulists = []
        for q in crit_q:
            wins = index.score(q, ok)
            by_u = {}
            for sc_, p in wins:
                by_u.setdefault(p.unit, []).append((sc_, p))
            top_w = wins[0][0] if wins else 1.0
            us = index.score_units(q) if cfg.unit_beta else {}
            top_u = max((us[index.uidx[id(u)]] for u in by_u), default=1.0) if us else 1.0
            ranked = []
            for u, ws in by_u.items():
                val = (1 - cfg.unit_beta) * ws[0][0] / top_w
                if us:
                    val += cfg.unit_beta * us.get(index.uidx[id(u)], 0.0) / (top_u or 1.0)
                ranked.append((val, u, ws))
            ranked.sort(key=lambda x: -x[0])
            ulists.append(ranked[: cfg.k_per_crit])
        for depth in range(cfg.k_per_crit):
            alive = False
            for ranked in ulists:
                if depth >= len(ranked):
                    continue
                val, u, ws = ranked[depth]
                if val < cfg.theta * ranked[0][0]:
                    continue
                alive = True
                if u.kind == "mem":
                    add_note(u)
                    continue
                best = ws[0][0]
                for sc_, p in ws[: cfg.max_win_per_unit]:
                    if sc_ >= cfg.win_keep * best or p is ws[0][1]:
                        add_lines(u, window_lines(u, p))
            if not alive:
                break
        gaps = [{"criterion": task["criteria"][ci]["text"], "coverage": 0.0} for ci, r in enumerate(ulists) if not r]
        return Pack2(keep, order, used, gaps, {"units": len(order), "lines": sum(len(v) for v in keep.values())})

    lists = [index.score(q, ok)[: cfg.k_per_crit] for q in crit_q]

    for depth in range(cfg.k_per_crit):
        alive = False
        for sc in lists:
            if depth >= len(sc):
                continue
            s, p = sc[depth]
            if s < cfg.theta * sc[0][0]:
                continue
            alive = True
            u = p.unit
            if u.kind == "mem":
                if u in keep:
                    continue
                c = unit_cost(u, set())
                if used + c <= cfg.budget:
                    keep[u], cost[u] = set(), c
                    order.append(u)
                    used += c
                continue
            lo, hi = max(0, p.a - cfg.expand), min(len(u.lines), p.b + cfg.expand)
            new = set(range(lo, hi)) - keep.get(u, set())
            if not new:
                continue
            merged = keep.get(u, set()) | new
            c = unit_cost(u, merged)
            delta = c - cost.get(u, 0)
            if used + delta > cfg.budget:
                continue
            if u not in keep:
                order.append(u)
            keep[u], cost[u] = merged, c
            used += delta
        if not alive:
            break

    gaps = []
    for ci, sc in enumerate(lists):
        if not sc:
            gaps.append({"criterion": task["criteria"][ci]["text"], "coverage": 0.0})
    return Pack2(keep, order, used, gaps, {"units": len(order), "lines": sum(len(v) for v in keep.values())})


def worker_context(pack: Pack2) -> list[dict]:
    code = [render_unit(u, pack.keep[u]) for u in pack.order if u.kind == "code"]
    notes = [render_unit(u, set()) for u in pack.order if u.kind == "mem"]
    ctx = []
    if code:
        ctx.append({"ref": "jevs:evidence", "title": "Selected source lines (... = omitted lines)", "content": "\n\n".join(code)})
    if notes:
        ctx.append({"ref": "jevs:notes", "title": "Selected project notes", "content": "\n\n".join(notes)})
    if pack.gaps:
        ctx.append({"ref": "jevs:gaps", "title": "No evidence found for (state it, do not guess)",
                    "content": "\n".join(g["criterion"] for g in pack.gaps)})
    return ctx


def head_context(pack: Pack2) -> list[dict]:
    lines = []
    for u in pack.order:
        if u.kind == "mem":
            lines.append(f"- note {u.id}")
        else:
            ks = sorted(pack.keep[u])
            lines.append(f"- {u.id} L{ks[0] + 1}-{ks[-1] + 1}")
    lines += [f"! no evidence: {g['criterion']}" for g in pack.gaps]
    return [{"ref": "jevs:evidence-map", "title": "Evidence map (bodies go to workers)", "content": "\n".join(lines)}]
