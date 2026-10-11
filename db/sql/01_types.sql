-- ============================================================================
-- 01_types.sql — الأنواع المخصصة | Custom ENUM Types
-- 18 نوعاً حسب المواصفات. ENUM (وليس TEXT+CHECK) للأنواع المستقرة محاسبياً.
-- مبرر: ENUM يمنع القيم الشاذة على مستوى التخزين + أداء أفضل من CHECK.
-- بديل مرفوض: TEXT حر — يسمح بأخطاء مثل 'Posted' مقابل 'posted'.
-- ============================================================================

DO $$ BEGIN CREATE TYPE account_type AS ENUM ('asset','liability','equity','income','expense','contra_asset','contra_liability','contra_equity','contra_income','contra_expense'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE account_control_type AS ENUM ('general','customer','supplier','employee','inventory','asset','bank','cash','tax','loan','equity'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE journal_type AS ENUM ('sale','purchase','cash','bank','general','opening','closing','adjustment','revaluation','consolidation'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE entry_status AS ENUM ('draft','pending_review','approved','posted','reversed','cancelled'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE entry_type AS ENUM ('manual','source','opening','reversal','closing','adjustment','accrual','deferral'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE period_status AS ENUM ('future','open','soft_closed','hard_closed'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE party_type AS ENUM ('customer','supplier','employee','student','guardian','bank','government','other'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE product_type AS ENUM ('stockable','service','consumable','kit','subscription'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE cost_method AS ENUM ('fifo','lifo','average','standard','specific'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE move_type AS ENUM ('receipt','delivery','internal','adjustment','scrap','return','manufacturing','transit'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE invoice_status AS ENUM ('draft','pending','approved','posted','paid','partially_paid','cancelled','reversed'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE payment_status AS ENUM ('draft','confirmed','posted','reconciled','cancelled','bounced'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE asset_status AS ENUM ('draft','active','fully_depreciated','disposed','transferred','impaired'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE tax_type AS ENUM ('sale','purchase','withholding','reverse_charge','exempt','zero_rated'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE tax_computation AS ENUM ('percentage','fixed','group','formula'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE employee_status AS ENUM ('active','on_leave','terminated','suspended','retired'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE student_status AS ENUM ('applicant','enrolled','active','graduated','withdrawn','suspended','transferred'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE budget_status AS ENUM ('draft','pending','approved','active','closed','cancelled'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE project_status AS ENUM ('draft','active','on_hold','completed','cancelled','closed'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE approval_status AS ENUM ('pending','approved','rejected','cancelled','expired'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE audit_action AS ENUM ('create','read','update','delete','post','reverse','approve','reject','export','login','logout','access','restore'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
