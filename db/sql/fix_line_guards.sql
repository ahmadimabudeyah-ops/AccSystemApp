-- Fix fn_line_guards: UUID was assigned into VARCHAR(30) (truncation error).
CREATE OR REPLACE FUNCTION fn_line_guards() RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE v_pid UUID; v_open TEXT; v_postable BOOL; v_active BOOL; v_eacc UUID;
BEGIN
  SELECT fiscal_period_id INTO v_pid FROM journal_entries WHERE id = NEW.entry_id;
  SELECT status INTO v_open FROM fiscal_periods WHERE id = v_pid;
  IF v_open IN ('soft_closed','hard_closed') THEN RAISE EXCEPTION 'PERIOD_CLOSED'; END IF;
  SELECT is_postable, is_active, entity_id INTO v_postable, v_active, v_eacc FROM accounts WHERE id = NEW.account_id;
  IF NOT v_postable THEN RAISE EXCEPTION 'ACCOUNT_NOT_POSTABLE %', NEW.account_id; END IF;
  IF NOT v_active THEN RAISE EXCEPTION 'ACCOUNT_INACTIVE %', NEW.account_id; END IF;
  IF v_eacc IS DISTINCT FROM NEW.entity_id THEN RAISE EXCEPTION 'ACCOUNT_OTHER_ENTITY'; END IF;
  RETURN NEW;
END $$;
