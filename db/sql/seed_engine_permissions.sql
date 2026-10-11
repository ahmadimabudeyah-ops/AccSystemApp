SET app.current_tenant_id='b39787b5-52fb-4fb0-b41f-98b90b5853d6';
INSERT INTO permissions(code,name_ar,name_en,module) VALUES
 ('journals.post','ترحيل القيود','Post entries','journals'),
 ('journals.reverse','عكس القيود','Reverse entries','journals'),
 ('journals.approve','اعتماد القيود','Approve entries','journals'),
 ('journals.create','إنشاء دفتر','Create journal','journals'),
 ('accounts.create','إنشاء حساب','Create account','accounts'),
 ('accounts.update','تعديل حساب','Update account','accounts'),
 ('accounts.delete','حذف حساب','Delete account','accounts'),
 ('reports.view','عرض التقارير','View reports','reports')
ON CONFLICT (code) DO NOTHING;
INSERT INTO role_permissions(tenant_id,role_id,permission_id)
SELECT r.tenant_id,r.id,p.id FROM roles r CROSS JOIN permissions p
WHERE r.code='TENANT_ADMIN'
AND p.code IN ('journals.post','journals.reverse','journals.approve','journals.create','accounts.create','accounts.update','accounts.delete','reports.view')
ON CONFLICT DO NOTHING;
