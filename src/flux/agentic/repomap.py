"""Smart Repository Mapping via Tree-sitter & AST (Aider-style RepoMap).

Parses source files into classes, method/function signatures, and import edges using
Tree-sitter grammars (with Python AST enrichment and regex fallback), builds the
inter-file dependency graph, ranks files by PageRank centrality + prompt relevance,
and renders a compact structural map within a strict character/token budget.
"""
from __future__ import annotations

import ast
import importlib
import os
import re
from collections import defaultdict
from pathlib import Path, PurePosixPath

SKIP_DIRS = {
    ".git", ".hg", ".svn", "__pycache__", "node_modules", ".venv", "venv", "env",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", ".tox", "dist", "build", "target",
    ".next", ".nuxt", ".turbo", "coverage", "htmlcov", "var", "tmp", "work",
    ".flux-worktree", ".idea", ".vscode", "backups", "vendor",
}

EXT_TO_LANG = {
    ".py": ("python", "language"),
    ".pyi": ("python", "language"),
    ".js": ("javascript", "language"),
    ".mjs": ("javascript", "language"),
    ".cjs": ("javascript", "language"),
    ".jsx": ("javascript", "language"),
    ".ts": ("typescript", "language_typescript"),
    ".tsx": ("typescript", "language_tsx"),
    ".go": ("go", "language"),
    ".rs": ("rust", "language"),
    ".java": ("java", "language"),
    ".c": ("c", "language"),
    ".h": ("c", "language"),
    ".cpp": ("cpp", "language"),
    ".cc": ("cpp", "language"),
    ".hpp": ("cpp", "language"),
    ".cs": ("c_sharp", "language"),
    ".rb": ("ruby", "language"),
    ".php": ("php", "language_php"),
    ".kt": ("kotlin", "language"),
    ".swift": ("swift", "language"),
    ".sh": ("bash", "language"),
}

CLASS_NODES = {
    "class_definition", "class_declaration", "interface_declaration",
    "struct_item", "trait_item", "enum_item", "type_alias_declaration",
    "struct_specifier", "class_specifier", "module", "object_declaration",
}
FUNC_NODES = {
    "function_definition", "function_declaration", "method_definition",
    "method_declaration", "function_item", "func_literal", "method",
}
IMPORT_NODES = {
    "import_statement", "import_from_statement", "import_declaration",
    "use_declaration", "preproc_include", "namespace_use_declaration",
}

_PARSERS: dict[tuple[str, str], object | None] = {}
_IDENTIFIER_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]{2,}")


def _get_ts_parser(mod_short: str, fn_name: str):
    key = (mod_short, fn_name)
    if key in _PARSERS:
        return _PARSERS[key]
    try:
        import tree_sitter
        mod = importlib.import_module(f"tree_sitter_{mod_short}")
        fn = getattr(mod, fn_name, None) or getattr(mod, "language", None)
        if fn is None:
            fns = [k for k in dir(mod) if k.startswith("language")]
            fn = getattr(mod, fns[0]) if fns else None
        parser = tree_sitter.Parser(tree_sitter.Language(fn())) if fn else None
    except Exception:
        parser = None
    _PARSERS[key] = parser
    return parser


def _split_ident(token: str) -> set[str]:
    parts = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", token).replace("_", " ").replace("-", " ").lower().split()
    return {token.lower(), *(p for p in parts if len(p) >= 3)}


def _header_line(source_bytes: bytes, node) -> str:
    raw = source_bytes[node.start_byte:min(node.end_byte, node.start_byte + 260)].decode("utf-8", errors="replace")
    first = raw.splitlines()[0].strip() if raw else ""
    for sep in ("{", " where "):
        if sep in first and not first.startswith("#"):
            first = first.split(sep, 1)[0].strip()
    if first.endswith(":"):
        first = first[:-1].strip()
    return re.sub(r"\s+", " ", first)[:140]


def _extract_node_name(source_bytes: bytes, node) -> str:
    name_node = node.child_by_field_name("name")
    if name_node is not None:
        return source_bytes[name_node.start_byte:name_node.end_byte].decode("utf-8", errors="replace").strip()
    for ch in node.children:
        if ch.type in {"identifier", "type_identifier", "constant"}:
            return source_bytes[ch.start_byte:ch.end_byte].decode("utf-8", errors="replace").strip()
    return ""


def _parse_python_ast(text: str) -> dict | None:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return None
    classes, functions, imports, symbols = [], [], [], set()

    def fmt_args(args: ast.arguments) -> str:
        items = []
        plain = list(args.posonlyargs) + list(args.args)
        defaults_offset = len(plain) - len(args.defaults)
        for idx, arg in enumerate(plain):
            piece = arg.arg
            if arg.annotation:
                try:
                    piece += f": {ast.unparse(arg.annotation)}"
                except Exception:
                    pass
            if idx >= defaults_offset:
                piece += "=..."
            items.append(piece)
        if args.vararg:
            items.append(f"*{args.vararg.arg}")
        for kw in args.kwonlyargs:
            items.append(kw.arg)
        if args.kwarg:
            items.append(f"**{args.kwarg.arg}")
        joined = ", ".join(items)
        return joined if len(joined) <= 90 else joined[:87] + "..."

    def fmt_func(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
        prefix = "async def " if isinstance(fn, ast.AsyncFunctionDef) else "def "
        ret = ""
        if fn.returns:
            try:
                ret = f" -> {ast.unparse(fn.returns)}"
            except Exception:
                pass
        return f"{prefix}{fn.name}({fmt_args(fn.args)}){ret}"

    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            base = ("." * node.level) + (node.module or "")
            imports.append(base or ".")
            for alias in node.names:
                if alias.name != "*":
                    imports.append(f"{base}.{alias.name}".strip("."))
        elif isinstance(node, ast.ClassDef):
            symbols.add(node.name)
            bases = []
            for b in node.bases[:3]:
                try:
                    bases.append(ast.unparse(b))
                except Exception:
                    pass
            base_str = f"({', '.join(bases)})" if bases else ""
            methods = []
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    symbols.add(item.name)
                    methods.append(fmt_func(item))
            classes.append({"name": node.name, "signature": f"class {node.name}{base_str}", "methods": methods[:16]})
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            symbols.add(node.name)
            functions.append({"name": node.name, "signature": fmt_func(node)})
    return {"classes": classes, "functions": functions, "imports": imports, "symbols": symbols}


def _parse_with_treesitter(source_bytes: bytes, parser) -> dict:
    tree = parser.parse(source_bytes)
    classes, functions, imports, symbols = [], [], [], set()

    def walk_class_body(cnode) -> list[str]:
        methods = []
        stack = list(reversed(cnode.children))
        while stack and len(methods) < 16:
            cur = stack.pop()
            if cur.type in FUNC_NODES:
                mname = _extract_node_name(source_bytes, cur)
                if mname:
                    symbols.add(mname)
                methods.append(_header_line(source_bytes, cur))
            elif cur.type not in CLASS_NODES:
                stack.extend(reversed(cur.children))
        return methods

    for child in tree.root_node.children:
        ctype = child.type
        if ctype in IMPORT_NODES:
            raw = source_bytes[child.start_byte:min(child.end_byte, child.start_byte + 200)].decode("utf-8", errors="replace")
            imports.append(re.sub(r"\s+", " ", raw).strip())
            continue
        # Handle export wrappers in JS/TS (`export class ...`, `export function ...`)
        target = child
        if ctype in {"export_statement", "decorated_definition"}:
            for sub in child.children:
                if sub.type in CLASS_NODES or sub.type in FUNC_NODES:
                    target = sub
                    break
        if target.type in CLASS_NODES and target.type != "module":
            cname = _extract_node_name(source_bytes, target)
            if cname:
                symbols.add(cname)
            classes.append({
                "name": cname or "anonymous",
                "signature": _header_line(source_bytes, target),
                "methods": walk_class_body(target),
            })
        elif target.type in FUNC_NODES:
            fname = _extract_node_name(source_bytes, target)
            if fname:
                symbols.add(fname)
            functions.append({"name": fname or "fn", "signature": _header_line(source_bytes, target)})
    return {"classes": classes, "functions": functions, "imports": imports, "symbols": symbols}


def _parse_regex_fallback(text: str) -> dict:
    classes, functions, imports, symbols = [], [], [], set()
    for line in text.splitlines():
        s = line.strip()
        if m := re.match(r"^(?:export\s+)?(?:abstract\s+)?(class|interface|struct|trait|enum)\s+([A-Za-z_]\w*)", s):
            symbols.add(m.group(2))
            classes.append({"name": m.group(2), "signature": s.rstrip("{:").strip()[:120], "methods": []})
        elif m := re.match(r"^(?:export\s+)?(?:async\s+)?(?:def|function|fn|func)\s+([A-Za-z_]\w*)\s*\([^)]*\)", s):
            symbols.add(m.group(1))
            functions.append({"name": m.group(1), "signature": s.rstrip("{:").strip()[:120]})
        elif s.startswith(("import ", "from ", "use ", "#include ")):
            imports.append(s[:140])
    return {"classes": classes, "functions": functions, "imports": imports, "symbols": symbols}


class RepoMapper:
    """Incremental Tree-sitter + AST repository mapper with dependency PageRank."""

    def __init__(self):
        self._cache: dict[str, tuple[int, int, dict]] = {}

    def _scan_files(self, root: Path, max_files: int = 800) -> list[Path]:
        found = []
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".venv"))
            for fname in sorted(filenames):
                ext = Path(fname).suffix.lower()
                if ext not in EXT_TO_LANG:
                    continue
                fpath = Path(dirpath) / fname
                try:
                    st = fpath.stat()
                except OSError:
                    continue
                if 0 < st.st_size <= 350_000:
                    found.append(fpath)
                    if len(found) >= max_files:
                        return found
        return found

    def _parse_file(self, fpath: Path, rel: str) -> dict:
        st = fpath.stat()
        key = str(fpath)
        cached = self._cache.get(key)
        if cached and cached[0] == st.st_mtime_ns and cached[1] == st.st_size:
            return cached[2]
        raw = fpath.read_bytes()
        text = raw.decode("utf-8", errors="replace")
        ext = fpath.suffix.lower()
        mod_short, fn_name = EXT_TO_LANG[ext]
        parser = _get_ts_parser(mod_short, fn_name)
        engine = "regex"
        info = None
        if parser is not None:
            info = _parse_with_treesitter(raw, parser)
            engine = "tree-sitter"
        if ext in {".py", ".pyi"}:
            ast_info = _parse_python_ast(text)
            if ast_info is not None:
                # Merge Tree-sitter parse confirmation with rich Python type-annotated signatures
                info = ast_info
                engine = "tree-sitter+ast" if parser is not None else "ast"
        if info is None:
            info = _parse_regex_fallback(text)
        record = {
            "path": rel,
            "size_chars": len(text),
            "lines": text.count("\n") + 1,
            "engine": engine,
            **info,
        }
        self._cache[key] = (st.st_mtime_ns, st.st_size, record)
        return record

    @staticmethod
    def _resolve_edges(records: dict[str, dict]) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
        """Map raw import strings to intra-repository file paths."""
        module_index: dict[str, str] = {}
        stem_index: dict[str, list[str]] = defaultdict(list)
        for rel in records:
            p = PurePosixPath(rel)
            no_ext = str(p.with_suffix(""))
            dotted = no_ext.replace("/", ".")
            module_index[dotted] = rel
            if dotted.startswith("src."):
                module_index[dotted[4:]] = rel
            if p.stem == "__init__":
                pkg = str(p.parent).replace("/", ".")
                module_index[pkg] = rel
                if pkg.startswith("src."):
                    module_index[pkg[4:]] = rel
            stem_index[p.stem.lower()].append(rel)

        outgoing: dict[str, set[str]] = {r: set() for r in records}
        incoming: dict[str, set[str]] = {r: set() for r in records}
        for src, rec in records.items():
            for imp in rec["imports"]:
                cleaned = re.sub(r"""['";()]""", " ", imp)
                tokens = [t.strip(".") for t in cleaned.split() if "/" in t or "." in t or t.isidentifier()]
                matched = None
                for tok in tokens:
                    cand_dot = tok.lstrip("./").replace("/", ".")
                    if cand_dot in module_index and module_index[cand_dot] != src:
                        matched = module_index[cand_dot]
                        break
                    last = cand_dot.rsplit(".", 1)[-1].lower()
                    if last in stem_index and len(stem_index[last]) == 1 and stem_index[last][0] != src:
                        matched = stem_index[last][0]
                        break
                if matched:
                    outgoing[src].add(matched)
                    incoming[matched].add(src)
        return outgoing, incoming

    @staticmethod
    def _pagerank(nodes: list[str], outgoing: dict[str, set[str]], iterations: int = 12, damping: float = 0.85) -> dict[str, float]:
        n = len(nodes)
        if n == 0:
            return {}
        ranks = {u: 1.0 / n for u in nodes}
        for _ in range(iterations):
            nxt = {u: (1.0 - damping) / n for u in nodes}
            sink_mass = sum(ranks[u] for u in nodes if not outgoing[u])
            for u in nodes:
                nxt[u] += damping * sink_mass / n
                outs = outgoing[u]
                if outs:
                    share = damping * ranks[u] / len(outs)
                    for v in outs:
                        nxt[v] += share
            ranks = nxt
        return ranks

    def build(self, cwd: str | Path, prompt: str = "", budget_chars: int = 6000, focus_files: list[str] | None = None) -> dict:
        root = Path(cwd).resolve()
        if not root.is_dir():
            return {"map": "", "files_scanned": 0, "files_selected": 0, "raw_tokens_est": 0,
                    "map_tokens_est": 0, "token_reduction_pct": 0.0, "engine": "none", "dependencies": {}}
        files = self._scan_files(root)
        if not files:
            return {"map": "", "files_scanned": 0, "files_selected": 0, "raw_tokens_est": 0,
                    "map_tokens_est": 0, "token_reduction_pct": 0.0, "engine": "tree-sitter", "dependencies": {}}

        records: dict[str, dict] = {}
        raw_chars = 0
        engines = set()
        for fpath in files:
            rel = fpath.relative_to(root).as_posix()
            rec = self._parse_file(fpath, rel)
            records[rel] = rec
            raw_chars += rec["size_chars"]
            engines.add(rec["engine"])

        outgoing, incoming = self._resolve_edges(records)
        pr = self._pagerank(list(records), outgoing)

        prompt_terms = set()
        for tok in _IDENTIFIER_RE.findall(prompt or ""):
            prompt_terms |= _split_ident(tok)
        focus_set = {PurePosixPath(f).as_posix() for f in (focus_files or [])}

        scored = []
        for rel, rec in records.items():
            score = pr.get(rel, 0.0) * 10.0 + len(incoming[rel]) * 0.6 + len(outgoing[rel]) * 0.15
            if rel in focus_set or any(rel.endswith(f) for f in focus_set):
                score += 12.0
            if prompt_terms:
                path_terms = _split_ident(PurePosixPath(rel).stem) | {p.lower() for p in PurePosixPath(rel).parts}
                sym_terms = set()
                for s in rec["symbols"]:
                    sym_terms |= _split_ident(s)
                overlap_path = len(prompt_terms & path_terms)
                overlap_sym = len(prompt_terms & sym_terms)
                score += overlap_path * 4.0 + overlap_sym * 2.5
            # Slight penalty for test files unless prompt mentions test
            if ("test" in rel.lower()) and ("test" not in prompt_terms and "تست" not in (prompt or "")):
                score *= 0.45
            scored.append((score, rel, rec))

        scored.sort(key=lambda item: (-item[0], item[1]))

        lines = ["### Repository Structural Map (Tree-sitter + AST)"]
        used = len(lines[0]) + 1
        selected = []
        for _, rel, rec in scored:
            block = [f"\n{rel}:"]
            deps = sorted(outgoing[rel])[:5]
            if deps:
                block.append(f"  -> deps: {', '.join(deps)}")
            for cls in rec["classes"][:10]:
                block.append(f"  {cls['signature']}")
                for m in cls["methods"][:8]:
                    block.append(f"    {m}")
            for fn in rec["functions"][:12]:
                block.append(f"  {fn['signature']}")
            if len(block) == 1:
                block.append(f"  ({rec['lines']} lines)")
            rendered = "\n".join(block)
            if used + len(rendered) > budget_chars and selected:
                break
            if used + len(rendered) > budget_chars:
                rendered = rendered[:max(120, budget_chars - used)]
            lines.append(rendered)
            used += len(rendered) + 1
            selected.append(rel)

        map_text = "\n".join(lines).strip()
        raw_tokens = max(1, raw_chars // 4)
        map_tokens = len(map_text) // 4
        reduction = round(max(0.0, (1.0 - (map_tokens / raw_tokens)) * 100.0), 1) if raw_chars else 0.0
        engine_label = "tree-sitter+ast" if any("tree-sitter" in e for e in engines) else (next(iter(engines), "ast"))
        return {
            "map": map_text,
            "files_scanned": len(records),
            "files_selected": len(selected),
            "selected_paths": selected,
            "raw_tokens_est": raw_tokens,
            "map_tokens_est": map_tokens,
            "token_reduction_pct": reduction,
            "engine": engine_label,
            "dependencies": {k: sorted(v) for k, v in outgoing.items() if v},
        }

