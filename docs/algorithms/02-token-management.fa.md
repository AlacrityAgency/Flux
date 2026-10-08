# الگوریتم مدیریت توکن، هزینه و سهمیهٔ Flux

نسخهٔ طراحی: ۱٫۰ — تاریخ بررسی سورس: ۱ اکتبر ۲۰۲۶ — پروژه: `alacrity-flux`

این سند قرارداد اجرایی پیشنهادی برای کنترل منابع سازمان هیبرید است. هدف، تحویل خروجی قابل پذیرش در حدود اختیار و منابع است؛ کم کردن متن بدون حفظ شاهد، موفقیت این الگوریتم محسوب نمی‌شود. اعداد مثال‌ها فرضی‌اند و تعرفهٔ زندهٔ هیچ ارائه‌دهنده‌ای نیستند.

سه موضوع را باید جدا نگه داشت: موتور قدیمی پنج نقش، مسیر فعلی گفت‌وگوی CLI در نسخهٔ ۰٫۴، و معماری سازمانی پیشنهادی. نوشتن این سند اتصال JEV به Flux، مهاجرت دیتابیس یا اجرای این الگوریتم در محصول ایجاد نمی‌کند. آزمایش و Skill مستقل JEV باید پیش از هر ادغام محصولی ارزیابی شوند.

## ۱. وضعیت واقعاً پیاده‌شده و فاصله تا مقصد

| مسیر | رفتار موجود در سورس | محدودیت نسبت به این طراحی |
|---|---|---|
| `BudgetLedger.reserve_for_call` | تخمین ورودی و حداکثر خروجی، snapshot دو نرخ، ثبت رزرو پیش از تماس | estimator نویسه‌ای؛ snapshot فاقد نسخه و همهٔ اقلام تعرفه |
| `Repository.reserve_budget` | سقف هر `run` و سقف روزانهٔ workspace؛ احتساب known/reserved/unknown؛ قفل همان repository | شرکت، بخش و root مشترک ندارد؛ تضمین چند فرایند/چند اتصال از قفل Python حاصل نمی‌شود |
| `Repository.settle_reservation` | مصرف معلوم را تسویه و مصرف نامعلوم را `held_unknown` می‌کند | این تابع فقط رزرو `active` را می‌پذیرد؛ مسیر تسویهٔ بعدی `held_unknown` ساخته نشده است |
| `FluxEngine._call` | حداکثر ۲۰ تماس run، Head حداکثر دو ارسال، بقیه حداکثر سه ارسال؛ deadline فعال ۱۲۰۰ ثانیه | سقف مشترک خانوادهٔ root، حاشیهٔ محفوظ بازبینی و سه تلاش اصلاح کیفی پیاده نشده‌اند |
| `GapGPTAdapter.generate` | usage از provider، SDK با `max_retries=0` | روی ۴۰۰ ناسازگاری پارامتر یک ارسال داخلی دیگر ممکن است؛ هر ارسال باید در مقصد دفتر جدا داشته باشد |
| `LocalRuntime` در نسخهٔ ۰٫۴ | CLI واقعی، usage خام نشست/نوبت، اجرای ترتیبی، timeout و لغو | از `BudgetLedger` استفاده نمی‌کند؛ سقف دلاری موتور قدیمی به اشتراک منتقل نشده است |
| `QuotaMonitor` | خواندن بازه‌های سهمیه، cache و نمایش snapshot قدیمی/ناموجود | درصد سهمیه دفتر توکن یا رزرو هزینهٔ API نیست |
| JEV مستقل | سقف دقیق متن شواهد با tokenizer محلی و خروجی دارای منشأ | کنترل کل prompt، تاریخچهٔ CLI، output، صورتحساب یا سهمیهٔ اشتراک نیست |

`config/pilot.json` طرح تاریخی پایلوت با ۳۲ تماس را ثبت می‌کند؛ سقف hard-coded موتور قدیمی اکنون ۲۰ تماس است. در اجرای واقعی، رفتار کد مرجع وضعیت موجود است. عدد ۵۰ دلار آن config نیز بودجهٔ یک پایلوت تاریخی است و بودجهٔ جاری یا ماهانهٔ شرکت محسوب نمی‌شود.

مبنای مقصد، وایت‌پیپر صفحه‌های ۸–۹، ۱۰ و ۱۲–۱۳ است: تلاش محدود، حافظهٔ منتخب، سقف شرکت و بخش و کار، رزرو پیش از تماس، حفظ هزینهٔ نامعلوم و انتخاب مدل واجد توانایی.

## ۲. واحدهای اندازه‌گیری؛ کدام عدد چه معنایی دارد؟

| کمیت | تعریف و واحد | کاربرد | نباید به آن نسبت داده شود |
|---|---|---|---|
| `evidence_tokens_local` | تعداد توکن متن نهایی بستهٔ شواهد با tokenizer مشخص | کنترل دقیق طول همان بسته | توکن قطعی provider یا کل prompt |
| `input_tokens_local` | شمارش محلی همهٔ بخش‌های قابل مشاهدهٔ request | برآورد قبل از تماس API | tokenizer/صورتحساب تضمین‌شدهٔ provider |
| `provider_input_tokens` | usage ورودی گزارش‌شدهٔ provider، با scope معلوم | تسویه/گزارش مصرف | تعداد صرفاً شواهد |
| `provider_output_tokens` | خروجی صورتحساب‌پذیر طبق قرارداد adapter | تسویه و سقف خروجی | طول متن قابل مشاهده به‌تنهایی |
| `reserved_usd_micros` | تعهد داخلی پیش از ارسال؛ میلیونیم دلار | کنترل رقابت هزینه | هزینهٔ قطعی پرداخت‌شده |
| `settled_usd_micros` | هزینهٔ معلوم، با منشأ و مبنای محاسبه | دفتر مصرف معلوم | تأیید مستقل صورتحساب خارجی |
| `remaining_percent` | درصد باقی‌ماندهٔ یک بازهٔ حساب اشتراکی | نمایش و admission محافظه‌کارانه | اعتبار دلاری یا تعداد توکن قابل خرج |
| `physical_dispatch_count` | شمار ارسال‌های مشاهده‌شده، شامل خطا و retry؛ موارد نامعلوم جدا | گزارش شبکه | تعداد تلاش اصلاح کیفی یا تعداد reservation |
| `generation_attempt` | نسخهٔ تولید/اصلاح یک leaf | سقف سه تلاش کیفی | retry انتقال همان request |

برای admission، شمارندهٔ جداگانهٔ `root_call_slots_committed` از قبل رزرو می‌شود و تماس ممکن‌الارسال نامعلوم را هم محدود می‌کند. این شمارنده با تعداد ارسال فیزیکی قطعی یکی نیست: رزرو بدون ارسال یا crash میان marker و شبکه ممکن است داشته باشیم. mode پایه با احتساب محافظه‌کارانهٔ همهٔ slotهای admitted سقف call را حفظ می‌کند؛ آزاد کردن slot فقط در صورت policy صریح و اثبات not-sent مجاز است. cache-read ورودی معمولاً زیرمجموعهٔ input گزارش‌شده است؛ قرارداد adapter باید این رابطه را مشخص کند. reasoning ممکن است زیرمجموعهٔ output باشد. جمع کردن دوبارهٔ این فیلدها ممنوع است مگر قرارداد provider صریحاً آن‌ها را جدا تعریف کرده باشد. فیلد ناموجود `null` است؛ صفر فقط با شاهد مصرف صفر ثبت می‌شود.

## ۳. هویت و مرز منابع

تمام رخدادهای منابع مقصد این شناسه‌ها را حمل می‌کنند:

```json
{
  "tenant_id": "alacrity-internal",
  "department_id": "technical",
  "project_id": "alacrity-flux",
  "root_task_id": "root-20261001-001",
  "task_id": "task-token-spec",
  "policy_revision": 7,
  "artifact_hash": "sha256:<artifact-bytes>",
  "acceptance_criteria": [
    {
      "criterion_id": "AC-BUDGET-01",
      "text": "تمام ارسال‌ها پیش از dispatch تعهد منابع قابل ردیابی دارند.",
      "required": true,
      "evidence_type": "test_execution"
    }
  ]
}
```

`policy_revision` عدد صحیح مثبت نسخهٔ سیاست است؛ نام نمایشی سیاست در فیلد جدا نگه داشته می‌شود. `evidence_type` از enum مشترک سند ۰۴ می‌آید؛ برای این معیار گزارش آزمون دفتر/رقابت و refهای مربوط همراه `test_execution` ذخیره می‌شوند. در سورس legacy نام فیلد `root_id` است؛ در قرارداد مقصد `root_task_id` استفاده می‌شود. adapter مهاجرت باید نگاشت صریح انجام دهد؛ ایجاد task جدید، تغییر مدل، ارجاع یا بازطراحی root، هزینهٔ قدیمی را حذف نمی‌کند.

هر تماس به یک root و یک بخش پرداخت‌کننده تعلق دارد. کار میان‌بخشی چند زیرکار با بخش پرداخت‌کنندهٔ مشخص دارد؛ جمع هزینهٔ آن‌ها زیر همان root باقی می‌ماند. یک هزینه داخل هر ledger فقط یک بار شمارش می‌شود. حضور همان هزینه در گزارش شرکت و بخش و root، گزارش تجمیعی چند سطح است و جمع کردن این گزارش‌ها با هم مجاز نیست.

بودجه‌های فعال هر تماس از registry سیاست معتبر تعیین می‌شوند:

```text
deployment/global safety ceiling
    → tenant/company period ceiling
    → department period ceiling
    → optional project period ceiling
    → root_task total ceiling
    → optional task/attempt ceiling
```

سقف global متعلق به کنترل‌کنندهٔ استقرار است و مجوز دسترسی به دادهٔ مشتریان ایجاد نمی‌کند. سقف شرکت برابر tenant مربوط است. همهٔ سقف‌های محدودکننده باید برقرار باشند؛ داشتن اعتبار root، عبور از سقف بخش را مجاز نمی‌کند. شناسهٔ budget و دورهٔ زمانی در رزرو ثابت می‌شود. گزارش تاریخی روزانهٔ legacy به روز UTC ایجاد run متصل است؛ مقصد دوره و timezone را صریح ثبت می‌کند. نمایش کاربر می‌تواند `Asia/Tehran` باشد، اما محاسبهٔ مرز دوره بدون `period_start/end/timezone` ممنوع است.

## ۴. ناورداهای الزامی

برای هر budget `b`:

```text
available(b) = approved_cap(b) − settled_known(b)
               − reserved_inflight(b) − held_unknown(b)

admit(next) ⇔ for every applicable b:
    settled_known(b) + reserved_inflight(b) + held_unknown(b)
    + next_commitment(b) <= approved_cap(b)
```

۱. شرط admission پیش از هر ارسال روی تمام سقف‌ها در یک تراکنش برقرار می‌شود. دو کارگر حق ندارند همزمان یک remaining را خرج کنند.

۲. unknown یک طبقه از تعهد باز است، نه هزینهٔ صفر. تبدیل active به unknown مقدار کل تعهد را کم نمی‌کند. یک reservation همزمان در دو طبقه شمارش نمی‌شود.

۳. `settled_known` گزارش حقیقت است. اگر مصرف واقعی از رزرو بیشتر شد، actual واقعی ثبت می‌شود حتی اگر invariant برنامه‌ریزی نقض شود؛ سپس budget breach ثبت و ارسال بعدی متوقف می‌شود. تغییر actual برای زیبا کردن سقف ممنوع است.

۴. رزرو تولید، سهم بازبینی ضروری را مصرف نمی‌کند. پیش از آغاز تولید، حداقل مسیر «تولید + بازبینی لازم + جمع‌بندی لازم» امکان تأمین دارد.

۵. تمام retryها، زیرکارها، Headها، بازبین‌ها و اصلاح‌ها به سقف root متصل‌اند. شمارنده‌ها با restart یا تغییر مسیر صفر نمی‌شوند.

۶. `count_tokens(rendered_evidence) <= evidence_budget` دقیقاً روی متن نهایی برقرار است. خارج بودن framing و output از این عدد باید در metadata و گزارش روشن باشد.

۷. اندازهٔ context، هزینه، تعداد call، تعداد تلاش و deadline قیود مستقل‌اند. برقرار بودن یکی جای بقیه را نمی‌گیرد.

۸. role، model و billing mode سه فیلد مستقل‌اند. انتخاب مدل گران‌تر، نقش جدید، مجوز جدید یا افزایش cap ایجاد نمی‌کند.

## ۵. قرارداد دادهٔ دفتر مقصد

### ۵٫۱. snapshot تعرفه و قابلیت

```text
PriceSnapshot {
  snapshot_id, provider_id, actual_model_id, billing_mode: API,
  currency: USD, effective_at, verified_at, verification_source,
  input_uncached_per_million, input_cached_per_million?,
  output_per_million, reasoning_billing_relation,
  additional_billable_items[], rounding_rule, revision, verified
}

CapabilitySnapshot {
  model_id, account_route_id, checked_at, status,
  context_limit?, max_output_limit?, output_limit_includes_reasoning?,
  supported_task_classes[], data_destinations[],
  usage_scope: PER_REQUEST | CUMULATIVE_SESSION | UNKNOWN,
  hard_cost_bound_supported, verification_refs[]
}
```

قیمت‌ها با Decimal یا واحد صحیح نگه داشته می‌شوند. رزرو رو به بالا به واحد دفتر گرد می‌شود تا rounding باعث کسری نشود. نرخ fallback بالای `pricing.py` در مسیر قدیمی ابزار تخمین است؛ نرخ قابل اتکا و مجوز یک مدل ناشناخته نیست. در mode دارای سقف سخت، تعرفه یا کران نامعلوم باعث عدم admission آن مسیر می‌شود؛ Head حق ندارد با نرخ فرضی اجرای زنده را مجاز کند.

### ۵٫۲. رزرو و usage

```text
Reservation {
  reservation_id, physical_request_id, operation_key,
  tenant_id, department_id, project_id, root_task_id, task_id,
  role_id, agent_id, model_id, billing_mode,
  budget_bindings[{budget_id, period_id, amount_usd_micros}],
  policy_revision, price_snapshot_id, capability_snapshot_id,
  prompt_hash, evidence_pack_hash?, local_tokenizer_id,
  estimated_input_tokens, max_billable_output_tokens,
  amount_usd_micros, generation_attempt, transport_attempt,
  status, dispatch_marker?, provider_request_id?, created_at
}

UsageRecord {
  physical_request_id, reservation_id, provider_request_id?,
  provider_input_tokens?, cached_input_tokens?, provider_output_tokens?,
  reasoning_tokens?, raw_usage_hash?, usage_scope,
  actual_usd_micros?, cost_basis: PROVIDER_REPORT | PRICE_SNAPSHOT | UNKNOWN,
  invoice_reconciled: false, observed_at
}
```

`physical_request_id` برای هر ارسال یکتاست؛ `operation_key` تلاش‌های یک عملیات منطقی را گروه می‌کند. روی settlement همان request قید uniqueness وجود دارد. raw usage با دادهٔ حداقلی ذخیره می‌شود و هیچ secret یا header احراز هویت وارد دفتر نمی‌شود.

### ۵٫۳. snapshot سهمیهٔ اشتراک

```text
SubscriptionQuotaSnapshot {
  account_route_id, provider_id, checked_at,
  availability: AVAILABLE | UNAVAILABLE,
  freshness: FRESH | STALE | UNKNOWN,
  windows[{window_id, remaining_percent?, resets_at?, window_minutes?}],
  shared_account: true, source_protocol_revision?, detail_code
}
```

این شیء مبلغ رزرو ندارد. هزینهٔ تخمینی نشست Claude با `cost_scope=session_estimate` در دفتر پرداخت API ثبت نمی‌شود. دو usage تجمعی نشست بدون رابطهٔ monotonic و scope معتبر نباید جمع شوند؛ تفاضل فقط در صورت اثبات همان نشست، همان تعریف counter و عدم reset مجاز است.

## ۶. بودجهٔ متن و آماده‌سازی request

### ۶٫۱. قرارداد شمارش محلی

در Skill مستقل JEV، شمارندهٔ `o200k_base` روی رشتهٔ نهایی اعمال می‌شود. metadata لازم:

```json
{
  "budget_scope": "rendered_evidence_text",
  "tokenizer_id": "tiktoken:o200k_base",
  "budget_tokens": 3000,
  "rendered_tokens": 2844,
  "includes": ["source_labels", "provenance", "selected_excerpts", "gap_warnings"],
  "excludes": ["system_and_task_framing", "output", "native_cli_history", "provider_hidden_context"],
  "semantic_sufficiency": "unverified"
}
```

عدد مثال نمایندهٔ یک قرارداد است؛ برای هر بسته دوباره شمرده می‌شود. tokenizer محلی شمارش دقیق همین رشته را می‌دهد، اما تطابق با tokenizer یا billing provider ادعا نمی‌شود. برآورد موجود `int(len(text)/2.5)+20` نه `ceil` واقعی است و نه کران تضمین‌شده؛ حتی اگر توضیح کد آن را conservative بخواند.

### ۶٫۲. تقسیم context در API دارای ورودی قابل مشاهده

```text
context_capacity >= fixed_framing + contract + role_instructions
                    + evidence + dependency_summaries + tool_schema
                    + preserved_history + max_output + safety_margin

evidence_budget = min(task_evidence_cap,
                      capacity − all_other_required_parts)
```

اجزای mandatory با کاهش criterion، حذف سیاست یا کوچک کردن شاهد لازم فشرده نمی‌شوند. اگر fixed parts ظرفیت را پر کنند، admission رد و تقسیم کار/مدل دارای ظرفیت کافی پیشنهاد می‌شود. prior outputهای بزرگ به خلاصهٔ نسخه‌دار همراه ref/hash تبدیل می‌شوند؛ متن قطع‌شده بی‌علامت، شاهد کامل نیست.

در CLI ادامهٔ نشست، history و compacting توسط خود CLI مدیریت می‌شود. Flux نمی‌تواند از شمارش prompt جدید، سقف کل context یا صورتحساب آن نشست را نتیجه بگیرد. کنترل دقیق شواهد تازه همچنان مفید است، اما `total_context_bounded=false` می‌ماند مگر adapter اطلاعات لازم را واقعاً فراهم کند.

### ۶٫۳. شبه‌کد بسته‌بندی نهایی

```text
function BUILD_BOUNDED_EVIDENCE(candidates, criteria, token_cap, tokenizer):
    eligible = FILTER_AUTHORIZED_CURRENT_PROJECT_SOURCES(candidates)
    chosen = SELECT_PER_CRITERION_WITH_SOURCE_PROVENANCE(eligible, criteria)
    rendered = RENDER(chosen, provenance=true, explicit_gaps=true)
    while COUNT(tokenizer, rendered) > token_cap:
        change = REMOVE_LOWEST_VALUE_OPTIONAL_UNIT_OR_MERGE_OVERLAP(chosen)
        if change unavailable:
            return MISSING_EVIDENCE_WITH_BOUNDED_WARNING(token_cap)
        chosen = APPLY(change)
        rendered = RENDER(chosen, provenance=true, explicit_gaps=true)
    assert COUNT(tokenizer, rendered) <= token_cap
    return PACK(rendered, hash(rendered), tokenizer, scope, criterion_map)
```

قیمت متادیتا و warning نیز حساب می‌شود؛ مجموع token count قطعه‌های جدا ممکن است با شمارش رشتهٔ الحاق‌شده فرق کند، بنابراین assert نهایی روی render کامل ضروری است. حافظهٔ معنایی بزرگ نباید وسط جمله قطع و همچنان کامل اعلام شود. حذف بخش کد با علامت excerpt و حدود برش ثبت می‌شود؛ guard، امضا و expression چندخطی موردنیاز باید باقی بمانند.

Head می‌تواند نقشهٔ شواهد و gaps را دریافت کند؛ کارگر و بازبین بستهٔ مرتبط با نقش خود را می‌گیرند. این کاهش تکرار یک پیشنهاد است. در legacy `build_head_prompt` فیلد context دارد و `_context` دوباره `reference_context` اضافه می‌کند؛ این تکرار در وضعیت جاری وجود دارد و این سند آن را به‌تنهایی اصلاح نمی‌کند.

## ۷. محاسبه و رزرو هزینهٔ API

در ساده‌ترین تعرفهٔ تأییدشده:

```text
reserve = ceil_money_unit(
    input_upper_bound × price_input / 1_000_000
  + output_billable_upper_bound × price_output / 1_000_000
  + other_billable_upper_bounds
)
```

در تخمین قبل از تماس، تخفیف cache نامطمئن فرض نمی‌شود. پس از usage معتبر، اگر cached input زیرمجموعهٔ input باشد:

```text
actual = (input_total − input_cached) × uncached_rate
       + input_cached × cached_rate
       + billable_output × output_rate
       + other_confirmed_billable_items
```

همهٔ اجزا در واحد قیمت معتبر اعمال می‌شوند. اگر pricing snapshot فقط نرخ ordinary input/output داشته باشد، محاسبه همان تعریف را ثبت می‌کند؛ نباید نام «actual invoice» بگیرد. اگر provider هزینهٔ مستقیم بدهد، مبنای `PROVIDER_REPORT` ثبت و برای تطبیق بعدی با صورتحساب نگهداری می‌شود.

### ۷٫۱. سهم محفوظ بازبینی

در تصویب plan، root یک `mandatory_completion_envelope` دارد: هزینهٔ بازبینی leafهای ضروری، یکپارچگی Head بخش و بستهٔ نامزد پذیرش. این envelope داخل تعهدات root و بودجه‌های پرداخت‌کننده رزرو می‌شود. هنگام ارسال call بازبینی، تعهد همان قسمت به reservation فیزیکی تبدیل می‌شود؛ مبلغ دوباره جمع نمی‌شود. ویرایش plan باید envelope را در همان تراکنش دوباره محاسبه کند.

زمانی که review cost هنوز کران قابل اتکا ندارد، تولیدی که وابسته به آن است شروع نمی‌شود. آزادسازی envelope پس از لغو/پایان فقط برای بخش بدون dispatch مجاز است. افزایش model/output که review envelope را ناکافی می‌کند نیازمند admission تازه و در صورت نبود اختیار، درخواست انسانی است.

### ۷٫۲. تراکنش admission

```text
function ADMIT_API_DISPATCH(call, expected_task_version):
    capability = VERIFIED_CAPABILITY(call.model, call.account_route)
    price = VERIFIED_PRICE(call.model, call.billable_items)
    bounds = COMPUTE_REQUEST_AND_COMPLETION_BOUNDS(call, capability, price)
    if bounds unavailable: return BLOCK(reason=UNBOUNDED_COST)

    begin serializable transaction:
        task = LOCK_TASK(call.task_id)
        require task.version == expected_task_version
        require VALID_ACTION_POLICY_NOW(call, task.policy_revision)
        require task.state allows dispatch and task not cancelled
        require root_call_slots_committed + 1 <= approved_max_calls
        require generation/transport/time/depth limits remain
        budgets = LOCK_ALL_APPLICABLE_BUDGETS_IN_STABLE_ORDER(call)
        require ALL_BALANCES_ALLOW(bounds.next_commitments)
        require MANDATORY_COMPLETION_ENVELOPE_REMAINS_FUNDED
        reservation = INSERT_UNIQUE_RESERVED_REQUEST(call, bounds)
        APPLY_COMMITMENTS_TO_ALL_BUDGET_BINDINGS(reservation)
        INCREMENT_DURABLE_ROOT_CALL_SLOT_COMMITMENT(root)
        INSERT_OUTBOX_REQUEST(reservation, payload_hash, policy_revision)
        WRITE_RESOURCE_EVENT(reason, before_after, reservation_id)
    commit
    return reservation
```

قفل پایگاه داده یا isolation واقعی باید از «خواندن remaining تا ثبت رزرو» محافظت کند. قفل Python فقط محافظ همان فرایند است. هیچ provider call داخل تراکنش طولانی شبکه نگه داشته نمی‌شود؛ تراکنش کوتاه، رزرو پایدار و outbox بعدی لازم‌اند. task/policy قبل از dispatch دوباره بررسی می‌شوند تا لغو یا revocation بین plan و اجرا نادیده نماند.

## ۸. چرخهٔ رزرو، ارسال و تسویه

```text
RESERVED ── durable dispatch intent ──> DISPATCH_STARTED
RESERVED ── proof of never sent ──────> RELEASED_NOT_SENT
DISPATCH_STARTED ── valid usage ─────> SETTLED
DISPATCH_STARTED ── unknown result ──> HELD_UNKNOWN
HELD_UNKNOWN ── reconciled usage ────> SETTLED
HELD_UNKNOWN ── proved no charge ────> RELEASED_CONFIRMED
```

`DISPATCH_STARTED` به معنای اثبات دریافت provider نیست؛ marker قبل از ارسال پایدار می‌شود و crash بعد از آن محافظه‌کارانه نامعلوم تلقی می‌شود. request ID provider در اولین زمان ممکن ذخیره می‌شود. مرز marker و شبکه بدون idempotency سمت provider، تضمین exactly-once نمی‌دهد.

```text
function SETTLE(response_or_error, reservation):
    if no reliable usage or dispatch outcome uncertain:
        begin transaction:
            lock reservation and budget bindings
            if state == HELD_UNKNOWN: commit; return existing hold
            if state in SETTLED/RELEASED_NOT_SENT/RELEASED_CONFIRMED:
                record conflicting late observation; commit; return BLOCKED_RECONCILIATION
            require state == DISPATCH_STARTED
            MOVE_COMMITMENT(reserved → held_unknown) exactly once
            WRITE_EVENT(UNKNOWN_USAGE, provider_request_id?)
        commit
        return

    validated = VALIDATE_USAGE_SCOPE_AND_VALUES(response_or_error.usage)
    if invalid: treat as unknown; return
    actual = COST_FROM_PROVIDER_REPORT_OR_PRICE_SNAPSHOT(validated)
    begin transaction:
        lock reservation and budget bindings
        if already terminal with same settlement: commit; return prior result
        if terminal with conflicting settlement:
            record reconciliation conflict; commit; return BLOCKED_RECONCILIATION
        MOVE_FROM_RESERVED_OR_UNKNOWN_TO_KNOWN(actual)
        STORE_USAGE_AND_SETTLEMENT_ONCE
        if actual exceeds reservation or any cap:
            MARK_BUDGET_BREACH_AND_BLOCK_FURTHER_DISPATCH
        WRITE_EVENT(actual, basis, release_delta, usage_scope)
    commit
```

اگر cancellation قبل از ارسال قطعی باشد، رزرو آزاد می‌شود. اگر فرایند ارسال شده یا نتیجه نامعلوم است، cancel هزینه را صفر نمی‌کند. پاسخ دیررس فقط دفتر مصرف و شاهد را تکمیل می‌کند و task لغوشده را دوباره RUNNING/ACCEPTED نمی‌کند.

هیچ timeout، ۴۲۹، disconnect یا خطای parser به‌تنهایی شاهد نبود هزینه نیست. retry انتقال ممکن است مجاز باشد، اما مصرف نامعلوم قبلی حفظ و ارسال بعدی جدا رزرو می‌شود. ناسازگاری پارامتر provider نیز در مقصد ارسال جدید قابل ثبت است؛ retry مخفی adapter باعث عبور از دفتر ممنوع است.

## ۹. مثال‌های عددی و رقابت

### ۹٫۱. بستهٔ شواهد با کل prompt یکی نیست

فرض: ۲۹۴۰ توکن evidence، ۹۰۰ framing/contract، ۱۱۰۰ خلاصهٔ وابستگی و ۵۰۰ schema ابزار. ورودی محلی قابل مشاهده ۵۴۴۰ است. با output cap برابر ۲۰۰۰، ظرفیت لازم دست‌کم ۷۴۴۰ به‌علاوهٔ safety margin است. «بسته زیر ۳۰۰۰» درست است؛ «کل درخواست ۳۰۰۰» غلط است. اگر نشست CLI history نامعلوم داشته باشد، کل context همچنان نامعلوم است.

### ۹٫۲. حاشیهٔ بازبینی

نرخ فرضی ورودی ۱ و خروجی ۵ دلار/میلیون: تولید با upper input برابر ۴۰۰۰ و max output برابر ۲۰۰۰، رزرو `0.014 USD` دارد. بازبینی با ۳۰۰۰ ورودی و ۱۰۰۰ خروجی `0.008 USD` می‌خواهد. root با remaining برابر `0.020` نمی‌تواند مسیر `0.022` را شروع کند. گزینه‌های مجاز کاهش اجزای optional، مدل واجد توانایی ارزان‌تر یا درخواست افزایش سقف‌اند؛ حذف بازبینی لازم مجاز نیست.

### ۹٫۳. پنج سقف همزمان

availableهای فرضی: global=`0.080`، company=`0.050`، department=`0.018`، project=`0.040`، root=`0.030`. رزرو `0.022` به دلیل department رد می‌شود حتی اگر root جا داشته باشد. نتیجه `BLOCKED_BUDGET` همراه budget محدودکننده و مبلغ لازم است؛ Head نمی‌تواند بخش پرداخت‌کننده را فقط برای دور زدن سقف عوض کند.

### ۹٫۴. مصرف نامعلوم و retry

root cap=`0.100`، settled=`0.050`، open reservation=`0.020`. تماس timeout می‌شود: reserved صفر و held_unknown=`0.020`؛ available همچنان `0.030` است. retry با رزرو `0.040` رد می‌شود. اگر retry با رزرو `0.020` مجاز شود، تعهد کل `0.090` است. بعداً هزینهٔ تماس اول `0.015` مشخص می‌شود: held_unknown به صفر، settled به `0.065`، reservation دوم `0.020` و available=`0.015` تبدیل می‌شود.

### ۹٫۵. دو کارگر و actual بالاتر

دو کارگر هر کدام `0.030` می‌خواهند و remaining مشترک `0.050` است. تراکنش اول می‌پذیرد؛ دوم remaining=`0.020` را می‌بیند و رد می‌شود. اگر first actual=`0.060` باشد، دفتر `0.060` واقعی را نگه می‌دارد و breach را نشان می‌دهد؛ cap گذشته اصلاح نمی‌شود و تماس تازه متوقف می‌ماند. این مثال نشان می‌دهد internal reservation فقط با bounds/provider billing معتبر سقف را حفظ می‌کند.

## ۱۰. مسیر اشتراکی و سهمیهٔ opaque

در v0.4 ورود و مصرف را CLI ارائه‌دهنده اداره می‌کند. `cli_environment` متغیرهای API را از فرایند جدید حذف می‌کند تا route اشتراکی به route پرداخت API پنهانی عوض نشود. نباید credential CLI را به حافظه، بستهٔ RAG یا گزارش منتقل کرد.

درصد هر بازه حساب مشترک را توصیف می‌کند: ممکن است همان حساب خارج از Flux مصرف شود. کاهش ۳٪ سهمیه را نمی‌توان به توکن یا دلار ثابت تبدیل کرد. ظرفیت مدل، سقف tool، read/write permissions و region access نیز جدا از quota هستند.

```text
function ADMIT_SUBSCRIPTION_TURN(task, route, snapshot, policy):
    require task/route/data/tool authorization
    require local call/time/concurrency limits remain
    require account authentication and confirmed route support

    if any required FRESH window is explicitly exhausted:
        return BLOCKED_BUDGET(reason=SUBSCRIPTION_LIMIT, reset_info)
    if snapshot unavailable or stale:
        if policy permits bounded probe under opaque quota:
            allow one bounded turn; record QUOTA_UNKNOWN
        else:
            return WAITING_APPROVAL_OR_BLOCKED_BUDGET(reason=QUOTA_UNKNOWN)

    return ADMIT_WITHOUT_PROMISING_QUOTA_RESERVATION
```

`bounded probe` خودکار پیش‌فرض نیست؛ سیاست یا مجوز معتبر لازم دارد. در محصول فعلی admission فقط auth و حدود اجرای محلی را اعمال می‌کند و quota عمدتاً نمایشی است؛ این policy target پیاده‌شده تلقی نمی‌شود. تازه بودن snapshot احتمال پایان موفق را تضمین نمی‌کند. رد quota در حین stream به شکست/توقف ثبت می‌شود؛ partial artifact با همان hash قابل بررسی می‌ماند و موفقیت سازمانی اعلام نمی‌شود.

رفتار موجود `QuotaMonitor`: refresh معمولی cache ۶۰ ثانیه، refresh دستی حداقل فاصلهٔ ۳۰ ثانیه، fallback آخرین snapshot با `stale=true` و timestamp قدیمی، پاک شدن windows بعد از logout. `window` مقادیر نامعتبر/NaN/bool را نمی‌پذیرد؛ remaining درصد clamp می‌شود. این semantics در مقصد حفظ می‌شود؛ endpoint ناموجود یا stale هرگز «۰ مصرف» یا «۱۰۰٪ قطعی باقی‌مانده» نیست.

NotebookLM یک مسیر query روی منابع دفتر است. `usage` آن از ابزار گزارش می‌شود و شمارش local evidence جای quota/hidden retrieval خود سرویس نیست. Antigravity فقط پس از احراز قابلیت واقعی account/region و مجوز اجرا انتخاب می‌شود؛ نصب CLI و بودن گزینه در UI شاهد آمادگی route نیستند.

## ۱۱. توقف، بازیابی و افزایش بودجه

| وضعیت | اقدام موتور مقصد | چیزهایی که حفظ می‌شوند |
|---|---|---|
| بودجهٔ لازم برای تولید و review کافی نیست | `BLOCKED_BUDGET`، ادامهٔ شاخهٔ مستقل مجاز | counters، artifacts، unknown، criterion و root |
| افزایش cap توسط انسان | ثبت before/after و authority، revision جدید، admission مجدد | مصرف و تعداد تلاش قبلی |
| لغو task | جلوگیری از dispatch تازه، توقف lease محلی مجاز | اثرهای انجام‌شده و مصرف نامعلوم |
| crash با رزرو بدون dispatch | آزادسازی فقط با شاهد not-sent | رخداد رزرو و علت آزادسازی |
| crash با dispatch نامعلوم | `RECOVERING` و reconciliation، بدون replay کور | request ID، hold، checkpoints |
| تعرفه/قابلیت لغو یا نامعتبر شده | توقف route و پیشنهاد مسیر معتبر | policy snapshot تاریخی و هزینهٔ قبلی |
| بدون خروجی پذیرفته‌شده | شاخص cost/outcome برابر «بدون خروجی پذیرفته‌شده» | هزینه‌های همهٔ تلاش‌ها |

در legacy `resume_run` همیشه `False` است؛ در v0.4 `recover` نوبت‌های queued/running را `interrupted` می‌کند و ادامه فقط با پیام تازه انجام می‌شود. `RECOVERING` state مقصد است و اکنون state کد legacy یا local turn نیست.

درخواست افزایش بودجه باید دقیق باشد: معلوم/نامعلوم/رزرو، سقف محدودکننده، کار باقی‌مانده، bounds ادامه، شواهد آخرین artifact و مقدار درخواست. Head پیشنهاد می‌دهد؛ authority انسانی یا delegation معتبر تغییر cap را تصویب می‌کند. عدم پاسخ انسان cap را تغییر نمی‌دهد.

## ۱۲. بهره‌وری و ادعاهای قابل دفاع

اولویت بهینه‌سازی: حذف اجرای مدل غیرضروری، حذف context تکراری، بازیابی per-criterion، خلاصهٔ نسخه‌دار وابستگی، caching مجاز، مدل واجد توانایی و سپس اصلاح مسیر. حذف شاهد یا بازبینی برای پایین آوردن عدد مصرف، بهینه‌سازی پذیرفتنی نیست.

شاخص‌های جدا: local evidence tokens، provider input/output، dispatch count، generation attempts، settled/unknown، زمان فعال و انتظار، تعداد accepted artifact، نرخ پذیرش و هزینهٔ خروجی پذیرفته‌شده. هزینهٔ ابزار، زیرساخت و زمان انسانی با روش اندازه‌گیری خودشان گزارش می‌شوند؛ کاهش توکن لزوماً کاهش کل هزینه نیست.

گزارش JEV بازنویسی‌شده در ۱۲ سناریوی اضافی با سقف ۳۰۰۰، ۲۹/۴۳ شاهد در برابر ۱۹/۴۳ نسخهٔ قبلی و میانگین متن ۲۸۴۴ در برابر ۲۸۷۰ ثبت کرد. هر دو چهار سناریوی دارای تمام شواهد داشتند. این شاهد بهبود پوشش بازیابی محلی است؛ احتمال موفقیت، کیفیت کامل پاسخ یا صرفه‌جویی عمومی Flux نیست. در سه نمونهٔ مدل، مقایسهٔ بستهٔ جدید ۳۰۰۰ با قبلی ۶۰۰۰ مصرف کل کمتر نشان داد؛ تعداد نمونه و تفاوت بودجه اجازهٔ تعمیم یک درصد ثابت نمی‌دهند.

## ۱۳. معیار پذیرش پیاده‌سازی آینده

این‌ها سناریوهای لازم برای زمان پیاده‌سازی‌اند؛ نوشتن جدول به معنای اجرای آن‌ها در محصول نیست.

| ID | ورودی/شرط | نتیجهٔ لازم |
|---|---|---|
| TM-01 | دو worker، remaining مشترک ۵۰هزار microUSD، دو رزرو ۳۰هزار | فقط یکی admit؛ همهٔ bindings سازگار |
| TM-02 | root جا دارد، department ندارد | بدون تماس شبکه، `BLOCKED_BUDGET` با علت department |
| TM-03 | timeout پس از dispatch، usage ناموجود | actual=null؛ hold محفوظ؛ remaining افزایش نمی‌یابد |
| TM-04 | retry پس از TM-03 | reservation/request/count جدید؛ hold قبلی باقی است |
| TM-05 | settlement یکسان دوبار | هزینه و counter فقط یک بار تغییر می‌کنند |
| TM-06 | unknown بعداً reconciled می‌شود | unknown کم و known افزوده؛ همان request دوباره bill نمی‌شود |
| TM-07 | actual بالاتر از bound | ثبت actual واقعی، breach، عدم dispatch بعدی |
| TM-08 | crash میان marker و دریافت request ID | RECOVERING؛ replay اثرگذار بدون reconciliation صفر |
| TM-09 | cancel و response دیررس | state=CANCELLED؛ usage قابل تسویه؛ task احیا نمی‌شود |
| TM-10 | evidence در مرز token cap با labels/warnings فارسی | شمارش render کامل <= cap؛ metadata exclusions حاضر |
| TM-11 | حذف excerpt ضروری برای جا شدن بسته | معیار missing/unverified؛ ACCEPT_CANDIDATE از این نقص عبور نمی‌کند |
| TM-12 | tokenizer local با usage provider فرق دارد | هر دو مقدار و scope حفظ؛ billing از local جایگزین نمی‌شود |
| TM-13 | cached/reasoning subset | جمع درست؛ دوباره‌شماری صفر |
| TM-14 | route subscription، هزینهٔ cumulative/session | در settled API جمع نمی‌شود؛ scope/session صریح |
| TM-15 | quota None، NaN یا stale | به صفر/۱۰۰٪ تبدیل نمی‌شود؛ policy مربوط unknown اعمال می‌شود |
| TM-16 | یک window صفر و window دیگر مثبت | در صورت required بودن هر دو، exhausted route admit نمی‌شود |
| TM-17 | user خارج Flux همان account را مصرف می‌کند | تغییر quota منبع Flux cost/token فرض نمی‌شود |
| TM-18 | production تمام remaining را می‌خواهد | review envelope محفوظ؛ admission تولید رد |
| TM-19 | root بازطراحی و چند child جدید | هزینه، سقف و attempt lineage حفظ می‌شوند |
| TM-20 | ۴۰۰ پارامتر ناسازگار باعث resend می‌شود | هر ارسال در دفتر و cap تماس نمایان؛ retry adapter پنهان صفر |
| TM-21 | افزایش cap بدون authority یا با revision قدیمی | رد قطعی؛ بودجه بدون تغییر |
| TM-22 | دو فرایند DB با race روی reserve | همان نتیجهٔ TM-01؛ قفل صرفاً process-local کافی نیست |
| TM-23 | تغییر روز/دوره و settlement دیررس | binding اولیه ثابت؛ هزینه از دورهٔ قبلی ناپدید نمی‌شود |
| TM-24 | تعرفه/usage scope نامعلوم در mode سقف سخت | route unavailable، بدون هزینهٔ حدسی صفر |

تست‌های موجود فقط بخشی از وضعیت legacy/local را بررسی می‌کنند: `test_budget_ledger.py` برای stop و hold unknown، `test_retry_limits.py` برای bounded transport، `test_concurrency.py` برای limiter دو slot و `test_local_quota.py` برای normalization/cache. قبولی این تست‌ها اثبات پیاده‌سازی TM-01 تا TM-24 نیست.

## ۱۴. نقشهٔ منابع و تصمیم‌های باز

| مرجع | تابع/بخش مورد استفاده | منشأ ادعا |
|---|---|---|
| [`ledger.py`](../../src/flux/budget/ledger.py) | `BudgetLedger.reserve_for_call`, `settle_call` | رزرو، نرخ snapshot و تسویهٔ legacy |
| [`estimator.py`](../../src/flux/budget/estimator.py) | `estimate_tokens_from_text`, `estimate_call_cost` | شمارندهٔ نویسه‌ای فعلی |
| [`pricing.py`](../../src/flux/budget/pricing.py) | `MODEL_PRICES`, `get_model_price` | نرخ‌های static و fallback؛ بدون ادعای تعرفهٔ زنده |
| [`repository.py`](../../src/flux/storage/repository.py) | `reserve_budget`, `settle_reservation`, `record_usage`, `get_usage_summary` | run/day cap، hold و محدودیت reconciliation |
| [`orchestrator.py`](../../src/flux/engine/orchestrator.py) | `_call`, `_context`, `execute_run`, `resume_run` | call caps، context، deadline و رفتار resume |
| [`gapgpt.py`](../../src/flux/providers/gapgpt.py) | `GapGPTAdapter.generate`, `_get_client` | provider usage، SDK retry خاموش و resend ۴۰۰ |
| [`runtime.py`](../../src/flux/local_agents/runtime.py) | `cli_environment`, `EventParser.feed`, `LocalRuntime.submit/execute/recover` | route اشتراکی، usage و cycle نوبت CLI |
| [`quota.py`](../../src/flux/local_agents/quota.py) | `window`, `codex_windows`, `claude_windows`, `read_notebooklm`, `QuotaMonitor.read` | semantics بازه/نامعلوم/stale |
| [`profiles.py`](../../src/flux/engine/profiles.py) | `PROFILES` | سقف‌های output فعلی، نه بودجهٔ سازمانی |
| [`local-agents.fa.md`](../local-agents.fa.md) و [`flux-identity-and-quota.fa.md`](../flux-identity-and-quota.fa.md) | مصرف و حدود نسخهٔ ۰٫۴ | مرز subscription و legacy |
| [`REPORT.fa.md`](../../experiments/jev_v2_rewrite_20261001/REPORT.fa.md) | روش، سقف و نتایج JEV مستقل | محدودیت local tokenizer و evidence-only claims |
| وایت‌پیپر Flux، صفحات ۸–۱۰ و ۱۲–۱۳ | چرخه، سه تلاش، حافظه، رزرو و اقتصاد | الزام مقصد محصول |

پیش از پیاده‌سازی مقصد باید تعیین شوند: مالک budget global/company، دورهٔ مالی و timezone، quota-unknown policy هر route، ارائه‌دهندگان دارای bounds معتبر، تعرفهٔ versioned، روش reconciliation، تقسیم هزینهٔ بین بخش‌ها و کف budget لازم برای review. تعیین این موارد با سیاست مشتری است؛ Head فقط پیشنهاد مستند می‌دهد.
