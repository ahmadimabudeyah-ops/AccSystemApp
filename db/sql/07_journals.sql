-- ============================================================================
-- 07_journals.sql — المحرك المحاسبي (المجموعة 5)
-- قرار: PARTITION BY RANGE (posting_date) شهرياً. PK يجب أن يتضمن مفتاح التقسيم:
-- PRIMARY KEY (id, posting_date). سطور القيود تحمل posting_date منسوخة + FK مركب.
-- بديل مرفوض: تقسيم HASH على id — لا يفيد purge الزمني ولا Partition Pruning للتقارير.
-- القيد المرحل لا يُعدّل: Trigger في 30_triggers.sql + RLS.
-- ============================================================================

CREATE TABLE IF NOT EXISTS journals (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
  entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE RESTRICT,
  code VARCHAR(30) NOT NULL, name_ar VARCHAR(255) NOT NULL, name_en VARCHAR(255),
  journal_type journal_type NOT NULL DEFAULT 'general',
  valid_from DATE NOT NULL DEFAULT CURRENT_DATE, valid_to DATE, is_active BOOLEAN NOT NULL DEFAULT TRUE,
  status VARCHAR(50) NOT NULL DEFAULT 'active',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID NOT NULL REFERENCES users(id), updated_by UUID NOT NULL REFERENCES users(id),
  version INTEGER NOT NULL DEFAULT 1, deleted_at TIMESTAMPTZ, deleted_by UUID REFERENCES users(id), is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT uq_journals_code UNIQUE (tenant_id, entity_id, code)
);

CREATE TABLE IF NOT EXISTS journal_sequences (
  journal_id UUID NOT NULL REFERENCES journals(id) ON DELETE CASCADE,
  fiscal_year_id UUID NOT NULL REFERENCES fiscal_years(id) ON DELETE RESTRICT,
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
  last_number BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID NOT NULL REFERENCES users(id), updated_by UUID NOT NULL REFERENCES users(id),
  version INTEGER NOT NULL DEFAULT 1, deleted_at TIMESTAMPTZ, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  PRIMARY KEY (journal_id, fiscal_year_id)
);

-- ---------- القيود (مقسّمة شهرياً) ----------
CREATE TABLE IF NOT EXISTS journal_entries (
  id UUID NOT NULL DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
  entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE RESTRICT,
  journal_id UUID NOT NULL REFERENCES journals(id) ON DELETE RESTRICT,
  fiscal_period_id UUID NOT NULL REFERENCES fiscal_periods(id) ON DELETE RESTRICT,
  entry_no VARCHAR(40) NOT NULL, -- تسلسل رسمي لكل كيان+سنة
  posting_date DATE NOT NULL,     -- مفتاح التقسيم | Partition key
  entry_date DATE NOT NULL,
  currency_id currency_code NOT NULL DEFAULT 'JOD',
  exchange_rate exchange_rate NOT NULL DEFAULT 1,
  entry_type entry_type NOT NULL DEFAULT 'manual',
  status entry_status NOT NULL DEFAULT 'draft',
  status_changed_at TIMESTAMPTZ, status_changed_by UUID REFERENCES users(id),
  posted_at TIMESTAMPTZ, posted_by UUID REFERENCES users(id),
  approved_at TIMESTAMPTZ, approved_by UUID REFERENCES users(id),
  reversed_at TIMESTAMPTZ, reversed_by UUID REFERENCES users(id),
  source_type VARCHAR(100) NOT NULL DEFAULT 'manual', source_id UUID,
  narration TEXT,
  total_debit signed_money NOT NULL DEFAULT 0, total_credit signed_money NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID NOT NULL REFERENCES users(id), updated_by UUID NOT NULL REFERENCES users(id),
  version INTEGER NOT NULL DEFAULT 1, deleted_at TIMESTAMPTZ, deleted_by UUID REFERENCES users(id), is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  PRIMARY KEY (id, posting_date),
  CONSTRAINT uq_je_no UNIQUE (tenant_id, entity_id, entry_no, posting_date),
  CONSTRAINT ck_je_balanced CHECK (total_debit = total_credit)
) PARTITION BY RANGE (posting_date);
COMMENT ON TABLE journal_entries IS 'القيود — مقسمة شهرياً | Partitioned monthly by posting_date';

-- أقسام أولية (تُوسّع تلقائياً عبر fn_ensure_entry_partition):
CREATE TABLE IF NOT EXISTS journal_entries_p2026_01 PARTITION OF journal_entries FOR VALUES FROM ('2026-01-01') TO ('2026-02-01');
CREATE TABLE IF NOT EXISTS journal_entries_p2026_02 PARTITION OF journal_entries FOR VALUES FROM ('2026-02-01') TO ('2026-03-01');
CREATE TABLE IF NOT EXISTS journal_entries_default PARTITION OF journal_entries DEFAULT;

CREATE TABLE IF NOT EXISTS journal_lines (
  id UUID NOT NULL DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
  entry_id UUID NOT NULL, entry_posting_date DATE NOT NULL, -- FK مركب للجدول المقسّم
  posting_date DATE NOT NULL, -- نسخة التقسيم | Partition key (يساوي entry_posting_date)
  line_no INTEGER NOT NULL,
  account_id UUID NOT NULL REFERENCES accounts(id) ON DELETE RESTRICT,
  debit money_amount NOT NULL DEFAULT 0, credit money_amount NOT NULL DEFAULT 0,
  currency_id currency_code NOT NULL DEFAULT 'JOD', amount_currency money_amount,
  party_id UUID, cost_center_id UUID, project_id UUID,
  narration TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID NOT NULL REFERENCES users(id), updated_by UUID NOT NULL REFERENCES users(id),
  version INTEGER NOT NULL DEFAULT 1, deleted_at TIMESTAMPTZ, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  PRIMARY KEY (id, posting_date),
  FOREIGN KEY (entry_id, entry_posting_date) REFERENCES journal_entries(id, posting_date) ON DELETE CASCADE,
  CONSTRAINT ck_jl_one_side CHECK (debit = 0 OR credit = 0),
  CONSTRAINT ck_jl_nonzero CHECK (NOT (debit = 0 AND credit = 0))
) PARTITION BY RANGE (posting_date);
CREATE TABLE IF NOT EXISTS journal_lines_p2026_01 PARTITION OF journal_lines FOR VALUES FROM ('2026-01-01') TO ('2026-02-01');
CREATE TABLE IF NOT EXISTS journal_lines_p2026_02 PARTITION OF journal_lines FOR VALUES FROM ('2026-02-01') TO ('2026-03-01');
CREATE TABLE IF NOT EXISTS journal_lines_default PARTITION OF journal_lines DEFAULT;

-- ---------- منع الازدواج ----------
CREATE TABLE IF NOT EXISTS event_keys (
  event_key TEXT NOT NULL,
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID NOT NULL REFERENCES users(id),
  PRIMARY KEY (event_key) -- عالمي UNIQUE لمنع إعادة المعالجة عبر الكيانات
);
COMMENT ON TABLE event_keys IS 'Idempotency — INSERT ... ON CONFLICT DO NOTHING أول كل Consumer';

CREATE TABLE IF NOT EXISTS reversal_links (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
  original_entry_id UUID NOT NULL, reversal_entry_id UUID NOT NULL,
  reason TEXT NOT NULL,
  reversed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), reversed_by UUID NOT NULL REFERENCES users(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID NOT NULL REFERENCES users(id), updated_by UUID NOT NULL REFERENCES users(id),
  version INTEGER NOT NULL DEFAULT 1, deleted_at TIMESTAMPTZ, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT uq_reversal_orig UNIQUE (original_entry_id),
  CONSTRAINT uq_reversal_rev UNIQUE (reversal_entry_id),
  CONSTRAINT ck_reversal_reason CHECK (LENGTH(reason) > 5)
);
-- ملاحظة: FK إلى journal_entries المقسّم يتطلب posting_date — يُفحص تطبيقياً + Trigger
-- (FK مباشر على id وحده مستحيل مع التقسيم؛ البديل المرفوض: إلغاء التقسيم من أجل FK بسيط).

CREATE TABLE IF NOT EXISTS entry_approvals (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
  entry_id UUID NOT NULL, action approval_status NOT NULL DEFAULT 'pending',
  approver_id UUID NOT NULL REFERENCES users(id),
  decided_at TIMESTAMPTZ, comment TEXT,
  status VARCHAR(50) NOT NULL DEFAULT 'pending',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID NOT NULL REFERENCES users(id), updated_by UUID NOT NULL REFERENCES users(id),
  version INTEGER NOT NULL DEFAULT 1, deleted_at TIMESTAMPTZ, is_deleted BOOLEAN NOT NULL DEFAULT FALSE
);
