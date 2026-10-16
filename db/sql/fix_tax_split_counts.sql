-- fix_tax_split_counts.sql — فصل ضريبة المدخلات/المخرجات + حساب فروقات الجرد + أعمدة إقرار.
-- additive فقط: INSERT ... WHERE NOT EXISTS / ADD COLUMN IF NOT EXISTS.

-- 1) حساب 2141 (ضريبة مدخلات قابلة للاسترداد) شقيق 2140 تحت نفس الأب لكل كيان
INSERT INTO accounts (tenant_id, entity_id, code, name_ar, name_en, parent_id, level, path,
    is_leaf, account_type, control_type, normal_balance, is_postable, is_reconcilable,
    require_partner, require_dimensions, allow_manual, valid_from, is_active, status,
    hierarchy_role, created_by, updated_by)
SELECT a.tenant_id, a.entity_id, '2141', 'ضريبة مدخلات قابلة للاسترداد', 'VAT recoverable',
    a.parent_id, a.level, REPLACE(a.path, '2140', '2141'),
    TRUE, 'asset', 'general', 'debit', TRUE, FALSE,
    FALSE, FALSE, TRUE, CURRENT_DATE, TRUE, 'active',
    a.hierarchy_role, a.created_by, a.updated_by
FROM accounts a
WHERE a.code = '2140' AND a.is_deleted = FALSE
  AND NOT EXISTS (SELECT 1 FROM accounts x WHERE x.entity_id = a.entity_id AND x.code = '2141' AND x.is_deleted = FALSE);

-- 2) حساب 5590 (فروقات الجرد) شقيق 5010 تحت نفس الأب لكل كيان
INSERT INTO accounts (tenant_id, entity_id, code, name_ar, name_en, parent_id, level, path,
    is_leaf, account_type, control_type, normal_balance, is_postable, is_reconcilable,
    require_partner, require_dimensions, allow_manual, valid_from, is_active, status,
    hierarchy_role, created_by, updated_by)
SELECT a.tenant_id, a.entity_id, '5590', 'فروقات الجرد', 'Inventory adjustments',
    a.parent_id, a.level, REPLACE(a.path, '5010', '5590'),
    TRUE, 'expense', 'general', 'debit', TRUE, FALSE,
    FALSE, FALSE, TRUE, CURRENT_DATE, TRUE, 'active',
    a.hierarchy_role, a.created_by, a.updated_by
FROM accounts a
WHERE a.code = '5010' AND a.is_deleted = FALSE
  AND NOT EXISTS (SELECT 1 FROM accounts x WHERE x.entity_id = a.entity_id AND x.code = '5590' AND x.is_deleted = FALSE);

-- 3) أعمدة تفصيل الإقرار الضريبي
ALTER TABLE tax_returns ADD COLUMN IF NOT EXISTS purchase_total NUMERIC(18,3) NOT NULL DEFAULT 0;
ALTER TABLE tax_returns ADD COLUMN IF NOT EXISTS input_tax NUMERIC(18,3) NOT NULL DEFAULT 0;
ALTER TABLE tax_returns ADD COLUMN IF NOT EXISTS output_tax NUMERIC(18,3) NOT NULL DEFAULT 0;
ALTER TABLE tax_returns ADD COLUMN IF NOT EXISTS net_due NUMERIC(18,3) NOT NULL DEFAULT 0;

-- 4) أثر تدقيق ضريبة بنود فواتير الموردين
ALTER TABLE vendor_bill_lines ADD COLUMN IF NOT EXISTS tax_id UUID NULL;
ALTER TABLE vendor_bill_lines ADD COLUMN IF NOT EXISTS tax_rate NUMERIC(7,4) NOT NULL DEFAULT 0;
ALTER TABLE vendor_bill_lines ADD COLUMN IF NOT EXISTS tax_amount NUMERIC(18,3) NOT NULL DEFAULT 0;

-- 5) ضريبة مرتجع المورد المعكوسة
ALTER TABLE vendor_returns ADD COLUMN IF NOT EXISTS vat_amount NUMERIC(18,3) NOT NULL DEFAULT 0;
