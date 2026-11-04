CREATE SCHEMA mooncake;

SELECT duckdb.install_extension(
    'mooncake',
    COALESCE(NULLIF(current_setting('mooncake.extension_repository', true), ''), 'community')
);
