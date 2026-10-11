-- Allow payment-application updates (paid/remaining/status) on posted invoices.
-- Financial fields (totals, dates, customer, currency) remain frozen.
CREATE OR REPLACE FUNCTION fn_forbid_posted_invoice() RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  IF OLD.status = 'posted' THEN
    IF NEW.grand_total IS NOT DISTINCT FROM OLD.grand_total
       AND NEW.subtotal IS NOT DISTINCT FROM OLD.subtotal
       AND NEW.tax_total IS NOT DISTINCT FROM OLD.tax_total
       AND NEW.invoice_date IS NOT DISTINCT FROM OLD.invoice_date
       AND NEW.customer_id IS NOT DISTINCT FROM OLD.customer_id
       AND NEW.currency_id IS NOT DISTINCT FROM OLD.currency_id THEN
      RETURN NEW;
    END IF;
    RAISE EXCEPTION 'POSTED_INVOICE_IMMUTABLE %', OLD.id;
  END IF;
  RETURN NEW;
END $$;
