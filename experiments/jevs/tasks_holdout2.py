"""HOLDOUT-2 tasks (G01-G12). Written BEFORE JEVS v2 was designed, on code areas not used by the dev set or
holdout-1. v2 is tuned only on T01-T15; holdout-1 and holdout-2 are each evaluated once at the end.
Same rules as tasks.py.
"""
import tasks as _t

_t.T = []
G = _t.T
task, code, mem = _t.task, _t.code, _t.mem

task("G01", "en",
     "How many agents can run at the same time, and how is that limit enforced?",
     [("Show the limiter construction and its default",
       [code("def __init__(self, max_concurrent: int = 2):", "self.semaphore = asyncio.Semaphore(max_concurrent)")]),
      ("Show how the peak concurrency is tracked", [code("if self.active_count > self.max_observed_concurrency:")]),
      ("Show the configured limit in settings", [code("max_concurrent_agents: int = 2")]),
      ("Show where the engine waits for a slot before a provider call", [code("await self.limiter.acquire()")]),
      ("Reference the concurrency test", [code("async def test_concurrency_never_exceeds_two")])])

task("G02", "fa",
     "وقتی کاربر اجرای یک گفت‌وگوی محلی را متوقف می‌کند، فرایند CLI و زیرفرایندهایش چگونه بسته می‌شوند؟",
     [("بستن درخت فرایند و زیرفرایندها نشان داده شود",
       [code("def kill_tree(process):", "children = root.children(recursive=True)")]),
      ("تابع توقف اجرای محلی و خطای اجرای پایان‌یافته نشان داده شود",
       [code("async def cancel(self, ident):", 'raise RuntimeError("این اجرا پایان یافته است.")')]),
      ("حالت توقف پیش از شروع اجرا نشان داده شود",
       [code("# A task cancelled before its first instruction has not entered execute/finally.")])])

task("G03", "en",
     "What happens to local chat turns that were still running when the app was closed?",
     [("Show the recovery update applied to unfinished turns",
       [code("UPDATE local_turns SET state='interrupted', error=?, updated_at=? WHERE state IN ('queued','running')")]),
      ("Show the message stored for the user", [code("برنامه در اجرای قبلی بسته شد. ادامه فقط با پیام تازه انجام می‌شود.")]),
      ("Show where recovery runs at startup", [code("local_runtime.recover()")])])

task("G04", "fa",
     "پذیرش خروجی توسط کاربر چگونه ثبت می‌شود و چه چیزی را تغییر می‌دهد؟",
     [("مسیر API پذیرش و شرط آماده‌بودن خروجی نشان داده شود",
       [code("async def accept(run_id: str):", 'raise HTTPException(409, "این خروجی هنوز آمادهٔ پذیرش نیست.")')]),
      ("ثبت hash خروجی پذیرفته‌شده نشان داده شود",
       [code("digest = hashlib.sha256(content.encode()).hexdigest()", "INSERT OR REPLACE INTO acceptances VALUES (?,?,?)")]),
      ("تکمیل تسک پروژهٔ مرتبط نشان داده شود",
       [code("UPDATE project_tasks SET status='COMPLETED', updated_at=? WHERE last_run_id=?")]),
      ("جدول پذیرش‌ها نشان داده شود", [code("CREATE TABLE IF NOT EXISTS acceptances (")]),
      ("معنای پذیرش انسانی در سند طراحی لحاظ شود", [mem("mem_fx_architecture#۷. معنای Accept، Reject و Escalate")])])

task("G05", "en",
     "What price is assumed for a model that is missing from the price table, and why?",
     [("Show the fallback price and its rationale",
       [code("# Fallback to high rate to prevent accidental budget overrun if unknown",
             "return ModelPrice(input_per_million=10.0, output_per_million=50.0)")]),
      ("Show a regular entry of the price table",
       [code('"gpt-5.6-luna": ModelPrice(input_per_million=0.2, output_per_million=1.2),')]),
      ("Show how a price turns into a cost", [code("in_cost = (input_tokens / 1_000_000.0) * self.input_per_million")])])

task("G06", "fa",
     "تغییر وضعیت هر run چگونه در جدول رویدادها ثبت و شماره‌گذاری می‌شود؟",
     [("محاسبهٔ شمارهٔ بعدی رویداد نشان داده شود",
       [code("SELECT COALESCE(MAX(sequence), 0) + 1 AS next_seq FROM events WHERE run_id = ?")]),
      ("درج رویداد با وضعیت قبلی و بعدی نشان داده شود",
       [code("INSERT INTO events (run_id, sequence, from_state, to_state, reason, metadata, created_at)")]),
      ("ثبت زمان پایان برای وضعیت‌های نهایی نشان داده شود", [code("completed_at = now if to_state in (")]),
      ("محل فراخوانی از موتور نشان داده شود", [code("self.repo.update_run_status(run_id, state, reason, metadata)")])])

task("G07", "en",
     "How does Flux decide between the demo provider and the live GapGPT provider?",
     [("Show how the live flag is derived from the environment",
       [code('enable_live_raw = os.environ.get("FLUX_ENABLE_LIVE", "1" if api_key else "0")',
             'default_prov = "gapgpt" if enable_live_env else "fake"')]),
      ("Show how .env files are loaded without overriding existing variables",
       [code("def load_env_files():", "if k and k not in os.environ:")]),
      ("Show the engine factory that picks the provider",
       [code("if enable_live or (settings.enable_live and settings.gapgpt_api_key):")])])

task("G08", "fa",
     "در گفت‌وگوی محلی، دسترسی فقط-خواندنی چه ابزارها و مجوزهایی را محدود می‌کند؟",
     [("سیاست sandbox برای Codex نشان داده شود",
       [code('policy = "read-only" if chat["access"] == "read" else "workspace-write"')]),
      ("فهرست ابزارهای مجاز برای Claude نشان داده شود",
       [code('tools = "Read,Glob,Grep" if chat["access"] == "read" else "Read,Glob,Grep,Edit,Write,Bash,WebFetch,WebSearch"')]),
      ("دستور فقط-خواندنی در متن درخواست نشان داده شود",
       [code("This turn is read-only: do not modify files or execute commands that write data.")])])

task("G09", "en",
     "Why are API key environment variables removed before launching a local CLI agent, and how is the CLI found?",
     [("Show the reason and the removal loop",
       [code("# Account login only: an inherited API key must not silently change the billing route.", "env.pop(name, None)")]),
      ("Show which Anthropic variables are removed",
       [code('"ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL", "CLAUDECODE",')]),
      ("Show how the CLI executable is located",
       [code("def find_cli(provider):", "PATH, native installs, and the bundled Codex installation; never read auth files.")])])

task("G10", "fa",
     "اجرای تسک پروژه چه درخواستی به موتور می‌فرستد و اگر تسک معیار پذیرش نداشته باشد چه می‌شود؟",
     [("مسیر اجرای تسک و معیار پیش‌فرض نشان داده شود",
       [code("async def run_project_task(ident: str, task_id: str):", 'criteria = ["تکمیل وظیفه با دقت و گزارش شفاف مراحل انجام‌شده."]')]),
      ("محدودهٔ کار ساخته‌شده برای پوشهٔ پروژه نشان داده شود",
       [code('"scope": [f"انجام تسک در پوشهٔ پروژهٔ {proj[\'name\']}"],')]),
      ("شناسهٔ اجرای ساخته‌شده نشان داده شود", [code('run_task_id = f"pt_{task_id[:8]}_{uuid.uuid4().hex[:6]}"')]),
      ("آزمون اجرای تسک پروژه معرفی شود", [code("async def test_project_task_creation_and_execution")])])

task("G11", "en",
     "What does the run detail endpoint return, and which fields are hidden from the client?",
     [("Show the hidden fields", [code("def detail(run_id):", 'if k not in ("task_payload", "idempotency_key")},')]),
      ("Show the call history query",
       [code("SELECT agent_role,model_id,status,attempt,latency_ms FROM agent_calls WHERE run_id=? ORDER BY created_at")]),
      ("Show that acceptance state is included", [code('"acceptance": workspace.acceptance(run_id),')])])

task("G12", "fa",
     "پروفایل‌های اجرا از low تا team چه مدل‌ها و سقف توکنی دارند و پیش‌فرض کدام است؟",
     [("جدول پروفایل‌ها و مدل‌های low نشان داده شود",
       [code('"low": ExecutionProfile(LOW_MODELS, 2500, 8000, 4000),', 'LOW_MODELS = dict.fromkeys(LEGACY_MODELS, "gpt-5.6-luna")')]),
      ("مقدار پیش‌فرض workflow در قرارداد کار نشان داده شود",
       [code('workflow: Literal["low", "medium", "high", "auto", "team"] = "low"')]),
      ("آزمون پیش‌فرض معرفی شود", [code("def test_default_is_low")]),
      ("محاسبهٔ سقف توکن خروجی هر زیرکار نشان داده شود",
       [code("token_limit = max(min(subtask.max_output_tokens, profile.worker_tokens), 512)")])])

HOLDOUT2 = G
