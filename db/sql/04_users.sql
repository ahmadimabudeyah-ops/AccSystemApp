-- ============================================================================
-- 04_users.sql — نواة المستخدمين (حد أدنى لكسر التبعية الدائرية)
-- الجداول الكاملة للأمان في 24_security.sql. هنا فقط users بأعمدة FK اللازمة.
-- created_by قابل NULL فقط لأول admin (bootstrap) ثم NOT NULL تطبيقاً.
-- ============================================================================

CREATE TABLE IF NOT EXISTS users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT,
  username VARCHAR(100) NOT NULL, email email_address NOT NULL,
  password_hash TEXT NOT NULL, -- argon2id (تُعامل كسرّية: Column-Level Security لاحقاً)
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id), updated_by UUID REFERENCES users(id),
  version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, deleted_by UUID REFERENCES users(id),
  is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  valid_from DATE NOT NULL DEFAULT CURRENT_DATE, valid_to DATE,
  CONSTRAINT uq_users_tenant_username UNIQUE (tenant_id, username),
  CONSTRAINT uq_users_tenant_email UNIQUE (tenant_id, email)
);
COMMENT ON TABLE users IS 'المستخدمون — tenant_id إلزامي، أول admin يُنشأ بـ created_by NULL ثم يُصلح';
