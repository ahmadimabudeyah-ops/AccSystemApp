# db/sql — ترتيب التطبيق

المصدر المعتمد للمخطط هو ملفات `phase*` بالترتيب:
1. `phase1_foundation.sql` (المستأجرون/المستخدمون/الكيانات)
2. `phase2_policies_periods.sql` (السياسات/الفترات)
3. `phase3_accounts_dimensions.sql` (الدليل/الأبعاد)
4. `phase4_engine.sql` (المحرك المحاسبي)
5. `phase5_parties.sql` (الأطراف)
6. `phase6_products_inventory.sql` (الأصناف/المخزون)
7. `phase7_sales.sql` (المبيعات)
8. `phase8_treasury_assets_taxes.sql` (الخزينة/الأصول/الضرائب)
9. `phase9_purchases.sql` (المشتريات)
10. `phase10_payroll.sql` (الرواتب)
11. `phase11_education.sql` (التعليم)
12. `phase12_projects_budgets_audit.sql` (المشاريع/الموازنات/التدقيق)
13. `phase13_procurement_docs.sql` (مستندات المشتريات)
14. `seed_engine_permissions.sql` + `seed_module_permissions.sql` + `seed_rbac_permissions.sql`
15. `fix_*.sql` (إصلاحات لاحقة — تُطبق مرة واحدة بالترتيب الأبجدي)

ملفات `00_*` إلى `34_*` مسودات مبكرة **لا تُطبق** (حلّت محلها ملفات المراحل).
`phase4_engine.sql` يتضمن الدوال والمشغلات والفهارس وRLS الخاصة بالمحرك.

> التهيئة في Docker تتم عبر خدمة `db-init` في `docker-compose.yml` التي تطبق هذا الترتيب صراحة.
> مجلد `./db/sql` مربوط إلى `/opt/sql` فقط ولا يُنفذ تلقائيًا عبر `/docker-entrypoint-initdb.d`.
