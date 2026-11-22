-- moonlink's directory is set at server start; the default is relative to the data directory.
SELECT name, setting <> '' AS configured, context FROM pg_settings WHERE name = 'mooncake.data_directory' \gset
\echo :name :configured :context
SET mooncake.data_directory = '/tmp';
