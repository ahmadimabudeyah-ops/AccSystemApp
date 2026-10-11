-- ============================================================================
-- Phase 10 — الرواتب الأردنية (ضمان 21.75% + ضريبة دخل تصاعدية قابلة للضبط)
-- Requires: phase1. الشرائح الضريبية في جدول لتُضبط دون تعديل الكود.
-- ============================================================================

CREATE TABLE IF NOT EXISTS employees (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  party_id UUID REFERENCES parties(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  employee_no VARCHAR(50) NOT NULL,
  full_name_ar VARCHAR(255) NOT NULL, full_name_en VARCHAR(255),
  national_id VARCHAR(20), ss_number VARCHAR(30),
  hire_date DATE NOT NULL, end_date DATE,
  basic_salary NUMERIC(18,3) NOT NULL CHECK (basic_salary >= 0),
  housing_allowance NUMERIC(18,3) NOT NULL DEFAULT 0,
  transport_allowance NUMERIC(18,3) NOT NULL DEFAULT 0,
  other_allowances NUMERIC(18,3) NOT NULL DEFAULT 0,
  bank_iban VARCHAR(34),
  status VARCHAR(20) NOT NULL DEFAULT 'active',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, deleted_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT uq_employees_no UNIQUE (tenant_id, entity_id, employee_no),
  CONSTRAINT ck_emp_status CHECK (status IN ('active','on_leave','terminated','suspended'))
);

CREATE TABLE IF NOT EXISTS income_tax_brackets (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  year INTEGER NOT NULL,
  from_amount NUMERIC(18,3) NOT NULL, to_amount NUMERIC(18,3),
  rate NUMERIC(7,4) NOT NULL CHECK (rate >= 0 AND rate <= 100),
  valid_from DATE NOT NULL DEFAULT CURRENT_DATE, valid_to DATE, is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1, deleted_at TIMESTAMPTZ, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT ck_bracket_range CHECK (to_amount IS NULL OR to_amount > from_amount)
);

CREATE TABLE IF NOT EXISTS payroll_runs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  fiscal_period_id UUID NOT NULL REFERENCES fiscal_periods(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  run_code VARCHAR(50) NOT NULL,
  pay_month DATE NOT NULL,
  total_gross NUMERIC(18,3) NOT NULL DEFAULT 0, total_ss_employee NUMERIC(18,3) NOT NULL DEFAULT 0,
  total_ss_employer NUMERIC(18,3) NOT NULL DEFAULT 0, total_tax NUMERIC(18,3) NOT NULL DEFAULT 0,
  total_net NUMERIC(18,3) NOT NULL DEFAULT 0,
  status VARCHAR(30) NOT NULL DEFAULT 'draft',
  status_changed_at TIMESTAMPTZ, status_changed_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  journal_entry_id UUID REFERENCES journal_entries(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  event_key VARCHAR(200),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1,
  deleted_at TIMESTAMPTZ, deleted_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT uq_payroll_code UNIQUE (tenant_id, entity_id, run_code),
  CONSTRAINT ck_pay_status CHECK (status IN ('draft','posted','paid','cancelled'))
);

CREATE TABLE IF NOT EXISTS payslips (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE ON UPDATE CASCADE,
  run_id UUID NOT NULL REFERENCES payroll_runs(id) ON DELETE CASCADE ON UPDATE CASCADE,
  employee_id UUID NOT NULL REFERENCES employees(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  gross NUMERIC(18,3) NOT NULL, ss_employee NUMERIC(18,3) NOT NULL DEFAULT 0,
  ss_employer NUMERIC(18,3) NOT NULL DEFAULT 0, income_tax NUMERIC(18,3) NOT NULL DEFAULT 0,
  deductions NUMERIC(18,3) NOT NULL DEFAULT 0, net NUMERIC(18,3) NOT NULL,
  status VARCHAR(20) NOT NULL DEFAULT 'draft',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1, deleted_at TIMESTAMPTZ, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT uq_payslip UNIQUE (tenant_id, run_id, employee_id)
);

CREATE TABLE IF NOT EXISTS payslip_lines (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE ON UPDATE CASCADE,
  payslip_id UUID NOT NULL REFERENCES payslips(id) ON DELETE CASCADE ON UPDATE CASCADE,
  line_type VARCHAR(20) NOT NULL, label_ar VARCHAR(255) NOT NULL,
  amount NUMERIC(18,3) NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1, deleted_at TIMESTAMPTZ, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT ck_psl_type CHECK (line_type IN ('earning','deduction','employer_cost'))
);

CREATE TABLE IF NOT EXISTS employee_loans (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  employee_id UUID NOT NULL REFERENCES employees(id) ON DELETE CASCADE ON UPDATE CASCADE,
  amount NUMERIC(18,3) NOT NULL CHECK (amount > 0),
  installment NUMERIC(18,3) NOT NULL CHECK (installment > 0),
  remaining NUMERIC(18,3) NOT NULL,
  starts_on DATE NOT NULL, status VARCHAR(20) NOT NULL DEFAULT 'active',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1, deleted_at TIMESTAMPTZ, is_deleted BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS leave_requests (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  employee_id UUID NOT NULL REFERENCES employees(id) ON DELETE CASCADE ON UPDATE CASCADE,
  leave_type VARCHAR(30) NOT NULL DEFAULT 'annual',
  from_date DATE NOT NULL, to_date DATE NOT NULL,
  days_count INTEGER NOT NULL CHECK (days_count > 0),
  status VARCHAR(20) NOT NULL DEFAULT 'pending',
  reason TEXT, decided_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
  version INTEGER NOT NULL DEFAULT 1, deleted_at TIMESTAMPTZ, is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
  CONSTRAINT ck_leave_dates CHECK (to_date >= from_date)
);

CREATE INDEX IF NOT EXISTS idx_emp_entity ON employees(entity_id) WHERE is_deleted=FALSE;
CREATE INDEX IF NOT EXISTS idx_payslip_run ON payslips(run_id);
CREATE INDEX IF NOT EXISTS idx_run_period ON payroll_runs(fiscal_period_id);

DO $$ DECLARE t TEXT; arr TEXT[] := ARRAY['employees','income_tax_brackets','payroll_runs','payslips','payslip_lines','employee_loans','leave_requests'];
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

COMMENT ON TABLE employees IS 'الموظفون (ضمان + بنك) | Employees';
COMMENT ON TABLE payroll_runs IS 'مسيرات الرواتب الشهرية | Monthly payroll runs';
COMMENT ON TABLE payslips IS 'قسائم الرواتب | Payslips';
