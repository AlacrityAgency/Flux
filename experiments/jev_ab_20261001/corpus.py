"""Corpus for the JEVS experiment: semantic chunks of the real Flux folder + memory records.

Nothing here calls a model. Chunks are function/class/section sized so that a "needed evidence"
unit has a stable id (path::qualname) that can be checked for presence in any assembled context.
"""
from __future__ import annotations

import ast
import random
import re
from dataclasses import dataclass, field
from pathlib import Path

FLUX_ROOT = Path(__file__).resolve().parents[2]

# Same filters as flux.api.app.build_project_context (kept in sync by import in run_experiment).
IGNORED_DIRS = {".git", ".hg", ".svn", ".venv", "venv", "node_modules", "__pycache__", "build", "dist", "coverage"}
TEXT_EXT = {".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".html", ".css", ".scss", ".json", ".yaml", ".yml",
            ".toml", ".ini", ".md", ".txt", ".sh", ".ps1", ".bat", ".java", ".go", ".rs", ".cs", ".cpp", ".h", ".sql"}
SENSITIVE = {".env", ".env.local", ".env.production", "id_rsa", "id_ed25519", "credentials.json", "service-account.json"}
SPLIT_FN_LINES = 40     # a function longer than this is split along its nested defs
WINDOW_LINES = 60       # non-python files are cut into fixed windows


@dataclass
class Chunk:
    id: str
    path: str
    text: str
    kind: str = "code"          # code | doc | text
    project_id: str = "flux"
    lines: tuple = field(default_factory=tuple)   # stripped non-trivial lines, for presence checks

    def __post_init__(self):
        self.lines = tuple(l.strip() for l in self.text.splitlines() if len(l.strip()) >= 3)


@dataclass
class Memory:
    id: str
    project_id: str
    title: str
    content: str
    status: str = "active"      # active | obsolete   (JEVS metadata; the current Flux table has no such column)
    revision: int = 1
    superseded_by: str | None = None
    source: str = "synthetic"


def project_files(root: Path = FLUX_ROOT) -> list[Path]:
    out = []
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        rel = p.relative_to(root)
        if any(part.startswith(".") or part.lower() in IGNORED_DIRS for part in rel.parts[:-1]):
            continue
        if p.name.lower() in SENSITIVE or p.suffix.lower() not in TEXT_EXT:
            continue
        if "experiments" in rel.parts:      # never index the experiment itself
            continue
        out.append(p)
    return out


def _py_chunks(rel: str, src: str) -> list[Chunk]:
    lines = src.splitlines()
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return _window_chunks(rel, src)
    taken: list[tuple[int, int, str]] = []      # (start, end, id) 1-based inclusive, child spans

    def span(n):
        start = min([n.lineno] + [d.lineno for d in getattr(n, "decorator_list", [])])
        return start, n.end_lineno

    chunks: dict[str, list[int]] = {}

    def visit(node, prefix, parent_id):
        s, e = span(node)
        cid = f"{rel}::{prefix}"
        kids = [c for c in node.body if isinstance(c, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
        split = isinstance(node, ast.ClassDef) or (e - s + 1 > SPLIT_FN_LINES and kids)
        own = set(range(s, e + 1))
        if split:
            for k in kids:
                ks, ke = span(k)
                own -= set(range(ks, ke + 1))
                visit(k, f"{prefix}.{k.name}", cid)
        chunks[cid] = sorted(own)

    top_lines = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            s, e = span(node)
            top_lines |= set(range(s, e + 1))
            visit(node, node.name, None)
    module_lines = [i for i in range(1, len(lines) + 1) if i not in top_lines]
    out = []
    mod_text = "\n".join(lines[i - 1] for i in module_lines).strip()
    if mod_text:
        out.append(Chunk(f"{rel}::<module>", rel, mod_text))
    for cid, idxs in chunks.items():
        text = "\n".join(lines[i - 1] for i in idxs).strip("\n")
        if text.strip():
            out.append(Chunk(cid, rel, text))
    return out


def _window_chunks(rel: str, src: str, kind: str = "text") -> list[Chunk]:
    ls = src.splitlines()
    return [Chunk(f"{rel}@L{i + 1}", rel, "\n".join(ls[i:i + WINDOW_LINES]), kind=kind)
            for i in range(0, len(ls), WINDOW_LINES) if "\n".join(ls[i:i + WINDOW_LINES]).strip()]


def _md_sections(rel: str, src: str) -> list[tuple[str, str]]:
    parts, cur_title, cur = [], "intro", []
    for line in src.splitlines():
        if re.match(r"^#{1,3}\s", line):
            if "".join(cur).strip():
                parts.append((cur_title, "\n".join(cur)))
            cur_title, cur = line.lstrip("# ").strip(), [line]
        else:
            cur.append(line)
    if "".join(cur).strip():
        parts.append((cur_title, "\n".join(cur)))
    return parts


def load_code_corpus(root: Path = FLUX_ROOT, include_docs: bool = False) -> list[Chunk]:
    """Chunks of the real Flux folder. docs/*.md live in the memory store, not here (see load_memories)."""
    chunks = []
    for p in project_files(root):
        rel = p.relative_to(root).as_posix()
        if p.stat().st_size > 400_000:
            continue
        if rel.startswith("docs/") and not include_docs:
            continue
        try:
            src = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if "\x00" in src:
            continue
        if p.suffix == ".py":
            chunks += _py_chunks(rel, src)
        elif p.suffix == ".md":
            for title, body in _md_sections(rel, src):
                chunks.append(Chunk(f"{rel}#{title}", rel, body, kind="doc"))
        else:
            chunks += _window_chunks(rel, src)
    return chunks


# ---------------------------------------------------------------- memories
def load_flux_doc_memories(root: Path = FLUX_ROOT) -> list[Memory]:
    """Real project knowledge: each section of the design docs becomes one memory record."""
    mems = []
    for name in ("architecture.fa.md", "mvp-design.fa.md", "projects-and-installation.fa.md"):
        p = root / "docs" / name
        if not p.exists():
            continue
        for title, body in _md_sections(name, p.read_text(encoding="utf-8")):
            body = body.strip()
            if len(body) < 80:
                continue
            body = body[:1800]
            mems.append(Memory(id=f"mem_fx_{name.split('.')[0]}#{title}", project_id="flux", title=title,
                               content=body, source=f"docs/{name}"))
    return mems


# Hand-written decision records. Facts match the code in this repo (checked when the tasks were written).
DECISIONS = [
    Memory("dec_ctx_current", "flux", "تصمیم فعلی: Context پروژه در هر تماس",
           "reference_context در تابع FluxEngine._context به همهٔ تماس‌های Head، کارگرها و بازبین اضافه می‌شود. "
           "build_head_prompt نیز فیلد context را در درخواست Head می‌گذارد، پس Head دو نسخه می‌گیرد. "
           "اصلاح پیشنهادی: حذف فیلد context از build_head_prompt.", revision=3),
    Memory("dec_ctx_old", "flux", "تصمیم قدیمی: Context فقط برای Head",
           "Context پروژه فقط داخل build_head_prompt قرار می‌گیرد و کارگرها و بازبین هیچ context مرجعی نمی‌گیرند.",
           status="obsolete", revision=1, superseded_by="dec_ctx_current"),
    Memory("dec_mem_current", "flux", "تصمیم فعلی: بازیابی حافظه",
           "Workspace.retrieve حافظه‌ها را با شمارش واژه‌های مشترک رتبه‌بندی می‌کند، حداکثر پنج مورد و سقف ۶۰۰۰ نویسه. "
           "هنوز فیلتر project_id ندارد و ستون project_id در جدول memories وجود ندارد.", revision=2),
    Memory("dec_mem_old", "flux", "تصمیم قدیمی: حافظه سراسری",
           "حافظه‌ها برای همهٔ پروژه‌ها مشترک است و جداسازی بر اساس پروژه لازم نیست؛ retrieve فقط عنوان را بررسی می‌کند.",
           status="obsolete", revision=1, superseded_by="dec_mem_current"),
    Memory("dec_retry_current", "flux", "تصمیم فعلی: سقف تلاش مجدد",
           "FluxEngine._call برای Head حداکثر دو ارسال و برای سایر نقش‌ها حداکثر سه ارسال انجام می‌دهد؛ فقط خطای گذرا "
           "(ProviderError.is_transient) دوباره ارسال می‌شود و هر run حداکثر بیست تماس دارد.", revision=2),
    Memory("dec_retry_old", "flux", "تصمیم قدیمی: تلاش مجدد نامحدود",
           "خطاهای provider تا موفقیت دوباره ارسال می‌شوند و سقف تماس برای run وجود ندارد.",
           status="obsolete", revision=1, superseded_by="dec_retry_current"),
]

_NOUNS = ["invoice", "shipment", "customer", "warehouse", "ledger entry", "campaign", "ticket", "booking", "payroll",
          "supplier", "route", "inventory", "subscription", "refund", "dashboard"]
_TECH = ["context", "memory", "token", "budget", "retrieve", "project", "run", "agent", "retry", "limit", "state",
         "snapshot", "criteria", "output", "review", "cost", "store", "validate", "queue", "cache"]
_TPL = [
    "The {n} module keeps a {t} per {t2}; changing the {t3} requires a {t4} check before release.",
    "Decision: {n} {t} is rebuilt nightly, the {t2} limit stays at {k} and the {t3} is validated on every {t4}.",
    "Note on {n}: the {t} for each {t2} is stored once; {t3} and {t4} are handled by the {n} service.",
    "For {n} the team agreed a {t} budget of {k} units, a retry limit of 3 and a separate {t2} review.",
]
_FA = ["یادداشت دربارهٔ ماژول {n}: {t} هر {t2} جدا ذخیره می‌شود و {t3} پیش از انتشار بررسی می‌شود.",
       "تصمیم تیم برای {n}: سقف {t} برابر {k} است و {t2} هر شب بازسازی می‌شود."]


def synth_memories(project_id: str, count: int, seed: int, relevant_topics: bool = False) -> list[Memory]:
    """Generated notes for another (or the same) project. They share generic technical vocabulary with Flux
    on purpose: that is what makes unscoped lexical retrieval leak."""
    rnd = random.Random(f"{project_id}:{seed}")
    out = []
    for i in range(count):
        n = rnd.choice(_NOUNS)
        pick = lambda: rnd.choice(_TECH)
        tpl = rnd.choice(_TPL + (_FA if rnd.random() < 0.25 else []))
        body = " ".join(tpl.format(n=n, t=pick(), t2=pick(), t3=pick(), t4=pick(), k=rnd.randint(2, 900))
                        for _ in range(rnd.randint(2, 6)))
        out.append(Memory(id=f"mem_{project_id}_{seed}_{i}", project_id=project_id, title=f"{n} note {i}",
                          content=body, source="synthetic"))
    return out


def build_memory_store(n_other_projects: int, mems_per_project: int, seed: int,
                       flux_noise: int | None = None) -> list[Memory]:
    store = load_flux_doc_memories() + list(DECISIONS)
    store += synth_memories("flux", flux_noise if flux_noise is not None else mems_per_project, seed)   # same-project noise
    for k in range(n_other_projects):
        store += synth_memories(f"other{k}", mems_per_project, seed)
    return store


if __name__ == "__main__":
    ch = load_code_corpus()
    print(len(ch), "chunks;", sum(len(c.text) for c in ch), "chars")
    import sys
    pat = sys.argv[1] if len(sys.argv) > 1 else ""
    for c in ch:
        if pat in c.id:
            print(f"{len(c.text):6d}  {c.id}")
    mem = load_flux_doc_memories()
    print(len(mem), "doc memories")
    if "--mem" in sys.argv:
        for m in mem:
            print(f"{len(m.content):5d}  {m.id}")
