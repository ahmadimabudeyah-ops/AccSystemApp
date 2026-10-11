# المخرج 3: وثيقة الـ API الكاملة (236 مسارًا — آخر جرد ساكن للكود)

## 1. العقد الموحد لكل Endpoints

- **الأساس:** `/api/v1` + JWT Bearer + هيدر `X-Tenant-ID` إجباري (400 عند غيابه، 403 عند تزويره مقابل مستأجر التوكن).
- **الاستجابة:** نجاح `{"data": {...}, "page"?}` — خطأ `{"error": {"code", "message"}}`.
- **الحالات:** 200/201 نجاح، 200 مع `DUPLICATE_EVENT` لإعادة المكرر، 400 تحقق، 401 مصادقة، 403 صلاحية/فصل مهام/تزوير مستأجر، 404 غياب، 409 تعارض (فترة مغلقة/تجاوز حد/مكرر عكس).
- **Idempotency-Key:** يُقبل في POST الحساسة ويُخزن كمفتاح الحدث.
- **الترقيم:** `?page=` (50/صفحة) + فلترة `?status=&entity_id=&q=` + فرز زمني تنازلي.
- **الإصدار:** بادئة `/v1`؛ كسر التوافق = `/v2` مع بقاء v1.
- **التحديد (Rate Limit):** توصية مرحلة 2 (100/دقيقة توكن) — غير مفعل في v1 المحلي.
- **OpenAPI:** يُولّد من المسارات أدناه (جدول التطابق الكامل في §3).

### تدفق المصادقة

```
POST /api/v1/auth/login {username|email, password} + X-Tenant-ID (UUID أو رمز مثل DEMO)
→ 200 {access_token (15د), refresh_token, permissions[]}
GET /api/v1/auth/me → {user_id, tenant_id, permissions}
POST /api/v1/auth/refresh (برمز التحديث) → access جديد
ملاحظة: لا يوجد logout خادمي (التوكنات عديمة الحالة) — الخروج = حذف التوكن + إلغاء الجلسة (جدول user_sessions جاهز للإلغاء الخادمي في مرحلة 2).
```

### مثال معياري: إنشاء قيد وترحيله

```http
POST /api/v1/journal-entries  Idempotency-Key: <uuid>
{"entity_id":"...","journal_id":"...","document_date":"2026-01-05","posting_date":"2026-01-05",
 "description":"بيع نقدي","source_event_key":"sales.inv.1001.v1",
 "lines":[{"account_id":"<101001>","debit":116},{"account_id":"<4010>","credit":100},{"account_id":"<2140>","credit":16}]}
→ 201 {"data": {"id":"...","status":"draft","total_debit":116,...}}
POST /api/v1/journal-entries/<id>/post  (بمستخدم ≠ الصانع)
→ 200 {"data": {"official_number":"GEN-2026-000123","status":"posted"}}
الأخطاء: 422 UNBALANCED | 409 PERIOD_CLOSED | 403 SELF_APPROVAL | 200 DUPLICATE_EVENT
الصلاحيات: journals.post للترحيل، journals.reverse للعكس، journals.approve للاعتماد.
```

## 2. جدول المسارات الكامل (159)

**Auth (3):** POST login, GET me, POST refresh.
**Tenants (3):** GET /tenants, GET /tenants/<id>/entities, GET /tenants/entities/<id>/branches.
**Accounts (6):** GET/POST /accounts, GET/PUT/DELETE /accounts/<id>, GET /accounts/tree.
**Journals (2)+Entries (9):** GET/POST /journals؛ GET/POST /journal-entries، GET <id> و/lines و/approvals و/comments، POST <id>/post و/reverse و/approve و/comments و/attachments.
**Users/Roles (6):** GET/POST /users، GET/PUT /users/<id>، POST <id>/deactivate، GET /roles.
**Parties (5):** GET/POST /parties (+?type=customer|supplier للمسارين المختصرين)، GET/PUT <id>، GET <id>/statement (كشف من المرحّل).
**Products (8):** uoms, product-categories, products CRUD, warehouses (+locations).
**Inventory (4):** GET/POST moves، POST moves/<id>/done (منع السالب + متوسط)، GET quants.
**Sales (19):** quotations (+convert)، orders (+invoice)، deliveries (+confirm)، invoices (+post)، payments (+post+allocate)، returns (+post)، credit-notes (+post)، payment-terms، einvoicing-queue.
**Purchases (11):** requests (+approve)، orders، receipts (+confirm)، bills (+post)، payments (+post+allocate).
**Treasury (11):** cash-boxes (+detail برصيد حي)، cash-transactions (+post)، banks، bank-accounts، checks (+PUT حالة)، transfers.
**Assets/Taxes/Currencies (8):** asset-categories، assets (+detail بصافي + depreciate ثابت/متناقص)، taxes، currencies.
**Payroll (8):** employees، payroll-runs (+post)، run detail بقسائم، loans، leaves.
**Education (7):** students، guardians، fee-contracts (+post)، contract detail بأقساط، pay installment.
**Projects (12):** projects (+costs/revenues)، budgets (+variance مخطط/فعلي)، audit-logs، dimensions، fiscal-years، fiscal-periods (+close/+reopen)، policies، aging-receivables، tax-summary.
**Reports (7):** trial-balance، ledger، balance-sheet، income-statement، account-balance، dashboard-summary، fiscal-periods.

## 3. الفجوات الصريحة (مرحلة 2 — بلا تجميل)

| المطلوب | الوضع الحالي | البديل العامل |
|---|---|---|
| logout خادمي | client-side فقط | إلغاء الجلسات عبر user_sessions (الجدول جاهز) |
| inventory adjustments/counts/transfers/scrap API | قراءة/حركة/أرصدة فقط | التسويات عبر قيود التعديل + حركات يدوية |
| bank-statements/reconciliation API | غير موجود | كشف + مطابقة يدوية بالصفحات |
| payroll contracts endpoint | شروط الراتب على الموظف مباشرة | كافٍ لشركات ≤200 موظف |
| reports cash-flow / aging-payables | غير موجود | التدفق من دفتر النقدية + أعمار مدينة فقط |
| settings backend (general/company/branches write) | قراءة فروع فقط | الإعدادات عبر tenant/entity_settings مباشرة |
| sales debit-notes / purchase returns API | غير موجود | إشعارات دائنة + مرتجعات بيع تغطي 90% |
| asset disposal / transfers API | غير موجود | قيد استبعاد يدوي + تغيير حالة |
| tax returns filing | ملخص الالتزام فقط | الإقرار الورقي من الملخص |
