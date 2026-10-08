"""HOLDOUT tasks (H01-H10). Written after JEVS v0 had been run on T01-T15 and BEFORE JEVS v1 existed.
v1 is tuned only on T01-T15; these tasks are evaluated once, at the end, with no further changes.
Same rules as tasks.py: needs are pre-declared anchors / memory ids; criteria use domain words, not helper names.
"""
import tasks as _t

_t.T = []                       # reuse the helper with a fresh list
H = _t.T
task, code, mem = _t.task, _t.code, _t.mem

task("H01", "en",
     "Explain how the local API protects state-changing requests from pages opened in other websites",
     [("Show the origin comparison applied to non-GET requests",
       [code("async def local_origin(request: Request, call_next):",
             'if origin and urlsplit(origin).netloc != request.headers.get("host"):')]),
      ("Show which host names are accepted",
       [code('app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "[::1]", "test", "testserver"])')]),
      ("Show the response hardening headers", [code('response.headers["X-Content-Type-Options"] = "nosniff"')]),
      ("Reference the test for the origin guard", [code("test_validation_idempotency_and_origin_guard")])])

task("H02", "fa",
     "کلید API چگونه ذخیره می‌شود و در رابط کاربری به‌صورت پوشیده نمایش داده می‌شود؟",
     [("ساخت متن پوشیدهٔ کلید نشان داده شود", [code('masked_key = f"{k[:7]}...{k[-4:]}" if len(k) > 12 else "***"')]),
      ("ذخیرهٔ کلید در محیط و فایل env نشان داده شود",
       [code("async def set_api_key(payload: ApiKeyRequest):", 'os.environ["GAPGPT_API_KEY"] = key')]),
      ("خواندن کلید فقط از متغیر محیطی نشان داده شود",
       [code("def gapgpt_api_key(self) -> str:", "Read API key exclusively from environment variable.")]),
      ("مدل درخواست ذخیرهٔ کلید نشان داده شود", [code("class ApiKeyRequest(BaseModel):")])])

task("H03", "en",
     "Document the recovery stages used when a model returns malformed JSON",
     [("Show the parser entry point and the thinking-tag removal",
       [code("def parse_llm_json(content: str) -> Dict[str, Any]:",
             "# 1. Remove reasoning / thinking tags (<think>...</think>) from thinking models")]),
      ("Show the markdown fence recovery",
       [code('fence_match = re.search(r"```(?:json)?\\s*([\\s\\S]*?)\\s*```", text)')]),
      ("Show the optional repair library stage",
       [code("repaired = json_repair.repair_json(text, return_objects=True)")]),
      ("Show how the engine reports an unreadable response",
       [code('"پاسخ JSON مدل قابل خواندن نیست."')]),
      ("Reference the invalid-JSON test", [code("async def test_invalid_json_from_model_handled_and_logged")])])

task("H04", "fa",
     "وقتی provider پاسخ ۴۰۰ دربارهٔ response_format یا reasoning_effort می‌دهد چه اتفاقی می‌افتد؟",
     [("حذف response_format و ارسال دوبارهٔ درخواست نشان داده شود",
       [code('if err.status_code == 400 and "response_format" in err_msg:', 'kwargs.pop("response_format", None)')]),
      ("شاخهٔ reasoning_effort نشان داده شود",
       [code('if err.status_code == 400 and "reasoning_effort" in err_msg:')]),
      ("حالت اولیهٔ JSON mode نشان داده شود", [code('kwargs["response_format"] = {"type": "json_object"}')]),
      ("غیرفعال‌بودن retry داخلی SDK نشان داده شود",
       [code("max_retries=0,  # Retries are managed deterministically by Flux engine")])])

task("H05", "en",
     "How does Flux decide which runs to fail on startup after the process was interrupted?",
     [("Show the startup recovery loop", [code("local_runtime.recover()", 'if record["status"] in ACTIVE:')]),
      ("Show the set of statuses considered active",
       [code('ACTIVE = {"NEW", "VALIDATING", "PLANNING", "QUEUED", "RUNNING", "VERIFYING"}')]),
      ("Show why interrupted runs are not resumed",
       [code("def resume_run(self, run_id):", "return False  # Uncertain provider calls must never be replayed blindly.")]),
      ("Reference the restart test", [code("async def test_restart_preserves_runs_counters_and_reservations")]),
      ("Cross-check the design section on interruption and cost", [mem("mem_fx_architecture#۱۲. قطع ارتباط، تکرار و هزینه")])])

task("H06", "fa",
     "تیم Agent سفارشی چه اعتبارسنجی‌هایی دارد؟",
     [("الگوی شناسهٔ Agent سفارشی نشان داده شود", [code('id: str = Field(pattern=r"^custom_[a-z0-9]{8,32}$")')]),
      ("اعتبارسنجی شناسهٔ تکراری و نقش‌ها نشان داده شود",
       [code("def validate_team(self):", "raise ValueError('شناسهٔ Agent تکراری است.')")]),
      ("اعتبارسنجی مدل مجاز نشان داده شود",
       [code("def known_model(cls, value):", "raise ValueError('مدل انتخاب‌شده در فهرست مدل‌ها نیست.')")]),
      ("سقف تعداد Agent سفارشی نشان داده شود",
       [code("custom_agents: list[CustomAgent] = Field(default_factory=list, max_length=5)")]),
      ("حفاظت موتور از شناسهٔ رزروشده نشان داده شود", [code("raise ValueError('Reserved custom agent identifier')")])])

task("H07", "en",
     "Where are the hard execution limits (calls, runtime, subtasks) defined and enforced?",
     [("Show the settings that define the limits",
       [code("max_root_calls: int = 20", "max_active_runtime_seconds: int = 20 * 60  # 20 minutes")]),
      ("Show the per-run call limit enforcement", [code('if run["total_calls"] >= 20:')]),
      ("Show the runtime timeout enforcement", [code("async with asyncio.timeout(remaining):")]),
      ("Show the subtask count enforcement",
       [code('raise DAGValidationError(f"Maximum {max_subtasks} subtasks allowed. Found: {len(subtasks)}")')])])

task("H08", "fa",
     "چگونه فایل‌های حساس مثل env. و پوشه‌های مخفی از snapshot پروژه کنار گذاشته می‌شوند؟",
     [("فهرست نام فایل‌های حساس نشان داده شود", [code('SENSITIVE_CONTEXT_NAMES = {".env",')]),
      ("شرط حذف فایل حساس در ساخت snapshot نشان داده شود",
       [code("and path.name.lower() not in SENSITIVE_CONTEXT_NAMES")]),
      ("شرط حذف پوشه‌های مخفی و ignore نشان داده شود",
       [code('part.startswith(".") or part.lower() in IGNORED_CONTEXT_DIRS')]),
      ("آزمون snapshot معرفی شود",
       [code("def test_project_snapshot_prioritizes_source_and_skips_hidden_cache")])])

task("H09", "en",
     "Check how the budget cap is enforced before a provider call is made and what the run state becomes if it is exceeded",
     [("Show the atomic reservation invariant",
       [code("def reserve_budget(", "Invariant: spent_known + held_unknown + reserved_cost + amount <= budget_cap")]),
      ("Show the error raised when the reservation fails", [code("Budget cap exceeded!")]),
      ("Show how the engine maps the error to a run state",
       [code("except BudgetExceededError:", 'self._transition(run_id, "PAUSED_BUDGET",')]),
      ("Reference the budget cap test", [code("async def test_budget_cap_stops_call_when_insufficient")]),
      ("Use the design section on budget", [mem("mem_fx_mvp-design#۶. بودجه و قابلیت ارائه‌دهنده")])])

task("H10", "fa",
     "پیام خطایی که هنگام شکست اجرا به کاربر نشان داده می‌شود بر چه اساسی انتخاب می‌شود؟",
     [("تشخیص خطای اتصال از روی متن خطا نشان داده شود",
       [code('if any(k in err_str for k in ("connection", "connect", "ssl", "timeout", "network", "wrong_version_number")):')]),
      ("پیام خطای ساختار پاسخ مدل نشان داده شود", [code('reason = "پاسخ مدل یا ساختار برنامه معتبر نبود."')]),
      ("پیام پایان زمان مجاز نشان داده شود",
       [code('self._transition(run_id, "FAILED", "زمان مجاز اجرا به پایان رسید.")')]),
      ("پیام گراف نامعتبر نشان داده شود", [code('"گراف وابستگی کارها (DAG) نامعتبر است."')])])

HOLDOUT = H
