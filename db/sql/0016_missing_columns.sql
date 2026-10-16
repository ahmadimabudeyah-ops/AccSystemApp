-- 0016_missing_columns.sql
-- Columns defined in SQLAlchemy models but missing from the DB schema.
-- Found by scripts/check_schema.py. Idempotent.

-- debit_notes: journal_entry_id + event_key + deleted_by
ALTER TABLE debit_notes ADD COLUMN IF NOT EXISTS journal_entry_id UUID REFERENCES journal_entries(id) ON DELETE RESTRICT;
ALTER TABLE debit_notes ADD COLUMN IF NOT EXISTS event_key VARCHAR(200);
ALTER TABLE debit_notes ADD COLUMN IF NOT EXISTS deleted_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE;

-- api_request_logs: deleted_at
ALTER TABLE api_request_logs ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;
