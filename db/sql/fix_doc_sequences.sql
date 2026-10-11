-- doc_sequences: تسلسل أرقام المستندات لكل كيان/نوع/سنة (فواتير، سندات، تحويلات).
CREATE TABLE IF NOT EXISTS doc_sequences (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  doctype VARCHAR(30) NOT NULL,
  year INTEGER NOT NULL,
  last_number BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, deleted_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT uq_docseq UNIQUE (tenant_id, entity_id, doctype, year)
);
ALTER TABLE doc_sequences ENABLE ROW LEVEL SECURITY;
ALTER TABLE doc_sequences FORCE ROW LEVEL SECURITY;
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename='doc_sequences' AND policyname='tenant_iso_sel') THEN
    CREATE POLICY tenant_iso_sel ON doc_sequences FOR SELECT USING (tenant_id = NULLIF(current_setting('app.current_tenant_id',true),'')::UUID);
    CREATE POLICY tenant_iso_ins ON doc_sequences FOR INSERT WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id',true),'')::UUID);
    CREATE POLICY tenant_iso_upd ON doc_sequences FOR UPDATE USING (tenant_id = NULLIF(current_setting('app.current_tenant_id',true),'')::UUID);
    CREATE POLICY tenant_iso_del ON doc_sequences FOR DELETE USING (tenant_id = NULLIF(current_setting('app.current_tenant_id',true),'')::UUID);
  END IF;
END $$;
DROP TRIGGER IF EXISTS trg_doc_sequences_touch ON doc_sequences;
CREATE TRIGGER trg_doc_sequences_touch BEFORE UPDATE ON doc_sequences FOR EACH ROW EXECUTE FUNCTION fn_touch_updated_at();
COMMENT ON TABLE doc_sequences IS 'تسلسلات المستندات | Document numbering';
