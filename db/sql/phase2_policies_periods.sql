-- ============================================================================
-- Phase 2 — السياسات والفترات المالية (12 جدول) | Requires: phase1_foundation.sql
-- psql -f phase2_policies_periods.sql
-- قرار: الحالات TEXT+CHECK (لا ENUM) — إضافة حالة إقفال لا تقفل الجدول.
-- الفترات لكل entity مستقلة؛ period_number 1-13 (13=تعديل)؛ سنة ميلادية JO افتراضياً.
-- ============================================================================

-- ================= A: السياسات (3) =================
CREATE TABLE IF NOT EXISTS accounting_policies (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  code VARCHAR(50) NOT NULL,
  framework VARCHAR(30) NOT NULL DEFAULT 'IFRS_SME', -- IFRS / IFRS_SME / CASH
  revenue_recognition TEXT NOT NULL DEFAULT 'accrual',
  expense_recognition TEXT NOT NULL DEFAULT 'accrual',
  inventory_method VARCHAR(20) NOT NULL DEFAULT 'average', -- fifo / average / standard
  capitalization_threshold NUMERIC(18,3) NOT NULL DEFAULT 500.000,
  depreciation_method VARCHAR(30) NOT NULL DEFAULT 'straight_line',
  foreign_currency_policy TEXT, provisions_policy TEXT, tax_policy TEXT,
  rounding_method VARCHAR(20) NOT NULL DEFAULT 'half_up',
  rounding_limit NUMERIC(18,3) NOT NULL DEFAULT 0.005,
  doc_numbering_policy JSONB NOT NULL DEFAULT '{}',
  effective_from DATE NOT NULL, effective_to DATE,
  status VARCHAR(30) NOT NULL DEFAULT 'draft',
  status_changed_at TIMESTAMPTZ, status_changed_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  approved_at TIMESTAMPTZ, approved_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  valid_from DATE NOT NULL DEFAULT CURRENT_DATE, valid_to DATE, is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, deleted_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT uq_accpol_code UNIQUE (tenant_id, entity_id, code),
  CONSTRAINT ck_accpol_status CHECK (status IN ('draft','approved','retired')),
  CONSTRAINT ck_accpol_framework CHECK (framework IN ('IFRS','IFRS_SME','CASH')),
  CONSTRAINT ck_accpol_inv CHECK (inventory_method IN ('fifo','average','standard')),
  CONSTRAINT ck_accpol_dates CHECK (effective_to IS NULL OR effective_to >= effective_from)
);

CREATE TABLE IF NOT EXISTS policy_versions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  policy_id UUID NOT NULL REFERENCES accounting_policies(id) ON DELETE CASCADE ON UPDATE CASCADE,
  version_no INTEGER NOT NULL CHECK (version_no >= 1),
  effective_from DATE NOT NULL, effective_to DATE,
  changes TEXT NOT NULL,
  attachment_url TEXT,
  status VARCHAR(30) NOT NULL DEFAULT 'draft',
  status_changed_at TIMESTAMPTZ, status_changed_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  approved_at TIMESTAMPTZ, approved_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, deleted_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT uq_policy_versions UNIQUE (tenant_id, policy_id, version_no),
  CONSTRAINT ck_pv_dates CHECK (effective_to IS NULL OR effective_to >= effective_from)
);

CREATE TABLE IF NOT EXISTS policy_applicability (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE ON UPDATE CASCADE,
  entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE ON UPDATE CASCADE,
  policy_id UUID NOT NULL REFERENCES accounting_policies(id) ON DELETE CASCADE ON UPDATE CASCADE,
  scope_type VARCHAR(30) NOT NULL, -- entity / branch / doc_type
  scope_ref UUID, -- branch_id أو NULL للكيان كله (FK مرن — يُشدّد في مرحلة الفروع)
  priority INTEGER NOT NULL DEFAULT 100,
  conditions JSONB NOT NULL DEFAULT '{}',
  valid_from DATE NOT NULL DEFAULT CURRENT_DATE, valid_to DATE, is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, deleted_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT ck_pa_scope CHECK (scope_type IN ('entity','branch','doc_type')),
  CONSTRAINT ck_pa_prio CHECK (priority BETWEEN 1 AND 999)
);

-- ================= B: السنوات والفترات (4) =================
CREATE TABLE IF NOT EXISTS fiscal_years (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  code VARCHAR(20) NOT NULL, -- YYYY
  name_ar VARCHAR(255) NOT NULL, name_en VARCHAR(255),
  starts_on DATE NOT NULL, ends_on DATE NOT NULL,
  start_month INTEGER NOT NULL DEFAULT 1,
  status VARCHAR(30) NOT NULL DEFAULT 'future',
  status_changed_at TIMESTAMPTZ, status_changed_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  approved_at TIMESTAMPTZ, approved_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  periods_count INTEGER NOT NULL DEFAULT 12 CHECK (periods_count BETWEEN 1 AND 13),
  year_type VARCHAR(20) NOT NULL DEFAULT 'regular', -- regular / transitional
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, deleted_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT uq_fy_code UNIQUE (tenant_id, entity_id, code),
  CONSTRAINT ck_fy_code CHECK (code ~ '^[0-9]{4}$'),
  CONSTRAINT ck_fy_dates CHECK (ends_on > starts_on),
  CONSTRAINT ck_fy_month CHECK (start_month BETWEEN 1 AND 12),
  CONSTRAINT ck_fy_status CHECK (status IN ('future','open','soft_closed','hard_closed'))
);

CREATE TABLE IF NOT EXISTS fiscal_periods (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  fiscal_year_id UUID NOT NULL REFERENCES fiscal_years(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  code VARCHAR(20) NOT NULL, -- YYYY-MM
  period_number INTEGER NOT NULL,
  name_ar VARCHAR(255) NOT NULL, name_en VARCHAR(255),
  starts_on DATE NOT NULL, ends_on DATE NOT NULL,
  period_type VARCHAR(20) NOT NULL DEFAULT 'regular', -- regular / adjusting / closing
  status VARCHAR(30) NOT NULL DEFAULT 'future',
  status_changed_at TIMESTAMPTZ, status_changed_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  approved_at TIMESTAMPTZ, approved_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  backdate_window_days INTEGER NOT NULL DEFAULT 0 CHECK (backdate_window_days >= 0),
  closed_at TIMESTAMPTZ, closed_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, deleted_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT uq_fp_code UNIQUE (tenant_id, entity_id, code),
  CONSTRAINT uq_fp_number UNIQUE (tenant_id, entity_id, fiscal_year_id, period_number),
  CONSTRAINT ck_fp_code CHECK (code ~ '^[0-9]{4}-[0-9]{2}$'),
  CONSTRAINT ck_fp_num CHECK (period_number BETWEEN 1 AND 13),
  CONSTRAINT ck_fp_dates CHECK (ends_on >= starts_on),
  CONSTRAINT ck_fp_status CHECK (status IN ('future','open','soft_closed','hard_closed')),
  CONSTRAINT ck_fp_type CHECK (period_type IN ('regular','adjusting','closing'))
);

CREATE TABLE IF NOT EXISTS period_locks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  fiscal_period_id UUID NOT NULL REFERENCES fiscal_periods(id) ON DELETE CASCADE ON UPDATE CASCADE,
  lock_type VARCHAR(20) NOT NULL, -- soft / hard
  locked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  locked_by UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  reason TEXT NOT NULL,
  status VARCHAR(30) NOT NULL DEFAULT 'active',
  status_changed_at TIMESTAMPTZ, status_changed_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  approved_at TIMESTAMPTZ, approved_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, deleted_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT ck_lock_type CHECK (lock_type IN ('soft','hard'))
);

CREATE TABLE IF NOT EXISTS period_lock_exceptions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE ON UPDATE CASCADE,
  entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE ON UPDATE CASCADE,
  fiscal_period_id UUID NOT NULL REFERENCES fiscal_periods(id) ON DELETE CASCADE ON UPDATE CASCADE,
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE ON UPDATE CASCADE,
  exception_type VARCHAR(20) NOT NULL, -- read / write / approve
  starts_on DATE NOT NULL, ends_on DATE NOT NULL,
  reason TEXT NOT NULL,
  approved_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  approved_at TIMESTAMPTZ,
  status VARCHAR(30) NOT NULL DEFAULT 'active',
  status_changed_at TIMESTAMPTZ, status_changed_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, deleted_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT ck_exc_type CHECK (exception_type IN ('read','write','approve')),
  CONSTRAINT ck_exc_dates CHECK (ends_on >= starts_on)
);

-- ================= C: مهام الإقفال (5) =================
CREATE TABLE IF NOT EXISTS closing_tasks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  fiscal_period_id UUID NOT NULL REFERENCES fiscal_periods(id) ON DELETE CASCADE ON UPDATE CASCADE,
  name_ar VARCHAR(255) NOT NULL, name_en VARCHAR(255),
  task_type VARCHAR(30) NOT NULL, -- complete_ops / reconcile / adjust / review
  description TEXT,
  assignee UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  status VARCHAR(30) NOT NULL DEFAULT 'pending',
  status_changed_at TIMESTAMPTZ, status_changed_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  approved_at TIMESTAMPTZ, approved_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  is_mandatory BOOLEAN NOT NULL DEFAULT TRUE,
  seq INTEGER NOT NULL DEFAULT 10,
  due_on DATE, completed_at TIMESTAMPTZ, notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, deleted_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT ck_ct_type CHECK (task_type IN ('complete_ops','reconcile','adjust','review')),
  CONSTRAINT ck_ct_status CHECK (status IN ('pending','in_progress','done','waived'))
);

CREATE TABLE IF NOT EXISTS closing_task_items (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE ON UPDATE CASCADE,
  closing_task_id UUID NOT NULL REFERENCES closing_tasks(id) ON DELETE CASCADE ON UPDATE CASCADE,
  item_name VARCHAR(255) NOT NULL, description TEXT,
  status VARCHAR(30) NOT NULL DEFAULT 'pending',
  status_changed_at TIMESTAMPTZ, status_changed_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  approved_at TIMESTAMPTZ, approved_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  notes TEXT, attachment_url TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, deleted_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT ck_cti_status CHECK (status IN ('pending','in_progress','done','waived'))
);

CREATE TABLE IF NOT EXISTS closing_task_assignments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE ON UPDATE CASCADE,
  closing_task_id UUID NOT NULL REFERENCES closing_tasks(id) ON DELETE CASCADE ON UPDATE CASCADE,
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE ON UPDATE CASCADE,
  role_in_task VARCHAR(50) NOT NULL DEFAULT 'executor', -- executor / reviewer
  assigned_on DATE NOT NULL DEFAULT CURRENT_DATE,
  is_completed BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, deleted_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT uq_cta UNIQUE (tenant_id, closing_task_id, user_id)
);

CREATE TABLE IF NOT EXISTS closing_snapshots (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  fiscal_period_id UUID NOT NULL UNIQUE REFERENCES fiscal_periods(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  entries_count INTEGER NOT NULL DEFAULT 0 CHECK (entries_count >= 0),
  last_entry_no VARCHAR(40),
  total_debit NUMERIC(18,3) NOT NULL DEFAULT 0,
  total_credit NUMERIC(18,3) NOT NULL DEFAULT 0,
  unposted_invoices INTEGER NOT NULL DEFAULT 0,
  unposted_entries INTEGER NOT NULL DEFAULT 0,
  snapshot_hash VARCHAR(128) NOT NULL,
  status VARCHAR(30) NOT NULL DEFAULT 'final',
  status_changed_at TIMESTAMPTZ, status_changed_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  approved_at TIMESTAMPTZ, approved_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  taken_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  taken_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, deleted_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT ck_snap_balanced CHECK (total_debit = total_credit)
);

CREATE TABLE IF NOT EXISTS closing_approvals (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  fiscal_period_id UUID NOT NULL REFERENCES fiscal_periods(id) ON DELETE CASCADE ON UPDATE CASCADE,
  approver_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  approval_type VARCHAR(20) NOT NULL, -- interim / final
  status VARCHAR(30) NOT NULL DEFAULT 'pending',
  status_changed_at TIMESTAMPTZ, status_changed_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  approved_at TIMESTAMPTZ, approved_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  reason TEXT,
  decided_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, deleted_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT ck_ca_type CHECK (approval_type IN ('interim','final')),
  CONSTRAINT ck_ca_status CHECK (status IN ('pending','approved','rejected')),
  CONSTRAINT uq_ca UNIQUE (tenant_id, fiscal_period_id, approver_id, approval_type)
);

-- ================= الفهارس =================
CREATE INDEX IF NOT EXISTS idx_accpol_tenant ON accounting_policies(tenant_id);
CREATE INDEX IF NOT EXISTS idx_accpol_entity ON accounting_policies(entity_id) WHERE is_deleted=FALSE;
CREATE INDEX IF NOT EXISTS idx_accpol_status ON accounting_policies(status) WHERE is_deleted=FALSE;
CREATE INDEX IF NOT EXISTS idx_pv_tenant ON policy_versions(tenant_id);
CREATE INDEX IF NOT EXISTS idx_pv_policy ON policy_versions(policy_id);
CREATE INDEX IF NOT EXISTS idx_pa_tenant ON policy_applicability(tenant_id);
CREATE INDEX IF NOT EXISTS idx_pa_policy ON policy_applicability(policy_id);
CREATE INDEX IF NOT EXISTS idx_fy_tenant ON fiscal_years(tenant_id);
CREATE INDEX IF NOT EXISTS idx_fy_entity_year ON fiscal_years(entity_id, code) WHERE is_deleted=FALSE;
CREATE INDEX IF NOT EXISTS idx_fp_tenant ON fiscal_periods(tenant_id);
CREATE INDEX IF NOT EXISTS idx_fp_entity_year ON fiscal_periods(entity_id, fiscal_year_id) WHERE is_deleted=FALSE;
CREATE INDEX IF NOT EXISTS idx_fp_status ON fiscal_periods(status) WHERE is_deleted=FALSE;
CREATE INDEX IF NOT EXISTS idx_plock_tenant ON period_locks(tenant_id);
CREATE INDEX IF NOT EXISTS idx_plock_period ON period_locks(fiscal_period_id);
CREATE INDEX IF NOT EXISTS idx_ple_tenant ON period_lock_exceptions(tenant_id);
CREATE INDEX IF NOT EXISTS idx_ple_period ON period_lock_exceptions(fiscal_period_id);
CREATE INDEX IF NOT EXISTS idx_ct_tenant ON closing_tasks(tenant_id);
CREATE INDEX IF NOT EXISTS idx_ct_period ON closing_tasks(fiscal_period_id);
CREATE INDEX IF NOT EXISTS idx_ct_status ON closing_tasks(status) WHERE is_deleted=FALSE;
CREATE INDEX IF NOT EXISTS idx_cti_task ON closing_task_items(closing_task_id);
CREATE INDEX IF NOT EXISTS idx_cta_task ON closing_task_assignments(closing_task_id);
CREATE INDEX IF NOT EXISTS idx_snap_tenant ON closing_snapshots(tenant_id);
CREATE INDEX IF NOT EXISTS idx_ca_period ON closing_approvals(fiscal_period_id);
CREATE INDEX IF NOT EXISTS idx_fp_active ON fiscal_periods(deleted_at) WHERE is_deleted=FALSE;

-- ================= Triggers =================
-- منع تداخل الفترات داخل نفس الكيان والسنة
CREATE OR REPLACE FUNCTION fn_no_overlapping_periods() RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  IF EXISTS (SELECT 1 FROM fiscal_periods WHERE entity_id=NEW.entity_id AND fiscal_year_id=NEW.fiscal_year_id
    AND id<>NEW.id AND is_deleted=FALSE AND daterange(starts_on,ends_on,'[]') && daterange(NEW.starts_on,NEW.ends_on,'[]')) THEN
    RAISE EXCEPTION 'OVERLAPPING_PERIOD %', NEW.code;
  END IF;
  IF NEW.starts_on < (SELECT starts_on FROM fiscal_years WHERE id=NEW.fiscal_year_id) OR NEW.ends_on > (SELECT ends_on FROM fiscal_years WHERE id=NEW.fiscal_year_id) THEN
    RAISE EXCEPTION 'PERIOD_OUTSIDE_YEAR %', NEW.code;
  END IF;
  RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS trg_fp_no_overlap ON fiscal_periods;
CREATE TRIGGER trg_fp_no_overlap BEFORE INSERT OR UPDATE ON fiscal_periods FOR EACH ROW EXECUTE FUNCTION fn_no_overlapping_periods();

-- منع تعديل سياسة معتمدة (التغيير عبر نسخة جديدة فقط)
CREATE OR REPLACE FUNCTION fn_freeze_approved_policy() RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  IF OLD.status='approved' AND (NEW.framework IS DISTINCT FROM OLD.framework OR NEW.inventory_method IS DISTINCT FROM OLD.inventory_method OR NEW.code IS DISTINCT FROM OLD.code) THEN
    RAISE EXCEPTION 'APPROVED_POLICY_FROZEN_USE_NEW_VERSION %', OLD.id;
  END IF;
  RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS trg_accpol_freeze ON accounting_policies;
CREATE TRIGGER trg_accpol_freeze BEFORE UPDATE ON accounting_policies FOR EACH ROW EXECUTE FUNCTION fn_freeze_approved_policy();

-- updated_at + version لكل جداول المرحلة
DO $$ DECLARE t TEXT; arr TEXT[] := ARRAY['accounting_policies','policy_versions','policy_applicability','fiscal_years','fiscal_periods','period_locks','period_lock_exceptions','closing_tasks','closing_task_items','closing_task_assignments','closing_snapshots','closing_approvals'];
BEGIN FOREACH t IN ARRAY arr LOOP EXECUTE format('DROP TRIGGER IF EXISTS trg_%s_touch ON %I',t,t); EXECUTE format('CREATE TRIGGER trg_%s_touch BEFORE UPDATE ON %I FOR EACH ROW EXECUTE FUNCTION fn_touch_updated_at()',t,t); END LOOP; END $$;

-- ================= RLS =================
DO $$ DECLARE t TEXT; arr TEXT[] := ARRAY['accounting_policies','policy_versions','policy_applicability','fiscal_years','fiscal_periods','period_locks','period_lock_exceptions','closing_tasks','closing_task_items','closing_task_assignments','closing_snapshots','closing_approvals'];
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

-- ================= Seed =================
-- سياسة افتراضية تُزرع لكل entity جديد عبر التطبيق (قالب):
-- framework=IFRS_SME, inventory=average (الوزن المرجح — شائع JO), depreciation=straight_line, rounding half_up 0.005
-- سنة مالية: 12 فترة شهرية تبدأ يناير (الأردن)، period 13 للتسويات فقط عند الحاجة.

-- ================= توثيق =================
COMMENT ON TABLE accounting_policies IS 'السياسات المحاسبية لكل كيان (IFRS/SME/نقدي) — التعديل بعد الاعتماد عبر نسخة | Policies per entity';
COMMENT ON TABLE policy_versions IS 'إصدارات السياسة المؤرخة (لا إعادة كتابة التاريخ) | Versioned policy history';
COMMENT ON TABLE policy_applicability IS 'نطاق تطبيق السياسة (كيان/فرع/مستند) بالأولوية | Applicability scope';
COMMENT ON TABLE fiscal_years IS 'السنوات المالية (رمز YYYY) لكل كيان | Fiscal years YYYY';
COMMENT ON TABLE fiscal_periods IS 'الفترات (YYYY-MM، 1-13) — عدم تداخل إجباري عبر Trigger | Periods, no-overlap enforced';
COMMENT ON TABLE period_locks IS 'أقفال الفترات (تشغيلي/نهائي) | Soft/hard locks';
COMMENT ON TABLE period_lock_exceptions IS 'استثناءات القفل لمستخدمين (مؤقتة ومعتمدة) | Lock exceptions';
COMMENT ON TABLE closing_tasks IS 'مهام الإقفال (إلزامية/اختيارية بالترتيب) | Closing checklist';
COMMENT ON TABLE closing_task_items IS 'بنود المهمة التفصيلية | Task line items';
COMMENT ON TABLE closing_task_assignments IS 'تعيين المنفذ/المراجع لكل مهمة | Assignments';
COMMENT ON TABLE closing_snapshots IS 'لقطة الإقفال المتوازنة (hash) — التقرير الرسمي منها | Immutable snapshot';
COMMENT ON TABLE closing_approvals IS 'اعتمادات الإقفال (مرحلي/نهائي، مانع ذاتي) | Approvals';
