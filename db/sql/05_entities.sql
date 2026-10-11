-- ============================================================================
-- 05_entities.sql — الكيانات والفروع (المجموعة 2)
-- التسلسل: tenant -> entities -> branches/departments. المجموعات للتجميع.
-- ============================================================================

CREATE TABLE IF NOT EXISTS entities (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
  code VARCHAR(30) NOT NULL, name_ar VARCHAR(255) NOT NULL, name_en VARCHAR(255),
  functional_currency currency_code NOT NULL DEFAULT 'JOD',
  timezone VARCHAR(64) NOT NULL DEFAULT 'Asia/Amman',
  is_consolidated BOOLEAN NOT NULL DEFAULT FALSE,
  valid_from DATE NOT NULL DEFAULT CURRENT_DATE, valid_to DATE, is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID NOT NULL REFERENCES users(id), updated_by UUID NOT NULL REFERENCES users(id),
  version INTEGER NOT NULL DEFAULT 1, deleted_at TIMESTAMPTZ, deleted_by UUID REFERENCES users(id), is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT uq_entities_tenant_code UNIQUE (tenant_id, code)
);
COMMENT ON TABLE entities IS 'الكيانات القانونية داخل المؤسسة (شركة/مدرسة) | Legal entities';

CREATE TABLE IF NOT EXISTS entity_settings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
  entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
  setting_key VARCHAR(150) NOT NULL, setting_value JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID NOT NULL REFERENCES users(id), updated_by UUID NOT NULL REFERENCES users(id),
  version INTEGER NOT NULL DEFAULT 1, deleted_at TIMESTAMPTZ, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT uq_entity_settings UNIQUE (tenant_id, entity_id, setting_key)
);

CREATE TABLE IF NOT EXISTS entity_legal_info (
  entity_id UUID PRIMARY KEY REFERENCES entities(id) ON DELETE CASCADE,
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
  commercial_reg VARCHAR(100), tax_id tax_id, national_id VARCHAR(50),
  legal_form VARCHAR(100), -- ذات مسؤولية محدودة/مساهمة/فردية
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID NOT NULL REFERENCES users(id), updated_by UUID NOT NULL REFERENCES users(id),
  version INTEGER NOT NULL DEFAULT 1, deleted_at TIMESTAMPTZ, is_deleted BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS branches (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
  entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE RESTRICT,
  code VARCHAR(30) NOT NULL, name_ar VARCHAR(255) NOT NULL, name_en VARCHAR(255),
  address JSONB, phone phone_number,
  valid_from DATE NOT NULL DEFAULT CURRENT_DATE, valid_to DATE, is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID NOT NULL REFERENCES users(id), updated_by UUID NOT NULL REFERENCES users(id),
  version INTEGER NOT NULL DEFAULT 1, deleted_at TIMESTAMPTZ, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT uq_branches_code UNIQUE (tenant_id, entity_id, code)
);

CREATE TABLE IF NOT EXISTS branch_settings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
  branch_id UUID NOT NULL REFERENCES branches(id) ON DELETE CASCADE,
  setting_key VARCHAR(150) NOT NULL, setting_value JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID NOT NULL REFERENCES users(id), updated_by UUID NOT NULL REFERENCES users(id),
  version INTEGER NOT NULL DEFAULT 1, deleted_at TIMESTAMPTZ, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT uq_branch_settings UNIQUE (tenant_id, branch_id, setting_key)
);

CREATE TABLE IF NOT EXISTS departments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
  entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE RESTRICT,
  code VARCHAR(30) NOT NULL, name_ar VARCHAR(255) NOT NULL, name_en VARCHAR(255),
  parent_id UUID REFERENCES departments(id),
  valid_from DATE NOT NULL DEFAULT CURRENT_DATE, valid_to DATE, is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID NOT NULL REFERENCES users(id), updated_by UUID NOT NULL REFERENCES users(id),
  version INTEGER NOT NULL DEFAULT 1, deleted_at TIMESTAMPTZ, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT uq_departments_code UNIQUE (tenant_id, entity_id, code)
);

CREATE TABLE IF NOT EXISTS positions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
  department_id UUID NOT NULL REFERENCES departments(id) ON DELETE RESTRICT,
  code VARCHAR(30) NOT NULL, title_ar VARCHAR(255) NOT NULL, title_en VARCHAR(255),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID NOT NULL REFERENCES users(id), updated_by UUID NOT NULL REFERENCES users(id),
  version INTEGER NOT NULL DEFAULT 1, deleted_at TIMESTAMPTZ, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT uq_positions_code UNIQUE (tenant_id, department_id, code)
);

CREATE TABLE IF NOT EXISTS groups (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
  code VARCHAR(30) NOT NULL, name_ar VARCHAR(255) NOT NULL, name_en VARCHAR(255),
  parent_id UUID REFERENCES groups(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID NOT NULL REFERENCES users(id), updated_by UUID NOT NULL REFERENCES users(id),
  version INTEGER NOT NULL DEFAULT 1, deleted_at TIMESTAMPTZ, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT uq_groups_code UNIQUE (tenant_id, code)
);

CREATE TABLE IF NOT EXISTS group_entities (
  group_id UUID NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
  entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID NOT NULL REFERENCES users(id), updated_by UUID NOT NULL REFERENCES users(id),
  version INTEGER NOT NULL DEFAULT 1, deleted_at TIMESTAMPTZ, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  PRIMARY KEY (group_id, entity_id)
);

CREATE TABLE IF NOT EXISTS group_ownership (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
  group_id UUID NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
  entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
  ownership_pct percentage NOT NULL,
  acquired_on DATE NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID NOT NULL REFERENCES users(id), updated_by UUID NOT NULL REFERENCES users(id),
  version INTEGER NOT NULL DEFAULT 1, deleted_at TIMESTAMPTZ, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT uq_group_ownership UNIQUE (tenant_id, group_id, entity_id)
);
