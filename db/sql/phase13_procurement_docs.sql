-- ============================================================================
-- Phase 13 — مستندات المشتريات (طلبات/أوامر/استلامات)
-- ============================================================================

CREATE TABLE IF NOT EXISTS purchase_requests (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  doc_number VARCHAR(50) NOT NULL,
  request_date DATE NOT NULL DEFAULT CURRENT_DATE,
  reason TEXT, status VARCHAR(30) NOT NULL DEFAULT 'draft',
  approved_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  notes TEXT, metadata JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1, deleted_at TIMESTAMPTZ, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT uq_preq_num UNIQUE (tenant_id, entity_id, doc_number)
);

CREATE TABLE IF NOT EXISTS purchase_request_lines (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE ON UPDATE CASCADE,
  request_id UUID NOT NULL REFERENCES purchase_requests(id) ON DELETE CASCADE ON UPDATE CASCADE,
  line_number INTEGER NOT NULL CHECK (line_number >= 1),
  product_id UUID NOT NULL REFERENCES products(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  qty NUMERIC(18,6) NOT NULL CHECK (qty > 0),
  notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1, deleted_at TIMESTAMPTZ, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT uq_prl UNIQUE (request_id, line_number)
);

CREATE TABLE IF NOT EXISTS purchase_orders (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  doc_number VARCHAR(50) NOT NULL,
  supplier_id UUID NOT NULL REFERENCES parties(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  request_id UUID REFERENCES purchase_requests(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  order_date DATE NOT NULL DEFAULT CURRENT_DATE, expected_on DATE,
  subtotal NUMERIC(18,3) NOT NULL DEFAULT 0, grand_total NUMERIC(18,3) NOT NULL DEFAULT 0,
  status VARCHAR(30) NOT NULL DEFAULT 'draft',
  notes TEXT, metadata JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1, deleted_at TIMESTAMPTZ, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT uq_po_num UNIQUE (tenant_id, entity_id, doc_number),
  CONSTRAINT ck_po_status CHECK (status IN ('draft','confirmed','partially_received','fully_received','cancelled'))
);

CREATE TABLE IF NOT EXISTS purchase_order_lines (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE ON UPDATE CASCADE,
  order_id UUID NOT NULL REFERENCES purchase_orders(id) ON DELETE CASCADE ON UPDATE CASCADE,
  line_number INTEGER NOT NULL CHECK (line_number >= 1),
  product_id UUID NOT NULL REFERENCES products(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  ordered_qty NUMERIC(18,6) NOT NULL CHECK (ordered_qty > 0),
  received_qty NUMERIC(18,6) NOT NULL DEFAULT 0,
  unit_price NUMERIC(18,3) NOT NULL CHECK (unit_price >= 0),
  line_total NUMERIC(18,3) NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1, deleted_at TIMESTAMPTZ, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT uq_pol UNIQUE (order_id, line_number)
);

CREATE TABLE IF NOT EXISTS goods_receipts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  doc_number VARCHAR(50) NOT NULL,
  order_id UUID REFERENCES purchase_orders(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  supplier_id UUID NOT NULL REFERENCES parties(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  warehouse_id UUID NOT NULL REFERENCES warehouses(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  receipt_date DATE NOT NULL DEFAULT CURRENT_DATE,
  status VARCHAR(30) NOT NULL DEFAULT 'draft',
  notes TEXT, metadata JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1, deleted_at TIMESTAMPTZ, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT uq_gr_num UNIQUE (tenant_id, entity_id, doc_number),
  CONSTRAINT ck_gr_status CHECK (status IN ('draft','confirmed'))
);

CREATE TABLE IF NOT EXISTS goods_receipt_lines (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE ON UPDATE CASCADE,
  receipt_id UUID NOT NULL REFERENCES goods_receipts(id) ON DELETE CASCADE ON UPDATE CASCADE,
  line_number INTEGER NOT NULL CHECK (line_number >= 1),
  product_id UUID NOT NULL REFERENCES products(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  received_qty NUMERIC(18,6) NOT NULL CHECK (received_qty > 0),
  unit_cost NUMERIC(18,6) NOT NULL DEFAULT 0,
  location_id UUID REFERENCES locations(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1, deleted_at TIMESTAMPTZ, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT uq_grl UNIQUE (receipt_id, line_number)
);

DO $$ DECLARE t TEXT; arr TEXT[] := ARRAY['purchase_requests','purchase_request_lines','purchase_orders','purchase_order_lines','goods_receipts','goods_receipt_lines'];
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
COMMENT ON TABLE goods_receipts IS 'الاستلامات — ترحيلها يرفع المخزون | Receipts raise stock';
