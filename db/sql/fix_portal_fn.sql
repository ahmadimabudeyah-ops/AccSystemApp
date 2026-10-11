-- portal_resolve: الدالة الوحيدة المتجاوزة لـ RLS (محدودة بما يمنحه التوكن).
CREATE OR REPLACE FUNCTION portal_resolve(p_hash TEXT)
RETURNS TABLE(tenant_id UUID, party_id UUID, scope TEXT, expires_at TIMESTAMPTZ)
LANGUAGE sql SECURITY DEFINER STABLE AS $$
  SELECT tenant_id, party_id, scope, expires_at FROM portal_tokens
  WHERE token_hash = p_hash AND is_deleted = FALSE;
$$;
REVOKE ALL ON FUNCTION portal_resolve(TEXT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION portal_resolve(TEXT) TO accounting;
