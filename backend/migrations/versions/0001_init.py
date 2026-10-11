"""Alembic revision: foundation marker (phase1-3 SQL).

revision = 0001_init
Foundation tables (tenants/users/entities/fiscal_years/fiscal_periods/
accounts/branches) are created by db/sql/phase1-3 SQL files, which are the
single source of truth for initial deploy (see db/sql/README.md + db-init
service in docker-compose.yml). This marker exists only to anchor the
dow_revision chain for 0002_engine. On a SQL-built database: flask db stamp 0002_engine.
"""
from alembic import op  # noqa: F401
import sqlalchemy as sa  # noqa: F401

revision = "0001_init"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
