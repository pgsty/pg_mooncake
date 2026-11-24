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

CREATE TABLE mooncake.mirror_registrations (
    relid oid NOT NULL,
    mirror_name text NOT NULL,
    generation text NOT NULL,
    dropped_xid xid8,
    PRIMARY KEY (mirror_name, generation)
);
CREATE UNIQUE INDEX ON mooncake.mirror_registrations (relid) WHERE dropped_xid IS NULL;
REVOKE ALL ON mooncake.mirror_registrations FROM PUBLIC;

CREATE FUNCTION mooncake._generation(text) RETURNS text
LANGUAGE C STRICT AS 'MODULE_PATHNAME', 'mirror_generation_wrapper';
CREATE FUNCTION mooncake._retire(text, text) RETURNS boolean
LANGUAGE C STRICT AS 'MODULE_PATHNAME', 'retire_generation_wrapper';
CREATE FUNCTION mooncake._managed_registrations() RETURNS TABLE (mirror_name text, generation text)
LANGUAGE C AS 'MODULE_PATHNAME', 'managed_registrations_wrapper';
REVOKE ALL ON FUNCTION mooncake._generation(text), mooncake._retire(text, text), mooncake._managed_registrations() FROM PUBLIC;

CREATE FUNCTION mooncake._bind_mirror(target regclass, expected text) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
DECLARE
    key text;
BEGIN
    IF expected IS NULL OR expected NOT LIKE 'pg-%' THEN
        RAISE EXCEPTION 'binding requires the generation returned by mooncake.create_table'
            USING ERRCODE = 'invalid_parameter_value';
    END IF;
    SELECT n.nspname || '.' || c.relname INTO STRICT key
      FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
      JOIN pg_am am ON am.oid = c.relam
     WHERE c.oid = target AND am.amname = 'mooncake'
       AND pg_has_role(session_user, c.relowner, 'USAGE');
    IF mooncake._generation(key) IS DISTINCT FROM expected THEN
        RAISE EXCEPTION 'mirror % has no matching Moonlink registration', key;
    END IF;
    INSERT INTO mooncake.mirror_registrations VALUES (target, key, expected, NULL);
END
$$;

INSERT INTO mooncake.mirror_registrations (relid, mirror_name, generation)
SELECT relid, mirror_name, mooncake._generation(mirror_name)
FROM (
    SELECT c.oid AS relid, n.nspname || '.' || c.relname AS mirror_name
    FROM pg_catalog.pg_class c
    JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
    JOIN pg_catalog.pg_am am ON am.oid = c.relam
    WHERE am.amname = 'mooncake' AND c.relkind = 'r'
) AS existing_mirrors;

CREATE OR REPLACE FUNCTION mooncake_drop_trigger() RETURNS event_trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
BEGIN
    IF to_regclass('mooncake.mirror_registrations') IS NULL THEN
        RETURN;
    END IF;
    UPDATE mooncake.mirror_registrations SET dropped_xid = pg_current_xact_id()
     WHERE dropped_xid IS NULL AND relid IN (
         SELECT objid FROM pg_event_trigger_dropped_objects()
          WHERE classid = 'pg_class'::regclass AND objsubid = 0 AND object_type = 'table'
     );
END
$$;
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_event_trigger WHERE evtname = 'mooncake_drop_trigger') THEN
        CREATE EVENT TRIGGER mooncake_drop_trigger ON sql_drop EXECUTE FUNCTION mooncake_drop_trigger();
    END IF;
END
$$;
ALTER EVENT TRIGGER mooncake_drop_trigger ENABLE ALWAYS;

CREATE FUNCTION mooncake._reconcile_drops(only_name text DEFAULT NULL) RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
DECLARE
    registration record;
BEGIN
    FOR registration IN SELECT mirror_name, generation FROM mooncake.mirror_registrations
        WHERE dropped_xid IS NOT NULL AND dropped_xid IS DISTINCT FROM pg_current_xact_id_if_assigned()
          AND (only_name IS NULL OR mirror_name = only_name)
        ORDER BY mirror_name, generation FOR UPDATE SKIP LOCKED
    LOOP
        IF mooncake._retire(registration.mirror_name, registration.generation) THEN
            DELETE FROM mooncake.mirror_registrations
             WHERE mirror_name = registration.mirror_name AND generation = registration.generation;
        END IF;
    END LOOP;
END
$$;

CREATE FUNCTION mooncake._reconcile_creates() RETURNS void
LANGUAGE plpgsql SET search_path = pg_catalog, pg_temp AS $$
DECLARE
    orphan record;
BEGIN
    FOR orphan IN
        SELECT remote.* FROM mooncake._managed_registrations() AS remote
         WHERE NOT EXISTS (SELECT FROM mooncake.mirror_registrations local
             WHERE (local.mirror_name, local.generation) = (remote.mirror_name, remote.generation))
    LOOP
        IF pg_try_advisory_xact_lock(hashtextextended('pg_mooncake/' || orphan.mirror_name, 0)) THEN
            IF NOT EXISTS (SELECT FROM mooncake.mirror_registrations local
                WHERE (local.mirror_name, local.generation) = (orphan.mirror_name, orphan.generation)) THEN
                PERFORM mooncake._retire(orphan.mirror_name, orphan.generation);
            END IF;
        END IF;
    END LOOP;
END
$$;
REVOKE ALL ON FUNCTION mooncake._reconcile_creates() FROM PUBLIC;

DO $$
BEGIN
    IF to_regprocedure('mooncake.load_files(text,text[])') IS NOT NULL THEN
        DROP PROCEDURE mooncake.load_files(text, text[]);
    END IF;
END
$$;
