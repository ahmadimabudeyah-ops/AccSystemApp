-- ============================================================================
-- 02_domains.sql — الدومينات | Domains (تحقق تلقائي على مستوى العمود)
-- NUMERIC(18,3) للمبالغ حسب المواصفات (3 منازل). exchange_rate بدقة (18,10).
-- ============================================================================

DO $$ BEGIN CREATE DOMAIN money_amount AS NUMERIC(18,3) CHECK (VALUE >= 0); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE DOMAIN signed_money AS NUMERIC(18,3); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE DOMAIN positive_amount AS NUMERIC(18,3) CHECK (VALUE > 0); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE DOMAIN percentage AS NUMERIC(7,4) CHECK (VALUE >= -100 AND VALUE <= 100); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE DOMAIN exchange_rate AS NUMERIC(18,10) CHECK (VALUE > 0); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE DOMAIN quantity AS NUMERIC(18,6) CHECK (VALUE >= 0); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE DOMAIN email_address AS VARCHAR(255) CHECK (VALUE ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE DOMAIN phone_number AS VARCHAR(50) CHECK (VALUE ~* '^\+?[0-9\s\-\(\)]+$'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE DOMAIN country_code AS CHAR(2) CHECK (VALUE ~ '^[A-Z]{2}$'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE DOMAIN currency_code AS CHAR(3) CHECK (VALUE ~ '^[A-Z]{3}$'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE DOMAIN iban AS VARCHAR(34) CHECK (VALUE ~* '^[A-Z]{2}[0-9]{2}[A-Z0-9]+$'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE DOMAIN tax_id AS VARCHAR(50) CHECK (LENGTH(VALUE) >= 5); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
