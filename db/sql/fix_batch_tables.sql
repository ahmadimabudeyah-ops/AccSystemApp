-- Fix batch: tax returns, bank statements + reconciliations, vendor returns,
-- recurring entries, notifications, password reset tokens.
CREATE TABLE IF NOT EXISTS tax_returns (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  tax_id UUID NOT NULL REFERENCES taxes(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  period_code VARCHAR(20) NOT NULL,
  sales_total NUMERIC(18,3) NOT NULL DEFAULT 0, tax_due NUMERIC(18,3) NOT NULL DEFAULT 0,
  status VARCHAR(20) NOT NULL DEFAULT 'draft',
  filed_at TIMESTAMPTZ, filed_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1, deleted_at TIMESTAMPTZ, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT uq_taxret UNIQUE (tenant_id, entity_id, tax_id, period_code)
);
CREATE TABLE IF NOT EXISTS bank_statements (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  bank_account_id UUID NOT NULL REFERENCES bank_accounts(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  stmt_date DATE NOT NULL, opening_balance NUMERIC(18,3) NOT NULL DEFAULT 0,
  closing_balance NUMERIC(18,3) NOT NULL DEFAULT 0,
  source_filename VARCHAR(255),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1, deleted_at TIMESTAMPTZ, is_deleted BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE TABLE IF NOT EXISTS bank_statement_lines (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE ON UPDATE CASCADE,
  statement_id UUID NOT NULL REFERENCES bank_statements(id) ON DELETE CASCADE ON UPDATE CASCADE,
  txn_date DATE NOT NULL, description TEXT NOT NULL,
  amount NUMERIC(18,3) NOT NULL,
  is_matched BOOLEAN NOT NULL DEFAULT FALSE, matched_entry_id UUID,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1, deleted_at TIMESTAMPTZ, is_deleted BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE TABLE IF NOT EXISTS vendor_returns (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  doc_number VARCHAR(50) NOT NULL,
  supplier_id UUID NOT NULL REFERENCES parties(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  bill_id UUID REFERENCES vendor_bills(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  return_date DATE NOT NULL DEFAULT CURRENT_DATE, reason TEXT NOT NULL,
  warehouse_id UUID REFERENCES warehouses(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  total_amount NUMERIC(18,3) NOT NULL DEFAULT 0,
  status VARCHAR(30) NOT NULL DEFAULT 'draft',
  journal_entry_id UUID REFERENCES journal_entries(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1, deleted_at TIMESTAMPTZ, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT uq_vret_num UNIQUE (tenant_id, entity_id, doc_number)
);
CREATE TABLE IF NOT EXISTS vendor_return_lines (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE ON UPDATE CASCADE,
  return_id UUID NOT NULL REFERENCES vendor_returns(id) ON DELETE CASCADE ON UPDATE CASCADE,
  line_number INTEGER NOT NULL CHECK (line_number >= 1),
  product_id UUID NOT NULL REFERENCES products(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  returned_qty NUMERIC(18,6) NOT NULL CHECK (returned_qty > 0),
  unit_price NUMERIC(18,3) NOT NULL, line_total NUMERIC(18,3) NOT NULL DEFAULT 0,
  location_id UUID REFERENCES locations(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1, deleted_at TIMESTAMPTZ, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT uq_vrl UNIQUE (return_id, line_number)
);
CREATE TABLE IF NOT EXISTS recurring_entries (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  code VARCHAR(50) NOT NULL, description TEXT NOT NULL,
  journal_id UUID NOT NULL REFERENCES journals(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  frequency VARCHAR(20) NOT NULL DEFAULT 'monthly',
  next_run_on DATE NOT NULL, last_run_on DATE,
  template JSONB NOT NULL DEFAULT '{"lines": []}',
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1, deleted_at TIMESTAMPTZ, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT uq_recurring UNIQUE (tenant_id, entity_id, code),
  CONSTRAINT ck_rec_freq CHECK (frequency IN ('monthly','quarterly','yearly'))
);
CREATE TABLE IF NOT EXISTS notifications (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE ON UPDATE CASCADE,
  user_id UUID REFERENCES users(id) ON DELETE CASCADE ON UPDATE CASCADE,
  title VARCHAR(255) NOT NULL, body TEXT,
  severity VARCHAR(20) NOT NULL DEFAULT 'info',
  is_read BOOLEAN NOT NULL DEFAULT FALSE,
  link_url VARCHAR(500),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1, deleted_at TIMESTAMPTZ, is_deleted BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE TABLE IF NOT EXISTS password_reset_tokens (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE ON UPDATE CASCADE,
  token_hash VARCHAR(128) NOT NULL UNIQUE,
  expires_at TIMESTAMPTZ NOT NULL,
  used_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
DO $$ DECLARE t TEXT; arr TEXT[] := ARRAY['tax_returns','bank_statements','bank_statement_lines','vendor_returns','vendor_return_lines','recurring_entries','notifications'];
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
