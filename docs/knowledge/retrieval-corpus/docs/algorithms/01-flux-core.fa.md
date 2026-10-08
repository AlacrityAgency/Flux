# الگوریتم اولیهٔ کامل Flux: قرارداد تا پذیرش خروجی

نسخه: ۱٫۰ طراحی؛ تاریخ: ۱ اکتبر ۲۰۲۶؛ پروژهٔ مرجع: `alacrity-flux`.

این مشخصات، هستهٔ محصول سازمانی مقصد است. `FluxEngine` فعلی یک دمو چندنقشی و `LocalRuntime` فعلی یک مسیر گفتگوی CLI هستند؛ ادغام آن‌ها و الگوریتم زیر در این نوبت انجام نشده است. وضعیت جاری و شواهد در [دفتر HEAD](00-head-brief.fa.md) مشخص شده‌اند.

## ۱. خروجی و حدود مسئولیت

ورودی: درخواست انسانی یا رخداد مجاز یک connector. خروجی: artifact نسخه‌دار، گزارش شواهد، نتیجهٔ بازبین و Head، هزینه/زمان/ابهام‌های باقی‌مانده و رکورد پذیرش انسانی همان نسخه. انتشار، merge، پرداخت یا ارسال بیرونی، اقدام‌های مستقل با مجوز مربوط‌اند؛ پذیرفته‌شدن متن خروجی مجوز آن‌ها را جعل نمی‌کند.

Head پیشنهاد برنامه و اقدام می‌دهد. موتور قطعی مسئول اعتبارسنجی قرارداد، مجوز، نسخه، dependency، بودجه، شمارنده، صف، ثبت رخداد و dispatch است. مدل نمی‌تواند با متن پاسخ، مجوز یا سقف را تغییر دهد. برای کار از قبل مجاز، approval معتبر قبلی کافی است؛ تکرار درخواست مجوز در هر فراخوانی لازم نیست.

## ۲. اجزای لازم

| جزء | مسئولیت | دادهٔ پایدار |
|---|---|---|
| Intake | حذف تکرار و تبدیل درخواست به قرارداد | request/event key و payload hash |
| Contract service | freeze هدف، دامنه، معیار و مالک | revision و contract hash |
| Policy gate | tenant، ACL، ابزار، مسیر، مقصد و تفویض | policy/authorization revision |
| Project mind / JEV | وضعیت پروژه، تصمیم‌های قبلی و retrieval | منبع، revision، assessment |
| Head و Head بخش | برنامه و پیشنهاد تصمیم | Plan/DecisionRecord ساخت‌یافته |
| Scheduler | DAG، ظرفیت، lease و وابستگی | task state، lease و checkpoint |
| Budget controller | admission و accounting | رزرو/مصرف/unknown برای همهٔ ancestorها |
| Model gateway | capability و response validation | request/response/usage metadata |
| Tool gateway | اقدام دارای مجوز و نتیجهٔ قابل بررسی | operation key، parameter hash، نتیجه |
| Review service | معیارمحور و مستقل از مجری | criterion results و artifact hash |
| Acceptance service | پذیرش/رد نسخه توسط انسان مجاز | approval و scope و زمان |
| Event log / outbox | رکورد تراکنشی و dispatch قابل بازیابی | sequence، event ID، delivery state |

در نصب محلی تک‌کاربره، tenant می‌تواند یک مقدار ثابت باشد؛ مهاجرت به چندمشتری نباید این مقدار را از متن مدل بگیرد. نقش عامل با حساب اجرا و مدل جدا ذخیره می‌شود.

## ۳. قرارداد مادر

```json
{
  "tenant_id": "alacrity-internal",
  "department_id": "technical",
  "project_id": "alacrity-flux",
  "root_task_id": "root-20261001-001",
  "task_id": "task-001",
  "parent_task_id": null,
  "request_key": "user-request-unique",
  "contract_revision": 1,
  "policy_revision": 1,
  "human_owner": "authorized-user-id",
  "objective": "مدیریت پروژه و حافظه داخل رابط فعلی باز شود",
  "scope": ["local UI", "existing project/memory APIs"],
  "out_of_scope": ["migration of production memory", "JEV integration"],
  "acceptance_criteria": [
    {"criterion_id":"C1","text":"دکمه بدون خروج از رابط فعلی پنل را باز کند","required":true,"evidence_type":"test_execution"},
    {"criterion_id":"C2","text":"پروژه و یادداشت ذخیره‌شده از API موجود قابل مدیریت باشند","required":true,"evidence_type":"test_execution"}
  ],
  "allowed_tools": ["read_workspace", "edit_workspace", "test"],
  "allowed_paths": ["src/flux/static", "tests", "tools", "docs"],
  "allowed_destinations": [],
  "data_class": "internal",
  "processing_policy": "approved_providers_only",
  "limits": {"max_children":5,"max_depth":1,"max_generation_attempts":3,"max_calls":32,"max_active_seconds":1200,"max_concurrency":2},
  "budget_ref": "budget-policy-revision-1",
  "source_revision_manifest": "manifest-hash",
  "expected_artifacts": ["reviewable diff", "test report", "build status"],
  "start_authorization_ref": "existing-human-request",
  "state": "REGISTERED"
}
```

اعداد limits بالا پیش‌فرض **پیشنهادی** قابل تنظیمند و از چارت/طراحی اولیه آمده‌اند؛ کد legacy فعلی مثلاً سقف ۲۰ تماس و runtime محلی فقط یک job همزمان دارد. این سند ادعای اعمال ۳۲ تماس یا دو CLI همزمان در نسخهٔ جاری نمی‌کند. سقف‌ها برای کل مادر، زیرکار و role مشخص می‌شوند؛ بدون fallback نامرئی. معیارهای typed، مقصد schema آینده‌اند؛ `TaskInput` امروز `List[str]` دارد.

کلید idempotency با `(tenant_id, request_key)` یکتا می‌شود. تکرار کلید با payload متفاوت خطاست؛ تکرار با همان hash، همان task را برمی‌گرداند. `project_id` باید به پروژهٔ موجود و مجاز resolve شود. نام مشابه یا cwd همسان جای هویت پروژه را نمی‌گیرد.

## ۴. ناورداهای هسته

1. معیار و دامنهٔ مادر با خروجی مدل تغییر نمی‌کنند. تغییر انسانی معتبر، revision جدید می‌سازد و اثرش بر taskهای جاری مشخص می‌شود.
2. هر task یک tenant/project و owner دارد؛ مسیر بین بخش‌ها در همان مادر است. محتوای پروژهٔ دیگر فقط با authorization ثبت‌شده وارد می‌شود.
3. مجموع مصرف settled، reservation باز و held_unknown در تمام ancestorهای بودجه بررسی می‌شود؛ dispatch بدون admission ممنوع است.
4. زیرکار، escalation، تغییر نقش، retry و resume شمارنده‌های مادر را صفر نمی‌کنند.
5. وابستگی به نسخهٔ خروجی معتبر است؛ پایان process یا متن «done» dependency را کافی نمی‌کند.
6. هر اثر بیرونی یک operation key و parameter/artifact hash دارد. نتیجهٔ نامعلوم بدون reconciliation تکرار نمی‌شود.
7. test ثبت‌نشده/اجرانشده وضعیت unknown دارد. ارجاع به فایل تست، شاهد اجرا نیست.
8. `ACCEPT_CANDIDATE` به معنای پیشنهاد پذیرش است؛ فقط انسان مجاز یا policy تفویض انسانی از پیش مصوب می‌تواند پذیرش لازم را ثبت کند. وایت‌پیپر پیش‌فرض پایان کار را انسانی می‌گذارد.
9. تغییر artifact پس از review/approval، hash قبلی را از نسخهٔ فعلی جدا و approval مؤثر قبلی را نامعتبر می‌کند.
10. snapshot config اجرا قابل بازتولید است؛ تغییر چارت یا مدل حین اجرا، رخداد و revision جدید می‌خواهد.

## ۵. ماشین حالت پیشنهادی

| حالت | رویداد مجاز و مقصد | gate |
|---|---|---|
| REGISTERED | validated → READY؛ missing → NEEDS_INFO؛ invalid → FAILED | قرارداد و هویت |
| NEEDS_INFO | clarification accepted → READY؛ cancel → CANCELLED | حفظ قرارداد/ثبت revision |
| READY | dispatched → RUNNING؛ review checkpoint → REVIEWING؛ auth missing → WAITING_APPROVAL؛ budget missing → BLOCKED_BUDGET | admission اتمی؛ REVIEWING فقط با checkpoint.phase=review و نسخهٔ معتبر |
| RUNNING | artifact complete → REVIEWING؛ ambiguity → NEEDS_INFO؛ permission blocked → WAITING_APPROVAL؛ error → RECOVERING/FAILED | نتیجهٔ واقعی و checkpoint |
| REVIEWING | all required pass → ACCEPT_CANDIDATE؛ fixable → NEEDS_REVISION؛ conflict → ESCALATED | معیار، شاهد و hash |
| NEEDS_REVISION | eligible retry → READY؛ exhausted → ESCALATED؛ budget missing → BLOCKED_BUDGET | تصمیم تغییر روش و شمارنده |
| WAITING_APPROVAL | valid scoped approval → READY؛ rejection → ESCALATED/CANCELLED | actor و expiry و نسخه |
| BLOCKED_BUDGET | revised budget → READY؛ stop → CANCELLED | افزایش توسط انسان مجاز |
| ACCEPT_CANDIDATE | accept exact version → ACCEPTED؛ reject with issue → NEEDS_REVISION/ESCALATED | پذیرش همان artifact |
| ESCALATED | human resolution → READY/NEEDS_INFO؛ terminate → FAILED/CANCELLED | دستور روشن با حفظ شمارنده |
| RECOVERING | known success → REVIEWING یا checkpoint بعد؛ safe resumable → READY؛ unknown effect → WAITING_APPROVAL؛ permanent failure → FAILED | reconciliation |
| ACCEPTED / FAILED / CANCELLED | پایان؛ ادامهٔ جدید قرارداد مرتبط می‌خواهد | رکورد نهایی تغییر پنهان ندارد |

لغو کارهای غیرنهایی از هر حالت مجاز است. artifactهای موجود و رزروهای unknown حفظ می‌شوند؛ لغو به معنی برگشت فایل یا حذف اثر بیرونی نیست. `WAITING_APPROVAL` برای آغاز/ابزار است؛ پذیرش نهایی در `ACCEPT_CANDIDATE` منتظر می‌ماند تا با تأیید آغاز اشتباه نشود. اگر review متوقف شود، `checkpoint.phase=review` ثبت می‌شود؛ بازگشت به READY نباید تولید را بی‌دلیل تکرار کند.

حالت‌های امروز legacy از `state_machine.VALID_TRANSITIONS` شامل NEW، VALIDATING، PLANNING، QUEUED، RUNNING، VERIFYING، REVISE و ... است. حالت‌های local turn شامل queued/running/completed/failed/cancelled/needs_input/interrupted است. نگاشت UI آینده باید این سه namespace را جدا نگه دارد؛ تنها عوض‌کردن labelهای امروز، مهاجرت ماشین حالت نیست.

## ۶. الگوریتم اصلی

```text
ON_REQUEST(actor, input, request_key):
    authenticate actor
    canonical = validate_and_canonicalize(input)
    authorize actor for canonical.tenant/project and requested scope
    payload_hash = hash(canonical)
    atomically:
        if same tenant/request_key exists:
            require prior.payload_hash == payload_hash
            return prior.task
        contract = freeze_contract(canonical, human_authorization)
        append REGISTERED event + contract hash
    if consequential ambiguity exists:
        persist NEEDS_INFO with precise missing field
        return
    enqueue PLAN_OR_TEMPLATE(contract)

PLAN_OR_TEMPLATE(contract):
    if valid approved deterministic template covers objective and criteria:
        plan = instantiate template under current contract
    else:
        evidence = JEV.retrieve_for_planning(contract)
        head_context = contract essentials + source map + gaps + authorized status
        require admission for Head AND essential review reserve
        plan = Head.propose(head_context)
    validate plan schema; all roles resolve to allowed capabilities
    require every required criterion owned by at least one task/review step
    validate unique IDs, DAG, depth/children/root limits, allowed branch routing
    freeze plan revision; append READY events for ready nodes
    do not send every low-level change through central Head

SCHEDULE_NEXT():
    choose fair eligible task by priority, dependencies, tenant/project capacity
    honor review checkpoint before repeating generation
    refresh authorization/source revisions and budget availability
    obtain atomic lease + admission + dispatch intent
    dispatch only after transaction commits
    execute selected bounded model/tool action with operation_id
    persist artifact/tool receipt + usage or unknown reservation
    release lease; queue review if deliverable complete

REVIEW(task, artifact_hash):
    freeze artifact and actual execution evidence
    independent reviewer receives exact criterion IDs/text and sufficient sources
    required checks must be run by authorized executor and linked to same revision
    parse typed result; missing/contradictory fields are UNKNOWN, not PASS
    Head of department checks integration, scope and dependency compatibility
    if all required criteria PASS with valid evidence and no blocking issue:
        persist ACCEPT_CANDIDATE for exact artifact hash
    elif actionable defect and changed repair method and limits permit:
        persist NEEDS_REVISION; route stronger eligible model if policy permits
    else:
        persist ESCALATED or NEEDS_INFO with precise reason

ACCEPT(actor, task_id, artifact_hash, review_revision):
    authenticate and authorize actor against task owner/delegation
    require candidate current; hash and reviews unchanged
    require current mandatory criteria satisfied and policy still valid
    atomically append acceptance + ACCEPTED event + memory proposal/outbox
    publishing or other effect requires independent action admission
```

ثبت outbox تراکنشی و اجرای بیرونی دو مرحله‌اند. اتصال شبکه داخل تراکنش طولانی DB انجام نمی‌شود. exactly-once در تمام سامانه‌های خارجی فرض نمی‌شود؛ کنترل کلید تکرار + reconciliation مبناست. ارسال outbox می‌تواند at-least-once باشد و receiver باید idempotent باشد؛ مقصد فاقد این قابلیت به بررسی نتیجه قبل از تکرار نیاز دارد.

## ۷. ترتیب کار و concurrency

ابتدا taskهای مستقل ready می‌شوند. dependency به artifact قبول‌شده برای مصرف داخلی با معیار stage وصل می‌شود؛ پذیرش نهایی انسان تنها وقتی برای downstream لازم است که قرارداد/policy آن را الزام کند. چنین stage gate از پذیرش نهایی مادر جدا ذخیره می‌شود. قرارداد وظیفه‌ای که به تصمیم انسانی معلق وابسته است، اجازهٔ حدس‌زدن آن تصمیم را نمی‌دهد.

گراف acyclic با topological sort بررسی می‌شود. Head نمی‌تواند cycle را با ادعای «همزمان اجرا کنید» حل کند. scheduler بین tenantها و پروژه‌ها سهم ظرفیت رعایت می‌کند؛ نوبت منتظر approval slot فعال نگه نمی‌دارد. ظرفیت ابزار با مدل متفاوت است: مثلاً workspace مشترک برای ویرایش، lock/path conflict دارد حتی اگر دو فراخوانی مدل مستقل باشند.

قواعد پیش‌فرض conflict: دو writer روی فایل/شاخهٔ مشترک همزمان نشوند؛ reader روی snapshot معتبر قابل موازی‌سازی است؛ آزمون‌های وابسته به محیط مشترک serial یا محیط جدا می‌خواهند. ابزار long-running، PID/process tree خود را ثبت می‌کند. cancel فقط فرایندهای متعلق به همان operation را هدف می‌گیرد.

## ۸. تلاش، اصلاح و ارتقا

`generation_attempt`، `provider_send`، `tool_attempt` و `review_attempt` شمارنده‌های جدا هستند؛ همه زیر سقف call/زمان/هزینهٔ مادر ثبت می‌شوند. سه تلاش تولید پیشنهادی:

1. ارزان‌ترین مدل دارای capability اثبات‌شده برای وظیفهٔ محدود.
2. پس از شکست کیفی مشخص، مدل توانمندترِ مجاز با feedback مربوط به معیار، همان artifact و شاهد.
3. فقط با تصمیم Head و تغییر معنادار روش/تقسیم/Context؛ نبود پیشرفت به escalation می‌انجامد.

خطای transient شبکه، تلاش تولید تازه نیست اما provider send و هزینه/رزرو خود را مصرف می‌کند. پاسخ خالی در adapter فعلی non-transient است؛ طراحی تازه بدون اصلاح accounting و contract tests آن را silently retry نمی‌کند. مدل قوی‌ترِ ناموجود، معیار نامعلوم و کمبود مجوز با ارتقای خیالی حل نمی‌شوند.

## ۹. مرز ابزار و مدل

`ActionRequest` حداقل role/actor، tool، operation_id، canonical parameters، destination، allowed path، data class، source revision، expected effect و approval ref دارد. پیش از dispatch، موتور path واقعی resolve‌شده و symlink را با allowed roots می‌سنجد؛ متن prompt و cwd فقط اطلاع اجرایی‌اند.

اگر gateway نتواند رفتار ابزار یا child process را محدود کند، آن adapter برای کنترل سازمانی strict فاقد capability لازم است. CLI امروز ممکن است چندین ابزار/فراخوانی native داشته باشد که Flux به‌طور مستقل admission نکرده است؛ این مسیر را نمی‌توان صرفاً با preface به gateway ابزار سازمانی تبدیل کرد. لازم است hook/adapter اجرایی یا محیط ایزولهٔ کنترل‌شده با سیاست آزموده‌شده فراهم شود.

منابع RAG، فایل و پیامِ connector untrusted reference هستند. درخواست عملیات داخل آن‌ها به candidate تبدیل می‌شود، سپس همان authorization gate را می‌گذراند؛ نمی‌تواند policy revision یا allowed tools را بازنویسی کند.

## ۱۰. ثبت شاهد و پذیرش

```json
{
  "criterion_id": "C1",
  "status": "PASS",
  "artifact_hash": "sha256:...",
  "source_revision": "revision-or-snapshot-hash",
  "evidence_refs": ["browser-check-id", "screenshot-or-result-hash"],
  "executor": "tool-executor-id",
  "observed_at": "ISO-8601 UTC",
  "limitations": []
}
```

`PASS/FAIL/UNKNOWN/NOT_APPLICABLE` enum معتبر است؛ N/A فقط اگر قرارداد آن را مجاز کند. خلاصهٔ مدل نمی‌تواند جای log آزمون و نسخهٔ fixture را بگیرد. نام تست، فرمان، محیط، exit code، شمار اجرا/skip و hash artifact ثبت می‌شود. اگر بعد از اجرای تست فایل عوض شده باشد، رابطهٔ شاهد با نسخه دوباره بررسی می‌شود.

نتیجهٔ بازبین و Head باید روی hash مشترک باشد. تناقض دو review، نتیجهٔ UNKNOWN/ESCALATE ایجاد می‌کند؛ اکثریت رأی مدل‌ها به‌تنهایی اثبات صحت نیست. شواهد مستقل انسانی و ابزارها برای خطر/دامنهٔ همان کار انتخاب می‌شوند.

## ۱۱. بازیابی و نتیجهٔ نامعلوم

هنگام restart، leaseهای منقضی، dispatch intentها، operationهای بدون receipt و رزروها بررسی می‌شوند. عملیات معلومِ تکمیل‌شده از receipt ادامه می‌یابد. model call با هزینهٔ نامعلوم held باقی می‌ماند تا usage/provider statement reconcile شود. عملیات بیرونیِ نامعلوم با query وضعیت یا idempotency key بررسی می‌شود؛ وجود timeout یعنی نتیجهٔ نامعلوم، نه نبود اثر.

اگر مقصد وضعیت را نمی‌دهد و اثر تکرارپذیر امن نیست، عملیات به صف تصمیم انسانی می‌رود. deadline اجرا cumulative است و زمان انتظار انسان جداست. resume کار accepted جدید نمی‌سازد مگر درخواست و قرارداد تازه صریح ثبت شود.

## ۱۲. به‌روزرسانی حافظه پس از کار

رویداد و شاهد واقعی در log ثبت می‌شوند. JEV یک memory delta می‌سازد: تصمیم جدید، artifact پذیرفته‌شده، خطای تکرارپذیر، موضوع باز و next action. source hash و scope لازم است. نتیجهٔ مدل ابتدا proposed است؛ تغییر قواعد/سیاست سازمانی نیازمند تأیید صاحب مربوط است. rollback منبع، حذف یا تغییر ACL، index و خلاصه و نشست‌های متأثر را invalidates می‌کند. الگوریتم دقیق در سند ۰۴ است.

## ۱۳. نمونهٔ کامل: باگ پروژه و حافظه

در سورس پیش از اصلاح، `local.html` پیوند «پروژه‌ها و حافظه» را مستقیم به `/legacy` می‌برد. این رفتار با رابط اصلی v0.4 ناسازگار است؛ قابلیت ذخیره‌سازی و API پروژه/یادداشت از قبل وجود دارند.

مسیر حل: freeze C1/C2 → خواندن local UI و APIها → پنل مدیریت همان رابط → استفاده از endpointهای موجود → آزمون رفتار و حفظ داده → review diff → گزارش build. تغییر این UI نباید به ادعای ساخت tenant/ACL/JEV تبدیل شود.

هنگام انتخاب پروژه از پنل، اگر دستیار جاری NotebookLM باشد، رابط گفتگوی تازهٔ Codex با پوشهٔ همان پروژه می‌سازد؛ دفتر NotebookLM با انتخاب پوشه محدود یا تغییر داده نمی‌شود. گزارش تفصیلی این اصلاح: `docs/project-memory-ui-fix.fa.md`. مرز تطبیق سورس و نسخهٔ نصب‌شده در گزارش verification ثبت می‌شود.

## ۱۴. آزمون‌های پذیرش الگوریتم هدف

| سناریو | انتظار |
|---|---|
| request_key تکراری با همان/متن دیگر | همان task / خطای conflict؛ بدون دوباره‌مصرف |
| معیار required بدون owner/evidence | plan رد یا NEEDS_INFO؛ پذیرش ممنوع |
| cycle و بیش از عمق/children | پیش از model/tool dispatch رد |
| دو رزرو همزمان روی مادر مشترک | admission اتمی؛ عدم عبور از ancestor cap |
| approval منقضی یا artifact عوض‌شده | WAITING_APPROVAL/بازبینی مجدد |
| فایل حاوی دستور افزایش اختیار | مرجع untrusted؛ policy تغییر نکند |
| آزمون فقط در کد موجود، اجرا نشده | criterion UNKNOWN |
| review PASS با blocking issue | خروجی ناسازگار رد؛ ایراد پاک نشود |
| تلاش سوم بدون تغییر روش | ESCALATED؛ call تازه ساخته نشود |
| توقف بعد از ارسال ولی قبل از receipt | RECOVERING؛ تکرار اثر فقط پس از reconciliation |
| مدیر غایب و کار فوری | اطلاع‌رسانی مجاز؛ عدم افزایش اختیار؛ کار مستقل ادامه |
| حافظهٔ پروژه/tenant دیگر | قبل از ranking و Context حذف |
| لغو task دارای فایل نوشته‌شده | process خود task متوقف؛ فایل و ریسک باقی‌مانده گزارش |

این جدول برنامهٔ آزمون آینده است، نه نتایج اجرای تست این نوبت. milestone تکمیل الگوریتم فقط با اجرای این مسیر کامل روی فرایند واقعی، failure injection و پذیرش انسانی اعلام می‌شود.

## ۱۵. نگاشت به سورس و کار باقیمانده

- قرارداد و DAG: `contracts/task.py`, `contracts/head.py`, `engine/dag.py`؛ افزودن tenant/department/typed criteria و قرارداد نسخه‌دار لازم است.
- scheduler/state: `engine/scheduler.py`, `engine/state_machine.py`, `storage/repository.py`؛ lease/outbox/shared-root recovery هدف جدید است.
- اجرا: `engine/orchestrator.py` دمو متنی؛ `local_agents/runtime.py` ابزار واقعی با یک گفتگو؛ کنترل مستقل هر action و evidence receipt نیازمند adapter است.
- review/acceptance: `contracts/reviewer.py`, `Workspace.accept`؛ criterion-ID، strict contradiction handling و artifact-bound approval لازم است.
- حافظه: `Workspace.retrieve` سراسری؛ v2 در experiments/Skill؛ schema و migration جداسازی قبل از ادغام لازم است.
- اقتصاد: ledger فعلی مبنای قابل استفاده است؛ ancestor budgeting، review reservation و reconciliation نامعلوم باید اضافه شوند.

پیشنهاد بعدی HEAD، پیاده‌سازی محدود پروژه/حافظه و criterion IDs با benchmark و regression قبل از افزودن خودمختاری بیشتر است. انتخاب مرحلهٔ بعد با صاحب محصول انجام می‌شود؛ این سند خودش مجوز deploy یا ارسال بیرونی ایجاد نمی‌کند.
