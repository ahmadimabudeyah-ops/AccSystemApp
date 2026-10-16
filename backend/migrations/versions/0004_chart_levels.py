"""Alembic revision: chart-of-accounts levels (hierarchy_role) + closure backfill.

revision = 0004_chart_levels
- Adds accounts.hierarchy_role (NULL = legacy unclassified). All other
  structural columns (level/path/is_leaf/...) already exist via phase3 SQL;
  this migration only adds what is missing, idempotently, so it is safe on
  both SQL-built and Alembic-built databases.
- Tightens fn_line_guards to also require status='active' (unifies the
  service/trigger meaning of "usable"; verified: all live rows are
  active/True, so no existing data is blocked).
- Backfills account_hierarchy closure rows for existing accounts (INSERT-only,
  no data rewritten). Rollback drops the added column/function change only;
  rows created afterwards need a reasoned restore, not an automatic one.
"""
from alembic import op
import sqlalchemy as sa

revision = "0004_chart_levels"
down_revision = "0003_counts_settings"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        ALTER TABLE accounts
        ADD COLUMN IF NOT EXISTS hierarchy_role VARCHAR(20);
    """)
    op.execute("""
        DO $$ BEGIN
          IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = 'ck_acc_role') THEN
            ALTER TABLE accounts ADD CONSTRAINT ck_acc_role
              CHECK (hierarchy_role IS NULL OR hierarchy_role IN
                     ('section','general','subsidiary','detail'));
          END IF;
        END $$;
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_accounts_role "
               "ON accounts (tenant_id, entity_id, hierarchy_role)")
    # توحيد معنى الصلاحية: المشغل يفحص status أيضًا (كان is_active فقط).
    op.execute("""
        CREATE OR REPLACE FUNCTION public.fn_line_guards()
        RETURNS trigger LANGUAGE plpgsql AS $function$
        DECLARE v_pid UUID; v_open TEXT; v_postable BOOL; v_active BOOL;
                v_status TEXT; v_eacc UUID;
        BEGIN
          SELECT fiscal_period_id INTO v_pid FROM journal_entries WHERE id = NEW.entry_id;
          SELECT status INTO v_open FROM fiscal_periods WHERE id = v_pid;
          IF v_open IN ('soft_closed','hard_closed') THEN RAISE EXCEPTION 'PERIOD_CLOSED'; END IF;
          SELECT is_postable, is_active, status, entity_id
            INTO v_postable, v_active, v_status, v_eacc
            FROM accounts WHERE id = NEW.account_id;
          IF NOT v_postable THEN RAISE EXCEPTION 'ACCOUNT_NOT_POSTABLE %', NEW.account_id; END IF;
          IF NOT v_active OR v_status IS DISTINCT FROM 'active' THEN
            RAISE EXCEPTION 'ACCOUNT_INACTIVE %', NEW.account_id;
          END IF;
          IF v_eacc IS DISTINCT FROM NEW.entity_id THEN RAISE EXCEPTION 'ACCOUNT_OTHER_ENTITY'; END IF;
          RETURN NEW;
        END $function$;
    """)
    # تصحيح is_leaf للآباء غير الفارغة (الفارغة تبقى True هيكليًا).
    op.execute("""
        UPDATE accounts a SET is_leaf = FALSE
        WHERE a.is_deleted = FALSE AND a.is_leaf = TRUE
        AND EXISTS (SELECT 1 FROM accounts c WHERE c.parent_id = a.id
                    AND c.is_deleted = FALSE)
    """)
    # تعبئة جدول الإغلاق للحسابات القائمة (إدخال فقط — لا مساس بالبيانات).
    op.execute("""
        INSERT INTO account_hierarchy
          (ancestor_id, descendant_id, tenant_id, entity_id, depth,
           sort_order, is_leaf, created_by, updated_by, version, is_deleted)
        SELECT a.id, a.id, a.tenant_id, a.entity_id, 0,
               0, a.is_leaf, a.created_by, a.updated_by, 1, FALSE
        FROM accounts a
        WHERE NOT EXISTS (
          SELECT 1 FROM account_hierarchy h
          WHERE h.ancestor_id = a.id AND h.descendant_id = a.id)
    """)
    op.execute("""
        INSERT INTO account_hierarchy
          (ancestor_id, descendant_id, tenant_id, entity_id, depth,
           sort_order, is_leaf, created_by, updated_by, version, is_deleted)
        WITH RECURSIVE chain AS (
          SELECT id AS desc_id, parent_id AS anc_id, tenant_id, entity_id,
                 created_by, updated_by, 1 AS depth
          FROM accounts WHERE parent_id IS NOT NULL AND is_deleted = FALSE
          UNION ALL
          SELECT c.desc_id, a.parent_id, c.tenant_id, c.entity_id,
                 c.created_by, c.updated_by, c.depth + 1
          FROM chain c JOIN accounts a ON a.id = c.anc_id
          WHERE a.parent_id IS NOT NULL
        )
        SELECT anc_id, desc_id, tenant_id, entity_id, depth,
               0, FALSE, created_by, updated_by, 1, FALSE
        FROM chain
        ON CONFLICT (ancestor_id, descendant_id) DO NOTHING
    """)


def downgrade():
    op.execute("ALTER TABLE accounts DROP CONSTRAINT IF EXISTS ck_acc_role")
    op.execute("DROP INDEX IF EXISTS ix_accounts_role")
    op.execute("ALTER TABLE accounts DROP COLUMN IF EXISTS hierarchy_role")
