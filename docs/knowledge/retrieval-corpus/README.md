# Flux ۰٫۴ — فضای کار دستیارها و منابع شما

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

«پروژه‌ها و حافظه» اکنون پنل مدیریت را داخل همین رابط باز می‌کند؛ افزودن/ویرایش/بایگانی پروژه و مدیریت یادداشت‌ها از همان ذخیره‌سازی قبلی انجام می‌شود. انتخاب پروژه گفتگوی تازه با پوشهٔ آن می‌سازد؛ اگر دستیار NotebookLM باشد، برای کار روی فایل‌های پروژه به Codex تغییر می‌کند. حافظهٔ فعلی میان پروژه‌ها مشترک است. [شرح اصلاح و بررسی](docs/project-memory-ui-fix.fa.md).

## مشخصات سازمانی و حافظهٔ HEAD

[دفتر HEAD و چهار الگوریتم](docs/algorithms/00-head-brief.fa.md) مقصد سازمانی Flux، مدیریت توکن، تصمیم‌گیری و حافظه/RAG را با قرارداد و شبه‌کد دقیق شرح می‌دهد. این مشخصات به runtime فعلی ادغام نشده‌اند. [حافظهٔ بازبینی‌شدهٔ پروژه](docs/knowledge/head-memory.fa.md)، [دفتر NotebookLM](https://notebooklm.google.com/notebook/cbd54447-058f-445c-a1e3-850f15cc5eb9) و [گزارش تحویل](docs/knowledge/VERIFICATION.fa.md) برای ادامهٔ کار موجودند.

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
