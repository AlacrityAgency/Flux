"""Deterministic Fake Provider for tests and offline development."""

import json
import asyncio
from flux.engine.profiles import LEGACY_MODELS
from typing import Any, Callable, Dict, Optional
from flux.providers.base import LLMProvider, LLMResponse, ProviderError


class FakeProvider(LLMProvider):
    def __init__(self):
        self.call_count = 0
        self.delay_seconds = 0
        self.recorded_calls = []
        # Hooks to customize responses or inject errors
        self.custom_responses: Dict[str, str] = {}
        self.transient_error_countdown: int = 0
        self.permanent_error: bool = False
        self.simulate_missing_usage: bool = False
        self.simulate_invalid_json: bool = False
        self.scenario: str = "default"  # "default", "out_of_company", "cycle", "too_many_subtasks", "not_run_check"

    async def generate(
        self,
        model_id: str,
        messages: list[Dict[str, str]],
        max_output_tokens: int = 2000,
        response_schema: Optional[Dict[str, Any]] = None
    ) -> LLMResponse:
        self.call_count += 1
        if self.delay_seconds:
            await asyncio.sleep(self.delay_seconds)
        self.recorded_calls.append({
            "model_id": model_id,
            "messages": messages,
            "max_output_tokens": max_output_tokens
        })

        # Check for simulated errors
        if self.permanent_error:
            raise ProviderError("Authentication failed: invalid key", is_transient=False, status_code=401)

        if self.transient_error_countdown > 0:
            self.transient_error_countdown -= 1
            raise ProviderError("Rate limit exceeded / Gateway timeout", is_transient=True, status_code=429)

        if self.simulate_invalid_json:
            return LLMResponse(
                content="This is plain text and definitely not valid JSON {{{",
                input_tokens=150,
                cached_input_tokens=0,
                output_tokens=30,
                latency_ms=45,
                usage_available=True,
                model_id=model_id
            )

        # Route fixtures by role when several roles share a cheaper model.
        fixture_model = model_id
        system = messages[0]["content"] if messages else ""
        for role, original_model in LEGACY_MODELS.items():
            if f"Flux role: {role}." in system:
                fixture_model = original_model
                break

        # Check custom response dictionary
        if fixture_model in self.custom_responses:
            content = self.custom_responses[fixture_model]
        else:
            content = self._generate_scenario_content(fixture_model)
            if self.scenario == "default":
                content = self._workspace_response(fixture_model, messages, content)

        usage_available = not self.simulate_missing_usage
        return LLMResponse(
            content=content,
            input_tokens=220 if usage_available else 0,
            cached_input_tokens=20 if usage_available else 0,
            output_tokens=380 if usage_available else 0,
            latency_ms=120,
            usage_available=usage_available,
            model_id=model_id
        )

    def _workspace_response(self, model_id, messages, fallback):
        data = {}
        for message in messages:
            text = message["content"]
            try:
                data.update(json.loads(text[text.index("{"):]))
            except (ValueError, TypeError):
                pass
        result = json.loads(fallback)
        objective = data.get("task_objective") or data.get("objective") or data.get("root_objective") or "کار شما"
        criteria = data.get("root_acceptance_criteria") or data.get("acceptance_criteria") or ["پوشش درخواست"]
        if model_id == "claude-fable-5":
            roles = [("sub_plan", "opus", "برنامه‌ریزی مراحل و مشخص‌کردن وابستگی‌ها"),
                     ("sub_tech", "sol", "تحلیل راه‌حل و محدودیت‌های فنی"),
                     ("sub_draft", "luna", "آماده‌کردن پیش‌نویس نهایی")]
            if data.get("workflow") not in ("team", "high"):
                roles = roles[-1:]
            result["subtasks"] = [{"subtask_id": ident, "assigned_agent": role,
                "objective": title, "acceptance_criteria": criteria,
                "dependencies": [roles[i-1][0]] if i else [], "max_output_tokens": 2000}
                for i, (ident, role, title) in enumerate(roles)]
            result["summary"] = "برنامهٔ آزمایشی آماده شد؛ فقط نقش‌های موردنیاز این مسیر اجرا می‌شوند."
        elif model_id == "gapgpt-qwen-3.6-thinking":
            result["passed_criteria"] = criteria
        else:
            result["subtask_id"] = data.get("subtask_id", result["subtask_id"])
            role = result["agent"]
            text = {
                "opus": "## برنامهٔ پیشنهادی\n\n1. هدف و خروجی موردانتظار را روشن کنیم.\n2. منابع مرتبط را از حافظه انتخاب کنیم.\n3. پیش‌نویس را بسازیم و با معیارها تطبیق بدهیم.\n\n### معیارهای این کار\n" + "\n".join("- " + c for c in criteria),
                "sol": "## بررسی فنی\n\nپیشنهاد این نمونه، تفکیک رابط، موتور و حافظه است. دادهٔ اجرای قبلی باید پس از راه‌اندازی دوباره حفظ شود.\n\n- رابط فقط وضعیت ثبت‌شده را نمایش می‌دهد.\n- مصرف هر فراخوانی در دفتر هزینه ثبت می‌شود.\n- کد و تست در این دمو اجرا نمی‌شوند.",
                "luna": "## پیش‌نویس آماده است\n\nاین یک پاسخ **آزمایشی و از پیش تعریف‌شده** برای نمایش گردش کار Flux است؛ مدل واقعی فراخوانی نشده است.\n\n### درخواست شما\n" + objective + "\n\n### مسیر انجام کار\n1. هدف و معیارهای شما به قرارداد کار تبدیل شدند.\n2. اطلاعات مرتبط، در صورت وجود، به زمینهٔ کار اضافه شدند.\n3. این پیش‌نویس برای بررسی مستقل فرستاده می‌شود.\n\n### قدم بعد\nخروجی را بررسی کنید یا در پیام بعدی اصلاح موردنظرتان را بنویسید. برای پاسخ اختصاصی، اتصال واقعی باید فعال و بررسی شود."
            }[role]
            result["summary"] = {"opus": "برنامهٔ نمونه آماده شد.", "sol": "تحلیل فنی نمونه آماده شد.", "luna": "پیش‌نویس آزمایشی برای بررسی شما آماده است."}[role]
            result["output"] = {"content": text}
            result["checks"] = [{"name": c, "status": "passed", "evidence": "شاهد شبیه‌سازی‌شدهٔ Fake Provider؛ ارزیابی واقعی انجام نشده است."} for c in criteria]
        return json.dumps(result, ensure_ascii=False)

    def _generate_scenario_content(self, model_id: str) -> str:
        # Head Agent (claude-fable-5)
        if model_id == "claude-fable-5":
            if self.scenario == "out_of_company":
                return json.dumps({
                    "task_type": "operations",
                    "company_relevance": "invalid",
                    "summary": "Task is outside the legitimate scope of company operations.",
                    "ambiguities": [],
                    "risk_level": "high",
                    "requires_human_input": False,
                    "subtasks": [],
                    "final_review_agent": "fable",
                    "reason": "Request is completely unrelated to company projects."
                })

            if self.scenario == "cycle":
                return json.dumps({
                    "task_type": "technical",
                    "company_relevance": "valid",
                    "summary": "Planning subtasks with cyclic dependency for testing.",
                    "ambiguities": [],
                    "risk_level": "medium",
                    "requires_human_input": False,
                    "subtasks": [
                        {
                            "subtask_id": "sub_1",
                            "objective": "First subtask depending on second",
                            "assigned_agent": "luna",
                            "acceptance_criteria": ["Draft code"],
                            "dependencies": ["sub_2"],
                            "max_output_tokens": 1500
                        },
                        {
                            "subtask_id": "sub_2",
                            "objective": "Second subtask depending on first",
                            "assigned_agent": "luna",
                            "acceptance_criteria": ["Review code"],
                            "dependencies": ["sub_1"],
                            "max_output_tokens": 1500
                        }
                    ],
                    "final_review_agent": "qwen",
                    "reason": "Cyclic DAG test"
                })

            if self.scenario == "too_many_subtasks":
                return json.dumps({
                    "task_type": "operations",
                    "company_relevance": "valid",
                    "summary": "Generating 6 subtasks to violate limit.",
                    "ambiguities": [],
                    "risk_level": "low",
                    "requires_human_input": False,
                    "subtasks": [
                        {
                            "subtask_id": f"sub_{i}",
                            "objective": f"Subtask {i}",
                            "assigned_agent": "luna",
                            "acceptance_criteria": ["Done"],
                            "dependencies": [],
                            "max_output_tokens": 1000
                        }
                        for i in range(1, 7)
                    ],
                    "final_review_agent": "qwen",
                    "reason": "Testing subtask count limit"
                })

            # Default Head Plan: 2 subtasks (execution by Luna, verification by Qwen)
            return json.dumps({
                "task_type": "documentation",
                "company_relevance": "valid",
                "summary": "Verified company relevance. Decomposing documentation task into drafting subtask.",
                "ambiguities": [],
                "risk_level": "low",
                "requires_human_input": False,
                "subtasks": [
                    {
                        "subtask_id": "sub_draft",
                        "objective": "Draft project documentation and verify criteria.",
                        "assigned_agent": "luna",
                        "acceptance_criteria": ["Documentation draft matches requirements"],
                        "dependencies": [],
                        "max_output_tokens": 2000
                    }
                ],
                "final_review_agent": "qwen",
                "reason": "Single execution step is sufficient for documentation task."
            })

        # Planning Agent (claude-opus-5)
        if model_id == "claude-opus-5":
            return json.dumps({
                "agent": "opus",
                "model_id": "claude-opus-5",
                "subtask_id": "sub_plan",
                "status": "completed",
                "summary": "Detailed execution plan structured.",
                "output": {"phases": ["Architecture", "Implementation", "Review"]},
                "artifacts": [
                    {
                        "type": "document",
                        "ref": "artifacts/plan.md",
                        "description": "Structured project execution plan"
                    }
                ],
                "checks": [
                    {
                        "name": "plan_completeness",
                        "status": "passed",
                        "evidence": "All acceptance criteria mapped to work packages."
                    }
                ],
                "unresolved_issues": []
            })

        # Technical Agent (gpt-5.6-sol)
        if model_id == "gpt-5.6-sol":
            return json.dumps({
                "agent": "sol",
                "model_id": "gpt-5.6-sol",
                "subtask_id": "sub_tech",
                "status": "completed",
                "summary": "Technical review and architecture verification complete.",
                "output": {"risk_assessment": "low", "architecture_approved": True},
                "artifacts": [
                    {
                        "type": "report",
                        "ref": "artifacts/tech_review.md",
                        "description": "Technical architecture assessment"
                    }
                ],
                "checks": [
                    {
                        "name": "architecture_soundness",
                        "status": "passed",
                        "evidence": "Clean modular separation confirmed."
                    }
                ],
                "unresolved_issues": []
            })

        # Execution Agent (gpt-5.6-luna)
        if model_id == "gpt-5.6-luna":
            checks = [
                {
                    "name": "criterion_validation",
                    "status": "not_run" if self.scenario == "not_run_check" else "passed",
                    "evidence": "Draft verified against criteria." if self.scenario != "not_run_check" else "Test was skipped."
                }
            ]
            return json.dumps({
                "agent": "luna",
                "model_id": "gpt-5.6-luna",
                "subtask_id": "sub_draft",
                "status": "completed",
                "summary": "Draft and artifacts prepared successfully.",
                "output": {"content": "Documentation content ready."},
                "artifacts": [
                    {
                        "type": "document",
                        "ref": "artifacts/output_draft.md",
                        "description": "Completed work product draft"
                    }
                ],
                "checks": checks,
                "unresolved_issues": []
            })

        # Verification Agent (gapgpt-qwen-3.6-thinking)
        if model_id == "gapgpt-qwen-3.6-thinking":
            if self.scenario == "not_run_check":
                return json.dumps({
                    "decision": "REVISE",
                    "blocking_issues": [
                        {
                            "criterion": "criterion_validation",
                            "evidence": "Check status is not_run.",
                            "required_change": "Run the necessary validation tests."
                        }
                    ],
                    "passed_criteria": [],
                    "failed_criteria": ["criterion_validation"],
                    "confidence": "high"
                })

            return json.dumps({
                "decision": "ACCEPT_CANDIDATE",
                "blocking_issues": [],
                "passed_criteria": ["Documentation draft matches requirements"],
                "failed_criteria": [],
                "confidence": "high"
            })

        return "{}"
