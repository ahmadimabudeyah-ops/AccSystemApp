-- 0014_admin_wildcard.sql
-- The API layer treats "admin.*" as a super-administrator wildcard in more than
-- 40 guards (tenants.py, settings.py, provisioning.py, biz.py, parties.py ...).
-- The permission catalog never contained that code, so every TENANT_ADMIN /
-- TENANT_OWNER received 403 on those endpoints even though they hold the full
-- catalog.  Insert the wildcard once (global catalog, no RLS on permissions).
-- Grants are applied per-tenant by scripts/seed_rbac.py / scripts/fix_admin_wildcard.py.
-- Idempotent.

INSERT INTO permissions (code, name_ar, name_en, module)
VALUES ('admin.*', 'صلاحية مدير النظام', 'Super administrator', 'admin')
ON CONFLICT (code) DO NOTHING;
