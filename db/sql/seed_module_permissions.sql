SET app.current_tenant_id='b39787b5-52fb-4fb0-b41f-98b90b5853d6';
INSERT INTO permissions(code,name_ar,module) VALUES
 ('parties.manage','إدارة الأطراف','parties'),
 ('products.manage','إدارة الأصناف','products'),
 ('inventory.manage','إدارة المخزون','inventory'),
 ('sales.manage','إدارة المبيعات','sales'),
 ('purchases.manage','إدارة المشتريات','purchases')
ON CONFLICT (code) DO NOTHING;
INSERT INTO role_permissions(tenant_id,role_id,permission_id)
SELECT r.tenant_id,r.id,p.id FROM roles r CROSS JOIN permissions p
WHERE r.code IN ('TENANT_ADMIN','ACCOUNTANT')
AND p.code IN ('parties.manage','products.manage','inventory.manage','sales.manage','purchases.manage')
ON CONFLICT DO NOTHING;
