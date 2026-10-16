"""0006 portal tokens + missing model columns

portal_tokens existed only in the ORM, so POST /api/v1/portal-tokens failed
with "permission denied for table portal_tokens"; debit_notes carried
journal_entry_id / event_key / deleted_by columns in the model only; and
api_request_logs lacked deleted_at.  All three gaps are closed here, matching
db/sql/0015_portal_tokens.sql and db/sql/0016_missing_columns.sql.

Revision ID: 0006_portal_tokens_columns
Revises: 0005_admin_wildcard
Create Date: 2026-10-14
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0006_portal_tokens_columns"
down_revision: Union[str, None] = "0005_admin_wildcard"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS portal_tokens (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE RESTRICT ON UPDATE CASCADE,
          party_id UUID NOT NULL REFERENCES parties(id) ON DELETE CASCADE,
          token_hash VARCHAR(128) NOT NULL,
          scope VARCHAR(30) NOT NULL DEFAULT 'statement',
          expires_at TIMESTAMPTZ NOT NULL,
          last_used_at TIMESTAMPTZ,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          created_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
          updated_by UUID REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE,
          version INTEGER NOT NULL DEFAULT 1,
          deleted_at TIMESTAMPTZ,
          is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
          CONSTRAINT uq_portal_tokens_hash UNIQUE (token_hash)
        )
    """))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_portal_tokens_party ON portal_tokens (party_id)"))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS ix_portal_tokens_tenant ON portal_tokens (tenant_id)"))

    conn.execute(sa.text(
        "ALTER TABLE debit_notes ADD COLUMN IF NOT EXISTS journal_entry_id UUID"
        " REFERENCES journal_entries(id) ON DELETE RESTRICT"))
    conn.execute(sa.text(
        "ALTER TABLE debit_notes ADD COLUMN IF NOT EXISTS event_key VARCHAR(200)"))
    conn.execute(sa.text(
        "ALTER TABLE debit_notes ADD COLUMN IF NOT EXISTS deleted_by UUID"
        " REFERENCES users(id) ON DELETE RESTRICT ON UPDATE CASCADE"))
    conn.execute(sa.text(
        "ALTER TABLE api_request_logs ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ"))

    # RLS with the same tenant_iso_* policies used by every other tenant table
    conn.execute(sa.text(
        "ALTER TABLE portal_tokens ENABLE ROW LEVEL SECURITY"))
    conn.execute(sa.text(
        "ALTER TABLE portal_tokens FORCE ROW LEVEL SECURITY"))
    for cmd, using in (
        ("tenant_iso_sel", "USING (tenant_id = NULLIF(current_setting('app.current_tenant_id',true),'')::UUID)"),
        ("tenant_iso_ins", "WITH CHECK (tenant_id = NULLIF(current_setting('app.current_tenant_id',true),'')::UUID)"),
        ("tenant_iso_upd", "USING (tenant_id = NULLIF(current_setting('app.current_tenant_id',true),'')::UUID)"),
        ("tenant_iso_del", "USING (tenant_id = NULLIF(current_setting('app.current_tenant_id',true),'')::UUID)"),
    ):
        verb = {"tenant_iso_sel": "SELECT", "tenant_iso_ins": "INSERT",
                "tenant_iso_upd": "UPDATE", "tenant_iso_del": "DELETE"}[cmd]
        conn.execute(sa.text(
            f"DROP POLICY IF EXISTS {cmd} ON portal_tokens"))
        conn.execute(sa.text(
            f"CREATE POLICY {cmd} ON portal_tokens FOR {verb} {using}"))

    conn.execute(sa.text("""
        CREATE OR REPLACE FUNCTION fn_touch_updated_at() RETURNS trigger AS $$
        BEGIN
          NEW.updated_at := NOW();
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """))
    conn.execute(sa.text(
        "DROP TRIGGER IF EXISTS trg_portal_tokens_touch ON portal_tokens"))
    conn.execute(sa.text(
        "CREATE TRIGGER trg_portal_tokens_touch BEFORE UPDATE ON portal_tokens"
        " FOR EACH ROW EXECUTE FUNCTION fn_touch_updated_at()"))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DROP TABLE IF EXISTS portal_tokens"))
    conn.execute(sa.text("ALTER TABLE debit_notes DROP COLUMN IF EXISTS journal_entry_id"))
    conn.execute(sa.text("ALTER TABLE debit_notes DROP COLUMN IF EXISTS event_key"))
    conn.execute(sa.text("ALTER TABLE debit_notes DROP COLUMN IF EXISTS deleted_by"))
    conn.execute(sa.text("ALTER TABLE api_request_logs DROP COLUMN IF EXISTS deleted_at"))
