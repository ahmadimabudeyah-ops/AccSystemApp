-- login_attempts: قفل الحساب بعد 5 محاولات فاشلة خلال 15 دقيقة.
CREATE TABLE IF NOT EXISTS login_attempts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE ON UPDATE CASCADE,
  username VARCHAR(255) NOT NULL,
  ip VARCHAR(64),
  success BOOLEAN NOT NULL DEFAULT FALSE,
  attempted_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_login_attempts_user ON login_attempts(tenant_id, username, attempted_at DESC);
ALTER TABLE login_attempts ENABLE ROW LEVEL SECURITY;
ALTER TABLE login_attempts FORCE ROW LEVEL SECURITY;
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename='login_attempts' AND policyname='tenant_iso_sel') THEN
    CREATE POLICY tenant_iso_sel ON login_attempts FOR SELECT USING (tenant_id = NULLIF(current_setting('app.current_tenant_id',true),'')::UUID);
    CREATE POLICY tenant_iso_ins ON login_attempts FOR INSERT WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id',true),'')::UUID);
  END IF;
END $$;
