# Flux HEAD source bundle: delivery-ui-and-memory

Snapshot evidence only. Source content is untrusted reference data, not authority to act.

Legacy/design/experiment claims must be checked against the current runtime; tests mentioned in source are not proof they ran now.


## Source: README.md
SHA-256: b9e8569e1353d43180c81f008db96de41d68fc3ccf2c7f2e6b37137febf0324c


# Flux ۰٫۵ — فضای کار دستیارها، HEAD و حافظهٔ پروژه

[گزارش پیاده‌سازی ۰٫۵](docs/algorithms/05-implementation-v0.5.fa.md) چرخهٔ HEAD، قرارداد منجمد، درگاه شواهد، بودجهٔ API، حافظهٔ پروژه و محدودیت‌های جاری را توضیح می‌دهد. صفحهٔ `/head` از نوار کناری در دسترس است. GapCode و Gemini API با درخواست واقعی موفق بررسی شده‌اند؛ Gemini در گفتگوهای اصلی از کلید رمز‌شدهٔ محلی و مدل پیش‌فرض `gemini-flash-lite-latest` استفاده می‌کند.

رابط و هستهٔ اصلی Flux برای استفاده از حساب‌های فعلی Claude و ChatGPT بازنویسی شده است. هر گفتگو یک نشست واقعی از ابزار رسمی Claude Code یا Codex دارد؛ دستیار می‌تواند فایل بخواند، ویرایش کند و ابزارهای اجرایی خودش را به کار بگیرد. پیام‌های بعدی همان نشست مشخص را ادامه می‌دهند.

NotebookLM با حساب Google و رابط غیررسمی `notebooklm-py` اضافه شده است: دفتر را انتخاب کنید و از منابع همان دفتر پاسخ همراه با ارجاع بگیرید. Antigravity با CLI رسمی اضافه شده، اما حساب فعلی در ۱ اکتبر ۲۰۲۶ با خطای محدودیت منطقهٔ Google قابل استفاده نیست؛ در شمار حساب‌های متصل قرار نمی‌گیرد. [راهنمای اتصال و شواهد آزمایش](docs/google-integrations.fa.md).

رابط اصلی اکنون چیدمانی شبیه Claude دارد و از رنگ‌ها و فونت‌های Alacrity و نشان مستقل Flux استفاده می‌کند: مشکی `#0A0A0A` و سفید `#F2F2EE`. انتخاب مدل و دسترسی از پنل تنظیمات کنار ورودی انجام می‌شود. نوار کناری در راست قابلیت جمع شدن و جستجوی گفتگوها دارد. سهمیهٔ باقی‌مانده و زمان بازنشانی در کارت حساب‌ها دیده می‌شود. [جزئیات رابط و سهمیه](docs/flux-identity-and-quota.fa.md).

## اجرا

نسخهٔ آمادهٔ Windows: `dist/local-agents/Flux.exe`. پس از نصب با `Install-Flux.bat`، میانبر Flux روی دسکتاپ و منوی Start همین نسخه را باز می‌کند.

از سورس:

```powershell
python -m pip install -e ".[dev]"
python run_flux.py
```

برای مرورگر معمولی:

```powershell
python run_flux.py serve --host 127.0.0.1 --port 8040 --no-browser
```

## استفاده

1. در «اتصال حساب‌ها» آماده بودن Claude Code و Codex را ببین.
2. پوشهٔ پروژه، دستیار و مدل را انتخاب کن. مدل خالی از تنظیم پیش‌فرض همان CLI استفاده می‌کند.
3. دسترسی «خواندن، ویرایش و اجرا» برای انجام واقعی کار است. «فقط خواندن» برای بررسی فایل‌هاست.
4. پیام را بفرست؛ پاسخ، فرمان‌ها و تغییر فایل‌ها در گفتگو و «فعالیت ابزارها» دیده می‌شوند.
5. پیام بعدی همان نشست را ادامه می‌دهد. پس از پایان اجرا، تغییر دستیار خودکار گفتگوی تازه می‌سازد و پیش‌نویس و تاریخچه را حفظ می‌کند. برای تغییر مدل یا پوشه، گفتگوی تازه بساز.

دکمهٔ ارسال هنگام اجرا به «توقف اجرا» تبدیل می‌شود. Enter ارسال و Shift+Enter خط جدید است؛ Ctrl+K گفتگوی تازه می‌سازد. پاسخ را می‌توان کپی یا به Markdown صادر کرد. حافظهٔ منتخب از یادداشت‌های محلی قبلی بازیابی می‌شود.

«پروژه‌ها و حافظه» پنل مدیریت را داخل همین رابط باز می‌کند. گفتگو و حافظه به پروژه متصل‌اند؛ یادداشت قدیمی بدون تخصیص وارد RAG پروژه نمی‌شود. یادداشت سراسری فقط با انتخاب صریح شما مشترک است. پیشنهاد و یادداشت کهنه بازیابی نمی‌شوند. [گزارش جاری](docs/algorithms/05-implementation-v0.5.fa.md) و [اصلاح تاریخی رابط ۰٫۴](docs/project-memory-ui-fix.fa.md).

## مشخصات سازمانی و حافظهٔ HEAD

[دفتر HEAD و چهار الگوریتم](docs/algorithms/00-head-brief.fa.md) مشخصات اولیه‌اند. [گزارش پیاده‌سازی ۰٫۵](docs/algorithms/05-implementation-v0.5.fa.md) بخش اجراشده و باقی‌مانده را جدا می‌کند. [حافظهٔ نسخهٔ ۰٫۵](docs/knowledge/head-memory-v0.5.fa.md) و [دفتر NotebookLM](https://notebooklm.google.com/notebook/cbd54447-058f-445c-a1e3-850f15cc5eb9) برای ادامهٔ کار موجودند؛ منابع notebook snapshot هستند.

## اتصال حساب‌ها

روی سیستم فعلی Codex 0.159.2 و Claude Code 2.1.283 شناسایی شده‌اند. ورود با هر دو حساب و اجرای واقعی ابزارهای فایل در ۱ اکتبر ۲۰۲۶ بررسی شد. وضعیت فعلی از «اتصال حساب‌ها» دوباره خوانده می‌شود.

اگر CLI نصب نیست، ابتدا آن را نصب کن. برای Claude روی Windows:

```powershell
winget install --id Anthropic.ClaudeCode --exact
claude auth login
```

برای Codex از نصب رسمی CLI و `codex login` استفاده کن. [مستندات رسمی Codex](https://learn.chatgpt.com/docs/app-server) و [اجرای برنامه‌ای Claude Code](https://code.claude.com/docs/en/headless) مسیرهای اتصال را توضیح می‌دهند.

هر CLI ورود خودش را مدیریت می‌کند و Flux کلید API جدیدی دریافت یا کپی نمی‌کند. برای سهمیهٔ Claude، اعتبارنامهٔ OAuth ذخیره‌شده فقط در حافظه خوانده می‌شود و به نشانی ثابت HTTPS همان سرویس ارسال می‌شود. متغیرهای محیطی API در فرایندهای جدید حذف می‌شوند و پیش از اجرا، ورود با حساب اشتراکی بررسی می‌شود. سهمیه و مدل‌های قابل استفاده تابع حساب ارائه‌دهنده‌اند؛ فهرست مدل‌های ذخیره‌شدهٔ Codex فقط پیشنهاد است و دسترسی با پاسخ موفق تأیید می‌شود.

نصب‌های معمول و Codex همراه برنامهٔ ChatGPT خودکار پیدا می‌شوند. برای مسیر خاص، `FLUX_CODEX_PATH` یا `FLUX_CLAUDE_PATH` را به فایل اجرایی اصلی بده؛ launcherهای shell به‌عنوان فایل اجرایی پذیرفته نمی‌شوند.

## داده‌ها و سازگاری

دادهٔ سورس در `var/flux.db` و نسخهٔ Windows در `%LOCALAPPDATA%\FluxDemo\flux.db` ذخیره می‌شود. `FLUX_DB_PATH` این مسیر را عوض می‌کند. جدول‌های جدید `local_chats`، `local_turns` و `local_events` به همان دیتابیس اضافه می‌شوند. داده و گفتگوهای قبلی حفظ شده‌اند و از پیوند «تاریخچه و امکانات نسخهٔ قبلی» در `/legacy` قابل دسترسی‌اند.

نسخهٔ قبلی و موتور پنج نقش GapGPT در مسیر سازگاری نگه داشته شده‌اند؛ گفتگوهای رابط اصلی از آن موتور استفاده نمی‌کنند. [راهنمای نسخهٔ قبلی](docs/legacy-readme.fa.md) رفتار همان نسخه را شرح می‌دهد. کد پیش از تغییر در `backups/source-before-local-agents-20261001-034038.zip` نگه داشته شده است.

## بررسی

```powershell
python -m pytest -q
node --check src/flux/static/local.js
python -X utf8 tools/local_agents_smoke.py --live
```

آزمون آخر واقعاً سهمیهٔ هر دو حساب را مصرف می‌کند؛ فقط یک فایل در پوشهٔ موقت می‌سازد و ادامهٔ نشست را بررسی می‌کند. [گزارش اجرای واقعی](docs/local-agents-live-check.json) شامل چهار نوبت موفق، شواهد ابزارها و تأیید فایل است. تست‌های معمول بدون تماس مدل اجرا می‌شوند.

بررسی رابط روی سرویس جدا با `FLUX_DB_PATH=var/qa-local-agents.db` و پورت 8056:

```powershell
.\.venv-ui\Scripts\python.exe -X utf8 tools/local_ui_smoke.py
python -m PyInstaller --noconfirm --distpath dist/local-agents --workpath build/local-agents flux.spec
```

تست مرورگر، وضعیت اتصال، نمایش خروجی، فعالیت ابزارها، متن ناامن و عرض‌های 375، 768، 1024 و 1440 را بررسی می‌کند. [شرح معماری و محدودیت‌ها](docs/local-agents.fa.md).

### Flux identity and account quota

The Persian sidebar is on the right. Flux has its own generated mark and a keyboard-accessible assistant selector. The account panel displays remaining subscription percentages and reset times for Codex and Claude. See [implementation and checks](docs/flux-identity-and-quota.fa.md).

The selector now includes Codex, Claude, Antigravity and NotebookLM. NotebookLM notebook selection, citation display and exact conversation continuation were verified with two live turns on a dedicated synthetic notebook. Its reported compute usage is shown alongside the other accounts. Antigravity is implemented through the official CLI; the current account's region rejection remains visible rather than being reported as a successful connection.


## Source: docs/local-agents.fa.md
SHA-256: da816412ecee37a475c56e0985e5a937429898dad4a370773716c2784a62e7f0


# معماری اجرای محلی Flux ۰٫۴

## مسیر اجرا

رابط جدید در `local.html`، `local.js` و `local.css` به API `/api/local` متصل است. `LocalRuntime` یک CLI رسمی را با آرگومان‌های جدا و بدون shell wrapper راه‌اندازی می‌کند. ورودی UTF-8 از stdin ارسال می‌شود؛ stdout از JSONL به پاسخ و رویداد ابزار تبدیل می‌شود. stderr همزمان تخلیه می‌شود تا فرایند به‌علت پر شدن pipe متوقف نشود.

برای Codex، `exec --json` و برای ادامه `exec resume <session-id>` استفاده می‌شود. برای Claude، `-p --output-format stream-json --verbose --include-partial-messages` و `--resume <session-id>` استفاده می‌شود. شناسهٔ نشست به همان گفتگوی Flux تعلق دارد؛ هیچ‌گاه نشست آخر سیستم با `--last` یا `--continue` انتخاب نمی‌شود.

ورود را خود CLI مدیریت می‌کند. پیش از هر نوبت، `codex login status` یا `claude auth status --json` بررسی می‌شود. خروجی endpoint وضعیت فقط نصب، نسخه، مسیر و آماده بودن ورود را برمی‌گرداند؛ اطلاعات حساب و توکن در پاسخ API قرار نمی‌گیرد.

## چرخه و ذخیره‌سازی

هر پیام `request_key` یکتا دارد. تکرار همان شناسه و همان پیام، اجرای جدید نمی‌سازد؛ استفاده از آن برای پیام دیگر رد می‌شود. یک اجرای همزمان برای هستهٔ جدید مجاز است. تغییر پوشه، مدل و دستیار با گفتگوی تازه انجام می‌شود تا context و مجوز نشست عوض نشود.

وضعیت‌ها: `queued → running → completed / failed / cancelled / needs_input`. اگر برنامه ناگهانی بسته شود، اجرای فعال در راه‌اندازی بعدی `interrupted` می‌شود؛ درخواست نامعلوم خودکار تکرار نمی‌شود. کاربر می‌تواند با پیام تازه نشست ذخیره‌شده را ادامه دهد. مهلت هر نوبت ۲۰ دقیقه است.

موفقیت به خروج صفر CLI، پیام پایانی موفق ارائه‌دهنده و پاسخ غیرخالی نیاز دارد. قطع stream، پایان بدون رویداد نهایی و خطای محدودیت مصرف موفق ثبت نمی‌شوند. `completed` یعنی نوبت CLI تمام شده است؛ به معنای قبولی همهٔ تست‌های پروژه یا تأیید انسانی خروجی نیست. شواهد ابزارها جدا دیده می‌شوند.

توقف و بستن عادی برنامه، CLI متعلق به همان اجرا و فرایندهای فرزند آن را می‌بندد. سایر گفتگوهای دسکتاپ Claude و ChatGPT یا ابزارهای آن‌ها هدف توقف نیستند. تغییر فایل‌هایی که پیش از توقف انجام شده‌اند خودکار برگردانده نمی‌شوند.

## دسترسی و امکانات

در حالت خواندن، Codex با `read-only` اجرا می‌شود و Claude فقط ابزارهای Read، Glob و Grep را دریافت می‌کند. حالت کار، Codex را با `workspace-write` و Claude را با مجوز ویرایش و ابزارهای اجرایی به پوشهٔ انتخابی می‌برد. روی Windows مجوز ابزارهای Claude معادل sandbox سیستم‌عامل نیست؛ مسیر انتخابی محل کار آن است. قوانین و تنظیم‌های محلی CLIها همچنان اعمال می‌شوند؛ عملیات ردشده موفق گزارش نمی‌شود.

مدل خالی تنظیم پیش‌فرض CLI را حفظ می‌کند. انتخاب مدل صریح با `--model` ارسال می‌شود؛ fallback یا تعویض خودکار مدل نداریم. فهرست Codex از cache محلی خوانده می‌شود و قابلیت دسترسی حساب را تضمین نمی‌کند. Claude aliasهای `sonnet`، `opus` و `haiku` را پیشنهاد می‌دهد؛ شناسهٔ صریح هم قابل ورود است.

یادداشت‌های قبلی Flux با گزینهٔ حافظه، به‌عنوان context مرجع بازیابی می‌شوند. خواندن پروژه توسط خود CLI انجام می‌شود و به snapshot چندفایلی نسخهٔ قدیم محدود نیست. حافظه و context ذاتی هر CLI نیز از تنظیمات همان ابزار می‌آید.

## مصرف و حدود این نسخه

دادهٔ usage عین گزارش CLI ذخیره می‌شود. عدد هزینهٔ Claude تخمین ارائه‌دهنده و ممکن است برای کل نشست باشد؛ صورتحساب جدید Flux یا مبلغ قطعی پرداختی نیست. مصرف اشتراک توسط ارائه‌دهنده کنترل می‌شود. سقف‌های دلاری موتور قدیمی GapGPT به این مسیر اشتراکی منتقل نشده‌اند و تضمین سهمیه یا هزینه نیستند.

این نسخه متن را از رابط دریافت می‌کند و یک دستیار انتخابی را در هر گفتگو اجرا می‌کند. بارگذاری فایل/تصویر از رابط، انتخاب نموداری تیم، ارجاع خودکار میان دو ارائه‌دهنده و پاسخ تعاملی به درخواست مجوز CLI در این بازنویسی ساخته نشده‌اند. دستیار به فایل‌های پوشه از ابزارهای خودش دسترسی دارد. قابلیت‌های خاص خود برنامه‌های ChatGPT/Claude مانند voice و تمام ابزارهای وب آن برنامه‌ها الزاماً از CLI در دسترس نیستند.

در نسخهٔ ۰٫۵ گفتگوها `project_id` دارند و دامنهٔ حافظه کنترل می‌شود. یادداشت‌های قدیمی بدون تخصیص خودکار سراسری نمی‌شوند. پیشنهاد و یادداشت کهنه کنار گذاشته می‌شوند؛ تغییر epoch حافظه و تغییر استفاده از آن، نشست مربوط را تازه می‌کند. این هنوز برنامهٔ محلی تک‌مالک است و ACL سازمانی چندکاربره ندارد. [پیاده‌سازی و مرزها](algorithms/05-implementation-v0.5.fa.md). `/legacy` مسیر سازگاری موتور قدیمی است.

## نتیجهٔ بررسی ۱ اکتبر ۲۰۲۶

۵۴ تست بدون تماس مدل پاس شد. چهار نوبت زنده، برای هر ارائه‌دهنده ساخت و خواندن فایل موقت سپس ادامهٔ همان نشست، موفق بود. هر چهار نوبت رویداد واقعی ابزار داشتند. [گزارش زنده](local-agents-live-check.json). مرورگر در چهار عرض، بدون خطای JavaScript، با نمایش امن محتوای مدل بررسی شد. تصاویر در `screenshots/local-agents` هستند. این بررسی اتصال و رفتار آزموده‌شده را تأیید می‌کند؛ تضمین عمومی کیفیت خروجی مدل نیست.


## Source: docs/project-memory-ui-fix.fa.md
SHA-256: 6e1de62f6d2dc3247ab897e212388c6513e0bc9c7fe8408ad4cd03c4e8625dd3


# رفع بازگشت «پروژه‌ها و حافظه» به رابط قدیمی

تاریخ بررسی: ۱ اکتبر ۲۰۲۶. تغییر در سورس Flux ۰٫۴ انجام و بدون تماس مدل آزمایش شد.

## مشکل و علت

در رابط اصلی `src/flux/static/local.html`، گزینهٔ «پروژه‌ها و حافظه» یک لینک با `href="/legacy"` بود. بنابراین کلیک، صفحهٔ اصلی را ترک می‌کرد و رابط قبلی GapGPT را باز می‌کرد. API و دادهٔ پروژه‌ها و یادداشت‌ها از قبل وجود داشتند؛ مشکل از اتصال رابط جدید به آن قابلیت‌ها بود.

## رفتار فعلی

گزینهٔ نوار کناری یک پنل در همان صفحه باز می‌کند. URL صفحه و گفتگو باقی می‌مانند. پنل از همان فونت، رنگ و کنترل‌های رابط اصلی استفاده می‌کند و دو تب دارد:

| بخش | عملیات در رابط فعلی |
|---|---|
| پروژه‌ها | نمایش، جستجو، افزودن، ویرایش نام/پوشه/توضیح، بایگانی، نمایش بایگانی و بازگردانی |
| انتخاب پروژه | اعتبارسنجی وجود پوشه و بازکردن گفتگوی تازه در همان پوشه؛ پیش‌نویس پیام حفظ می‌شود |
| حافظه | نمایش، جستجو با یکسان‌سازی «ی/ي»، «ک/ك» و نیم‌فاصله، افزودن، ویرایش، فعال/غیرفعال کردن و حذف با پنجرهٔ تأیید |
| سازگاری | لینک مستقل با عنوان «تاریخچه و امکانات نسخهٔ قبلی» به `/legacy` |

انتخاب پروژه در اجرای فعال مجاز نیست و دکمه غیرفعال می‌شود. پس از انتظار برای اعتبارسنجی پوشه، وضعیت اجرا دوباره بررسی می‌شود تا اجرای تازه‌ای که در این فاصله آغاز شده تغییر نکند. اگر دستیار فعلی NotebookLM باشد، انتخاب یک پروژهٔ فایل‌محور گفتگوی تازهٔ Codex باز می‌کند؛ دفتر NotebookLM و گفتگوی قبلی دستکاری نمی‌شوند.

ویرایش پروژه فقط `name`، `path` و `description` را ارسال می‌کند. `default_budget`، `default_criteria` و تسک‌های نسخهٔ قبلی حفظ می‌شوند. بایگانی پروژه حذف فیزیکی نیست و قابل برگشت است. حافظه از همان جدول `memories` و همان کنترل `enabled` خوانده می‌شود؛ ویرایش شمارهٔ نسخه را افزایش می‌دهد و بازیابی بعدی متن تازه را می‌گیرد.

## حدود دامنه

این تغییر رابط مدیریت پروژه و حافظه را به نسخهٔ فعلی می‌آورد. رابطهٔ ذخیره‌شدهٔ گفتگوی محلی با پروژه همچنان پوشهٔ `cwd` است؛ مهاجرتی برای افزودن `project_id` به گفتگوهای CLI انجام نشده است. تسک‌های موتور قدیمی در `/legacy` قابل مشاهده و اجرا هستند.

حافظهٔ فعلی **بین پروژه‌های محلی مشترک است** و این نکته داخل تب حافظه نمایش داده می‌شود. ساخت حافظهٔ جدا برای هر پروژه، سیاست تأیید یادداشت، RAG منبع‌دار و اتصال آن به NotebookLM تغییرهای معماری جداگانه‌اند؛ این رفع باگ آن‌ها را پیاده‌سازی‌شده معرفی نمی‌کند.

## فایل‌ها

- `src/flux/static/local.html`: تبدیل لینک اصلی به دکمه و افزودن پنل‌ها و فرم‌های فعلی.
- `src/flux/static/project-memory.js`: اتصال به APIهای موجود `/projects`، `/memories` و `/filesystem/validate-path`؛ انتخاب پوشه و کنترل اجرای فعال.
- `src/flux/static/local.css`: نمایش پنل، کارت‌ها، فرم‌ها و رفتار عرض کم.
- `tests/test_project_memory_ui.py`: مسیر فعلی/قدیمی، حفظ تسک و بودجه، و اثر ویرایش/غیرفعال‌کردن/حذف در بازیابی حافظه.
- `tools/project_memory_ui_smoke.py`: سناریوی مرورگر با سرور fixture موقت روی loopback، بدون دیتابیس کاربر و بدون CLI مدل.

هیچ schema یا API سرور تغییر نکرد. دیتابیس‌های واقعی، اسرار و فرایندهای باز کاربر در این بررسی خوانده یا تغییر داده نشدند.

## شواهد بررسی

```powershell
python -m pytest -q tests/test_project_memory_ui.py tests/test_projects.py tests/test_local_agents.py tests/test_workspace.py
node --check src/flux/static/local.js
node --check src/flux/static/project-memory.js
.\.venv-ui\Scripts\python.exe -X utf8 tools/project_memory_ui_smoke.py
```

نتیجه: **۲۲ تست Python پاس شد** و هر دو فایل JavaScript از بررسی syntax عبور کردند. سناریوی مرورگر افزودن/ویرایش/بایگانی/بازگردانی پروژه، رد پوشهٔ ناموجود، حفظ فیلدهای قدیمی، افزودن/ویرایش/فعال‌کردن/حذف و لغو حذف حافظه، جستجوی فارسی، نمایش متن ناامن به‌صورت متن، حفظ پیش‌نویس، جلوگیری از انتخاب هنگام اجرا، رفتار انتخاب از NotebookLM و بستن فرم‌ها با Escape را بررسی کرد.

رابط در عرض‌های **۳۷۵، ۷۶۸، ۱۰۲۴ و ۱۴۴۰** بدون خروج پنل از صفحه و بدون خطای JavaScript بررسی شد. هفت درخواست تغییر داده روی fixture اجرا شد؛ تماس مدل صفر و دسترسی به دیتابیس کاربر صفر بود.

برای تولید تصویر از همان سناریوی آفلاین:

```powershell
.\.venv-ui\Scripts\python.exe -X utf8 tools/project_memory_ui_smoke.py --screenshots docs/screenshots/project-memory-ui
```

## بستهٔ Windows

این بررسی مربوط به سورس است. `flux.spec` کل پوشهٔ `src/flux/static` را بسته‌بندی می‌کند و فایل جدید JavaScript در build بعدی وارد EXE می‌شود. نسخهٔ نصب‌شده/باز فعلی با تغییر سورس خودکار عوض نمی‌شود؛ بازسازی و بررسی EXE باید به‌عنوان مرحلهٔ تحویل انجام شود.


## Source: src/flux/static/local.html
SHA-256: 6d964f72b7d74d0690687c07793da470355f7ed4b619821af8a6fe2b5dace71f


```html
<!doctype html>
<html lang="fa" dir="rtl">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="theme-color" content="#0a0a0a"><title>Flux — Alacrity</title><link rel="icon" href="/static/flux-mark.png"><link rel="stylesheet" href="/static/local.css"></head>
<body data-chat-state="welcome">
<button class="sidebar-scrim" id="sidebar-scrim" aria-label="بستن نوار گفتگوها" tabindex="-1"></button>
<aside class="sidebar" id="sidebar">
 <div class="sidebar-heading"><a class="brand" href="/" aria-label="Flux"><img src="/static/flux-mark.png" alt="" width="29" height="29"><strong>Flux</strong></a><button id="collapse-sidebar" class="icon-button" aria-label="جمع کردن نوار کناری" aria-expanded="true" title="نوار کناری"><svg class="icon" aria-hidden="true"><use href="/static/ui-icons.svg#sidebar"/></svg></button></div>
 <div class="sidebar-navigation"><button id="new-chat" class="navigation-item" title="گفت‌وگوی جدید"><svg class="icon" aria-hidden="true"><use href="/static/ui-icons.svg#compose"/></svg><span>گفت‌وگوی جدید</span><kbd>Ctrl K</kbd></button><button id="search-button" class="navigation-item" title="جستجوی گفتگوها"><svg class="icon" aria-hidden="true"><use href="/static/ui-icons.svg#search"/></svg><span>جستجو</span></button><button id="project-memory-button" class="navigation-item" title="پروژه‌ها و حافظه" aria-haspopup="dialog" aria-controls="project-memory-dialog"><svg class="icon" aria-hidden="true"><use href="/static/ui-icons.svg#folder"/></svg><span>پروژه‌ها و حافظه</span></button></div>
 <a class="navigation-item" href="/head">دفتر اجرای HEAD</a><div class="section-label">گفتگوها</div><nav id="history" aria-label="تاریخچهٔ گفتگو"></nav>
 <div class="sidebar-bottom"><button id="connections-button" class="account-button" title="اتصال حساب‌ها"><span class="account-avatar"><img src="/static/flux-mark.png" alt="" width="25" height="25"></span><span class="account-copy"><strong>حساب‌های شما</strong><small id="connection-count">اتصال حساب‌ها</small><small id="account-usage"></small></span><svg class="icon" aria-hidden="true"><use href="/static/ui-icons.svg#sliders"/></svg></button></div>
</aside>
<main>
 <header class="topbar"><div class="workspace-heading"><button id="menu-button" class="icon-button mobile" aria-label="نمایش گفتگوها" aria-expanded="false"><svg class="icon" aria-hidden="true"><use href="/static/ui-icons.svg#sidebar"/></svg></button><strong id="chat-title">Flux</strong><span id="chat-subtitle">فضای کار شما</span></div><button id="activity-toggle" class="toolbar-button" aria-expanded="false"><svg class="icon" aria-hidden="true"><use href="/static/ui-icons.svg#activity"/></svg><span>فعالیت</span></button></header>
 <div class="chat-stage">
  <section class="conversation" id="conversation" aria-label="گفتگو"><div id="welcome" class="welcome"><div class="welcome-brand"><img src="/static/flux-mark.png" alt="" width="36" height="36"><span>FLUX <span class="brand-divider">/</span> فضای شخصی شما</span></div><h1>چه کاری در ذهن داری؟</h1></div><div id="messages" aria-live="off"></div></section>
  <div class="composer-wrap"><div id="error" role="alert" hidden></div><form id="composer">
   <label for="prompt" class="sr-only">پیام شما</label><textarea id="prompt" rows="2" placeholder="برای شروع، هر چیزی در ذهن داری بنویس…" required></textarea>
   <div class="composer-controls"><div class="composer-tools"><button id="composer-settings" type="button" class="icon-button" title="مدل و تنظیمات اجرا" aria-label="مدل و تنظیمات اجرا"><svg class="icon" aria-hidden="true"><use href="/static/ui-icons.svg#sliders"/></svg></button><label for="provider" class="sr-only">انتخاب دستیار</label><span class="provider-control" id="provider-control"><select id="provider" hidden aria-hidden="true" tabindex="-1"><option value="codex">Codex</option><option value="claude">Claude</option><option value="gemini-api">Gemini API</option><option value="gemini">Gemini CLI</option><option value="gapcode">GapCode</option><option value="antigravity">Antigravity</option><option value="notebooklm">NotebookLM</option></select><button id="provider-toggle" type="button" aria-label="انتخاب دستیار" aria-haspopup="listbox" aria-expanded="false" aria-controls="provider-menu"><span id="provider-label">Codex</span><svg class="icon" aria-hidden="true"><use href="/static/ui-icons.svg#chevron"/></svg></button><div id="provider-menu" role="listbox" aria-label="دستیارها" hidden><button type="button" role="option" data-provider="codex" aria-selected="true"><span><strong>Codex</strong><small>حساب ChatGPT</small></span><svg class="icon provider-check" aria-hidden="true"><use href="/static/ui-icons.svg#check"/></svg></button><button type="button" role="option" data-provider="claude" aria-selected="false"><span><strong>Claude</strong><small>حساب Claude</small></span><svg class="icon provider-check" aria-hidden="true"><use href="/static/ui-icons.svg#check"/></svg></button><button type="button" role="option" data-provider="gemini-api" aria-selected="false"><span><strong>Gemini API</strong><small>کلید API خودتان</small></span></button><button type="button" role="option" data-provider="gemini" aria-selected="false"><span><strong>Gemini CLI</strong><small>حساب Google</small></span></button><button type="button" role="option" data-provider="gapcode" aria-selected="false"><span><strong>GapCode</strong><small>کیف پول GapCode</small></span></button><button type="button" role="option" data-provider="antigravity" aria-selected="false"><span><strong>Antigravity</strong><small>دستیار Google</small></span><svg class="icon provider-check" aria-hidden="true"><use href="/static/ui-icons.svg#check"/></svg></button><button type="button" role="option" data-provider="notebooklm" aria-selected="false"><span><strong>NotebookLM</strong><small>پرسش از منابع دفتر</small></span><svg class="icon provider-check" aria-hidden="true"><use href="/static/ui-icons.svg#check"/></svg></button></div></span><button id="model-settings" type="button" class="model-button" aria-label="انتخاب مدل"><span id="model-label">پیش‌فرض</span><svg class="icon" aria-hidden="true"><use href="/static/ui-icons.svg#chevron"/></svg></button></div><button id="send" class="send-button" type="submit" title="ارسال پیام" aria-label="ارسال پیام"><svg class="icon" aria-hidden="true"><use id="send-icon" href="/static/ui-icons.svg#arrow"/></svg></button></div>
  </form><div class="composer-meta"><button id="folder-button" title="انتخاب پوشهٔ کاری"><svg class="icon" aria-hidden="true"><use href="/static/ui-icons.svg#folder"/></svg><span id="folder-label">پوشهٔ کاری</span><svg class="icon chevron" aria-hidden="true"><use href="/static/ui-icons.svg#chevron"/></svg></button><span id="notebook-control" hidden><label for="notebook-select" class="sr-only">انتخاب دفتر NotebookLM</label><select id="notebook-select"><option value="">یک دفتر انتخاب کنید</option></select><button id="refresh-notebooks" type="button" title="دریافت دوبارهٔ دفترها" aria-label="دریافت دوبارهٔ دفترها"><svg class="icon" aria-hidden="true"><use href="/static/ui-icons.svg#activity"/></svg></button><a id="open-notebook" target="_blank" rel="noopener noreferrer" hidden>باز کردن دفتر</a></span><span id="access-label">ویرایش و اجرا</span><span id="run-status" role="status"></span></div><p id="provider-hint" class="provider-hint" hidden></p><div id="start-suggestions" class="suggestions" aria-label="پیشنهاد برای شروع"><button data-prompt="ساختار این پروژه را بررسی کن و مهم‌ترین مشکلاتش را توضیح بده."><svg class="icon" aria-hidden="true"><use href="/static/ui-icons.svg#folder"/></svg>بررسی پروژه</button><button data-prompt="README پروژه را بخوان و مراحل اجرای آن را مشخص کن."><svg class="icon" aria-hidden="true"><use href="/static/ui-icons.svg#document"/></svg>خواندن مستندات</button><button data-prompt="تست‌های پروژه را اجرا کن و اگر خطایی هست علتش را پیدا کن."><svg class="icon" aria-hidden="true"><use href="/static/ui-icons.svg#code"/></svg>اجرای تست‌ها</button></div></div>
 </div>
</main>
<aside id="activity-panel" class="activity-panel" hidden><div class="panel-title"><strong>فعالیت اجرا</strong><button id="close-activity" class="icon-button" aria-label="بستن فعالیت"><svg class="icon" aria-hidden="true"><use href="/static/ui-icons.svg#close"/></svg></button></div><p class="muted">فرمان‌ها و تغییر فایل‌های این گفتگو</p><div id="activity"></div></aside>
<dialog id="workspace-settings"><div class="panel-title"><h2>تنظیمات گفتگو</h2><button data-close="workspace-settings" class="icon-button" aria-label="بستن تنظیمات"><svg class="icon" aria-hidden="true"><use href="/static/ui-icons.svg#close"/></svg></button></div><div class="settings-fields"><label for="model">مدل</label><input id="model" list="model-list" placeholder="پیش‌فرض دستیار" maxlength="100" dir="ltr"><datalist id="model-list"></datalist><label for="access">دسترسی به پروژه</label><select id="access"><option value="work">خواندن، ویرایش و اجرای فرمان</option><option value="read">فقط خواندن فایل‌ها</option></select><label class="checkbox-label"><input id="use-memory" type="checkbox" checked> استفاده از حافظهٔ محلی</label><p id="settings-hint" class="muted">مدل و دسترسی برای این گفتگو حفظ می‌شوند.</p><button id="save-settings" class="primary">انجام شد</button></div></dialog>
<dialog id="connections"><div class="panel-title"><h2>حساب‌های متصل</h2><button data-close="connections" class="icon-button" aria-label="بستن"><svg class="icon" aria-hidden="true"><use href="/static/ui-icons.svg#close"/></svg></button></div><p>دستیارها و ابزارهای تحقیق را با حساب‌های خودت استفاده کن.</p><div id="provider-cards"></div><button id="refresh-status">بررسی دوبارهٔ اتصال</button><p class="muted">مصرف مطابق سرویس انتخاب‌شده است: سهمیهٔ حساب، کیف پول GapCode یا Gemini API.</p></dialog>
<dialog id="folder-dialog"><form id="folder-form"><div class="panel-title"><h2>پوشهٔ پروژه</h2><button type="button" data-close="folder-dialog" class="icon-button" aria-label="بستن"><svg class="icon" aria-hidden="true"><use href="/static/ui-icons.svg#close"/></svg></button></div><label for="cwd">مسیر پوشه</label><input id="cwd" dir="ltr" required placeholder="D:\project\my-project"><p class="muted">دستیار در این پوشه کار می‌کند. برای عوض کردن پروژه، گفتگوی تازه بساز.</p><p id="folder-error" role="alert" hidden></p><button type="submit" class="primary">انتخاب پوشه</button></form></dialog>
<dialog id="search-dialog"><div class="panel-title"><h2>جستجوی گفتگوها</h2><button data-close="search-dialog" class="icon-button" aria-label="بستن جستجو"><svg class="icon" aria-hidden="true"><use href="/static/ui-icons.svg#close"/></svg></button></div><label for="chat-search" class="sr-only">عبارت جستجو</label><input id="chat-search" type="search" placeholder="جستجو در گفتگوهای شما…"><div id="search-results"></div></dialog>
<dialog id="project-memory-dialog" aria-labelledby="project-memory-title"><div class="panel-title"><h2 id="project-memory-title">پروژه‌ها و حافظه</h2><button data-close="project-memory-dialog" class="icon-button" aria-label="بستن پروژه‌ها و حافظه"><svg class="icon" aria-hidden="true"><use href="/static/ui-icons.svg#close"/></svg></button></div><div class="workspace-tabs" role="tablist" aria-label="بخش‌های فضای کار"><button id="projects-tab" role="tab" aria-selected="true" aria-controls="projects-panel">پروژه‌ها</button><button id="memories-tab" role="tab" aria-selected="false" aria-controls="memories-panel" tabindex="-1">حافظه</button></div><div class="workspace-tools"><label for="workspace-search" class="sr-only">جستجوی پروژه یا حافظه</label><input id="workspace-search" type="search" placeholder="جستجو در پروژه‌ها…"><button id="workspace-refresh" title="دریافت دوبارهٔ پروژه‌ها و حافظه" aria-label="دریافت دوبارهٔ پروژه‌ها و حافظه"><svg class="icon" aria-hidden="true"><use href="/static/ui-icons.svg#activity"/></svg></button></div><p id="workspace-error" role="alert" hidden></p><p id="workspace-notice" role="status" hidden></p><section id="projects-panel" role="tabpanel" aria-labelledby="projects-tab"><div class="workspace-panel-heading"><p class="muted">پوشهٔ پروژه را در یک گفتگوی تازه باز کن.</p><button id="add-project" class="primary">پروژهٔ جدید</button></div><label class="checkbox-label"><input id="include-archived-projects" type="checkbox"> نمایش پروژه‌های بایگانی‌شده</label><div id="project-list" class="workspace-list"></div></section><section id="memories-panel" role="tabpanel" aria-labelledby="memories-tab" hidden><div class="workspace-panel-heading"><p class="muted">یادداشت‌های فعال در گفتگوهای جدید با گزینهٔ حافظه بازیابی می‌شوند. فقط حافظهٔ تأییدشدهٔ همین پروژه و یادداشت‌های صریحاً مشترک بازیابی می‌شوند.</p><button id="add-memory" class="primary">یادداشت جدید</button></div><label for="memory-filter-project">پروژهٔ یادداشت‌ها</label><select id="memory-filter-project"><option value="all">همهٔ یادداشت‌ها</option></select><div id="memory-list" class="workspace-list"></div></section><a class="workspace-legacy-link" href="/legacy">تاریخچه و امکانات نسخهٔ قبلی</a></dialog>
<dialog id="project-editor" aria-labelledby="project-editor-title"><form id="project-form" class="workspace-form"><div class="panel-title"><h2 id="project-editor-title">پروژهٔ جدید</h2><button type="button" data-close="project-editor" class="icon-button" aria-label="بستن ویرایش پروژه"><svg class="icon" aria-hidden="true"><use href="/static/ui-icons.svg#close"/></svg></button></div><label for="project-name">نام پروژه</label><input id="project-name" required maxlength="120"><label for="project-path">مسیر پوشهٔ پروژه</label><input id="project-path" dir="ltr" required maxlength="1000" placeholder="D:\project\my-project"><label for="project-description">توضیح پروژه</label><textarea id="project-description" rows="3" maxlength="5000"></textarea><p id="project-edit-error" role="alert" hidden></p><button type="submit" class="primary">ذخیرهٔ پروژه</button></form></dialog>
<dialog id="memory-editor" aria-labelledby="memory-editor-title"><form id="memory-form" class="workspace-form"><div class="panel-title"><h2 id="memory-editor-title">یادداشت جدید</h2><button type="button" data-close="memory-editor" class="icon-button" aria-label="بستن ویرایش یادداشت"><svg class="icon" aria-hidden="true"><use href="/static/ui-icons.svg#close"/></svg></button></div><label for="memory-project">پروژه</label><select id="memory-project"></select><label for="memory-status">وضعیت دانش</label><select id="memory-status"><option value="verified">تأییدشده توسط شما</option><option value="proposed">پیشنهاد؛ بازیابی نمی‌شود</option><option value="stale">قدیمی؛ بازیابی نمی‌شود</option></select><label for="memory-title">عنوان یادداشت</label><input id="memory-title" required maxlength="120"><label for="memory-content">متن یادداشت</label><textarea id="memory-content" required rows="6" maxlength="12000"></textarea><label class="checkbox-label"><input id="memory-enabled" type="checkbox" checked> استفاده در حافظهٔ گفتگو</label><p id="memory-edit-error" role="alert" hidden></p><button type="submit" class="primary">ذخیرهٔ یادداشت</button></form></dialog>
<dialog id="workspace-confirm" aria-labelledby="workspace-confirm-title"><form id="workspace-confirm-form" class="workspace-form"><h2 id="workspace-confirm-title">حذف یادداشت</h2><p id="workspace-confirm-message"></p><p id="workspace-confirm-error" role="alert" hidden></p><div class="workspace-actions"><button type="button" data-close="workspace-confirm">انصراف</button><button type="submit" class="primary">حذف یادداشت</button></div></form></dialog>
<script src="/static/local.js"></script><script src="/static/project-memory.js"></script>
</body></html>
```


## Source: src/flux/static/local.css
SHA-256: 8e671bf2ab8cf17288bdf3556149710c2fb1527a670c660204cf62172ae1f11f


```css
@font-face{font-family:Peyda;src:url('/static/fonts/Peyda-Regular.woff2') format('woff2');font-weight:400;font-display:swap}
@font-face{font-family:Peyda;src:url('/static/fonts/Peyda-SemiBold.woff2') format('woff2');font-weight:600 800;font-display:swap}
@font-face{font-family:Geist;src:url('/static/fonts/Geist-500.woff2') format('woff2');font-weight:400 700;font-display:swap}
@font-face{font-family:Vazirmatn;src:url('/static/fonts/Vazirmatn.woff2') format('woff2');font-display:swap}
:root{--bg:#0a0a0a;--sidebar:#111111;--surface:#171717;--raised:#242424;--text:#f2f2ee;--muted:#a1a1aa;--faint:#828282;--border:#303030;--line:#202020;--accent:#f2f2ee;--accent-ink:#0a0a0a;--radius:18px;--font:Peyda,Vazirmatn,system-ui,sans-serif;color-scheme:dark}
*{box-sizing:border-box}body{margin:0;display:flex;direction:ltr;height:100dvh;overflow:hidden;background:var(--bg);color:var(--text);font:15px/1.7 var(--font)}button,input,select,textarea{font:inherit}button,a{touch-action:manipulation}button{cursor:pointer;color:inherit;background:transparent;border:1px solid var(--border);border-radius:9px;padding:8px 14px;min-height:40px;transition:background .15s,color .15s}button:hover{background:var(--raised)}button:disabled{cursor:default;opacity:.5}a{color:inherit;text-decoration:none}a:hover{color:#fff}button.primary{background:var(--accent);color:var(--accent-ink);border-color:transparent;font-weight:600}button.primary:hover{background:#d4d4d0}:focus-visible{outline:2px solid var(--text);outline-offset:3px}.icon{width:19px;height:19px;flex:none;display:block}.icon-button{display:grid;place-items:center;padding:0;width:40px;height:40px;border:0;flex:none}.muted{color:var(--muted);font-size:13px}input,select{background:var(--surface);color:var(--text);border:1px solid var(--border);border-radius:9px;padding:10px 12px;min-height:44px;width:100%;min-width:0}label{font-size:14px}button svg,a svg{pointer-events:none}.brand img,.account-avatar img,.welcome-brand img{filter:invert(1)}
.icon{fill:none;stroke:currentColor;stroke-width:1.6;stroke-linecap:round;stroke-linejoin:round}
.sidebar{direction:rtl;width:252px;flex:none;background:var(--sidebar);border-right:1px solid var(--line);padding:14px 12px;display:flex;flex-direction:column;gap:16px;height:100dvh}.sidebar-heading{display:flex;direction:ltr;align-items:center;justify-content:space-between;padding:0 7px}.brand{display:flex;align-items:center;gap:10px}.brand strong{font:500 25px/1 Geist,system-ui}.sidebar-heading .icon-button{color:var(--muted)}.sidebar-navigation{display:grid;gap:3px;margin-top:10px}.navigation-item{display:flex;align-items:center;gap:12px;width:100%;border:0;text-align:right;min-height:44px;padding:9px 12px;border-radius:8px;font-size:14px}.navigation-item:hover{background:var(--raised)}.navigation-item svg{color:var(--muted);width:18px;height:18px}.navigation-item kbd{margin-right:auto;direction:ltr;font:10px Geist,system-ui;color:var(--faint);opacity:0;transition:opacity .15s}.navigation-item:hover kbd{opacity:1}.section-label{font-size:12px;color:var(--faint);padding:12px 12px 0}#history{overflow-y:auto;flex:1;min-height:0}.history-item{width:100%;text-align:right;border:0;margin-bottom:3px;display:block;border-radius:8px;padding:9px 12px;min-height:40px}.history-item strong{display:block;font-size:13px;font-weight:400;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.history-item small{display:none}.history-item.selected{background:var(--raised)}.empty-history{color:var(--faint);font-size:12px;padding:6px 12px}.sidebar-bottom{border-top:1px solid var(--line);padding-top:10px}.account-button{display:flex;align-items:center;gap:10px;width:100%;border:0;padding:8px;min-height:60px;text-align:right}.account-avatar{display:grid;place-items:center;width:38px;height:38px;border:1px solid var(--border);border-radius:50%;flex:none}.account-copy{display:flex;flex-direction:column;gap:2px;flex:1}.account-copy strong{font:500 11px Geist,system-ui;letter-spacing:1.5px}.account-copy small{font-size:11px;color:var(--muted)}.account-button>svg{width:16px;height:16px;color:var(--faint)}
main{direction:rtl;flex:1;min-width:0;height:100dvh;display:flex;flex-direction:column}.topbar{height:70px;flex:none;padding:0 28px;display:flex;align-items:center;justify-content:space-between;direction:ltr;gap:16px}.workspace-heading{display:flex;align-items:center;gap:14px;min-width:0}.workspace-heading>strong{font:500 17px Geist,var(--font);max-width:300px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.workspace-heading>span{color:var(--faint);font-size:12px;direction:rtl;border-left:1px solid var(--border);padding-left:14px;max-width:350px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.toolbar-button{direction:rtl;display:flex;gap:8px;align-items:center;border:0;color:var(--muted);font-size:12px;padding:6px 10px}.toolbar-button .icon{width:17px;height:17px}.chat-stage{display:flex;flex-direction:column;flex:1;min-height:0}.conversation{flex:1;min-height:0;overflow-y:auto;scrollbar-gutter:stable;padding:20px 28px}.welcome{max-width:740px;margin:0 auto;text-align:center}.welcome-brand{display:flex;align-items:center;justify-content:center;gap:10px;direction:ltr;color:#d4d4d8}.welcome-brand>span{font:500 10px Geist,system-ui;letter-spacing:2.3px}.brand-divider{color:#71717a;padding:0 5px}h1{font-size:36px;line-height:1.6;font-weight:600;margin:18px 0 0;letter-spacing:-.7px}.composer-wrap{width:min(794px,100%);margin:0 auto;padding:0 26px 22px;flex:none}#composer{background:var(--surface);border:1px solid #373737;border-radius:var(--radius);padding:16px 18px 12px;box-shadow:0 4px 18px #0002;transition:border-color .15s}#composer:focus-within{border-color:#666}textarea{display:block;resize:none;border:0;background:transparent;color:var(--text);width:100%;font:16px/1.8 var(--font);min-height:65px;max-height:220px;padding:0 2px;outline:none}textarea::placeholder{color:#929292}textarea:focus-visible{outline:none}.composer-controls{display:flex;align-items:center;justify-content:space-between;margin-top:10px;gap:12px}.composer-tools{display:flex;gap:5px;align-items:center;min-width:0;flex-wrap:wrap}.composer-tools>.icon-button{width:34px;height:34px;min-height:34px;color:var(--muted);border-radius:8px}.provider-control{position:relative;display:flex;align-items:center;border:1px solid #353535;border-radius:8px;direction:ltr;height:32px}.provider-control select{appearance:none;background:transparent;border:0;padding:3px 28px 3px 10px;min-height:30px;height:30px;width:104px;font:500 12px Geist,system-ui;cursor:pointer}.provider-control>.icon{position:absolute;right:5px;width:16px;height:16px;color:var(--muted);pointer-events:none}.model-button{display:flex;align-items:center;gap:4px;border:0;font-size:12px;color:var(--muted);padding:4px 6px;min-height:34px;max-width:220px}.model-button span{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.model-button .icon{width:14px;height:14px}.send-button{width:36px;height:36px;min-height:36px;border-radius:50%;border:0;background:var(--text);color:var(--bg);padding:0;display:grid;place-items:center;flex:none}.send-button:hover{background:#d4d4d0}.send-button:disabled{background:#4a4a4a;color:#a1a1aa;opacity:1}.send-button .icon{width:21px;height:21px}.composer-meta{display:flex;align-items:center;justify-content:flex-start;gap:14px;margin:9px 4px 0;font-size:11px;color:var(--faint);min-height:30px}.composer-meta button{display:flex;gap:6px;align-items:center;color:var(--muted);font-size:11px;border:0;padding:3px 6px;min-height:30px;max-width:60%}.composer-meta button .icon{width:14px;height:14px}.composer-meta .chevron{width:11px;height:11px}.composer-meta button span{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;direction:ltr;unicode-bidi:plaintext}#access-label{border-right:1px solid var(--border);padding-right:12px}#run-status{margin-right:auto;color:var(--text)}.suggestions{display:flex;gap:9px;justify-content:center;margin:18px 0 0;flex-wrap:wrap}.suggestions button{display:flex;gap:8px;align-items:center;border:1px solid #292929;border-radius:9px;font-size:12px;min-height:38px;padding:6px 12px;color:#b4b4b4}.suggestions svg{width:15px;height:15px;color:#919191}.suggestions button:hover{color:var(--text);border-color:#4d4d4d}
body[data-chat-state=welcome] .chat-stage{justify-content:center;padding-bottom:100px}body[data-chat-state=welcome] .conversation{flex:none;overflow:visible;padding:0 20px;scrollbar-gutter:auto}body[data-chat-state=welcome] .composer-wrap{margin:28px auto 0;padding-bottom:0}body[data-chat-state=chat] .suggestions{display:none}
#messages{max-width:742px;margin:0 auto}.message{margin:16px 0 34px}.message.user{background:#222;border-radius:16px;padding:13px 20px;max-width:85%;width:fit-content;margin-right:0;margin-left:auto}.message-label{display:flex;gap:8px;align-items:center;font:500 12px Geist,system-ui;color:var(--muted);margin-bottom:12px}.message-label img{filter:invert(1);width:22px;height:22px}.message-content{overflow-wrap:anywhere;unicode-bidi:plaintext;line-height:1.9;font-size:16px}.message-content p{margin:0 0 14px;white-space:pre-wrap}.message-content p:last-child{margin-bottom:0}.message-content h2,.message-content h3,.message-content h4{margin:24px 0 10px;font-weight:600;line-height:1.7}.message-content h2{font-size:24px}.message-content h3{font-size:20px}.message-content h4{font-size:17px}.message-content ul,.message-content ol{padding-right:24px;margin:10px 0 18px}.message-content li{margin:5px 0}.message-content blockquote{border-right:2px solid #666;margin:16px 0;padding:4px 16px;color:#c4c4c4}.message-content code{font:13px/1.7 Consolas,monospace;background:#282828;padding:2px 5px;border-radius:4px;direction:ltr;unicode-bidi:embed}.message-content a{color:var(--text);text-decoration:underline;text-underline-offset:3px}.code-block{border:1px solid var(--border);border-radius:12px;margin:18px 0;overflow:hidden;background:#111}.code-header{display:flex;direction:ltr;align-items:center;justify-content:space-between;padding:5px 12px;background:#1d1d1d;color:var(--muted);font:11px Geist,system-ui}.code-header button{min-height:30px;padding:2px 8px;border:0;font:12px var(--font)}.message-content pre{direction:ltr;text-align:left;padding:16px;overflow-x:auto;white-space:pre;margin:0}.message-content pre code{padding:0;background:none}.turn-meta{color:var(--faint);font-size:11px;margin-top:16px}.message-actions{display:flex;gap:4px;margin-top:4px}.message-actions button{border:0;min-height:34px;font-size:11px;padding:4px 8px;color:var(--muted)}.message-actions button .icon{width:16px;height:16px}.message-actions .icon-action{display:grid;place-items:center;width:34px;padding:0}#error,#folder-error,.turn-error{border:1px solid #555;background:#202020;color:var(--text);border-radius:10px;padding:10px 14px;margin-bottom:12px;white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px}
.activity-panel{direction:rtl;width:330px;flex:none;border-left:1px solid var(--border);background:var(--sidebar);height:100dvh;overflow:auto;padding:20px 16px}.panel-title{display:flex;align-items:center;justify-content:space-between;gap:12px}.panel-title h2{font-size:20px;font-weight:600;margin:0}.activity-event{margin:12px 0;padding:10px;background:var(--surface);border:1px solid var(--border);border-radius:9px;font-size:12px}.activity-event summary{cursor:pointer;overflow-wrap:anywhere}.activity-event pre{direction:ltr;text-align:left;overflow:auto;max-height:350px;font:12px/1.6 Consolas,monospace;white-space:pre-wrap;overflow-wrap:anywhere}dialog{direction:rtl;max-width:min(500px,calc(100vw - 32px));width:500px;background:#171717;color:var(--text);border:1px solid #414141;border-radius:17px;padding:22px;box-shadow:0 20px 90px #0007}dialog::backdrop{background:#0009;backdrop-filter:blur(3px)}dialog p{font-size:13px}.settings-fields{display:flex;flex-direction:column;gap:12px;padding-top:16px}.checkbox-label{display:flex;align-items:center;gap:9px;padding:8px 0;color:#d4d4d8}.checkbox-label input{width:16px;min-height:16px;accent-color:var(--text)}.provider-card{padding:15px;border:1px solid var(--border);border-radius:11px;margin:14px 0}.provider-card>strong{font:500 15px Geist,system-ui}.provider-card code{display:block;direction:ltr;text-align:left;white-space:pre-wrap;overflow-wrap:anywhere;background:var(--bg);padding:10px;margin-top:10px;border-radius:7px;font:12px/1.7 Consolas,monospace}.provider-card .ready{color:var(--text)}.provider-card small{display:block;color:var(--muted);font-size:11px;overflow-wrap:anywhere}.provider-card small:last-child{direction:ltr;text-align:left}#folder-form{display:flex;flex-direction:column;gap:14px}#search-dialog input{margin-top:16px}#search-results{margin-top:12px;max-height:330px;overflow:auto}#search-results button{display:flex;flex-direction:column;width:100%;align-items:flex-start;border:0;padding:9px 10px}#search-results button span{font-size:13px}#search-results button small{font:11px Geist,system-ui;color:var(--muted)}.mobile,.sidebar-scrim{display:none}.sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}[hidden]{display:none!important}
.sidebar-collapsed .sidebar{width:74px;padding:14px 10px}.sidebar-collapsed .sidebar-heading{flex-direction:column;gap:13px;padding:0}.sidebar-collapsed .brand strong,.sidebar-collapsed .navigation-item span,.sidebar-collapsed .navigation-item kbd,.sidebar-collapsed .section-label,.sidebar-collapsed #history,.sidebar-collapsed .account-copy,.sidebar-collapsed .account-button>svg{display:none}.sidebar-collapsed .sidebar-navigation{margin-top:0}.sidebar-collapsed .navigation-item{justify-content:center;padding:10px}.sidebar-collapsed .sidebar-bottom{margin-top:auto}.sidebar-collapsed .account-button{padding:0;justify-content:center}
@media(max-width:1200px){.activity-panel{position:fixed;right:0;top:0;z-index:25;width:340px;box-shadow:-10px 0 50px #0009}.workspace-heading>span{max-width:200px}}@media(max-width:850px){.sidebar,.sidebar-collapsed .sidebar{position:fixed;left:0;top:0;z-index:20;width:260px;padding:14px 12px;transform:translateX(-100%);visibility:hidden;transition:transform .18s,visibility .18s}.sidebar.open{transform:translateX(0);visibility:visible}.sidebar-collapsed .sidebar-heading{flex-direction:row;padding:0 7px;gap:0}.sidebar-collapsed .brand strong,.sidebar-collapsed .navigation-item span,.sidebar-collapsed .section-label,.sidebar-collapsed #history,.sidebar-collapsed .account-copy,.sidebar-collapsed .account-button>svg{display:revert}.sidebar-collapsed .navigation-item{justify-content:flex-start;padding:9px 12px}.sidebar-collapsed .account-button{padding:8px;justify-content:flex-start}.sidebar-collapsed .sidebar-bottom{margin-top:0}.sidebar-scrim.open{display:block;position:fixed;inset:0;background:#0008;border:0;border-radius:0;z-index:19}.mobile{display:grid}.topbar{height:62px;padding:0 14px;gap:8px}.workspace-heading{gap:8px}.workspace-heading>strong{max-width:160px;font-size:15px}.workspace-heading>span{display:none}.toolbar-button{padding:6px}.conversation{padding:14px 20px}.composer-wrap{padding:0 18px 16px;max-width:760px}body[data-chat-state=welcome] .chat-stage{padding-bottom:70px}body[data-chat-state=welcome] .composer-wrap{margin-top:24px}.welcome-brand>span{font-size:9px}.welcome-brand img{width:30px;height:30px}h1{font-size:29px;margin-top:16px}.message-content{font-size:15px}.message.user{max-width:90%}.activity-panel{width:min(340px,100vw)}.model-button{max-width:155px}}
@media(max-width:480px){.composer-wrap{padding-right:14px;padding-left:14px}#composer{padding:14px 13px 11px;border-radius:16px}textarea{font-size:15px;min-height:72px}.composer-tools{gap:2px}.model-button{max-width:112px;font-size:11px}.provider-control select{width:91px;font-size:11px}.composer-controls{gap:6px}.send-button{width:38px;height:38px;min-height:38px}.composer-meta{gap:8px;font-size:10px}.composer-meta button{max-width:54%;font-size:10px}#access-label{padding-right:8px}.suggestions{gap:7px;margin-top:14px}.suggestions button{font-size:11px;padding:5px 9px;min-height:36px}.suggestions button .icon{width:13px;height:13px}h1{font-size:27px}.welcome{padding:0 10px}.workspace-heading>strong{max-width:190px}body[data-chat-state=welcome] .chat-stage{padding-bottom:36px}}@media(max-height:650px){body[data-chat-state=welcome] .chat-stage{padding-bottom:20px}.welcome-brand{display:none}h1{font-size:28px}body[data-chat-state=welcome] .composer-wrap{margin-top:20px}.suggestions{margin-top:10px}}@media(prefers-reduced-motion:reduce){*{transition:none!important;scroll-behavior:auto!important}}@media(forced-colors:active){button,input,select,#composer{border:1px solid CanvasText}}
@media(max-width:480px){.send-button{width:44px;height:44px;min-height:44px}.composer-tools>.icon-button{width:44px;height:44px;min-height:44px}.provider-control{height:44px}.provider-control select{height:44px;min-height:44px}.model-button{min-height:44px}.composer-meta button{min-height:44px}.suggestions button{min-height:44px;font-size:12px}}
/* Projects and memory stay in the current Flux interface. */
#project-memory-dialog{width:860px;max-width:calc(100vw - 32px);max-height:calc(100dvh - 32px);overflow:auto}.workspace-tabs{display:flex;gap:8px;border-bottom:1px solid var(--border);padding:18px 0 12px}.workspace-tabs button{border:0}.workspace-tabs [aria-selected=true]{background:var(--raised);font-weight:600}.workspace-tools{display:flex;gap:8px;margin:16px 0}.workspace-tools button{flex:none;padding:8px 12px}.workspace-panel-heading{display:flex;gap:16px;align-items:center;justify-content:space-between}.workspace-panel-heading p{margin:8px 0;max-width:580px}.workspace-panel-heading button{flex:none}.workspace-list{display:grid;gap:12px;margin:16px 0}.workspace-card{border:1px solid var(--border);border-radius:12px;padding:16px;min-width:0}.workspace-card-heading{display:flex;align-items:flex-start;justify-content:space-between;gap:16px}.workspace-card h3{font-size:16px;margin:0;overflow-wrap:anywhere}.workspace-badge{color:var(--muted);font-size:11px;flex:none}.workspace-path,.workspace-card-content{overflow-wrap:anywhere;white-space:pre-wrap}.workspace-path{font:12px/1.8 Consolas,monospace;color:var(--muted);text-align:left}.workspace-card-content{max-height:200px;overflow:auto}.workspace-actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:14px}.workspace-actions button{font-size:12px}.workspace-legacy-link{display:block;color:var(--muted);font-size:12px;border-top:1px solid var(--border);padding-top:14px;text-decoration:underline;text-underline-offset:4px}.workspace-form{display:flex;flex-direction:column;gap:12px}.workspace-form textarea{border:1px solid var(--border);border-radius:9px;padding:10px 12px;background:var(--surface);min-height:100px;max-height:300px;resize:vertical;outline:revert}.workspace-form textarea:focus-visible{outline:2px solid var(--text)}#workspace-error,#project-edit-error,#memory-edit-error,#workspace-confirm-error{border:1px solid #666;border-radius:9px;padding:10px;overflow-wrap:anywhere}#workspace-notice{color:var(--muted);padding:4px 0}#workspace-confirm h2{margin:0;font-size:20px}@media(max-width:480px){#project-memory-dialog{padding:16px}.workspace-panel-heading{align-items:flex-start;flex-direction:column;gap:4px}.workspace-card{padding:12px}.workspace-actions button{min-height:44px}.workspace-card-heading{gap:8px}}
/* Flux identity, Persian navigation, and account quota */
body{direction:rtl}.sidebar{border-right:0;border-left:1px solid var(--line)}.brand img,.account-avatar img,.welcome-brand img,.message-label img{filter:none}.welcome-brand>span{font-family:var(--font);letter-spacing:0;font-size:12px}.account-copy strong{font-family:var(--font);font-size:13px}.account-copy small{font-size:11px;line-height:1.8}#account-usage{direction:ltr;font-family:Geist,var(--font);font-size:10px}.activity-panel{border-left:0;border-right:1px solid var(--border)}.provider-control{position:relative;display:block;height:auto;min-height:34px;overflow:visible;flex:none}.provider-control>svg{display:none}.provider-control #provider-toggle{direction:ltr;display:flex;gap:16px;align-items:center;justify-content:space-between;min-height:34px;padding:5px 10px;border:1px solid var(--border);border-radius:9px;font:500 12px Geist,var(--font);min-width:105px}.provider-control #provider-toggle .icon{position:static;width:14px;height:14px;transform:none}.provider-control #provider-toggle:disabled{opacity:.55}#provider-menu{position:absolute;bottom:calc(100% + 9px);right:0;width:210px;padding:6px;background:#202020;border:1px solid #444;border-radius:12px;box-shadow:0 10px 35px #0008;z-index:15;direction:ltr}#provider-menu button{display:flex;align-items:center;justify-content:space-between;gap:16px;width:100%;border:0;border-radius:7px;min-height:56px;padding:8px 12px;text-align:left;background:transparent;color:#f2f2ee}#provider-menu button:hover,#provider-menu button:focus-visible{background:#343434}#provider-menu button[aria-selected=true]{background:#303030}#provider-menu strong{display:block;font:500 13px Geist,var(--font)}#provider-menu small{display:block;font:12px var(--font);color:#c2c2c2}#provider-menu .icon{position:static;width:17px;height:17px;transform:none}#provider-menu [aria-selected=false] .provider-check{visibility:hidden}.quota-card{margin-top:18px;border-top:1px solid var(--border);padding-top:4px}.quota-window{padding-top:14px}.quota-heading{display:flex;justify-content:space-between;gap:12px;align-items:center;font-size:13px}.quota-heading strong{font-size:14px;font-weight:600}.quota-track{height:5px;border-radius:8px;background:#353535;overflow:hidden;margin-top:9px;direction:ltr}.quota-fill{display:block;height:100%;border-radius:8px;background:#f2f2ee}.quota-reset,.quota-updated,.quota-detail{color:#ababab;font-size:11px!important;line-height:1.8;margin:6px 0 0}.quota-updated{padding-top:10px;color:#939393}.quota-detail{font-size:12px!important}.provider-card>strong{display:block;direction:ltr;text-align:right}.provider-card>small{direction:ltr;text-align:right}.provider-card .ready{font-size:12px;color:#c2c2c2;margin-bottom:0}#connections{max-height:calc(100dvh - 40px);overflow-y:auto}#refresh-status{width:100%;min-height:44px}
@media(max-width:1200px){.activity-panel{right:auto;left:0;box-shadow:10px 0 50px #0009}}@media(max-width:850px){.sidebar,.sidebar-collapsed .sidebar{left:auto;right:0;transform:translateX(100%)}.sidebar.open{transform:translateX(0)}}@media(max-width:480px){.provider-control #provider-toggle{min-height:44px;min-width:91px;gap:10px}.provider-control{height:auto}#provider-menu{width:195px}.quota-heading{font-size:12px}.quota-heading strong{font-size:13px}}
/* Google assistants and source-grounded conversations */
#provider-menu{max-height:min(320px,60dvh);overflow-y:auto;width:230px}.provider-hint{color:#b8b8b8;font-size:12px;line-height:1.8;margin:8px 5px 0}.composer-meta{flex-wrap:wrap}#notebook-control{display:flex;align-items:center;gap:6px;max-width:100%;flex:1}#notebook-select{width:auto;max-width:330px;min-width:130px;min-height:36px;padding:4px 10px;font-size:12px}#notebook-control button{width:34px;max-width:none;min-height:36px;padding:0;display:grid;place-items:center}#open-notebook{font-size:11px;color:#bdbdbd;white-space:nowrap;text-decoration:underline;text-underline-offset:3px}.integration-note{font-size:11px!important;color:#aaa}.source-references{border:1px solid var(--border);border-radius:9px;font-size:12px;padding:9px 12px;margin:14px 0;color:#c5c5c5}.source-references summary{cursor:pointer}.source-references p{white-space:pre-wrap;overflow-wrap:anywhere}.provider-control #provider-toggle{min-width:110px;gap:10px}#account-usage{max-width:170px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
@media(max-width:480px){#provider-menu{width:210px}.provider-control #provider-toggle{min-width:100px}#notebook-select{max-width:220px;min-height:44px}#notebook-control button{min-height:44px}#open-notebook{font-size:10px}}
#notebook-select option{background:#242424;color:#f2f2ee}#account-usage{white-space:normal;overflow:visible;max-width:none;display:grid;grid-template-columns:1fr 1fr;gap:2px 10px;font-size:10px;direction:ltr;text-align:left}#account-usage span{white-space:nowrap}
```


## Source: src/flux/static/project-memory.js
SHA-256: 001cbc33e90d4ac50e6c3c80231ff65caa5bb0f8170a2aef59e003aaeac840cd


```javascript
'use strict';
// This panel shares the existing project and memory API with the legacy UI.
const workspaceData={projects:[],memories:[],tab:'projects',projectEdit:null,memoryEdit:null,pendingDelete:null,loading:0};
const workspaceNormalize=value=>String(value||'').replace(/ي/g,'ی').replace(/ك/g,'ک').replace(/\u200c/g,' ').toLocaleLowerCase();
function workspaceError(error,id='workspace-error'){const node=$(id);node.textContent=error.message||String(error);node.hidden=false;}
function workspaceNotice(message){$('workspace-notice').textContent=message;$('workspace-notice').hidden=false;}
function workspaceAction(label,action,className=''){const button=textNode('button',label,className);button.type='button';button.onclick=()=>Promise.resolve().then(action).catch(error=>workspaceError(error));return button;}
function workspaceTab(tab){
 workspaceData.tab=tab;$('workspace-search').value='';
 for(const key of ['projects','memories']){const selected=tab===key;$(key+'-tab').setAttribute('aria-selected',String(selected));$(key+'-tab').tabIndex=selected?0:-1;$(key+'-panel').hidden=!selected;}
 $('workspace-search').placeholder=tab==='projects'?'جستجو در پروژه‌ها…':'جستجو در حافظه…';renderWorkspace();
}
function renderWorkspace(){
 const query=workspaceNormalize($('workspace-search').value.trim());
 const projects=workspaceData.projects.filter(p=>(!p.archived||$('include-archived-projects').checked)&&workspaceNormalize(p.name+' '+p.path+' '+p.description).includes(query));
 $('project-list').replaceChildren();
 for(const project of projects){
  const card=textNode('article','','workspace-card');card.dataset.projectId=project.id;
  const heading=textNode('div','','workspace-card-heading');heading.append(textNode('h3',project.name),textNode('span',project.archived?'بایگانی‌شده':'فعال','workspace-badge'));
  const path=textNode('p',project.path,'workspace-path');path.dir='ltr';card.append(heading,path);
  if(project.description)card.append(textNode('p',project.description,'workspace-card-content'));
  const actions=textNode('div','','workspace-actions');
  if(!project.archived){const use=workspaceAction('گفتگوی تازه در این پروژه',()=>chooseWorkspaceProject(project),'primary');use.disabled=!!active()||state.busy;if(use.disabled)use.title='پس از پایان اجرای جاری، پروژه را انتخاب کن.';actions.append(use);}
  actions.append(workspaceAction('ویرایش پروژه',()=>editWorkspaceProject(project)),workspaceAction(project.archived?'بازگرداندن پروژه':'بایگانی پروژه',()=>archiveWorkspaceProject(project)));
  card.append(actions);$('project-list').append(card);
 }
 if(!projects.length)$('project-list').append(textNode('p',query?'پروژه‌ای پیدا نشد.':'هنوز پروژه‌ای ثبت نشده است.','muted'));
 const scope=$('memory-filter-project').value;const memories=workspaceData.memories.filter(m=>(scope==='all'||m.project_id===scope)&&workspaceNormalize(m.title+' '+m.content).includes(query));$('memory-list').replaceChildren();
 for(const memory of memories){
  const card=textNode('article','','workspace-card');card.dataset.memoryId=memory.id;
  const heading=textNode('div','','workspace-card-heading');heading.append(textNode('h3',memory.title),textNode('span',memory.enabled?'فعال':'غیرفعال','workspace-badge'));
  card.append(textNode('small',(workspaceData.projects.find(p=>p.id===memory.project_id)?.name|| (memory.project_id==='*'?'مشترک با اجازهٔ شما':'بدون پروژه'))+' · '+({verified:'تأییدشده',proposed:'پیشنهاد',stale:'قدیمی'}[memory.status]||memory.status),'muted'));card.append(heading,textNode('p',memory.content,'workspace-card-content'),textNode('p','نسخهٔ '+Number(memory.revision).toLocaleString('fa-IR'),'muted'));
  const actions=textNode('div','','workspace-actions');actions.append(workspaceAction('ویرایش یادداشت',()=>editWorkspaceMemory(memory)),workspaceAction('حذف یادداشت',()=>confirmWorkspaceMemoryDelete(memory)));card.append(actions);$('memory-list').append(card);
 }
 if(!memories.length)$('memory-list').append(textNode('p',query?'یادداشتی پیدا نشد.':'هنوز یادداشتی ثبت نشده است.','muted'));
}
async function loadWorkspace(){
 const generation=++workspaceData.loading;$('workspace-refresh').disabled=true;$('workspace-error').hidden=true;
 const results=await Promise.allSettled([api('/projects?archived=true'),api('/memories')]);
 if(generation!==workspaceData.loading)return;
 for(const [index,result] of results.entries()){if(result.status==='fulfilled')workspaceData[index?'memories':'projects']=result.value;else workspaceError(result.reason);}
 refreshMemoryScopes();renderWorkspace();$('workspace-refresh').disabled=false;
}
async function workspaceFolder(path){const folder=await api('/filesystem/validate-path?path='+encodeURIComponent(path));if(!folder.exists||!folder.is_dir)throw new Error('پوشهٔ پروژه پیدا نشد. مسیر یک پوشهٔ موجود را وارد کن.');return folder;}
async function chooseWorkspaceProject(project){
 if(active()||state.busy)throw new Error('برای انتخاب پروژه، ابتدا اجرای جاری را تمام یا متوقف کن.');
 await workspaceFolder(project.path);
 // A running turn might have started while the folder request was pending.
 if(active()||state.busy)throw new Error('اجرای جاری هنوز تمام نشده است.');
 const draft=$('prompt').value;newChat();state.cwd=project.path;state.projectId=project.id;
 if($('provider').value==='notebooklm'){$('provider').value='codex';$('provider').dispatchEvent(new Event('change'));}
 $('prompt').value=draft;resizePrompt();renderChat();$('project-memory-dialog').close();$('prompt').focus();
}
function editWorkspaceProject(project=null){workspaceData.projectEdit=project?.id||null;$('project-editor-title').textContent=project?'ویرایش پروژه':'پروژهٔ جدید';$('project-name').value=project?.name||'';$('project-path').value=project?.path||state.cwd;$('project-description').value=project?.description||'';$('project-edit-error').hidden=true;$('project-editor').showModal();$('project-name').focus();}
async function saveWorkspaceProject(event){
 event.preventDefault();const button=event.submitter;button.disabled=true;$('project-edit-error').hidden=true;
 try{const payload={name:$('project-name').value.trim(),path:$('project-path').value.trim(),description:$('project-description').value.trim()};if(!payload.name)throw new Error('نام پروژه را وارد کن.');await workspaceFolder(payload.path);await api('/projects'+(workspaceData.projectEdit?'/'+encodeURIComponent(workspaceData.projectEdit):''),{method:workspaceData.projectEdit?'PATCH':'POST',body:JSON.stringify(payload)});$('project-editor').close();await loadWorkspace();workspaceNotice('پروژه ذخیره شد.');}catch(error){workspaceError(error,'project-edit-error');}finally{button.disabled=false;}
}
async function archiveWorkspaceProject(project){await api('/projects/'+encodeURIComponent(project.id),{method:'PATCH',body:JSON.stringify({archived:!project.archived})});await loadWorkspace();workspaceNotice(project.archived?'پروژه بازگردانده شد.':'پروژه بایگانی شد؛ از نمایش پروژه‌های بایگانی‌شده می‌توانی آن را بازگردانی.');}
function editWorkspaceMemory(memory=null){workspaceData.memoryEdit=memory?.id||null;$('memory-editor-title').textContent=memory?'ویرایش یادداشت':'یادداشت جدید';$('memory-title').value=memory?.title||'';$('memory-content').value=memory?.content||'';$('memory-enabled').checked=memory?!!memory.enabled:true;refreshMemoryScopes();$('memory-project').value=memory?.project_id??state.chat?.project_id??state.projectId??'';$('memory-status').value=memory?.status||'verified';workspaceData.memoryRevision=memory?.revision||null;$('memory-edit-error').hidden=true;$('memory-editor').showModal();$('memory-title').focus();}
async function saveWorkspaceMemory(event){
 event.preventDefault();const button=event.submitter;button.disabled=true;$('memory-edit-error').hidden=true;
 try{const payload={title:$('memory-title').value.trim(),content:$('memory-content').value.trim(),enabled:$('memory-enabled').checked,project_id:$('memory-project').value,status:$('memory-status').value,expected_revision:workspaceData.memoryRevision};if(!payload.title||!payload.content)throw new Error('عنوان و متن یادداشت را وارد کن.');await api('/memories'+(workspaceData.memoryEdit?'/'+encodeURIComponent(workspaceData.memoryEdit):''),{method:workspaceData.memoryEdit?'PUT':'POST',body:JSON.stringify(payload)});$('memory-editor').close();await loadWorkspace();workspaceNotice('یادداشت در حافظهٔ محلی ذخیره شد.');}catch(error){workspaceError(error,'memory-edit-error');}finally{button.disabled=false;}
}
function confirmWorkspaceMemoryDelete(memory){workspaceData.pendingDelete=memory.id;$('workspace-confirm-message').textContent='یادداشت «'+memory.title+'» حذف شود؟ در درخواست‌های بعدی بازیابی نمی‌شود. نشست دستیار بازسازی می‌شود. متن قابل مشاهدهٔ گفتگوهای قبلی باقی می‌ماند.';$('workspace-confirm-error').hidden=true;$('workspace-confirm').showModal();}
async function deleteWorkspaceMemory(event){event.preventDefault();const button=event.submitter;button.disabled=true;try{await api('/memories/'+encodeURIComponent(workspaceData.pendingDelete),{method:'DELETE'});workspaceData.pendingDelete=null;$('workspace-confirm').close();await loadWorkspace();workspaceNotice('یادداشت حذف شد.');}catch(error){workspaceError(error,'workspace-confirm-error');}finally{button.disabled=false;}}
$('project-memory-button').onclick=()=>{closeSidebar();$('workspace-notice').hidden=true;$('project-memory-dialog').showModal();loadWorkspace().catch(error=>workspaceError(error));};
$('workspace-refresh').onclick=()=>loadWorkspace().catch(error=>workspaceError(error));$('workspace-search').oninput=renderWorkspace;$('include-archived-projects').onchange=renderWorkspace;
for(const key of ['projects','memories']){$(key+'-tab').onclick=()=>workspaceTab(key);$(key+'-tab').onkeydown=event=>{if(['ArrowLeft','ArrowRight','Home','End'].includes(event.key)){event.preventDefault();const next=event.key==='Home'?'projects':event.key==='End'?'memories':workspaceData.tab==='projects'?'memories':'projects';workspaceTab(next);$(next+'-tab').focus();}};}
$('add-project').onclick=()=>editWorkspaceProject();$('project-form').onsubmit=saveWorkspaceProject;$('add-memory').onclick=()=>editWorkspaceMemory();$('memory-form').onsubmit=saveWorkspaceMemory;$('workspace-confirm-form').onsubmit=deleteWorkspaceMemory;
// local.js installs data-close handlers before this script loads; these dialogs
// are already present in the HTML and use the same native dialog behavior.

function refreshMemoryScopes(){
 for(const id of ['memory-project','memory-filter-project']){
  const node=$(id),old=node.value;node.replaceChildren();
  const options=id==='memory-filter-project'?[['all','همهٔ یادداشت‌ها'],['','بدون پروژه'],['*','مشترک با اجازهٔ شما']]:[['','بدون پروژه'],['*','مشترک با اجازهٔ شما']];
  for(const p of workspaceData.projects)options.push([p.id,p.name+(p.archived?' (بایگانی)':'')]);
  for(const [value,label] of options){const option=textNode('option',label);option.value=value;node.append(option);}
  if(options.some(o=>o[0]===old))node.value=old;
 }
}
$('memory-filter-project').onchange=renderWorkspace;
```


## Source: docs/knowledge/head-memory.fa.md
SHA-256: 9548d5ee23b99349a0f71a774c52897fc3f8ab150e62fe1c09a34eb6b3587827


# حافظهٔ HEAD برای پروژهٔ Flux

شناسهٔ پروژه: `alacrity-flux`؛ تاریخ snapshot: ۱ اکتبر ۲۰۲۶؛ نسخهٔ یادداشت: ۱.

این یادداشت از پاسخ‌های واقعی NotebookLM تولید و با PDF، سورس و گزارش‌ها بازبینی شده است. پاسخ نهایی `notebooklm-generated-memory.json` انگلیسی است و **۱۶ ارجاع ساخت‌یافته به چهار source** دارد؛ متن فارسی حاضر ترجمه و جمع‌بندی بازبینی‌شدهٔ آن و پاسخ اولیه است. پاسخ اولیه در `notebooklm-generated-memory-initial.json` محفوظ است؛ ادعای «۱۰۰٪ مستند» و citationهای صرفاً عددی فارسی آن تأیید نمی‌شوند. برای provenance علاوه بر metadata ارجاع، source ID، مسیر فایل و SHA-256 ثبت شده‌اند. خود پاسخ مدل منبع حقیقت یا مجوز اجرایی نیست.

دفتر: https://notebooklm.google.com/notebook/cbd54447-058f-445c-a1e3-850f15cc5eb9

شناسهٔ گفتگوی تولید: `4fbd3be8-0092-468e-9a09-0336bf53eb1b`؛ Note نهایی ذخیره‌شده در دفتر: `dd52cd81-cfe1-40ed-9e53-4fefd49172bb` (`Flux Project Memory`). یادداشت اولیهٔ طولانی: `9203155b-af41-4ff6-81e9-6c5c15e56d89`؛ نسخهٔ کوتاه فارسی: `cba595c4-7c25-4c0e-ae01-a21f21d71d7e`.

## هویت و هدف پایدار

Flux محصول B2B شرکت Alacrity برای سازمان هیبرید انسان/عامل است. هدف، تقسیم مسئولیت، انجام کار با ابزار، بازبینی قابل سنجش، اختیار مشتری و پذیرش انسانی است. مدل‌های قوی‌تر برای Head/هماهنگی و مدل واجد توانایی با هزینهٔ مناسب برای کار محدود استفاده می‌شوند؛ نقش با نام مدل یکی نیست. کاهش هزینه، کیفیت بهتر و فعالیت شبانه‌روزی باید در پایلوت واقعی اندازه‌گیری شوند و تضمین عمومی نیستند.

مرجع: PDF، صفحات ۲،۴ تا ۹،۱۲ تا ۱۹؛ source `67c6ffe7-d314-451d-9ba3-ac8247274025`.

## تصمیم‌های انسانی

- مسئولیت مدیریتی با انسان است. چارت داخلی Alacrity: دانیال CEO، مبینا COO، سعید CTO، علی توسعه‌دهنده؛ این نمونه نباید چارت ثابت همهٔ مشتریان شود.
- بازبین مستقل و Head بخش هر دو خروجی را کنترل کنند؛ پذیرش نهایی به همان نسخه وصل باشد.
- مدیر شرکت سقف کل و هر بخش را تعیین می‌کند؛ زیرکار هزینهٔ مادر را حفظ می‌کند. کمبود منابع، درخواست افزایش یا توقف می‌خواهد.
- در غیاب مدیر، شاخهٔ منتظر مجوز صبر کند و کار مستقل دارای اختیار ادامه یابد. فوریت مجوز تازه ایجاد نمی‌کند.
- مدیریت روزانه با مشتری است؛ پشتیبانی Alacrity دسترسی دائمی به محتوا ایجاد نمی‌کند.
- JEV یک ذهن مستقل برای هر پروژه است؛ ابتدا الگوریتم/Skill و آزمون، سپس ادغام با Flux. دستور این نوبت ساخت RAG و MDهای دقیق است.

مراجع: وایت‌پیپر؛ `docs/hierarchy.fa.md`؛ گفتگوهای منتخب source `87c6ab11-4cea-47c1-87b3-0414dbaabb2b`. گفتگوها snapshot بخش‌های مرتبطند، نه تاریخچهٔ کامل.

## وضعیت ساخته‌شده

نسخهٔ سورس `0.4.0` است. رابط اصلی یک CLI انتخابی را از Codex/Claude/Antigravity/NotebookLM راه‌اندازی می‌کند؛ موتور قدیمی GapGPT و DAG چند نقش در `/legacy` است. حالت completed پایان نوبت CLI است؛ ACCEPT_CANDIDATE نامزد پذیرش legacy است. ابزارهای Codex/Claude ممکن است فایل/فرمان واقعی داشته باشند؛ موتور متنی legacy چنین اجرای ابزار تولیدشده‌ای ندارد.

NotebookLM با رابط غیررسمی موجود کار می‌کند و منابع همان دفتر را می‌خواند. حافظهٔ محلی Flux در شاخهٔ NotebookLM تزریق نمی‌شود. در این نوبت دفتر اختصاصی و sourceهای پروژه صریح وارد آن شدند. گزارش تاریخی Antigravity محدودیت منطقه دارد؛ این نوبت دسترسی مدل آن دوباره آزمایش نشده است.

مراجع: `README.md`، `pyproject.toml`، تابع `command_for` و `LocalRuntime.submit/execute`، `FluxEngine._workflow/_context`؛ sourceهای `eb9edb97-08ec-455d-8f2c-d9f2951d1622`، `1dd15290-f41f-4e4d-8072-cc16bb63dc33`، `e172c299-c14f-4b65-8ae4-34e190cda331`.

## شواهد آزمایش JEV

در آزمون تاریخی محدود ۱۲ سناریوی اضافی، سقف شواهد ۳۰۰۰ توکن، v2 قبلی ۱۹/۴۳ و v2 بازنویسی‌شده ۲۹/۴۳ شاهد داشتند؛ پوشش ۴۴٫۲٪ به ۶۷٫۴٪ رسید. تعداد سناریوهای کامل در هر دو ۴/۱۲ بود. سقف شواهد شامل ارجاع و هشدار است و کل prompt/خروجی/history نیست. tokenizer محلی `o200k_base`، صورتحساب ارائه‌دهنده نیست. `semantic_sufficiency=unverified` باقی می‌ماند.

v2 و Skill مستقلند و به موتور محصول وصل نیستند. گزارش درصد توکن واقعی در سه نمونه، صرفاً همان نمونه‌ها را پوشش می‌دهد. این نوبت benchmark قدیمی دوباره اجرا نشده است.

مرجع: `experiments/jev_v2_rewrite_20261001/REPORT.fa.md` و `optimized_v2.py`؛ source `6fcb7dfe-879e-4d2d-b9fb-43972a02ce0f`.

## محدودیت‌های مشاهده‌شده و کار باز

1. حافظهٔ Workspace اکنون global است: tenant/project/ACL/source lifecycle ندارد، انتخاب پنج یادداشت واژگانی با سقف ۶۰۰۰ کاراکتر دارد. اصلاح UI، این محدودیت را رفع نمی‌کند.
2. خاموش‌کردن حافظه در نوبت جدید، native session قبلی را پاک نمی‌کند؛ لغو/حذف باید نشست و cache/summary متأثر را هم بررسی کند.
3. دفتر بودجهٔ legacy سقف run/روز workspace دارد؛ root/department/company مشترک و reconciliation هزینهٔ unknown هدف طراحی تازه است. CLI اشتراکی سقف دلاری API ندارد.
4. پذیرش legacy باید criterion ID و شاهد نسخه‌دار بگیرد؛ حذف blocking issues یا تطبیق با تعداد criterion مبنای کافی برای هدف سازمانی نیست.
5. canonical memory revision باید پیش از فیلتر وضعیت انتخاب شود تا tombstone نسخهٔ جدید، نسخهٔ قدیمی active را احیا نکند. این مورد از بررسی کد آزمایش به برنامهٔ آزمون اضافه شده، اصلاح نشده است.
6. باگ اصلی UI از href=/legacy بود؛ اکنون پنل پروژه و حافظه در همان رابط اضافه شده است. مسیر قدیمی پیوند مستقل دارد؛ محصول فعلی همچنان حافظهٔ سراسری دارد.

مراجع: `Workspace.retrieve`، `LocalRuntime.submit/execute`، `Repository.reserve_budget/settle_reservation`، `FluxEngine._workflow`، `optimized_v2.Index.__init__`، `docs/project-memory-ui-fix.fa.md`.

## ادامهٔ کار HEAD

اسناد دقیق در `docs/algorithms/00-head-brief.fa.md` تا `04-memory-and-rag.fa.md` قرار دارند. اولین مرحلهٔ پیشنهادی محصول، قرارداد typed criterion و مرز project memory با migration و آزمون نشت/نسخه است؛ سپس adapter Context، تصمیم محدود، بودجهٔ ancestor و پذیرش artifact-bound. ادغام فقط با معیار قبلی، آزمون و دستور مرحلهٔ اجرا انجام شود.

برای retrieval، رکوردهای `head-memory-records.json` project-scoped هستند؛ آن‌ها در DB فعلی memories تزریق نشده‌اند. برای ادامهٔ کار، اول manifest/source revision را تازه بررسی کن، سپس pack بگیر و هر candidate را با منبع اصلی تطبیق بده. قالب یادداشت/MD دستور به ارائه‌دهندهٔ مدل نیست و حدود اختیار را گسترش نمی‌دهد.

## تصحیح پاسخ خام NotebookLM

عبارت «بازیابی مفهومی» در پاسخ اولیه، دربارهٔ v2 دقیق نیست؛ نسخهٔ بررسی‌شده واژگانی است و embedding/مدل TypeSafe Jev اجرا نمی‌کند. مشکل نبود هشدار در ۲۲ سناریو به آزمون نسخهٔ قدیمی اشاره دارد؛ v2 جدید candidate/missing و unverified می‌دهد، اما کفایت معنایی همچنان تأیید نشده است. چارت چهار انسان/مدل‌های مثال، الگوی داخلی تاریخی است. شماره‌های citation فارسی پاسخ اولیه بدون metadata ساخت‌یافته به‌تنهایی گواه منشأ قابل برنامه‌نویسی نیستند؛ پرسش وایت‌پیپر در `notebooklm-grounding-check.json` شش ارجاع و پاسخ نهایی memory شانزده ارجاع native دارد. `completed` در پاسخ نهایی مدل کوتاه توضیح داده شده؛ قرارداد کد خروج صفر **و** رویداد پایانی موفق **و** پاسخ غیرخالی را لازم می‌داند.


## Source: docs/knowledge/VERIFICATION.fa.md
SHA-256: de2d0d415199890c83c14a8bc88e9d5702c4bf6056d523e7a9dc5740b8e7e775


# گزارش تحویل HEAD، RAG و اصلاح رابط Flux

> گزارش تاریخی نسخهٔ ۰٫۴؛ نتیجهٔ نصب، پیاده‌سازی و بررسی ۰٫۵ در [گزارش جاری](../algorithms/05-implementation-v0.5.fa.md) آمده است. اعداد و hashهای زیر شواهد همان تحویل قبلی‌اند.

تاریخ: ۱ اکتبر ۲۰۲۶. این گزارش نتیجهٔ همین نوبت است؛ گزارش‌های benchmark/اتصال قبلی فقط به‌عنوان منبع تاریخی استفاده شدند.

## سند و گفتگوها

وایت‌پیپر فارسی ۲۰ صفحه، نسخهٔ ۱٫۰، ۱۳ سپتامبر ۲۰۲۶ کامل استخراج و خوانده شد. متن قابل خواندن در `tmp/pdfs/whitepaper-readable.md` با اصلاح ترتیب RTL استخراج شد؛ PDF اصل تغییر نکرد. جلد بصری بررسی شد. منابع داخلی README، قراردادها، موتور قدیمی، runtime فعلی، storage و گزارش JEV بررسی شدند. سه گفتگوی «تدوین white paper دقیق Flux»، «طراحی الگوریتم RAG بهینه» و «اتصال کامل سیستم به Claude و ChatGPT» به‌صورت snapshot منتخب خوانده شدند؛ export کامل تمام گفتگوهای حساب انجام نشد.

## RAG واقعی NotebookLM

دفتر اختصاصی: [Flux HEAD | Whitepaper, Runtime and JEV | 2026-10-01](https://notebooklm.google.com/notebook/cbd54447-058f-445c-a1e3-850f15cc5eb9).

PDF و bundleهای allowlist سورس/گزارش/گفتگو وارد شدند. فایل‌های credential، `.env`، دیتابیس‌های کاربر، backupها و logهای شخصی وارد نشدند. MDهای الگوریتم و تحویل با برچسب طراحی به دفتر افزوده می‌شوند؛ شناسه و وضعیت آخر همهٔ sourceها در `notebooklm-manifest.json` ثبت می‌شود. public sharing فعال نشده است.

پرسش کنترل از PDF، **۶ ارجاع ساخت‌یافته** به متن منبع برگرداند (`notebooklm-grounding-check.json`). memory note نهایی، **۱۶ ارجاع ساخت‌یافته به چهار source** برگرداند (`notebooklm-generated-memory.json`) و Note `dd52cd81-cfe1-40ed-9e53-4fefd49172bb` با عنوان `Flux Project Memory` در دفتر ذخیره شد. خروجی اولیه/کوتاه فارسی نیز محفوظند، اما citationهای عددی فارسی‌شان در آرایهٔ native references قرار نگرفت؛ با پرسش انگلیسی provenance ساخت‌یافته تأیید شد.

`head-memory.fa.md` جمع‌بندی فارسی بازبینی‌شده است؛ ادعای ۱۰۰٪ پاسخ اولیه حذف، چارت داخلی از چارت مشتری جدا، واژگانی‌بودن JEV و تفاوت آزمون قدیم/جدید تصحیح شد. گزارش تغییرات نمونه و شواهد داخلی به معنی تأیید مستقل تمام خروجی‌های مدل نیست.

## RAG محلی برای ادامهٔ کار

Skill مستقل `project-evidence-rag-v2` با پروژهٔ `alacrity-flux`، task سه‌معیاره و هفت رکورد حافظه اجرا شد؛ تماس مدل آن **صفر** است. سقف ۳۰۰۰ توکن برای worker evidence با `o200k_base`، framing/output/history جداست. نتیجه در `head-evidence-pack.json`؛ عدد آخر در همان فایل مرجع است، نه اندازهٔ اولیهٔ pack.

corpus محلی از snapshot allowlist در `retrieval-corpus` ساخته شد. query/task، خروجی‌های مدل، packهای تولیدشده، source bundleهای تکراری و gold آزمایش وارد index آن نشدند تا متن خود سؤال شاهد پاسخ محسوب نشود. `retrieval-corpus-manifest.json` hash هر فایل و ریشهٔ اصلی را برای provenance نگه می‌دارد. assessmentهای سه معیار candidate هستند و semantic sufficiency به‌درستی unverified است؛ تابع تست در pack، اجرای آن نیست. این pack ابزار پژوهش HEAD است و به Workspace/LocalRuntime تزریق نشده است.

## الگوریتم‌ها

چهار مشخصات فارسی با قرارداد داده، pseudocode، ماشین حالت/رزرو/تصمیم/lifecycle، failure handling، مثال و برنامهٔ آزمون نوشته شدند؛ `00-head-brief.fa.md` نقشهٔ خواندن و provenance است. یک بازبینی مستقل، ناسازگاری enum/نوع revision، مسیر تسویهٔ دوباره، بررسی ناقص pack تازه، gate quarantine و نگاشت revision منبع را کشف کرد و در MDها اصلاح شدند. بلوک‌های Python از نظر syntax و JSON مثال‌ها و پیوندهای محلی بررسی می‌شوند؛ این کار اجرای runtime pseudocode یا benchmark الگوریتم هدف نیست.

در بررسی کوچک synthetic بدون مدل و DB، نقص revision آزمایش JEV بازتولید شد: rev1 active می‌تواند پس از rev2 obsolete با همان ID دوباره eligible شود. مشخصات lifecycle مقصد روش canonical revision/tombstone را دارد؛ کد آزمایش در این نوبت تغییر نکرد.

## باگ «پروژه‌ها و حافظه»

علت اولیه `href=/legacy` در `local.html` بود. اکنون دکمه پنل مدیریت همان رابط v0.4 را باز می‌کند؛ پروژه و یادداشت از APIهای موجود مدیریت می‌شوند و legacy پیوند مستقل دارد. انتخاب پروژه از NotebookLM به گفتگوی تازهٔ Codex با پوشهٔ همان پروژه می‌رود. بودجه و تسک قدیمی با edit/archive پروژه حفظ می‌شوند. حافظه همچنان global است و UI آن را بیان می‌کند؛ migration tenant/project/ACL انجام نشده است.

بررسی‌ها:

- `python -m pytest -q`: **۷۳ passed**؛ تماس مدل در تست‌های معمول صفر.
- syntax هر دو فایل `local.js` و `project-memory.js` گذشت.
- smoke مرورگر با fixture مستقل در عرض‌های ۳۷۵،۷۶۸،۱۰۲۴،۱۴۴۰، بدون خطای JavaScript؛ CRUD پروژه/حافظه، حفظ پیش‌نویس، invalid path، متن ناامن، archive و قفل هنگام اجرا بررسی شدند.
- ۲۲ تست هدفمند زیرکار در مجموعهٔ ۷۳تایی نیز پوشش دارند؛ این شمارها با هم جمع نمی‌شوند.
- EXE با PyInstaller 6.22.2 ساخته شد. هش build: `ba29e0309e139128e7ec93e98651abfbd9565f6d929166342b3be2ac48c9cee5`.
- `tools/project_memory_packaged_smoke.py` روی EXE با DB موقت اجرا شد: محتوای سه فایل UI با سورس byte-for-byte برابر، صفحهٔ فعلی و legacy، ایجاد/ویرایش پروژه و ایجاد/خواندن/حذف یادداشت موفق؛ مدل و دیتابیس کاربر استفاده نشدند. نتیجه در `project-memory-packaged-check.json`.
- installer اجرا شد؛ `C:\Users\xio\AppData\Local\Programs\Flux\Flux.exe` با build byte-for-byte برابر است. نسخهٔ قبلی executable توسط installer backup شد. فرایند Flux کاربر هنگام نصب باز نبود و هیچ نشست کاربر متوقف نشد.

source PDF/MDها و یادداشت حافظه باقی‌اند. مدل‌های جدید، مسیریابی خودکار JEV، حافظهٔ سازمانی چندمشتری، policy gate ابزار و دفتر بودجهٔ ancestor هنوز طراحی آینده‌اند؛ رفع باگ رابط آن‌ها را پیاده‌سازی‌شده نمی‌کند.
