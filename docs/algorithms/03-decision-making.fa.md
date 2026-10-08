# الگوریتم تصمیم‌گیری Head و دروازهٔ اختیار Flux

نسخهٔ طراحی: ۱٫۰ — تاریخ بررسی سورس: ۱ اکتبر ۲۰۲۶ — پروژه: `alacrity-flux`

Head هدف را به کار قابل بررسی تبدیل می‌کند و پیشنهاد می‌دهد؛ موتور قطعی Flux مجاز بودن، امکان اجرا، تغییر وضعیت و تعهد منابع را تعیین می‌کند. پذیرش سازمانی با انسان یا اختیار واگذارشدهٔ معتبر اوست. توانایی یک مدل، ادعای confidence یا قرار گرفتن در جایگاه Head، مجوز تازه ایجاد نمی‌کند.

این سند طراحی مقصد سازمانی است. رفتار موتور پنج نقش legacy و runtime فعلی CLI ۰٫۴ جدا گزارش می‌شود. شبه‌کدها قرارداد پیاده‌سازی آینده‌اند، نه اعلام ساخت runtime جدید. JEV و Skill بازیابی مستقل در این مرحله ابزار تولید شواهدند؛ بدون تصمیم جداگانه به موتور Flux ادغام نمی‌شوند.

## ۱. تصمیم خوب در Flux چه تعریفی دارد؟

برای هر تصمیم، چهار سؤال به‌ترتیب پاسخ داده می‌شوند:

۱. **حق انجام:** آیا این عامل برای همین شرکت، پروژه، ابزار، مسیر، مقصد، نوع داده و زمان اختیار دارد؟

۲. **اطلاعات کافی:** آیا هدف، معیار و ورودی لازم برای اقدام مشخص‌اند؟ نبودن چیزی که نتیجه را تغییر می‌دهد باعث سؤال/توقف شاخه می‌شود.

۳. **امکان اجرا:** آیا وابستگی، capability، بودجه، سهم فراخوانی، تلاش و زمان لازم موجود است؟

۴. **تناسب راه:** میان راه‌های مجاز و قابل اجرا، کدام مسیر معیارها را با سربار مناسب پوشش می‌دهد؟

پاسخ مطلوب «پیشنهاد مستند + حکم قابل بازتولید موتور» است. رأی مدل فقط ورودی تصمیم است. سیستم نباید از کم بودن خطا در یک نمونهٔ محدود، احتمال قطعی موفقیت یا عدد confidence کالیبره‌شده تولید کند.

## ۲. وضعیت کنونی با مقصد یکسان نیست

| حوزه | legacy اکنون | CLI نسخهٔ ۰٫۴ اکنون | مقصد این سند |
|---|---|---|---|
| شروع کار | `TaskInput` و pre-API validation، سپس Head | `ChatSpec` و `TurnSpec`، انتخاب صریح provider توسط کاربر | قرارداد immutable و سیاست سازمانی versioned |
| تقسیم کار | Head تا پنج subtask، agentهای custom تا سقف کل ده، DAG tiered | یک CLI در هر گفتگو؛ routing خودکار میان providerها ندارد | Head مرکزی/بخش، DAG محدود و lineage مشترک |
| اختیار | allowed_tools/paths در schema؛ demo ابزار shell اجرا نمی‌کند | CLI با read/work و تنظیم‌های محلی خود اجرا می‌شود | gate مستقل پیش از هر اقدام و ACL داده |
| اصلاح | transport retry محدود؛ verdict=`REVISE` اجرای جاری را متوقف می‌کند | retry/تعویض مدل خودکار در Flux ساخته نشده است | سه تلاش کیفی محدود با تغییر مستند روش |
| بازبینی | یک مرحلهٔ verification و gateهایی روی check/criteria | اتمام CLI و tool events؛ reviewer سازمانی ندارد | بازبین مستقل + Head بخش + gate شواهد |
| پایان | `ACCEPT_CANDIDATE`؛ human_acceptance_required=true | `completed` برای نوبت CLI | artifact مشخص → نامزد → پذیرش انسانی |
| recovery | `resume_run=False`؛ وضعیت‌ها/دفتر پایدار | queued/running پس از restart → interrupted | RECOVERING با reconciliation و عدم replay کور |

دو نقص مهم در normalization فعلی legacy باید در پیاده‌سازی مقصد رفع شوند: `_workflow` برای verdict نامعتبر گاهی ACCEPT_CANDIDATE را fallback می‌گذارد و برای verdict ACCEPT فهرست blocking/failed را پاک می‌کند؛ سپس passed criteria دارای تعداد کافی را به متن معیارهای root نگاشت می‌کند. gateهای بعدی برخی قبولی‌های نامعتبر را می‌بندند، اما حذف تعارض یا نگاشت صرفاً برحسب تعداد، شاهد بررسی واقعی هر معیار نیست. مقصد پاسخ متعارض یا schema نامعتبر را پذیرش نمی‌کند و معیارها را با ID و evidence بررسی می‌کند.

`TaskInput.max_attempts` اکنون بین ۱ و ۳ validate می‌شود؛ در `_execute_subtask` loop اصلاح کیفی بر اساس آن وجود ندارد. سه ارسال `_call` برای خطای گذرا، اجرای سه تلاش اصلاح محصول نیست. `HeadOutput.final_review_agent` و `risk_level` نیز در schema هستند، اما نمی‌توان از وجود فیلد نتیجه گرفت که تمام routing اضافی موردنظر طراحی اجرا می‌شود.

## ۳. نقش‌ها از مدل‌ها جدا هستند

| نقش مقصد | تصمیم/مسئولیت | حد اختیار |
|---|---|---|
| مدیر انسانی | هدف، معیار، cap، delegation و پذیرش | مطابق سیاست شرکت و هویت واقعی خودش |
| Head مرکزی | relevance، تقسیم بین بخش‌ها، وابستگی و تعارض کل | پیشنهاد؛ بدون اعطای مجوز به خود |
| Head بخش | انتخاب executor، برنامهٔ تخصصی، یکپارچگی | بخش، داده و بودجهٔ معتبر خودش |
| executor | ساخت نسخهٔ خروجی و شاهد | بدون تغییر criteria یا cap |
| reviewer | بررسی معیار و defect مستند | بدون اصلاح پنهانی artifact یا کاهش معیار |
| موتور Flux | schema، سیاست، state، counters، ledger و dispatch | قواعد قطعی با audit و revision |
| درگاه ابزار/مدل | اجرای درخواست مجاز، ثبت نتیجه و usage | مقصد و پارامترهای مصوب هر درخواست |

شناسهٔ نقش نمونه: `engineering.executor`؛ شناسهٔ مدل در فیلد جدا `model_id` است. تعویض مدل executor آن را reviewer مستقل یا مدیر نمی‌کند. استقلال reviewer یعنی نقش، assignment و گزارش جدا؛ دو مدل یا دو نشست نیز استقلال آماری خطا را تضمین نمی‌کنند.

Head بالاتر فقط اطلاعات مجاز خودش را می‌گیرد. برای هماهنگی می‌توان خلاصهٔ مجاز بین بخش‌ها داد؛ قرار گرفتن در رأس چارت حق خواندن همهٔ اسناد محرمانه را ایجاد نمی‌کند.

## ۴. قرارداد ثابت و دادهٔ تصمیم

### ۴٫۱. قرارداد کار

```json
{
  "schema_version": "org-task-1.0",
  "tenant_id": "alacrity-internal",
  "department_id": "technical",
  "project_id": "alacrity-flux",
  "root_task_id": "root-20261001-001",
  "task_id": "task-demo-memory-view",
  "human_owner": "owner-product",
  "objective": "صفحهٔ پروژه و حافظه در ظاهر جاری Flux باز شود.",
  "scope": ["navigation", "project_and_memory_view"],
  "out_of_scope": ["automatic_JEV_runtime_integration"],
  "acceptance_criteria": [
    {
      "criterion_id": "AC-NAV-01",
      "text": "انتخاب پروژه و حافظه رابط جاری را حفظ می‌کند.",
      "required": true,
      "evidence_type": "test_execution"
    },
    {
      "criterion_id": "AC-DATA-01",
      "text": "پروژه‌ها و یادداشت‌های موجود قابل مشاهده می‌مانند.",
      "required": true,
      "evidence_type": "test_execution"
    }
  ],
  "dependencies": [],
  "allowed_tools": ["workspace_read", "workspace_edit", "browser_check"],
  "allowed_paths": ["D:/project/Alacrity/Flux"],
  "allowed_destinations": ["local_workspace", "localhost_preview"],
  "data_class": "internal",
  "policy_revision": 7,
  "contract_hash": "sha256:<canonical-contract>",
  "acceptance_criteria_hash": "sha256:<canonical-criteria>",
  "artifact_hash": null,
  "limits": {
    "max_generation_attempts": 3,
    "max_transport_sends_per_request": 3,
    "max_calls": 32,
    "max_children": 5,
    "max_depth": 1,
    "max_active_seconds": 1200,
    "max_concurrency": 2
  }
}
```

این یک قرارداد نمونه است؛ عددهای limit باید در سیاست مصوب همان کار ثابت شوند. فیلدهای limits با سند ۰۱ مشترک‌اند و سقف ۳۲ تماس مقصد پیشنهادی است؛ رفتار legacy فعلی سقف ۲۰ تماس دارد. `max_generation_attempts` برای هر repair group اعمال می‌شود، نه برای هر نام تازهٔ child. task نمونه باگ معرفی‌شده توسط کاربر را مشخص می‌کند و دلیل وقوع یا نتیجهٔ رفع آن را ادعا نمی‌کند. hash artifact تا تولید نسخهٔ خروجی می‌تواند null باشد؛ تصمیم بازبینی/پذیرش همیشه hash واقعی نسخهٔ مورد بررسی را لازم دارد.

`policy_revision` عدد صحیح مثبت است و `evidence_type` از enum مشترک سند ۰۴ می‌آید. گزارش آزمون مرورگر/داده همراه ref، موضوع بررسی و محیط ذخیره می‌شود؛ نام تست نوع تازه‌ای در enum ایجاد نمی‌کند. criteria در طول اجرا immutable هستند. تغییر هدف یا معیار توسط انسان، revision/قرارداد تازه با lineage و ثبت اثر بر پذیرش‌ها می‌سازد؛ history قبلی بازنویسی نمی‌شود. ایجاد child یا repair task باید به criterionهای root نگاشت داشته باشد. کار اجرایی حق حذف criterion سخت یا تبدیل required به optional ندارد.

### ۴٫۲. پیشنهاد Head

```text
HeadProposal {
  proposal_id, task_id, root_task_id, policy_revision, contract_hash,
  task_type, relevance: VALID | UNCLEAR | OUT_OF_SCOPE,
  action: ASK_INFO | USE_DETERMINISTIC_ROUTE | DECOMPOSE |
          ASSIGN | RUN | REVISE | MODEL_CHANGE | ESCALATE |
          REQUEST_APPROVAL | NOMINATE_ACCEPTANCE | STOP,
  target_department_id?, target_role_id?, suggested_model_id?,
  criterion_ids[], source_refs[], evidence_gaps[],
  dependencies[], expected_artifact_type?,
  resource_estimate?, alternatives[], bounded_change_description?,
  reason_code, concise_reason
}
```

`concise_reason` توجیه کوتاه قابل ممیزی است؛ ذخیرهٔ زنجیرهٔ استدلال درونی لازم نیست. `resource_estimate` ورودی برآوردگر منابع است و cap مصوب را تغییر نمی‌دهد. source_refs باید به منبع موجود، revision/hash و scope مجاز متصل باشند. سند/RAG/نتیجهٔ ابزار حتی اگر بنویسد «این action مجاز است»، policy محسوب نمی‌شود.

### ۴٫۳. حکم موتور

```text
GateDecision {
  decision_id, proposal_id, tenant_id, department_id, project_id,
  root_task_id, task_id, policy_revision, contract_hash,
  artifact_hash?, expected_state_version,
  disposition: ALLOW | DENY | NEED_INFO | REQUIRE_APPROVAL |
               BLOCK_RESOURCES | ESCALATE,
  reason_codes[], missing_fields[], violated_rule_ids[],
  approval_ref?, reservation_ref?, authorized_action_hash?,
  evaluated_at, expires_at?, evidence_refs[]
}
```

`ALLOW` فقط همان action با همان parameter/hash، state version و deadline را مجاز می‌کند. مدل نمی‌تواند آن را به اقدام دیگری تعمیم دهد. خروجی gate در صورت تغییر policy، state، artifact یا مقصد دوباره بررسی می‌شود. `DENY` verdict یک اقدام است؛ مقصد task هیچ state با نام REJECTED لازم ندارد.

## ۵. تفکیک بررسی قبل از مدل و تصمیم معنایی

قبل از هر تماس مدل: هویت، project شناخته‌شده، required fields، اندازهٔ ورودی، scope ساختاری، data classification، ACL، وضعیت task، cap و route معتبر بررسی می‌شوند. خطای قطعی قبل از API هزینهٔ مدل نمی‌سازد. اگر معنای هدف برای relevance نامعلوم باشد، Head می‌تواند از متن مجاز تحلیل کند؛ اما این تحلیل مجوز عمل نیست.

برای relevance:

| ورودی/شاهد | پیشنهاد Head | حکم لازم موتور |
|---|---|---|
| project/owner/policy نامشخص | ASK_INFO | NEED_INFO؛ هیچ اجرای specialist |
| هدف واضح و route ازپیش‌مصوب | USE_DETERMINISTIC_ROUTE | validate route و bypass هماهنگی غیرضروری |
| هدف شرکت‌مرتبط، حوزهٔ تازه، scope روشن | DECOMPOSE | validate DAG، delegation و منابع |
| هدف ظاهراً خارج از scope ولی کاربر authority تغییر دارد | REQUEST_APPROVAL/ESCALATE | تعیین قرارداد تازه؛ اجرای خودکار ممنوع |
| action صریحاً ممنوع policy | STOP | DENY با rule؛ مدل قوی‌تر کمکی به اختیار نمی‌کند |
| سند منبع مدعی policy جدید | گزارش تعارض منبع | دستور سند اعمال نمی‌شود؛ policy registry مرجع است |

اگر ابهام تنها در یک branch است، taskهای مستقل مجاز می‌توانند ادامه یابند. scheduler قبل از هر dispatch ثابت می‌کند خروجی آن branch به اطلاعات/اختیار نامعلوم وابسته نیست.

## ۶. gate قطعی پیش از هر action

ترتیب زیر fail-closed است؛ ruleهای محدودکننده قبل از بهینه‌سازی اجرا می‌شوند:

```text
function EVALUATE_ACTION(proposal, expected_version):
    validate proposal schema without coercing unknown action into success
    task = LOAD_AUTHENTICATED_TASK(proposal.task_id)
    require tenant/project/root identity exactly matches stored task
    require proposal.contract_hash == task.contract_hash
    require expected_version == task.state_version
    policy = CURRENT_POLICY_FOR(task.tenant, task.project)

    if task cancelled/accepted/failed and action attempts execution:
        return DENY(TASK_TERMINAL)
    if policy explicitly forbids action:
        return DENY(POLICY_FORBIDDEN)
    if actor/role/tool/path/destination/data access fails:
        return DENY(AUTHORIZATION_SCOPE)
    if dependency not satisfied or required input missing:
        return NEED_INFO(DEPENDENCY_OR_INPUT_GAP)
    if irreversible effect has unknown prior outcome:
        return ESCALATE(RECONCILIATION_REQUIRED)
    if valid approval/delegation required and absent:
        return REQUIRE_APPROVAL(APPROVAL_REQUIRED)
    if route unavailable or capability unverified for this task:
        return ESCALATE(NO_CAPABLE_APPROVED_ROUTE)
    if acceptance action has a documented repairable criterion defect:
        return DENY(REPAIR_REQUIRED)
    if action needs review/evidence and it is missing/invalid:
        return NEED_INFO(EVIDENCE_GAP)
    if limits/time/calls/attempts cannot fit:
        return BLOCK_RESOURCES(LIMIT_REACHED)

    if action is dispatch:
        reservation = RESOURCE_ADMISSION_IN_ATOMIC_TRANSACTION(action)
        if refused: return BLOCK_RESOURCES(BUDGET_OR_QUOTA)
    authorized_hash = HASH_EXACT_ACTION_PARAMETERS_AND_INPUT_ARTIFACTS(action)
    record GateDecision with policy revision and resources
    return ALLOW(authorized_hash, current state version, expiry)
```

disposition حکم یک action است و state کار نیست. برای `DENY(REPAIR_REQUIRED)` در مرحلهٔ پذیرش، orchestrator جداگانه transition معتبر از REVIEWING/ACCEPT_CANDIDATE به NEEDS_REVISION را همراه `reason_code=REPAIRABLE_CRITERION_DEFECT` و refهای defect در تراکنش state/event ثبت می‌کند؛ acceptance dispatch انجام نمی‌شود. `NEED_INFO(EVIDENCE_GAP)` فقط نبود/نامعتبر بودن شاهد لازم را گزارش می‌کند و route اطلاعات/بازیابی محدود را فعال می‌سازد؛ هیچ disposition خارج از enum ساخته نمی‌شود.

ruleهای حساس حداقل publication، پرداخت، حذف، پیام مشتری و تغییر permission را پوشش می‌دهند. هر کدام delegation قبلی صریح می‌تواند داشته باشد؛ داشتن مجوز معتبر همان action باعث پرسیدن دوباره نمی‌شود. scope wildcard فقط اگر policy واقعاً آن را واگذار کرده باشد معتبر است، و همچنان revoked/expiry/cap/data constraints اعمال می‌شوند.

canonical path و junction/symlink/traversal باید در درگاه ابزار بررسی شوند. در Windows حالت ابزارهای Claude معادل sandbox سیستم‌عامل نیست و cwd صرفاً محل شروع است؛ کنترل سازمانی باید در زیرساخت ابزار/runner هم اعمال شود. audit metadata هر action حداقل actor/role/model/tool، parameter hash، policy، time، نتیجه، artifact/evidence و authorization ref دارد.

## ۷. انتخاب روش اجرا و مدل

اول route قطعی کافی بررسی می‌شود: validation ثابت، formatting، aggregation و انتقال کنترل‌شده نیازمند تماس مدل نیستند. برای reasoning یا هماهنگی واقعاً لازم، candidate مدل فقط اگر تمام موارد زیر برقرار باشد وارد انتخاب می‌شود:

- route/account available با شاهد capability مربوط، نه صرفاً نام در فهرست UI؛
- داده و مقصد پردازش مجاز؛ ابزار/structured output/context/output مناسب؛
- authority همان اقدام، هزینه و review لازم در حدود منابع؛
- سابقهٔ ارزیابی مرتبط یا capability check قابل اتکا برای task class.

انتخاب پایه میان candidateهای واجد شرط، کم‌هزینه‌ترین مسیر مناسب است. مقایسه ابتدا feasibility و معیارهای mandatory، سپس هزینهٔ قابل مقایسه، زمان لازم و سربار هماهنگی را بررسی می‌کند. اگر دادهٔ تاریخی معتبر وجود ندارد، quality guarantee یا expected-success عددی ساخته نمی‌شود. انتخاب با reason و سطح اعتبار `verified_for_class | limited_evidence | unverified` ثبت می‌شود؛ `unverified` برای کار حساس/سقف سخت قابل انتخاب نیست.

سنجش cost/outcome در pilot باید شامل تلاش ناموفق و review انسانی باشد. استفاده از «احتمال ۸۰٪» در score بدون dataset، تعریف موفقیت و calibration ممنوع است. امتیاز BM25، رتبهٔ JEV و برچسب candidate نیز احتمال صحت نیستند. الگوریتم بدون این اعداد ساختگی قابل اجراست: hard gate و ترتیب deterministic با tie-break صریح، مثلاً model ID ثابت پس از cost/capability و latency evidence.

تغییر provider/model در میانهٔ کار باید source context، ابزار، policy، reservation و model capability را دوباره validate کند. اگر نشست قدیمی قابل ادامه با مدل جدید نیست، نشست تازه به همان task/root/artifact lineage متصل می‌شود؛ session جدید معیار و مصرف را صفر نمی‌کند.

## ۸. برنامه، DAG و تخصیص

```text
function VALIDATE_PLAN(plan, task, policy):
    require nonempty executable plan or return NEED_INFO
    require unique task IDs and authorized departments/roles
    require children_count <= approved max_children
    require lineage_depth <= approved max_depth
    require every required root criterion has owner and evidence route
    require child criterion IDs map to root or approved supplementary criteria
    require no child broadens tool/path/data/destination authority
    reject unknown/self/duplicate dependency and cycles
    require external dependency has versioned completion evidence
    require resource envelope covers execution and mandatory review
    return topological tiers with assignment snapshot and stable plan hash
```

ورودی وابستگی شامل artifact hash، check status و policy-validity است؛ جملهٔ «قبلاً تمام شد» کافی نیست. هر assignment snapshot نقش/مدل/ابزار را در زمان اجرا ثبت می‌کند تا ویرایش چارت در UI سابقه را عوض نکند.

کارهای مستقل در tier یکسان فقط در حدود concurrency و منابع اجرا می‌شوند. ورود به tier بعد نیازمند artifact نسخه‌دار معتبر upstream و عبور از criterion stage gate مشخص همان وابستگی است؛ این stage gate مصرف داخلی با ref/hash و گزارش validator ثبت می‌شود. پذیرش نهایی انسانی upstream فقط وقتی پیش‌نیاز downstream است که قرارداد یا policy آن را الزام کرده باشد. state برابر `completed` متعلق به نوبت CLI است و به‌تنهایی dependency را رفع نمی‌کند. اگر یک task لغو شود، descendants وابسته مسدود می‌شوند؛ siblings مستقل بعد از admission خودشان می‌توانند ادامه دهند. taskهای blocked دنبال‌هم timeout تولید نمی‌کنند و سقف root را با task تازه دور نمی‌زنند.

## ۹. ماشین وضعیت مقصد و مرز پذیرش

وضعیت‌های هدف: `REGISTERED`, `NEEDS_INFO`, `READY`, `RUNNING`, `REVIEWING`, `NEEDS_REVISION`, `WAITING_APPROVAL`, `BLOCKED_BUDGET`, `ACCEPT_CANDIDATE`, `ACCEPTED`, `ESCALATED`, `FAILED`, `CANCELLED`, `RECOVERING`.

| وضعیت | معنای دقیق | شرط خروج اصلی |
|---|---|---|
| REGISTERED | درخواست با شناسه و actor ثبت شده | قرارداد معتبر یا نیاز اطلاعات |
| NEEDS_INFO | اطلاعات/وابستگی اثرگذار کافی نیست | ورودی معتبر و revision ثبت‌شده |
| READY | قرارداد و مرحلهٔ بعد روشن؛ هنوز dispatch نشده | gate/action admission موفق |
| RUNNING | executor/ابزار دارای lease مجاز فعال است | artifact و شواهد برای review یا توقف |
| REVIEWING | بازبین مستقل و Head بخش artifact مشخص را می‌سنجند | criterion evidence، defect یا تصمیم انسانی |
| NEEDS_REVISION | ایراد قابل اصلاح و criterion mapping موجود | plan اصلاحی با limits/authority کافی |
| WAITING_APPROVAL | شروع یا action ابزار مشخص منتظر مرجع اختیار است | approval معتبر برای همان action/hash/scope |
| BLOCKED_BUDGET | منبع لازم برای مرحلهٔ بعد قابل تعهد نیست | cap/route معتبر یا کاهش optional scope با حفظ معیار |
| ACCEPT_CANDIDATE | همهٔ required criteria شاهد دارند و review دوگانه کامل است؛ منتظر پذیرش نهایی | تصمیم صاحب انسانی روی همین artifact |
| ACCEPTED | artifact مشخص تحت قرارداد مشخص پذیرفته شده | پایانی برای همان task version |
| ESCALATED | تعارض/نبود پیشرفت/اختیار نیازمند Head بالاتر یا انسان | resolution ثبت‌شده و admission تازه |
| FAILED | ادامه در قرارداد فعلی ممکن نیست و failure مستند است | پایانی؛ ادامه با task مرتبط تازه |
| CANCELLED | کار با authority معتبر لغو شده | پایانی؛ settlement دیررس ممکن است |
| RECOVERING | checkpoint یا نتیجهٔ dispatch در حال reconciliation است | رفع ابهام بدون replay کور |

این سه دستگاه state با هم مخلوط نمی‌شوند:

```text
Legacy RunState:
NEW, VALIDATING, PLANNING, QUEUED, RUNNING, VERIFYING,
ACCEPT_CANDIDATE, NEEDS_INPUT, REVISE, ESCALATED,
REJECTED, PAUSED_BUDGET, FAILED, CANCELLED

Local CLI turn state:
queued, running, completed, failed, cancelled, needs_input, interrupted

Organizational target state:
REGISTERED, NEEDS_INFO, READY, RUNNING, REVIEWING, NEEDS_REVISION,
WAITING_APPROVAL, BLOCKED_BUDGET, ACCEPT_CANDIDATE, ACCEPTED,
ESCALATED, FAILED, CANCELLED, RECOVERING
```

نگاشت فقط برای نمایش/مهاجرت است: legacy VERIFYING به REVIEWING نزدیک است، PAUSED_BUDGET به BLOCKED_BUDGET، REVISE به NEEDS_REVISION؛ این نگاشت lifecycle مقصد را در legacy پیاده نمی‌کند. local `completed` هیچ‌گاه به ACCEPTED یا ACCEPT_CANDIDATE بدون فرآیند review نگاشت نمی‌شود.

### ۹٫۱. جدول transition پیشنهادی

`FAILURE_OR_CANCEL` در جدول یعنی FAILED/CANCELLED با رخداد و authority/علت معتبر. جدول مقصد مستقل از `state_machine.py` فعلی است.

| مبدأ | مقصدهای مجاز |
|---|---|
| REGISTERED | NEEDS_INFO، READY، FAILURE_OR_CANCEL |
| NEEDS_INFO | READY، CANCELLED |
| READY | RUNNING؛ REVIEWING فقط برای checkpoint.phase=review؛ WAITING_APPROVAL، BLOCKED_BUDGET، FAILURE_OR_CANCEL |
| RUNNING | REVIEWING، NEEDS_INFO، WAITING_APPROVAL، RECOVERING، FAILURE_OR_CANCEL |
| REVIEWING | ACCEPT_CANDIDATE، NEEDS_REVISION، ESCALATED، WAITING_APPROVAL، BLOCKED_BUDGET، CANCELLED |
| NEEDS_REVISION | READY، BLOCKED_BUDGET، ESCALATED، CANCELLED |
| WAITING_APPROVAL | READY، ESCALATED، CANCELLED |
| BLOCKED_BUDGET | READY، CANCELLED |
| ACCEPT_CANDIDATE | ACCEPTED، NEEDS_REVISION، ESCALATED، CANCELLED |
| ESCALATED | READY، NEEDS_INFO، FAILURE_OR_CANCEL |
| RECOVERING | READY، REVIEWING، WAITING_APPROVAL، FAILED، CANCELLED |
| ACCEPTED، FAILED، CANCELLED | هیچ transition اجرایی در همان task version |

برای WAITING_APPROVAL/BLOCKED_BUDGET، `checkpoint.phase=generation|review|tool` مرحلهٔ واقعی بعد را مشخص می‌کند. بازگشت به READY و admission تازه باید همان checkpoint را ادامه دهد؛ review متوقف‌شده نباید باعث تکرار تولید شود. READY دارای phase=review پس از admission بازبین مستقیماً به REVIEWING می‌رود؛ RUNNING در جدول مسیر تولید/ابزار است. جدول و guards با سند ۰۱ مشترک‌اند. WAITING_APPROVAL برای شروع/ابزار است و پذیرش نهایی در ACCEPT_CANDIDATE منتظر می‌ماند. شیء Approval در هر دو مسیر با `purpose` متفاوت استفاده می‌شود؛ فقط ACCEPT_CANDIDATE → ACCEPTED با purpose=`artifact_acceptance` و hash نامزد بازبینی‌شده مجاز است. RECOVERING → READY فقط برای checkpoint ایمن است؛ اثر نامعلوم در WAITING_APPROVAL برای reconciliation می‌ماند و رد/ابهام حل‌نشده به ESCALATED می‌رسد.

state update و event در یک transaction با `expected_state_version` ثبت می‌شوند. lease stale یا پاسخ دیررس اجازهٔ برگشت CANCELLED به RUNNING ندارد. شکست/لغو، اثرهای قبلی را rollback اعلام نمی‌کنند؛ artifact و هزینه و audit محفوظ‌اند.

## ۱۰. review بر مبنای معیار و شاهد

### ۱۰٫۱. قرارداد نتیجهٔ هر معیار

```text
CriterionReview {
  criterion_id, artifact_hash, contract_hash,
  status: PASS | FAIL | UNKNOWN | NOT_APPLICABLE,
  reason_code?: NOT_RUN | MISSING | CONFLICT | OTHER,
  evidence_refs[{source_id, revision, hash, locator, produced_by}],
  evidence_type, defect?, required_change?,
  reviewed_by, reviewed_at
}

ReviewReport {
  role_id, agent_id, model_id?, task_id, artifact_hash,
  criteria_results[], blocking_issues[], input_evidence_pack_hash,
  conflicts[], concise_reason,
  semantic_sufficiency: VERIFIED_FOR_CRITERIA | UNVERIFIED
}
```

source locator باید نوع روشن داشته باشد: خط مطلق فایل، position داخل chunk، صفحهٔ PDF یا record ID. position داخل chunk JEV شمارهٔ خط مطلق سورس نیست. ref/hash بدون خواندن/اعتبارسنجی شاهد، خودبه‌خود PASS نمی‌سازد.

status معیار با سند ۰۱ مشترک است. آزمون اجرا‌نشده، شاهد missing و تعارض در `status=UNKNOWN` با reason مربوط نگه داشته می‌شوند. NOT_APPLICABLE فقط وقتی قرارداد صریحاً آن را برای همان criterion اجازه داده معتبر است؛ required criterion بدون این اجازه با N/A حذف نمی‌شود. برای criterion آزمون رفتار کد، evidence لازم نتیجهٔ runner/test واقعی با command/environment/hash/exit-status است. برای سند، پوشش، تناقض، traceability و بررسی منابع شاهد مناسب‌اند؛ اجرای تست کدِ بی‌ربط الزام همهٔ taskها نیست. test=`NOT_RUN` برای criterion ضروری مانع نامزد پذیرش است. statement تولیدشدهٔ مدل که «تست پاس شد» با tool event یا گزارش runner مساوی نیست.

### ۱۰٫۲. کنترل دوگانه

بازبین مستقل هر criterion را بررسی می‌کند. Head بخش یکپارچگی، dependency و scope بخش را روی همان artifact hash می‌سنجد. Head مرکزی فقط برای تعارض بین بخش‌ها یا تصمیم سطح شرکت دخالت می‌کند؛ بازبینی اضافی بی‌نیاز از مسئله، هزینهٔ غیرضروری است.

```text
function NOMINATE_ACCEPTANCE(task, artifact, reviewer, department_head):
    require artifact exists and bytes hash == artifact_hash
    require reports refer to same artifact_hash and contract_hash
    require report schema valid and criterion IDs exactly cover required set
    require every required criterion status == PASS
    require expected evidence types are present and validated
    require no UNKNOWN or reason NOT_RUN/MISSING/CONFLICT for required criteria
    require no blocking issue or unhandled policy/data violation
    require independent reviewer role assignment and Head integration approval
    require original criteria hash unchanged
    return ACCEPT_CANDIDATE with immutable acceptance package
```

هر نقص فقط به criterion مشخص و evidence واقعی متصل می‌شود. reviewer حق ندارد output را پنهانی اصلاح کند و سپس همان نسخه را pass اعلام کند. اصلاح artifact hash تازه می‌سازد و review دوباره روی همان hash تازه انجام می‌شود.

### ۱۰٫۳. معیار انتخاب اقدام پس از review

| مشاهده | اقدام |
|---|---|
| همهٔ معیارهای ضروری PASS با شاهد و کنترل دوگانه | نامزد پذیرش؛ بسته به صاحب انسانی |
| defect مشخص و قابل اصلاح | NEEDS_REVISION، feedback دقیق، bounded repair plan |
| test ضروری اجرا نشده | MISSING/NOT_RUN؛ runner مجاز یا درخواست اختیار/اطلاعات |
| شاهد بازیابی ناقص یا semantic sufficiency تأیید نشده | بازیابی تکمیلی محدود یا NEEDS_INFO؛ حدس به‌عنوان PASS ممنوع |
| تعارض reviewer و Head | ESCALATED با criterion/evidence هر دو، بدون پاک کردن رأی مخالف |
| نقض policy یا scope | توقف action و audit؛ رفع اختیار توسط مدل قوی‌تر ممنوع |
| schema verdict نامعتبر/متعارض | failure قرارداد پاسخ؛ قبولی fallback ممنوع |
| تمام تلاش‌ها مصرف شده | ESCALATED یا FAILED با علت؛ child تازه سقف را صفر نمی‌کند |

## ۱۱. سه تلاش اصلاح کیفی، مستقل از retry انتقال

قید پایه `max_generation_attempts_per_repair_group=min(contract_limit,3)` است. `repair_group_id` به مسئولیت/معیار ریشه متصل می‌شود تا تبدیل leaf شکست‌خورده به دو child جدید شمارنده را reset نکند. اگر contract_limit یک باشد، دوم/سوم مجاز نیستند. call cap، deadline، بودجه و review envelope مستقل و ممکن است قبل از تلاش سوم ادامه را متوقف کنند.

| تلاش | شرط شروع | مسیر |
|---|---|---|
| ۱ | قرارداد، capability، budget و معیار روشن | کم‌هزینه‌ترین executor واجد توانایی و مجاز |
| ۲ | شکست کیفی مستند، defect قابل اصلاح، مسیر دارای توان بیشتر برای همین defect در دسترس و مجاز | feedback criterion/evidence + artifact قبلی؛ همان criterionهای ثابت |
| ۳ | تصمیم Head، تغییر معنادار روش/تقسیم/ورودی، budget و capability کافی | اصلاح با delta مشخص؛ بدون delta به انسان ارجاع |

«توانمندتر» برای task class و defect تعریف می‌شود؛ قیمت بالاتر یا اسم مدل کافی نیست. route باید available، approved و دارای ابزار/context لازم باشد. اگر مدل قوی‌تر در دسترس نیست، Head نمی‌تواند silently fallback یا تضمین حل بسازد: می‌تواند روش جایگزین مصوب دارای تغییر واقعی پیشنهاد کند یا موضوع را ارجاع دهد. انتخاب fallback، اگر policy اجازه دهد، یک تلاش همان group و منابع همان root مصرف می‌کند و در audit ظاهر است.

```text
function CHOOSE_REPAIR(task, reports, lineage):
    if reports have policy/authority/data gap:
        return WAITING_APPROVAL_OR_NEEDS_INFO
    defect = PRECISE_REPAIRABLE_DEFECT(reports)
    if defect unavailable or reports conflict:
        return ESCALATED
    n = DURABLE_ATTEMPTS(lineage.repair_group_id)
    if n >= min(task.limits.max_generation_attempts, 3):
        return ESCALATED(ATTEMPTS_EXHAUSTED)

    if n == 1:
        candidate = CAPABLE_STRONGER_APPROVED_AVAILABLE_ROUTE(defect)
        if candidate unavailable:
            alternative = EXPLICIT_APPROVED_METHOD_CHANGE(defect)
            if alternative unavailable: return ESCALATED(NO_REPAIR_ROUTE)
            candidate = alternative
    else if n == 2:
        delta = HEAD_PROPOSED_MEANINGFUL_CHANGE(defect, prior_attempts)
        if delta absent or merely repeats prompt: return ESCALATED(NO_PROGRESS)
        candidate = VALIDATE_CHANGED_METHOD_AND_CAPABILITY(delta)

    require original contract/criteria hashes unchanged
    require execution + review fits every resource ceiling
    return NEEDS_REVISION_WITH_VALIDATED_REPAIR(candidate, next_attempt=n+1)
```

اعتبارسنجی transport response یا خطای auth، defect کیفی محصول نیست. شبکهٔ گذرا می‌تواند همان request منطقی را با سقف ارسال مصوب و backoff محدود تکرار کند؛ هر physical dispatch در call/budget دفتر جدا دارد. پایان deadline یا نبود دو هزینهٔ احتمالی (unknown اول + retry) باعث توقف retry می‌شود. در اثرهای مهم مثل payment/message، retry فقط بعد از بررسی idempotency/وضعیت مقصد مجاز است.

retry hidden در adapter یا SDK ممنوع است. رفتار کنونی GapGPT SDK retry را خاموش کرده ولی برای ۴۰۰ برخی پارامترها دوباره ارسال می‌کند؛ مقصد باید این ارسال را از gate/counter/ledger عبور دهد. policy پیشنهادی سه تلاش تولید و سه ارسال transport ضرب نامحدود نمی‌سازد؛ root call cap حد نهایی مستقل است.

## ۱۲. تشخیص نبود پیشرفت بدون احتمال ساختگی

Head برای ادامهٔ اصلاح به داده‌های قابل مشاهده تکیه می‌کند:

```text
progress_record = {
  prior_artifact_hash, new_artifact_hash,
  required_criteria_passed_before/after,
  blocking_defect_ids_before/after,
  changed_method_or_inputs,
  newly_validated_evidence_refs,
  costs_and_calls_of_attempt
}
```

تعویض متن با defect ثابت، اضافه شدن justification بدون شاهد، یا تکرار همان خطا پس از feedback روشن، progress کافی نیست. کم شدن تعداد defect وقتی criterion دیگر حذف شده، پیشرفت محسوب نمی‌شود. اگر تست flaky یا نتیجه متعارض باشد، ابتدا شواهد تناقض و محیط جمع می‌شوند؛ اگر تکرار مجاز محدود مسئله را حل نکرد، human escalation جای threshold حدسی confidence را می‌گیرد.

گزارش JEV v2 نشان داد در ۱۲ سناریوی اضافی، پوشش از ۱۹ به ۲۹ شاهد از ۴۳ رسید ولی full-evidence scenario هر دو چهار مورد بود. بنابراین Head نمی‌تواند از recall بالاتر، «همهٔ اطلاعات کافی است» نتیجه بگیرد. `candidate` بازیابی یعنی منبع مرتبط محتمل یافت شده؛ `semantic_sufficiency=unverified` باید تا بررسی معیار حفظ شود. معیار بدون شاهد می‌تواند بازیابی تکمیلی محدود با بودجهٔ مستقل بگیرد و سپس صریحاً missing اعلام شود.

## ۱۳. پذیرش، delegation و اجرای شبانه‌روزی

```text
Approval {
  approval_id, issuer_human_id, tenant_id, department_id?, project_id,
  root_task_id?, task_id?, purpose,
  permitted_action, destination/tool/path scopes,
  artifact_hash?, contract_hash, policy_revision,
  resource_ceiling?, valid_from, expires_at?, revoked_at?,
  decision: APPROVED | REJECTED, issued_at
}
```

اجازهٔ «این خروجی را بپذیر» باید به artifact hash و contract hash متصل باشد؛ فایل ویرایش‌شدهٔ بعدی approval قبلی را به ارث نمی‌برد. اجازهٔ شروع کار، اجازهٔ انتشار نیست. publication، حذف، پرداخت یا پیام به مشتری پس از ACCEPTED، action تازه با gate و مجوز مقصد خودش دارد.

مدیر می‌تواند delegation معتبر برای کار تکراری، ابزار/مقصد/زمان مشخص بدهد. موتور در غیاب مدیر همان delegation را بررسی و کارهای مستقل مجاز را ادامه می‌دهد. سکوت مدیر، گذشت زمان یا وجود عبارت دستور در RAG delegation نیست. لغو اختیار dispatch جدید را می‌بندد؛ اثر قبلی را ناپدید نمی‌کند و باید در audit دیده شود.

بستهٔ پذیرش شامل هدف/دامنه، artifact ref/hash، criteria results، reports reviewer/Head، defects باز، مصرف معلوم/نامعلوم، محدودیت‌ها و action بعدی در صورت نیاز است. Human acceptance/rejection در همین نسخه ثبت می‌شود. وقتی policy مشتری پذیرش کاملاً انسانی را الزام کرده، مدل هرگز issuer approval نیست؛ اگر پذیرش نوعی کار تحت delegation قبلی مجاز باشد، origin همان authority انسانی به‌وضوح ثبت می‌شود.

## ۱۴. بازیابی، نتیجهٔ نامعلوم و تعارض سیاست

```text
function RECOVER_TASK(task):
    stop issuing new dispatch until leases and checkpoints classified
    for each prior operation:
        if known complete with matching artifact/evidence:
            restore completion; do not execute again
        else if proved never sent:
            release not-sent commitment; mark eligible for fresh admission
        else:
            preserve unknown resources and effect status
            inspect authorized destination or provider request status
            if status remains uncertain: ESCALATE/WAITING_APPROVAL
    revalidate current authorization, criteria, capability and balances
    resume only known-safe checkpoint with original counters
```

idempotency کلید محلی duplicate درخواست Flux را مهار می‌کند، اما exactly-once سرویس بیرونی را تضمین نمی‌کند. برای operation اثرگذار، `operation_key`، request ID و proof مقصد لازم‌اند. crash بین ارسال و ثبت پاسخ، «شکست قطعی بدون اثر» نیست.

هر run قرارداد شروع و snapshot تاریخی را حفظ می‌کند؛ authorization مجوز انجام اقدام تازه را با policy/revocation فعلی می‌سنجد. سیاست جدید restrictive فوراً جلوی اقدام را می‌گیرد؛ اصل immutable بودن criteria مجوز bypass revocation نیست. اگر تغییر policy اجرای قرارداد قدیمی را ناممکن کند، کار متوقف و قرارداد/تصمیم انسانی تازه لازم می‌شود؛ تاریخچه قبلی معتبر به همان شرایط زمان خود می‌ماند.

## ۱۵. دو مثال مرحله‌به‌مرحله

### ۱۵٫۱. رفع باگ «پروژه و حافظه»

۱. Head گزارش کاربر را به قرارداد مشاهده‌پذیر تبدیل می‌کند: انتخاب این گزینه باید در ظاهر جاری بماند و داده‌های قبلی نمایش داده شوند. دلیل باگ هنوز hypothesis است؛ مشاهدهٔ UI، route و handler باید بررسی شود.

۲. gate بررسی می‌کند read/edit/browser در workspace مجاز است و هدف شامل ادغام خودکار JEV نیست. executor ابتدا source route و browser observation را جمع می‌کند؛ نتیجهٔ قبلی NotebookLM جای مشاهدهٔ current UI نیست.

۳. executor نسخهٔ اصلاح‌شده را تولید و hash می‌کند. reviewer روی همان نسخه، کلیک واقعی، data visibility و widths مرتبط را بررسی می‌کند. «کد route را تغییر دادم» به‌تنهایی AC-NAV-01 را PASS نمی‌کند.

۴. اگر ظاهر جاری حفظ شده ولی notes نمایش داده نشوند، criterion اول PASS و دوم FAIL است؛ نامزد پذیرش ساخته نمی‌شود. Head defect دقیق و روش repair متفاوت می‌دهد. هیچ معیار حذف نمی‌شود.

۵. اگر هر دو با شاهد برقرارند، Head تناسب تغییر و reviewer پوشش معیار را ثبت می‌کنند؛ نامزد به انسان می‌رود. packaging/publication نصب فعلی اگر خارج از authority اصلاح باشد action جدا با همان نسخه و مجوز خودش است.

### ۱۵٫۲. گزارش سفارش‌های مشتری

شرکت export گزارش را می‌خواهد؛ دادهٔ سفارش فقط برای بخش عملیات مجاز و ارسال ایمیل مشتری نیازمند تأیید است. Head کار را به schema، اجرا، تست و مستندات تقسیم می‌کند. توسعه schema می‌تواند با دادهٔ synthetic مجاز پیش برود؛ executor حق کپی دادهٔ واقعی به provider نامجاز ندارد.

اگر schema آماده و test runner مجاز باشد، review با synthetic fixtures انجام می‌شود. ارسال فایل نهایی به مشتری تا approval مقصد در WAITING_APPROVAL می‌ماند. نامزد پذیرش فایل export، ایمیل را خودکار ارسال نمی‌کند. اگر effect ارسال پس از crash نامعلوم باشد، RECOVERING ابتدا وضعیت مقصد را بررسی می‌کند؛ reply مدل که «حتماً نرسیده» مجوز resend نیست.

## ۱۶. معیار پذیرش پیاده‌سازی آینده

| ID | سناریو | انتظار قطعی |
|---|---|---|
| DM-01 | model پیشنهاد tool خارج allowlist می‌دهد | DENY پیش از dispatch؛ model upgrade اجرا نمی‌شود |
| DM-02 | PDF/RAG دستور افزایش budget دارد | policy unchanged؛ content فقط source data |
| DM-03 | Head role دادهٔ بخش دیگر را می‌خواهد | ACL اعمال؛ سلسله‌مراتب bypass نیست |
| DM-04 | criterion توسط executor حذف/required=false می‌شود | contract mismatch؛ artifact نامزد نمی‌شود |
| DM-05 | verdict ACCEPT با failed criterion همزمان | schema conflict؛ هیچ normalize-to-success |
| DM-06 | passed criteria تعداد درست ولی IDs نامرتبط | رد review؛ count مساوی کافی نیست |
| DM-07 | test ضروری NOT_RUN | ACCEPT_CANDIDATE مسدود |
| DM-08 | artifact پس از review ویرایش شود | hash mismatch؛ review و approval قبلی معتبر برای نسخهٔ تازه نیست |
| DM-09 | یکی از dependencies فاقد witness/hash معتبر | branch شروع نمی‌شود؛ independent siblings قابل admission |
| DM-10 | DAG دارای cycle/self/duplicate/unknown dep | بدون executor call، plan رد |
| DM-11 | تلاش اول defect مشخص، مدل قوی‌تر unavailable | escalation یا alternative صریح مجاز؛ fallback پنهان صفر |
| DM-12 | تلاش دوم همان defect را بدون method delta تکرار کرده | سوم dispatch نمی‌شود؛ ESCALATED |
| DM-13 | split repair task با نام‌های تازه | همان repair group/root counters؛ سقف سه تلاش حفظ |
| DM-14 | transient retry بعد از timeout | هزینه/call جدید؛ generation attempt کیفی افزایش بی‌دلیل ندارد |
| DM-15 | auth/schema error ثابت | retry گذرای خودکار ندارد؛ failure/needs info مستند |
| DM-16 | review PASS ولی Head conflict دارد | ESCALATED با هر دو گزارش؛ dissent حذف نمی‌شود |
| DM-17 | local turn completed با متن «تست پاس شد» | فقط completed CLI؛ پذیرش نیازمند گزارش واقعی آزمون |
| DM-18 | approval معتبر قبلی همان tool/path/destination/action | بدون درخواست تکراری؛ gate scope/expiry را ثبت می‌کند |
| DM-19 | approval شروع کار، publication پیشنهاد می‌شود | مجوز انتشار جدا لازم؛ ACCEPTED مجوز dispatch عمومی نیست |
| DM-20 | policy revoked بین plan و dispatch | action متوقف؛ historical snapshot حفظ |
| DM-21 | response دیررس پس از cancel | artifacts/usage ثبت؛ state=CANCELLED باقی |
| DM-22 | unknown payment/message بعد از crash | RECOVERING و وضعیت مقصد؛ replay کور صفر |
| DM-23 | JEV candidate ولی semantic sufficiency unverified | تکمیل evidence محدود یا gap؛ confidence احتمالی اختراع نمی‌شود |
| DM-24 | company relevance unclear | NEEDS_INFO؛ specialist اجرا نمی‌شود |
| DM-25 | یک route قطعی همهٔ معیارها را پوشش می‌دهد | تماس Head/model غیرضروری حذف با ثبت route و policy |
| DM-26 | دو عامل state version یکسان را تغییر می‌دهند | یکی commit؛ دیگری stale-version conflict |
| DM-27 | quota/budget یک branch کافی نیست | BLOCKED_BUDGET؛ مصرف/root قبلی حفظ |
| DM-28 | مدل جدید ابزار/structured output لازم را ندارد | route capability رد، نقش اجرایی پنهانی تغییر نمی‌کند |
| DM-29 | reviewer defect دارد ولی شاهد/criterion ندارد | REVISE غیرقابل اقدام پذیرفته نمی‌شود؛ clarification/escalation |
| DM-30 | انسان معیار را تغییر می‌دهد | revision/task lineage تازه؛ counters و تاریخچه پنهان نمی‌شوند |

تست‌های موجود برای وضعیت فعلی: `test_head_rejection.py` relevance legacy، `test_dag_validation.py` گراف، `test_verification.py` not_run و immutability، `test_retry_limits.py` transport caps، `test_local_agents.py` cycle/stream/session، `test_restart_recovery.py` persistence. این تست‌ها جای سناریوهای DM-01 تا DM-30 مقصد را نمی‌گیرند.

## ۱۷. منابع، نگاشت و تصمیم‌های باقی‌مانده

| مرجع سورس/سند | محل دقیق | موضوع |
|---|---|---|
| [`task.py`](../../src/flux/contracts/task.py) | `TaskInput`, `validate_task_pre_api` | contract فعلی، root_id، معیارهای string و max_attempts |
| [`head.py`](../../src/flux/contracts/head.py) | `HeadOutput`, `SubtaskSpec` | relevance، risk، assigned roles و سقف پنج |
| [`reviewer.py`](../../src/flux/contracts/reviewer.py) | `ReviewDecision.validate_rules` | شرط verdict و blocking issue فعلی |
| [`run.py`](../../src/flux/contracts/run.py) | `RunState`, `RunResult` | stateهای legacy و human_acceptance_required |
| [`orchestrator.py`](../../src/flux/engine/orchestrator.py) | `_workflow`, `_execute_subtask`, `_call`, `_context`, `resume_run` | routing، review normalization، عدم repair loop، calls و resume |
| [`dag.py`](../../src/flux/engine/dag.py) | `DAGValidator.validate_and_tier` | topological validation فعلی |
| [`state_machine.py`](../../src/flux/engine/state_machine.py) | `VALID_TRANSITIONS`, `validate_transition` | transitionهای legacy؛ مستقل از جدول مقصد |
| [`runtime.py`](../../src/flux/local_agents/runtime.py) | `ChatSpec`, `TurnSpec`, `command_for`, `EventParser`, `LocalRuntime` | cycle CLI، access، session و اتمام نوبت |
| [`gapgpt.py`](../../src/flux/providers/gapgpt.py) | `GapGPTAdapter.generate` | resend داخلی ۴۰۰ و scope transport |
| [`verification.py`](../../src/flux/agents/verification.py) | `VERIFICATION_SYSTEM_PROMPT`, `build_verification_prompt` | دستور reviewer فعلی؛ متن دستور جای gate نیست |
| [`mvp-design.fa.md`](../mvp-design.fa.md) و [`hierarchy.fa.md`](../hierarchy.fa.md) | قرارداد/اصلاح/اختیار | سابقهٔ طراحی؛ ادعای current implementation از سورس جدا |
| [`local-agents.fa.md`](../local-agents.fa.md) | چرخه و محدودیت‌ها | مرز completed CLI و قبول سازمانی |
| [`REPORT.fa.md`](../../experiments/jev_v2_rewrite_20261001/REPORT.fa.md) | کفایت، benchmark و محدودیت | candidate شواهد با semantic sufficiency unverified |
| وایت‌پیپر Flux، صفحات ۴–۹، ۱۱–۱۳ و ۱۷–۱۸ | hierarchy، gate، سه تلاش، اختیار و readiness | الزامات محصول مقصد |
| [مدیریت توکن و منابع](02-token-management.fa.md) | admission و ledger مقصد | تمام actionهای مصرف‌کننده زیر قیود مستقل منابع |
| [حافظه و RAG](04-memory-and-rag.fa.md) | نسخه/ACL/منشأ/کفایت | ورودی evidence gate |

تصمیم‌های لازم پیش از runtime سازمانی: policy registry و صاحب انسانی، قرارداد delegation، taxonomy ابزار و مقصد، مدل‌های capability-verified هر task class، runner دارای شاهد واقعی، independent reviewer assignment، format evidence، transition guards و repair lineage، روش reconciliation و enforcement درگاه ابزار. این تصمیم‌ها نباید با حدس Head یا متن پیشنهادی مدل به وضعیت «ساخته‌شده» تبدیل شوند.
