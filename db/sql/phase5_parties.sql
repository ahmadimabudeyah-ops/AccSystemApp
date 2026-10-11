-- ============================================================================
-- Phase 5 — الأطراف الموحدة (20 جدول) | Requires: phase1
-- psql -f phase5_parties.sql
-- قرار: طرف موحد + أنواع عبر assignments (N:M) — نفس الشركة عميل+مورد بسجل واحد.
-- البديل المرفوض: جداول منفصلة customers/suppliers (تكرار عناوين/اتصالات + انشطار الذمم).
-- الوحدانية: فهرس جزئي UNIQUE(party_id) WHERE is_primary — رئيسي واحد فقط لكل نوع.
-- ============================================================================

-- ================= A: النواة (7) =================
CREATE TABLE IF NOT EXISTS parties (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  code VARCHAR(50) NOT NULL,
  name_ar VARCHAR(500) NOT NULL, name_en VARCHAR(500), legal_name VARCHAR(500),
  legal_type VARCHAR(30) NOT NULL DEFAULT 'company', -- individual/company/government
  status VARCHAR(30) NOT NULL DEFAULT 'draft',
  preferred_lang VARCHAR(10) NOT NULL DEFAULT 'ar',
  default_currency CHAR(3) NOT NULL DEFAULT 'JOD',
  payment_terms_days INTEGER NOT NULL DEFAULT 0 CHECK (payment_terms_days >= 0),
  credit_limit NUMERIC(18,3) NOT NULL DEFAULT 0, credit_currency CHAR(3) NOT NULL DEFAULT 'JOD',
  notes TEXT, metadata JSONB NOT NULL DEFAULT '{}',
  registered_on DATE, last_txn_at TIMESTAMPTZ, qr_code TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, deleted_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT uq_parties_code UNIQUE (tenant_id, entity_id, code),
  CONSTRAINT ck_party_legal CHECK (legal_type IN ('individual','company','government')),
  CONSTRAINT ck_party_status CHECK (status IN ('draft','active','inactive','suspended','blocked','archived'))
);

CREATE TABLE IF NOT EXISTS party_types (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  code VARCHAR(50) NOT NULL, name_ar VARCHAR(255) NOT NULL, name_en VARCHAR(255),
  description TEXT, is_default BOOLEAN NOT NULL DEFAULT FALSE, is_system BOOLEAN NOT NULL DEFAULT TRUE,
  valid_from DATE NOT NULL DEFAULT CURRENT_DATE, valid_to DATE, is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, deleted_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT uq_ptypes_code UNIQUE (tenant_id, code)
);

CREATE TABLE IF NOT EXISTS party_type_assignments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE ON UPDATE CASCADE,
  party_id UUID NOT NULL REFERENCES parties(id) ON DELETE CASCADE ON UPDATE CASCADE,
  party_type_id UUID NOT NULL REFERENCES party_types(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  valid_from DATE NOT NULL DEFAULT CURRENT_DATE, valid_to DATE, is_active BOOLEAN NOT NULL DEFAULT TRUE,
  is_primary BOOLEAN NOT NULL DEFAULT FALSE,
  notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, deleted_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT uq_pta UNIQUE (tenant_id, party_id, party_type_id)
);

CREATE TABLE IF NOT EXISTS party_categories (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  code VARCHAR(50) NOT NULL, name_ar VARCHAR(255) NOT NULL, name_en VARCHAR(255),
  description TEXT, parent_id UUID REFERENCES party_categories(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  valid_from DATE NOT NULL DEFAULT CURRENT_DATE, valid_to DATE, is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, deleted_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT uq_pcat_code UNIQUE (tenant_id, code)
);

CREATE TABLE IF NOT EXISTS party_category_assignments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE ON UPDATE CASCADE,
  party_id UUID NOT NULL REFERENCES parties(id) ON DELETE CASCADE ON UPDATE CASCADE,
  category_id UUID NOT NULL REFERENCES party_categories(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  valid_from DATE NOT NULL DEFAULT CURRENT_DATE, valid_to DATE, is_active BOOLEAN NOT NULL DEFAULT TRUE,
  notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, deleted_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT uq_pca UNIQUE (tenant_id, party_id, category_id)
);

CREATE TABLE IF NOT EXISTS party_tags (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  code VARCHAR(50) NOT NULL, name_ar VARCHAR(255) NOT NULL, name_en VARCHAR(255),
  color VARCHAR(20),
  valid_from DATE NOT NULL DEFAULT CURRENT_DATE, valid_to DATE, is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, deleted_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT uq_ptags_code UNIQUE (tenant_id, code)
);

CREATE TABLE IF NOT EXISTS party_tag_assignments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE ON UPDATE CASCADE,
  party_id UUID NOT NULL REFERENCES parties(id) ON DELETE CASCADE ON UPDATE CASCADE,
  tag_id UUID NOT NULL REFERENCES party_tags(id) ON DELETE CASCADE ON UPDATE CASCADE,
  assigned_on DATE NOT NULL DEFAULT CURRENT_DATE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, deleted_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT uq_ptta UNIQUE (tenant_id, party_id, tag_id)
);

-- ================= B: العناوين والاتصال (4) =================
CREATE TABLE IF NOT EXISTS party_addresses (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE ON UPDATE CASCADE,
  party_id UUID NOT NULL REFERENCES parties(id) ON DELETE CASCADE ON UPDATE CASCADE,
  address_type VARCHAR(20) NOT NULL DEFAULT 'primary',
  address1 VARCHAR(500) NOT NULL, address2 VARCHAR(500),
  city VARCHAR(150), region VARCHAR(150), postal_code VARCHAR(30),
  country CHAR(2) NOT NULL DEFAULT 'JO',
  latitude NUMERIC(10,7), longitude NUMERIC(10,7),
  contact_name VARCHAR(255), phone VARCHAR(50), email CITEXT,
  is_primary BOOLEAN NOT NULL DEFAULT FALSE,
  valid_from DATE NOT NULL DEFAULT CURRENT_DATE, valid_to DATE, is_active BOOLEAN NOT NULL DEFAULT TRUE,
  notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, deleted_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT ck_addr_type CHECK (address_type IN ('primary','billing','shipping','legal','branch','warehouse','other'))
);

CREATE TABLE IF NOT EXISTS party_contacts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE ON UPDATE CASCADE,
  party_id UUID NOT NULL REFERENCES parties(id) ON DELETE CASCADE ON UPDATE CASCADE,
  contact_type VARCHAR(20) NOT NULL, -- phone/mobile/email/fax/whatsapp/...
  contact_value VARCHAR(500) NOT NULL,
  is_primary BOOLEAN NOT NULL DEFAULT FALSE, is_verified BOOLEAN NOT NULL DEFAULT FALSE,
  verified_at TIMESTAMPTZ,
  valid_from DATE NOT NULL DEFAULT CURRENT_DATE, valid_to DATE, is_active BOOLEAN NOT NULL DEFAULT TRUE,
  notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, deleted_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT ck_contact_type CHECK (contact_type IN ('phone','mobile','email','fax','whatsapp','telegram','website','linkedin','other'))
);

CREATE TABLE IF NOT EXISTS party_contact_verifications (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE ON UPDATE CASCADE,
  contact_id UUID NOT NULL REFERENCES party_contacts(id) ON DELETE CASCADE ON UPDATE CASCADE,
  method VARCHAR(20) NOT NULL,
  verification_code VARCHAR(20) NOT NULL,
  sent_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), verified_at TIMESTAMPTZ,
  status VARCHAR(20) NOT NULL DEFAULT 'pending',
  attempts INTEGER NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, deleted_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT ck_ver_method CHECK (method IN ('email','sms','call')),
  CONSTRAINT ck_ver_status CHECK (status IN ('pending','verified','expired','failed'))
);

CREATE TABLE IF NOT EXISTS party_relationships (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE ON UPDATE CASCADE,
  from_party_id UUID NOT NULL REFERENCES parties(id) ON DELETE CASCADE ON UPDATE CASCADE,
  to_party_id UUID NOT NULL REFERENCES parties(id) ON DELETE CASCADE ON UPDATE CASCADE,
  relationship_type VARCHAR(30) NOT NULL,
  valid_from DATE NOT NULL DEFAULT CURRENT_DATE, valid_to DATE, is_active BOOLEAN NOT NULL DEFAULT TRUE,
  notes TEXT,
  ownership_pct NUMERIC(7,4),
  guarantee_amount NUMERIC(18,3), guarantee_currency CHAR(3) DEFAULT 'JOD',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, deleted_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT ck_rel_self CHECK (from_party_id <> to_party_id),
  CONSTRAINT ck_rel_type CHECK (relationship_type IN ('parent','subsidiary','affiliate','guarantor','authorized_signatory','financial_responsible','beneficiary','payer','contact_person','emergency_contact','other')),
  CONSTRAINT uq_rel UNIQUE (tenant_id, from_party_id, to_party_id, relationship_type)
);

-- ================= C: المالي والضريبي (4) =================
CREATE TABLE IF NOT EXISTS party_bank_accounts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE ON UPDATE CASCADE,
  party_id UUID NOT NULL REFERENCES parties(id) ON DELETE CASCADE ON UPDATE CASCADE,
  bank_name VARCHAR(255) NOT NULL, swift_code VARCHAR(20),
  account_number VARCHAR(50) NOT NULL, iban VARCHAR(34),
  currency_id CHAR(3) NOT NULL DEFAULT 'JOD',
  branch_name VARCHAR(255), holder_name VARCHAR(255) NOT NULL,
  is_primary BOOLEAN NOT NULL DEFAULT FALSE,
  is_approved BOOLEAN NOT NULL DEFAULT FALSE, approved_at TIMESTAMPTZ,
  approved_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  valid_from DATE NOT NULL DEFAULT CURRENT_DATE, valid_to DATE, is_active BOOLEAN NOT NULL DEFAULT TRUE,
  notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, deleted_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT uq_bank_acct UNIQUE (tenant_id, party_id, account_number),
  CONSTRAINT ck_iban_fmt CHECK (iban IS NULL OR iban ~* '^[A-Z]{2}[0-9]{2}[A-Z0-9]+$')
);

CREATE TABLE IF NOT EXISTS party_bank_account_approvals (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE ON UPDATE CASCADE,
  bank_account_id UUID NOT NULL REFERENCES party_bank_accounts(id) ON DELETE CASCADE ON UPDATE CASCADE,
  approver_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  approval_action VARCHAR(20) NOT NULL, -- create/update/delete
  status VARCHAR(20) NOT NULL DEFAULT 'pending',
  reason TEXT, decided_at TIMESTAMPTZ, notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, deleted_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT ck_baa_action CHECK (approval_action IN ('create','update','delete')),
  CONSTRAINT ck_baa_status CHECK (status IN ('pending','approved','rejected'))
);

CREATE TABLE IF NOT EXISTS party_tax_profiles (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE ON UPDATE CASCADE,
  party_id UUID NOT NULL REFERENCES parties(id) ON DELETE CASCADE ON UPDATE CASCADE,
  country_code CHAR(2) NOT NULL DEFAULT 'JO',
  tax_id VARCHAR(50) NOT NULL,
  registered_on DATE, expires_on DATE,
  tax_type VARCHAR(30) NOT NULL DEFAULT 'vat',
  tax_rate NUMERIC(7,4),
  is_exempt BOOLEAN NOT NULL DEFAULT FALSE, exempt_reason TEXT, exempt_cert_url TEXT,
  exempt_from DATE, exempt_to DATE,
  notes TEXT,
  valid_from DATE NOT NULL DEFAULT CURRENT_DATE, valid_to DATE, is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, deleted_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT uq_tax_profile UNIQUE (tenant_id, party_id, tax_id, country_code),
  CONSTRAINT ck_tax_len CHECK (LENGTH(tax_id) >= 5)
);

CREATE TABLE IF NOT EXISTS party_tax_registrations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE ON UPDATE CASCADE,
  party_id UUID NOT NULL REFERENCES parties(id) ON DELETE CASCADE ON UPDATE CASCADE,
  tax_type VARCHAR(30) NOT NULL,
  reg_number VARCHAR(50) NOT NULL,
  registered_on DATE NOT NULL, cancelled_on DATE,
  status VARCHAR(20) NOT NULL DEFAULT 'active', notes TEXT,
  valid_from DATE NOT NULL DEFAULT CURRENT_DATE, valid_to DATE, is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, deleted_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT uq_tax_reg UNIQUE (tenant_id, party_id, tax_type, reg_number)
);

-- ================= D: الائتمان والمستندات (5) =================
CREATE TABLE IF NOT EXISTS party_credit_limits (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE ON UPDATE CASCADE,
  party_id UUID NOT NULL REFERENCES parties(id) ON DELETE CASCADE ON UPDATE CASCADE,
  credit_limit NUMERIC(18,3) NOT NULL CHECK (credit_limit >= 0),
  currency_id CHAR(3) NOT NULL DEFAULT 'JOD',
  valid_from DATE NOT NULL DEFAULT CURRENT_DATE, valid_to DATE, is_active BOOLEAN NOT NULL DEFAULT TRUE,
  override_reason TEXT,
  approved_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, deleted_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE, is_deleted BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS party_credit_history (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE ON UPDATE CASCADE,
  party_id UUID NOT NULL REFERENCES parties(id) ON DELETE CASCADE ON UPDATE CASCADE,
  old_limit NUMERIC(18,3) NOT NULL, new_limit NUMERIC(18,3) NOT NULL,
  currency_id CHAR(3) NOT NULL DEFAULT 'JOD',
  changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  change_reason TEXT NOT NULL,
  approved_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, deleted_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE, is_deleted BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS party_documents (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE ON UPDATE CASCADE,
  party_id UUID NOT NULL REFERENCES parties(id) ON DELETE CASCADE ON UPDATE CASCADE,
  doc_type VARCHAR(50) NOT NULL, doc_number VARCHAR(100) NOT NULL,
  issued_on DATE, expires_on DATE, issuer VARCHAR(255),
  storage_path TEXT NOT NULL, file_size BIGINT, file_hash VARCHAR(128),
  status VARCHAR(20) NOT NULL DEFAULT 'active', notes TEXT,
  valid_from DATE NOT NULL DEFAULT CURRENT_DATE, valid_to DATE, is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, deleted_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT ck_doc_status CHECK (status IN ('active','expired','cancelled'))
);

CREATE TABLE IF NOT EXISTS party_notes (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE ON UPDATE CASCADE,
  party_id UUID NOT NULL REFERENCES parties(id) ON DELETE CASCADE ON UPDATE CASCADE,
  note_text TEXT NOT NULL,
  note_type VARCHAR(20) NOT NULL DEFAULT 'general',
  priority VARCHAR(20) NOT NULL DEFAULT 'medium',
  is_pinned BOOLEAN NOT NULL DEFAULT FALSE, attachments JSONB NOT NULL DEFAULT '[]',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, deleted_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT ck_note_type CHECK (note_type IN ('general','internal','warning','important')),
  CONSTRAINT ck_note_prio CHECK (priority IN ('low','medium','high','urgent'))
);

CREATE TABLE IF NOT EXISTS party_attachments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE ON UPDATE CASCADE,
  party_id UUID NOT NULL REFERENCES parties(id) ON DELETE CASCADE ON UPDATE CASCADE,
  file_name VARCHAR(255) NOT NULL, file_type VARCHAR(100) NOT NULL,
  file_size BIGINT NOT NULL CHECK (file_size > 0 AND file_size <= 52428800),
  storage_path TEXT NOT NULL, file_hash VARCHAR(128) NOT NULL,
  uploaded_by UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  uploaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, deleted_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE, is_deleted BOOLEAN NOT NULL DEFAULT FALSE
);

-- ================= الفهارس =================
CREATE INDEX IF NOT EXISTS idx_parties_tenant ON parties(tenant_id);
CREATE INDEX IF NOT EXISTS idx_parties_entity ON parties(entity_id) WHERE is_deleted=FALSE;
CREATE INDEX IF NOT EXISTS idx_pta_party ON party_type_assignments(party_id);
CREATE INDEX IF NOT EXISTS idx_pta_type ON party_type_assignments(party_type_id);
CREATE INDEX IF NOT EXISTS idx_addr_party_primary ON party_addresses(party_id, is_primary) WHERE is_deleted=FALSE;
CREATE INDEX IF NOT EXISTS idx_addr_validity ON party_addresses(party_id, valid_from, valid_to);
CREATE INDEX IF NOT EXISTS idx_contact_party_type ON party_contacts(party_id, contact_type) WHERE is_deleted=FALSE;
CREATE INDEX IF NOT EXISTS idx_bank_party_primary ON party_bank_accounts(party_id, is_primary) WHERE is_deleted=FALSE;
CREATE INDEX IF NOT EXISTS idx_tax_party ON party_tax_profiles(party_id, tax_id);
CREATE INDEX IF NOT EXISTS idx_rel_party_type ON party_relationships(from_party_id, relationship_type) WHERE is_deleted=FALSE;
CREATE INDEX IF NOT EXISTS idx_credit_party_curr ON party_credit_limits(party_id, currency_id) WHERE is_deleted=FALSE;
CREATE INDEX IF NOT EXISTS gin_parties_meta ON parties USING GIN (metadata);
CREATE INDEX IF NOT EXISTS gin_parties_name_trgm ON parties USING GIN (name_ar gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_parties_active ON parties(deleted_at) WHERE is_deleted=FALSE;
-- وحدانية الرئيسي (جزئي):
CREATE UNIQUE INDEX IF NOT EXISTS uq_addr_primary ON party_addresses(party_id) WHERE is_primary AND is_deleted=FALSE;
CREATE UNIQUE INDEX IF NOT EXISTS uq_bank_primary ON party_bank_accounts(party_id) WHERE is_primary AND is_deleted=FALSE;

-- ================= Triggers =================
-- سجل الائتمان تلقائياً عند تغيير الحد
CREATE OR REPLACE FUNCTION fn_credit_history() RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  IF OLD.credit_limit IS DISTINCT FROM NEW.credit_limit THEN
    INSERT INTO party_credit_history(tenant_id, party_id, old_limit, new_limit, currency_id, change_reason, created_by, updated_by)
    VALUES (NEW.tenant_id, NEW.party_id, OLD.credit_limit, NEW.credit_limit, NEW.currency_id, COALESCE(NEW.override_reason,'limit change'), NEW.updated_by, NEW.updated_by);
  END IF;
  RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS trg_credit_hist ON party_credit_limits;
CREATE TRIGGER trg_credit_hist AFTER UPDATE ON party_credit_limits FOR EACH ROW EXECUTE FUNCTION fn_credit_history();

-- منع حذف طرف له مستندات/قيود مستقبلية (مستندات هنا)
CREATE OR REPLACE FUNCTION fn_party_no_delete_with_docs() RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  IF EXISTS (SELECT 1 FROM party_documents WHERE party_id=OLD.id AND is_deleted=FALSE) THEN RAISE EXCEPTION 'PARTY_HAS_DOCUMENTS %', OLD.id; END IF;
  RETURN OLD;
END $$;
DROP TRIGGER IF EXISTS trg_party_nodelete ON parties;
CREATE TRIGGER trg_party_nodelete BEFORE DELETE ON parties FOR EACH ROW EXECUTE FUNCTION fn_party_no_delete_with_docs();

DO $$ DECLARE t TEXT; arr TEXT[] := ARRAY['parties','party_types','party_type_assignments','party_categories','party_category_assignments','party_tags','party_tag_assignments','party_addresses','party_contacts','party_contact_verifications','party_relationships','party_bank_accounts','party_bank_account_approvals','party_tax_profiles','party_tax_registrations','party_credit_limits','party_credit_history','party_documents','party_notes','party_attachments'];
BEGIN FOREACH t IN ARRAY arr LOOP EXECUTE format('DROP TRIGGER IF EXISTS trg_%s_touch ON %I',t,t); EXECUTE format('CREATE TRIGGER trg_%s_touch BEFORE UPDATE ON %I FOR EACH ROW EXECUTE FUNCTION fn_touch_updated_at()',t,t); END LOOP; END $$;

-- ================= RLS =================
DO $$ DECLARE t TEXT; arr TEXT[] := ARRAY['parties','party_types','party_type_assignments','party_categories','party_category_assignments','party_tags','party_tag_assignments','party_addresses','party_contacts','party_contact_verifications','party_relationships','party_bank_accounts','party_bank_account_approvals','party_tax_profiles','party_tax_registrations','party_credit_limits','party_credit_history','party_documents','party_notes','party_attachments'];
BEGIN FOREACH t IN ARRAY arr LOOP
  EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY',t);
  EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY',t);
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename=t AND policyname='tenant_iso_sel') THEN
    EXECUTE format('CREATE POLICY tenant_iso_sel ON %I FOR SELECT USING (tenant_id = NULLIF(current_setting(%L,true),%L)::UUID)',t,'app.current_tenant_id','');
    EXECUTE format('CREATE POLICY tenant_iso_ins ON %I FOR INSERT WITH CHECK (tenant_id = NULLIF(current_setting(%L,true),%L)::UUID)',t,'app.current_tenant_id','');
    EXECUTE format('CREATE POLICY tenant_iso_upd ON %I FOR UPDATE USING (tenant_id = NULLIF(current_setting(%L,true),%L)::UUID)',t,'app.current_tenant_id','');
    EXECUTE format('CREATE POLICY tenant_iso_del ON %I FOR DELETE USING (tenant_id = NULLIF(current_setting(%L,true),%L)::UUID)',t,'app.current_tenant_id','');
  END IF;
END LOOP; END $$;

-- ================= Seed =================
INSERT INTO party_types(tenant_id, code, name_ar, name_en) SELECT id, x.code, x.ar, x.en FROM tenants, (VALUES
 ('customer','عميل','Customer'),('supplier','مورد','Supplier'),('employee','موظف','Employee'),
 ('student','طالب','Student'),('guardian','ولي أمر','Guardian'),('bank','بنك','Bank'),
 ('government','جهة حكومية','Government'),('shareholder','مساهم','Shareholder'),('partner','شريك','Partner'),
 ('agent','وكيل','Agent'),('distributor','موزع','Distributor'),('contractor','مقاول','Contractor'),
 ('consultant','مستشار','Consultant'),('landlord','مالك عقار','Landlord'),('other','أخرى','Other')
) AS x(code,ar,en) ON CONFLICT DO NOTHING; -- يُزرع لكل tenant موجود؛ الجديد عبر التطبيق

COMMENT ON TABLE parties IS 'الأطراف الموحدة — سجل واحد متعدد الأنواع عبر assignments | Unified parties';
COMMENT ON TABLE party_relationships IS 'علاقات الأطراف — منع ذاتي CK + وحدانية الاتجاه | No self-relation';
COMMENT ON TABLE party_bank_accounts IS 'حسابات بنكية — رئيسي واحد (فهرس جزئي) + اعتماد | Single primary';
