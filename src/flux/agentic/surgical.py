"""Surgical File Edits vs. Full Rewrite.

Provides exact and whitespace-tolerant ``replace_in_file``, multi-hunk
``<<<<<<< SEARCH ... ======= ... >>>>>>> REPLACE`` block execution, and unified
git diff patching — all strictly path-jailed inside the workspace root so
untouched code is never accidentally dropped or rewritten.
"""
from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path


class SurgicalEditError(ValueError):
    """Raised when a surgical edit cannot be safely or unambiguously applied."""


EDIT_BLOCK_RE = re.compile(
    r"<flux-edit\s+path=[\"']([^\"']+)[\"']\s*>\s*(.*?)\s*</flux-edit>",
    re.DOTALL,
)
CREATE_BLOCK_RE = re.compile(
    r"<flux-create\s+path=[\"']([^\"']+)[\"']\s*>\n?(.*?)</flux-create>",
    re.DOTALL,
)
HUNK_RE = re.compile(
    r"<{5,9}\s*SEARCH[ \t]*\r?\n(.*?)\r?\n={5,9}[ \t]*\r?\n(.*?)\r?\n>{5,9}\s*REPLACE",
    re.DOTALL,
)

SURGICAL_PROMPT_GUIDE = (
    "SURGICAL FILE EDITING PROTOCOL (never rewrite entire files when changing existing code):\n"
    "To edit an existing file, emit ONLY minimal SEARCH/REPLACE hunks wrapped in <flux-edit>:\n"
    "<flux-edit path=\"relative/path/to/file.py\">\n"
    "<<<<<<< SEARCH\n"
    "exact existing lines with 2-3 lines of context\n"
    "=======\n"
    "updated replacement lines\n"
    ">>>>>>> REPLACE\n"
    "</flux-edit>\n"
    "To create a brand-new file, use <flux-create path=\"relative/path/to/new_file.py\">...</flux-create>.\n"
)


def resolve_jailed_path(cwd: str | Path, rel_path: str) -> Path:
    root = Path(cwd).resolve()
    cleaned = rel_path.strip().replace("\\", "/").lstrip("/")
    if not cleaned or cleaned in {".", ".."}:
        raise SurgicalEditError("مسیر فایل نامعتبر است.")
    target = (root / cleaned).resolve()
    try:
        rel = target.relative_to(root)
    except ValueError as exc:
        raise SurgicalEditError(f"خروج از پوشهٔ کاری مجاز نیست: {rel_path}") from exc
    if ".git" in rel.parts:
        raise SurgicalEditError("ویرایش مستقیم پوشهٔ .git مجاز نیست.")
    return target


def _apply_single_hunk(content: str, search: str, replace: str, label: str = "") -> str:
    if not search:
        raise SurgicalEditError(f"بلوک SEARCH در {label} نباید خالی باشد.")
    newline = "\r\n" if "\r\n" in content else "\n"

    # Tier 1: exact match
    count = content.count(search)
    if count == 1:
        return content.replace(search, replace, 1)
    if count > 1:
        raise SurgicalEditError(f"بلوک SEARCH در {label} در {count} نقطه تکرار شده است؛ خطوط کانتکست بیشتری بدهید.")

    # Tier 2: newline-normalized exact match
    norm_content = content.replace("\r\n", "\n")
    norm_search = search.replace("\r\n", "\n")
    norm_replace = replace.replace("\r\n", "\n")
    ncount = norm_content.count(norm_search)
    if ncount == 1:
        updated = norm_content.replace(norm_search, norm_replace, 1)
        return updated.replace("\n", newline) if newline == "\r\n" else updated
    if ncount > 1:
        raise SurgicalEditError(f"بلوک SEARCH در {label} مبهم است ({ncount} تطابق).")

    # Tier 3: line-by-line trailing-whitespace tolerant match
    src_lines = norm_content.split("\n")
    needle_lines = [ln.rstrip() for ln in norm_search.split("\n")]
    m = len(needle_lines)
    matches = []
    for i in range(len(src_lines) - m + 1):
        if [ln.rstrip() for ln in src_lines[i:i + m]] == needle_lines:
            matches.append(i)
    if len(matches) == 1:
        idx = matches[0]
        rep_lines = norm_replace.split("\n")
        merged = src_lines[:idx] + rep_lines + src_lines[idx + m:]
        updated = "\n".join(merged)
        return updated.replace("\n", newline) if newline == "\r\n" else updated
    if len(matches) > 1:
        raise SurgicalEditError(f"بلوک SEARCH در {label} در چند خط ({matches}) تطابق دارد؛ زمینهٔ بیشتری مشخص کنید.")

    raise SurgicalEditError(f"بلوک SEARCH در {label} پیدا نشد؛ مطمئن شوید کد فعلی فایل را دقیق نوشته‌اید.")


def replace_in_file(cwd: str | Path, rel_path: str, search: str, replace: str) -> dict:
    """Apply a single surgical replacement inside ``rel_path`` without rewriting the whole file."""
    target = resolve_jailed_path(cwd, rel_path)
    if not target.is_file():
        raise SurgicalEditError(f"فایل پیدا نشد: {rel_path}")
    original = target.read_text(encoding="utf-8")
    updated = _apply_single_hunk(original, search, replace, rel_path)
    target.write_text(updated, encoding="utf-8")
    total_lines = original.count("\n") + 1
    edited_lines = max(search.count("\n") + 1, replace.count("\n") + 1)
    saved_pct = round(max(0.0, (1.0 - min(1.0, edited_lines / max(1, total_lines))) * 100.0), 1)
    return {
        "path": target.relative_to(Path(cwd).resolve()).as_posix(),
        "total_lines": total_lines,
        "edited_lines": edited_lines,
        "token_saving_pct": saved_pct,
        "changed": original != updated,
    }


def has_surgical_directives(text: str) -> bool:
    return bool(text and ("<flux-edit" in text or "<flux-create" in text))


def apply_model_edits(cwd: str | Path, text: str) -> dict:
    """Parse and apply all ``<flux-create>`` and ``<flux-edit>`` blocks emitted by a model."""
    applied, errors = [], []
    root = Path(cwd).resolve()

    for match in CREATE_BLOCK_RE.finditer(text or ""):
        rel_path, body = match.group(1), match.group(2)
        try:
            target = resolve_jailed_path(root, rel_path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(body, encoding="utf-8")
            applied.append({"path": target.relative_to(root).as_posix(), "op": "create", "hunks": 1,
                            "edited_lines": body.count("\n") + 1, "total_lines": body.count("\n") + 1})
        except (SurgicalEditError, OSError) as exc:
            errors.append({"path": rel_path, "error": str(exc)})

    for match in EDIT_BLOCK_RE.finditer(text or ""):
        rel_path, inner = match.group(1), match.group(2)
        hunks = list(HUNK_RE.finditer(inner))
        if not hunks:
            errors.append({"path": rel_path, "error": "هیچ بلوک SEARCH/REPLACE معتبری درون <flux-edit> یافت نشد."})
            continue
        try:
            target = resolve_jailed_path(root, rel_path)
            if not target.is_file():
                raise SurgicalEditError(f"فایل وجود ندارد: {rel_path}")
            original = target.read_text(encoding="utf-8")
            working = original
            edited_lines = 0
            for idx, h in enumerate(hunks, 1):
                s_block, r_block = h.group(1), h.group(2)
                working = _apply_single_hunk(working, s_block, r_block, f"{rel_path}#hunk{idx}")
                edited_lines += max(s_block.count("\n") + 1, r_block.count("\n") + 1)
            target.write_text(working, encoding="utf-8")
            total_lines = original.count("\n") + 1
            applied.append({
                "path": target.relative_to(root).as_posix(),
                "op": "edit",
                "hunks": len(hunks),
                "total_lines": total_lines,
                "edited_lines": edited_lines,
                "token_saving_pct": round(max(0.0, (1.0 - min(1.0, edited_lines / max(1, total_lines))) * 100.0), 1),
            })
        except (SurgicalEditError, OSError) as exc:
            errors.append({"path": rel_path, "error": str(exc)})

    return {"applied": applied, "errors": errors, "ok": len(errors) == 0}


def _apply_unified_diff_python(root: Path, norm_patch: str) -> list[str]:
    """Deterministic, atomic pure-Python unified diff applier (handles LLM short-context hunks & CRLF)."""
    hunk_hdr = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
    lines = norm_patch.splitlines()
    idx = 0
    file_patches: list[tuple[Path, str, list[tuple[int, list[str]]]]] = []
    while idx < len(lines):
        line = lines[idx]
        if not line.startswith("--- "):
            idx += 1
            continue
        old_hdr = line[4:].strip()
        idx += 1
        if idx >= len(lines) or not lines[idx].startswith("+++ "):
            raise SurgicalEditError("ساختار هدر diff ناقص است.")
        new_hdr = lines[idx][4:].strip()
        idx += 1
        rel = (new_hdr[2:] if new_hdr.startswith("b/") else new_hdr) if new_hdr != "/dev/null" else (
            old_hdr[2:] if old_hdr.startswith("a/") else old_hdr
        )
        target = resolve_jailed_path(root, rel)
        hunks: list[tuple[int, list[str]]] = []
        while idx < len(lines) and not lines[idx].startswith("--- "):
            m = hunk_hdr.match(lines[idx])
            if not m:
                idx += 1
                continue
            old_start = int(m.group(1))
            idx += 1
            hunk_lines: list[str] = []
            while idx < len(lines) and not lines[idx].startswith(("@@ ", "--- ", "diff --git ")):
                if lines[idx].startswith("\\ No newline"):
                    idx += 1
                    continue
                hunk_lines.append(lines[idx])
                idx += 1
            hunks.append((old_start, hunk_lines))
        file_patches.append((target, rel, hunks))

    if not file_patches:
        raise SurgicalEditError("هیچ hunk معتبری در diff یافت نشد.")

    staged_writes: list[tuple[Path, str, str]] = []
    for target, rel, hunks in file_patches:
        raw = target.read_text(encoding="utf-8", errors="replace") if target.exists() else ""
        eol = "\r\n" if "\r\n" in raw else "\n"
        src_lines = raw.replace("\r\n", "\n").split("\n")
        had_trailing_nl = raw.endswith(("\n", "\r\n")) or raw == ""
        if had_trailing_nl and src_lines and src_lines[-1] == "":
            src_lines.pop()

        offset = 0
        for old_start, hunk_lines in hunks:
            old_block = [hl[1:] for hl in hunk_lines if hl.startswith((" ", "-"))]
            new_block = [hl[1:] for hl in hunk_lines if hl.startswith((" ", "+"))]
            pos_guess = max(0, old_start - 1 + offset)
            match_pos = None
            if not old_block:
                match_pos = min(pos_guess, len(src_lines))
            else:
                # Search exact around pos_guess first, then stripped whitespace
                candidates = [pos_guess] + [
                    pos_guess + d for r in range(1, len(src_lines) + 1) for d in (-r, r)
                    if 0 <= pos_guess + d <= len(src_lines) - len(old_block)
                ]
                seen: set[int] = set()
                for c in candidates:
                    if c in seen or c < 0 or c + len(old_block) > len(src_lines):
                        continue
                    seen.add(c)
                    if src_lines[c : c + len(old_block)] == old_block:
                        match_pos = c
                        break
                if match_pos is None:
                    old_trim = [x.rstrip() for x in old_block]
                    for c in candidates:
                        if c < 0 or c + len(old_block) > len(src_lines):
                            continue
                        if [x.rstrip() for x in src_lines[c : c + len(old_block)]] == old_trim:
                            match_pos = c
                            break
            if match_pos is None:
                raise SurgicalEditError(f"اعمال diff معتبر نیست: hunk در {rel}:{old_start} منطبق نشد.")
            src_lines[match_pos : match_pos + len(old_block)] = new_block
            offset += len(new_block) - len(old_block)

        out = eol.join(src_lines) + (eol if had_trailing_nl else "")
        staged_writes.append((target, rel, out))

    touched: list[str] = []
    for target, rel, out in staged_writes:
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8", newline="") as fh:
            fh.write(out)
        touched.append(rel.replace("\\", "/"))
    return sorted(set(touched))


def apply_unified_diff(cwd: str | Path, patch_text: str) -> dict:
    """Validate and apply a standard unified diff safely inside ``cwd``."""
    root = Path(cwd).resolve()
    if not patch_text.strip():
        raise SurgicalEditError("متن diff خالی است.")
    for line in patch_text.splitlines():
        if line.startswith(("+++ b/", "--- a/")):
            rel = line[6:].strip()
            if rel != "/dev/null":
                resolve_jailed_path(root, rel)
    flags = {"creationflags": subprocess.CREATE_NO_WINDOW} if hasattr(subprocess, "CREATE_NO_WINDOW") else {}
    norm_patch = patch_text.replace("\r\n", "\n")
    if not norm_patch.endswith("\n"):
        norm_patch += "\n"
    with tempfile.NamedTemporaryFile("w", suffix=".patch", encoding="utf-8", newline="\n", delete=False) as tmp:
        tmp.write(norm_patch)
        patch_file = Path(tmp.name)
    try:
        chk = subprocess.run(
            ["git", "apply", "--check", "--recount", "--unidiff-zero", "--ignore-whitespace", "--whitespace=nowarn", str(patch_file)],
            cwd=str(root), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20, **flags,
        )
        if chk.returncode == 0:
            run = subprocess.run(
                ["git", "apply", "--recount", "--unidiff-zero", "--ignore-whitespace", "--whitespace=nowarn", str(patch_file)],
                cwd=str(root), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20, **flags,
            )
            if run.returncode == 0:
                touched = [
                    line[6:].strip()
                    for line in norm_patch.splitlines()
                    if line.startswith("+++ b/") and line[6:].strip() != "/dev/null"
                ]
                return {"applied": sorted(set(touched)), "ok": True}
        touched = _apply_unified_diff_python(root, norm_patch)
        return {"applied": touched, "ok": True}
    finally:
        patch_file.unlink(missing_ok=True)
