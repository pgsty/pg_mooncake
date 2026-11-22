DO $$
DECLARE
    installed_version text;
BEGIN
    SELECT extversion INTO installed_version FROM pg_catalog.pg_extension WHERE extname = 'pg_duckdb';
    IF installed_version IS DISTINCT FROM '1.2.1' THEN
        RAISE EXCEPTION 'pg_mooncake 0.3.1 requires pg_duckdb 1.2.1; installed version is %', installed_version
            USING ERRCODE = 'feature_not_supported';
    END IF;
END
$$;

CREATE SCHEMA mooncake;

SELECT duckdb.install_extension(
    'mooncake',
    COALESCE(NULLIF(current_setting('mooncake.extension_repository', true), ''), 'community')
);
