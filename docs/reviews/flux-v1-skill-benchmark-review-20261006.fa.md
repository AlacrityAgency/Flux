# بازبینی مستقل گزارش «مقایسهٔ واقعی FLux v1 با Codex معمول»

تاریخ بازبینی: ۲۰۲۶-۱۰-۰۶ · بازبین: نشست DSH روی `D:\project\Alacrity\Flux` · وضعیت: **تأییدشده با محدودیت‌های تفسیری**

---

## ۰. خلاصهٔ یک‌پاراگرافی

متنی که فرستادی، یک **گزارش بنچمارک فارسی** است که به‌صورت ماشینی در یک نشست «skill-creator» ابزار Codex ساخته شده و ادعا می‌کند گردش‌کار اسکیل نصب‌شدهٔ `flux-v1` با تنظیم فعلی دستگاه (`gpt-6.1-sol / medium` + shell) دقت برابر (۱۲/۱۲) و ۵۶٫۶۷٪ توکن کمتر دارد، اما در اجرای سرد سریع‌تر نیست (۱٫۶۸٪- کندتر). **همهٔ اعداد، هش‌ها و ادعاهای روش‌شناختی گزارش را از رسیدهای خام بازتولید کردم و درست از آب درآمدند**؛ اما سه نکته که در گزارش نیامده، تصویر را تغییر می‌دهد: (۱) تنها ارتقای اجرا ناشی از باگ checker خودِ مدل بود نه پاسخ غلط، (۲) بخش عمدهٔ «صرفه‌جویی» از خاموش‌کردن اسکافولد ابزار می‌آید نه از مسیریابی/Laya، و در مقایسه با همان مدل بدون ابزار، FLux **۱۷٫۷٪ بیشتر** مصرف کرده، (۳) Laya در نتیجهٔ این آزمون عملاً بی‌اثر بود. این متن یک گزارش آزمون است، نه یک ادعای اثبات‌شدهٔ «ارزان‌تر بودن»؛ خودِ گزارش هم تقریباً همین را می‌گوید، ولی تیتر و جدول اصلی آن را پررنگ‌تر از شواهد نشان می‌دهند.

---

## ۱. این متن دقیقاً چیست و از کجا آمده

| پرسش | پاسخ مستند |
|---|---|
| چه چیزی است؟ | گزارش مقایسهٔ چهار حالت اجرا روی ۱۲ تسک مصنوعی، با ارزیاب مستقل |
| چه کسی/چه چیزی ساخته؟ | اسکریپت [make_report.py](<C:/Users/xio/Documents/Codex/2026-10-06/skill-creator-c-users-xio-agents/work/flux-v1-benchmark/make_report.py>) (خطوط ۷۵–۹۸ متن گزارش را مونتاژ می‌کند) در نشست Codex با اسکیل `.system/skill-creator` |
| فایل خروجی | [FLux-v1-benchmark-2026-10-06.fa.md](<C:/Users/xio/Documents/Codex/2026-10-06/skill-creator-c-users-xio-agents/outputs/FLux-v1-benchmark-2026-10-06.fa.md>) + [.json](<C:/Users/xio/Documents/Codex/2026-10-06/skill-creator-c-users-xio-agents/outputs/FLux-v1-benchmark-2026-10-06.json>) + [.zip](<C:/Users/xio/Documents/Codex/2026-10-06/skill-creator-c-users-xio-agents/outputs/FLux-v1-benchmark-2026-10-06.zip>) (۱۹۲ ورودی، بدون credential) |
| هارنس آزمون | [benchmark.py](<C:/Users/xio/Documents/Codex/2026-10-06/skill-creator-c-users-xio-agents/work/flux-v1-benchmark/benchmark.py>) (خطوط ۲۳–۳۲ قرارداد و طرح)، [tools_baseline.py](<C:/Users/xio/Documents/Codex/2026-10-06/skill-creator-c-users-xio-agents/work/flux-v1-benchmark/tools_baseline.py>) (پیوست حالت ابزار) |
| اسکیل آزمون‌شده | [SKILL.md](<C:/Users/xio/.codex/skills/flux-v1/SKILL.md>) در `C:/Users/xio/.codex/skills/flux-v1` — کپی تغییرنام‌یافتهٔ اسکیل `senior-v2` (نام، description و تیتر عوض شده) |
| «FLux v1» یعنی چه؟ | یک **اسکیل Codex/گردش‌کار helper-محور**، نه سرویس یا مسیریاب داخل مخزن Flux. خود اسکیل این را می‌گوید: «این فایل دستور اجرای عامل است، نه سرویس پس‌زمینه یا مسیریاب خودکار نصب‌شده در Flux» ([SKILL.md](<C:/Users/xio/.codex/skills/flux-v1/SKILL.md>) خط ۸) |
| وابستگی به مخزن Flux | checkpoint و مفسر Laya از خود مخزن می‌آید: `experiments/flux_laya_policy_20261006/checkpoint` و `.venv` ([benchmark.py](<C:/Users/xio/Documents/Codex/2026-10-06/skill-creator-c-users-xio-agents/work/flux-v1-benchmark/benchmark.py>) خطوط ۱۶–۲۱) |
| پیشینهٔ نزدیک در مخزن | [senior_v2_gapcode_20261006](experiments/senior_v2_gapcode_20261006) (کاتالوگ/سازگاری مدل‌های GapCode و تست helperها) و [flux_laya_v2_repeat_20261006](experiments/flux_laya_v2_repeat_20261006) (آزمایش ۱۲تسکی v1→v2 با Laya). این گزارش، آزمون مستقل و تازه‌ای روی همان گردش‌کار است |

**مسیر اجرا در حالت «FLux v1»** (از `plan.json`): فرصت ۱ = `codex/gpt-6-luna low` → فرصت ۲ = `gapcode/gpt-6.1-sol high` → فرصت ۳ = `gapcode/gpt-6-astra high`؛ بررسی محلی با worker محدود + تصمیم Laya در ابتدا/پایان + گارد قطعی.

---

## ۲. چک‌های مستقلی که انجام دادم (همه سبز)

اسکریپت‌های بازبینی که نوشتم: [verify_flux_v1_benchmark.py](tmp/verify_flux_v1_benchmark.py) · [verify_flux_v1_benchmark2.py](tmp/verify_flux_v1_benchmark2.py) · [verify_flux_v1_benchmark3.py](tmp/verify_flux_v1_benchmark3.py) · [verify_flux_v1_benchmark4.py](tmp/verify_flux_v1_benchmark4.py) · [verify_flux_v1_benchmark5.py](tmp/verify_flux_v1_benchmark5.py)

| # | ادعای گزارش | نتیجهٔ بازبینی |
|---|---|---|
| ۱ | SHA256 سؤال‌ها `5318c385…` | ✅ برابر `tasks.json` |
| ۲ | SHA256 «برنامهٔ منجمد» `93341933…` | ✅ برابر `plan.json`؛ هش خودِ کد اجرا `7930b56f…` است که درون `plan.json` ثبت شده و با فایل فعلی `benchmark.py` می‌خواند (بدون drift) |
| ۳ | جدول توکن: ۲۹۵٬۸۱۲ / ۱۰۸٬۸۹۷ / ۱۰۱٬۶۰۴ / ۱۲۸٬۱۷۳ | ✅ بازتجمیع ۴۹ رسید، رقم‌به‌رقم یکسان |
| ۴ | کش ورودی: ۱۳۴٬۶۵۶ / ۲۷٬۷۷۶ / ۶۳٬۲۳۲ / ۷۱٬۴۲۴ | ✅ یکسان |
| ۵ | زمان متوسط ۱۷٫۷۲ / ۳۳٫۱۶ / ۵٫۱۱ / ۱۷٫۱۷ ثانیه | ✅ = مجموع ثانیهٔ trials ÷ ۱۲ (۲۱۲٫۶۸۸ / ۳۹۷٫۸۸۷ / ۶۱٫۳۲۷ / ۲۰۶٫۰۵۹) |
| ۶ | کاهش توکن ۵۶٫۶۷٪، کاهش زمان ۳٫۱۲٪، سرد ۱٫۶۸٪- | ✅ بازمحاسبه: ۵۶٫۶۷۰۸٪ / ۳٫۱۱۶۶٪ / ۱٫۶۷۸٪- |
| ۷ | بازهٔ بوت‌استرپ جفتی ۳۹٫۸۶ تا ۶۵٫۸۱٪ | ✅ با همان seed (۶۱۰۶۲۰۲۶) عیناً؛ با seed دیگر ۴۰٫۱۳–۶۵٫۸۰ ⇒ نتیجه حساس به seed نیست |
| ۸ | Laya: ۲۵ تصمیم، ۵٫۳۵s، ۲۲٬۹۹۵ توکن encoder، بارگذاری ۱۰٫۲۰s، peak ۱٫۴۸۵ GiB | ✅ برابر `runtime.json` و خلاصهٔ `results.json` |
| ۹ | دقت گروهی (فاکتور/شمارش/زمان‌بندی) | ✅ برابر `by_family` |
| ۱۰ | «shell در دسترس بود؛ رویداد ابزار مشاهده‌شده ۰» | ✅ هیچ‌یک از ۴۹ رسید `tool_events>0` ندارد (شامل خود حالت ابزار) |
| ۱۱ | «حالت ابزار بعد از چهار فاکتور اولیه اضافه شد» | ✅ `tools-baseline-plan.json` در ۱۴:۲۹:۴۰Z منجمد شد و آخرین تسک فاکتور اصلی ~۱۴:۲۷Z تمام شده بود |
| ۱۲ | «هیچ پاسخ مرجعی وارد prompt نشد» | ✅ promptها فقط `TASK` + `FACTS` دارند؛ oracle فقط داخل `check()` اجرا می‌شود |
| ۱۳ | ZIP بدون credential | ✅ ۱۹۲ ورودی، هیچ فایل auth/cookie/.env |
| ۱۴ | اسکیل پس از freeze تغییر نکرده | ✅ هش ۱۰ فایل اسکیل با `plan.json` می‌خواند (`source_hashes`) |

**نتیجه:** گزارش از نظر «حسابداری» سالم است. هیچ عددی جعل یا گرد نشده و اعتراف‌های سخت‌گیرانه (usage نامعلوم، `actual_billing_usd=null`، `server_model_identity_independently_verified=false`) در رسیدها هست.

---

## ۳. چیزهایی که گزارش نمی‌گوید ولی شواهد نشان می‌دهد

### ۳٫۱ ارتقای واحد، نتیجهٔ باگ checker خودِ مدل بود، نه پاسخ غلط
در تسک I1، تلاش اول (Luna low) با `worker.pass=false` رد شد و گارد آن را به ارتقا تبدیل کرد. علت واقعی از رسید و تریال:

- `solve()` مقدار **درست** را برگردانده: `subtotal=43738, tax=3171, total=47239` (به شکل `Fraction`).
- اما `check()` خودِ مدل، در شاخهٔ `Fraction` تقسیم بر ۱۰۰ را جا انداخته و مقدار بزرگ‌تری حساب کرده بود؛ پس `verified=False` شد.
- `validate_program.validate()` با `verified is not True` استثنا می‌دهد ([validate_program.py](<C:/Users/xio/.codex/skills/flux-v1/scripts/validate_program.py>) خط ۳۶) → گارد، ارتقا را اجباری کرد.
- پاسخ ارتقا (Sol high) **همان سه عدد** بود و پذیرفته شد.

یعنی گارد درست و fail-safe عمل کرد (پذیرش غلط رخ نداد)، ولی این ارتقا «لازم» نبود: هزینه‌اش ۸٬۲۰۴ توکن ورودی + ۸۹۸ خروجی روی کیف پول GapCode بود. اگر این باگ نبود، FLux با ۱۲ فراخوانی و ~۱۱۹k توکن تمام می‌شد (۱۲۰٬۶۸۵ − ۸٬۲۰۴ ورودی و ۷٬۴۸۸ − ۸۹۸ خروجی). نکتهٔ قابل‌اقدام: قرارداد prompt صریحاً `fractions` را مجاز می‌کند، اما ترکیب «checker مدل + رمزگذاری دقیق worker» در همین یک مورد شکننده بود؛ این نقطه باید هدف بهینه‌سازی بعدی باشد (یا نرمال‌سازی خروجی به int، یا اجباری‌کردن همان `_half_up` در هر دو تابع).

### ۳٫۲ بخش عمدهٔ ۵۶٫۶۷٪ «صرفه‌جویی» از خاموش‌کردن اسکافولد است، نه از مسیریابی
کانتکست واقعی هر فراخوانی (از usage رسیدها):

| حالت | مدل | ورودی/فراخوانی | کش/فراخوانی |
|---|---|---:|---:|
| Codex با ابزار | sol medium | **۲۴٬۲۶۹** | ۱۱٬۲۲۱ |
| Sol مستقیم (بدون ابزار) | sol medium | ۸٬۴۳۸ | ۲٬۳۱۵ |
| Luna مستقیم | luna low | ۸٬۴۳۸ | ۵٬۲۶۹ |
| FLux (فرصت اول) | luna low | ۹٬۳۷۳ | ۵٬۳۷۶ |
| FLux (ارتقا) | sol high | ۸٬۲۰۴ | ۶٬۹۱۲ |

- اختلاف ۸٬۴۳۸ در برابر ۲۴٬۲۶۹ ≈ **۱۵٫۸k توکن در هر فراخوانی** فقط برای «در دسترس بودن» shell است؛ در ۱۲ فراخوانی ≈ ۱۹۰k از ۲۹۵٬۸k حالت ابزار. چون `tool_events=0` بود، این هزینه صرفاً سربار اسکافولد است. پس سوگیری مقایسهٔ اصلی **به نفع FLux** است.
- در مقایسه با حالت **بدون ابزار** و همان مدل، اعداد معلوم چنین است: Sol مستقیم ۱۰۸٬۸۹۷ توکن (۱۱/۱۲ درست + ۱ شکست provider) و FLux ۱۲۸٬۱۷۳ توکن (۱۲/۱۲). یعنی FLux **~۱۷٫۷٪ بیشتر** مصرف کرد، هرچند زمان را تقریباً نصف کرد (۲۰۶ در برابر ۳۹۸ ثانیه).
- گزارش این را صریح نمی‌گوید؛ فقط می‌گوید «مصرف ناقص است؛ درصد صرفه‌جویی قابل محاسبه نیست». این جمله از نظر فنی درست است (یک فراخوانی Sol بدون usage است و مجموع یک حد پایین است)، اما نتیجهٔ ضمنی‌اش برای خواننده این است که مقایسه «نامعلوم» است، در حالی که **مصرف معلوم FLux از مصرف معلوم آن baseline بیشتر است**.

### ۳٫۳ Laya در نتیجهٔ اندازه‌گیری‌شده عملاً بی‌اثر بود
- **FRONT فقط عمق بررسی را انتخاب می‌کند** ([SKILL.md](<C:/Users/xio/.codex/skills/flux-v1/SKILL.md>) خط ۴۷) و در هارنس، `level = 'full'` برای همهٔ تسک‌ها ثابت است چون `risk_floor` همه «high» است ([benchmark.py](<C:/Users/xio/Documents/Codex/2026-10-06/skill-creator-c-users-xio-agents/work/flux-v1-benchmark/benchmark.py>) خط ۱۷۸). `front_choice` فقط ثبت می‌شود.
- **END** در ۱۲ موردِ پاس با تصمیم گارد یکی بود؛ ارتقای واحد را گارد اجباری کرد، نه Laya.
- پس این آزمون «گردش‌کار با حضور Laya» را می‌سنجد، نه ارزش Laya. هزینهٔ آن ثبت شده است (۲۵ تصمیم، ۵٫۳۵s، ۲۲٬۹۹۵ توکن encoder محلی، ~۱٫۴۸۵ GiB VRAM) و گزارش هم می‌گوید اثر مستقل Laya اثبات نمی‌شود — اما نمی‌گوید که فاز FRONT در این مجموعهٔ تسک **قراردادی** بی‌اثر است.

### ۳٫۴ «Codex معمول با ابزار» یک Codex پیش‌فرض کامل نیست
طبق رسیدها، حالت ابزار هم مثل بقیه با `--ignore-user-config --ephemeral --sandbox read-only` و `features.apps/memories/multi_agent/skill_search=false`, `web_search="disabled"`, `project_doc_max_bytes=0`, `personality="none"` اجرا شده و فقط دو تفاوت دارد: `features.shell_tool=true` و یک فایل instructions متفاوت که محاسبهٔ shell را مجاز می‌کند. نام «Codex معمول» کمی سخاوتمندانه است؛ دقیق‌تر: «همان هارنس برهنه با ابزار محاسبهٔ فعال و بدون استفاده از آن».

### ۳٫۵ عدم‌تقارن شکست provider در دقت
دو حالت مستقیم هرکدام **یک** `provider_failure` دارند (Luna در C1، Sol در C4) و چون آن فراخوانی ناتمام بوده، در دقت «غلط» شمرده شده است. حالت ابزار و FLux صفر شکست دارند. بنابراین بخشی از فاصلهٔ «۱۲/۱۲ در برابر ۱۱/۱۲» تصادف زیرساخت است، نه تفاوت کیفیت مدل.

### ۳٫۶ دامنهٔ عدد «۱٫۶۸٪ کندتر»
۱۰٫۲ ثانیه بارگذاری Laya روی یک دستهٔ ۱۲تایی سرشکن شده است. برای **یک درخواست تک**، همان هزینه معادل ۲۷٫۴ ثانیه در برابر ۱۷٫۷ ثانیه می‌شود (≈ ۵۵٪ کندتر). عدد ۱٫۶۸٪- فقط برای اجرای دسته‌ای معنا دارد و گزارش این را در یک جمله گفته، ولی اهمیتش برای استفادهٔ واقعی («تک درخواست») بیشتر از ظاهر آن است.

### ۳٫۷ ترکیب دو حساب/دو کیف پول در یک ستون «توکن»
فرصت اول از حساب Codex (ChatGPT) و ارتقا از کیف پول GapCode می‌آید. «درصد توکن» بین دو صورت‌حساب متفاوت جمع شده است. گزارش خودش هشدار می‌دهد که درصد توکن ≠ درصد هزینه/سهمیه؛ این هشدار درست و لازم است و باید در نقل‌قول‌ها حفظ شود.

### ۳٫۸ جزئیات بازتولید
- واژهٔ «SHA256 برنامهٔ منجمد» در انتهای گزارش، در واقع هش `plan.json` است؛ هش کد اجرا (`benchmark.py`) `7930b56f…` است. برای بازتولید دقیق، هر دو را باید ذکر کرد.
- تسک‌ها با seed ثابت `106202641` و از همان سه خانوادهٔ آزمایش‌های قبلی ساخته شده‌اند (۱۲ تسک، ۱ تکرار). بازهٔ اطمینان بوت‌استرپ فقط عدم‌قطعیت همین نمونه را می‌سنجد.
- ارزیاب مستقل، مقایسهٔ دقیق JSON با oracle محاسبه‌شده با `Decimal`/`itertools.permutations` است؛ قوی و بدون نشت به prompt.

---

## ۴. جمع‌بندی: چه چیزی از این گزارش قابل ادعاست

**قابل ادعا (پشتیبانی‌شده):**
1. روی این ۱۲ تسک، گردش‌کار FLux v1 به دقت ۱۲/۱۲ رسید؛ برابر با تنظیم فعلی دستگاه (Sol/medium + shell) و بالاتر از Sol مستقیم بدون ابزار (۱۱/۱۲).
2. نسبت به همان تنظیم فعلی با ابزار فعال، ۵۶٫۶۷٪ توکن کمتر مصرف شد (بازهٔ ۹۵٪: ۳۹٫۹–۶۵٫۸٪) و صفر پذیرش غلط ثبت شد.
3. در اجرای سرد، FLux سریع‌تر نبود؛ و هزینهٔ راه‌اندازی Laya در استفادهٔ تک‌درخواستی چشمگیر است.
4. هیچ عدد یا هشی در گزارش دست‌کاری نشده؛ بستهٔ شواهد کامل و قابل بازتولید است.

**قابل ادعا نیست (و برخی نقل‌قول‌ها آن را القا می‌کنند):**
5. «FLux v1 ارزان‌تر/کم‌مصرف‌تر است» به‌طور کلی. در برابر همان مدل بدون ابزار، مصرف بیشتر بود؛ صرفه‌جویی اصلی به پیکربندی سبک (ابزار خاموش + instructions کوتاه) وابسته است و سهم مستقل هر جزء اندازه‌گیری نشده است.
6. «ارزش Laya» یا «اثر خلاصه‌سازی prompt» — هیچ‌کدام در این طرح تفکیک نشده‌اند.
7. تعمیم به کار واقعی (مخزن، RAG، نوشتار، کدنویسی عمومی) — ۱۲ تسک مصنوعی، ۱ تکرار.

**پیشنهاد برای اجرای بعدی (به‌ترتیب اثر):**
1. یک بازوی ابلشن با **اسکافولد برابر**: همان `instructions.txt` و همان کانفیگ، فقط تفاوت مسیریابی/بررسی/ارتقا ⇒ سهم واقعی گردش‌کار جدا می‌شود.
2. یک بازو با ابزار فعال **و استفادهٔ واقعی** از آن (تسک‌هایی که بدون محاسبه قابل حل نیستند) تا اثر ابزار سنجیده شود، نه سربار آن.
3. رفع ناسازگاری checker/Fraction (یا نرمال‌سازی خروجی worker به عدد صحیح) و تکرار؛ انتظار: حذف ارتقای بی‌مورد و مصرف کمتر.
4. تفکیک سهم Laya با یک بازو بدون FRONT/END (گارد قطعی تنها).
5. گزارش مبلغ/سهمیه به‌جای توکن، و حداقل ۳ تکرار با خانواده‌های متنوع‌تر و holdout جدا.

---

## ۵. فهرست شواهد (برای ادامهٔ کار)

**داخل مخزن Flux**
- [experiments/senior_v2_gapcode_20261006](experiments/senior_v2_gapcode_20261006) — کاتالوگ GapCode، سازگاری مدل‌ها، رسید helperها (منبع `model-tests.fa.md`)
- [experiments/flux_laya_policy_20261006](experiments/flux_laya_policy_20261006) — checkpoint و `.venv` استفاده‌شده؛ گزارش ۶تسکی Senior/GOAT
- [experiments/flux_laya_v2_repeat_20261006](experiments/flux_laya_v2_repeat_20261006) — آزمایش ۱۲تسکی v1→v2 با Laya (پیشینهٔ نزدیک)
- اسکریپت‌های بازبینی این گزارش: [tmp/verify_flux_v1_benchmark.py](tmp/verify_flux_v1_benchmark.py) و چهار نسخهٔ بعدی در همان پوشه

**بیرون از مخزن (نشست Codex)**
- گزارش: [FLux-v1-benchmark-2026-10-06.fa.md](<C:/Users/xio/Documents/Codex/2026-10-06/skill-creator-c-users-xio-agents/outputs/FLux-v1-benchmark-2026-10-06.fa.md>)
- داده و کد آزمون: [results.json](<C:/Users/xio/Documents/Codex/2026-10-06/skill-creator-c-users-xio-agents/work/flux-v1-benchmark/results.json>) · [plan.json](<C:/Users/xio/Documents/Codex/2026-10-06/skill-creator-c-users-xio-agents/work/flux-v1-benchmark/plan.json>) · [tasks.json](<C:/Users/xio/Documents/Codex/2026-10-06/skill-creator-c-users-xio-agents/work/flux-v1-benchmark/tasks.json>) · [benchmark.py](<C:/Users/xio/Documents/Codex/2026-10-06/skill-creator-c-users-xio-agents/work/flux-v1-benchmark/benchmark.py>) · [tools_baseline.py](<C:/Users/xio/Documents/Codex/2026-10-06/skill-creator-c-users-xio-agents/work/flux-v1-benchmark/tools_baseline.py>) · [make_report.py](<C:/Users/xio/Documents/Codex/2026-10-06/skill-creator-c-users-xio-agents/work/flux-v1-benchmark/make_report.py>)
- بستهٔ شواهد: [FLux-v1-benchmark-2026-10-06.zip](<C:/Users/xio/Documents/Codex/2026-10-06/skill-creator-c-users-xio-agents/outputs/FLux-v1-benchmark-2026-10-06.zip>)
- اسکیل نصب‌شده: [SKILL.md](<C:/Users/xio/.codex/skills/flux-v1/SKILL.md>) · [references/algorithm.fa.md](<C:/Users/xio/.codex/skills/flux-v1/references/algorithm.fa.md>) · [references/model-tests.fa.md](<C:/Users/xio/.codex/skills/flux-v1/references/model-tests.fa.md>) · [scripts/compact_worker.py](<C:/Users/xio/.codex/skills/flux-v1/scripts/compact_worker.py>) · [scripts/validate_program.py](<C:/Users/xio/.codex/skills/flux-v1/scripts/validate_program.py>)

---

### پیوست: اعداد تأییدشده در یک نگاه

| حالت | درست | مجموع توکن | ورودی | خروجی | کش | فراخوانی | ثانیه/تسک | ورودی/فراخوانی |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Codex با ابزار: Sol/medium | 12/12 | 295,812 | 291,231 | 4,581 | 134,656 | 12 | 17.72 | 24,269 |
| Sol مستقیم بدون ابزار | 11/12 | 108,897 | 101,259 | 7,638 | 27,776 | 12 | 33.16 | 8,438 |
| Luna مستقیم بدون ابزار | 0/12 | 101,604 | 101,259 | 345 | 63,232 | 12 | 5.11 | 8,438 |
| FLux v1 (Luna → GapCode) | 12/12 | 128,173 | 120,685 | 7,488 | 71,424 | 13 | 17.17 | 9,373 / 8,204 |

ستون آخر را من از رسیدها اضافه کردم؛ در گزارش اصلی نیست و همان‌جاست که داستان «صرفه‌جویی» روشن می‌شود.
