-- ============================================================================
-- 30_triggers.sql — المشغلات العامة | Generic triggers
-- نمط واحد لكل الجداول: updated_at + version + audit. يُركّب عبر سكربت لاحق.
-- ============================================================================

CREATE OR REPLACE FUNCTION fn_update_timestamp() RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN NEW.updated_at = NOW(); RETURN NEW; END $$;

CREATE OR REPLACE FUNCTION fn_bump_version() RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN NEW.version = COALESCE(OLD.version,0) + 1; RETURN NEW; END $$;

-- منع تعديل/حذف القيد المرحّل (القاعدة 2)
CREATE OR REPLACE FUNCTION fn_forbid_posted_mutation() RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  IF OLD.status = 'posted' THEN RAISE EXCEPTION 'POSTED_IMMUTABLE_USE_REVERSAL %', OLD.id; END IF;
  RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS trg_forbid_posted ON journal_entries;
CREATE TRIGGER trg_forbid_posted BEFORE UPDATE OR DELETE ON journal_entries
  FOR EACH ROW EXECUTE FUNCTION fn_forbid_posted_mutation();

-- توحيد posting_date في السطور مع رأس القيد
CREATE OR REPLACE FUNCTION fn_sync_line_date() RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  SELECT posting_date INTO NEW.entry_posting_date FROM journal_entries WHERE id = NEW.entry_id AND posting_date = NEW.entry_posting_date;
  NEW.posting_date := NEW.entry_posting_date;
  RETURN NEW;
END $$;

-- تركيب updated_at + version على الجداول المرجعية (تُكرر لكل جدول جديد):
-- CREATE TRIGGER trg_tenants_ts BEFORE UPDATE ON tenants FOR EACH ROW EXECUTE FUNCTION fn_update_timestamp();
