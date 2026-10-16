"""0014 admin.* wildcard permission

The API layer treats "admin.*" as a super-administrator wildcard in more than
40 guards, but the permission catalog never contained that code, so
TENANT_ADMIN / TENANT_OWNER received 403 on those endpoints.

Revision ID: 0015_admin_wildcard
Revises: 0004_chart_levels
Create Date: 2026-10-14
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0005_admin_wildcard"
down_revision: Union[str, None] = "0004_chart_levels"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text(
        "INSERT INTO permissions (code, name_ar, name_en, module) VALUES"
        " ('admin.*', 'صلاحية مدير النظام', 'Super administrator', 'admin')"
        " ON CONFLICT (code) DO NOTHING"))
    # Grant to the owner-level roles of every existing tenant.
    rows = conn.execute(sa.text(
        "SELECT DISTINCT rp.tenant_id, r.id AS role_id"
        " FROM roles r"
        " JOIN role_permissions rp ON rp.role_id = r.id"
        " JOIN permissions p ON p.id = rp.permission_id"
        " WHERE r.code IN ('TENANT_ADMIN','TENANT_OWNER')"
        "   AND p.code = 'reports.view'")).fetchall()
    perm_id = conn.execute(sa.text(
        "SELECT id FROM permissions WHERE code='admin.*'")).scalar()
    for tenant_id, role_id in rows:
        conn.execute(sa.text(
            "SET app.current_tenant_id = :t"), {"t": str(tenant_id)})
        conn.execute(sa.text(
            "INSERT INTO role_permissions (tenant_id, role_id, permission_id)"
            " VALUES (:t, :r, :p) ON CONFLICT (role_id, permission_id) DO NOTHING"),
            {"t": str(tenant_id), "r": str(role_id), "p": str(perm_id)})


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text(
        "DELETE FROM role_permissions WHERE permission_id IN"
        " (SELECT id FROM permissions WHERE code='admin.*')"))
    conn.execute(sa.text(
        "DELETE FROM permissions WHERE code='admin.*'"))
