-- 0015_portal_tokens.sql
-- PortalToken model (app/models/biz.py) had no table in the schema, so
-- POST /api/v1/portal-tokens failed with "permission denied for table
-- portal_tokens".  Create the table with the standard tenant mixins and the
-- same RLS isolation used by every other tenant-scoped table.
-- Idempotent.

CREATE TABLE IF NOT EXISTS portal_tokens (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  party_id UUID NOT NULL REFERENCES parties(id) ON DELETE CASCADE,
  token_hash VARCHAR(128) NOT NULL,
  scope VARCHAR(30) NOT NULL DEFAULT 'statement',
  expires_at TIMESTAMPTZ NOT NULL,
  last_used_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ,
  is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT uq_portal_tokens_hash UNIQUE (token_hash)
);

CREATE INDEX IF NOT EXISTS ix_portal_tokens_party ON portal_tokens (party_id);
CREATE INDEX IF NOT EXISTS ix_portal_tokens_tenant ON portal_tokens (tenant_id);

ALTER TABLE portal_tokens ENABLE ROW LEVEL SECURITY;
ALTER TABLE portal_tokens FORCE ROW LEVEL SECURITY;

DO $$
DECLARE t TEXT := 'portal_tokens';
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename=t AND policyname='tenant_iso_sel') THEN
    EXECUTE format('CREATE POLICY tenant_iso_sel ON %I FOR SELECT USING (tenant_id = NULLIF(current_setting(%L,true),%L)::UUID)', t, 'app.current_tenant_id', '');
    EXECUTE format('CREATE POLICY tenant_iso_ins ON %I FOR INSERT WITH CHECK (tenant_id = NULLIF(current_setting(%L,true),%L)::UUID)', t, 'app.current_tenant_id', '');
    EXECUTE format('CREATE POLICY tenant_iso_upd ON %I FOR UPDATE USING (tenant_id = NULLIF(current_setting(%L,true),%L)::UUID)', t, 'app.current_tenant_id', '');
    EXECUTE format('CREATE POLICY tenant_iso_del ON %I FOR DELETE USING (tenant_id = NULLIF(current_setting(%L,true),%L)::UUID)', t, 'app.current_tenant_id', '');
  END IF;
END $$;

-- keep updated_at fresh
CREATE OR REPLACE FUNCTION fn_touch_updated_at() RETURNS trigger AS $$
BEGIN
  NEW.updated_at := NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_portal_tokens_touch ON portal_tokens;
CREATE TRIGGER trg_portal_tokens_touch BEFORE UPDATE ON portal_tokens
FOR EACH ROW EXECUTE FUNCTION fn_touch_updated_at();
