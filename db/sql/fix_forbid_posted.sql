-- Fix fn_forbid_posted: DELETE triggers must RETURN OLD (RETURN NEW silently skips).
CREATE OR REPLACE FUNCTION fn_forbid_posted() RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  IF OLD.status = 'posted' THEN RAISE EXCEPTION 'POSTED_IMMUTABLE % — use reversal', OLD.id; END IF;
  IF TG_OP = 'DELETE' THEN RETURN OLD; ELSE RETURN NEW; END IF;
END $$;
