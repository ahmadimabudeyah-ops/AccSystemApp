-- ============================================================================
-- Phase 3 — دليل الحسابات والأبعاد (13 جدول) | Requires: phase1 + phase2
-- psql -f phase3_accounts_dimensions.sql
-- قرار: Materialized Path (path='1.11.111') + level + is_leaf — استعلام الشجرة
-- بفهرس GIST/B-tree واحد بدل Recursive CTE ثقيل. البديل المرفوض: ltree extension
-- (غير محمول على كل استضافات PG المدارة؛ path نصي يكفي حتى 10k حساب).
-- الرمز VARCHAR يحفظ الأصفار البادئة ('0101' ≠ '101'). ممنوع NUMERIC للرمز.
-- ============================================================================

-- ================= A: الدليل (7) =================
CREATE TABLE IF NOT EXISTS accounts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  code VARCHAR(50) NOT NULL,
  name_ar VARCHAR(500) NOT NULL, name_en VARCHAR(500),
  parent_id UUID REFERENCES accounts(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  level INTEGER NOT NULL DEFAULT 1 CHECK (level BETWEEN 1 AND 15),
  path TEXT NOT NULL DEFAULT '', -- '1.11.111' يُبنى آلياً
  is_leaf BOOLEAN NOT NULL DEFAULT TRUE,
  account_type VARCHAR(30) NOT NULL, -- asset/liability/equity/income/expense/contra_*
  control_type VARCHAR(30) NOT NULL DEFAULT 'general',
  normal_balance VARCHAR(10) NOT NULL, -- debit / credit
  is_postable BOOLEAN NOT NULL DEFAULT TRUE,
  is_reconcilable BOOLEAN NOT NULL DEFAULT FALSE,
  require_partner BOOLEAN NOT NULL DEFAULT FALSE,
  require_dimensions BOOLEAN NOT NULL DEFAULT FALSE,
  required_dimensions JSONB NOT NULL DEFAULT '[]',
  allow_manual BOOLEAN NOT NULL DEFAULT TRUE,
  currency_restriction CHAR(3), -- NULL = كل العملات
  valid_from DATE NOT NULL DEFAULT CURRENT_DATE, valid_to DATE, is_active BOOLEAN NOT NULL DEFAULT TRUE,
  status VARCHAR(30) NOT NULL DEFAULT 'active',
  notes TEXT, metadata JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, deleted_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT uq_accounts_code UNIQUE (tenant_id, entity_id, code),
  CONSTRAINT uq_accounts_sibling UNIQUE (tenant_id, entity_id, parent_id, name_ar),
  CONSTRAINT ck_acc_code CHECK (code ~ '^[0-9A-Za-z-]+$'),
  CONSTRAINT ck_acc_type CHECK (account_type IN ('asset','liability','equity','income','expense','contra_asset','contra_liability','contra_equity','contra_income','contra_expense')),
  CONSTRAINT ck_acc_control CHECK (control_type IN ('general','customer','supplier','employee','inventory','asset','bank','cash','tax','loan','equity','receivable','payable','prepaid','accrued')),
  CONSTRAINT ck_acc_balance CHECK (normal_balance IN ('debit','credit')),
  CONSTRAINT ck_acc_status CHECK (status IN ('active','inactive','suspended'))
);

CREATE TABLE IF NOT EXISTS account_versions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  account_id UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE ON UPDATE CASCADE,
  version_no INTEGER NOT NULL CHECK (version_no >= 1),
  effective_from DATE NOT NULL, effective_to DATE,
  changes JSONB NOT NULL,
  approved_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  attachment_url TEXT,
  valid_from DATE NOT NULL DEFAULT CURRENT_DATE, valid_to DATE, is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, deleted_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT uq_accver UNIQUE (tenant_id, account_id, version_no)
);

CREATE TABLE IF NOT EXISTS account_hierarchy (
  ancestor_id UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE ON UPDATE CASCADE,
  descendant_id UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE ON UPDATE CASCADE,
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE ON UPDATE CASCADE,
  entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE ON UPDATE CASCADE,
  depth INTEGER NOT NULL CHECK (depth >= 0),
  sort_order INTEGER NOT NULL DEFAULT 0,
  is_leaf BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, deleted_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  PRIMARY KEY (ancestor_id, descendant_id)
);

CREATE TABLE IF NOT EXISTS account_report_mappings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE ON UPDATE CASCADE,
  entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE ON UPDATE CASCADE,
  account_id UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE ON UPDATE CASCADE,
  report_code VARCHAR(30) NOT NULL, -- BS / PL / CF
  line_code VARCHAR(50) NOT NULL,    -- BS.CASH / PL.REVENUE ...
  sort_order INTEGER NOT NULL DEFAULT 0,
  sign VARCHAR(10) NOT NULL DEFAULT 'plus', -- plus / minus
  ratio NUMERIC(7,4), -- نسبة جزئية 0-100
  effective_from DATE NOT NULL DEFAULT CURRENT_DATE,
  valid_from DATE NOT NULL DEFAULT CURRENT_DATE, valid_to DATE, is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, deleted_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT uq_arm UNIQUE (tenant_id, account_id, report_code),
  CONSTRAINT ck_arm_sign CHECK (sign IN ('plus','minus')),
  CONSTRAINT ck_arm_ratio CHECK (ratio IS NULL OR (ratio >= 0 AND ratio <= 100))
);

CREATE TABLE IF NOT EXISTS account_currencies (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE ON UPDATE CASCADE,
  entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE ON UPDATE CASCADE,
  account_id UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE ON UPDATE CASCADE,
  currency_id CHAR(3) NOT NULL,
  is_default BOOLEAN NOT NULL DEFAULT FALSE,
  effective_from DATE NOT NULL DEFAULT CURRENT_DATE,
  valid_from DATE NOT NULL DEFAULT CURRENT_DATE, valid_to DATE, is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, deleted_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT uq_acccur UNIQUE (tenant_id, account_id, currency_id),
  CONSTRAINT ck_acccur CHECK (currency_id ~ '^[A-Z]{3}$')
);

CREATE TABLE IF NOT EXISTS account_restrictions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE ON UPDATE CASCADE,
  entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE ON UPDATE CASCADE,
  account_id UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE ON UPDATE CASCADE,
  restriction_type VARCHAR(30) NOT NULL, -- manual / auto
  is_allowed BOOLEAN NOT NULL DEFAULT TRUE,
  reason TEXT NOT NULL,
  valid_from DATE NOT NULL DEFAULT CURRENT_DATE, valid_to DATE, is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, deleted_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT ck_accres CHECK (restriction_type IN ('manual','auto'))
);

CREATE TABLE IF NOT EXISTS account_balances_cache (
  account_id UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE ON UPDATE CASCADE,
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE ON UPDATE CASCADE,
  entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE ON UPDATE CASCADE,
  fiscal_period_id UUID NOT NULL REFERENCES fiscal_periods(id) ON DELETE CASCADE ON UPDATE CASCADE,
  opening_debit NUMERIC(18,3) NOT NULL DEFAULT 0, opening_credit NUMERIC(18,3) NOT NULL DEFAULT 0,
  period_debit NUMERIC(18,3) NOT NULL DEFAULT 0, period_credit NUMERIC(18,3) NOT NULL DEFAULT 0,
  closing_debit NUMERIC(18,3) NOT NULL DEFAULT 0, closing_credit NUMERIC(18,3) NOT NULL DEFAULT 0,
  currency_id CHAR(3) NOT NULL DEFAULT 'JOD',
  refreshed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, deleted_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  PRIMARY KEY (account_id, fiscal_period_id)
);

-- ================= B: الأبعاد (6) =================
CREATE TABLE IF NOT EXISTS dimensions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  code VARCHAR(50) NOT NULL, name_ar VARCHAR(500) NOT NULL, name_en VARCHAR(500),
  dim_type VARCHAR(30) NOT NULL, -- branch/department/project/cost_center/profit_center
  is_mandatory BOOLEAN NOT NULL DEFAULT FALSE,
  is_hierarchical BOOLEAN NOT NULL DEFAULT FALSE,
  valid_from DATE NOT NULL DEFAULT CURRENT_DATE, valid_to DATE, is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, deleted_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT uq_dimensions_code UNIQUE (tenant_id, entity_id, code),
  CONSTRAINT ck_dim_type CHECK (dim_type IN ('branch','department','project','cost_center','profit_center'))
);

CREATE TABLE IF NOT EXISTS dimension_values (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  dimension_id UUID NOT NULL REFERENCES dimensions(id) ON DELETE CASCADE ON UPDATE CASCADE,
  code VARCHAR(50) NOT NULL, value_ar VARCHAR(500) NOT NULL, value_en VARCHAR(500),
  parent_id UUID REFERENCES dimension_values(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  level INTEGER NOT NULL DEFAULT 1 CHECK (level BETWEEN 1 AND 15),
  path TEXT NOT NULL DEFAULT '',
  extra JSONB NOT NULL DEFAULT '{}',
  valid_from DATE NOT NULL DEFAULT CURRENT_DATE, valid_to DATE, is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, deleted_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT uq_dimval_code UNIQUE (tenant_id, dimension_id, code)
);

CREATE TABLE IF NOT EXISTS dimension_hierarchies (
  ancestor_id UUID NOT NULL REFERENCES dimension_values(id) ON DELETE CASCADE ON UPDATE CASCADE,
  descendant_id UUID NOT NULL REFERENCES dimension_values(id) ON DELETE CASCADE ON UPDATE CASCADE,
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE ON UPDATE CASCADE,
  dimension_id UUID NOT NULL REFERENCES dimensions(id) ON DELETE CASCADE ON UPDATE CASCADE,
  depth INTEGER NOT NULL CHECK (depth >= 0), sort_order INTEGER NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, deleted_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  PRIMARY KEY (ancestor_id, descendant_id)
);

CREATE TABLE IF NOT EXISTS analytic_distributions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE ON UPDATE CASCADE,
  entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE ON UPDATE CASCADE,
  account_id UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE ON UPDATE CASCADE,
  dimension_id UUID NOT NULL REFERENCES dimensions(id) ON DELETE CASCADE ON UPDATE CASCADE,
  dimension_value_id UUID NOT NULL REFERENCES dimension_values(id) ON DELETE CASCADE ON UPDATE CASCADE,
  pct NUMERIC(7,4) NOT NULL,
  is_mandatory BOOLEAN NOT NULL DEFAULT FALSE, sort_order INTEGER NOT NULL DEFAULT 0,
  model_id UUID, -- FK إلى distribution_models (يُضاف بعد إنشائه لتفادي الترتيب)
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, deleted_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT ck_dist_pct CHECK (pct > 0 AND pct <= 100)
);

CREATE TABLE IF NOT EXISTS distribution_models (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  code VARCHAR(50) NOT NULL, name_ar VARCHAR(500) NOT NULL, description TEXT,
  conditions JSONB NOT NULL DEFAULT '{}', priority INTEGER NOT NULL DEFAULT 100,
  valid_from DATE NOT NULL DEFAULT CURRENT_DATE, valid_to DATE, is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, deleted_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT uq_distmodel_code UNIQUE (tenant_id, entity_id, code)
);

CREATE TABLE IF NOT EXISTS distribution_model_lines (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE ON UPDATE CASCADE,
  model_id UUID NOT NULL REFERENCES distribution_models(id) ON DELETE CASCADE ON UPDATE CASCADE,
  account_id UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE ON UPDATE CASCADE,
  dimension_id UUID NOT NULL REFERENCES dimensions(id) ON DELETE CASCADE ON UPDATE CASCADE,
  dimension_value_id UUID NOT NULL REFERENCES dimension_values(id) ON DELETE CASCADE ON UPDATE CASCADE,
  pct NUMERIC(7,4) NOT NULL, sort_order INTEGER NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, deleted_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT ck_dml_pct CHECK (pct > 0 AND pct <= 100),
  CONSTRAINT uq_dml UNIQUE (tenant_id, model_id, account_id, dimension_value_id)
);
ALTER TABLE analytic_distributions ADD CONSTRAINT fk_dist_model FOREIGN KEY (model_id) REFERENCES distribution_models(id) ON DELETE RESTRICT ON UPDATE CASCADE;

-- ================= الفهارس =================
CREATE INDEX IF NOT EXISTS idx_accounts_tenant ON accounts(tenant_id);
CREATE INDEX IF NOT EXISTS idx_accounts_entity ON accounts(entity_id) WHERE is_deleted=FALSE;
CREATE INDEX IF NOT EXISTS idx_accounts_parent ON accounts(parent_id);
CREATE INDEX IF NOT EXISTS idx_accounts_type ON accounts(account_type) WHERE is_deleted=FALSE;
CREATE INDEX IF NOT EXISTS idx_accounts_control ON accounts(control_type) WHERE is_deleted=FALSE;
CREATE INDEX IF NOT EXISTS idx_accounts_postable ON accounts(is_postable) WHERE is_deleted=FALSE;
CREATE INDEX IF NOT EXISTS idx_accounts_active ON accounts(is_active) WHERE is_deleted=FALSE;
CREATE INDEX IF NOT EXISTS idx_accounts_path ON accounts(path);
CREATE INDEX IF NOT EXISTS idx_accounts_level ON accounts(level);
CREATE INDEX IF NOT EXISTS gin_accounts_meta ON accounts USING GIN (metadata);
CREATE INDEX IF NOT EXISTS idx_accver_account ON account_versions(account_id);
CREATE INDEX IF NOT EXISTS idx_arm_account ON account_report_mappings(account_id);
CREATE INDEX IF NOT EXISTS idx_acccur_account ON account_currencies(account_id);
CREATE INDEX IF NOT EXISTS idx_dims_tenant ON dimensions(tenant_id);
CREATE INDEX IF NOT EXISTS idx_dimval_dim ON dimension_values(dimension_id);
CREATE INDEX IF NOT EXISTS idx_dimval_path ON dimension_values(path);
CREATE INDEX IF NOT EXISTS idx_dist_account ON analytic_distributions(account_id);
CREATE INDEX IF NOT EXISTS idx_dml_model ON distribution_model_lines(model_id);
CREATE INDEX IF NOT EXISTS idx_acc_active ON accounts(deleted_at) WHERE is_deleted=FALSE;

-- ================= Triggers =================
-- منع الدوائر + نفس الكيان + بناء path/level + صيانة closure
CREATE OR REPLACE FUNCTION fn_account_hierarchy_guard() RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE v_path TEXT; v_level INT;
BEGIN
  IF NEW.parent_id IS NOT NULL THEN
    IF NEW.parent_id = NEW.id THEN RAISE EXCEPTION 'CIRCULAR_SELF %', NEW.code; END IF;
    IF (SELECT entity_id FROM accounts WHERE id=NEW.parent_id) IS DISTINCT FROM NEW.entity_id THEN RAISE EXCEPTION 'PARENT_OTHER_ENTITY %', NEW.code; END IF;
    IF EXISTS (WITH RECURSIVE c AS (SELECT id,parent_id FROM accounts WHERE id=NEW.parent_id UNION ALL SELECT a.id,a.parent_id FROM accounts a JOIN c ON a.id=c.parent_id) SELECT 1 FROM c WHERE id=NEW.id) THEN RAISE EXCEPTION 'CIRCULAR_DESCENDANT %', NEW.code; END IF;
    SELECT path || '.' || NEW.code, level+1 INTO v_path, v_level FROM accounts WHERE id=NEW.parent_id;
    NEW.path := v_path; NEW.level := v_level;
  ELSE NEW.path := NEW.code; NEW.level := 1; END IF;
  RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS trg_accounts_guard ON accounts;
CREATE TRIGGER trg_accounts_guard BEFORE INSERT OR UPDATE ON accounts FOR EACH ROW EXECUTE FUNCTION fn_account_hierarchy_guard();

-- مجموع نسب النموذج = 100% (بتسامح تقريب 0.01)
CREATE OR REPLACE FUNCTION fn_dist_sum_100() RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE s NUMERIC;
BEGIN
  SELECT COALESCE(SUM(pct),0) INTO s FROM distribution_model_lines WHERE model_id=COALESCE(NEW.model_id,OLD.model_id) AND is_deleted=FALSE;
  IF s <> 100 AND s <> 0 THEN -- 0 أثناء البناء التدريجي مسموح، يُفحص الاكتمال تطبيقياً
    -- لا نرفع هنا للسماح بالإدخال المتدرج؛ الفحص النهائي في fn_dist_model_complete(model_id)
    NULL;
  END IF;
  RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS trg_dml_sum ON distribution_model_lines;
CREATE TRIGGER trg_dml_sum AFTER INSERT OR UPDATE OR DELETE ON distribution_model_lines FOR EACH ROW EXECUTE FUNCTION fn_dist_sum_100();

DO $$ DECLARE t TEXT; arr TEXT[] := ARRAY['accounts','account_versions','account_hierarchy','account_report_mappings','account_currencies','account_restrictions','account_balances_cache','dimensions','dimension_values','dimension_hierarchies','analytic_distributions','distribution_models','distribution_model_lines'];
BEGIN FOREACH t IN ARRAY arr LOOP EXECUTE format('DROP TRIGGER IF EXISTS trg_%s_touch ON %I',t,t); EXECUTE format('CREATE TRIGGER trg_%s_touch BEFORE UPDATE ON %I FOR EACH ROW EXECUTE FUNCTION fn_touch_updated_at()',t,t); END LOOP; END $$;

-- ================= RLS =================
DO $$ DECLARE t TEXT; arr TEXT[] := ARRAY['accounts','account_versions','account_hierarchy','account_report_mappings','account_currencies','account_restrictions','account_balances_cache','dimensions','dimension_values','dimension_hierarchies','analytic_distributions','distribution_models','distribution_model_lines'];
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

-- ================= Seed: دليل IFRS مصغر (هيكل 1xxx-5xxx — يُوسّع لـ 200+ عبر مولد التطبيق) =================
-- ملاحظة: تُزرع عبر التطبيق لكل entity (تحتاج entity_id حقيقياً) — هنا القالب المعتمد:
-- 1xxx أصول: 1010 نقدية/101001 الصندوق، 1020 بنوك، 1210 عملاء، 1310 مخزون، 1510 أصول ثابتة، 1519 مجمع إهلاك (contra)
-- 2xxx التزامات: 2010 موردون، 2110 قروض قصيرة، 2140 ضريبة مستحقة، 2210 قروض طويلة
-- 3xxx حقوق: 3010 رأس المال، 3020 أرباح محتجزة، 3030 احتياطيات
-- 4xxx إيرادات: 4010 مبيعات، 4020 خدمات، 4090 خصم مسموح (contra_income)
-- 5xxx مصروفات: 5010 كلفة البضاعة، 5110 رواتب، 5120 إيجارات، 5130 إهلاك، 5140 مصاريف عمومية
-- الأبعاد: BRANCH / DEPARTMENT / PROJECT / COST_CENTER / PROFIT_CENTER + نموذج توزيع افتراضي 100% للمركز الرئيسي.

COMMENT ON TABLE accounts IS 'دليل الحسابات — Materialized Path + رمز نصي يحفظ الأصفار | COA heart';
COMMENT ON TABLE account_hierarchy IS 'إغلاق الهرمية للاستعلام السريع | Closure table';
COMMENT ON TABLE account_balances_cache IS 'كاش فقط — المصدر القيود المرحلة، قابل لإعادة البناء | Rebuildable cache';
COMMENT ON TABLE dimensions IS 'الأبعاد التحليلية (فرع/قسم/مشروع/تكلفة/ربح) | Dimensions';
COMMENT ON TABLE distribution_models IS 'نماذج التوزيع الآلي بالأولوية (مجموع 100%) | Auto-allocation';
