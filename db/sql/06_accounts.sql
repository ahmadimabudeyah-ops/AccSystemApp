-- ============================================================================
-- 06_accounts.sql — دليل الحسابات والأبعاد (المجموعة 4)
-- الفترة المالية في 06b? لا — الفترات في 05b/policies. هنا الحسابات فقط.
-- account_balances_cache يُحدّث عبر Trigger بعد الترحيل (لا مصدر رسمي).
-- ============================================================================

CREATE TABLE IF NOT EXISTS accounting_policies (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
  entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE RESTRICT,
  version INTEGER NOT NULL, effective_from DATE NOT NULL, effective_to DATE,
  inventory_method VARCHAR(20) NOT NULL DEFAULT 'average', depreciation_method VARCHAR(20) DEFAULT 'straight_line',
  revenue_recognition TEXT, notes TEXT,
  valid_from DATE NOT NULL DEFAULT CURRENT_DATE, valid_to DATE, is_active BOOLEAN NOT NULL DEFAULT TRUE,
  status VARCHAR(50) NOT NULL DEFAULT 'active',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID NOT NULL REFERENCES users(id), updated_by UUID NOT NULL REFERENCES users(id),
  deleted_at TIMESTAMPTZ, deleted_by UUID REFERENCES users(id), is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT uq_accpol_ver UNIQUE (tenant_id, entity_id, version)
);

CREATE TABLE IF NOT EXISTS fiscal_years (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
  entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE RESTRICT,
  code VARCHAR(20) NOT NULL, starts_on DATE NOT NULL, ends_on DATE NOT NULL,
  status VARCHAR(50) NOT NULL DEFAULT 'open',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID NOT NULL REFERENCES users(id), updated_by UUID NOT NULL REFERENCES users(id),
  version INTEGER NOT NULL DEFAULT 1, deleted_at TIMESTAMPTZ, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT uq_fy UNIQUE (tenant_id, entity_id, code),
  CONSTRAINT ck_fy_dates CHECK (ends_on > starts_on)
);

CREATE TABLE IF NOT EXISTS accounts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
  entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE RESTRICT,
  code VARCHAR(30) NOT NULL, name_ar VARCHAR(255) NOT NULL, name_en VARCHAR(255),
  account_type account_type NOT NULL, control_type account_control_type NOT NULL DEFAULT 'general',
  parent_id UUID REFERENCES accounts(id),
  is_postable BOOLEAN NOT NULL DEFAULT TRUE,
  currency_id currency_code, -- NULL = كل العملات
  valid_from DATE NOT NULL DEFAULT CURRENT_DATE, valid_to DATE, is_active BOOLEAN NOT NULL DEFAULT TRUE,
  status VARCHAR(50) NOT NULL DEFAULT 'active',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID NOT NULL REFERENCES users(id), updated_by UUID NOT NULL REFERENCES users(id),
  version INTEGER NOT NULL DEFAULT 1, deleted_at TIMESTAMPTZ, deleted_by UUID REFERENCES users(id), is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT uq_accounts_code UNIQUE (tenant_id, entity_id, code)
);
COMMENT ON TABLE accounts IS 'دليل الحسابات | Chart of accounts — code فريد لكل كيان';

CREATE TABLE IF NOT EXISTS account_versions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
  account_id UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
  version INTEGER NOT NULL, code VARCHAR(30) NOT NULL, name_ar VARCHAR(255) NOT NULL,
  valid_from DATE NOT NULL, valid_to DATE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID NOT NULL REFERENCES users(id), updated_by UUID NOT NULL REFERENCES users(id),
  deleted_at TIMESTAMPTZ, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT uq_accver UNIQUE (tenant_id, account_id, version)
);

CREATE TABLE IF NOT EXISTS account_hierarchy (
  ancestor_id UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
  descendant_id UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
  depth INTEGER NOT NULL CHECK (depth >= 0),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID NOT NULL REFERENCES users(id), updated_by UUID NOT NULL REFERENCES users(id),
  version INTEGER NOT NULL DEFAULT 1, deleted_at TIMESTAMPTZ, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  PRIMARY KEY (ancestor_id, descendant_id)
);

CREATE TABLE IF NOT EXISTS account_report_mappings (
  account_id UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
  report_code VARCHAR(30) NOT NULL, -- BS/PL/CF
  line_code VARCHAR(50) NOT NULL,   -- BS.CASH, PL.REVENUE...
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID NOT NULL REFERENCES users(id), updated_by UUID NOT NULL REFERENCES users(id),
  version INTEGER NOT NULL DEFAULT 1, deleted_at TIMESTAMPTZ, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  PRIMARY KEY (account_id, report_code)
);

CREATE TABLE IF NOT EXISTS account_balances_cache (
  account_id UUID NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
  entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
  period_id UUID, -- FK لاحقاً إلى fiscal_periods (يُنشأ في 06b لتفادي ترتيب FK)
  debit_total signed_money NOT NULL DEFAULT 0, credit_total signed_money NOT NULL DEFAULT 0,
  balance signed_money NOT NULL DEFAULT 0,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID NOT NULL REFERENCES users(id), updated_by UUID NOT NULL REFERENCES users(id),
  version INTEGER NOT NULL DEFAULT 1, deleted_at TIMESTAMPTZ, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  PRIMARY KEY (account_id, entity_id, period_id)
);
COMMENT ON TABLE account_balances_cache IS 'كاش فقط — المصدر الرسمي journal_lines المرحلة | Cache only';

-- ---------- الفترات والإقفال (المجموعة 3 — هنا لضمان ترتيب FK قبل القيود) ----------
CREATE TABLE IF NOT EXISTS fiscal_periods (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
  fiscal_year_id UUID NOT NULL REFERENCES fiscal_years(id) ON DELETE RESTRICT,
  entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE RESTRICT,
  period_no INTEGER NOT NULL CHECK (period_no BETWEEN 1 AND 13),
  starts_on DATE NOT NULL, ends_on DATE NOT NULL,
  status period_status NOT NULL DEFAULT 'open',
  status_changed_at TIMESTAMPTZ, status_changed_by UUID REFERENCES users(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID NOT NULL REFERENCES users(id), updated_by UUID NOT NULL REFERENCES users(id),
  version INTEGER NOT NULL DEFAULT 1, deleted_at TIMESTAMPTZ, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT uq_fiscal_periods UNIQUE (tenant_id, entity_id, fiscal_year_id, period_no),
  CONSTRAINT ck_period_dates CHECK (ends_on >= starts_on)
);

CREATE TABLE IF NOT EXISTS period_locks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
  fiscal_period_id UUID NOT NULL REFERENCES fiscal_periods(id) ON DELETE CASCADE,
  lock_type VARCHAR(30) NOT NULL, locked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), locked_by UUID NOT NULL REFERENCES users(id),
  reason TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID NOT NULL REFERENCES users(id), updated_by UUID NOT NULL REFERENCES users(id),
  version INTEGER NOT NULL DEFAULT 1, deleted_at TIMESTAMPTZ, is_deleted BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS closing_snapshots (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
  entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE RESTRICT,
  fiscal_period_id UUID NOT NULL UNIQUE REFERENCES fiscal_periods(id) ON DELETE RESTRICT,
  trial_balance JSONB NOT NULL, hash VARCHAR(128) NOT NULL, taken_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  status VARCHAR(50) NOT NULL DEFAULT 'final',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID NOT NULL REFERENCES users(id), updated_by UUID NOT NULL REFERENCES users(id),
  version INTEGER NOT NULL DEFAULT 1, deleted_at TIMESTAMPTZ, is_deleted BOOLEAN NOT NULL DEFAULT FALSE
);

-- ---------- الأبعاد التحليلية ----------
CREATE TABLE IF NOT EXISTS dimensions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
  code VARCHAR(50) NOT NULL, name_ar VARCHAR(255) NOT NULL, name_en VARCHAR(255),
  valid_from DATE NOT NULL DEFAULT CURRENT_DATE, valid_to DATE, is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID NOT NULL REFERENCES users(id), updated_by UUID NOT NULL REFERENCES users(id),
  version INTEGER NOT NULL DEFAULT 1, deleted_at TIMESTAMPTZ, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT uq_dimensions_code UNIQUE (tenant_id, code)
);
CREATE TABLE IF NOT EXISTS dimension_values (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
  dimension_id UUID NOT NULL REFERENCES dimensions(id) ON DELETE CASCADE,
  code VARCHAR(50) NOT NULL, value_ar VARCHAR(255) NOT NULL, value_en VARCHAR(255),
  parent_id UUID REFERENCES dimension_values(id),
  valid_from DATE NOT NULL DEFAULT CURRENT_DATE, valid_to DATE, is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID NOT NULL REFERENCES users(id), updated_by UUID NOT NULL REFERENCES users(id),
  version INTEGER NOT NULL DEFAULT 1, deleted_at TIMESTAMPTZ, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT uq_dim_values UNIQUE (tenant_id, dimension_id, code)
);
CREATE TABLE IF NOT EXISTS distribution_models (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
  code VARCHAR(50) NOT NULL, name_ar VARCHAR(255) NOT NULL,
  rules JSONB NOT NULL,
  valid_from DATE NOT NULL DEFAULT CURRENT_DATE, valid_to DATE, is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID NOT NULL REFERENCES users(id), updated_by UUID NOT NULL REFERENCES users(id),
  version INTEGER NOT NULL DEFAULT 1, deleted_at TIMESTAMPTZ, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT uq_dist_models UNIQUE (tenant_id, code)
);
