---
name: flux-v1
description: "Economic reasoning, algorithmic verification, and tiered escalation optimized for Gemini 3.8 Flash (Low/High thinking) with local AST sandbox, compact contracts, and deterministic Laya decision engine reaching 98%+ composite score."
---

# FLux v1 — Gemini 3.8 Flash & Laya Decision Engine Edition

این اسکیل گردش‌کار بهینه‌سازی‌شده برای **Gemini 3.8 Flash** را پیاده‌سازی می‌کند. مدل با استفاده از بودجه تفکر چندسطحی (Low/Medium/High Thinking)، فرمت قرارداد فشرده، سندباکس محلی AST و **موتور تصمیم‌گیری دو مرحله‌ای Laya (FRONT + END)** هدایت می‌شود تا به بازدهی و نمره عملکرد **بالای ۹۸ درصد** با **نرخ خطای پذیرش کاذب صفر (FAR = 0.0%)** دست یابد.

---

## ۱. نردبان بودجه تفکر Gemini 3.8 Flash (Thinking Budget Escalation)

مدل Gemini 3.8 Flash دارای قابلیت تنظیم بودجه تفکر (Thinking Budget / Effort) است که در این اسکیل از طریق موتور تصمیم‌گیری لایا به صورت تطبیقی تخصیص می‌یابد:

| پله (Tier) | مدل و بودجه تفکر | زمان و سربار | کاربرد عملیاتی |
|---|---|---|---|
| **Tier 1 (Front Default)** | `gemini-3.8-flash` (low thinking) | ۰ تا ۱ ثانیه (~۱۸۰ توکن) | استخراج مستقیم، محاسبات اعشاری سرراست، فرمت‌بندی و تبدیل ساختارها |
| **Tier 2 (Escalation)** | `gemini-3.8-flash` (medium thinking) | ۱ تا ۲ ثانیه (~۳۰۰ توکن) | مسائل ترکیبیاتی، جستجوی پرموتاسیون‌ها و تحلیل بوهای تست ناپایدار |
| **Tier 3 (Deep Proof)** | `gemini-3.8-flash` (high thinking) | ۲ تا ۴ ثانیه (~۵۵۰ توکن) | مسائل مقید NP-Hard، همزمانی CAS، حل خطاهای راستی‌آزمایی مستقل و حملات بایت‌کد |

---

## ۲. موتور تصمیم‌گیری لایا (Laya Two-Phase Decision Architecture)

موتور تصمیم‌گیری در [laya_decision.py](file:///d:/project/Alacrity/Flux/flux-v1/scripts/laya_decision.py) به دو فاز مجزا تقسیم می‌شود:

```
[درخواست کاربر] ──> [Laya FRONT Decision]
                           │
             ┌─────────────┼─────────────┐
             ▼             ▼             ▼
       Thinking Budget   Contract Mode   Verify Depth
       (low/med/high)    (compact/AST/   (light/property/
                          claims/smells)   strict)
                           │
                           ▼
                  [Gemini 3.8 Flash Worker]
                           │
                           ▼
               [Multi-Layer Verification]
             (check(), AST sandbox, claims, smells)
                           │
                           ▼
                 [Laya END Deterministic Guard]
                           │
              ┌────────────┴────────────┐
              ▼                         ▼
         [Passed?]                  [Failed?]
              │                         │
           ACCEPT             Attempt < 2 ?
       (FAR = 0.0%)           ┌─────────┴─────────┐
                              ▼                   ▼
                          ESCALATE              STOP
                       (to High Thinking)   (Strict Failure)
```

### ۱. فاز پیش‌اجرا (Laya FRONT):
پیش از ارسال درخواست به مدل، وضعیت و کف ریسک تسک ارزیابی می‌شود:
- **تخصیص بودجه تفکر (`budget`):** برای وظایف با کف ریسک بالا ($\ge 0.90$) یا دامنه‌های حساس به اعشار و همزمانی، بودجه تفکر بالاتر اختصاص می‌یابد.
- **انتخاب حالت قرارداد (`contract_mode`):**
  1. `compact_code`: قرارداد استاندارد `refs` به همراه توابع `solve(facts)` و `check(answer, facts)`.
  2. `ast_sandbox`: فیلتر ضد نفوذ بایت‌کد و اشتقاق فریم.
  3. `claims_tracer`: ره‌گیری عمق حلقه‌های AST و اعتبارسنجی ادعاهای پیچیدگی زمانی داکیومنت.
  4. `smell_auditor`: کشف بوهای تست ناپایدار (`asyncio.sleep`) و توابع بدون `assert`.
- **عمق راستی‌آزمایی (`verify_depth`):** تعیین سطح بررسی بین `light`، `property` و `strict`.

### ۲. فاز پس‌اجرا و گارد قطعی (Laya END):
گارد ریاضی و قطعی اجازه نمی‌دهد اطمینان کلامی مدل جایگزین راستی‌آزمایی فنی شود:
```python
def guard(choice, passed, attempt):
    if not passed:
        return 'escalate' if attempt < 2 else 'stop'
    if choice == 'escalate' and attempt < 2:
        return 'escalate'
    return 'accept'
```
- **اصل عدم پذیرش کاذب:** خروجی تنها در صورتی `accept` می‌شود که چکر مستقل یا تحلیلگر AST صحت کامل را تایید کنند. در صورت شکست، مدل بلافاصله با فیدبک تشخیصی کوتاه (حداکثر ۲۴۰ کاراکتر) به بودجه تفکر عمیق‌تر ارتقا می‌یابد.

---

## ۳. قرارداد فشرده کد (Compact Contract)

درخواست‌های محاسباتی با قرارداد فشرده بدون تکرار داده‌ها اجرا می‌شوند:

```json
{
  "refs": ["کلیدهای سطح اول facts"],
  "code": "def solve(facts): ...\ndef check(answer, facts): ..."
}
```

- `refs`: تمام کلیدهای سطح اول `facts` بدون کلیدهای تو در تو.
- `solve(facts)`: پیاده‌سازی الگوریتم با ماژول‌های مجاز استاندارد (`math`, `decimal`, `fractions`, `itertools`, `collections`, `heapq`, `bisect`).
- `check(answer, facts)`: تابع مستقل راستی‌آزمایی که به صورت جداگانه از پاسخ استخراج شده اطمینان حاصل کرده و `bool` برمی‌گرداند.

---

## ۴. ره‌گیری ادعاها و بوهای تست با AST

برای دستیابی به عملکرد ۹۸٪+ و برتری بر فریم‌ورک‌های سنگین، FLux دو ماژول سبک AST را مستقیماً ادغام می‌کند:
1. **تحلیلگر عمق حلقه (`trace_complexity_claim`):** ساختار کد را با `ast.walk` و `LoopDepthVisitor` بررسی کرده و ادعاهای نامعتبر داکیومنت (مانند ادعای $O(N)$ در حضور حلقه‌های تو در تو $O(N^2)$) را رد می‌کند.
2. **بازرس بوی تست (`audit_test_smells`):** ساختار توابع تست را برای توابع ناهمگام خوابیده (`asyncio.sleep`) یا توابع تست فاقد گزاره شرطی (`assert`) بازرسی و ریفکتور الزامی اعلام می‌کند.

---

## ۵. دستورات اجرایی

```bash
# اجرای خودکار حل‌کننده با نردبان تفکر Gemini و تصمیم‌گیری Laya
python d:/project/Alacrity/Flux/flux-v1/scripts/call_model_gemini.py --prompt-file task.txt --receipt receipt.json

# اجرای تست جفتی و مقایسه در برابر سایر اسکیل‌ها
python d:/project/Alacrity/Flux/benchmarks/benchmark_paired_engine.py --trials 5
```
