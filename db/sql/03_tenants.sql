-- ============================================================================
-- 03_tenants.sql — المؤسسات والعزل | Tenants (المجموعة 1)
-- قرار معماري: tenants هو الجذر — لا يحمل tenant_id ولا created_by (كسر التبعية
-- الدائرية tenants<->users). كل الجداول اللاحقة تحمل tenant_id FK->tenants(id).
-- البديل المرفوض: Database-per-Tenant فيزيائياً لكل عميل صغير — كلفة تشغيلية
-- عالية في الأردن؛ اخترنا Shared DB + RLS強制 + إمكانية نقل tenant ثقيل لاحقاً.
-- ============================================================================

CREATE TABLE IF NOT EXISTS tenants (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(), -- tenant_id المرجعي لكل النظام
  code VARCHAR(30) NOT NULL UNIQUE,               -- slug: e.g. 'abc-schools'
  name_ar VARCHAR(255) NOT NULL,                  -- اسم المؤسسة عربي
  name_en VARCHAR(255),                           -- اسم المؤسسة إنجليزي
  status VARCHAR(50) NOT NULL DEFAULT 'active',   -- active/suspended/provisioning
  timezone VARCHAR(64) NOT NULL DEFAULT 'Asia/Amman',
  default_currency currency_code NOT NULL DEFAULT 'JOD',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  version INTEGER NOT NULL DEFAULT 1,             -- optimistic locking
  deleted_at TIMESTAMPTZ, is_deleted BOOLEAN NOT NULL DEFAULT FALSE
);
COMMENT ON TABLE tenants IS 'المؤسسات (المستأجرون) — جذر العزل | Tenants root';
COMMENT ON COLUMN tenants.code IS 'رمز فريد للمؤسسة | Unique tenant slug';

CREATE TABLE IF NOT EXISTS plans (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT, -- خطة لكل tenant (لتوحيد RLS)
  code VARCHAR(50) NOT NULL, name_ar VARCHAR(255) NOT NULL, name_en VARCHAR(255),
  price money_amount NOT NULL DEFAULT 0,
  max_entities INTEGER NOT NULL DEFAULT 1, max_users INTEGER NOT NULL DEFAULT 5,
  valid_from DATE NOT NULL DEFAULT CURRENT_DATE, valid_to DATE,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID, updated_by UUID, version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT uq_plans_tenant_code UNIQUE (tenant_id, code)
);

CREATE TABLE IF NOT EXISTS plan_features (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
  plan_id UUID NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
  feature_code VARCHAR(100) NOT NULL, -- e.g. 'payroll','manufacturing','consolidation'
  is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
  limit_value INTEGER,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID, updated_by UUID, version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT uq_plan_features_tp UNIQUE (tenant_id, plan_id, feature_code)
);

CREATE TABLE IF NOT EXISTS subscriptions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
  plan_id UUID NOT NULL REFERENCES plans(id) ON DELETE RESTRICT,
  starts_on DATE NOT NULL, ends_on DATE NOT NULL,
  status VARCHAR(50) NOT NULL DEFAULT 'active',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID, updated_by UUID, version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT ck_subscriptions_dates CHECK (ends_on > starts_on)
);

CREATE TABLE IF NOT EXISTS subscription_history (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
  subscription_id UUID NOT NULL REFERENCES subscriptions(id) ON DELETE CASCADE,
  old_plan_id UUID REFERENCES plans(id), new_plan_id UUID REFERENCES plans(id),
  changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), changed_by UUID,
  reason TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID, updated_by UUID, version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, is_deleted BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS tenant_settings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  setting_key VARCHAR(150) NOT NULL, setting_value JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID, updated_by UUID, version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT uq_tenant_settings_key UNIQUE (tenant_id, setting_key)
);

CREATE TABLE IF NOT EXISTS tenant_domains (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
  domain VARCHAR(255) NOT NULL UNIQUE, -- نطاق مخصص لكل مؤسسة
  is_primary BOOLEAN NOT NULL DEFAULT FALSE, is_verified BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID, updated_by UUID, version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, is_deleted BOOLEAN NOT NULL DEFAULT FALSE
);
