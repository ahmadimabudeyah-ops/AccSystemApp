-- fix_counts_settings_match.sql — إكمال النواقص دون حذف شيء.
-- يُطبق عبر db-init (fix_*.sql) — كل العبارات IF NOT EXISTS لسلامة إعادة التشغيل.
-- يقابله ترحيل Alembic 0003_counts_settings لنشر flask-db.

-- 1) اسم المستخدم الكامل (الملف الشخصي)
ALTER TABLE users ADD COLUMN IF NOT EXISTS full_name TEXT;

-- 2) الرقم الضريبي للمستأجر (بيانات الشركة)
ALTER TABLE tenants ADD COLUMN IF NOT EXISTS tax_id VARCHAR(50);

-- 3) سعر الصرف على فواتير الموردين
ALTER TABLE vendor_bills ADD COLUMN IF NOT EXISTS exchange_rate NUMERIC(18, 10) NOT NULL DEFAULT 1;
ALTER TABLE vendor_payments ADD COLUMN IF NOT EXISTS exchange_rate NUMERIC(18, 10) NOT NULL DEFAULT 1;
ALTER TABLE customer_payments ADD COLUMN IF NOT EXISTS exchange_rate NUMERIC(18, 10) NOT NULL DEFAULT 1;

-- 4) دورة الجرد الفعلي: رأس + بنود
CREATE TABLE IF NOT EXISTS stock_counts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE RESTRICT,
    doc_number VARCHAR(50) NOT NULL,
    warehouse_id UUID NOT NULL REFERENCES warehouses(id) ON DELETE RESTRICT,
    count_date DATE NOT NULL DEFAULT CURRENT_DATE,
    status VARCHAR(30) NOT NULL DEFAULT 'draft',
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID,
    updated_by UUID,
    version INTEGER NOT NULL DEFAULT 1,
    deleted_at TIMESTAMPTZ,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (tenant_id, entity_id, doc_number)
);
CREATE INDEX IF NOT EXISTS ix_stock_counts_entity_status ON stock_counts(entity_id, status);

CREATE TABLE IF NOT EXISTS stock_count_lines (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    count_id UUID NOT NULL REFERENCES stock_counts(id) ON DELETE CASCADE,
    line_number INTEGER NOT NULL,
    product_id UUID NOT NULL REFERENCES products(id) ON DELETE RESTRICT,
    location_id UUID REFERENCES locations(id) ON DELETE RESTRICT,
    system_qty NUMERIC(18, 6) NOT NULL DEFAULT 0,
    counted_qty NUMERIC(18, 6),
    unit_cost NUMERIC(18, 6) NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID,
    updated_by UUID,
    version INTEGER NOT NULL DEFAULT 1,
    deleted_at TIMESTAMPTZ,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (count_id, line_number)
);
CREATE INDEX IF NOT EXISTS ix_count_lines_count ON stock_count_lines(count_id);

-- 5) سجل المطابقة الثلاثية المعتمدة
CREATE TABLE IF NOT EXISTS bill_matches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE RESTRICT,
    bill_id UUID NOT NULL REFERENCES vendor_bills(id) ON DELETE RESTRICT,
    matched BOOLEAN NOT NULL,
    details JSONB NOT NULL DEFAULT '[]',
    matched_by UUID,
    matched_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID,
    updated_by UUID,
    version INTEGER NOT NULL DEFAULT 1,
    deleted_at TIMESTAMPTZ,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE INDEX IF NOT EXISTS ix_bill_matches_bill ON bill_matches(bill_id);
