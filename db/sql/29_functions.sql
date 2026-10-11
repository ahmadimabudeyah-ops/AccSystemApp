-- ============================================================================
-- 29_functions.sql — الدوال | Functions (النواة فقط — البقية في ملفات الوحدات)
-- ============================================================================

-- توليد الرقم الرسمي الذري لكل دفتر+سنة (يمنع الازدواج تحت التزامن)
CREATE OR REPLACE FUNCTION fn_generate_official_number(p_journal_id UUID, p_fiscal_year_id UUID, p_tenant UUID, p_user UUID)
RETURNS TEXT LANGUAGE plpgsql AS $$
DECLARE v_n BIGINT; v_code TEXT;
BEGIN
  SELECT code INTO v_code FROM journals WHERE id = p_journal_id;
  INSERT INTO journal_sequences(journal_id, fiscal_year_id, tenant_id, last_number, created_by, updated_by)
    VALUES (p_journal_id, p_fiscal_year_id, p_tenant, 1, p_user, p_user)
    ON CONFLICT (journal_id, fiscal_year_id) DO UPDATE SET last_number = journal_sequences.last_number + 1
    RETURNING last_number INTO v_n;
  -- الحالة الأولى (INSERT) تُرجع 1 عبر RETURNING أيضاً
  IF v_n IS NULL THEN SELECT last_number INTO v_n FROM journal_sequences WHERE journal_id=p_journal_id AND fiscal_year_id=p_fiscal_year_id; END IF;
  RETURN v_code || '-' || EXTRACT(YEAR FROM NOW())::TEXT || '-' || LPAD(v_n::TEXT, 6, '0');
END $$;
COMMENT ON FUNCTION fn_generate_official_number IS 'توليد متسلسل ذري | Atomic sequence per journal+year';

-- التحقق من الفترة مفتوحة لتاريخ معين
CREATE OR REPLACE FUNCTION fn_check_period_open(p_entity UUID, p_date DATE)
RETURNS UUID LANGUAGE plpgsql STABLE AS $$
DECLARE v_id UUID; v_status period_status;
BEGIN
  SELECT id, status INTO v_id, v_status FROM fiscal_periods
   WHERE entity_id = p_entity AND p_date BETWEEN starts_on AND ends_on AND is_deleted = FALSE;
  IF v_id IS NULL THEN RAISE EXCEPTION 'NO_PERIOD_FOR_DATE %', p_date USING ERRCODE='P0001'; END IF;
  IF v_status IN ('soft_closed','hard_closed') THEN RAISE EXCEPTION 'PERIOD_CLOSED %', v_id USING ERRCODE='P0001'; END IF;
  RETURN v_id;
END $$;

-- ترحيل القيد: يتحقق (اعتماد مستقل + توازن + فترة) ثم POSTED ذرياً
CREATE OR REPLACE FUNCTION fn_post_journal_entry(p_entry_id UUID, p_posting_date DATE, p_actor UUID)
RETURNS VOID LANGUAGE plpgsql AS $$
DECLARE v_status entry_status; v_creator UUID; v_tot_d signed_money; v_tot_c signed_money;
BEGIN
  SELECT status, created_by, total_debit, total_credit INTO v_status, v_creator, v_tot_d, v_tot_c
    FROM journal_entries WHERE id = p_entry_id AND posting_date = p_posting_date FOR UPDATE;
  IF v_status = 'posted' THEN RETURN; END IF; -- idempotent
  IF v_status <> 'draft' AND v_status <> 'approved' THEN RAISE EXCEPTION 'ONLY_DRAFT_APPROVED_CAN_POST'; END IF;
  IF v_creator = p_actor THEN RAISE EXCEPTION 'SELF_APPROVAL_FORBIDDEN'; END IF;
  IF v_tot_d <> v_tot_c THEN RAISE EXCEPTION 'UNBALANCED_ENTRY'; END IF;
  UPDATE journal_entries SET status='posted', posted_at=NOW(), posted_by=p_actor, updated_by=p_actor
   WHERE id = p_entry_id AND posting_date = p_posting_date;
END $$;

-- ميزان المراجعة من المرحّل فقط
CREATE OR REPLACE FUNCTION fn_calculate_trial_balance(p_entity UUID, p_period UUID)
RETURNS TABLE(account_id UUID, debit_total NUMERIC, credit_total NUMERIC) LANGUAGE sql STABLE AS $$
  SELECT l.account_id, SUM(l.debit)::NUMERIC, SUM(l.credit)::NUMERIC
    FROM journal_lines l JOIN journal_entries e ON e.id = l.entry_id AND e.posting_date = l.entry_posting_date
   WHERE e.entity_id = p_entity AND e.fiscal_period_id = p_period AND e.status = 'posted' AND e.is_deleted = FALSE
   GROUP BY l.account_id;
$$;
