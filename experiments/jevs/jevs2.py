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
    # --- v2 structure: code graph expansion seeded by the lexical hits
    graph: bool = False
    seed_n: int = 3               # top windows per criterion used as seeds
    gamma_def: float = 0.6        # score of a "go to definition" window = seed score x gamma_def
    gamma_call: float = 0.6       # score of a "find usages" window = seed score x gamma_call
    def_lines: int = 6            # lines kept from a definition (signature + body head)
    max_callers: int = 4
    fa_stop: bool = False         # drop Persian request phrasing ("نشان داده شود", "بررسی", ...)
    fa_translated: float = 1.0    # weight of a Persian query word whose English gloss is also in the query
    path_prior: bool = False      # src 1.0, tests 0.85, other dirs/root scripts 0.6, logs 0.4 (as Flux's own snapshot order)
    dedup_lines: bool = False     # do not pay again for lines whose text is already in the pack
    cov_stop: float = 1.01        # a criterion stops taking evidence once this share of its query weight is covered
    # --- v2 vocabulary: query-side morphology and project-trained semantic vectors (no external model)
    morph: float = 0.0            # weight of vocabulary words sharing an English stem with a query word (0 = off)
    lsa: float = 0.0              # weight of the LSA cosine in the fused score (0 = off)
    lsa_dims: int = 128
    lsa_pool: int = 150           # candidates taken from the semantic list in addition to the BM25 list
    per_crit: int = 0             # >0: budget = per_crit x number of criteria (capped by `budget`)
    note_every: int = 0           # >0: code and notes ranked separately, one note after every `note_every` code items

    def index_key(self):
        return (self.win, self.stride, self.id_weight, self.file_prior, self.path_prior,
                self.lsa_dims if self.lsa else 0)


def v2_cfg(profile: str = "economy", **kw) -> Cfg:
    """Frozen v2 settings (chosen on the 15 dev tasks only, before either holdout set was run).
    Rejected on dev and left off: MaxP/unit blend, note caps, coverage stop, project LSA, morphology, mined lexicon."""
    base = dict(graph=True, fa_stop=True, fa_translated=0.5, path_prior=True, dedup_lines=True,
                per_crit=700, budget=6000)
    if profile == "accurate":
        base.update(per_crit=1400, budget=8000)
    base.update(kw)
    return Cfg(**base)


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


FA_REQUEST_WORDS = set("""نشان داده شوند مشخص بررسی معرفی لحاظ پاسخ کدام چیست وقتی اتفاقی افتد بیفتد دیگر
 آیا کمترین برای همین چنین اینکه""".split())
GENERIC_CALLS = set("""len str int float dict list set tuple print range sorted any all min max sum open isinstance getattr
 setattr hasattr super type enumerate zip map filter get append extend update items keys values join split strip lower
 upper replace startswith endswith format execute executescript fetchone fetchall commit dumps loads read_text write_text
 exists mkdir model_dump model_copy Field field_validator model_validator classmethod staticmethod property ValueError
 Exception HTTPException RuntimeError TypeError KeyError now uuid4 hex time sleep gather create_task JSONResponse Path
 Query Header Counter defaultdict deque search match sub findall compile group warn info error debug lock acquire release
 add pop remove copy encode decode hexdigest sha256 monotonic perf_counter resolve is_file is_dir glob rglob iterdir
 relative_to as_posix with_suffix cancel done result wait_for timeout run wrap wraps partial dataclass field abstractmethod
 asdict asynccontextmanager""".split())
_CALL_RE = re.compile(r"(?<![\w])([A-Za-z_]\w*)\s*\(")

def path_prior(path: str) -> float:
    p = path.lower()
    if p.endswith((".txt", ".log")):
        return 0.4
    if p.startswith(("src/", "lib/", "app/", "packages/")):
        return 1.0
    if p.startswith("tests/"):
        return 0.85
    return 0.6


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
            if cfg.path_prior:
                prior = path_prior(c.path)
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
        # query-side morphology: English vocabulary grouped by stem (the index itself stays unstemmed)
        self.stem_map = defaultdict(set)
        for t in self.idf:
            if t.isascii() and t.isalpha() and len(t) >= 5:
                self.stem_map[J.stem(t)].add(t)
        self.P = None
        if cfg.lsa:
            self._build_lsa(cfg.lsa_dims)
        # symbol table and call sites (python only), built once per project revision
        self.defs = defaultdict(list)      # name -> [Unit]
        self.calls = defaultdict(list)     # name -> [(Unit, line)]
        for u in self.units:
            if u.kind != "code" or not u.path.endswith(".py"):
                continue
            if u.sig is not None:
                m = re.match(r"\s*(?:async\s+def|def|class)\s+(\w+)", u.lines[u.sig])
                if m:
                    self.defs[m.group(1)].append(u)
            for i, l in enumerate(u.lines):
                if i == u.sig or l.lstrip().startswith(("#", "def ", "async def ", "class ", "@")):
                    continue
                for name in set(_CALL_RE.findall(l)):
                    if name not in GENERIC_CALLS:
                        self.calls[name].append((u, i))

    # -- project-trained semantic space: TF-IDF windows x terms -> truncated SVD (LSA). No external model.
    def _build_lsa(self, dims):
        import numpy as np
        from scipy.sparse import csr_matrix
        from sklearn.decomposition import TruncatedSVD
        self.tix = {t: i for i, t in enumerate(self.idf)}
        rows, cols, vals = [], [], []
        for pid, p in enumerate(self.passages):
            for t, f in p.tf.items():
                rows.append(pid)
                cols.append(self.tix[t])
                vals.append((1 + math.log(f)) * self.idf[t])
        X = csr_matrix((vals, (rows, cols)), shape=(len(self.passages), len(self.tix)), dtype=np.float32)
        norms = np.sqrt(X.multiply(X).sum(axis=1)).A1
        norms[norms == 0] = 1
        X = csr_matrix(X.multiply(1 / norms[:, None]))
        svd = TruncatedSVD(n_components=dims, random_state=0)
        P = svd.fit_transform(X)
        P /= np.maximum(np.linalg.norm(P, axis=1, keepdims=True), 1e-9)
        self.P = P.astype(np.float32)
        self.V = svd.components_.astype(np.float32)          # dims x vocab

    def semantic(self, q: dict):
        import numpy as np
        qv = np.zeros(self.V.shape[0], dtype=np.float32)
        for t, w in q.items():
            i = self.tix.get(t)
            if i is not None:
                qv += w * self.V[:, i]
        n = np.linalg.norm(qv)
        return self.P @ (qv / n) if n else np.zeros(len(self.passages), dtype=np.float32)

    def score_fused(self, q: dict, ok, cfg: "Cfg") -> list:
        """BM25 list fused with the LSA cosine; both normalised by their own maximum."""
        import numpy as np
        lex = self.score(q, ok)
        if not cfg.lsa or self.P is None:
            return lex
        sem = self.semantic(q)
        pool = {id(p): (s, p) for s, p in lex[:300]}
        top_bm = lex[0][0] if lex else 1.0
        order = np.argsort(-sem)
        added = 0
        for pid in order:
            if added >= cfg.lsa_pool or sem[pid] <= 0:
                break
            p = self.passages[pid]
            if ok(p.unit) and id(p) not in pool:
                pool[id(p)] = (0.0, p)
                added += 1
        top_sem = float(sem.max()) if len(sem) and sem.max() > 0 else 1.0
        pidx = {id(p): i for i, p in enumerate(self.passages)} if not hasattr(self, "_pidx") else self._pidx
        self._pidx = pidx
        out = []
        for s, p in pool.values():
            cs = max(0.0, float(sem[pidx[id(p)]])) / top_sem
            out.append((((1 - cfg.lsa) * (s / top_bm) + cfg.lsa * cs * p.unit.prior), p))
        out.sort(key=lambda x: -x[0])
        return out

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
    def query(self, text: str, cfg: "Cfg | None" = None) -> dict:
        cfg = cfg or self.cfg                 # query-time options come from the caller, not the cached index
        toks = J.tokenize(text, glossary=cfg.glossary)
        if cfg.fa_stop:
            toks = [t for t in toks if t not in FA_REQUEST_WORDS]
        glossed = {t for t in toks if not t.isascii() and t in J.GLOSSARY}
        q = {}
        for t in set(toks):
            if t in self.idf:
                w = self.idf[t] * (cfg.symbol_boost if t in self.symbols else 1.0)
                if t in glossed:
                    w *= cfg.fa_translated
                q[t] = max(q.get(t, 0), w)
        if self.lexicon:
            for t in set(toks):
                for e in self.lexicon.get(t, []):
                    if e in self.idf and e not in q:
                        q[e] = cfg.lexicon_weight * self.idf[e]
        if cfg.morph:
            for t in list(q):
                if t.isascii() and t.isalpha() and len(t) >= 5:
                    for v in self.stem_map.get(J.stem(t), ()):
                        if v not in q:
                            q[v] = cfg.morph * self.idf[v]
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
    if cfg.per_crit:
        from dataclasses import replace
        cfg = replace(cfg, budget=min(cfg.budget, cfg.per_crit * len(task["criteria"])))
    obj = index.query(task["objective"], cfg)
    crit_q = []
    for c in task["criteria"]:
        q = {t: w * 0.5 for t, w in obj.items()}
        for t, w in index.query(c["text"], cfg).items():
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

    seen_text = set()

    def add_lines(u, new_lines):
        nonlocal used
        new = set(new_lines) - keep.get(u, set())
        if cfg.dedup_lines:
            fresh = {i for i in new if len(u.lines[i].strip()) < 4 or u.lines[i].strip() not in seen_text}
            if new and len(fresh) < 0.2 * len(new):
                return
            new = fresh
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
        seen_text.update(u.lines[i].strip() for i in new)

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

    if cfg.note_every:
        lists = [two_channel(index.score_fused(q, ok, cfg), cfg) for q in crit_q]
    else:
        lists = [index.score_fused(q, ok, cfg)[: cfg.k_per_crit] for q in crit_q]
    if cfg.graph:
        lists = [expand_graph(index, sc, cfg, ok) for sc in lists]
    covered = [set() for _ in crit_q]
    mass = [sum(q.values()) or 1.0 for q in crit_q]

    def note_cover(ci, toks):
        covered[ci] |= {t for t in crit_q[ci] if t in toks}

    def coverage(ci):
        return sum(crit_q[ci][t] for t in covered[ci]) / mass[ci]

    for depth in range(cfg.k_per_crit + 40):
        alive = False
        for ci, sc in enumerate(lists):
            if depth >= len(sc):
                continue
            s, p = sc[depth]
            if s < cfg.theta * sc[0][0]:
                continue
            if coverage(ci) >= cfg.cov_stop:
                continue
            alive = True
            if isinstance(p, tuple):              # graph candidate: (unit, line range)
                add_lines(*p)
                u0, rng = p
                note_cover(ci, set(J.tokenize("\n".join(u0.lines[i] for i in rng))))
                continue
            note_cover(ci, p.tf)
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
            add_lines(u, window_lines(u, p))
        if not alive:
            break

    gaps = []
    for ci, sc in enumerate(lists):
        if not sc:
            gaps.append({"criterion": task["criteria"][ci]["text"], "coverage": 0.0})
    return Pack2(keep, order, used, gaps, {"units": len(order), "lines": sum(len(v) for v in keep.values())})


def two_channel(ranked: list, cfg: Cfg) -> list:
    """Rank code windows and notes separately (each with its own relative cutoff), then interleave them so a flood
    of notes cannot take the code budget and vice versa. Scores are rewritten as a decreasing sequence."""
    code = [x for x in ranked if x[1].unit.kind == "code"]
    notes = [x for x in ranked if x[1].unit.kind == "mem"]
    code = [x for x in code if x[0] >= cfg.theta * code[0][0]][: cfg.k_per_crit] if code else []
    notes = [x for x in notes if x[0] >= cfg.theta * notes[0][0]][: cfg.k_per_crit] if notes else []
    out, ci, ni = [], 0, 0
    while ci < len(code) or ni < len(notes):
        for _ in range(cfg.note_every):
            if ci < len(code):
                out.append(code[ci][1]); ci += 1
        if ni < len(notes):
            out.append(notes[ni][1]); ni += 1
    top = ranked[0][0] if ranked else 1.0
    n = max(1, len(out))
    return [(top * (1 - 0.5 * i / n), p) for i, p in enumerate(out)]   # monotone, stays above theta


def expand_graph(index: Index2, ranked: list, cfg: Cfg, ok) -> list:
    """Go-to-definition and find-usages from the best lexical windows of one criterion.
    Returns the criterion's list with graph candidates (score, (unit, lines)) merged in by score."""
    extra = []
    seen = set()
    for s, p in ranked[: cfg.seed_n]:
        u = p.unit
        if u.kind != "code":
            continue
        # go to definition: functions/classes called inside the seed window
        names = set()
        for l in u.lines[p.a:p.b]:
            names |= {n for n in _CALL_RE.findall(l) if n not in GENERIC_CALLS}
        for n in names:
            targets = [d for d in index.defs.get(n, []) if d is not u and ok(d)]
            if not targets or len(targets) > 3:
                continue
            for d in targets:
                key = (d.id, "def")
                if key in seen:
                    continue
                seen.add(key)
                lo = d.sig or 0
                extra.append((s * cfg.gamma_def, (d, range(lo, min(len(d.lines), lo + cfg.def_lines)))))
        # find usages: call sites of the function this seed window belongs to
        if u.sig is not None:
            m = re.match(r"\s*(?:async\s+def|def|class)\s+(\w+)", u.lines[u.sig])
            name = m.group(1) if m else None
            if name and name not in GENERIC_CALLS and len(index.defs.get(name, [])) <= 3:
                sites = [(c, i) for c, i in index.calls.get(name, []) if c is not u and ok(c)]
                for c, i in sites[: cfg.max_callers]:
                    key = (c.id, i)
                    if key in seen:
                        continue
                    seen.add(key)
                    extra.append((s * cfg.gamma_call, (c, range(max(0, i - cfg.expand), min(len(c.lines), i + cfg.expand + 1)))))
    merged = list(ranked) + extra
    merged.sort(key=lambda x: -x[0])
    return merged[: cfg.k_per_crit + len(extra)]


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
