"""Alembic revision: stock counts, bill matches, settings columns.

revision = 0003_counts_settings
Complements db/sql/fix_counts_settings_match.sql (db-init path).
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "0003_counts_settings"
down_revision = "0002_engine"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("full_name", sa.Text(), nullable=True))
    op.add_column("tenants", sa.Column("tax_id", sa.String(50), nullable=True))
    for tbl in ("vendor_bills", "vendor_payments", "customer_payments"):
        op.add_column(tbl, sa.Column("exchange_rate", sa.Numeric(18, 10),
                                     server_default="1", nullable=False))
    op.create_table(
        "stock_counts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("entity_id", UUID(as_uuid=True),
                  sa.ForeignKey("entities.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("doc_number", sa.String(50), nullable=False),
        sa.Column("warehouse_id", UUID(as_uuid=True),
                  sa.ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("count_date", sa.Date, nullable=False),
        sa.Column("status", sa.String(30), server_default="draft", nullable=False),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", UUID(as_uuid=True)),
        sa.Column("updated_by", UUID(as_uuid=True)),
        sa.Column("version", sa.Integer, server_default="1", nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("is_deleted", sa.Boolean, server_default="false", nullable=False),
        sa.UniqueConstraint("tenant_id", "entity_id", "doc_number"),
    )
    op.create_index("ix_stock_counts_entity_status", "stock_counts", ["entity_id", "status"])
    op.create_table(
        "stock_count_lines",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("count_id", UUID(as_uuid=True),
                  sa.ForeignKey("stock_counts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("line_number", sa.Integer, nullable=False),
        sa.Column("product_id", UUID(as_uuid=True),
                  sa.ForeignKey("products.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("location_id", UUID(as_uuid=True),
                  sa.ForeignKey("locations.id", ondelete="RESTRICT")),
        sa.Column("system_qty", sa.Numeric(18, 6), server_default="0", nullable=False),
        sa.Column("counted_qty", sa.Numeric(18, 6)),
        sa.Column("unit_cost", sa.Numeric(18, 6), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", UUID(as_uuid=True)),
        sa.Column("updated_by", UUID(as_uuid=True)),
        sa.Column("version", sa.Integer, server_default="1", nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("is_deleted", sa.Boolean, server_default="false", nullable=False),
        sa.UniqueConstraint("count_id", "line_number"),
    )
    op.create_index("ix_count_lines_count", "stock_count_lines", ["count_id"])
    op.create_table(
        "bill_matches",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("entity_id", UUID(as_uuid=True),
                  sa.ForeignKey("entities.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("bill_id", UUID(as_uuid=True),
                  sa.ForeignKey("vendor_bills.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("matched", sa.Boolean, nullable=False),
        sa.Column("details", JSONB, server_default="[]", nullable=False),
        sa.Column("matched_by", UUID(as_uuid=True)),
        sa.Column("matched_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", UUID(as_uuid=True)),
        sa.Column("updated_by", UUID(as_uuid=True)),
        sa.Column("version", sa.Integer, server_default="1", nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("is_deleted", sa.Boolean, server_default="false", nullable=False),
    )
    op.create_index("ix_bill_matches_bill", "bill_matches", ["bill_id"])


def downgrade():
    op.drop_index("ix_bill_matches_bill", table_name="bill_matches")
    op.drop_table("bill_matches")
    op.drop_index("ix_count_lines_count", table_name="stock_count_lines")
    op.drop_table("stock_count_lines")
    op.drop_index("ix_stock_counts_entity_status", table_name="stock_counts")
    op.drop_table("stock_counts")
    for tbl in ("vendor_bills", "vendor_payments", "customer_payments"):
        op.drop_column(tbl, "exchange_rate")
    op.drop_column("tenants", "tax_id")
    op.drop_column("users", "full_name")
