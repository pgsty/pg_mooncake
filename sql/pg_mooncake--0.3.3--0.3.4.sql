DO $$
DECLARE
    minimum_version CONSTANT text := '1.2.1';
    installed_version text;
    parts text[];
    scanner text;
BEGIN
    SELECT extversion INTO installed_version FROM pg_catalog.pg_extension WHERE extname = 'pg_duckdb';
    -- Compare numeric major/minor/patch fields. At the same core version a prerelease
    -- sorts before the final release. Build metadata has no effect on precedence.
    parts := regexp_match(installed_version,
        '^(0|[1-9][0-9]*)[.](0|[1-9][0-9]*)[.](0|[1-9][0-9]*)'
        '(-[0-9A-Za-z-]+(?:[.][0-9A-Za-z-]+)*)?(?:[+][0-9A-Za-z-]+(?:[.][0-9A-Za-z-]+)*)?$');
    IF parts IS NULL OR
       (parts[1:3]::numeric[], parts[4] IS NULL) < (string_to_array(minimum_version, '.')::numeric[], true) THEN
        RAISE EXCEPTION 'pg_mooncake requires pg_duckdb % or newer (installed version: %)', minimum_version, installed_version
            USING ERRCODE = 'feature_not_supported';
    END IF;
    PERFORM duckdb.install_extension('mooncake', COALESCE(NULLIF(current_setting('mooncake.extension_repository', true), ''), 'community'));
    PERFORM duckdb.load_extension('mooncake');
    EXECUTE $query$SELECT * FROM duckdb.query('SELECT extension_version FROM duckdb_extensions() WHERE extension_name = ''mooncake'' AND loaded')$query$ INTO scanner;
    IF scanner IS DISTINCT FROM 'v0.0.5' THEN
        RAISE EXCEPTION 'pg_mooncake 0.3.4 requires loaded DuckDB scanner v0.0.5; found %', scanner
            USING ERRCODE = 'feature_not_supported',
            HINT = 'Install the matching scanner into a fresh duckdb.extension_directory and reconnect.';
    END IF;
END
$$;
