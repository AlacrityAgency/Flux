"""Agentic Engineering Suite for Flux (v0.7.0).

Unifies six core engineering capabilities around ``LocalRuntime``:
1. ``RepoMapper``         — Tree-sitter + AST structural repository map & PageRank
2. ``PlanActManager``     — Two-phase Plan (read-only) vs. Act (blueprint execution)
3. ``FeedbackVerifier``   — Automated compiler / linter / typechecker / pytest loop
4. ``SurgicalEditor``     — Surgical ``replace_in_file``, SEARCH/REPLACE & unified diff
5. ``ShadowCheckpoints``  — Zero-interference Shadow Git snapshots & 1-click rollback
6. ``ContextSentinel``    — ``AGENTS.md``/rules re-injection & persistent error memory
"""
from __future__ import annotations

from pathlib import Path

from flux.agentic.checkpoints import ShadowCheckpoints
from flux.agentic.feedback import FeedbackVerifier
from flux.agentic.plan_act import PLAN_MODE_INSTRUCTIONS, PlanActManager
from flux.agentic.repomap import RepoMapper
from flux.agentic.sentinel import ContextSentinel
from flux.agentic.surgical import (
    SURGICAL_PROMPT_GUIDE,
    apply_model_edits,
    apply_unified_diff,
    has_surgical_directives,
    replace_in_file,
)


class AgenticHub:
    def __init__(self, repo, workspace, runtime, shadow_root=None, events=None):
        self.repo, self.workspace, self.runtime = repo, workspace, runtime
        self.events = events
        self.repomap = RepoMapper()
        self.sentinel = ContextSentinel(repo)
        self.plans = PlanActManager(repo)
        self.verifier = FeedbackVerifier()
        self.checkpoints = ShadowCheckpoints(repo, shadow_root)
        runtime.agentic = self

    def build_turn_preface(self, chat: dict, turn: dict, prompt: str) -> tuple[str, dict]:
        """Construct the Context Sentinel + RepoMap + Plan/Act + Surgical preface and telemetry."""
        cwd = chat.get("cwd") or ""
        mode = turn.get("mode") or chat.get("mode") or "act"
        meta: dict = {"mode": mode}
        parts: list[str] = []

        if chat.get("provider") == "notebooklm" or not cwd or not Path(cwd).is_dir():
            return "", meta

        # 1. Context Sentinel (Rules + Past Repository Error Memory) — injected on EVERY turn
        if turn.get("use_sentinel", True):
            s_ctx = self.sentinel.build_context(cwd, prompt)
            if s_ctx["rendered"]:
                parts.append(s_ctx["rendered"])
            meta["sentinel"] = {
                "rule_sources": s_ctx["rule_sources"],
                "lessons_injected": s_ctx["lessons_injected"],
                "chars": s_ctx["chars"],
            }

        # 2. Tree-sitter + AST Smart Repo Map
        if turn.get("use_repomap", True):
            rmap = self.repomap.build(cwd, prompt, budget_chars=5500)
            if rmap["map"]:
                parts.append(rmap["map"] + "\n")
            meta["repomap"] = {
                "engine": rmap["engine"],
                "files_scanned": rmap["files_scanned"],
                "files_selected": rmap["files_selected"],
                "raw_tokens_est": rmap["raw_tokens_est"],
                "map_tokens_est": rmap["map_tokens_est"],
                "token_reduction_pct": rmap["token_reduction_pct"],
            }

        # 3. Plan Mode vs. Act Mode + Surgical Editing Protocol
        if mode == "plan":
            parts.append(PLAN_MODE_INSTRUCTIONS)
        else:
            approved = self.plans.active_approved_plan(chat["id"])
            if approved:
                parts.append(self.plans.render_act_blueprint(approved))
                meta["active_plan_id"] = approved["id"]
            if chat.get("access") == "work" or chat.get("surgical_edits"):
                parts.append(SURGICAL_PROMPT_GUIDE)

        return ("\n".join(parts) + "\n") if parts else "", meta

    def before_turn(self, turn_id: str, chat: dict, mode: str) -> dict | None:
        """Take a pre-turn Shadow Git snapshot so Plan mode stays read-only and Act mode can roll back."""
        cwd = chat.get("cwd") or ""
        if not cwd or not Path(cwd).is_dir() or chat.get("provider") == "notebooklm":
            return None
        if mode != "plan" and chat.get("access") != "work" and not chat.get("surgical_edits"):
            return None
        try:
            return self.checkpoints.capture(cwd, chat["id"], turn_id, stage="before", label=f"before {turn_id}")
        except Exception:
            return None

    def process_round(
        self,
        turn_id: str,
        chat: dict,
        turn: dict,
        mode: str,
        cp_before: dict | None,
        model_text: str,
        round_idx: int,
        had_prior_failure: bool,
    ) -> dict:
        """Apply surgical edits (or enforce Plan read-only), run compiler/test gates, and decide whether to self-heal."""
        cwd = chat.get("cwd") or ""
        result: dict = {
            "needs_heal": False,
            "repair_prompt": "",
            "surgical": None,
            "verification": None,
            "plan": None,
            "checkpoint_after": None,
        }
        if not cwd or not Path(cwd).is_dir():
            return result

        # --- PLAN MODE: strictly read-only + parse & persist structured plan ---
        if mode == "plan":
            if cp_before:
                stray = self.checkpoints.changed_since(cwd, cp_before["commit_sha"])
                if stray:
                    self.checkpoints.restore(cp_before["id"], create_backup=False)
            plan = self.plans.record_plan(cwd, turn["prompt"], model_text, chat_id=chat["id"], turn_id=turn_id)
            result["plan"] = plan
            if self.events:
                self.events.publish("agentic.plan_created", {"plan_id": plan["id"], "chat_id": chat["id"], "turn_id": turn_id})
            return result

        # --- ACT MODE: surgical edits + compiler/linter/test feedback loop ---
        can_write = chat.get("access") == "work" or bool(chat.get("surgical_edits"))
        if not can_write:
            return result

        surgical_errors = []
        if has_surgical_directives(model_text):
            s_out = apply_model_edits(cwd, model_text)
            result["surgical"] = s_out
            surgical_errors = s_out["errors"]

        changed = self.checkpoints.changed_since(cwd, cp_before["commit_sha"]) if cp_before else []
        if result["surgical"] and result["surgical"]["applied"]:
            for item in result["surgical"]["applied"]:
                if item["path"] not in changed:
                    changed.append(item["path"])

        if surgical_errors:
            err_msg = "\n".join(f"- {e['path']}: {e['error']}" for e in surgical_errors)
            self.sentinel.record_lesson(cwd, "surgical_edit", err_msg, [e["path"] for e in surgical_errors])
            max_rounds = int(turn.get("max_heal_rounds", 2))
            if turn.get("auto_heal", True) and round_idx < max_rounds:
                result["needs_heal"] = True
                result["repair_prompt"] = (
                    "SURGICAL EDIT APPLICATION FAILED:\n"
                    f"{err_msg}\n"
                    "بلوک SEARCH با متن دقیق فعلی فایل هم‌خوانی نداشت؛ خطوط دقیق فایل را بررسی کن و یک <flux-edit> معتبر بفرست."
                )
                return result

        if changed:
            v_report = self.verifier.verify(cwd, changed, run_tests=True)
            result["verification"] = v_report
            if not v_report["passed"]:
                for stage_name in v_report["failed_checks"]:
                    self.sentinel.record_lesson(cwd, stage_name, v_report["error_summary"], changed)
                max_rounds = int(turn.get("max_heal_rounds", 2))
                if turn.get("auto_heal", True) and round_idx < max_rounds:
                    result["needs_heal"] = True
                    result["repair_prompt"] = v_report["repair_prompt"]
                    return result
            elif had_prior_failure:
                self.sentinel.record_lesson(
                    cwd,
                    "self_healed",
                    f"Errors in {', '.join(changed[:3])} caught by feedback loop",
                    changed,
                    resolution=f"Verified clean after self-correction round {round_idx}",
                )

            try:
                result["checkpoint_after"] = self.checkpoints.capture(
                    cwd, chat["id"], turn_id, stage="after", label=f"after {turn_id} (r{round_idx})"
                )
            except Exception:
                pass

        approved = self.plans.active_approved_plan(chat["id"])
        if approved and changed and (not result["verification"] or result["verification"]["passed"]):
            self.plans.mark_executed(approved["id"])

        return result


__all__ = [
    "AgenticHub",
    "RepoMapper",
    "PlanActManager",
    "FeedbackVerifier",
    "ShadowCheckpoints",
    "ContextSentinel",
    "replace_in_file",
    "apply_model_edits",
    "apply_unified_diff",
]

