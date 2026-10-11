-- ============================================================================
-- 34_indexes.sql — الفهارس الإلزامية | Indexes
-- القاعدة: كل FK له فهرس + (tenant_id, ...) مركب + جزئي WHERE is_deleted=FALSE.
-- BRIN للجداول المقسمة زمنياً، GIN للنصوص العربية (trgm) و JSONB.
-- ============================================================================

-- tenant-first مركبة:
CREATE INDEX IF NOT EXISTS idx_accounts_tenant_entity ON accounts(tenant_id, entity_id) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_je_tenant_period ON journal_entries(tenant_id, fiscal_period_id, status, posting_date) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_jl_account ON journal_lines(tenant_id, account_id, posting_date);
CREATE INDEX IF NOT EXISTS idx_jl_entry ON journal_lines(entry_id, entry_posting_date);
CREATE INDEX IF NOT EXISTS idx_periods_entity_dates ON fiscal_periods(tenant_id, entity_id, starts_on, ends_on);
CREATE INDEX IF NOT EXISTS idx_users_tenant ON users(tenant_id) WHERE is_deleted = FALSE;

-- BRIN للجداول الكبيرة المقسمة (أرخص من B-tree زمنياً):
CREATE INDEX IF NOT EXISTS brin_je_date ON journal_entries USING BRIN (posting_date);
CREATE INDEX IF NOT EXISTS brin_jl_date ON journal_lines USING BRIN (posting_date);

-- GIN للبحث العربي + JSONB:
CREATE INDEX IF NOT EXISTS gin_accounts_name_trgm ON accounts USING GIN (name_ar gin_trgm_ops);
CREATE INDEX IF NOT EXISTS gin_closing_tb ON closing_snapshots USING GIN (trial_balance);

-- فريد لمنع ازدواج الترقيم داخل المستأجر (نفذت كقيود UNIQUE في DDL — توثيق فقط):
-- uq_accounts_code, uq_je_no, uq_users_tenant_username, uq(event_key) في event_keys.
