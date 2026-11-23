DO $$
DECLARE
    installed_version text;
    scanner text;
BEGIN
    SELECT extversion INTO installed_version FROM pg_catalog.pg_extension WHERE extname = 'pg_duckdb';
    IF installed_version IS DISTINCT FROM '1.2.1' THEN
        RAISE EXCEPTION 'pg_mooncake 0.3.3 requires pg_duckdb 1.2.1; installed version is %', installed_version
            USING ERRCODE = 'feature_not_supported';
    END IF;
    PERFORM duckdb.install_extension('mooncake', COALESCE(NULLIF(current_setting('mooncake.extension_repository', true), ''), 'community'));
    PERFORM duckdb.load_extension('mooncake');
    EXECUTE $query$SELECT * FROM duckdb.query('SELECT extension_version FROM duckdb_extensions() WHERE extension_name = ''mooncake'' AND loaded')$query$ INTO scanner;
    IF scanner IS DISTINCT FROM 'v0.0.5' THEN
        RAISE EXCEPTION 'pg_mooncake 0.3.3 requires loaded DuckDB scanner v0.0.5; found %', scanner
            USING ERRCODE = 'feature_not_supported',
            HINT = 'Install the matching scanner into a fresh duckdb.extension_directory and reconnect.';
    END IF;
END
$$;
