-- ============================================================================
-- Phase 8 — الخزينة والأصول والضرائب والعملات | Requires: phase1
-- psql -f phase8_treasury_assets_taxes.sql
-- ============================================================================

CREATE TABLE IF NOT EXISTS currencies (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  code CHAR(3) NOT NULL, name_ar VARCHAR(255) NOT NULL, name_en VARCHAR(255),
  decimals INTEGER NOT NULL DEFAULT 3, symbol VARCHAR(10),
  valid_from DATE NOT NULL DEFAULT CURRENT_DATE, valid_to DATE, is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, deleted_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT uq_currencies_code UNIQUE (tenant_id, code),
  CONSTRAINT ck_curr_code CHECK (code ~ '^[A-Z]{3}$')
);

CREATE TABLE IF NOT EXISTS taxes (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  code VARCHAR(50) NOT NULL, name_ar VARCHAR(255) NOT NULL, name_en VARCHAR(255),
  rate NUMERIC(7,4) NOT NULL CHECK (rate >= 0 AND rate <= 100),
  tax_type VARCHAR(30) NOT NULL DEFAULT 'sale',
  valid_from DATE NOT NULL DEFAULT CURRENT_DATE, valid_to DATE, is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, deleted_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT uq_taxes_code UNIQUE (tenant_id, entity_id, code),
  CONSTRAINT ck_tax_type CHECK (tax_type IN ('sale','purchase','withholding','exempt','zero_rated'))
);

CREATE TABLE IF NOT EXISTS cash_boxes (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  branch_id UUID REFERENCES branches(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  code VARCHAR(50) NOT NULL, name_ar VARCHAR(255) NOT NULL,
  currency_id CHAR(3) NOT NULL DEFAULT 'JOD',
  opening_balance NUMERIC(18,3) NOT NULL DEFAULT 0,
  is_active BOOLEAN NOT NULL DEFAULT TRUE, notes TEXT,
  valid_from DATE NOT NULL DEFAULT CURRENT_DATE, valid_to DATE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, deleted_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT uq_cashbox_code UNIQUE (tenant_id, entity_id, code)
);

CREATE TABLE IF NOT EXISTS cash_transactions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  box_id UUID NOT NULL REFERENCES cash_boxes(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  doc_number VARCHAR(50) NOT NULL,
  txn_type VARCHAR(20) NOT NULL, -- in / out
  txn_date DATE NOT NULL DEFAULT CURRENT_DATE,
  amount NUMERIC(18,3) NOT NULL CHECK (amount > 0),
  currency_id CHAR(3) NOT NULL DEFAULT 'JOD',
  party_id UUID REFERENCES parties(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  description TEXT, reference VARCHAR(100),
  journal_entry_id UUID REFERENCES journal_entries(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  event_key VARCHAR(200),
  status VARCHAR(30) NOT NULL DEFAULT 'posted',
  status_changed_at TIMESTAMPTZ, status_changed_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, deleted_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT uq_cashtxn_num UNIQUE (tenant_id, entity_id, doc_number),
  CONSTRAINT uq_cashtxn_event UNIQUE (tenant_id, entity_id, event_key),
  CONSTRAINT ck_txn_type CHECK (txn_type IN ('in','out'))
);

CREATE TABLE IF NOT EXISTS banks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  code VARCHAR(50) NOT NULL, name_ar VARCHAR(255) NOT NULL, name_en VARCHAR(255),
  swift_code VARCHAR(20),
  valid_from DATE NOT NULL DEFAULT CURRENT_DATE, valid_to DATE, is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, deleted_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT uq_banks_code UNIQUE (tenant_id, code)
);

CREATE TABLE IF NOT EXISTS bank_accounts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  bank_id UUID NOT NULL REFERENCES banks(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  code VARCHAR(50) NOT NULL, iban VARCHAR(34),
  currency_id CHAR(3) NOT NULL DEFAULT 'JOD',
  opening_balance NUMERIC(18,3) NOT NULL DEFAULT 0,
  is_active BOOLEAN NOT NULL DEFAULT TRUE, notes TEXT,
  valid_from DATE NOT NULL DEFAULT CURRENT_DATE, valid_to DATE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, deleted_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT uq_bankacct_code UNIQUE (tenant_id, entity_id, code),
  CONSTRAINT ck_iban_fmt2 CHECK (iban IS NULL OR iban ~* '^[A-Z]{2}[0-9]{2}[A-Z0-9]+$')
);

CREATE TABLE IF NOT EXISTS checks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  bank_account_id UUID NOT NULL REFERENCES bank_accounts(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  check_no VARCHAR(50) NOT NULL, payee VARCHAR(255) NOT NULL,
  amount NUMERIC(18,3) NOT NULL CHECK (amount > 0),
  currency_id CHAR(3) NOT NULL DEFAULT 'JOD',
  issue_date DATE NOT NULL DEFAULT CURRENT_DATE, due_on DATE NOT NULL,
  status VARCHAR(30) NOT NULL DEFAULT 'issued',
  status_changed_at TIMESTAMPTZ, status_changed_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, deleted_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT uq_checks_no UNIQUE (tenant_id, bank_account_id, check_no),
  CONSTRAINT ck_check_status CHECK (status IN ('issued','cashed','bounced','cancelled','deferred'))
);

CREATE TABLE IF NOT EXISTS transfers (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  doc_number VARCHAR(50) NOT NULL,
  from_box_id UUID REFERENCES cash_boxes(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  to_box_id UUID REFERENCES cash_boxes(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  from_bank_account_id UUID REFERENCES bank_accounts(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  to_bank_account_id UUID REFERENCES bank_accounts(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  transfer_date DATE NOT NULL DEFAULT CURRENT_DATE,
  amount NUMERIC(18,3) NOT NULL CHECK (amount > 0),
  currency_id CHAR(3) NOT NULL DEFAULT 'JOD',
  status VARCHAR(30) NOT NULL DEFAULT 'posted',
  status_changed_at TIMESTAMPTZ, status_changed_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, deleted_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT uq_transfer_num UNIQUE (tenant_id, entity_id, doc_number)
);

CREATE TABLE IF NOT EXISTS asset_categories (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  code VARCHAR(50) NOT NULL, name_ar VARCHAR(255) NOT NULL, name_en VARCHAR(255),
  useful_life_years INTEGER NOT NULL DEFAULT 5 CHECK (useful_life_years > 0),
  depreciation_method VARCHAR(30) NOT NULL DEFAULT 'straight_line',
  valid_from DATE NOT NULL DEFAULT CURRENT_DATE, valid_to DATE, is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, deleted_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT uq_assetcat_code UNIQUE (tenant_id, code)
);

CREATE TABLE IF NOT EXISTS assets (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  category_id UUID NOT NULL REFERENCES asset_categories(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  code VARCHAR(50) NOT NULL, name_ar VARCHAR(255) NOT NULL, name_en VARCHAR(255),
  acquisition_date DATE NOT NULL, acquisition_cost NUMERIC(18,3) NOT NULL CHECK (acquisition_cost >= 0),
  residual_value NUMERIC(18,3) NOT NULL DEFAULT 0,
  accumulated_depreciation NUMERIC(18,3) NOT NULL DEFAULT 0,
  status VARCHAR(30) NOT NULL DEFAULT 'active',
  status_changed_at TIMESTAMPTZ, status_changed_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  location_text VARCHAR(255), notes TEXT,
  valid_from DATE NOT NULL DEFAULT CURRENT_DATE, valid_to DATE, is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, deleted_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT uq_assets_code UNIQUE (tenant_id, entity_id, code),
  CONSTRAINT ck_asset_status CHECK (status IN ('draft','active','fully_depreciated','disposed'))
);

-- ================= فهارس وRLS وTriggers =================
CREATE INDEX IF NOT EXISTS idx_currencies_tenant ON currencies(tenant_id) WHERE is_deleted=FALSE;
CREATE INDEX IF NOT EXISTS idx_taxes_tenant ON taxes(tenant_id);
CREATE INDEX IF NOT EXISTS idx_cashbox_entity ON cash_boxes(entity_id) WHERE is_deleted=FALSE;
CREATE INDEX IF NOT EXISTS idx_cashtxn_box ON cash_transactions(box_id);
CREATE INDEX IF NOT EXISTS idx_bankacct_entity ON bank_accounts(entity_id) WHERE is_deleted=FALSE;
CREATE INDEX IF NOT EXISTS idx_checks_due ON checks(due_on) WHERE is_deleted=FALSE;
CREATE INDEX IF NOT EXISTS idx_assets_entity ON assets(entity_id) WHERE is_deleted=FALSE;

DO $$ DECLARE t TEXT; arr TEXT[] := ARRAY['currencies','taxes','cash_boxes','cash_transactions','banks','bank_accounts','checks','transfers','asset_categories','assets'];
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

-- Seed: العملات والضريبة الأردنية (تُزرع لكل tenant عبر التطبيق)
COMMENT ON TABLE currencies IS 'العملات | Currencies';
COMMENT ON TABLE taxes IS 'الضرائب (16% مبيعات JO) | Taxes';
COMMENT ON TABLE cash_boxes IS 'الصناديق النقدية | Cash boxes';
COMMENT ON TABLE cash_transactions IS 'حركات النقد (قبض/صرف) | Cash IN/OUT';
COMMENT ON TABLE banks IS 'البنوك | Banks';
COMMENT ON TABLE bank_accounts IS 'الحسابات البنكية | Bank accounts';
COMMENT ON TABLE checks IS 'الشيكات | Checks';
COMMENT ON TABLE transfers IS 'التحويلات الداخلية | Internal transfers';
COMMENT ON TABLE asset_categories IS 'فئات الأصول | Asset categories';
COMMENT ON TABLE assets IS 'الأصول الثابتة | Fixed assets';
