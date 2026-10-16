-- fix_rls_counts_match.sql — RLS + triggers للجداول التي كانت بلا حماية + جداول ناقصة.
-- additive فقط: لا حذف لأي كائن قائم.
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='portal_svc') THEN
    CREATE ROLE portal_svc NOLOGIN;
  END IF;
END $$;

-- 1) RLS للجداول الثلاثة الناقصة
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename='stock_counts' AND policyname='tenant_iso_sel') THEN
    ALTER TABLE stock_counts ENABLE ROW LEVEL SECURITY;
    ALTER TABLE stock_counts FORCE ROW LEVEL SECURITY;
    CREATE POLICY tenant_iso_sel ON stock_counts FOR SELECT USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', TRUE), '')::UUID);
    CREATE POLICY tenant_iso_ins ON stock_counts FOR INSERT WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', TRUE), '')::UUID);
    CREATE POLICY tenant_iso_upd ON stock_counts FOR UPDATE USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', TRUE), '')::UUID);
    CREATE POLICY tenant_iso_del ON stock_counts FOR DELETE USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', TRUE), '')::UUID);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename='stock_count_lines' AND policyname='tenant_iso_sel') THEN
    ALTER TABLE stock_count_lines ENABLE ROW LEVEL SECURITY;
    ALTER TABLE stock_count_lines FORCE ROW LEVEL SECURITY;
    CREATE POLICY tenant_iso_sel ON stock_count_lines FOR SELECT USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', TRUE), '')::UUID);
    CREATE POLICY tenant_iso_ins ON stock_count_lines FOR INSERT WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', TRUE), '')::UUID);
    CREATE POLICY tenant_iso_upd ON stock_count_lines FOR UPDATE USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', TRUE), '')::UUID);
    CREATE POLICY tenant_iso_del ON stock_count_lines FOR DELETE USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', TRUE), '')::UUID);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename='bill_matches' AND policyname='tenant_iso_sel') THEN
    ALTER TABLE bill_matches ENABLE ROW LEVEL SECURITY;
    ALTER TABLE bill_matches FORCE ROW LEVEL SECURITY;
    CREATE POLICY tenant_iso_sel ON bill_matches FOR SELECT USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', TRUE), '')::UUID);
    CREATE POLICY tenant_iso_ins ON bill_matches FOR INSERT WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', TRUE), '')::UUID);
    CREATE POLICY tenant_iso_upd ON bill_matches FOR UPDATE USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', TRUE), '')::UUID);
    CREATE POLICY tenant_iso_del ON bill_matches FOR DELETE USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', TRUE), '')::UUID);
  END IF;
END $$;

-- touch triggers
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='trg_stock_counts_touch') THEN
    CREATE TRIGGER trg_stock_counts_touch BEFORE UPDATE ON stock_counts FOR EACH ROW EXECUTE FUNCTION fn_touch_updated_at();
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='trg_stock_count_lines_touch') THEN
    CREATE TRIGGER trg_stock_count_lines_touch BEFORE UPDATE ON stock_count_lines FOR EACH ROW EXECUTE FUNCTION fn_touch_updated_at();
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='trg_bill_matches_touch') THEN
    CREATE TRIGGER trg_bill_matches_touch BEFORE UPDATE ON bill_matches FOR EACH ROW EXECUTE FUNCTION fn_touch_updated_at();
  END IF;
END $$;

-- 2) الجداول الناقصة من المجموعة 2: branch_settings + positions
CREATE TABLE IF NOT EXISTS branch_settings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    branch_id UUID NOT NULL REFERENCES branches(id) ON DELETE CASCADE,
    settings JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID, updated_by UUID, version INTEGER NOT NULL DEFAULT 1,
    deleted_at TIMESTAMPTZ, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (tenant_id, branch_id)
);
CREATE TABLE IF NOT EXISTS positions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE RESTRICT,
    department_id UUID REFERENCES departments(id) ON DELETE SET NULL,
    code VARCHAR(50) NOT NULL, name_ar VARCHAR(200) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by UUID, updated_by UUID, version INTEGER NOT NULL DEFAULT 1,
    deleted_at TIMESTAMPTZ, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    UNIQUE (tenant_id, entity_id, code)
);
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename='branch_settings' AND policyname='tenant_iso_sel') THEN
    ALTER TABLE branch_settings ENABLE ROW LEVEL SECURITY;
    ALTER TABLE branch_settings FORCE ROW LEVEL SECURITY;
    CREATE POLICY tenant_iso_sel ON branch_settings FOR SELECT USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', TRUE), '')::UUID);
    CREATE POLICY tenant_iso_ins ON branch_settings FOR INSERT WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', TRUE), '')::UUID);
    CREATE POLICY tenant_iso_upd ON branch_settings FOR UPDATE USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', TRUE), '')::UUID);
    CREATE POLICY tenant_iso_del ON branch_settings FOR DELETE USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', TRUE), '')::UUID);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename='positions' AND policyname='tenant_iso_sel') THEN
    ALTER TABLE positions ENABLE ROW LEVEL SECURITY;
    ALTER TABLE positions FORCE ROW LEVEL SECURITY;
    CREATE POLICY tenant_iso_sel ON positions FOR SELECT USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', TRUE), '')::UUID);
    CREATE POLICY tenant_iso_ins ON positions FOR INSERT WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id', TRUE), '')::UUID);
    CREATE POLICY tenant_iso_upd ON positions FOR UPDATE USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', TRUE), '')::UUID);
    CREATE POLICY tenant_iso_del ON positions FOR DELETE USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', TRUE), '')::UUID);
  END IF;
END $$;
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='trg_branch_settings_touch') THEN
    CREATE TRIGGER trg_branch_settings_touch BEFORE UPDATE ON branch_settings FOR EACH ROW EXECUTE FUNCTION fn_touch_updated_at();
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='trg_positions_touch') THEN
    CREATE TRIGGER trg_positions_touch BEFORE UPDATE ON positions FOR EACH ROW EXECUTE FUNCTION fn_touch_updated_at();
  END IF;
END $$;

-- 3) indexes مفقودة لمشتريات phase13
CREATE INDEX IF NOT EXISTS ix_pr_lines_request ON purchase_request_lines(request_id);
CREATE INDEX IF NOT EXISTS ix_po_lines_order ON purchase_order_lines(order_id);
CREATE INDEX IF NOT EXISTS ix_gr_lines_receipt ON goods_receipt_lines(receipt_id);
