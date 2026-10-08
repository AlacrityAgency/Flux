# الگوریتم حافظه و RAG و ذهن مستقل پروژه در Flux

نسخهٔ مشخصات: `1.0` · تاریخ بررسی: ۱ اکتبر ۲۰۲۶ · پروژهٔ پایدار: `alacrity-flux`

این سند قرارداد طراحی برای لایهٔ دانش Flux است. وظیفهٔ این لایه، نگهداری وضعیت معتبر پروژه و ساخت بستهٔ شواهد مجاز برای هر کار است؛ ادعای مدل را به حقیقت یا مجوز تبدیل نمی‌کند. Head درخواست دانش را می‌سازد و شکاف‌ها را پیگیری می‌کند؛ موتور نرم‌افزاری، هویت، نسخه، دسترسی، بودجه و تغییر وضعیت را اعمال می‌کند. سیاست و پذیرش نهایی سازمان در اختیار انسان باقی می‌ماند.

مبنای محصول، وایت‌پیپر فارسی نسخهٔ ۱٫۰، به‌ویژه صفحات ۸ تا ۱۲ و ۱۷ است. جدول وضعیت فعلی وایت‌پیپر مربوط به دموی ۰٫۲ در ۱۳ سپتامبر است؛ برای وضعیت فعلی، سورس و README نسخهٔ ۰٫۴ در همین بررسی مرجع‌اند. متن سند، فایل واردشده و پاسخ NotebookLM دادهٔ مرجع هستند؛ دستور کاربر و سیاست ثبت‌شده را تغییر نمی‌دهند.

## ۱. سه وضعیت متفاوت که باید قابل تشخیص بمانند

| سطح | آنچه اکنون وجود دارد | حدود آن |
|---|---|---|
| پیاده‌سازی دموی ۰٫۴ | یادداشت محلی SQLite، `enabled`، شمارهٔ revision، جست‌وجوی واژگانی؛ نشست CLI واقعی؛ انتخاب دفتر NotebookLM و نمایش references | حافظهٔ سازمانی با tenant/ACL و چرخهٔ اعتبار ندارد؛ بستهٔ شواهد به معیار پذیرش متصل نیست |
| آزمایش مستقل | `experiments/jev_v2_rewrite_20261001/optimized_v2.py` و Skill محلی `project-evidence-rag-v2` | selector محلی برای شواهد؛ نه TypeSafe Jev، نه فراخوان مدل در مسیر انتخاب، نه اتصال به runtime Flux |
| مقصد این سند | سرویس مستقل JEV برای ذهن پروژه، رجیستری منبع/حافظه، retrieval دارای مجوز، اعتبارسنجی کفایت و invalidation | مشخصات پیشنهادی؛ پیاده‌سازی، migration دیتابیس و استقرار آن در این کار انجام نمی‌شود |

نام **JEV** در این سند نام منطقی سرویس پیشنهادی دانش پروژه است. نام **JEVS v2** به selector آزمایشی موجود اشاره می‌کند. از یکسان بودن نام‌ها نباید یکسان بودن محصول یا اجرای TypeSafe Jev را نتیجه گرفت.

### ۱.۱. مسیر فعلی و ایرادهای مشاهده‌شده

| محل واقعی | رفتار مشاهده‌شده در سورس | فاصله با مقصد |
|---|---|---|
| `src/flux/storage/workspace.py::Workspace.__init__` | جدول `memories` فقط `id/title/content/enabled/revision/created_at/updated_at` دارد | tenant، بخش، پروژه، صاحب دانش، شاهد، ACL و وضعیت اعتبار ثبت نمی‌شوند |
| `Workspace.save_memory` | revision افزایش می‌یابد ولی همان ردیف بازنویسی می‌شود | نسخهٔ قبلی، علت تغییر، پذیرش متصل به hash و lineage نگهداری نمی‌شوند |
| `Workspace.retrieve` | روی تمام یادداشت‌های enabled، هم‌پوشانی واژه‌های objective را می‌سنجد؛ حداکثر ۵ یادداشت | انتخاب پروژه و دسترسی پیش از رتبه‌بندی ندارد؛ criteria وارد query نمی‌شود |
| `Workspace.retrieve` | `limit=6000` طول نویسهٔ `content` است؛ از ابتدای متن برش می‌زند | سقف توکن نیست؛ عنوان/ref/revision و framing را نمی‌شمارد؛ شرط یا استثنای انتهای متن ممکن است حذف شود |
| `Workspace.delete_memory` | `DELETE` مستقیم روی ردیف | tombstone، سیاست نگهداری، وابستگی خلاصه و ابطال زمینه ندارد |
| `src/flux/local_agents/runtime.py::LocalRuntime.submit` | `workspace.retrieve(spec.prompt)`؛ جدول `local_chats` پروژه/tenant ندارد | `cwd` به‌تنهایی مرز دسترسی یا هویت پروژه نیست |
| `LocalRuntime.execute` | یادداشت‌ها را در preface به‌عنوان reference data قرار می‌دهد | هشدار متنی مفید است، اما جای کنترل نرم‌افزاری مجوز و صحت شاهد را نمی‌گیرد |
| `LocalRuntime.execute`، شاخهٔ `notebooklm` | prompt را دوباره از متن کاربر می‌سازد و preface/یادداشت‌های انتخاب‌شده را کنار می‌گذارد | `use_memory` در این شاخه، منبع پاسخ دفتر را عوض نمی‌کند؛ حافظهٔ محلی به پاسخ NotebookLM متصل نیست |
| `src/flux/api/app.py`، مسیر `/runs` و `run_project_task` | مسیر legacy هم `workspace.retrieve(objective)` را بدون scope فراخوانی می‌کند | داشتن `project_id` در task به‌تنهایی retrieval را جدا نمی‌کند |
| `LocalRuntime.execute` و `command_for` | نشست provider با session/conversation ID ادامه می‌یابد | خاموش کردن `use_memory` فقط retrieval تازه را متوقف می‌کند؛ یادداشت تزریق‌شده در نوبت قبلی از نشست provider پاک نمی‌شود |

این‌ها یافتهٔ خواندن سورس‌اند. این سند نشت واقعی داده یا شکست امنیتی در اجرای مشتری را گزارش نمی‌کند؛ کنترل‌های لازم در مدل داده و مسیر کد فعلی دیده نمی‌شوند. هیچ فایل credential یا دیتابیس عملیاتی برای این بررسی خوانده نشده است.

## ۲. نقش ذهن مستقل پروژه

ذهن پروژه یک مدل همیشه‌روشن یا خلاصهٔ طولانی کل گفتگو نیست. مجموعه‌ای نسخه‌دار از **هدف تثبیت‌شده، وضعیت کارها، تصمیم‌های معتبر، دانش تأییدشده، منابع، تعارض‌ها و پرسش‌های باز** است. خارج از context مدل نگهداری می‌شود و پس از قطع نشست قابل بازسازی است.

تقسیم مسئولیت مقصد:

1. **Flux orchestration:** قرارداد کار، سلسله‌مراتب، صف، بودجهٔ مصرف، مجوز اقدام و پذیرش خروجی را اداره می‌کند.
2. **JEV project mind:** ثبت منابع و نسخه‌ها، حافظهٔ پیشنهادی/معتبر، رجیستری تعارض و بستهٔ شواهد را اداره می‌کند.
3. **retrieval adapter:** به منابع مجاز، index واژگانی و در صورت ارزیابی موفق به index معنایی دسترسی می‌دهد. adapter حق ایجاد مجوز یا تغییر معیار ندارد.
4. **NotebookLM:** دفتر پژوهش و مرور منابع پروژه است. پاسخ و referenceهایش ورودی پیشنهاد دانش‌اند و باید به snapshot منبع اصلی قابل بررسی متصل شوند.
5. **model gateway:** فقط بستهٔ مجاز همان نوبت را به مقصد پردازش مجاز می‌فرستد و مصرف واقعی را گزارش می‌کند.

JEV می‌تواند به‌صورت سرویس یا ماژول مستقل کار کند؛ قرارداد API و داده ثابت می‌ماند. انتخاب فناوری index و پایگاه داده تصمیم مرحلهٔ پیاده‌سازی است. الزام اصلی، ذخیرهٔ بادوام، transaction تغییر اعتبار، کنترل مجوز و قابلیت بازتولید است؛ افزودن embedding به‌خودی‌خود این الزامات را برقرار نمی‌کند.

## ۳. ناوردایی‌های اجباری

1. دادهٔ یک tenant در candidate، آمار واژگانی، graph، cache یا context tenant دیگر وارد نمی‌شود.
2. ACL، وضعیت معتبر، نسخه و پروژه **پیش از** محاسبهٔ IDF، استخراج واژگان، traversal و رتبه‌بندی اعمال می‌شوند.
3. Head بالاتر به‌خاطر جایگاه سازمانی، دسترسی بیشتری به جزئیات ندارد؛ هویت اجرایی و grant معتبر ملاک‌اند.
4. خلاصه و خروجی مشتق، محدودیت خواندن/پردازش همهٔ منابع استفاده‌شده را به ارث می‌برند. عمومی‌سازی خودکار ممنوع است.
5. متن criterion و هدف تأییدشده ثابت‌اند. ترجمهٔ query، متن اصلی معیار را جایگزین یا کوتاه نمی‌کند.
6. شاهد پیدا‌شده فقط `candidate` است. کلمهٔ مشترک، عنوان تابع، test موجود و پاسخ مدل، کفایت معنایی یا موفقیت اجرای test را ثابت نمی‌کنند.
7. `proposed`، `superseded`، `deleted`، منبع منقضی و شاهد ناسازگار، مرجع قطعی تصمیم آینده نمی‌شوند.
8. همهٔ excerptها منشأ، revision و hash دارند؛ شمارهٔ خط محلی chunk با خط مطلق فایل اشتباه نمی‌شود.
9. بودجه بر متن نهایی **رندرشده** با metadata، warning و separator کنترل می‌شود. بودجهٔ prompt کامل و خروجی جداست.
10. تغییر منبع، ACL یا سیاست، تمام packها، خلاصه‌ها، cacheها و نشست‌های وابسته را پیش از استفادهٔ بعدی نامعتبر می‌کند.
11. فایل، پیام و پاسخ NotebookLM حق تغییر سیاست سازمان، ایجاد grant یا پذیرش خروجی را ندارند.
12. شکست، عدم قطعیت و تلاش ناموفق ثبت می‌شوند؛ پاک کردن آن‌ها برای بهتر نشان دادن شاخص مجاز نیست.

## ۴. قرارداد دادهٔ مقصد

تمام زمان‌ها UTC با قالب RFC3339 ذخیره می‌شوند؛ رابط می‌تواند آن‌ها را به زمان کاربر نمایش دهد. شناسه‌ها immutable هستند. `revision` افزایش یکنواخت دارد. `artifact_hash`، SHA-256 بایت دقیق artifact ثبت‌شده است؛ به‌روزرسانی متن، hash جدید می‌سازد. برای JSON قراردادی، canonicalization و encoding باید در `hash_format` ثبت شوند.

### ۴.۱. هویت مشترک و معیار typed

```python
from typing import Literal, TypedDict

class Scope(TypedDict):
    tenant_id: str
    department_id: str | None
    project_id: str                 # برای این پروژه: alacrity-flux
    root_task_id: str | None        # برای دانش عمومی پروژه ممکن است null باشد
    task_id: str | None
    policy_revision: int

class Principal(TypedDict):
    principal_id: str
    principal_type: Literal['human', 'agent', 'service']
    tenant_id: str
    department_ids: list[str]
    project_ids: list[str]
    role_ids: list[str]
    acl_revision: int

class DataGrant(TypedDict):
    grant_id: str
    tenant_id: str
    principal_id: str
    project_ids: list[str]
    department_ids: list[str]
    permitted_layers: list[str]
    operations: list[Literal['read', 'research', 'propose', 'verify', 'delete']]
    source_constraints: dict
    processor_ids: list[str]
    policy_revision: int
    issued_by: str
    valid_from: str
    expires_at: str | None
    revoked_at: str | None
    artifact_hash: str

class Criterion(TypedDict):
    criterion_id: str
    text: str                      # عین متن تثبیت‌شده
    required: bool
    evidence_type: Literal[
        'code', 'test_definition', 'test_execution', 'approved_decision',
        'policy', 'source_document', 'tool_result', 'ui_observation'
    ]
    predicate_id: str | None       # validator ثبت‌شده؛ کد دلخواه مدل نیست
    source_constraints: dict       # مسیر/نوع/نسخه/محیط مجاز
    freshness_seconds: int | None
```

حداقل درخواست کار باید هر چهار فیلد `criterion_id/text/required/evidence_type` را داشته باشد. مقادیر inferشده از واژهٔ «تست» یا «مستند» فقط پیشنهاد‌اند؛ Head باید آن‌ها را در قرارداد تثبیت کند. در مثال «تست عبور کرد»، evidence_type برابر `test_execution` است؛ وجود تابع تست از نوع `test_definition` کافی نیست. مشاهدهٔ UI نیز از روی فایل CSS یا گفتهٔ مدل تأیید نمی‌شود.

### ۴.۲. artifact و chunk

```python
class SourceArtifact(TypedDict):
    source_id: str
    scope: Scope
    owner_principal_id: str
    source_type: Literal['repository', 'pdf', 'document', 'chat', 'tool', 'notebooklm']
    locator: str                   # مسیر/URL/شناسه؛ بدون secret
    revision: int
    source_revision: str | None    # commit یا version سرویس اصلی
    artifact_hash: str
    hash_format: str               # sha256:raw-bytes یا قرارداد canonical ثابت
    media_type: str
    created_at: str
    observed_at: str
    valid_from: str
    valid_until: str | None
    classification: str
    read_acl_id: str
    permitted_processor_ids: list[str]
    trust: Literal['untrusted_input', 'observed', 'owner_approved']
    status: Literal['available', 'quarantined', 'superseded', 'deleted']
    derived_from: list[dict]       # source_id/revision/artifact_hash
    retention_policy_id: str

class EvidenceChunk(TypedDict):
    chunk_id: str
    source_id: str
    source_registry_revision: int  # همان SourceArtifact.revision داخلی
    provider_source_revision: str | None  # همان SourceArtifact.source_revision
    artifact_hash: str             # hash artifact اصلی
    content_hash: str              # hash بایت excerpt یا chunk
    chunker_revision: str
    scope: Scope
    evidence_type: str
    locator: dict                  # page، symbol، absolute_line یا chunk_line
    text: str
    omitted_spans: list[dict]
    guard_spans: list[dict]
    read_acl_id: str
    permitted_processor_ids: list[str]
    indexed_at: str
```

برای PDF، `locator.page` و نام snapshot ثبت می‌شود. متن استخراج‌شده خود artifact مشتق است؛ hash PDF اصلی و hash متن استخراجی جدا ثبت می‌شوند. ترتیب خواندن RTL یا OCR نامطمئن باید با محدودیت extractor همراه باشد. برای کد، commit/hash و مسیر اصلی معیار است؛ برای گزارش test، فرمان، محیط، زمان، exit code، نسخهٔ مورد آزمون و فایل خروجی ابزار لازم است.

`SourceArtifact.revision` و `EvidenceChunk.source_registry_revision` شمارهٔ داخلی رجیستری از نوع int هستند. `SourceArtifact.source_revision` و `EvidenceChunk.provider_source_revision` شناسهٔ نسخهٔ سرویس اصلی از نوع str یا null هستند؛ commit SHA یا نسخهٔ متنی provider به عدد revision داخلی تبدیل نمی‌شود.

### ۴.۳. رکورد حافظه

```python
class MemoryRecord(TypedDict):
    memory_id: str                 # هویت پایدار یک گزاره/تصمیم
    revision: int                 # نسخه‌ها append-only
    scope: Scope
    layer: Literal['company', 'department', 'project', 'task']
    kind: Literal['fact', 'decision', 'procedure', 'preference', 'lesson', 'open_question']
    title: str
    content: str
    artifact_hash: str
    hash_format: str
    status: Literal['proposed', 'verified', 'superseded', 'deleted']
    verification_state: Literal['unverified', 'valid', 'stale', 'conflicted', 'rejected']
    owner_principal_id: str
    proposed_by: str
    created_at: str
    verified_at: str | None
    verified_by: str | None
    valid_from: str
    valid_until: str | None
    read_acl_id: str
    permitted_processor_ids: list[str]
    evidence_refs: list[dict]      # source_id/revision/hash/locator و ادعای پشتیبانی‌شده
    acceptance_ref: dict | None   # grant/acceptance_id + artifact_hash
    depends_on: list[dict]        # هویت و نسخهٔ دقیق منبع/حافظه
    contradicts: list[dict]
    supersedes: dict | None
    superseded_by: dict | None
    change_reason: str
    retention_policy_id: str
    deletion_event_id: str | None
```

هویت منطقی در دیتابیس مرکب از `(tenant_id, project_id, memory_id)` و کلید هر نسخه از همان سه فیلد به‌اضافهٔ `revision` است. استفادهٔ مجدد از memory_id یک پروژه در پروژهٔ دیگر مجاز است و سبب ادغام نمی‌شود. هیچ قاعده‌ای با «آخرین timestamp کل سیستم» انتخاب نمی‌شود؛ latest revision فقط در همان هویت و همان زنجیرهٔ نسخه معتبر است.

زنجیرهٔ authoritative ابتدا با eventها و pointer نسخهٔ مؤثر حل می‌شود؛ سپس status و ACL فیلتر می‌شوند. tombstone یا withdrawal معتبر، نسخه‌های قدیمی همان هویت را برای اجرای تازه می‌بندد. نسخهٔ پیشنهادی تازه، نسخهٔ verified قبلی را خودکار جایگزین نمی‌کند؛ جابه‌جایی pointer فقط پس از promotion معتبر و transaction انجام می‌شود. صرف حذف نسخهٔ غیرفعال از ورودی و انتخاب جدیدترین نسخهٔ فعال باقی‌مانده، می‌تواند تصمیم لغوشده را دوباره زنده کند.

`verified` به معنی صحت ابدی نیست. `verification_state=stale/conflicted`، expiry یا وابستگی نامعتبر باعث حذف رکورد از منابع معتبر اجرای تازه می‌شود. وضعیت اصلی رکورد و وضعیت verification جدا هستند تا تاریخ پذیرش گذشته حفظ شود و اعتبار اکنون صادقانه نمایش یابد.

### ۴.۴. snapshot ذهن پروژه

```python
class ProjectMindSnapshot(TypedDict):
    mind_id: str
    revision: int
    scope: Scope
    artifact_hash: str
    generated_at: str
    goal_ref: dict
    contract_refs: list[dict]
    active_task_refs: list[dict]
    accepted_artifact_refs: list[dict]
    verified_memory_refs: list[dict]
    source_manifest_refs: list[dict]
    open_question_refs: list[dict]
    contradiction_refs: list[dict]
    pending_approval_refs: list[dict]
    invalidated_dependency_refs: list[dict]
    read_acl_id: str
    permitted_processor_ids: list[str]
```

snapshot، index بازیابی یا کل محتوای همهٔ این رکوردها نیست. مسیرهای مرجع و نسخه‌ها را نگه می‌دارد. projection مخصوص یک principal فقط موارد مجاز او را دارد؛ اگر تولید خلاصهٔ واحد از منابع چند ACL موجب افشا شود، projection جدا تولید می‌شود. نسخهٔ خلاصهٔ مدیر حق افشای جزئیات ممنوع شاخه را ندارد.

### ۴.۵. درخواست retrieval و بستهٔ شواهد

```python
class RetrievalRequest(TypedDict):
    request_id: str
    scope: Scope
    principal: Principal
    objective: str
    criteria: list[Criterion]
    processor_id: str
    evidence_budget_tokens: int
    tokenizer_id: str
    tokenizer_revision: str
    max_stages: int
    max_candidates_per_criterion: int
    snapshot_revision: int
    deadline_at: str
    allowed_layers: list[str]
    purpose: Literal['execution', 'review', 'research', 'historical_audit']

class Assessment(TypedDict):
    criterion_id: str
    expected_evidence_type: str
    retrieval_status: Literal['missing', 'candidate']
    semantic_sufficiency: Literal['unverified', 'sufficient', 'insufficient', 'conflicted']
    evidence_refs: list[dict]
    missing_reason: str | None
    verifier_id: str | None
    verified_at: str | None
    verification_artifact_hash: str | None

class EvidencePack(TypedDict):
    pack_id: str
    scope: Scope
    artifact_hash: str
    request_hash: str
    snapshot_revision: int
    acl_revision: int
    index_revision: str
    selector_revision: str
    tokenizer_id: str
    tokenizer_revision: str
    rendered_text: str
    counted_tokens: int
    evidence_budget_tokens: int
    source_manifest: list[dict]
    assessments: list[Assessment]
    contradiction_refs: list[dict]
    dependency_refs: list[dict]
    valid_until: str | None
    invalidated_at: str | None
    invalidation_reason: str | None
```

به‌صورت پیش‌فرض selector تمام assessments را `semantic_sufficiency=unverified` می‌سازد. سرویس verifier فقط روی **همان hash بسته، همان قرارداد معیار و همان نسخهٔ خروجی** گزارش کافی/ناکافی می‌دهد. تغییر هرکدام تأیید قبلی را باطل می‌کند. متن هشدار و provenance جزو `rendered_text` و بودجهٔ آن‌اند؛ assessments بیرون از متن اگر به مدل فرستاده شوند، gateway هزینهٔ توکن آن‌ها را نیز در prompt کل می‌شمارد.

## ۵. مدل دسترسی پیش از انتخاب شاهد

مرز پایه tenant است؛ دادهٔ `global` در آزمایش محلی معادل دانش مشترک بین همهٔ مشتریان نیست. در مقصد، دانش مشترک شرکت `layer=company` و **همان tenant_id** دارد. منبع عمومی خارجی نیز باید با ورود مجاز، provenance و policy به namespace مشتری ثبت شود؛ رکورد cross-tenant با برچسب global راه دور زدن مرز نیست.

تابع eligibility باید این شرایط را پیش از ranking برقرار کند:

```text
same_tenant
AND scope_allowed_by_grant
AND layer_allowed_for_this_task
AND read_acl_allows(principal, source)
AND source_processor_policy_allows(processor_id)
AND purpose_allowed
AND canonical_effective_revision_after_tombstones
AND source_artifact_status == available
AND not_quarantined
AND not_deleted_or_superseded
AND not_expired
AND verified_or_explicitly_research_candidate
AND no_invalid_dependency
```

artifact دارای `status=quarantined`، از جمله خطای استخراج یا ناسازگاری hash، وارد index، candidate، reranker، graph یا context نمی‌شود. لغو quarantine فقط پس از اصلاح علت، ثبت شاهد و snapshot معتبر تازه انجام می‌شود؛ purpose پژوهش اجازهٔ عبور از این gate را نمی‌دهد.

اشتراک project میان دو بخش فقط با عضویت/مجوز پروژه برقرار می‌شود. دانش شرکت می‌تواند وارد بستهٔ پروژه شود؛ دانش department دیگر بدون grant وارد نمی‌شود. دانش task فقط برای همان کار و نقش‌های بازبین/اجرایی دارای مجوز است. `root_task_id` وسیلهٔ گروه‌بندی هزینه و lineage است و مجوز خواندن تمام زیرکارها را ایجاد نمی‌کند.

برای اجرای عادی، منابع policy/decision باید owner-approved و حافظه باید `verified + valid` باشند. در پژوهش یا audit، رکورد proposed/تاریخی فقط با مجوز purpose و برچسب آشکار وارد بخش «شواهد غیرقطعی/تاریخی» می‌شود؛ هرگز به بخش حقیقت عملیاتی ارتقا نمی‌یابد. خروجی تحقیقی NotebookLM با متن مشابه policy، grant ایجاد نمی‌کند.

یک cache key حداقل باید tenant، project، principal/ACL digest، processor، purpose، snapshot، policy_revision، index_revision، request_hash و tokenizer_revision را داشته باشد. نبود یکی از این مرزها می‌تواند reuse نامعتبر بسازد. index مشترک فیزیکی فقط وقتی مجاز است که query و graph و statistics به view مجاز محدود شوند؛ post-filter بعد از top-k کافی نیست.

## ۶. ورود منابع و تولید memory note

### ۶.۱. مسیر ورود

1. صاحب انسانی پروژه، مجموعهٔ اولیهٔ مجاز را مشخص می‌کند: وایت‌پیپر، docs فعلی، سورس لازم و گزارش‌های اجرا. همهٔ تاریخچهٔ شخصی یا credential وارد نمی‌شود.
2. ingest با principal و مقصد پردازش مشخص آغاز می‌شود؛ owner، ACL و retention قبل از دریافت محتوا تعیین می‌شوند.
3. بایت منبع snapshot می‌شود؛ `artifact_hash` و revision ثبت می‌شود. کلید و فایل credential از corpus خارج‌اند؛ secret detector مکمل allowlist است و تضمین کامل کشف اسرار نیست.
4. extractor متن و locator را ثبت می‌کند. خطای استخراج یا ناسازگاری hash، منبع را quarantined می‌کند.
5. chunking در مرز ساختاری انجام می‌شود؛ برای کد guard و امضا، برای سند heading/تعریف، برای حافظه گزارهٔ کامل حفظ می‌شود.
6. استخراج candidate fact/decision/lesson روی منابع مجاز انجام می‌شود؛ هر candidate با citation و محدودیت اعتبار `proposed` ثبت می‌شود.
7. verifier شاهد، نسخه، scope، نوع معیار و تعارض را بررسی می‌کند. rule کسب‌وکار، policy یا دستورالعمل آینده به تأیید owner انسانی همان hash نیاز دارد.
8. snapshot و index پس از transaction موفق تغییر می‌کنند؛ idempotency_key از source hash و نسخهٔ extractor از ingest تکراری جلوگیری می‌کند.

### ۶.۲. الگوریتم استخراج یادداشت

```python
def propose_notes(source_refs, task, ports):
    sources = ports.load_authorized_snapshots(
        source_refs, task['principal'], task['scope'], task['processor_id'])
    proposals = ports.extract_atomic_claims(sources)  # مدل/کد: فقط پیشنهاد
    saved = []
    for proposal in proposals:
        if not proposal['evidence_refs']:
            ports.record_rejection(proposal, 'missing_provenance')
            continue
        if not ports.refs_match_snapshot_hashes(proposal['evidence_refs']):
            ports.record_rejection(proposal, 'source_revision_changed')
            continue
        acl = ports.intersect_source_permissions(proposal['evidence_refs'])
        conflicts = ports.find_authorized_contradictions(proposal, acl)
        record = ports.make_memory_record(
            proposal, scope=task['scope'], status='proposed',
            verification_state='unverified', read_acl=acl,
            contradictions=conflicts)
        saved.append(ports.append_proposal_idempotently(record))
    return saved
```

`ports` قرارداد adapterهای پیاده‌نشدهٔ مقصد است؛ شبه‌کد از نظر جریان کنترل قابل تبدیل مستقیم به Python است، اما اجرای آن به پیاده‌سازی این portها نیاز دارد. استخراج یادداشت، اجرای آموزش مجدد مدل پایه نیست. تعداد زیاد note نیز مزیت نیست؛ هر note باید یک گزاره، تصمیم یا پرسش قابل بررسی داشته باشد.

قالب قابل‌خواندن note:

```text
memory_id / revision / scope / status
گزاره: ...
نوع: fact | decision | procedure | lesson | preference | open_question
مبنای اعتبار: منبع، نسخه، hash، locator
دورهٔ اعتبار و شرایط کاربرد: ...
محدودیت یا تعارض: ...
صاحب تأیید / artifact_hash تأییدشده: ...
وابستگی‌ها و جایگزینی: ...
```

نمونهٔ درست برای همین پروژه: «README فعلی Flux نسخهٔ ۰٫۴ را فضای کار نشست‌های CLI می‌نامد؛ وایت‌پیپر در جدول تاریخی خود وضعیت دموی ۰٫۲ را توضیح می‌دهد.» این دو مشاهده با زمان/نسخه متفاوت‌اند و تعارض ماهوی ندارند. نمونهٔ نادرست: «همهٔ قابلیت‌های سازمانی وایت‌پیپر پیاده‌سازی شده‌اند.» سند مقصد چنین چیزی را تأیید نمی‌کند.

## ۷. چرخهٔ عمر و تأیید دانش

```text
proposed -- شاهد معتبر + verifier + grant معتبر --> verified
proposed -- رد --> proposed با verification_state=rejected
verified -- نسخهٔ جدید تأییدشده --> superseded
proposed / verified / superseded -- درخواست حذف مجاز --> deleted
verified -- تغییر منبع/انقضا/تعارض --> verified با verification_state=stale/conflicted
```

رد شدن، حذف کردن نیست؛ سابقهٔ پیشنهاد ردشده طبق retention باقی می‌ماند و در retrieval اجرایی واجد انتخاب نیست. وضعیت deleted، مانع retrieval آینده است؛ پاک‌سازی فیزیکی تاریخی عملیات جداگانه است.

```python
def verify_and_promote(memory_key, expected_revision, approval, ports):
    note_snapshot = ports.load_proposal_snapshot(memory_key, expected_revision)
    review = ports.verify_claims_against_sources(note_snapshot)
    # تماس مدل/ابزار پیش از transaction؛ سپس نسخه و شاهد دوباره بررسی می‌شوند.
    with ports.transaction():
        note = ports.lock_memory(memory_key, expected_revision)
        ports.require_status(note, 'proposed')
        ports.require_current_policy(approval['policy_revision'])
        ports.require_owner_authority(approval, note['scope'])
        ports.require_approval_hash(approval, note['artifact_hash'])
        ports.require_current_authorized_dependencies(note['depends_on'])
        ports.require_review_bound_to_hash(review, note['artifact_hash'])
        ports.require_current_review_evidence(review)
        if review['status'] != 'sufficient' or review['contradictions']:
            return ports.keep_proposed(note, review)
        promoted = ports.append_verified_revision(note, approval, review)
        if promoted['supersedes']:
            ports.mark_superseded_atomically(promoted['supersedes'], promoted)
        ports.append_event('memory_verified', promoted)
        ports.bump_project_snapshot_revision(note['scope'])
        ports.publish_invalidation_after_commit(note['scope'])
        return promoted
```

تأیید بایت/نسخهٔ مشخص است. اگر draft پس از تأیید تغییر کند، approval قابل reuse نیست. سیاست مصوب مشتری می‌تواند promotion تجربهٔ کم‌خطر را به validator قطعی تفویض کند؛ این تفویض باید نوع record، سقف اثر، scope و policy_revision را مشخص کند. مدل نمی‌تواند این مسیر را برای policy سازمان یا کسب دسترسی استفاده کند.

## ۸. تشخیص و حل تعارض

دو گزارهٔ متعارض را با تعداد رأی، جدیدترین timestamp یا اعتماد بیشتر یک مدل حل نمی‌کنیم. ابتدا معلوم می‌شود آیا هر دو دربارهٔ یک subject/predicate، scope، نسخه و دورهٔ اعتبار حرف می‌زنند. اختلاف وضعیت تاریخی ۰٫۲ و سورس ۰٫۴ نمونهٔ تفاوت نسخه است؛ دو policy فعال متفاوت دربارهٔ مقصد مجاز پردازش نمونهٔ تعارض مؤثر است.

`ContradictionRecord` شامل `conflict_id`، scope، subject/predicate، refs دقیق دو طرف، دورهٔ هم‌پوشان، criterionهای متأثر، severity، status باز/حل‌شده، owner مسئول، resolution_ref و زمان ثبت است. هیچ طرفی با خلاصه‌سازی حذف نمی‌شود. فقط metadata مجاز تعارض به Head فاقد دسترسی جزئیات داده می‌شود.

ترتیب رسیدگی:

1. hash و revision هر طرف بررسی شود؛ artifact منسوخ از اجرای تازه کنار گذاشته شود.
2. اختلاف طبقهٔ ادعا تشخیص داده شود: جهت‌گیری محصول، طراحی پیشنهادی، مشاهدهٔ کد، test اجراشده، benchmark یا پذیرش انسانی.
3. اگر نسخه/دوره/محیط متفاوت است، هر دو با شرایط کاربرد خود حفظ شوند.
4. اگر تعارض همچنان مؤثر است، `semantic_sufficiency=conflicted` و رکوردهای مربوط `verification_state=conflicted` شوند.
5. شاخهٔ وابسته به تصمیم متوقف و مسئله به owner انسانی/Head دارای اختیار حل ارجاع شود؛ کار مستقل ادامه یابد.
6. resolution باید رکورد تصمیم نسخه‌دار با شاهد و پذیرش همان hash باشد؛ index و بسته‌های وابسته invalidate شوند.

پاسخ NotebookLM، رأی reviewer یا source prior در ranking جای resolution رسمی را نمی‌گیرد.

## ۹. بازیابی تدریجی بر اساس معیار

هر stage روی snapshot و view مجاز مشخص اجرا می‌شود. اگر snapshot/ACL تغییر کند، stage جدید بستهٔ قبلی را refresh می‌کند؛ شواهد stale با شواهد جاری بی‌علامت مخلوط نمی‌شوند.

| مرحله | ورودی و عمل | شرط پایان |
|---|---|---|
| صفر: نقشه | projection مجاز ذهن پروژه، قرارداد، منابع و معیارهای typed | scope/مالک/معیار نامشخص به درخواست اطلاعات تبدیل شود |
| یک: بازیابی مستقیم | lexicon دوزبانه، شناسه/مسیر صریح، ranking جدا برای هر criterion؛ objective با وزن کمتر | candidateها و gapها با منبع ثبت شوند |
| دو: گسترش محدود | فقط معیار ناکافی؛ منبع اصلی، caller/callee مجاز، بخش مجاور، query جایگزین؛ semantic adapter فقط در صورت ارزیابی | شاهد تازه و مرتبط پیدا شود یا no-progress ثبت شود |
| سه: تأیید | بررسی معنایی علیه معیار، hash/نسخه، guard، گزارش اجرای واقعی و تعارض | sufficient/insufficient/conflicted ثبت شود |
| چهار: درخواست/ارجاع | دادهٔ لازم، permission یا بودجهٔ مشخص درخواست شود | پایان تلاش retrieval؛ بدون ادعای تکمیل criterion |

حد stage و deadline جزو قراردادند. stage جدید تنها وقتی مجاز است که مسیر یا شاهد جدید مشخص باشد، هزینهٔ model/tool رزرو شود و فرصت review باقی بماند. queryهای مکرر با متن یکسان مصرف root task را صفر نمی‌کنند. retrieval محلی نیز محدودیت زمان/حافظه دارد؛ تماس embedding/reranker/NotebookLM اگر انجام شود در بودجهٔ تماس و ledger ثبت می‌شود.

```python
def retrieve_for_task(request, ports):
    ports.validate_request_and_fixed_criteria(request)
    # validation: max_stages >= 1 و criteria برای execution غیرخالی‌اند.
    view = ports.authorized_snapshot_view(request)  # scope/ACL/version FIRST
    space = ports.build_or_load_index(view)         # IDF/graph فقط از همین view
    candidates = {c['criterion_id']: [] for c in request['criteria']}
    prior_signatures = set()
    latest_pack = None
    for stage in range(request['max_stages']):
        ports.require_before_deadline(request['deadline_at'])
        ports.require_unchanged_acl_policy_and_snapshot(view)
        missing = ports.criteria_needing_evidence(request['criteria'], latest_pack)
        if not missing:
            break
        queries = ports.query_plan(request['objective'], missing, stage)
        signature = ports.canonical_query_signature(queries)
        if signature in prior_signatures:
            break
        prior_signatures.add(signature)
        additions = ports.rank_per_criterion(space, queries, request)
        candidates = ports.merge_deduplicate_and_check_types(candidates, additions)
        latest_pack = exact_pack(request, candidates, ports)
        if ports.is_budget_error(latest_pack):
            return latest_pack
        # بستهٔ تازه ممکن است شاهد معیار قبلاً کافی را حذف یا تغییر داده باشد.
        # جست‌وجو فقط missing است، ولی تأیید روی همهٔ معیارهای همین بسته انجام می‌شود.
        review = ports.verify_pack_for_criteria(latest_pack, request['criteria'])
        latest_pack = ports.attach_review_to_same_hash(latest_pack, review)
        if review['blocking_conflict'] or not review['new_evidence']:
            break
    return ports.finalize_with_explicit_gaps(latest_pack, request)
```

ساخت pack تازه، assessments را دوباره unverified می‌کند. وضعیت sufficient بستهٔ قدیم به بستهٔ جدید منتقل نمی‌شود؛ همهٔ معیارهای required و هر معیار اختیاری مورد گزارش، علیه شواهد واقعاً موجود در همان hash جدید بررسی می‌شوند. در این شبه‌کد همهٔ معیارها دوباره بررسی می‌شوند. cache تأیید فقط با criterion contract، hash دقیق evidence بدون تغییر، نسخهٔ خروجی و مجوز/سیاست/منبع معتبر قابل reuse است و در صورت تغییر وابستگی باطل می‌شود.

در مقصد رتبه‌بندی hybrid اختیاری است: union candidateهای واژگانی و معنایی، rerank در view مجاز، سپس تنوع و coverage. ورودی مدل reranker هم تابع processor policy است. وزن‌ها و thresholdها باید با مجموعهٔ ارزیابی منجمد تعیین شوند؛ این سند ادعای برتری embedding یا درصد عمومی recall نمی‌کند.

## ۱۰. بسته‌بندی دقیق در سقف توکن

بستهٔ Head نقشهٔ کوتاه منابع، تعارض‌ها و شکاف‌هاست. بستهٔ Worker، شاهد موردنیاز اجرای زیرکار است. هر دو اگر در prompt قرار بگیرند مصرف دارند؛ کوتاه بودن Head نباید provenance لازم Worker را حذف کند.

اولویت بسته‌بندی مقصد: حداقل شاهد سالم برای معیار required، شاهد رفع تعارض/guard لازم، سپس شاهد تکمیلی و معیار اختیاری. انتخاب حریصانه الزاماً optimum نیست؛ guarantee این الگوریتم **رعایت سقف و صداقت gap** است، نه حداکثر پوشش ممکن.

```python
def exact_pack(request, candidates, ports):
    budget = request['evidence_budget_tokens']
    render = ports.render_evidence_with_provenance_and_warning
    count = ports.tokenizer(request['tokenizer_id'], request['tokenizer_revision'])
    chosen = {}
    empty_text = render(chosen)
    if count(empty_text) > budget:
        return ports.budget_too_small_result(request, count(empty_text))
    for candidate in ports.required_first_round_robin(candidates, request['criteria']):
        ports.require_eligible_current_candidate(candidate, request)
        unit = ports.expand_to_semantically_safe_unit(candidate)
        # امضا، guard، عبارت چندخطی و provenance داخل واحد حفظ می‌شوند.
        proposal = ports.merge_source_spans(chosen, unit)
        text = render(proposal)
        if count(text) <= budget:
            chosen = proposal
        else:
            alternative = ports.smaller_complete_unit(candidate)
            if alternative is not None:
                trial = ports.merge_source_spans(chosen, alternative)
                if count(render(trial)) <= budget:
                    chosen = trial
    text = render(chosen)
    actual = count(text)           # شمارش کل متن نهایی؛ نه جمع هزینهٔ پنجره‌ها
    assert actual <= budget
    return ports.make_pack(request, chosen, text, actual,
                           semantic_sufficiency='unverified')
```

برش نویسه‌ای تصادفی برای جا دادن حافظه مجاز نیست. اگر گزارهٔ کامل جا نمی‌شود، chunk مستقل با مرز معنایی و reference به اصل انتخاب می‌شود، یا آن candidate کنار گذاشته و علت `budget_insufficient` ثبت می‌شود. نام تابع یا ID حافظه بدون متن مرتبط coverage واقعی نیست.

بودجهٔ کل gateway:

```text
serialized_input_tokens
  = tokens(system_policy + fixed_task + dialogue + head_map + worker_pack
           + tool_schemas + message_framing)

serialized_input_tokens + reserved_output_tokens + context_margin
  <= model_context_limit

worker_pack_tokens <= granted_evidence_budget_tokens
```

شمارندهٔ `o200k_base` آزمایش محلی برای worker evidence دقیق است، ولی معادل قطعی صورتحساب همهٔ providerها نیست. مقصد باید tokenizer/adapter واقعی مدل و framing را بشناسد؛ margin جای ثبت usage واقعی را نمی‌گیرد. هزینهٔ ورودی، حداکثر خروجی و review طبق قرارداد مدیریت توکن رزرو می‌شود؛ صرفه‌جویی در شواهد فقط یکی از اجزای هزینهٔ خروجی پذیرفته‌شده است.

## ۱۱. invalidation، حذف و بازیابی پس از قطع

رویدادهای `source_changed`، `memory_superseded`، `access_revoked`، `policy_changed`، `source_deleted` و `expired` به نسخهٔ مشخص اشاره می‌کنند. dependency graph فقط روی منابع مجاز ساخته می‌شود و در سرویس داخلی جهت invalidation استفاده می‌شود؛ نام منبع ممنوع در trace عمومی هم نباید افشا شود.

```python
def invalidate_or_delete(target_ref, actor, mode, expected_revision, ports):
    with ports.transaction():
        target = ports.lock_target(target_ref, expected_revision)
        ports.require_mutation_authority(actor, target, mode)
        if mode == 'delete_from_future_retrieval':
            ports.mark_deleted_and_tombstone(target)  # gate آینده فوراً بسته می‌شود
        else:
            ports.mark_dependency_stale(target)
        affected = ports.transitive_derivatives(target_ref)
        ports.invalidate_packs_summaries_and_indices(affected)
        ports.retire_affected_provider_sessions(affected)
        event = ports.append_invalidation_event(target, affected, actor, mode)
        ports.bump_visibility_epoch(target['scope'])
        ports.schedule_physical_prune_after_commit(event)
    return ports.report_deletion_scope_and_retention(event)
```

cache/embedding/summary فیزیکی می‌تواند پس از commit با job پاک شود؛ gateway باید با visibility epoch/tombstone استفاده از آن را از همان commit منع کند. حداکثر تاخیر job، وضعیت prune و شکست آن قابل مشاهده‌اند. این سازوکار از استفادهٔ دوباره جلوگیری می‌کند؛ دادهٔ قبلاً ارسال‌شده به provider را از ذهن نشست یا ذخیرهٔ خارجی به‌صورت تضمینی حذف نمی‌کند.

نشست resumed که یادداشت لغوشده دیده است، برای اجرای تازه بازنشسته و از منابع مجاز بازسازی می‌شود. تغییر `use_memory=False` به‌تنهایی این اثر را ندارد. خروجی مشتق‌شده از منبع حذف‌شده، از خودکارسازی بعدی خارج می‌شود تا سیاست owner دربارهٔ نگهداری/استفادهٔ آن تعیین شود.

**حذف از retrieval آینده** و **پاک‌سازی تاریخچه** دو انتخاب جدا در UI‌اند. پاک‌سازی تاریخی به retention، مجوز حذف، backup و نیاز audit بستگی دارد. tombstone حداقل hash/شناسه/زمان/علت مجاز را حفظ می‌کند؛ متن حساس در event عمومی نوشته نمی‌شود. پذیرش تاریخی نشان می‌دهد در زمان گذشته چه نسخه‌ای پذیرفته شده، ولی برای استفادهٔ جاریِ نسخهٔ نامعتبر authority نمی‌سازد.

پس از restart، JEV از آخرین snapshot و event commit‌شده projection را بازسازی می‌کند. درخواست دارای `request_id/request_hash` دوباره artifact تازهٔ متفاوت نمی‌سازد. وضعیت ingest/verification نیمه‌تمام `pending` باقی می‌ماند؛ کامل فرض نمی‌شود. عملیات با نتیجهٔ نامعلوم قبل از تکرار از رجیستری مقصد بررسی می‌شود.

## ۱۲. NotebookLM در زنجیرهٔ دانش این پروژه

در این پروژه NotebookLM دفتر پژوهش زنده برای مجموعهٔ منابع مجاز است. notebook ID، source ID، زمان upload/پرسش و hash snapshot محلی در manifest ثبت می‌شوند. اگر نسخهٔ service برای source مشخص نباشد، `source_revision=null` و محدودیت آن صریح است؛ hash پاسخ جای hash منبع را نمی‌گیرد.

الگوریتم استفاده:

1. corpus مجاز و بدون credential با manifest آماده شود؛ upload فقط به مقصد پردازش مجاز پروژه باشد.
2. پرسش دارای objective و criterion روشن از همان notebook انجام شود.
3. پاسخ خام، referenceها و notebook/source ID به‌عنوان research artifact ذخیره شوند.
4. هر گزارهٔ پاسخ با صفحه/بخش/نسخهٔ منبع اصلی محلی تطبیق داده شود. reference گم‌شده یا نامشخص، `unverified` می‌ماند.
5. note از گزارهٔ تأییدپذیر ساخته و به lifecycle `proposed` وارد شود.
6. پس از بررسی source و owner approval لازم، note به رجیستری دانش معتبر ارتقا یابد.

NotebookLM منبع انحصاری حقیقت نیست. تصمیم پروژه در رجیستری نسخه‌دار ثبت می‌شود، نه فقط در history گفتگو با notebook. انتخاب prompt یا پاسخ دفتر، grantهای Flux را تغییر نمی‌دهد. اگر پاسخ یا سرویس در دسترس نباشد، منابع محلیِ snapshot‌شده قابل بازیابی‌اند؛ پاسخ هزینه‌دار یا upload دوباره بدون نیاز انجام نمی‌شود.

## ۱۳. درس‌های قابل انتقال از JEVS v2 موجود

توابع `Index.__init__` و `Index.space` در آزمایش، انتخاب namespace و active/latest revision را پیش از ساخت `ProjectSpace` و IDF انجام می‌دهند. `Index.rank` برای هر معیار passage مستقل، نرمال‌سازی طول، نام owner و source prior دارد. `_prepare/render` امضا، guard و عبارت چندخطی محدود را حفظ می‌کنند. `Index.select` round-robin، هزینهٔ merged span و شمارش نهایی با warning دارد.

مواردی که هنوز نیاز طراحی مقصد هستند:

- `required_kind` نوع شاهد را از متن حدس می‌زند؛ معیار typed مقصد جای آن را می‌گیرد.
- `Index.space` رکوردهای `global` را اضافه می‌کند؛ ACL/tenant/processor purpose در این ساختار نیست.
- انتخاب `active` یا latest revision، وابستگی تازه و اعتبار حقیقت را ثابت نمی‌کند؛ revocation/tombstone و stale gate اضافه می‌شوند.
- در `Index.__init__` وضعیت غیرactive پیش از dedup نسخه‌ها حذف می‌شود. اگر یک ID، revision قدیمی active و revision تازهٔ deleted/obsolete داشته باشد و نسخهٔ قدیمی جداگانه superseded نشده باشد، نسخهٔ قدیمی ممکن است دوباره انتخاب شود. در همین بررسی، مثال مصنوعی و بدون فایل/DB با ID=`same`، revision=۱ active و revision=۲ obsolete اجرا شد؛ `Index.space('alpha')` نسخهٔ ۱ active را برگرداند. آزمون وضعیت موجود، obsolete با ID جدا را بررسی می‌کند؛ وضعیت tombstone همان ID را پوشش نمی‌دهد. مقصد ابتدا زنجیرهٔ مؤثر را حل و سپس eligibility را اعمال می‌کند.
- assessments واژگان مشترک را می‌سنجند و همیشه کفایت را unverified نگه می‌دارند؛ verifier مستقل لازم است.
- render فعلی شمارهٔ خط داخل chunk می‌دهد، نه خط مطلق؛ hash commit/PDF و locator دقیق مقصد لازم است.
- source graph یک‌مرحله‌ای آزمایش، تعارض یا lineage graph نیست؛ در تنظیم نهایی خاموش است.
- index/candidate cache فعلی در حافظهٔ فرایند است؛ invalidation بادوام، transaction دانش و recovery سازمانی ندارد.
- helper فقط pack می‌نویسد؛ memory را mutate نمی‌کند، کد پروژه را اجرا نمی‌کند و runtime Flux را عوض نمی‌کند.

این درس‌ها قابلیت reuse الگوریتمی دارند؛ کپی selector به runtime بدون قرارداد داده و آزمون isolation، تحقق RAG سازمانی نیست.

## ۱۴. اعداد محلی و حدود استناد

مرجع: `experiments/jev_v2_rewrite_20261001/REPORT.fa.md` و `summary.json`. این بررسی گزارش‌ها را خواند و hash کد و snapshot را با `frozen_candidate.json` تطبیق داد؛ benchmark یا تماس‌های هزینه‌دار نمونه دوباره اجرا نشده‌اند.

| ۱۲ سناریوی اضافی، سقف worker evidence=۳۰۰۰ | v2 قبلی | v2 بازنویسی‌شده |
|---|---:|---:|
| شاهد یافته‌شده | ۱۹/۴۳ | ۲۹/۴۳ |
| پوشش مجموع شواهد | ۴۴٫۲٪ | ۶۷٫۴٪ |
| میانگین توکن شواهد | ۲۸۷۰٫۱ | ۲۸۴۴٫۵ |
| سناریوی دارای همهٔ شواهد | ۴/۱۲ | ۴/۱۲ |
| میانهٔ زمان انتخاب محلی | حدود ۱۹٫۶ ms | حدود ۴۹٫۰ ms |

مجموعه شامل ۶۱۴ chunk و ۴۴۰ memory با منابع واقعی و نویز/تصمیم مصنوعی است. گزارش ۳۷ سناریو، ۱۵۲ واحد شاهد و ۳۳۳ اجرای انتخاب را ثبت می‌کند. صفر عبور از سقف/حافظهٔ خارجی/obsolete در همین اجراها گزارش شده؛ این نتیجه tenant ACL تولیدی، به‌روز بودن همهٔ activeها یا امنیت مطلق را ثابت نمی‌کند. ۱۶ آزمون رفتاری و ۲ آزمون CLI بسته‌بندی‌شده نتیجهٔ ثبت‌شدهٔ همان گزارش‌اند.

سه سناریوی زنده با یک مدل و سقف خروجی یکسان، نسخهٔ قبلی با evidence=۶۰۰۰ را با نسخهٔ جدید evidence=۳۰۰۰ مقایسه کردند: ورودی واقعی ۱۹٬۳۳۱ در برابر ۱۰٬۱۰۰، مجموع ۲۲٬۱۴۲ در برابر ۱۲٬۸۲۵، هزینهٔ گزارش provider حدود ۰٫۰۰۸۲۰۵۵ در برابر ۰٫۰۰۵۷۹۴۵۵ دلار. کاهش مجموع ۴۲٫۱٪ و هزینه ۲۹٫۴٪ فقط مربوط به همین مقایسه با **سقف شواهد متفاوت** است. در مقایسهٔ زنده با سقف یکسان، کاهش توکن کل نشان داده نشده است.

این benchmark حضور شواهد را می‌سنجد، نه موفقیت کلی پروژه، صحت تمام پاسخ‌ها یا پذیرش مشتری. هنوز ۱۴ شاهد از ۴۳ شاهد مجموعهٔ اضافی پیدا نشده و ۸ سناریو کامل نیستند. مؤلف benchmark از تاریخچهٔ توسعه مستقل نیست. هیچ درصد عمومی افزایش دقت، صرفه‌جویی تجاری یا اجرای موفق TypeSafe Jev از آن نتیجه نمی‌گیریم.

hashهای بازبینی‌شده در این بررسی:

```text
optimized_v2.py:
1bad973fe8570b4f7416c98cd3f7cc69fdfe418ae29e2ae18a956767745e1a57
corpus_snapshot.json:
90af8a3b95fbf845228bd0dd15849fdd9f2b175cc310912dad0f1f34ea4bb847
summary.json:
0c77ab136d1b96e44a0a1fca5632e257faa00fbbc828acbb24e86f8e918ce58e
```

## ۱۵. دروازه‌های پیاده‌سازی و معیار آمادگی

| آزمون مقصد | شاهد لازم برای پذیرش |
|---|---|
| tenant/پروژه | اضافه کردن corpus tenant یا پروژهٔ دیگر، candidate/آمار/ranking/pack پروژهٔ حاضر را تغییر ندهد |
| ACL/processor | یادداشت ممنوع حتی در intermediate reranker/graph/cache/context یا trace قابل مشاهده وارد نشود |
| نسخه و حذف | latest معتبر در هویت خودش انتخاب شود؛ proposed/rejected/stale/superseded/deleted در execution truth نباشد |
| derivative | خلاصهٔ چندمنبعی ACL همهٔ منابع را حفظ کند؛ revocation یک منبع، خلاصه و pack وابسته را invalidate کند |
| نشست provider | session دارای منبع لغوشده retire شود؛ درخواست بعدی با context مجاز نو ساخته شود |
| معیار typed | test definition معیار test execution را کافی نشان ندهد؛ code معیار UI مشاهده‌شده را تأیید نکند |
| semantic sufficiency | keyword overlap به‌تنهایی sufficient نسازد؛ گزارش verifier به hash معیار/pack/output متصل باشد |
| برش سالم | guard، exception و عبارت کامل حفظ شوند؛ حافظهٔ بزرگ یا واحد کامل کوچک‌تر شود یا gap بودجه ثبت شود |
| سقف دقیق | متن نهایی با provenance/warning/frame شمرده شود؛ ورودی کل و سقف خروجی در محدودیت مدل جا بگیرند |
| approval/revision | approval hash نسخهٔ قبلی روی ویرایش جدید قبول نشود؛ optimistic concurrency جلوی overwrite هم‌زمان را بگیرد |
| contradiction | دو policy ناسازگار فعال، تعارض مسدودکننده ایجاد کنند؛ هیچ‌کدام پنهانی حذف نشود |
| recovery | restart ingest و invalidation را از commit بازسازی کند؛ side effect با نتیجهٔ نامعلوم تکرار کور نداشته باشد |
| NotebookLM | هر claim پذیرفته‌شده به منبع/نسخهٔ اصلی وصل باشد؛ reference نامشخص unverified بماند |

برای سنجش retrieval، مجموعهٔ development، مجموعهٔ منجمد اضافی و موارد تزریق دستور/تعارض/ACL جدا نگهداری شوند. gold anchorها فقط وارد evaluator شوند. علاوه بر recall شواهد، precision، نرخ کافی اعلام‌شدهٔ اشتباه، نرخ شکاف پنهان، latency، توکن prompt کامل، هزینهٔ review و پذیرش نهایی گزارش شوند. آستانه‌ها پیش از آزمون پایلوت با owner تعیین شوند؛ این سند عدد ساختگی برای آمادگی نمی‌گذارد.

ترتیب ساخت پیشنهادی: ابتدا registry/version/lifecycle و authorization؛ سپس adapter selector و exact packing؛ سپس verifier/contradiction/invalidation؛ پس از آن اتصال کنترل‌شده به runtime و تجربهٔ UI؛ در پایان ارزیابی پایلوت و تصمیم دربارهٔ semantic index. مهاجرت یادداشت‌های محلی بدون scope معلوم، باید آن‌ها را به staging فاقد authority ببرد؛ نسبت دادن خودکار همهٔ یادداشت‌های قدیمی به `alacrity-flux` مجاز نیست.

## ۱۶. منابع داخلی این مشخصات

- وایت‌پیپر PDF نسخهٔ ۱٫۰، متن استخراجی `tmp/pdfs/whitepaper-readable.md`؛ صفحات ۸ تا ۱۲ برای قرارداد، حافظه، مجوز و هزینه؛ صفحهٔ ۱۷ برای فاصلهٔ دمو تا محصول.
- `README.md` و `src/flux/storage/workspace.py`، `src/flux/local_agents/runtime.py` و `src/flux/api/app.py` برای رفتار فعلی ۰٫۴.
- `experiments/jev_v2_rewrite_20261001/optimized_v2.py`، `REPORT.fa.md`، `summary.json` و `frozen_candidate.json` برای selector و مرز شواهد benchmark.
- `C:/Users/xio/.codex/skills/project-evidence-rag-v2/SKILL.md` برای قرارداد helper مستقل، سقف worker evidence، namespace و محدودیت semantic sufficiency.

خروجی این سند مشخصات الگوریتم و قرارداد قابل پیاده‌سازی است. ثبت دفتر زندهٔ NotebookLM و noteهای همین پروژه در تحویل پژوهشی پروژه گزارش می‌شوند؛ وجود آن‌ها پیاده‌سازی lifecycle و JEV مقصد در runtime را ثابت نمی‌کند.
