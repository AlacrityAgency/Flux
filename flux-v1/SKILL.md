---
name: flux-v1
description: "Economic reasoning, algorithmic verification, and tiered escalation optimized for Gemini 3.8 Flash (Low/High thinking) with local AST sandbox, compact contracts, and deterministic Laya policy guard."
---

# FLux v1 — Gemini 3.8 Flash Edition

این اسکیل گردش‌کار بهینه‌سازی‌شده برای **Gemini 3.8 Flash** را پیاده‌سازی می‌کند. مدل با استفاده از بودجه تفکر چندسطحی (Low Thinking برای حل سریع و اقتصادی $\to$ High Thinking برای مسائل پیچیده و استدلالی)، فرمت فشرده کدهای پایتون، سندباکس AST محلی و گارد قطعی تصمیم‌گیری Laya هدایت می‌شود.

## ۱. نردبان ارتقای Gemini 3.8 Flash (Escalation Ladder)

برای دستیابی به حداکثر صرفه‌جویی در هزینه و زمان توکن، برنامه اجرایی به سه سطح تفکر تقسیم می‌شود:

| پله (Opportunity) | مدل و پیکربندی | سطح تفکر (Thinking Level) | هدف عملیاتی |
|---|---|---|---|
| **پله ۱ (Tier 1)** | `gemini-3.8-flash` | `low` (پاسخ سریع، اقتصادی) | حل مسائل سرراست، اعتبارسنجی سریع و استخراج بدون سربار |
| **پله ۲ (Tier 2)** | `gemini-3.8-flash` | `high` (تفکر عمیق و استدلالی) | حل مسائل پیچیده ترکیبیاتی، اثبات فرمول‌ها و بازسازی خطاهای ورکر |
| **پله ۳ (Tier 3)** | `gemini-3.8-flash` | `high` + بازخورد خطای چکر | تلاش نهایی با کانتکست خطای ایزوله‌شده ورکر محلی (حداکثر ۲۴۰ کاراکتر) |

## ۲. قرارداد فشرده داده و خروجی (Compact Contract)

درخواست‌های محاسباتی، شبیه‌سازی و منطقی به صورت `TASK` به همراه داده‌های ساختاریافته در `FACTS` ارائه می‌شوند. مدل ملزم است خروجی را **تنها** در یک ساختار JSON به فرمت زیر برگرداند:

```json
{
  "refs": ["کلیدهای سطح اول facts"],
  "code": "def solve(facts): ...\ndef check(answer, facts): ..."
}
```

### الزامات قرارداد:
1. `refs`: باید دقیقاً و منحصراً برابر با کلیدهای سطح اول شیء `facts` باشد (بدون کلیدهای تو در تو).
2. `solve(facts)`: تابع اصلی تولید پاسخ ساختاریافته JSON.
3. `check(answer, facts)`: تابع مستقل ارزیابی که در صورت صحت پاسخ مقدار `True` و در غیر این صورت `False` برمی‌گرداند (استفاده از فرمول و اشتقاق مستقل، بدون صدا زدن مستقیم `solve`).
4. **عدم تکرار داده:** مدل نباید دیتاست مسئله را درون متن کد کپی کند؛ تمام داده‌ها از متغیر `facts` خوانده می‌شوند.

## ۳. بازرسی امنیتی AST و ورکر مقید پایتون

پیش از هرگونه اجرای کد، خروجی مدل از فیلترهای زیر عبور می‌کند:
1. **تجزیه انتزاعی نحو (AST Audit):**
   - ایمپورت‌های غیرمجاز (`os`, `sys`, `subprocess`, `shutil`, `socket`) ممنوع و مسدود می‌شوند.
   - ماژول‌های مجاز استاندارد محاسباتی: `math`, `fractions`, `itertools`, `functools`, `collections`, `heapq`, `bisect`, `decimal`, `operator`, `statistics`.
   - توابع خطرناک (`eval`, `exec`, `open`, `compile`, `__import__`) ممنوع هستند.
   - دسترسی به ویژگی‌های خصوصی و بازتابی (`__class__`, `__subclasses__`, `__dict__`, `f_globals`) ممنوع است.
2. **ورکر مقید در ساب‌پراسس:**
   - کد در یک پردازش فرزند ایزوله (`python -I -S compact_worker.py`) با سقف زمانی سخت ۴ ثانیه اجرا می‌شود.
   - پاسخ با کدگذاری قوی عددی (`Fraction`, `Decimal`, `int`) به صورت یکپارچه مقایسه می‌شود.

## ۴. سیاست تصمیم‌گیری Laya و گارد قطعی

در ابتدا و انتهای هر تلاش، وضعیت بررسی می‌شود:
- **Laya FRONT:** عمق راستی‌آزمایی (`light` / `medium` / `full`) را بر اساس کف ریسک وظیفه انتخاب می‌کند.
- **Laya END و گارد قطعی:**
  ```python
  def guard(choice, passed, attempt):
      if not passed:
          return 'escalate' if attempt < 2 else 'stop'
      return 'escalate' if choice == 'escalate' and attempt < 2 else 'accept'
  ```
- **اصل عدم پذیرش کاذب:** حتی اگر شبکه عصبی Laya یا مدل اطمینان کاذب گزارش کند، در صورتی که ورکر محلی یا چکر مستقل شکست بخورد، گارد قطعی بلافاصله ارتقا یا توقف با شکست را تحمیل می‌کند.

## ۵. دستورات اجرایی

```bash
# فراخوانی یکپارچه حل‌کننده با مدل Gemini 3.8 Flash
python d:/project/Alacrity/Flux/flux-v1/scripts/call_model_gemini.py --model gemini-3.8-flash --effort low --prompt-file prompt.txt --receipt receipt.json

# اعتبارسنجی ساختار برنامه با AST
python d:/project/Alacrity/Flux/flux-v1/scripts/validate_program.py --candidate candidate.json --facts facts.json
```
