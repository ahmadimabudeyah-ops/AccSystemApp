-- ============================================================================
-- 00_extensions.sql — الإضافات | Extensions (PostgreSQL 16+)
-- تنفيذ أولاً | Run first. Idempotent.
-- قرار: gen_random_uuid() من pgcrypto هو المعيار (UUID v4).
-- بديل مرفوض: UUID v7 يحتاج pg_uuidv7 (غير مدمج في PG16) — نتحول لـ uuidv7()
-- في PG18+ بتبديل سطر واحد، دون تغيير الأعمدة.
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;            -- gen_random_uuid(), pgp_sym_encrypt
CREATE EXTENSION IF NOT EXISTS pg_trgm;             -- بحث عربي/إنجليزي + GIN trigram
CREATE EXTENSION IF NOT EXISTS btree_gin;          -- فهارس مركبة GIN
CREATE EXTENSION IF NOT EXISTS btree_gist;         -- GiST للفترات الزمنية
CREATE EXTENSION IF NOT EXISTS pg_stat_statements; -- تحليل الأداء (EXPLAIN/مراقبة)

-- Collation عربي موحد (إن توفرت ICU في البناء، وإلا fallback لـ C.UTF-8):
-- CREATE COLLATION IF NOT EXISTS ar_JO (LOCALE = 'ar-JO.utf8', PROVIDER = icu);
