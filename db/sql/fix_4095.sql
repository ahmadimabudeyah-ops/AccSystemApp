UPDATE accounts SET name_ar = 'أرباح (خسائر) فروقات العملة' WHERE code = '4095';
INSERT INTO accounts(tenant_id, entity_id, code, name_ar, name_en, parent_id,
                         account_type, normal_balance, is_postable)
SELECT a.tenant_id, a.entity_id, '4095', 'أرباح (خسائر) فروقات العملة', 'FX gain (loss)', a.id,
       'income', 'credit', TRUE
FROM accounts a WHERE a.code = '4' AND a.is_deleted = FALSE
  AND NOT EXISTS (SELECT 1 FROM accounts x WHERE x.entity_id = a.entity_id AND x.code = '4095');
