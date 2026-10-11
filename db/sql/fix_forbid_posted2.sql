-- Allow the single legitimate transition posted -> reversed (status flip only).
-- All other mutations of posted rows still raise.
CREATE OR REPLACE FUNCTION fn_forbid_posted() RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  IF OLD.status = 'posted' THEN
    IF NEW.status = 'reversed'
       AND NEW.total_debit IS NOT DISTINCT FROM OLD.total_debit
       AND NEW.total_credit IS NOT DISTINCT FROM OLD.total_credit
       AND NEW.posting_date IS NOT DISTINCT FROM OLD.posting_date
       AND NEW.fiscal_period_id IS NOT DISTINCT FROM OLD.fiscal_period_id
       AND NEW.entry_type IS NOT DISTINCT FROM OLD.entry_type
       AND NEW.journal_id IS NOT DISTINCT FROM OLD.journal_id THEN
      IF TG_OP = 'DELETE' THEN RETURN OLD; ELSE RETURN NEW; END IF;
    END IF;
    RAISE EXCEPTION 'POSTED_IMMUTABLE % — use reversal', OLD.id;
  END IF;
  IF TG_OP = 'DELETE' THEN RETURN OLD; ELSE RETURN NEW; END IF;
END $$;
