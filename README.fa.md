# Flux ۰٫۷٫۰ — موتور مهندسی عاملی (Tree-sitter RepoMap، Plan/Act، خوداصلاحی خودکار)، ارکستراسیون موازی ایزوله و مدل‌های رایگان/محلی

**Author: [XioDr](https://github.com/XioDr)** · Alacrity · **License: [Apache-2.0](LICENSE)**

[اتصال وب با فایل نشست](docs/web-session-connections.fa.md): گزینه‌های Gemini Web و DeepSeek Web اضافه شده‌اند. فایل نشست را محلی وارد کنید و آزمون دریافت پاسخ را اجرا کنید. سلامت تب‌های واردشدهٔ Codex جداگانه بررسی شده است؛ فعال‌سازی در Flux هنوز به فایل نشست کاربر نیاز دارد.

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

---

## قابلیت‌های نسخهٔ متنباز ۰٫۶٫۰ (اجرای موازی و ارکستراسیون سازمانی)

صفحهٔ اختصاصی **`/attention`** و واسط خط فرمان **`flux daemon` / `flux ctl`** شش چالش اصلی اجرای موازی عامل‌های کدنویسی را پوشش می‌دهند:

1. **انزوای کامل محیط فراتر از Git Worktree (`src/flux/parallel/worktrees.py`)**:
   - تخصیص و تزریق خودکار پورت‌های آزاد و یکتا (`PORT`, `API_PORT`, `VITE_PORT`, `E2E_PORT`) به هر Worktree بدون تداخل سرورهای توسعه و تست‌های E2E.
   - اشتراک‌گذاری وابستگی‌های سنگین (`node_modules`, `.venv`, `.pnpm-store`, `.gradle`, `.next/cache`) از طریق پیوند سیستمی (Junction در ویندوز بدون نیاز به دسترسی Admin و Symlink در لینوکس/مک) به‌شرط یکسان بودن بایت‌به‌بایت Lockfile، به همراه کپی امن فایل‌های `.env`.
   - پایگاه‌دادهٔ ایزولهٔ فوری: دایرکتوری داده و SQLite اختصاصی (`DATABASE_URL`) و `COMPOSE_PROJECT_NAME` یکتا برای هر محیط، به‌همراه پشتیبانی اختیاری از کانتینر موقت PostgreSQL روی `tmpfs` در صورت فعال بودن Docker.
2. **پیشگیری فعالانه از تعارض کد پیش از Merge (`src/flux/parallel/overlap.py`)**:
   - تحلیل چهارسطحی همپوشانی (`conflict` با `git merge-tree` بدون دستکاری ایندکس واقعی، `symbol` در سطح توابع/کلاس‌ها با AST، `file` و `scope`).
   - تعویق خودکار (`deferred`) تسک‌های همپوشان در حین اجرای عامل دیگر و ازسرگیری خودکار به‌محض رفع تداخل یا آزاد شدن ظرفیت موازی.
3. **حافظهٔ مشترک و ماندگار میان عامل‌ها بر پایهٔ گیت (`src/flux/parallel/wiki.py`)**:
   - ذخیره‌سازی اتمیک درس‌آموخته‌ها، استانداردهای مخزن و ریشهٔ باگ‌ها روی مرجع اختصاصی `refs/flux/memory` بدون آلوده کردن شاخه‌های کد یا ایجاد تعارض Merge.
   - استخراج خودکار تگ‌های `<flux-memory>` از خروجی عامل‌ها، تأیید انسانی در صندوق توجه، و تزریق خودکار نکات سنجاق‌شده و مرتبط به پرامپت همهٔ عامل‌های موازی و جلسات بعدی.
4. **صندوق هوشمند جلب توجه و فصل‌بندی تغییرات (`src/flux/parallel/attention.py`, `chapters.py`)**:
   - صف اولویت‌بندی‌شده در `/attention`: عامل‌های متوقف‌شده برای تأیید دسترسی یا سؤال (`P0 blocked`) در بالاترین نقطهٔ بورد قرار می‌گیرند؛ پشتیبانی از میانبرهای کیبورد (`j/k`, `Enter`, `o`, `d`, `a`, `r`, `1-9`)، پاسخ سریع درجا، پرش مستقیم به پرامپت گفتگو، اعلان وب و وب‌هوک موبایل (`FLUX_NOTIFY_URL`).
   - **Diff Chapters**: دسته‌بندی تغییرات بزرگ به فصل‌های منطقی (وابستگی‌ها، داده/اسکیما، قراردادها/API، پیاده‌سازی هر ماژول، آزمون‌ها، مستندات) همراه با سطح ریسک.
5. **پایپلاین‌های دارای وابستگی ساختاریافته (`src/flux/parallel/pipelines.py`)**:
   - اجرای گراف وابستگی غیرمدور (DAG)؛ هر گام در Worktree ایزولهٔ خود اجرا شده، پس از پایان کار با دروازه‌های بیلد/تست (`gates`) سنجیده می‌شود (همراه با تلاش مجدد خودکار در صورت خطای تست) و گام‌های وابسته مستقیماً از کامیتِ تست‌پاس‌کردهٔ گام قبل منشعب یا ادغام می‌شوند. شامل ارکستراتور هوشمند (`plan`) برای شکستن هدف کلان به گام‌های DAG.
6. **معماری دِمون بدون سر (Headless Daemon) و مجوز Apache-2.0 (`src/flux/cli.py`, `ctl.py`, `LICENSE`)**:
   - اجرای مستقل سرور روی لینوکس، ویندوز، مک و CI با پشتیبانی از TCP، سوکت یونیکس (`--uds`)، احراز هویت توکنی (`--token` / `FLUX_API_TOKEN`)، جریان رخداد زنده (SSE و WebSocket) و کلاینت ترمینال/بورد زنده (`flux ctl top`, `flux ctl watch`, `flux ctl attention`, `flux ctl worktree`, `flux ctl pipeline`, `flux ctl memory`).

```powershell
# اجرای دمون بدون مرورگر (مناسب سرور و CI)
flux daemon --host 127.0.0.1 --port 8040 --max-parallel 3

# مشاهدهٔ بورد زنده و صندوق توجه در ترمینال
flux ctl status
flux ctl attention
flux ctl top
```

---

## قابلیت‌های نسخهٔ ۰٫۷٫۰ — مهندسی عاملی پیشرفته (Agentic Engineering) و مدل‌های رایگان/محلی

بستهٔ `src/flux/agentic/` و مسیرهای `/api/agentic/*` شش قابلیت کلیدی مهندسی نرم‌افزار عاملی را روی هر مدل متصل (از جمله **Gemini 3.8 Flash**، **Ollama محلی**، **Groq**، **OpenRouter `:free`**، **Claude Code** و **Codex**) فعال می‌کنند:

1. **نقشهٔ هوشمند مخزن با Tree-sitter و AST (`src/flux/agentic/repomap.py`)**:
   - تحلیل ساختاری ۱۴ زبان برنامه‌نویسی با `tree-sitter` و `ast`، استخراج کلاس‌ها، امضای دقیق متدها/توابع و یال‌های وابستگی درون‌مخزنی، رتبه‌بندی با PageRank + هم‌پوشانی واژگانی پرامپت و کش مبتنی بر `(mtime_ns, size)`.
   - کاهش بیش از **۹۵٪** توکن‌های ورودی نسبت به ارسال خام فایل‌های مخزن و حذف توهم در ارجاع به توابع و ماژول‌ها.
2. **معماری دوفازی تفکر و اجرا — Plan vs. Act (`src/flux/agentic/plan_act.py`)**:
   - **Plan Mode (فقط-خواندنی قطعی):** تحلیل نیازمندی‌ها، سناریوهای مرزی و فایل‌های هدف همراه با تضمین عدم تغییر فایل‌ها (بازگردانی خودکار هر تغییر ناخواسته توسط Shadow Checkpoint).
   - **Act Mode:** تأیید یک‌کلیکی طرح در رابط وب یا API (`/api/agentic/plans/{id}/execute`) و اجرای گام‌به‌گام طرح معماری مصوب.
3. **حلقهٔ بازخورد و خوداصلاحی خودکار کامپایلر/لینتر/تست (`src/flux/agentic/feedback.py`)**:
   - اجرای خودکار بررسی سینتکس (`ast.parse`, `py_compile`, `node --check`)، لینتر (`ruff`, `eslint`)، تایپ‌چکر (`mypy`, `tsc --noEmit`) و تست‌های مرتبط پروژه (`pytest`) بلافاصله پس از ویرایش فایل‌ها و بازگرداندن Stack Trace به مدل جهت اصلاح خودکار پیش از تحویل به کاربر.
4. **ویرایش جراحی فایل‌ها به جای بازنویسی کامل (`src/flux/agentic/surgical.py`)**:
   - پشتیبانی از `replace_in_file`، بلوک‌های `<flux-edit>` (`<<<<<<< SEARCH ... ======= ... >>>>>>> REPLACE`) و اعمال امن `Unified Diff` درون حصار امنیتی مسیر پروژه (Path Jail)؛ بیش از **۵ تا ۵۰ برابر** سریع‌تر در تولید خروجی مدل و بدون حذف ناخواستهٔ کدهای اطراف.
5. **نقطه‌های بازگشت مخفی با Shadow Git (`src/flux/agentic/checkpoints.py`)**:
   - ثبت خودکار Snapshot در مخزن مخفی جداگانه (`~/.flux/shadow-git`) پیش و پس از هر اقدام عامل، **بدون کوچک‌ترین دستکاری یا کامیت اضافی در `.git` اصلی پروژه** و امکان بازگشت یک‌کلیکی (`Rollback`).
6. **سنجاق استانداردها و حافظهٔ خطاهای مخزن — Context Sentinel (`src/flux/agentic/sentinel.py`)**:
   - تزریق فشردهٔ قوانین پروژه (`AGENTS.md`, `CLAUDE.md`, `.cursorrules`, `.flux/rules.md`) در هر نوبت برای جلوگیری از فراموشی قوانین (Context Drift) و ثبت پایدار خطاهای کامپایلر/تست در SQLite (`sentinel_lessons`) تا مدل یک خطا را دوباره تکرار نکند.
7. **اتصال مستقیم به مدل‌های رایگان و محلی (`src/flux/local_agents/free_apis.py`)**:
   - پشتیبانی بومی از **Ollama** (بدون کلید API روی سیستم محلی)، **Groq**، **OpenRouter** (کشف خودکار مدل‌های `:free`)، **Together AI** و **Google Gemini API**.

```powershell
# دستورات خط فرمان قابلیت‌های ۰٫۷٫۰
python -m flux serve --port 8000
flux ctl repomap --cwd . --prompt "auth middleware"
flux ctl verify --cwd .
flux ctl checkpoint list --cwd .
```

