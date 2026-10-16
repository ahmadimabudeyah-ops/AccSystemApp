-- fix_missing_modules.sql — الجداول الغائبة من تغطية MASTER (تمويل/توحيد جزئي/تكاملات/تفاصيل).
-- additive فقط: CREATE TABLE IF NOT EXISTS + سياسات RLS + touch triggers + فهارس + Seed مرجعي.

-- ============ مرجعية عامة (بلا tenant — كتالوج عمومي كـ plans/permissions) ============
CREATE TABLE IF NOT EXISTS countries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code CHAR(2) NOT NULL UNIQUE, name_ar VARCHAR(100) NOT NULL, name_en VARCHAR(100) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    version INTEGER NOT NULL DEFAULT 1, is_deleted BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE TABLE IF NOT EXISTS cities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    country_id UUID NOT NULL REFERENCES countries(id) ON DELETE RESTRICT,
    code VARCHAR(20) NOT NULL, name_ar VARCHAR(100) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    version INTEGER NOT NULL DEFAULT 1, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (country_id, code)
);
CREATE INDEX IF NOT EXISTS ix_cities_country ON cities(country_id);

-- ============ مشتريات: اتفاقيات ============
CREATE TABLE IF NOT EXISTS purchase_agreements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id UUID NOT NULL,
    entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE RESTRICT,
    doc_number VARCHAR(50) NOT NULL, supplier_id UUID NOT NULL REFERENCES parties(id) ON DELETE RESTRICT,
    start_on DATE NOT NULL, ends_on DATE NOT NULL, status VARCHAR(30) NOT NULL DEFAULT 'draft',
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID, updated_by UUID, version INTEGER NOT NULL DEFAULT 1,
    deleted_at TIMESTAMPTZ, deleted_by UUID, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (tenant_id, entity_id, doc_number)
);
CREATE TABLE IF NOT EXISTS purchase_agreement_lines (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id UUID NOT NULL,
    agreement_id UUID NOT NULL REFERENCES purchase_agreements(id) ON DELETE CASCADE,
    line_number INTEGER NOT NULL, product_id UUID NOT NULL REFERENCES products(id) ON DELETE RESTRICT,
    qty NUMERIC(18,6) NOT NULL, unit_price NUMERIC(18,3) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID, updated_by UUID, version INTEGER NOT NULL DEFAULT 1,
    deleted_at TIMESTAMPTZ, deleted_by UUID, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (agreement_id, line_number)
);

-- ============ مبيعات: إشعارات مدينة ============
CREATE TABLE IF NOT EXISTS debit_notes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id UUID NOT NULL,
    entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE RESTRICT,
    doc_number VARCHAR(50) NOT NULL, customer_id UUID NOT NULL REFERENCES parties(id) ON DELETE RESTRICT,
    note_date DATE NOT NULL DEFAULT CURRENT_DATE, reason TEXT NOT NULL DEFAULT '',
    currency_id CHAR(3) NOT NULL DEFAULT 'JOD',
    subtotal NUMERIC(18,3) NOT NULL DEFAULT 0, tax_total NUMERIC(18,3) NOT NULL DEFAULT 0,
    grand_total NUMERIC(18,3) NOT NULL DEFAULT 0, status VARCHAR(30) NOT NULL DEFAULT 'draft',
    journal_entry_id UUID REFERENCES journal_entries(id) ON DELETE RESTRICT,
    event_key VARCHAR(200),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID, updated_by UUID, version INTEGER NOT NULL DEFAULT 1,
    deleted_at TIMESTAMPTZ, deleted_by UUID, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (tenant_id, entity_id, doc_number)
);
CREATE TABLE IF NOT EXISTS debit_note_lines (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id UUID NOT NULL,
    note_id UUID NOT NULL REFERENCES debit_notes(id) ON DELETE CASCADE,
    line_number INTEGER NOT NULL, product_id UUID REFERENCES products(id) ON DELETE RESTRICT,
    qty NUMERIC(18,6) NOT NULL DEFAULT 1, unit_price NUMERIC(18,3) NOT NULL,
    discount_pct NUMERIC(7,4) NOT NULL DEFAULT 0, tax_id UUID REFERENCES taxes(id) ON DELETE RESTRICT,
    line_total NUMERIC(18,3) NOT NULL DEFAULT 0,
    account_id UUID REFERENCES accounts(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID, updated_by UUID, version INTEGER NOT NULL DEFAULT 1,
    deleted_at TIMESTAMPTZ, deleted_by UUID, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (note_id, line_number)
);

-- ============ خزينة: مطابقة + دفاتر شيكات ============
CREATE TABLE IF NOT EXISTS bank_reconciliations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id UUID NOT NULL,
    entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE RESTRICT,
    statement_id UUID NOT NULL REFERENCES bank_statements(id) ON DELETE RESTRICT,
    reconciled_on DATE NOT NULL DEFAULT CURRENT_DATE, status VARCHAR(30) NOT NULL DEFAULT 'draft',
    matched_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID, updated_by UUID, version INTEGER NOT NULL DEFAULT 1,
    deleted_at TIMESTAMPTZ, deleted_by UUID, is_deleted BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE TABLE IF NOT EXISTS bank_reconciliation_lines (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id UUID NOT NULL,
    reconciliation_id UUID NOT NULL REFERENCES bank_reconciliations(id) ON DELETE CASCADE,
    statement_line_id UUID NOT NULL REFERENCES bank_statement_lines(id) ON DELETE RESTRICT,
    entry_id UUID REFERENCES journal_entries(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID, updated_by UUID, version INTEGER NOT NULL DEFAULT 1,
    deleted_at TIMESTAMPTZ, deleted_by UUID, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (reconciliation_id, statement_line_id)
);
CREATE TABLE IF NOT EXISTS check_books (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id UUID NOT NULL,
    entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE RESTRICT,
    bank_account_id UUID NOT NULL REFERENCES bank_accounts(id) ON DELETE RESTRICT,
    code VARCHAR(50) NOT NULL, start_no VARCHAR(50) NOT NULL, end_no VARCHAR(50) NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID, updated_by UUID, version INTEGER NOT NULL DEFAULT 1,
    deleted_at TIMESTAMPTZ, deleted_by UUID, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (tenant_id, entity_id, code)
);

-- ============ أصول: نقل/استبعاد/إعادة تقييم/جدول إهلاك ============
CREATE TABLE IF NOT EXISTS asset_transfers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id UUID NOT NULL,
    entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE RESTRICT,
    asset_id UUID NOT NULL REFERENCES assets(id) ON DELETE RESTRICT,
    transfer_date DATE NOT NULL DEFAULT CURRENT_DATE,
    from_text VARCHAR(200), to_text VARCHAR(200) NOT NULL, reason TEXT,
    status VARCHAR(30) NOT NULL DEFAULT 'posted',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID, updated_by UUID, version INTEGER NOT NULL DEFAULT 1,
    deleted_at TIMESTAMPTZ, deleted_by UUID, is_deleted BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE TABLE IF NOT EXISTS asset_disposals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id UUID NOT NULL,
    entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE RESTRICT,
    asset_id UUID NOT NULL REFERENCES assets(id) ON DELETE RESTRICT,
    disposal_date DATE NOT NULL DEFAULT CURRENT_DATE,
    proceeds NUMERIC(18,3) NOT NULL DEFAULT 0, gain_loss NUMERIC(18,3) NOT NULL DEFAULT 0,
    journal_entry_id UUID REFERENCES journal_entries(id) ON DELETE RESTRICT,
    status VARCHAR(30) NOT NULL DEFAULT 'posted',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID, updated_by UUID, version INTEGER NOT NULL DEFAULT 1,
    deleted_at TIMESTAMPTZ, deleted_by UUID, is_deleted BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE TABLE IF NOT EXISTS asset_revaluations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id UUID NOT NULL,
    entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE RESTRICT,
    asset_id UUID NOT NULL REFERENCES assets(id) ON DELETE RESTRICT,
    reval_date DATE NOT NULL DEFAULT CURRENT_DATE,
    old_cost NUMERIC(18,3) NOT NULL, new_cost NUMERIC(18,3) NOT NULL,
    journal_entry_id UUID REFERENCES journal_entries(id) ON DELETE RESTRICT,
    status VARCHAR(30) NOT NULL DEFAULT 'posted',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID, updated_by UUID, version INTEGER NOT NULL DEFAULT 1,
    deleted_at TIMESTAMPTZ, deleted_by UUID, is_deleted BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE TABLE IF NOT EXISTS asset_depreciation_schedules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id UUID NOT NULL,
    asset_id UUID NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
    period_no INTEGER NOT NULL, due_on DATE NOT NULL, amount NUMERIC(18,3) NOT NULL,
    entry_id UUID REFERENCES journal_entries(id) ON DELETE RESTRICT,
    status VARCHAR(30) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID, updated_by UUID, version INTEGER NOT NULL DEFAULT 1,
    deleted_at TIMESTAMPTZ, deleted_by UUID, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (asset_id, period_no)
);

-- ============ تمويل: قروض ============
CREATE TABLE IF NOT EXISTS loans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id UUID NOT NULL,
    entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE RESTRICT,
    code VARCHAR(50) NOT NULL, lender VARCHAR(200) NOT NULL,
    principal NUMERIC(18,3) NOT NULL, annual_rate NUMERIC(7,4) NOT NULL DEFAULT 0,
    start_on DATE NOT NULL, months INTEGER NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID, updated_by UUID, version INTEGER NOT NULL DEFAULT 1,
    deleted_at TIMESTAMPTZ, deleted_by UUID, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (tenant_id, entity_id, code)
);
CREATE TABLE IF NOT EXISTS loan_schedules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id UUID NOT NULL,
    loan_id UUID NOT NULL REFERENCES loans(id) ON DELETE CASCADE,
    period_no INTEGER NOT NULL, due_on DATE NOT NULL,
    payment NUMERIC(18,3) NOT NULL, principal_part NUMERIC(18,3) NOT NULL,
    interest_part NUMERIC(18,3) NOT NULL, remaining NUMERIC(18,3) NOT NULL,
    entry_id UUID REFERENCES journal_entries(id) ON DELETE RESTRICT,
    status VARCHAR(30) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID, updated_by UUID, version INTEGER NOT NULL DEFAULT 1,
    deleted_at TIMESTAMPTZ, deleted_by UUID, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (loan_id, period_no)
);
CREATE TABLE IF NOT EXISTS loan_transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id UUID NOT NULL,
    loan_id UUID NOT NULL REFERENCES loans(id) ON DELETE CASCADE,
    txn_date DATE NOT NULL DEFAULT CURRENT_DATE, kind VARCHAR(30) NOT NULL,
    amount NUMERIC(18,3) NOT NULL,
    journal_entry_id UUID REFERENCES journal_entries(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID, updated_by UUID, version INTEGER NOT NULL DEFAULT 1,
    deleted_at TIMESTAMPTZ, deleted_by UUID, is_deleted BOOLEAN NOT NULL DEFAULT FALSE
);

-- ============ ضرائب: مجموعات/أسعار/سداد/اقتطاع ============
CREATE TABLE IF NOT EXISTS tax_groups (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id UUID NOT NULL,
    entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE RESTRICT,
    code VARCHAR(50) NOT NULL, name_ar VARCHAR(200) NOT NULL, is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID, updated_by UUID, version INTEGER NOT NULL DEFAULT 1,
    deleted_at TIMESTAMPTZ, deleted_by UUID, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (tenant_id, entity_id, code)
);
CREATE TABLE IF NOT EXISTS tax_rates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id UUID NOT NULL,
    group_id UUID NOT NULL REFERENCES tax_groups(id) ON DELETE CASCADE,
    tax_id UUID NOT NULL REFERENCES taxes(id) ON DELETE RESTRICT,
    valid_from DATE NOT NULL DEFAULT CURRENT_DATE, valid_to DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID, updated_by UUID, version INTEGER NOT NULL DEFAULT 1,
    deleted_at TIMESTAMPTZ, deleted_by UUID, is_deleted BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE TABLE IF NOT EXISTS tax_payments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id UUID NOT NULL,
    entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE RESTRICT,
    tax_id UUID NOT NULL REFERENCES taxes(id) ON DELETE RESTRICT,
    pay_date DATE NOT NULL DEFAULT CURRENT_DATE, amount NUMERIC(18,3) NOT NULL,
    period_code VARCHAR(20), journal_entry_id UUID REFERENCES journal_entries(id) ON DELETE RESTRICT,
    status VARCHAR(30) NOT NULL DEFAULT 'draft',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID, updated_by UUID, version INTEGER NOT NULL DEFAULT 1,
    deleted_at TIMESTAMPTZ, deleted_by UUID, is_deleted BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE TABLE IF NOT EXISTS withholding_taxes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id UUID NOT NULL,
    entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE RESTRICT,
    party_id UUID NOT NULL REFERENCES parties(id) ON DELETE RESTRICT,
    base_amount NUMERIC(18,3) NOT NULL, rate NUMERIC(7,4) NOT NULL,
    amount NUMERIC(18,3) NOT NULL, doc_ref VARCHAR(100),
    status VARCHAR(30) NOT NULL DEFAULT 'draft',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID, updated_by UUID, version INTEGER NOT NULL DEFAULT 1,
    deleted_at TIMESTAMPTZ, deleted_by UUID, is_deleted BOOLEAN NOT NULL DEFAULT FALSE
);

-- ============ رواتب: عقود/هياكل/إجازات/حضور ============
CREATE TABLE IF NOT EXISTS employee_contracts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id UUID NOT NULL,
    employee_id UUID NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    start_on DATE NOT NULL, end_on DATE, basic_salary NUMERIC(18,3) NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID, updated_by UUID, version INTEGER NOT NULL DEFAULT 1,
    deleted_at TIMESTAMPTZ, deleted_by UUID, is_deleted BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE TABLE IF NOT EXISTS salary_structures (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id UUID NOT NULL,
    entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE RESTRICT,
    code VARCHAR(50) NOT NULL, name_ar VARCHAR(200) NOT NULL, is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID, updated_by UUID, version INTEGER NOT NULL DEFAULT 1,
    deleted_at TIMESTAMPTZ, deleted_by UUID, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (tenant_id, entity_id, code)
);
CREATE TABLE IF NOT EXISTS salary_structure_lines (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id UUID NOT NULL,
    structure_id UUID NOT NULL REFERENCES salary_structures(id) ON DELETE CASCADE,
    code VARCHAR(50) NOT NULL, name_ar VARCHAR(200) NOT NULL, kind VARCHAR(30) NOT NULL DEFAULT 'earning',
    formula VARCHAR(200) NOT NULL DEFAULT 'fixed', amount NUMERIC(18,3) NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID, updated_by UUID, version INTEGER NOT NULL DEFAULT 1,
    deleted_at TIMESTAMPTZ, deleted_by UUID, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (structure_id, code)
);
CREATE TABLE IF NOT EXISTS leave_types (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id UUID NOT NULL,
    entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE RESTRICT,
    code VARCHAR(50) NOT NULL, name_ar VARCHAR(200) NOT NULL, annual_days INTEGER NOT NULL DEFAULT 14,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID, updated_by UUID, version INTEGER NOT NULL DEFAULT 1,
    deleted_at TIMESTAMPTZ, deleted_by UUID, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (tenant_id, entity_id, code)
);
CREATE TABLE IF NOT EXISTS leave_balances (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id UUID NOT NULL,
    employee_id UUID NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    leave_type_id UUID NOT NULL REFERENCES leave_types(id) ON DELETE RESTRICT,
    year INTEGER NOT NULL, entitled NUMERIC(10,2) NOT NULL DEFAULT 0,
    used NUMERIC(10,2) NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID, updated_by UUID, version INTEGER NOT NULL DEFAULT 1,
    deleted_at TIMESTAMPTZ, deleted_by UUID, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (employee_id, leave_type_id, year)
);
CREATE TABLE IF NOT EXISTS attendance_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id UUID NOT NULL,
    employee_id UUID NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    work_date DATE NOT NULL, status VARCHAR(30) NOT NULL DEFAULT 'present',
    hours NUMERIC(6,2) NOT NULL DEFAULT 8,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID, updated_by UUID, version INTEGER NOT NULL DEFAULT 1,
    deleted_at TIMESTAMPTZ, deleted_by UUID, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (employee_id, work_date)
);

-- ============ تعليم: هيكل أكاديمي وهياكل رسوم ============
CREATE TABLE IF NOT EXISTS academic_years (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id UUID NOT NULL,
    entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE RESTRICT,
    code VARCHAR(20) NOT NULL, starts_on DATE NOT NULL, ends_on DATE NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID, updated_by UUID, version INTEGER NOT NULL DEFAULT 1,
    deleted_at TIMESTAMPTZ, deleted_by UUID, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (tenant_id, entity_id, code)
);
CREATE TABLE IF NOT EXISTS academic_terms (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id UUID NOT NULL,
    year_id UUID NOT NULL REFERENCES academic_years(id) ON DELETE CASCADE,
    code VARCHAR(20) NOT NULL, name_ar VARCHAR(200) NOT NULL,
    starts_on DATE NOT NULL, ends_on DATE NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID, updated_by UUID, version INTEGER NOT NULL DEFAULT 1,
    deleted_at TIMESTAMPTZ, deleted_by UUID, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (year_id, code)
);
CREATE TABLE IF NOT EXISTS grade_levels (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id UUID NOT NULL,
    entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE RESTRICT,
    code VARCHAR(20) NOT NULL, name_ar VARCHAR(200) NOT NULL, order_no INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID, updated_by UUID, version INTEGER NOT NULL DEFAULT 1,
    deleted_at TIMESTAMPTZ, deleted_by UUID, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (tenant_id, entity_id, code)
);
CREATE TABLE IF NOT EXISTS fee_structures (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id UUID NOT NULL,
    entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE RESTRICT,
    code VARCHAR(50) NOT NULL, name_ar VARCHAR(200) NOT NULL,
    academic_year VARCHAR(20) NOT NULL DEFAULT '2026',
    status VARCHAR(30) NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID, updated_by UUID, version INTEGER NOT NULL DEFAULT 1,
    deleted_at TIMESTAMPTZ, deleted_by UUID, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (tenant_id, entity_id, code)
);
CREATE TABLE IF NOT EXISTS fee_structure_lines (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id UUID NOT NULL,
    structure_id UUID NOT NULL REFERENCES fee_structures(id) ON DELETE CASCADE,
    grade_code VARCHAR(20) NOT NULL, amount NUMERIC(18,3) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID, updated_by UUID, version INTEGER NOT NULL DEFAULT 1,
    deleted_at TIMESTAMPTZ, deleted_by UUID, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (structure_id, grade_code)
);

-- ============ مشاريع وموازنات: مراحل/مهام/نسخ/مناقلات/تنبؤات ============
CREATE TABLE IF NOT EXISTS project_phases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id UUID NOT NULL,
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    code VARCHAR(50) NOT NULL, name_ar VARCHAR(200) NOT NULL,
    starts_on DATE, ends_on DATE, status VARCHAR(30) NOT NULL DEFAULT 'planned',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID, updated_by UUID, version INTEGER NOT NULL DEFAULT 1,
    deleted_at TIMESTAMPTZ, deleted_by UUID, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (project_id, code)
);
CREATE TABLE IF NOT EXISTS project_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id UUID NOT NULL,
    phase_id UUID NOT NULL REFERENCES project_phases(id) ON DELETE CASCADE,
    code VARCHAR(50) NOT NULL, name_ar VARCHAR(200) NOT NULL,
    planned_cost NUMERIC(18,3) NOT NULL DEFAULT 0, progress_pct NUMERIC(5,2) NOT NULL DEFAULT 0,
    status VARCHAR(30) NOT NULL DEFAULT 'planned',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID, updated_by UUID, version INTEGER NOT NULL DEFAULT 1,
    deleted_at TIMESTAMPTZ, deleted_by UUID, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (phase_id, code)
);
CREATE TABLE IF NOT EXISTS budget_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id UUID NOT NULL,
    budget_id UUID NOT NULL REFERENCES budgets(id) ON DELETE CASCADE,
    version_no INTEGER NOT NULL, notes TEXT, status VARCHAR(30) NOT NULL DEFAULT 'draft',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID, updated_by UUID, version INTEGER NOT NULL DEFAULT 1,
    deleted_at TIMESTAMPTZ, deleted_by UUID, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (budget_id, version_no)
);
CREATE TABLE IF NOT EXISTS budget_transfers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id UUID NOT NULL,
    budget_id UUID NOT NULL REFERENCES budgets(id) ON DELETE CASCADE,
    from_account_id UUID NOT NULL REFERENCES accounts(id) ON DELETE RESTRICT,
    to_account_id UUID NOT NULL REFERENCES accounts(id) ON DELETE RESTRICT,
    amount NUMERIC(18,3) NOT NULL, reason TEXT, status VARCHAR(30) NOT NULL DEFAULT 'draft',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID, updated_by UUID, version INTEGER NOT NULL DEFAULT 1,
    deleted_at TIMESTAMPTZ, deleted_by UUID, is_deleted BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE TABLE IF NOT EXISTS forecasts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id UUID NOT NULL,
    entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE RESTRICT,
    code VARCHAR(50) NOT NULL, name_ar VARCHAR(200) NOT NULL,
    year INTEGER NOT NULL, status VARCHAR(30) NOT NULL DEFAULT 'draft',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID, updated_by UUID, version INTEGER NOT NULL DEFAULT 1,
    deleted_at TIMESTAMPTZ, deleted_by UUID, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (tenant_id, entity_id, code)
);
CREATE TABLE IF NOT EXISTS forecast_lines (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id UUID NOT NULL,
    forecast_id UUID NOT NULL REFERENCES forecasts(id) ON DELETE CASCADE,
    account_id UUID NOT NULL REFERENCES accounts(id) ON DELETE RESTRICT,
    month DATE NOT NULL, amount NUMERIC(18,3) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID, updated_by UUID, version INTEGER NOT NULL DEFAULT 1,
    deleted_at TIMESTAMPTZ, deleted_by UUID, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (forecast_id, account_id, month)
);

-- ============ تكاملات ============
CREATE TABLE IF NOT EXISTS integrations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id UUID NOT NULL,
    entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE RESTRICT,
    code VARCHAR(50) NOT NULL, kind VARCHAR(50) NOT NULL DEFAULT 'webhook',
    config JSONB NOT NULL DEFAULT '{}', is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID, updated_by UUID, version INTEGER NOT NULL DEFAULT 1,
    deleted_at TIMESTAMPTZ, deleted_by UUID, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (tenant_id, entity_id, code)
);
CREATE TABLE IF NOT EXISTS webhooks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id UUID NOT NULL,
    integration_id UUID NOT NULL REFERENCES integrations(id) ON DELETE CASCADE,
    event VARCHAR(100) NOT NULL, target_url TEXT NOT NULL, secret VARCHAR(200),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID, updated_by UUID, version INTEGER NOT NULL DEFAULT 1,
    deleted_at TIMESTAMPTZ, deleted_by UUID, is_deleted BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE TABLE IF NOT EXISTS webhook_deliveries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id UUID NOT NULL,
    webhook_id UUID NOT NULL REFERENCES webhooks(id) ON DELETE CASCADE,
    payload JSONB NOT NULL DEFAULT '{}', http_status INTEGER,
    attempts INTEGER NOT NULL DEFAULT 0, status VARCHAR(30) NOT NULL DEFAULT 'queued',
    last_error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID, updated_by UUID, version INTEGER NOT NULL DEFAULT 1,
    deleted_at TIMESTAMPTZ, deleted_by UUID, is_deleted BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE TABLE IF NOT EXISTS api_request_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id UUID,
    method VARCHAR(10) NOT NULL, path TEXT NOT NULL, status_code INTEGER,
    duration_ms INTEGER, actor_id UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    version INTEGER NOT NULL DEFAULT 1, is_deleted BOOLEAN NOT NULL DEFAULT FALSE
);

-- ============ مرفقات وقوالب ============
CREATE TABLE IF NOT EXISTS attachments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id UUID NOT NULL,
    entity_id UUID REFERENCES entities(id) ON DELETE RESTRICT,
    file_name VARCHAR(255) NOT NULL, file_type VARCHAR(100), file_size BIGINT NOT NULL DEFAULT 0,
    storage_path TEXT NOT NULL, file_hash VARCHAR(128),
    linked_type VARCHAR(100), linked_id UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID, updated_by UUID, version INTEGER NOT NULL DEFAULT 1,
    deleted_at TIMESTAMPTZ, deleted_by UUID, is_deleted BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE TABLE IF NOT EXISTS document_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id UUID NOT NULL,
    entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE RESTRICT,
    code VARCHAR(50) NOT NULL, name_ar VARCHAR(200) NOT NULL, kind VARCHAR(50) NOT NULL DEFAULT 'invoice',
    body TEXT NOT NULL DEFAULT '', is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID, updated_by UUID, version INTEGER NOT NULL DEFAULT 1,
    deleted_at TIMESTAMPTZ, deleted_by UUID, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (tenant_id, entity_id, code)
);

-- ============ أمان: تفويض ومفاتيح API ============
CREATE TABLE IF NOT EXISTS delegations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id UUID NOT NULL,
    from_user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    to_user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    starts_on DATE NOT NULL, ends_on DATE NOT NULL, scope VARCHAR(200) NOT NULL DEFAULT 'all',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID, updated_by UUID, version INTEGER NOT NULL DEFAULT 1,
    deleted_at TIMESTAMPTZ, deleted_by UUID, is_deleted BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE TABLE IF NOT EXISTS api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(), tenant_id UUID NOT NULL,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    prefix VARCHAR(20) NOT NULL, key_hash VARCHAR(128) NOT NULL UNIQUE,
    scopes JSONB NOT NULL DEFAULT '[]', expires_on DATE,
    last_used_at TIMESTAMPTZ, is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID, updated_by UUID, version INTEGER NOT NULL DEFAULT 1,
    deleted_at TIMESTAMPTZ, deleted_by UUID, is_deleted BOOLEAN NOT NULL DEFAULT FALSE
);

-- ============ RLS + touch لكل جداول المستأجرين الجديدة ============
DO $$
DECLARE t TEXT;
BEGIN
  FOREACH t IN ARRAY ARRAY[
    'purchase_agreements','purchase_agreement_lines','debit_notes','debit_note_lines',
    'bank_reconciliations','bank_reconciliation_lines','check_books',
    'asset_transfers','asset_disposals','asset_revaluations','asset_depreciation_schedules',
    'loans','loan_schedules','loan_transactions',
    'tax_groups','tax_rates','tax_payments','withholding_taxes',
    'employee_contracts','salary_structures','salary_structure_lines',
    'leave_types','leave_balances','attendance_records',
    'academic_years','academic_terms','grade_levels','fee_structures','fee_structure_lines',
    'project_phases','project_tasks','budget_versions','budget_transfers','forecasts','forecast_lines',
    'integrations','webhooks','webhook_deliveries','api_request_logs',
    'attachments','document_templates','delegations','api_keys']
  LOOP
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
    EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', t);
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename = t AND policyname = 'tenant_iso_sel') THEN
      EXECUTE format('CREATE POLICY tenant_iso_sel ON %I FOR SELECT USING (tenant_id = NULLIF(current_setting(''app.current_tenant_id'', TRUE), '''')::UUID)', t);
      EXECUTE format('CREATE POLICY tenant_iso_ins ON %I FOR INSERT WITH CHECK (tenant_id = NULLIF(current_setting(''app.current_tenant_id'', TRUE), '''')::UUID)', t);
      EXECUTE format('CREATE POLICY tenant_iso_upd ON %I FOR UPDATE USING (tenant_id = NULLIF(current_setting(''app.current_tenant_id'', TRUE), '''')::UUID)', t);
      EXECUTE format('CREATE POLICY tenant_iso_del ON %I FOR DELETE USING (tenant_id = NULLIF(current_setting(''app.current_tenant_id'', TRUE), '''')::UUID)', t);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_' || t || '_touch') THEN
      EXECUTE format('CREATE TRIGGER trg_%I_touch BEFORE UPDATE ON %I FOR EACH ROW EXECUTE FUNCTION fn_touch_updated_at()', t, t);
    END IF;
  END LOOP;
END $$;

-- ============ فهارس ============
CREATE INDEX IF NOT EXISTS ix_agreement_lines_ag ON purchase_agreement_lines(agreement_id);
CREATE INDEX IF NOT EXISTS ix_debit_lines_note ON debit_note_lines(note_id);
CREATE INDEX IF NOT EXISTS ix_recon_lines_recon ON bank_reconciliation_lines(reconciliation_id);
CREATE INDEX IF NOT EXISTS ix_disposal_asset ON asset_disposals(asset_id);
CREATE INDEX IF NOT EXISTS ix_loan_sched_loan ON loan_schedules(loan_id);
CREATE INDEX IF NOT EXISTS ix_taxpay_tax ON tax_payments(tax_id);
CREATE INDEX IF NOT EXISTS ix_contracts_emp ON employee_contracts(employee_id);
CREATE INDEX IF NOT EXISTS ix_struct_lines_struct ON salary_structure_lines(structure_id);
CREATE INDEX IF NOT EXISTS ix_phases_project ON project_phases(project_id);
CREATE INDEX IF NOT EXISTS ix_tasks_phase ON project_tasks(phase_id);
CREATE INDEX IF NOT EXISTS ix_forecast_lines_fc ON forecast_lines(forecast_id);
CREATE INDEX IF NOT EXISTS ix_wh_deliveries_wh ON webhook_deliveries(webhook_id);
CREATE INDEX IF NOT EXISTS ix_attachments_link ON attachments(linked_type, linked_id);

-- ============ Seed مرجعي ============
INSERT INTO countries (code, name_ar, name_en) VALUES
 ('JO','الأردن','Jordan'),('SA','السعودية','Saudi Arabia'),('AE','الإمارات','UAE'),
 ('EG','مصر','Egypt'),('US','الولايات المتحدة','United States'),('EU','الاتحاد الأوروبي','European Union')
ON CONFLICT (code) DO NOTHING;
INSERT INTO cities (country_id, code, name_ar)
SELECT c.id, x.code, x.name FROM countries c JOIN (VALUES
 ('JO','AMM','عمّان'),('JO','ZAR','الزرقاء'),('JO','IRB','إربد'),
 ('SA','RUH','الرياض'),('SA','JED','جدة'),('AE','DXB','دبي'),('AE','AUH','أبوظبي')
) AS x(cc, code, name) ON x.cc = c.code
ON CONFLICT DO NOTHING;
