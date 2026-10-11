-- ============================================================================
-- Phase 1 Foundation — المرحلة الأولى: الأساس (23 جدول فقط)
-- PostgreSQL 16+ | تنفيذ مباشر: psql -f phase1_foundation.sql
-- الترتيب: extensions -> domains -> tenants/plans -> users/roles -> entities
-- قرار bootstrap: created_by/updated_by NULLABLE مع FK مؤجل DEFERRABLE
-- (البديل المرفوض: NOT NULL صارم يكسر إنشاء أول tenant/user — تبعية دائرية).
-- plants/permissions عمومية بلا tenant_id (كتالوج مشترك)، الباقي tenant-scoped + RLS.
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS citext;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ---------- دوال Triggers العامة ----------
CREATE OR REPLACE FUNCTION fn_touch_updated_at() RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN NEW.updated_at = NOW(); NEW.version = COALESCE(OLD.version,0)+1; RETURN NEW; END $$;

-- ================= A: المستأجرون والاشتراكات (7) =================

CREATE TABLE IF NOT EXISTS tenants (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  code VARCHAR(30) NOT NULL UNIQUE,
  name_ar VARCHAR(255) NOT NULL, name_en VARCHAR(255),
  status VARCHAR(30) NOT NULL DEFAULT 'active',
  timezone VARCHAR(64) NOT NULL DEFAULT 'Asia/Amman',
  default_currency CHAR(3) NOT NULL DEFAULT 'JOD',
  country CHAR(2) NOT NULL DEFAULT 'JO',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID, updated_by UUID, -- NULL لأول سجل (bootstrap)، التطبيق يلزمها بعدها
  version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, deleted_by UUID, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT ck_tenants_status CHECK (status IN ('provisioning','active','suspended','deleted')),
  CONSTRAINT ck_tenants_currency CHECK (default_currency ~ '^[A-Z]{3}$'),
  CONSTRAINT ck_tenants_country CHECK (country ~ '^[A-Z]{2}$')
);

CREATE TABLE IF NOT EXISTS plans (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(), -- عمومي بلا tenant_id (كتالوج موحد)
  code VARCHAR(50) NOT NULL UNIQUE,
  name_ar VARCHAR(255) NOT NULL, name_en VARCHAR(255),
  price NUMERIC(18,3) NOT NULL DEFAULT 0,
  max_entities INTEGER NOT NULL DEFAULT 1 CHECK (max_entities > 0),
  max_users INTEGER NOT NULL DEFAULT 5 CHECK (max_users > 0),
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID, updated_by UUID, version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, deleted_by UUID, is_deleted BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS tenant_settings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE ON UPDATE CASCADE,
  setting_key VARCHAR(150) NOT NULL, setting_value JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID, updated_by UUID, version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, deleted_by UUID, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT uq_tenant_settings_key UNIQUE (tenant_id, setting_key)
);

CREATE TABLE IF NOT EXISTS tenant_domains (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE ON UPDATE CASCADE,
  domain CITEXT NOT NULL UNIQUE,
  is_primary BOOLEAN NOT NULL DEFAULT FALSE, is_verified BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID, updated_by UUID, version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, deleted_by UUID, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT ck_tenant_domains_fmt CHECK (domain ~* '^[a-z0-9.-]+\.[a-z]{2,}$')
);

CREATE TABLE IF NOT EXISTS tenant_features (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE ON UPDATE CASCADE,
  feature_code VARCHAR(100) NOT NULL, -- payroll, manufacturing, consolidation, edu
  is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
  limit_value INTEGER CHECK (limit_value IS NULL OR limit_value >= 0),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID, updated_by UUID, version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, deleted_by UUID, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT uq_tenant_features_code UNIQUE (tenant_id, feature_code)
);

CREATE TABLE IF NOT EXISTS plan_features (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE ON UPDATE CASCADE,
  plan_id UUID NOT NULL REFERENCES plans(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  feature_code VARCHAR(100) NOT NULL, is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
  limit_value INTEGER CHECK (limit_value IS NULL OR limit_value >= 0),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID, updated_by UUID, version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, deleted_by UUID, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT uq_plan_features_code UNIQUE (tenant_id, plan_id, feature_code)
);

CREATE TABLE IF NOT EXISTS subscriptions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  plan_id UUID NOT NULL REFERENCES plans(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  starts_on DATE NOT NULL, ends_on DATE NOT NULL,
  status VARCHAR(30) NOT NULL DEFAULT 'active',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID, updated_by UUID, version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, deleted_by UUID, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT ck_sub_dates CHECK (ends_on > starts_on),
  CONSTRAINT ck_sub_status CHECK (status IN ('trial','active','expired','cancelled'))
);

-- ================= B: المستخدمون والأدوار (8) =================

CREATE TABLE IF NOT EXISTS users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  username VARCHAR(100) NOT NULL, email CITEXT NOT NULL,
  password_hash TEXT NOT NULL,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE DEFERRABLE INITIALLY DEFERRED,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE DEFERRABLE INITIALLY DEFERRED,
  version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, deleted_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT uq_users_tenant_username UNIQUE (tenant_id, username),
  CONSTRAINT uq_users_tenant_email UNIQUE (tenant_id, email),
  CONSTRAINT ck_users_email CHECK (email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$')
);

CREATE TABLE IF NOT EXISTS user_profiles (
  user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE ON UPDATE CASCADE,
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  full_name_ar VARCHAR(255) NOT NULL, full_name_en VARCHAR(255),
  phone VARCHAR(50), avatar_url TEXT, locale VARCHAR(10) NOT NULL DEFAULT 'ar-JO',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, deleted_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  is_deleted BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS user_sessions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE ON UPDATE CASCADE,
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE ON UPDATE CASCADE,
  refresh_jti UUID NOT NULL UNIQUE, ip VARCHAR(64), user_agent TEXT,
  expires_at TIMESTAMPTZ NOT NULL, revoked_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, deleted_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT ck_session_exp CHECK (expires_at > created_at)
);

CREATE TABLE IF NOT EXISTS user_mfa_methods (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE ON UPDATE CASCADE,
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE ON UPDATE CASCADE,
  method VARCHAR(20) NOT NULL DEFAULT 'totp', secret TEXT NOT NULL,
  is_verified BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, deleted_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT ck_mfa_method CHECK (method IN ('totp','sms','email')),
  CONSTRAINT uq_mfa_user_method UNIQUE (tenant_id, user_id, method)
);

CREATE TABLE IF NOT EXISTS roles (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE ON UPDATE CASCADE,
  code VARCHAR(50) NOT NULL, name_ar VARCHAR(255) NOT NULL, name_en VARCHAR(255),
  is_system BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, deleted_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT uq_roles_code UNIQUE (tenant_id, code)
);

CREATE TABLE IF NOT EXISTS permissions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(), -- كتالوج عمومي بلا tenant_id
  code VARCHAR(150) NOT NULL UNIQUE,
  name_ar VARCHAR(255) NOT NULL, name_en VARCHAR(255),
  module VARCHAR(50) NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID, updated_by UUID, version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, deleted_by UUID, is_deleted BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS role_permissions (
  role_id UUID NOT NULL REFERENCES roles(id) ON DELETE CASCADE ON UPDATE CASCADE,
  permission_id UUID NOT NULL REFERENCES permissions(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE ON UPDATE CASCADE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, deleted_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  PRIMARY KEY (role_id, permission_id)
);

CREATE TABLE IF NOT EXISTS user_roles (
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE ON UPDATE CASCADE,
  role_id UUID NOT NULL REFERENCES roles(id) ON DELETE CASCADE ON UPDATE CASCADE,
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE ON UPDATE CASCADE,
  entity_id UUID, -- نطاق الكيان (NULL = كل الكيانات) — FK يُضاف في مرحلة الكيانات؟ هنا بلا FK لتفادي الترتيب
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, deleted_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  PRIMARY KEY (user_id, role_id)
);

-- ================= C: الكيانات والفروع (8) =================

CREATE TABLE IF NOT EXISTS entities (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  code VARCHAR(30) NOT NULL, name_ar VARCHAR(255) NOT NULL, name_en VARCHAR(255),
  functional_currency CHAR(3) NOT NULL DEFAULT 'JOD',
  timezone VARCHAR(64) NOT NULL DEFAULT 'Asia/Amman',
  is_consolidated BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, deleted_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT uq_entities_code UNIQUE (tenant_id, code),
  CONSTRAINT ck_entities_curr CHECK (functional_currency ~ '^[A-Z]{3}$')
);

CREATE TABLE IF NOT EXISTS entity_settings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE ON UPDATE CASCADE,
  entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE ON UPDATE CASCADE,
  setting_key VARCHAR(150) NOT NULL, setting_value JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, deleted_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT uq_entity_settings_key UNIQUE (tenant_id, entity_id, setting_key)
);

CREATE TABLE IF NOT EXISTS entity_legal_info (
  entity_id UUID PRIMARY KEY REFERENCES entities(id) ON DELETE CASCADE ON UPDATE CASCADE,
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  commercial_reg VARCHAR(100), tax_id VARCHAR(50), national_id VARCHAR(50),
  legal_form VARCHAR(100),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, deleted_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT ck_legal_tax CHECK (tax_id IS NULL OR LENGTH(tax_id) >= 5)
);

CREATE TABLE IF NOT EXISTS branches (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  code VARCHAR(30) NOT NULL, name_ar VARCHAR(255) NOT NULL, name_en VARCHAR(255),
  address JSONB, phone VARCHAR(50),
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, deleted_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT uq_branches_code UNIQUE (tenant_id, entity_id, code)
);

CREATE TABLE IF NOT EXISTS groups (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  code VARCHAR(30) NOT NULL, name_ar VARCHAR(255) NOT NULL, name_en VARCHAR(255),
  parent_id UUID REFERENCES groups(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, deleted_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT uq_groups_code UNIQUE (tenant_id, code)
);

CREATE TABLE IF NOT EXISTS group_entities (
  group_id UUID NOT NULL REFERENCES groups(id) ON DELETE CASCADE ON UPDATE CASCADE,
  entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE ON UPDATE CASCADE,
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE ON UPDATE CASCADE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, deleted_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  PRIMARY KEY (group_id, entity_id)
);

CREATE TABLE IF NOT EXISTS group_ownership (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  group_id UUID NOT NULL REFERENCES groups(id) ON DELETE CASCADE ON UPDATE CASCADE,
  entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE ON UPDATE CASCADE,
  ownership_pct NUMERIC(7,4) NOT NULL,
  acquired_on DATE NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, deleted_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT uq_group_ownership UNIQUE (tenant_id, group_id, entity_id),
  CONSTRAINT ck_ownership_pct CHECK (ownership_pct >= 0 AND ownership_pct <= 100)
);

CREATE TABLE IF NOT EXISTS departments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  code VARCHAR(30) NOT NULL, name_ar VARCHAR(255) NOT NULL, name_en VARCHAR(255),
  parent_id UUID REFERENCES departments(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, deleted_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT uq_departments_code UNIQUE (tenant_id, entity_id, code)
);

-- ================= الفهارس =================
CREATE INDEX IF NOT EXISTS idx_tenant_settings_tenant ON tenant_settings(tenant_id);
CREATE INDEX IF NOT EXISTS idx_tenant_domains_tenant ON tenant_domains(tenant_id);
CREATE INDEX IF NOT EXISTS idx_tenant_features_tenant ON tenant_features(tenant_id);
CREATE INDEX IF NOT EXISTS idx_plan_features_tenant ON plan_features(tenant_id);
CREATE INDEX IF NOT EXISTS idx_plan_features_plan ON plan_features(plan_id);
CREATE INDEX IF NOT EXISTS idx_subscriptions_tenant ON subscriptions(tenant_id);
CREATE INDEX IF NOT EXISTS idx_subscriptions_plan ON subscriptions(plan_id);
CREATE INDEX IF NOT EXISTS idx_users_tenant ON users(tenant_id);
CREATE INDEX IF NOT EXISTS idx_users_created ON users(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_user_profiles_tenant ON user_profiles(tenant_id);
CREATE INDEX IF NOT EXISTS idx_user_sessions_tenant ON user_sessions(tenant_id);
CREATE INDEX IF NOT EXISTS idx_user_sessions_user ON user_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_user_mfa_tenant ON user_mfa_methods(tenant_id);
CREATE INDEX IF NOT EXISTS idx_roles_tenant ON roles(tenant_id);
CREATE INDEX IF NOT EXISTS idx_role_permissions_tenant ON role_permissions(tenant_id);
CREATE INDEX IF NOT EXISTS idx_role_permissions_role ON role_permissions(role_id);
CREATE INDEX IF NOT EXISTS idx_user_roles_tenant ON user_roles(tenant_id);
CREATE INDEX IF NOT EXISTS idx_user_roles_user ON user_roles(user_id);
CREATE INDEX IF NOT EXISTS idx_entities_tenant ON entities(tenant_id);
CREATE INDEX IF NOT EXISTS idx_entity_settings_tenant ON entity_settings(tenant_id);
CREATE INDEX IF NOT EXISTS idx_entity_settings_entity ON entity_settings(entity_id);
CREATE INDEX IF NOT EXISTS idx_branches_tenant ON branches(tenant_id);
CREATE INDEX IF NOT EXISTS idx_branches_entity ON branches(entity_id);
CREATE INDEX IF NOT EXISTS idx_groups_tenant ON groups(tenant_id);
CREATE INDEX IF NOT EXISTS idx_group_entities_tenant ON group_entities(tenant_id);
CREATE INDEX IF NOT EXISTS idx_group_ownership_tenant ON group_ownership(tenant_id);
CREATE INDEX IF NOT EXISTS idx_departments_tenant ON departments(tenant_id);
CREATE INDEX IF NOT EXISTS idx_departments_entity ON departments(entity_id);
-- Partial: النشطة فقط
CREATE INDEX IF NOT EXISTS idx_users_active ON users(deleted_at) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_entities_active ON entities(deleted_at) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_branches_active ON branches(deleted_at) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_roles_active ON roles(deleted_at) WHERE is_deleted = FALSE;
-- Trigram عربي
CREATE INDEX IF NOT EXISTS gin_tenants_name_trgm ON tenants USING GIN (name_ar gin_trgm_ops);
CREATE INDEX IF NOT EXISTS gin_entities_name_trgm ON entities USING GIN (name_ar gin_trgm_ops);

-- ================= Triggers (updated_at + version) =================
DO $$ DECLARE t TEXT; arr TEXT[] := ARRAY['tenants','plans','tenant_settings','tenant_domains','tenant_features','plan_features','subscriptions','users','user_profiles','user_sessions','user_mfa_methods','roles','permissions','role_permissions','user_roles','entities','entity_settings','entity_legal_info','branches','groups','group_entities','group_ownership','departments'];
BEGIN FOREACH t IN ARRAY arr LOOP EXECUTE format('DROP TRIGGER IF EXISTS trg_%s_touch ON %I', t, t); EXECUTE format('CREATE TRIGGER trg_%s_touch BEFORE UPDATE ON %I FOR EACH ROW EXECUTE FUNCTION fn_touch_updated_at()', t, t); END LOOP; END $$;

-- ================= RLS (كل جدول يحمل tenant_id + FORCE) =================
DO $$ DECLARE t TEXT; arr TEXT[] := ARRAY['tenant_settings','tenant_domains','tenant_features','plan_features','subscriptions','users','user_profiles','user_sessions','user_mfa_methods','roles','role_permissions','user_roles','entities','entity_settings','entity_legal_info','branches','groups','group_entities','group_ownership','departments'];
BEGIN FOREACH t IN ARRAY arr LOOP
  EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
  EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', t);
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename=t AND policyname='tenant_iso_sel') THEN
    EXECUTE format('CREATE POLICY tenant_iso_sel ON %I FOR SELECT USING (tenant_id = NULLIF(current_setting(%L,true),%L)::UUID)', t, 'app.current_tenant_id', '');
    EXECUTE format('CREATE POLICY tenant_iso_ins ON %I FOR INSERT WITH CHECK (tenant_id = NULLIF(current_setting(%L,true),%L)::UUID)', t, 'app.current_tenant_id', '');
    EXECUTE format('CREATE POLICY tenant_iso_upd ON %I FOR UPDATE USING (tenant_id = NULLIF(current_setting(%L,true),%L)::UUID)', t, 'app.current_tenant_id', '');
    EXECUTE format('CREATE POLICY tenant_iso_del ON %I FOR DELETE USING (tenant_id = NULLIF(current_setting(%L,true),%L)::UUID)', t, 'app.current_tenant_id', '');
  END IF;
END LOOP; END $$;
-- tenants/plans/permissions عمومية: بلا RLS (تُقرأ بـ service_role + فلترة تطبيقية).

-- ================= Seed: باقات + صلاحيات + أدوار =================
INSERT INTO plans(code,name_ar,name_en,price,max_entities,max_users) VALUES
 ('basic','الأساسية','Basic',29.000,1,5),
 ('business','الأعمال','Business',99.000,3,25),
 ('enterprise','المؤسسات','Enterprise',299.000,10,200)
ON CONFLICT (code) DO NOTHING;

INSERT INTO permissions(code,name_ar,name_en,module) VALUES
 ('tenants.manage','إدارة المستأجرين','Manage tenants','admin'),
 ('entities.create','إنشاء كيان','Create entity','core'),
 ('entities.view','عرض الكيانات','View entities','core'),
 ('branches.manage','إدارة الفروع','Manage branches','core'),
 ('groups.manage','إدارة المجموعات','Manage groups','core'),
 ('users.create','إنشاء مستخدم','Create user','admin'),
 ('users.view','عرض المستخدمين','View users','admin'),
 ('users.deactivate','تعطيل مستخدم','Deactivate user','admin'),
 ('roles.assign','إسناد الأدوار','Assign roles','admin'),
 ('roles.manage','إدارة الأدوار','Manage roles','admin'),
 ('audit.view','عرض التدقيق','View audit','admin'),
 ('settings.manage','إدارة الإعدادات','Manage settings','admin'),
 ('subscriptions.manage','إدارة الاشتراكات','Manage subscriptions','billing'),
 ('reports.view','عرض التقارير','View reports','reports'),
 ('export.data','تصدير البيانات','Export data','reports'),
 ('mfa.enforce','فرض المصادقة الثنائية','Enforce MFA','security'),
 ('sessions.revoke','إلغاء الجلسات','Revoke sessions','security'),
 ('departments.manage','إدارة الأقسام','Manage departments','core'),
 ('domains.verify','توثيق النطاقات','Verify domains','admin'),
 ('features.toggle','تبديل الميزات','Toggle features','admin')
ON CONFLICT (code) DO NOTHING;

-- ================= توثيق الجداول =================
COMMENT ON TABLE tenants IS 'المستأجرون (جذر العزل) | Tenants root — no tenant_id by design';
COMMENT ON TABLE plans IS 'الباقات العمومية (كتالوج مشترك بلا tenant_id) | Global plans catalog';
COMMENT ON TABLE tenant_settings IS 'إعدادات المستأجر key/value | Tenant settings';
COMMENT ON TABLE tenant_domains IS 'نطاقات المستأجر المخصصة | Custom domains (CITEXT unique)';
COMMENT ON TABLE tenant_features IS 'ميزات المستأجر المفعلة | Tenant feature flags';
COMMENT ON TABLE plan_features IS 'ميزات كل باقة | Plan feature matrix';
COMMENT ON TABLE subscriptions IS 'اشتراكات المستأجرين (فترة + حالة) | Subscriptions';
COMMENT ON TABLE users IS 'المستخدمون — tenant-scoped + self-FK مؤجل للـ bootstrap | Users';
COMMENT ON TABLE user_profiles IS 'ملفات المستخدمين 1:1 | Profiles (1:1 users)';
COMMENT ON TABLE user_sessions IS 'جلسات Refresh (jti قابل للإلغاء) | Sessions';
COMMENT ON TABLE user_mfa_methods IS 'طرق MFA (TOTP/SMS) | MFA methods';
COMMENT ON TABLE roles IS 'الأدوار لكل مستأجر | Tenant roles';
COMMENT ON TABLE permissions IS 'كتالوج الصلاحيات العمومي | Global permission catalog';
COMMENT ON TABLE role_permissions IS 'ربط دور↔صلاحية N:M | Role-permission matrix';
COMMENT ON TABLE user_roles IS 'إسناد المستخدم↔دور + نطاق كيان اختياري | User-role assignments';
COMMENT ON TABLE entities IS 'الكيانات القانونية (JOD افتراضياً) | Legal entities';
COMMENT ON TABLE entity_settings IS 'إعدادات الكيان | Entity settings';
COMMENT ON TABLE entity_legal_info IS 'البيانات القانونية 1:1 (سجل/ضريبة) | Legal info 1:1';
COMMENT ON TABLE branches IS 'الفروع (تابعة لكيان) | Branches';
COMMENT ON TABLE groups IS 'مجموعات التجميع (هرمية) | Consolidation groups';
COMMENT ON TABLE group_entities IS 'عضوية كيان في مجموعة N:M | Group membership';
COMMENT ON TABLE group_ownership IS 'نسب الملكية 0-100 | Ownership %';
COMMENT ON TABLE departments IS 'الأقسام (هرمية داخل كيان) | Departments';
