-- Portal service role: owns ONLY portal_resolve (BYPASSRLS inside the function).
-- The function returns at most the single row matching an unguessable token hash.
DO $$ BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'portal_svc') THEN
    CREATE ROLE portal_svc NOLOGIN BYPASSRLS;
  END IF;
END $$;
ALTER FUNCTION portal_resolve(TEXT) OWNER TO portal_svc;
REVOKE ALL ON FUNCTION portal_resolve(TEXT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION portal_resolve(TEXT) TO accounting;
GRANT SELECT ON portal_tokens TO portal_svc;
