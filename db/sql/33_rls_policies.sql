-- ============================================================================
-- 33_rls_policies.sql — سياسات العزل | RLS (تُطبق على كل جدول tenant)
-- المفتاح: SET app.current_tenant_id = '<uuid>' قبل كل معاملة (من Middleware).
-- بدون SET: current_setting يُرجع NULL -> الشرط FALSE -> صفر صفوف (آمن افتراضياً).
-- ============================================================================

-- قالب يُكرر لكل جدول (مثال موثق على 6 جداول نواة، والبقية بنفس النمط عبر مولد):
DO $$ DECLARE t TEXT; tables TEXT[] := ARRAY['entities','branches','accounts','journals','journal_entries','journal_lines','users','fiscal_periods','event_keys'];
BEGIN
  FOREACH t IN ARRAY tables LOOP
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
    EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', t);
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE tablename=t AND policyname='tenant_iso_sel') THEN
      EXECUTE format('CREATE POLICY tenant_iso_sel ON %I FOR SELECT USING (tenant_id = NULLIF(current_setting(%L,true),%L)::UUID)', t, 'app.current_tenant_id', '');
      EXECUTE format('CREATE POLICY tenant_iso_ins ON %I FOR INSERT WITH CHECK (tenant_id = NULLIF(current_setting(%L,true),%L)::UUID)', t, 'app.current_tenant_id', '');
      EXECUTE format('CREATE POLICY tenant_iso_upd ON %I FOR UPDATE USING (tenant_id = NULLIF(current_setting(%L,true),%L)::UUID)', t, 'app.current_tenant_id', '');
      EXECUTE format('CREATE POLICY tenant_iso_del ON %I FOR DELETE USING (tenant_id = NULLIF(current_setting(%L,true),%L)::UUID)', t, 'app.current_tenant_id', '');
    END IF;
  END LOOP;
END $$;

-- استثناء tenants نفسها: تُقرأ عبر service_role فقط (لا RLS على الجذر):
-- ALTER TABLE tenants DISABLE ROW LEVEL SECURITY;
