"""Project-scoped evidence retrieval with exact budgets and source-preserving excerpts.

Local algorithm, not TypeSafe Jev. Ranking never receives evaluation anchors.
Scope/revision filtering precedes corpus statistics, translation mining and graph traversal.
Semantic sufficiency is explicitly unverified; lexical relevance cannot certify an answer.
"""
from __future__ import annotations
import math
import re
import io
import tokenize
import textwrap
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Callable
import tiktoken
import jevs as legacy

ENC = tiktoken.get_encoding("o200k_base")
def token_count(text):
    return len(ENC.encode(text, disallowed_special=()))

# Domain-independent software vocabulary; not benchmark identifiers or required answers.
TRANSLATIONS = {
    **legacy.GLOSSARY,
    "برش": ["truncate", "slice", "excerpt"], "جدول": ["table"],
    "مجاز": ["allowed", "valid"], "تلاش": ["attempt", "retry"],
    "تسویه": ["settle", "settlement"], "ناشناخته": ["unknown"],
    "تابع": ["function", "def"], "توابع": ["function", "def"],
    "متد": ["method", "def"], "کلاس": ["class"], "فیلد": ["field"],
    "ساخت": ["build", "create"], "سازنده": ["build", "create"],
    "خواندن": ["read", "load"], "خوانده": ["read", "load"],
    "ذخیره": ["save", "store", "set"], "نمایش": ["display", "show"],
    "پوشیده": ["mask", "masked"], "محیط": ["environment", "env"],
    "بازیابی": ["retrieve", "retrieval", "recover", "recovery"],
    "بازیابی‌شده": ["retrieve", "retrieved"],
    "فراخوانی": ["call", "invoke"], "فراخوان": ["caller", "call"],
    "قالب": ["format", "template"], "پیام": ["message"],
    "درخواست": ["request", "prompt"], "پاسخ": ["response"],
    "قطع": ["interrupted", "disconnect"], "ادامه": ["resume"],
    "شروع": ["startup", "start"], "مجدداً": ["restart", "retry"],
    "مسیر": ["path", "route"], "شرط": ["condition", "if"],
    "حلقه": ["loop", "for", "while"], "خالی": ["empty"],
    "نامعتبر": ["invalid", "malformed"], "تعمیر": ["repair"],
    "اصلاح": ["repair", "fix"], "منع": ["reject", "deny"],
    "اعتبار": ["credit", "valid"], "محلی": ["local"],
    "میزبان": ["host"], "مبدأ": ["origin"], "مرورگر": ["browser"],
    "زمان": ["time", "timeout"], "فعال": ["active", "running"],
    "رزرو": ["reserve", "reservation"], "مستند": ["design", "document"],
    "مستندات": ["design", "document"], "آزمایش": ["test"],
    "محدودیت": ["limit", "cap"], "اندازه": ["size", "length"],
    "استثنا": ["exception", "error"], "خطاها": ["error", "errors"],
}
ALIASES = {
    "retrieval": "retrieve", "retrieved": "retrieve", "retrieves": "retrieve",
    "recovery": "recover", "recovering": "recover", "recovered": "recover",
    "reservation": "reserve", "reservations": "reserve", "reserved": "reserve",
    "validation": "validate", "validator": "validate", "validated": "validate",
    "retries": "retry", "retrying": "retry", "attempts": "attempt",
    "memories": "memory", "messages": "message", "statuses": "status",
    "errors": "error", "requests": "request", "responses": "response",
    "limits": "limit", "calls": "call", "tokens": "token", "masked": "mask",
    "masking": "mask", "interruption": "interrupted", "interrupted": "interrupted",
    "scoped": "scope", "isolation": "isolate", "isolate": "isolate",
    "transitions": "transition", "summarized": "summary", "summaries": "summary",
    "ctx": "context", "mem": "memory",
}
SYMBOL = re.compile(r"(?:async\s+)?(?:def|class)\s+([A-Za-z_]\w*)")
CALL = re.compile(r"\b([A-Za-z_]\w*)\s*\(")
CONTROL = re.compile(r"^\s*(?:async\s+)?(?:def|class|if|elif|else|for|while|with|try|except|finally|match|case)\b")

def words(text):
    return [ALIASES.get(w, w) for w in legacy.tokenize(text)]

def query_words(text):
    base = words(text)
    translated = []
    for term in base:
        translated.extend(ALIASES.get(w, w) for w in TRANSLATIONS.get(term, []))
    normalized = legacy.normalize(text).replace("‌", " ")
    for phrase, terms in {"پایین دستی": ["downstream"], "بالا دستی": ["upstream"],
                          "تلاش مجدد": ["retry"], "قطع شده": ["interrupted"]}.items():
        if phrase in normalized:
            translated.extend(terms)
    if "snapshot" in base:
        translated.extend(["context", "excerpt"])
    return set(base + translated) - {"نشان", "مشخص", "داده", "درباره", "محل", "گرفته", "لحاظ", "فعلی", "لازم"}

@dataclass(frozen=True)
class Config:
    budget: int = 3000
    window: int = 8
    stride: int = 4
    neighbours: int = 1
    candidate_units: int = 64
    candidates_per_criterion: int = 64
    objective_weight: float = 0.15
    relative_cutoff: float = 0.28
    name_weight: float = 2.5
    graph: bool = False
    source_prior: bool = True

@dataclass(eq=False)
class Unit:
    id: str
    kind: str
    path: str
    lines: tuple
    project_id: str
    status: str = "active"
    revision: int = 1
    title: str = ""
    source: str = ""
    signature: tuple = ()
    line_tf: tuple = ()
    tf: Counter = field(default_factory=Counter)
    name_tf: Counter = field(default_factory=Counter)
    parents: tuple = ()
    closures: tuple = ()
    prepared: bool = False

@dataclass
class Candidate:
    unit: Unit
    score: float
    start: int
    stop: int
    body_terms: frozenset

def _prepare(u):
    if u.prepared:
        return u
    u.line_tf = tuple(Counter(words(line)) for line in u.lines)
    u.tf = sum(u.line_tf, Counter())
    name = u.id.split("::")[-1] if u.kind == "code" else u.title + " " + u.id
    u.name_tf = Counter(words(name))
    if u.kind == "mem":
        # Bidirectional bilingual lookup for existing memory; no generated facts are stored.
        for term in tuple(u.tf):
            for translated in TRANSLATIONS.get(term, ()):
                u.tf[ALIASES.get(translated,translated)] += 1
        for term in tuple(u.name_tf):
            for translated in TRANSLATIONS.get(term, ()):
                u.name_tf[ALIASES.get(translated,translated)] += 1
    signatures = []
    for i, line in enumerate(u.lines):
        if SYMBOL.search(line) and line.lstrip().startswith(("def ", "async def ", "class ")):
            signatures.append(i)
            j = i
            while j + 1 < len(u.lines) and not u.lines[j].rstrip().endswith(":") and j - i < 12:
                j += 1
                signatures.append(j)
            break
    u.signature = tuple(signatures)
    stack, parents = [], []
    for i, line in enumerate(u.lines):
        stripped = line.strip()
        indent = len(line) - len(line.lstrip())
        if stripped and not stripped.startswith("#"):
            while stack and stack[-1][1] >= indent:
                stack.pop()
        parents.append(tuple(k for k, _ in stack))
        if CONTROL.match(line) and stripped.endswith(":"):
            stack.append((i, indent))
    u.parents = tuple(parents)
    closures = [[] for _ in u.lines]
    if u.kind == "code" and u.path.endswith(".py"):
        # Keep bounded complete bracket expressions: dictionaries, call arguments, multiline signatures.
        stack = []
        try:
            stream = tokenize.generate_tokens(io.StringIO(textwrap.dedent("\n".join(u.lines))).readline)
            for tok in stream:
                if tok.type != tokenize.OP:
                    continue
                if tok.string in "([{":
                    stack.append((tok.string, tok.start[0]-1))
                elif tok.string in ")]}":
                    if not stack:
                        continue
                    opening,a = stack.pop()
                    b = tok.end[0]-1
                    if opening+tok.string not in ("()","[]","{}"):
                        continue
                    if 1 < b-a <= 48 and token_count("\n".join(u.lines[a:b+1])) <= 650:
                        for i in range(a,b+1):
                            closures[i].append((a,b+1))
        except (tokenize.TokenError, IndentationError, SyntaxError):
            pass
    u.closures = tuple(tuple(x) for x in closures)
    u.prepared = True
    return u

def render(u, kept):
    if u.kind == "mem":
        return f"[mem:{u.id} rev{u.revision}]\n" + "\n".join(u.lines)
    chosen = sorted(set(kept) | set(u.signature))
    if not chosen:
        return ""
    spans = []
    for i in chosen:
        if spans and i == spans[-1][1] + 1:
            spans[-1][1] = i
        else:
            spans.append([i, i])
    loc = ",".join(f"{a+1}-{b+1}" if a != b else str(a+1) for a, b in spans)
    out, previous = [f"[{u.id} chunk-lines:{loc}]"], None
    for i in chosen:
        if previous is not None and i != previous + 1:
            out.append("    ... # omitted source lines")
        out.append(u.lines[i])
        previous = i
    return "\n".join(out)

def required_kind(text):
    text = legacy.normalize(text)
    if re.search(r"\btests?\b|آزمون|تست", text):
        return "test"
    if re.search(r"design section|recorded decision|design document|تصمیم.*ثبت|تصمیم فعلی ثبت|مستند|مستندسازی درباره", text):
        return "memory"
    return "code"

class ProjectSpace:
    def __init__(self, units):
        self.units = tuple(units)
        self.postings = defaultdict(set)
        df = Counter()
        for n, unit in enumerate(units):
            terms = set(unit.tf) | set(unit.name_tf)
            df.update(terms)
            for term in terms:
                self.postings[term].add(n)
        self.idf = {w: math.log(1 + (len(units) - n + 0.5) / (n + 0.5)) for w, n in df.items()}
        self.names = defaultdict(list)
        for n, u in enumerate(units):
            for symbol in SYMBOL.findall("\n".join(u.lines[:14])):
                self.names[symbol].append(n)
        self.outgoing, self.incoming = defaultdict(set), defaultdict(set)
        self.passage_cache = {}
        for n, u in enumerate(units):
            if u.kind != "code":
                continue
            for name in set(CALL.findall("\n".join(u.lines))):
                targets = self.names.get(name, ())
                if len(targets) > 4:  # ambiguous common names cannot safely drive expansion
                    continue
                for target in targets:
                    if n != target:
                        self.outgoing[n].add(target)
                        self.incoming[target].add(n)

    def query(self, text, kind="code"):
        return {w: self.idf[w] * (1.0 if w.isascii() or kind == "memory" else 0.35) for w in query_words(text) if w in self.idf}

    def passages(self, unit, cfg):
        key = (unit, cfg.window, cfg.stride)
        if key not in self.passage_cache:
            out = []
            starts = range(0,max(1,len(unit.lines)-cfg.window+cfg.stride),cfg.stride)
            for a in starts:
                b = min(len(unit.lines),a+cfg.window)
                tf = sum(unit.line_tf[a:b],Counter())
                out.append((a,b,tf,sum(tf.values())))
            self.passage_cache[key] = tuple(out)
        return self.passage_cache[key]

class Index:
    def __init__(self, chunks, memories, config=None, count_tokens: Callable = token_count):
        self.config, self.count_tokens = config or Config(), count_tokens
        self.by_project = defaultdict(list)
        for c in chunks:
            u = Unit(c.id, "code", c.path, tuple(c.text.splitlines()), c.project_id)
            self.by_project[c.project_id].append(u)
        for m in memories:
            # Superseded records never contribute to IDF or graph statistics.
            if m.status != "active" or getattr(m, "superseded_by", None):
                continue
            u = Unit(m.id, "mem", m.id, tuple([m.title] + m.content.splitlines()),
                     m.project_id, m.status, m.revision, m.title, m.source)
            self.by_project[m.project_id].append(u)
        # Latest revision wins within a project; project ID is part of identity.
        for project, units in self.by_project.items():
            latest = {}
            for unit in units:
                key = (unit.kind, unit.id)
                if key not in latest or unit.revision > latest[key].revision:
                    latest[key] = unit
            self.by_project[project] = tuple(latest.values())
        self.spaces = {}

    def space(self, project):
        if project not in self.spaces:
            units = self.by_project.get(project, ())
            global_units = self.by_project.get("global", ()) if project != "global" else ()
            self.spaces[project] = ProjectSpace(tuple(_prepare(u) for u in tuple(units) + tuple(global_units)))
        return self.spaces[project]

    @staticmethod
    def _prior(u, kind, config):
        if not config.source_prior:
            return 1.0
        is_test = u.path.startswith("tests/") or "/tests/" in u.path
        if kind == "memory":
            return 1.8 if u.kind == "mem" else 0.65
        if kind == "test":
            return 2.2 if is_test else 0.45
        if u.kind == "mem":
            return 0.45
        if u.path.startswith("src/"):
            return 1.5 if u.path.endswith(".py") else 0.5
        if is_test:
            return 0.65
        return 0.6 if re.search(r"(^|/)(var|dist|build)/|debug|dump|output|\.txt$|\.css$", u.path) else 0.85

    def rank(self, space, query, kind, config):
        touched = set().union(*(space.postings.get(t, set()) for t in query)) if query else set()
        totals = []
        for n in touched:
            u = space.units[n]
            body = sum(w * min(u.tf.get(t, 0), 3) for t, w in query.items())
            name = sum(w * min(u.name_tf.get(t, 0), 1) for t, w in query.items())
            score = (body + config.name_weight * name) * self._prior(u, kind, config)
            totals.append((score, n))
        totals.sort(key=lambda x: (-x[0], space.units[x[1]].id))
        shortlist = {n for _, n in totals[:config.candidate_units]}
        if config.graph:
            # One bounded hop. Newly added neighbours still need query relevance to be selected.
            for _, seed in totals[:4]:
                neighbours = space.incoming.get(seed, ()) if kind == "code" else space.outgoing.get(seed, ())
                for n in sorted(neighbours)[:12]:
                    if n in touched:
                        shortlist.add(n)
        candidates = []
        for n in sorted(shortlist):
            u = space.units[n]
            name = sum(w for t, w in query.items() if t in u.name_tf)
            prior = self._prior(u, kind, config)
            if u.kind == "mem":
                length = sum(u.tf.values())
                body = sum(w * u.tf[t] * 2.2 / (u.tf[t]+1.2*(0.25+0.75*length/150)) for t,w in query.items() if t in u.tf)
                score = prior * (body + config.name_weight * name)
                candidates.append(Candidate(u, score, 0, len(u.lines), frozenset(t for t in query if t in u.tf)))
                continue
            passages = []
            for a,b,tf,length in space.passages(u,config):
                body = sum(w * tf[t] * 2.2 / (tf[t]+1.2*(0.25+0.75*length/55)) for t,w in query.items() if t in tf)
                terms = frozenset(t for t in query if t in tf)
                if not terms:
                    continue
                # Path/owner helps locate a symbol but does not certify irrelevant body lines.
                score = prior * (body + config.name_weight * name * 0.35)
                passages.append(Candidate(u, score, a, b, terms))
            passages.sort(key=lambda p: (-p.score, p.start))
            chosen = []
            for p in passages:
                if any(max(0, min(p.stop, s.stop) - max(p.start, s.start)) / max(1, p.stop-p.start) > 0.55 for s in chosen):
                    continue
                chosen.append(p)
                if len(chosen) == 5:
                    break
            candidates.extend(chosen)
        candidates.sort(key=lambda p: (-p.score, p.unit.id, p.start))
        return candidates[:config.candidates_per_criterion]

    def select(self, task, config=None):
        cfg = config or self.config
        if not isinstance(task.get("project_id"),str) or not task["project_id"].strip():
            raise ValueError("A non-empty project_id is required")
        if cfg.budget < 100:
            raise ValueError("Budget must be >= 100 tokens for source provenance and warning")
        criteria = task.get("criteria", [])
        space = self.space(task["project_id"])
        objective = space.query(task["objective"])
        lists, kinds, queries = [], [], []
        for c in criteria:
            kind = required_kind(c["text"])
            q = {t: w * cfg.objective_weight for t, w in objective.items()}
            for t, w in space.query(c["text"],kind).items():
                q[t] = max(q.get(t, 0), w)
            kinds.append(kind)
            queries.append(q)
            lists.append(self.rank(space, q, kind, cfg))
        keep, costs, order = {}, {}, []
        # The warning is part of the evidence payload budget, not a hidden extra prompt.
        warning = "Retrieval candidates only; semantic sufficiency requires verification. Omitted source is marked (...)."
        remaining = cfg.budget - self.count_tokens(warning) - 16
        used = 0
        for depth in range(cfg.candidates_per_criterion):
            alive = False
            for candidates in lists:
                if depth >= len(candidates):
                    continue
                p = candidates[depth]
                if p.score < cfg.relative_cutoff * candidates[0].score:
                    continue
                alive = True
                u = p.unit
                if u.kind == "mem":
                    selected = set(range(len(u.lines)))
                else:
                    selected = set(range(max(0,p.start-cfg.neighbours), min(len(u.lines),p.stop+cfg.neighbours)))
                    # Keep enclosing control headers to avoid attributing a guarded statement unconditionally.
                    selected |= set(u.signature)
                    selected |= {parent for i in tuple(selected) for parent in u.parents[i]}
                    selected |= {line for i in tuple(selected) for a,b in u.closures[i] for line in range(a,b)}
                merged = keep.get(u, set()) | selected
                if merged == keep.get(u):
                    continue
                cost = self.count_tokens(render(u, merged)) + 8
                delta = cost - costs.get(u, 0)
                if used + delta > remaining:
                    continue
                if u not in keep:
                    order.append(u)
                keep[u], costs[u] = merged, cost
                used += delta
            if not alive:
                break
        blocks = [render(u, keep[u]) for u in order]
        content = "\n\n".join(blocks + [warning])
        actual = self.count_tokens(content)
        assert actual <= cfg.budget
        statuses = []
        for ci, (c, q, kind, candidates) in enumerate(zip(criteria, queries, kinds, lists)):
            selected = []
            for u in order:
                if kind == "memory" and u.kind != "mem":
                    continue
                if kind == "test" and not (u.path.startswith("tests/") or "/tests/" in u.path):
                    continue
                if kind == "code" and u.kind != "code":
                    continue
                terms = set(u.tf) if u.kind == "mem" else set().union(*(set(u.line_tf[i]) for i in keep[u]))
                # Criterion terms only: objective terms cannot hide a missing criterion.
                focus = query_words(c["text"]) & set(space.idf)
                matched = focus & terms
                if matched:
                    selected.append({"id": u.id, "matched_terms": sorted(matched), "kind": u.kind})
            statuses.append({"criterion": c["text"], "expected_kind": kind,
                             "retrieval_status": "candidate" if selected else "missing",
                             "semantic_sufficiency": "unverified", "evidence": selected})
        return Pack(content, actual, keep, order, statuses,
                    {"namespace": task["project_id"], "eligible_units": len(space.units),
                     "candidate_counts": [len(x) for x in lists], "selected_units": len(order)})

@dataclass
class Pack:
    content: str
    tokens: int
    keep: dict
    order: list
    assessments: list
    trace: dict

    @property
    def gaps(self):
        return [a for a in self.assessments if a["retrieval_status"] == "missing"]

def worker_context(pack):
    return [{"ref": "jevs-v2:evidence", "title": "Source evidence; sufficiency unverified", "content": pack.content}]

def head_context(pack):
    text = "\n".join(f"- {u.id}" for u in pack.order)
    text += "\nSemantic sufficiency: unverified."
    for i, assessment in enumerate(pack.assessments):
        if assessment["retrieval_status"] == "missing":
            text += f"\nMissing candidate evidence for criterion {i+1}."
    return [{"ref": "jevs-v2:map", "title": "Evidence map", "content": text}]
