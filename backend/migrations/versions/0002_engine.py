"""Alembic revision: Core Accounting Engine (11 tables), reversible.

revision = 0002_engine
Requires: tenants/users/entities/fiscal_years/fiscal_periods/accounts/branches
(phase1-3 SQL or revision 0001_init). Stamp if already built from SQL:
    flask db stamp 0002_engine
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "0002_engine"
down_revision = "0001_init"
branch_labels = None
depends_on = None

AUDIT = [
    ("created_at", sa.DateTime(timezone=True), dict(server_default=sa.func.now(), nullable=False)),
    ("updated_at", sa.DateTime(timezone=True), dict(server_default=sa.func.now(), nullable=False)),
    ("created_by", UUID(as_uuid=True), {}),
    ("updated_by", UUID(as_uuid=True), {}),
    ("version", sa.Integer, dict(server_default="1", nullable=False)),
    ("deleted_at", sa.DateTime(timezone=True), {}),
    ("deleted_by", UUID(as_uuid=True), {}),
    ("is_deleted", sa.Boolean, dict(server_default="false", nullable=False)),
]


def _cols(*specs):
    return [sa.Column(n, t, **kw) for n, t, kw in specs + AUDIT]


def upgrade():
    op.create_table("journals", *_cols(
        ("id", UUID(as_uuid=True), dict(primary_key=True)),
        ("tenant_id", UUID(as_uuid=True), dict(nullable=False)),
        ("entity_id", UUID(as_uuid=True), dict(sa.ForeignKey("entities.id", ondelete="RESTRICT"), nullable=False)),
        ("code", sa.String(30), dict(nullable=False)),
        ("name", sa.String(255), dict(nullable=False)),
        ("type", sa.String(30), dict(server_default="general", nullable=False)),
        ("currency_id", sa.String(3), dict(server_default="JOD", nullable=False)),
        ("default_account_id", UUID(as_uuid=True), dict(sa.ForeignKey("accounts.id", ondelete="RESTRICT"))),
        ("sequence_prefix", sa.String(20), dict(server_default="", nullable=False)),
        ("sequence_length", sa.Integer, dict(server_default="6", nullable=False)),
        ("requires_approval", sa.Boolean, dict(server_default="true", nullable=False)),
        ("allow_manual", sa.Boolean, dict(server_default="true", nullable=False)),
        ("status", sa.String(30), dict(server_default="active", nullable=False)),
    ))
    op.create_unique_constraint("uq_journals_code", "journals", ["tenant_id", "entity_id", "code"])

    op.create_table("journal_sequences", *_cols(
        ("id", UUID(as_uuid=True), dict(primary_key=True)),
        ("tenant_id", UUID(as_uuid=True), dict(nullable=False)),
        ("entity_id", UUID(as_uuid=True), dict(sa.ForeignKey("entities.id", ondelete="RESTRICT"), nullable=False)),
        ("journal_id", UUID(as_uuid=True), dict(sa.ForeignKey("journals.id", ondelete="CASCADE"), nullable=False)),
        ("fiscal_year_id", UUID(as_uuid=True), dict(sa.ForeignKey("fiscal_years.id", ondelete="RESTRICT"), nullable=False)),
        ("last_number", sa.BigInteger, dict(server_default="0", nullable=False)),
        ("prefix", sa.String(20), dict(server_default="", nullable=False)),
        ("suffix", sa.String(20), dict(server_default="", nullable=False)),
        ("length", sa.Integer, dict(server_default="6", nullable=False)),
        ("last_used_at", sa.DateTime(timezone=True), {}),
        ("last_used_by", UUID(as_uuid=True), {}),
    ))
    op.create_unique_constraint("uq_jseq", "journal_sequences", ["tenant_id", "journal_id", "fiscal_year_id"])

    op.create_table("journal_entries", *_cols(
        ("id", UUID(as_uuid=True), dict(primary_key=True)),
        ("tenant_id", UUID(as_uuid=True), dict(nullable=False, index=True)),
        ("entity_id", UUID(as_uuid=True), dict(sa.ForeignKey("entities.id", ondelete="RESTRICT"), nullable=False, index=True)),
        ("journal_id", UUID(as_uuid=True), dict(sa.ForeignKey("journals.id", ondelete="RESTRICT"), nullable=False, index=True)),
        ("entry_type", sa.String(30), dict(server_default="manual", nullable=False)),
        ("document_date", sa.Date, dict(nullable=False)),
        ("posting_date", sa.Date, dict(nullable=False, index=True)),
        ("period_id", UUID(as_uuid=True), dict(sa.ForeignKey("fiscal_periods.id", ondelete="RESTRICT"), nullable=False)),
        ("description", sa.Text, {}),
        ("reference", sa.String(100), {}),
        ("source_module", sa.String(50), dict(server_default="manual", nullable=False)),
        ("source_document_id", UUID(as_uuid=True), {}),
        ("source_event_key", sa.String(200), {}),
        ("source_version", sa.Integer, dict(server_default="1", nullable=False)),
        ("currency_id", sa.String(3), dict(server_default="JOD", nullable=False)),
        ("exchange_rate", sa.Numeric(18, 10), dict(server_default="1", nullable=False)),
        ("total_debit", sa.Numeric(18, 3), dict(server_default="0", nullable=False)),
        ("total_credit", sa.Numeric(18, 3), dict(server_default="0", nullable=False)),
        ("status", sa.String(30), dict(server_default="draft", nullable=False, index=True)),
        ("status_changed_at", sa.DateTime(timezone=True), {}),
        ("status_changed_by", UUID(as_uuid=True), {}),
        ("official_number", sa.String(60), dict(index=True)),
        ("approved_at", sa.DateTime(timezone=True), {}),
        ("approved_by", UUID(as_uuid=True), {}),
        ("posted_at", sa.DateTime(timezone=True), {}),
        ("posted_by", UUID(as_uuid=True), {}),
        ("reversal_of_id", UUID(as_uuid=True), dict(index=True)),
        ("is_reversed", sa.Boolean, dict(server_default="false", nullable=False)),
    ))
    op.create_foreign_key("fk_entries_reversal", "journal_entries", "journal_entries",
                          ["reversal_of_id"], ["id"], ondelete="RESTRICT")
    op.create_unique_constraint("uq_entry_official", "journal_entries",
                                ["tenant_id", "entity_id", "journal_id", "official_number"])
    op.create_unique_constraint("uq_entry_event", "journal_entries",
                                ["tenant_id", "entity_id", "source_event_key"])
    op.create_index("ix_entries_entity_status", "journal_entries", ["entity_id", "status"])

    op.create_table("journal_lines", *_cols(
        ("id", UUID(as_uuid=True), dict(primary_key=True)),
        ("tenant_id", UUID(as_uuid=True), dict(nullable=False)),
        ("entity_id", UUID(as_uuid=True), dict(sa.ForeignKey("entities.id", ondelete="RESTRICT"), nullable=False)),
        ("entry_id", UUID(as_uuid=True), dict(sa.ForeignKey("journal_entries.id", ondelete="CASCADE"), nullable=False)),
        ("line_number", sa.Integer, dict(nullable=False)),
        ("account_id", UUID(as_uuid=True), dict(sa.ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False)),
        ("debit", sa.Numeric(18, 3), dict(server_default="0", nullable=False)),
        ("credit", sa.Numeric(18, 3), dict(server_default="0", nullable=False)),
        ("currency_id", sa.String(3), dict(server_default="JOD", nullable=False)),
        ("amount_currency", sa.Numeric(18, 3), dict(server_default="0", nullable=False)),
        ("exchange_rate", sa.Numeric(18, 10), dict(server_default="1", nullable=False)),
        ("amount_functional", sa.Numeric(18, 3), dict(server_default="0", nullable=False)),
        ("partner_id", UUID(as_uuid=True), {}),
        ("due_date", sa.Date, {}),
        ("branch_id", UUID(as_uuid=True), dict(sa.ForeignKey("branches.id", ondelete="RESTRICT"))),
        ("dimensions", JSONB, dict(server_default="{}", nullable=False)),
        ("description", sa.Text, {}),
        ("source_line_ref", sa.String(100), {}),
        ("reconciliation_id", UUID(as_uuid=True), {}),
    ))
    op.create_unique_constraint("uq_line_no", "journal_lines", ["entry_id", "line_number"])
    op.create_index("ix_lines_entry", "journal_lines", ["entry_id"])
    op.create_index("ix_lines_account", "journal_lines", ["account_id"])

    op.create_table("account_hierarchy", *_cols(
        ("ancestor_id", UUID(as_uuid=True), dict(sa.ForeignKey("accounts.id", ondelete="CASCADE"), primary_key=True)),
        ("descendant_id", UUID(as_uuid=True), dict(sa.ForeignKey("accounts.id", ondelete="CASCADE"), primary_key=True)),
        ("tenant_id", UUID(as_uuid=True), dict(nullable=False)),
        ("entity_id", UUID(as_uuid=True), dict(sa.ForeignKey("entities.id", ondelete="CASCADE"), nullable=False)),
        ("depth", sa.Integer, dict(server_default="0", nullable=False)),
        ("sort_order", sa.Integer, dict(server_default="0", nullable=False)),
        ("is_leaf", sa.Boolean, dict(server_default="true", nullable=False)),
    ))

    op.create_table("event_keys", *_cols(
        ("id", UUID(as_uuid=True), dict(primary_key=True)),
        ("tenant_id", UUID(as_uuid=True), dict(nullable=False)),
        ("entity_id", UUID(as_uuid=True), dict(sa.ForeignKey("entities.id", ondelete="RESTRICT"), nullable=False)),
        ("source_module", sa.String(50), dict(nullable=False)),
        ("source_document_id", UUID(as_uuid=True), dict(nullable=False)),
        ("event_type", sa.String(100), dict(nullable=False)),
        ("event_version", sa.Integer, dict(server_default="1", nullable=False)),
        ("event_key", sa.String(200), dict(nullable=False)),
        ("status", sa.String(20), dict(server_default="pending", nullable=False)),
        ("journal_entry_id", UUID(as_uuid=True), dict(sa.ForeignKey("journal_entries.id", ondelete="RESTRICT"))),
        ("processed_at", sa.DateTime(timezone=True), {}),
        ("retry_count", sa.Integer, dict(server_default="0", nullable=False)),
        ("last_error", sa.Text, {}),
    ))
    op.create_unique_constraint("uq_event_key", "event_keys", ["tenant_id", "entity_id", "event_key"])

    op.create_table("reversal_links", *_cols(
        ("id", UUID(as_uuid=True), dict(primary_key=True)),
        ("tenant_id", UUID(as_uuid=True), dict(nullable=False)),
        ("entity_id", UUID(as_uuid=True), dict(sa.ForeignKey("entities.id", ondelete="RESTRICT"), nullable=False)),
        ("original_entry_id", UUID(as_uuid=True), dict(sa.ForeignKey("journal_entries.id", ondelete="RESTRICT"), nullable=False, unique=True)),
        ("reversal_entry_id", UUID(as_uuid=True), dict(sa.ForeignKey("journal_entries.id", ondelete="RESTRICT"), nullable=False, unique=True)),
        ("reversal_date", sa.Date, dict(nullable=False)),
        ("reason", sa.Text, dict(nullable=False)),
        ("reversed_by", UUID(as_uuid=True), dict(nullable=False)),
        ("reversal_type", sa.String(20), dict(server_default="full", nullable=False)),
        ("amount_reversed", sa.Numeric(18, 3), {}),
    ))

    op.create_table("entry_approvals", *_cols(
        ("id", UUID(as_uuid=True), dict(primary_key=True)),
        ("tenant_id", UUID(as_uuid=True), dict(nullable=False)),
        ("entity_id", UUID(as_uuid=True), dict(sa.ForeignKey("entities.id", ondelete="CASCADE"), nullable=False)),
        ("entry_id", UUID(as_uuid=True), dict(sa.ForeignKey("journal_entries.id", ondelete="CASCADE"), nullable=False)),
        ("approver_id", UUID(as_uuid=True), dict(sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)),
        ("approval_level", sa.Integer, dict(server_default="1", nullable=False)),
        ("status", sa.String(20), dict(server_default="pending", nullable=False)),
        ("reason", sa.Text, {}),
        ("approved_at", sa.DateTime(timezone=True), {}),
        ("sequence", sa.Integer, dict(server_default="1", nullable=False)),
        ("is_mandatory", sa.Boolean, dict(server_default="true", nullable=False)),
        ("expires_at", sa.DateTime(timezone=True), {}),
    ))
    op.create_unique_constraint("uq_entry_approval", "entry_approvals",
                                ["tenant_id", "entry_id", "approver_id"])
    op.create_index("ix_approvals_entry", "entry_approvals", ["entry_id"])

    op.create_table("entry_attachments", *_cols(
        ("id", UUID(as_uuid=True), dict(primary_key=True)),
        ("tenant_id", UUID(as_uuid=True), dict(nullable=False)),
        ("entity_id", UUID(as_uuid=True), dict(sa.ForeignKey("entities.id", ondelete="CASCADE"), nullable=False)),
        ("entry_id", UUID(as_uuid=True), dict(sa.ForeignKey("journal_entries.id", ondelete="CASCADE"), nullable=False)),
        ("file_name", sa.String(255), dict(nullable=False)),
        ("file_type", sa.String(100), dict(nullable=False)),
        ("file_size", sa.BigInteger, dict(nullable=False)),
        ("storage_path", sa.Text, dict(nullable=False)),
        ("file_hash", sa.String(128), dict(nullable=False)),
        ("uploaded_by", UUID(as_uuid=True), dict(nullable=False)),
        ("uploaded_at", sa.DateTime(timezone=True), dict(server_default=sa.func.now(), nullable=False)),
    ))

    op.create_table("entry_comments", *_cols(
        ("id", UUID(as_uuid=True), dict(primary_key=True)),
        ("tenant_id", UUID(as_uuid=True), dict(nullable=False)),
        ("entity_id", UUID(as_uuid=True), dict(sa.ForeignKey("entities.id", ondelete="CASCADE"), nullable=False)),
        ("entry_id", UUID(as_uuid=True), dict(sa.ForeignKey("journal_entries.id", ondelete="CASCADE"), nullable=False)),
        ("comment", sa.Text, dict(nullable=False)),
        ("commented_by", UUID(as_uuid=True), dict(nullable=False)),
        ("commented_at", sa.DateTime(timezone=True), dict(server_default=sa.func.now(), nullable=False)),
        ("comment_type", sa.String(30), dict(server_default="note", nullable=False)),
        ("is_internal", sa.Boolean, dict(server_default="true", nullable=False)),
    ))


def downgrade():
    for table in ("entry_comments", "entry_attachments", "entry_approvals",
                  "reversal_links", "event_keys", "account_hierarchy",
                  "journal_lines", "journal_entries", "journal_sequences", "journals"):
        op.drop_table(table)
