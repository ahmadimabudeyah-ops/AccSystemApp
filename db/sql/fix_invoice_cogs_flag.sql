-- إضافة عمود تتبع ترحيل كلفة البضاعة المباعة للفواتير المباشرة
-- عند ترحيل فاتورة بها أصناف مخزنية ولم يُرحَّل COGS بعد (فاتورة مباشرة بلا توصيل)
ALTER TABLE customer_invoices ADD COLUMN IF NOT EXISTS cogs_posted BOOLEAN NOT NULL DEFAULT FALSE;
