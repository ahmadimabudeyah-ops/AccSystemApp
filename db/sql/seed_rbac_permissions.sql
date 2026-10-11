SET app.current_tenant_id='b39787b5-52fb-4fb0-b41f-98b90b5853d6';
INSERT INTO permissions(code,name_ar,module) VALUES
 ('payroll.manage','إدارة الرواتب','payroll'),
 ('education.manage','إدارة التعليم','education'),
 ('projects.manage','إدارة المشاريع والموازنات','projects'),
 ('period.close','إقفال الفترات','periods'),
 ('parties.view','عرض الأطراف','parties'),
 ('sales.view','عرض المبيعات','sales'),
 ('purchases.view','عرض المشتريات','purchases'),
 ('inventory.view','عرض المخزون','inventory'),
 ('treasury.view','عرض الخزينة','treasury')
ON CONFLICT (code) DO NOTHING;
