-- ============================================================================
-- Phase 9 — المشتريات (فواتير الموردين ودفعاتها) | Requires: phase1,7
-- ============================================================================

CREATE TABLE IF NOT EXISTS vendor_bills (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  doc_number VARCHAR(50) NOT NULL,
  supplier_id UUID NOT NULL REFERENCES parties(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  bill_date DATE NOT NULL DEFAULT CURRENT_DATE, due_on DATE NOT NULL,
  supplier_ref VARCHAR(100),
  currency_id CHAR(3) NOT NULL DEFAULT 'JOD', exchange_rate NUMERIC(18,10) NOT NULL DEFAULT 1,
  subtotal NUMERIC(18,3) NOT NULL DEFAULT 0, tax_total NUMERIC(18,3) NOT NULL DEFAULT 0,
  grand_total NUMERIC(18,3) NOT NULL DEFAULT 0,
  paid_amount NUMERIC(18,3) NOT NULL DEFAULT 0, remaining_amount NUMERIC(18,3) NOT NULL DEFAULT 0,
  status VARCHAR(30) NOT NULL DEFAULT 'draft',
  status_changed_at TIMESTAMPTZ, status_changed_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  journal_entry_id UUID REFERENCES journal_entries(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  event_key VARCHAR(200), notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, deleted_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT uq_vbill_num UNIQUE (tenant_id, entity_id, doc_number),
  CONSTRAINT uq_vbill_event UNIQUE (tenant_id, entity_id, event_key),
  CONSTRAINT ck_vbill_status CHECK (status IN ('draft','posted','partially_paid','paid','cancelled'))
);

CREATE TABLE IF NOT EXISTS vendor_bill_lines (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE ON UPDATE CASCADE,
  bill_id UUID NOT NULL REFERENCES vendor_bills(id) ON DELETE CASCADE ON UPDATE CASCADE,
  line_number INTEGER NOT NULL CHECK (line_number >= 1),
  product_id UUID NOT NULL REFERENCES products(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  description TEXT, qty NUMERIC(18,6) NOT NULL CHECK (qty > 0),
  unit_price NUMERIC(18,3) NOT NULL CHECK (unit_price >= 0),
  line_total NUMERIC(18,3) NOT NULL DEFAULT 0,
  account_id UUID REFERENCES accounts(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1, deleted_at TIMESTAMPTZ, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT uq_vbl UNIQUE (bill_id, line_number)
);

CREATE TABLE IF NOT EXISTS vendor_payments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  doc_number VARCHAR(50) NOT NULL,
  supplier_id UUID NOT NULL REFERENCES parties(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  pay_date DATE NOT NULL DEFAULT CURRENT_DATE, pay_method VARCHAR(20) NOT NULL DEFAULT 'bank_transfer',
  currency_id CHAR(3) NOT NULL DEFAULT 'JOD',
  amount NUMERIC(18,3) NOT NULL CHECK (amount > 0),
  allocated_amount NUMERIC(18,3) NOT NULL DEFAULT 0, unallocated_amount NUMERIC(18,3) NOT NULL DEFAULT 0,
  status VARCHAR(30) NOT NULL DEFAULT 'draft',
  journal_entry_id UUID REFERENCES journal_entries(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  event_key VARCHAR(200), reference VARCHAR(100),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1, deleted_at TIMESTAMPTZ, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT uq_vpay_num UNIQUE (tenant_id, entity_id, doc_number),
  CONSTRAINT ck_vpay_status CHECK (status IN ('draft','confirmed','posted','cancelled'))
);

CREATE TABLE IF NOT EXISTS vendor_payment_allocations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE ON UPDATE CASCADE,
  payment_id UUID NOT NULL REFERENCES vendor_payments(id) ON DELETE CASCADE ON UPDATE CASCADE,
  bill_id UUID NOT NULL REFERENCES vendor_bills(id) ON DELETE CASCADE ON UPDATE CASCADE,
  allocated_amount NUMERIC(18,3) NOT NULL CHECK (allocated_amount > 0),
  allocated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  allocated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1, deleted_at TIMESTAMPTZ, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT uq_valloc UNIQUE (tenant_id, payment_id, bill_id)
);

CREATE INDEX IF NOT EXISTS idx_vbill_supplier ON vendor_bills(supplier_id, status) WHERE is_deleted=FALSE;
CREATE INDEX IF NOT EXISTS idx_vbill_due ON vendor_bills(due_on) WHERE is_deleted=FALSE;

DO $$ DECLARE t TEXT; arr TEXT[] := ARRAY['vendor_bills','vendor_bill_lines','vendor_payments','vendor_payment_allocations'];
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

COMMENT ON TABLE vendor_bills IS 'فواتير الموردين — ترحيل آلي: مخزون/مصروف مدين / مورد دائن';
