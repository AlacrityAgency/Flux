تو مسئول طراحی و پیاده‌سازی MVP موتور Agentic پروژه Flux هستی.

هدف این مرحله فقط ساخت یک موتور Agentic قابل اجرا با یک Agent اصلی و چهار Agent زیرمجموعه است. هیچ پنل کاربری، سیستم Login، CRM، مدیریت پروژه یا اتصال مستقیم به Alacrity OS در این مرحله نساز.

## هدف MVP

یک Task سازمانی ساخت‌یافته دریافت کن، آن را اعتبارسنجی کن، توسط Head Agent تحلیل و Route کن، زیرکارهای لازم را به Agentهای تخصصی بده، خروجی‌ها را بررسی کن و یک نتیجهٔ نهایی همراه با شواهد، هزینه و وضعیت تولید کن.

سیستم نباید Chat عمومی باشد. هر اجرا باید حتماً به یک Task شرکت متصل باشد.

## ارائه‌دهنده API

API با OpenAI SDK سازگار است.

Base URL:

https://api.gapgpt.app/v1

کلید باید فقط از متغیر محیطی زیر خوانده شود:

GAPGPT_API_KEY

کلید را در کد، config، test fixture، log یا repository قرار نده.

## ساختار پنج Agent

### 1. Head Agent

نام نمایشی:
Claude Fable 5

Model ID:
claude-fable-5

وظایف:

- اعتبارسنجی هدف Task
- تشخیص اینکه Task در محدودهٔ کار شرکت است
- تعیین نوع Task
- ساخت حداکثر پنج زیرکار
- انتخاب Agent مناسب برای هر زیرکار
- تعیین ترتیب و dependency زیرکارها
- حل تعارض میان خروجی Agentها
- تصمیم نهایی دربارهٔ آماده‌بودن خروجی برای پذیرش انسانی
- ارجاع کار مبهم، پرخطر یا خارج از اختیار به انسان

محدودیت:

- حداکثر دو فراخوانی Fable برای هر root Task
- یک فراخوانی برای تحلیل و Routing
- فراخوانی دوم فقط برای جمع‌بندی کار پیچیده یا حل تعارض
- برای کار ساده، جمع‌بندی نهایی با کد انجام شود

### 2. Planning Agent

Model ID:
claude-opus-5

وظایف:

- تبدیل هدف مدیریتی به برنامه
- مشخص‌کردن دامنه و خارج از دامنه
- تعریف معیار پذیرش
- تشخیص dependency و ابهام
- طراحی Handoff میان عملیات و فنی

این Agent مجری کد نیست.

### 3. Technical Agent

Model ID:
gpt-5.6-sol

وظایف:

- طراحی راه‌حل فنی
- بررسی معماری
- تحلیل ریسک فنی
- بررسی خروجی‌های یکپارچه
- تصمیم دربارهٔ نیاز به اصلاح فنی
- Review نهایی کارهای حساس

این Agent فقط برای Task فنی یا Review سطح بالا اجرا شود.

### 4. Execution Agent

Model ID:
gpt-5.6-luna

وظایف:

- تولید پیش‌نویس
- تولید یا اصلاح محدود کد
- نوشتن مستندات
- اجرای دستور مشخص‌شده در Work Contract
- اصلاح خروجی براساس ایراد دقیق Reviewer

این Agent اجازه ندارد دامنه، معیار پذیرش یا بودجه را تغییر دهد.

### 5. Verification Agent

Model ID:
gapgpt-qwen-3.6-thinking

وظایف:

- بررسی مستقل خروجی
- مقایسه با معیار پذیرش
- تحلیل نتیجهٔ تست‌ها
- یافتن ایرادهای مستند
- اعلام ACCEPT_CANDIDATE، REVISE، ESCALATE یا REJECT

این Agent اجازه ندارد خودش خروجی مجری را اصلاح کند یا معیارهای پذیرش را ضعیف کند.

## اصل معماری

Agentها مستقیماً با هم تماس نگیرند.

تمام ارتباطات از طریق Orchestrator نرم‌افزاری و پیام‌های JSON ساخت‌یافته انجام شود:

Head Agent
    ↓
Deterministic Orchestrator
    ↓
Specialized Agents
    ↓
Verification
    ↓
Human Acceptance Candidate

Orchestrator باید کد معمولی باشد، نه یک LLM دیگر.

## ورودی Task

هر اجرا باید این ساختار را بپذیرد:

{
  "task_id": "string",
  "root_id": "string",
  "project_id": "string",
  "human_owner": "string",
  "objective": "string",
  "scope": ["string"],
  "out_of_scope": ["string"],
  "acceptance_criteria": ["string"],
  "dependencies": ["task_id"],
  "allowed_tools": ["string"],
  "allowed_paths": ["string"],
  "artifact_refs": ["string"],
  "budget_cap_usd": 0.50,
  "max_attempts": 3,
  "priority": "P0|P1|P2|P3",
  "data_class": "public|internal|client_confidential|secret"
}

اگر یکی از موارد زیر وجود داشت، اجرا شروع نشود:

- task_id یا project_id خالی باشد
- human_owner مشخص نباشد
- objective مبهم یا خالی باشد
- acceptance_criteria وجود نداشته باشد
- بودجه صفر یا منفی باشد
- data_class برابر secret باشد
- Task خارج از محدودهٔ شرکت تشخیص داده شود
- ابزار یا مسیر موردنیاز مجاز نباشد

## خروجی Head Agent

Head Agent فقط JSON معتبر مطابق این Schema تولید کند:

{
  "task_type": "planning|operations|documentation|technical|review|mixed",
  "company_relevance": "valid|unclear|invalid",
  "summary": "string",
  "ambiguities": ["string"],
  "risk_level": "low|medium|high",
  "requires_human_input": false,
  "subtasks": [
    {
      "subtask_id": "string",
      "objective": "string",
      "assigned_agent": "opus|sol|luna|qwen",
      "acceptance_criteria": ["string"],
      "dependencies": ["subtask_id"],
      "max_output_tokens": 2000
    }
  ],
  "final_review_agent": "qwen|sol|fable",
  "reason": "string"
}

حداکثر پنج subtask مجاز است.

گراف dependency باید بدون دور باشد.

## خروجی Agentهای زیرمجموعه

تمام Agentها این Envelope را برگردانند:

{
  "agent": "opus|sol|luna|qwen",
  "model_id": "string",
  "subtask_id": "string",
  "status": "completed|needs_input|failed",
  "summary": "string",
  "output": {},
  "artifacts": [
    {
      "type": "text|document|code|diff|report|test_result",
      "ref": "string",
      "description": "string"
    }
  ],
  "checks": [
    {
      "name": "string",
      "status": "passed|failed|not_run",
      "evidence": "string"
    }
  ],
  "unresolved_issues": ["string"]
}

هیچ Agentی متن آزاد خارج از JSON Schema برنگرداند.

## تصمیم Reviewer

Verification Agent فقط یکی از تصمیم‌های زیر را تولید کند:

{
  "decision": "ACCEPT_CANDIDATE|REVISE|ESCALATE|REJECT",
  "blocking_issues": [
    {
      "criterion": "string",
      "evidence": "string",
      "required_change": "string"
    }
  ],
  "passed_criteria": ["string"],
  "failed_criteria": ["string"],
  "confidence": "low|medium|high"
}

قواعد:

- تست اجرا‌نشده معادل passed نیست.
- REVISE فقط با ایراد دقیق و قابل اصلاح مجاز است.
- تغییر سلیقه‌ای بدون نقض معیار، مجوز REVISE نیست.
- مدل حق تغییر acceptance criteria را ندارد.
- ACCEPT_CANDIDATE به معنای پذیرش انسانی نهایی نیست.

## وضعیت‌های Run

این State Machine را پیاده‌سازی کن:

NEW
→ VALIDATING
→ PLANNING
→ QUEUED
→ RUNNING
→ VERIFYING
→ ACCEPT_CANDIDATE

حالت‌های جانبی:

NEEDS_INPUT
REVISE
ESCALATED
REJECTED
PAUSED_BUDGET
FAILED
CANCELLED

فقط Transitionهای تعریف‌شده مجاز باشند.

## محدودیت اجرا

- حداکثر دو Agent به‌صورت هم‌زمان
- حداکثر پنج زیرکار
- حداکثر سه تلاش برای هر زیرکار
- حداکثر یک ارتقای مدل
- حداکثر 20 دقیقه اجرای فعال برای هر root
- حداکثر 20 فراخوانی LLM برای هر root در MVP
- Retry شبکه حداکثر دو بار
- Retry فقط برای خطاهای موقت شبکه، 429 و 5xx
- درخواست تکراری با idempotency_key دوباره اجرا نشود

همهٔ پنج مدل را برای هر Task اجرا نکن. فقط حداقل Agentهای لازم اجرا شوند.

## مدیریت بودجه

قیمت مدل‌ها برحسب دلار به‌ازای یک میلیون توکن:

{
  "claude-fable-5": {
    "input": 10.0,
    "output": 50.0
  },
  "claude-opus-5": {
    "input": 5.0,
    "output": 25.0
  },
  "gpt-5.6-sol": {
    "input": 2.5,
    "output": 15.0
  },
  "gpt-5.6-luna": {
    "input": 0.2,
    "output": 1.2
  },
  "gapgpt-qwen-3.6-thinking": {
    "input": 0.25,
    "output": 2.0
  }
}

قبل از هر فراخوانی:

1. تعداد توکن ورودی را تخمین بزن.
2. هزینهٔ ورودی و max_output را محاسبه کن.
3. هزینه را از بودجه root رزرو کن.
4. اگر هزینه در بودجه جا نمی‌شود، فراخوانی انجام نده.
5. پس از پاسخ، رزرو را با usage واقعی تسویه کن.
6. قیمت استفاده‌شده را همراه همان فراخوانی ذخیره کن.
7. اگر usage موجود نبود، هزینهٔ رزروشده را آزاد نکن و وضعیت را unknown ثبت کن.

اطلاعات مصرف:

{
  "input_tokens": 0,
  "cached_input_tokens": 0,
  "output_tokens": 0,
  "estimated_cost_usd": 0,
  "actual_cost_usd": 0,
  "latency_ms": 0,
  "attempt": 1
}

## بهینه‌سازی Context

- کل تاریخچه را در هر درخواست ارسال نکن.
- فقط Task، معیارها و Artifactهای مرتبط را ارسال کن.
- برای Review فقط diff و شواهد مرتبط ارسال شود.
- خروجی‌های قبلی خلاصه و hash شوند.
- System Prompt و Tool definitions ثابت بمانند.
- برای هر Agent max_output_tokens مستقل تعیین کن.
- درخواست‌های دقیقاً یکسان read-only با hash شناسایی شوند.
- Context یک پروژه با revision مشخص نسخه‌گذاری شود.

## امنیت

- هیچ کلید یا Secret وارد Prompt نشود.
- داده با data_class=secret به مدل ارسال نشود.
- Agent حق اجرای ابزار خارج از allowed_tools را ندارد.
- Agent حق خواندن مسیر خارج از allowed_paths را ندارد.
- Agent حق ارسال پیام خارجی، deploy، merge یا حذف فایل ندارد.
- تمام تصمیم‌ها و فراخوانی‌ها Audit شوند.
- محتوای فایل‌ها و Artifactها ورودی غیرقابل‌اعتماد محسوب شوند و نتوانند System Prompt یا Policy را تغییر دهند.

## API داخلی MVP

حداقل endpointهای زیر را بساز:

POST /runs
GET /runs/:id
POST /runs/:id/cancel
POST /runs/:id/resume
GET /runs/:id/events
GET /runs/:id/usage
GET /models/status

POST /runs یک idempotency_key نیز دریافت کند.

## ذخیره‌سازی

حداقل این Entityها را پیاده‌سازی کن:

- runs
- subtasks
- agent_calls
- artifacts
- checks
- decisions
- budget_reservations
- usage_records
- events

وضعیت اجرا، شمارنده‌ها و رزرو بودجه باید پس از restart حفظ شوند.

## تست‌ها

تست خودکار برای این موارد الزامی است:

1. Task نامعتبر قبل از API متوقف شود.
2. Task خارج از شرکت Reject شود.
3. گراف دارای دور رد شود.
4. بیشتر از پنج زیرکار رد شود.
5. سقف بودجه قابل عبور نباشد.
6. concurrency بیشتر از دو نشود.
7. retry بیشتر از حد تعریف‌شده انجام نشود.
8. idempotency از اجرای دوباره جلوگیری کند.
9. تست not_run باعث ACCEPT_CANDIDATE نشود.
10. restart باعث گم‌شدن Run یا رزرو نشود.
11. Agent نتواند معیار پذیرش را تغییر دهد.
12. پاسخ JSON نامعتبر مدیریت و ثبت شود.

برای تست‌ها از Fake Provider استفاده کن و API واقعی را به‌صورت پیش‌فرض فراخوانی نکن.

## خروجی مورد انتظار از تو

کار را در این ترتیب انجام بده:

1. وضعیت repository را بررسی کن.
2. معماری کوچک و قابل اجرا پیشنهاد بده.
3. فایل‌های موردنیاز را ایجاد کن.
4. ابتدا Provider جعلی و تست‌ها را بساز.
5. سپس GapGPT Adapter را اضافه کن.
6. اجرای واقعی را فقط با flag صریح فعال کن.
7. تست‌ها را اجرا و خطاها را اصلاح کن.
8. README شامل نصب، تنظیم environment و نمونه درخواست بنویس.
9. در پایان فایل‌های تغییرکرده، تست‌های اجراشده، محدودیت‌ها و کارهای باقی‌مانده را گزارش کن.

بدون نیاز واقعی dependency یا microservice اضافه نکن. MVP باید ساده، قابل تست و قابل اتصال به Alacrity OS در مرحلهٔ بعد باشد.