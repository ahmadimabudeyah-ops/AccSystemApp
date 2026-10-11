-- ============================================================================
-- Phase 12 — المشاريع والموازنات + سجل التدقيق
-- ============================================================================

CREATE TABLE IF NOT EXISTS projects (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  code VARCHAR(50) NOT NULL, name_ar VARCHAR(255) NOT NULL,
  customer_id UUID REFERENCES parties(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  budget_total NUMERIC(18,3) NOT NULL DEFAULT 0,
  starts_on DATE, ends_on DATE,
  status VARCHAR(20) NOT NULL DEFAULT 'draft',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, deleted_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT uq_projects_code UNIQUE (tenant_id, entity_id, code),
  CONSTRAINT ck_proj_status CHECK (status IN ('draft','active','on_hold','completed','closed','cancelled'))
);

CREATE TABLE IF NOT EXISTS project_costs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE ON UPDATE CASCADE,
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE ON UPDATE CASCADE,
  cost_date DATE NOT NULL DEFAULT CURRENT_DATE,
  amount NUMERIC(18,3) NOT NULL CHECK (amount >= 0),
  description TEXT, journal_entry_id UUID REFERENCES journal_entries(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1, deleted_at TIMESTAMPTZ, is_deleted BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS project_revenues (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE ON UPDATE CASCADE,
  project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE ON UPDATE CASCADE,
  revenue_date DATE NOT NULL DEFAULT CURRENT_DATE,
  amount NUMERIC(18,3) NOT NULL CHECK (amount >= 0),
  description TEXT, invoice_id UUID,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1, deleted_at TIMESTAMPTZ, is_deleted BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS budgets (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  fiscal_year_id UUID NOT NULL REFERENCES fiscal_years(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  code VARCHAR(50) NOT NULL, name_ar VARCHAR(255) NOT NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'draft',
  approved_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, deleted_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT uq_budgets_code UNIQUE (tenant_id, entity_id, code),
  CONSTRAINT ck_budget_status CHECK (status IN ('draft','approved','active','closed'))
);

CREATE TABLE IF NOT EXISTS budget_lines (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE ON UPDATE CASCADE,
  budget_id UUID NOT NULL REFERENCES budgets(id) ON DELETE CASCADE ON UPDATE CASCADE,
  account_id UUID NOT NULL REFERENCES accounts(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  planned_amount NUMERIC(18,3) NOT NULL,
  notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1, deleted_at TIMESTAMPTZ, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT uq_budget_line UNIQUE (tenant_id, budget_id, account_id)
);

-- سجل التدقيق: إلحاقي فقط (بلا تحديث/حذف) — يُفرض عبر REVOKE لاحقًا
CREATE TABLE IF NOT EXISTS audit_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  actor_id UUID,
  action VARCHAR(50) NOT NULL,
  entity_type VARCHAR(100) NOT NULL, entity_id UUID,
  old_values JSONB, new_values JSONB,
  ip VARCHAR(64),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_audit_tenant_time ON audit_logs(tenant_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_actor ON audit_logs(actor_id);
CREATE INDEX IF NOT EXISTS idx_audit_entity ON audit_logs(entity_type, entity_id);

DO $$ DECLARE t TEXT; arr TEXT[] := ARRAY['projects','project_costs','project_revenues','budgets','budget_lines'];
BEGIN FOREACH t IN ARRAY arr LOOP
  EXECUTE format('DROP TRIGGER IF EXISTS trg_%s_touch ON %I',t,t);
  EXECUTE format('CREATE TRIGGER trg_%s_touch BEFORE UPDATE ON %I FOR EACH ROW EXECUTE FUNCTION fn_touch_updated_at()',t,t);
  EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY',t);
  EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY',t);
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename=t AND policyname='tenant_iso_sel') THEN
    EXECUTE format('CREATE POLICY tenant_iso_sel ON %I FOR SELECT USING (tenant_id = NULLIF(current_setting(%L,true),%L)::UUID)',t,'app.current_tenant_id','');
    EXECUTE format('CREATE POLICY tenant_iso_ins ON %I FOR INSERT WITH CHECK (tenant_id = NULLIF(current_setting(%L,true),%L)::UUID)',t,'app.current_tenant_id','');
    EXECUTE format('CREATE POLICY tenant_iso_upd ON %I FOR UPDATE USING (tenant_id = NULLIF(current_setting(%L,true),%L)::UUID)',t,'app.current_tenant_id','');
    EXECUTE format('CREATE POLICY tenant_iso_del ON %I FOR DELETE USING (tenant_id = NULLIF(current_setting(%L,true),%L)::UUID)',t,'app.current_tenant_id','');
  END IF;
END LOOP; END $$;
ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_logs FORCE ROW LEVEL SECURITY;
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename='audit_logs' AND policyname='tenant_iso_sel') THEN
    CREATE POLICY tenant_iso_sel ON audit_logs FOR SELECT USING (tenant_id = NULLIF(current_setting('app.current_tenant_id',true),'')::UUID);
    CREATE POLICY tenant_iso_ins ON audit_logs FOR INSERT WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id',true),'')::UUID);
  END IF;
END $$;
COMMENT ON TABLE audit_logs IS 'سجل التدقيق الإلحاقي | Append-only audit trail';
