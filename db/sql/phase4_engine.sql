-- ============================================================================
-- Phase 4 — المحرك المحاسبي (12 جدول) | Requires: phase1+2+3
-- psql -f phase4_engine.sql
-- قرار أداء: بلا native partitioning في v1 (الفهارس BRIN+B-tree تكفي حتى ~5M قيد).
-- التقسيم الشهري يُفعّل في 4b (يتطلب PK مركباً ويكسر FKs البسيطة) — موثق في المخرج 11.
-- التوازن يُفحص بـ TRIGGER تجميعي (CHECK لا يرى جدول السطور). المرحّل IMMUTABLE.
-- ============================================================================

-- ================= A: الدفاتر (2) =================
CREATE TABLE IF NOT EXISTS journals (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  code VARCHAR(30) NOT NULL, name_ar VARCHAR(255) NOT NULL, name_en VARCHAR(255),
  journal_type VARCHAR(30) NOT NULL DEFAULT 'general',
  default_currency CHAR(3) NOT NULL DEFAULT 'JOD',
  default_account_id UUID REFERENCES accounts(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  prefix VARCHAR(20) NOT NULL DEFAULT '', suffix VARCHAR(20) NOT NULL DEFAULT '',
  number_length INTEGER NOT NULL DEFAULT 6 CHECK (number_length BETWEEN 4 AND 12),
  last_number BIGINT NOT NULL DEFAULT 0,
  require_approval BOOLEAN NOT NULL DEFAULT TRUE,
  allow_manual BOOLEAN NOT NULL DEFAULT TRUE, allow_auto BOOLEAN NOT NULL DEFAULT TRUE,
  approval_threshold NUMERIC(18,3),
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  notes TEXT,
  valid_from DATE NOT NULL DEFAULT CURRENT_DATE, valid_to DATE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, deleted_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT uq_journals_code UNIQUE (tenant_id, entity_id, code),
  CONSTRAINT ck_jtype CHECK (journal_type IN ('sale','purchase','cash','bank','general','opening','closing','adjustment','revaluation','consolidation','payroll','inventory','asset'))
);

CREATE TABLE IF NOT EXISTS journal_sequences (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  journal_id UUID NOT NULL REFERENCES journals(id) ON DELETE CASCADE ON UPDATE CASCADE,
  fiscal_year_id UUID NOT NULL REFERENCES fiscal_years(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  last_number BIGINT NOT NULL DEFAULT 0,
  prefix VARCHAR(20) NOT NULL DEFAULT '', suffix VARCHAR(20) NOT NULL DEFAULT '',
  number_length INTEGER NOT NULL DEFAULT 6,
  last_used_at TIMESTAMPTZ, last_used_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, deleted_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT uq_jseq UNIQUE (tenant_id, journal_id, fiscal_year_id)
);

-- ================= B: القيود (4) =================
CREATE TABLE IF NOT EXISTS journal_entries (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  journal_id UUID NOT NULL REFERENCES journals(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  fiscal_period_id UUID NOT NULL REFERENCES fiscal_periods(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  entry_type VARCHAR(30) NOT NULL DEFAULT 'manual',
  document_date DATE NOT NULL, posting_date DATE NOT NULL,
  description TEXT, reference VARCHAR(100),
  source_module VARCHAR(50) NOT NULL DEFAULT 'manual', source_document_id UUID,
  event_key VARCHAR(200), event_version INTEGER NOT NULL DEFAULT 1,
  currency_id CHAR(3) NOT NULL DEFAULT 'JOD',
  exchange_rate NUMERIC(18,10) NOT NULL DEFAULT 1,
  total_debit NUMERIC(18,3) NOT NULL DEFAULT 0, total_credit NUMERIC(18,3) NOT NULL DEFAULT 0,
  total_functional NUMERIC(18,3) NOT NULL DEFAULT 0,
  status VARCHAR(30) NOT NULL DEFAULT 'draft',
  status_changed_at TIMESTAMPTZ, status_changed_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  official_number VARCHAR(60),
  approved_at TIMESTAMPTZ, approved_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  posted_at TIMESTAMPTZ, posted_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  reversed_at TIMESTAMPTZ, reversed_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  reversal_of_id UUID REFERENCES journal_entries(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  is_reversed BOOLEAN NOT NULL DEFAULT FALSE,
  metadata JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, deleted_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT ck_etype CHECK (entry_type IN ('manual','source','opening','reversal','closing','adjustment','accrual','deferral','revaluation','consolidation','payroll','inventory','depreciation')),
  CONSTRAINT ck_estatus CHECK (status IN ('draft','pending_review','approved','posted','reversed','cancelled','rejected')),
  CONSTRAINT ck_eexch CHECK (exchange_rate > 0),
  CONSTRAINT ck_ecurr CHECK (currency_id ~ '^[A-Z]{3}$'),
  CONSTRAINT ck_etot CHECK (total_debit >= 0 AND total_credit >= 0),
  CONSTRAINT uq_entry_official UNIQUE (tenant_id, entity_id, journal_id, official_number),
  CONSTRAINT uq_entry_event UNIQUE (tenant_id, entity_id, event_key)
);

CREATE TABLE IF NOT EXISTS journal_entry_versions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE ON UPDATE CASCADE,
  entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE ON UPDATE CASCADE,
  entry_id UUID NOT NULL REFERENCES journal_entries(id) ON DELETE CASCADE ON UPDATE CASCADE,
  version_no INTEGER NOT NULL CHECK (version_no >= 1),
  effective_from DATE NOT NULL, changes JSONB NOT NULL,
  approved_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  attachment_url TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, deleted_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT uq_ever UNIQUE (tenant_id, entry_id, version_no)
);

CREATE TABLE IF NOT EXISTS journal_lines (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  entry_id UUID NOT NULL REFERENCES journal_entries(id) ON DELETE CASCADE ON UPDATE CASCADE,
  line_number INTEGER NOT NULL CHECK (line_number >= 1),
  account_id UUID NOT NULL REFERENCES accounts(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  debit NUMERIC(18,3) NOT NULL DEFAULT 0, credit NUMERIC(18,3) NOT NULL DEFAULT 0,
  currency_id CHAR(3) NOT NULL DEFAULT 'JOD',
  amount_currency NUMERIC(18,3) NOT NULL DEFAULT 0,
  exchange_rate NUMERIC(18,10) NOT NULL DEFAULT 1,
  amount_functional NUMERIC(18,3) NOT NULL DEFAULT 0,
  partner_id UUID, -- FK مرن للأطراف (phase5) — يُشدّد لاحقاً
  due_on DATE,
  branch_id UUID REFERENCES branches(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  cost_center_id UUID, project_id UUID, -- FK للأبعاد (قيم مرنة — تُشدّد مع phase3 values)
  dims JSONB NOT NULL DEFAULT '{}',
  description TEXT, source_line_ref VARCHAR(100),
  recon_id UUID, recon_at TIMESTAMPTZ, is_reconciled BOOLEAN NOT NULL DEFAULT FALSE,
  settled_amount NUMERIC(18,3) NOT NULL DEFAULT 0, remaining_amount NUMERIC(18,3) NOT NULL DEFAULT 0,
  metadata JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, deleted_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT uq_line_no UNIQUE (entry_id, line_number),
  CONSTRAINT ck_line_side CHECK ((debit = 0 AND credit > 0) OR (credit = 0 AND debit > 0)),
  CONSTRAINT ck_line_amt CHECK (amount_functional >= 0 AND settled_amount >= 0 AND remaining_amount >= 0)
);

CREATE TABLE IF NOT EXISTS journal_line_dimensions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE ON UPDATE CASCADE,
  line_id UUID NOT NULL REFERENCES journal_lines(id) ON DELETE CASCADE ON UPDATE CASCADE,
  dimension_id UUID NOT NULL REFERENCES dimensions(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  dimension_value_id UUID NOT NULL REFERENCES dimension_values(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  pct NUMERIC(7,4), sort_order INTEGER NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, deleted_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT ck_jld_pct CHECK (pct IS NULL OR (pct > 0 AND pct <= 100)),
  CONSTRAINT uq_jld UNIQUE (tenant_id, line_id, dimension_value_id)
);

-- ================= C: الازدواج والعكس (3) =================
CREATE TABLE IF NOT EXISTS event_keys (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  source_module VARCHAR(50) NOT NULL, source_document_id UUID NOT NULL,
  event_type VARCHAR(100) NOT NULL, event_version INTEGER NOT NULL DEFAULT 1,
  event_key VARCHAR(200) NOT NULL,
  process_status VARCHAR(20) NOT NULL DEFAULT 'pending',
  resulting_entry_id UUID REFERENCES journal_entries(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  processed_at TIMESTAMPTZ, attempts INTEGER NOT NULL DEFAULT 0, last_error TEXT,
  metadata JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, deleted_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT uq_event_key UNIQUE (tenant_id, entity_id, event_key),
  CONSTRAINT ck_ek_status CHECK (process_status IN ('pending','processed','failed'))
);

CREATE TABLE IF NOT EXISTS event_key_registry (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  event_key VARCHAR(200) NOT NULL,
  source_module VARCHAR(50) NOT NULL, source_document_id UUID,
  event_type VARCHAR(100) NOT NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'active',
  expires_at TIMESTAMPTZ, notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, deleted_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT uq_ekr UNIQUE (tenant_id, event_key)
);

CREATE TABLE IF NOT EXISTS reversal_links (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  original_entry_id UUID NOT NULL REFERENCES journal_entries(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  reversal_entry_id UUID NOT NULL REFERENCES journal_entries(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  reversed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  reversed_by UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  reason TEXT NOT NULL,
  reversal_type VARCHAR(20) NOT NULL DEFAULT 'full', -- full / partial
  reversed_amount NUMERIC(18,3),
  fiscal_period_id UUID NOT NULL REFERENCES fiscal_periods(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, deleted_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT uq_reversal_orig UNIQUE (original_entry_id),
  CONSTRAINT uq_reversal_rev UNIQUE (reversal_entry_id),
  CONSTRAINT ck_rev_type CHECK (reversal_type IN ('full','partial')),
  CONSTRAINT ck_rev_reason CHECK (LENGTH(reason) > 5)
);

-- ================= D: المرفقات والاعتمادات (3) =================
CREATE TABLE IF NOT EXISTS entry_attachments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE ON UPDATE CASCADE,
  entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE ON UPDATE CASCADE,
  entry_id UUID NOT NULL REFERENCES journal_entries(id) ON DELETE CASCADE ON UPDATE CASCADE,
  file_name VARCHAR(255) NOT NULL, file_type VARCHAR(100) NOT NULL,
  file_size BIGINT NOT NULL CHECK (file_size > 0 AND file_size <= 52428800),
  storage_path TEXT NOT NULL, file_hash VARCHAR(128) NOT NULL,
  uploaded_by UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  uploaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, deleted_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE, is_deleted BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS entry_comments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE ON UPDATE CASCADE,
  entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE ON UPDATE CASCADE,
  entry_id UUID NOT NULL REFERENCES journal_entries(id) ON DELETE CASCADE ON UPDATE CASCADE,
  comment_text TEXT NOT NULL,
  commented_by UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  commented_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  comment_type VARCHAR(30) NOT NULL DEFAULT 'note',
  is_internal BOOLEAN NOT NULL DEFAULT TRUE, attachments JSONB NOT NULL DEFAULT '[]',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, deleted_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT ck_comment_type CHECK (comment_type IN ('note','reject_reason','reverse_reason','edit_reason'))
);

CREATE TABLE IF NOT EXISTS entry_approvals (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE ON UPDATE CASCADE,
  entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE ON UPDATE CASCADE,
  entry_id UUID NOT NULL REFERENCES journal_entries(id) ON DELETE CASCADE ON UPDATE CASCADE,
  approver_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  approval_type VARCHAR(20) NOT NULL DEFAULT 'final',
  status VARCHAR(20) NOT NULL DEFAULT 'pending',
  reason TEXT, decided_at TIMESTAMPTZ,
  seq INTEGER NOT NULL DEFAULT 1, is_mandatory BOOLEAN NOT NULL DEFAULT TRUE,
  sla_due_at TIMESTAMPTZ, expires_at TIMESTAMPTZ, notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, deleted_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT ck_ea_type CHECK (approval_type IN ('interim','final')),
  CONSTRAINT ck_ea_status CHECK (status IN ('pending','approved','rejected')),
  CONSTRAINT uq_ea UNIQUE (tenant_id, entry_id, approver_id, approval_type)
);

-- ================= الفهارس =================
CREATE INDEX IF NOT EXISTS idx_journals_tenant ON journals(tenant_id);
CREATE INDEX IF NOT EXISTS idx_journals_entity ON journals(entity_id) WHERE is_deleted=FALSE;
CREATE INDEX IF NOT EXISTS idx_jseq_journal ON journal_sequences(journal_id);
CREATE INDEX IF NOT EXISTS idx_je_tenant ON journal_entries(tenant_id);
CREATE INDEX IF NOT EXISTS idx_je_entity_date ON journal_entries(entity_id, posting_date DESC) WHERE is_deleted=FALSE;
CREATE INDEX IF NOT EXISTS idx_je_entity_status ON journal_entries(entity_id, status) WHERE is_deleted=FALSE;
CREATE INDEX IF NOT EXISTS idx_je_journal_period ON journal_entries(journal_id, fiscal_period_id);
CREATE INDEX IF NOT EXISTS idx_je_official ON journal_entries(official_number) WHERE official_number IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_je_reversal_of ON journal_entries(reversal_of_id) WHERE reversal_of_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS gin_je_meta ON journal_entries USING GIN (metadata);
CREATE INDEX IF NOT EXISTS idx_jl_entry ON journal_lines(entry_id, line_number);
CREATE INDEX IF NOT EXISTS idx_jl_account ON journal_lines(account_id) WHERE is_deleted=FALSE;
-- تاريخ الترحيل للسطر يُشتق من رأس القيد (join) — لا عمود مكرر في v1 (قرار تطبيع)؛
-- فهرس (account_id, entry_id) يغطي تقارير الأستاذ حتى 4b (التقسيم يضيف posting_date منسوخاً).
CREATE INDEX IF NOT EXISTS idx_ek_key ON event_keys(tenant_id, entity_id, event_key);
CREATE INDEX IF NOT EXISTS idx_ea_entry ON entry_approvals(entry_id);
CREATE INDEX IF NOT EXISTS idx_je_active ON journal_entries(deleted_at) WHERE is_deleted=FALSE;
CREATE INDEX IF NOT EXISTS brin_je_posting ON journal_entries USING BRIN (posting_date);

-- ================= Triggers الحرجة =================
-- 1) توازن القيد عند الترحيل (مجموع السطور بالوظيفية = صفر فرق)
CREATE OR REPLACE FUNCTION fn_entry_must_balance() RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE d NUMERIC(18,3); c NUMERIC(18,3);
BEGIN
  IF NEW.status = 'posted' AND (OLD.status IS DISTINCT FROM 'posted') THEN
    SELECT COALESCE(SUM(debit),0), COALESCE(SUM(credit),0) INTO d, c FROM journal_lines WHERE entry_id=NEW.id AND is_deleted=FALSE;
    IF d <> c THEN RAISE EXCEPTION 'UNBALANCED_ENTRY debit=% credit=%', d, c; END IF;
    IF d = 0 THEN RAISE EXCEPTION 'EMPTY_ENTRY %', NEW.id; END IF;
    NEW.total_debit := d; NEW.total_credit := c;
  END IF;
  RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS trg_je_balance ON journal_entries;
CREATE TRIGGER trg_je_balance BEFORE UPDATE ON journal_entries FOR EACH ROW EXECUTE FUNCTION fn_entry_must_balance();

-- 2) منع تعديل/حذف المرحّل
CREATE OR REPLACE FUNCTION fn_forbid_posted() RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  IF OLD.status='posted' THEN
    IF NEW.status='reversed'
       AND NEW.total_debit IS NOT DISTINCT FROM OLD.total_debit
       AND NEW.total_credit IS NOT DISTINCT FROM OLD.total_credit
       AND NEW.posting_date IS NOT DISTINCT FROM OLD.posting_date
       AND NEW.fiscal_period_id IS NOT DISTINCT FROM OLD.fiscal_period_id
       AND NEW.entry_type IS NOT DISTINCT FROM OLD.entry_type
       AND NEW.journal_id IS NOT DISTINCT FROM OLD.journal_id THEN
      IF TG_OP='DELETE' THEN RETURN OLD; ELSE RETURN NEW; END IF;
    END IF;
    RAISE EXCEPTION 'POSTED_IMMUTABLE % — use reversal', OLD.id;
  END IF;
  IF TG_OP='DELETE' THEN RETURN OLD; ELSE RETURN NEW; END IF;
END $$;
DROP TRIGGER IF EXISTS trg_je_immutable ON journal_entries;
CREATE TRIGGER trg_je_immutable BEFORE UPDATE OR DELETE ON journal_entries FOR EACH ROW EXECUTE FUNCTION fn_forbid_posted();

-- 3) الفترة مفتوحة + الحساب حركي ومن نفس الكيان (يفحص عند إدخال السطر)
CREATE OR REPLACE FUNCTION fn_line_guards() RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE v_pid UUID; v_open TEXT; v_postable BOOL; v_active BOOL; v_eacc UUID;
BEGIN
  SELECT fiscal_period_id INTO v_pid FROM journal_entries WHERE id=NEW.entry_id;
  SELECT status INTO v_open FROM fiscal_periods WHERE id = v_pid;
  IF v_open IN ('soft_closed','hard_closed') THEN RAISE EXCEPTION 'PERIOD_CLOSED'; END IF;
  SELECT is_postable, is_active, entity_id INTO v_postable, v_active, v_eacc FROM accounts WHERE id=NEW.account_id;
  IF NOT v_postable THEN RAISE EXCEPTION 'ACCOUNT_NOT_POSTABLE %', NEW.account_id; END IF;
  IF NOT v_active THEN RAISE EXCEPTION 'ACCOUNT_INACTIVE %', NEW.account_id; END IF;
  IF v_eacc IS DISTINCT FROM NEW.entity_id THEN RAISE EXCEPTION 'ACCOUNT_OTHER_ENTITY'; END IF;
  RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS trg_jl_guards ON journal_lines;
CREATE TRIGGER trg_jl_guards BEFORE INSERT OR UPDATE ON journal_lines FOR EACH ROW EXECUTE FUNCTION fn_line_guards();

-- 4) منع العكس المكرر + تاريخ العكس >= الأصل
CREATE OR REPLACE FUNCTION fn_reversal_guards() RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE v_d DATE;
BEGIN
  IF EXISTS (SELECT 1 FROM reversal_links WHERE original_entry_id=NEW.original_entry_id AND id<>NEW.id) THEN RAISE EXCEPTION 'ALREADY_REVERSED %', NEW.original_entry_id; END IF;
  SELECT posting_date INTO v_d FROM journal_entries WHERE id=NEW.original_entry_id;
  IF (SELECT posting_date FROM journal_entries WHERE id=NEW.reversal_entry_id) < v_d THEN RAISE EXCEPTION 'REVERSAL_BEFORE_ORIGINAL'; END IF;
  RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS trg_rev_guards ON reversal_links;
CREATE TRIGGER trg_rev_guards BEFORE INSERT ON reversal_links FOR EACH ROW EXECUTE FUNCTION fn_reversal_guards();

DO $$ DECLARE t TEXT; arr TEXT[] := ARRAY['journals','journal_sequences','journal_entries','journal_entry_versions','journal_lines','journal_line_dimensions','event_keys','event_key_registry','reversal_links','entry_attachments','entry_comments','entry_approvals'];
BEGIN FOREACH t IN ARRAY arr LOOP EXECUTE format('DROP TRIGGER IF EXISTS trg_%s_touch ON %I',t,t); EXECUTE format('CREATE TRIGGER trg_%s_touch BEFORE UPDATE ON %I FOR EACH ROW EXECUTE FUNCTION fn_touch_updated_at()',t,t); END LOOP; END $$;

-- ================= RLS =================
DO $$ DECLARE t TEXT; arr TEXT[] := ARRAY['journals','journal_sequences','journal_entries','journal_entry_versions','journal_lines','journal_line_dimensions','event_keys','event_key_registry','reversal_links','entry_attachments','entry_comments','entry_approvals'];
BEGIN FOREACH t IN ARRAY arr LOOP
  EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY',t);
  EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY',t);
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename=t AND policyname='tenant_iso_sel') THEN
    EXECUTE format('CREATE POLICY tenant_iso_sel ON %I FOR SELECT USING (tenant_id = NULLIF(current_setting(%L,true),%L)::UUID)',t,'app.current_tenant_id','');
    EXECUTE format('CREATE POLICY tenant_iso_ins ON %I FOR INSERT WITH CHECK (tenant_id = NULLIF(current_setting(%L,true),%L)::UUID)',t,'app.current_tenant_id','');
    EXECUTE format('CREATE POLICY tenant_iso_upd ON %I FOR UPDATE USING (tenant_id = NULLIF(current_setting(%L,true),%L)::UUID)',t,'app.current_tenant_id','');
    EXECUTE format('CREATE POLICY tenant_iso_del ON %I FOR DELETE USING (tenant_id = NULLIF(current_setting(%L,true),%L)::UUID)',t,'app.current_tenant_id','');
  END IF;
END LOOP; END $$;

-- ================= Seed: دفاتر افتراضية (تُزرع لكل entity عبر التطبيق) =================
-- SALE مبيعات / PURCH مشتريات / CASH نقدية / BANK بنكية / GEN عامة — كلها allow_auto=TRUE عدا GEN يدوي فقط، require_approval حسب العتبة.

COMMENT ON TABLE journals IS 'دفاتر اليومية (ترقيم وتسلسل لكل كيان) | Journals';
COMMENT ON TABLE journal_entries IS 'القيود — التوازن إجباري عند الترحيل، المرحّل لا يُعدّل | Entries immutable when posted';
COMMENT ON TABLE journal_lines IS 'سطور القيود — جهة واحدة لكل سطر (مدين XOR دائن) | One side per line';
COMMENT ON TABLE event_keys IS 'منع الازدواج UQ(tenant,entity,event_key) — INSERT ON CONFLICT DO NOTHING | Idempotency';
COMMENT ON TABLE reversal_links IS 'العكس الكامل مرة واحدة للأصل + تاريخ العكس >= الأصل | Full reversal once';
