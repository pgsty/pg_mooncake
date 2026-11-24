#!/usr/bin/env python3
"""End-to-end tests against a disposable PG15–19 database (requires psycopg 3).

Run normally, restart PostgreSQL, then run with --after-restart. Connection
parameters come from libpq's PGHOST/PGPORT/PGUSER/PGDATABASE environment variables.
"""

import argparse
import json
import time

import psycopg


def main():
    if not __debug__:
        raise RuntimeError("Run the integration test with Python assertions enabled")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--after-restart", action="store_true")
    parser.add_argument("--pg-major", type=int, choices=range(15, 20), default=18)
    parser.add_argument("--pg-duckdb-version", help="expected version of the installed pg_duckdb package")
    parser.add_argument("--duckdb-version", default="v2.0.1", help="DuckDB version targeted by the test scanner")
    args = parser.parse_args()
    with psycopg.connect(autocommit=True, prepare_threshold=None) as conn:
        conn.execute("SET statement_timeout = '120s'")

        def rows(sql, params=None):
            return conn.execute(sql, params).fetchall()

        def compare(query="SELECT * FROM {} ORDER BY id"):
            expected = rows(query.format("mooncake_it.source"))
            actual = rows(query.format("mooncake_it.mirror"))
            assert actual == expected, (query, actual[:10], expected[:10])

        def checkpoint(label):
            print(f"PASS: {label}", flush=True)

        versions = rows("SELECT extversion FROM pg_extension WHERE extname = 'pg_duckdb'")
        assert len(versions) == 1, versions
        if args.pg_duckdb_version:
            assert versions == [(args.pg_duckdb_version,)], versions
        print(f"Testing pg_duckdb {versions[0][0]}", flush=True)
        assert int(rows("SHOW server_version_num")[0][0]) // 10000 == args.pg_major
        assert rows("SELECT extversion FROM pg_extension WHERE extname = 'pg_mooncake'") == [("0.3.4",)]
        if args.after_restart:
            if not rows("SELECT started < pg_postmaster_start_time() FROM mooncake_it.restart_check")[0][0]:
                raise RuntimeError("PostgreSQL must restart between the two integration phases")
            deadline = time.monotonic() + 90
            while True:
                try:
                    assert rows("SELECT mooncake._generation('mooncake_it.mirror') IS NOT NULL") == [(True,)]
                    break
                except psycopg.Error as exc:
                    if "failed to connect to moonlink" not in str(exc) or time.monotonic() >= deadline:
                        raise
                    time.sleep(0.25)
        assert rows("SELECT * FROM duckdb.query('SELECT version() AS version')") == [(args.duckdb_version,)]
        assert rows("""
            SELECT * FROM duckdb.query($$
                SELECT loaded, extension_version FROM duckdb_extensions() WHERE extension_name = 'mooncake'
            $$)
        """) == [(True, "v0.0.5")]

        if args.after_restart:
            compare()
            conn.execute("INSERT INTO mooncake_it.source VALUES (30001, 'restart', 123.45, true, '2030-01-01', NULL)")
            conn.execute("UPDATE mooncake_it.source SET amount = 999.99 WHERE id = 1")
            conn.execute("DELETE FROM mooncake_it.source WHERE id = 2")
            compare()
            conn.execute("CALL mooncake.create_snapshot('mooncake_it.mirror')")
            compare()
            checkpoint("restart recovery and continued INSERT/UPDATE/DELETE replication")
            conn.execute("DROP SCHEMA mooncake_it CASCADE")
            assert not rows("SELECT * FROM mooncake.list_tables() WHERE \"table\" LIKE 'mooncake_it.%'")
            checkpoint("drop removes Moonlink table registrations")
            return

        conn.execute("CREATE SCHEMA mooncake_it")
        conn.execute("CREATE TABLE mooncake_it.restart_check AS SELECT pg_postmaster_start_time() AS started")
        conn.execute("CREATE TABLE mooncake_it.ssi(id int PRIMARY KEY, val int)")
        conn.execute("INSERT INTO mooncake_it.ssi VALUES (1, 0), (2, 0)")
        create_mirror = "CALL mooncake.create_table('mooncake_it.ssi_m', 'mooncake_it.ssi')"
        try:
            with conn.transaction():
                conn.execute(create_mirror)
        except psycopg.errors.ActiveSqlTransaction:
            pass
        else:
            raise AssertionError("mirror creation inside a transaction must be rejected")
        conn.execute("SET default_transaction_read_only = on")
        try:
            conn.execute(create_mirror)
        except psycopg.errors.ReadOnlySqlTransaction:
            pass
        else:
            raise AssertionError("mirror creation in a read-only session must be rejected")
        finally:
            conn.execute("RESET default_transaction_read_only")
        assert rows("SELECT to_regclass('mooncake_it.ssi_m'), mooncake._generation('mooncake_it.ssi_m')") == [(None, None)]
        checkpoint("transaction and read-only guards leave both catalogs untouched")
        conn.execute(create_mirror)
        assert rows("""SELECT pronargdefaults FROM pg_catalog.pg_proc
                       WHERE oid = 'mooncake._bind_mirror(regclass,text)'::regprocedure""") == [(0,)]
        for invalid_generation in (None, "legacy"):
            try:
                conn.execute("SELECT mooncake._bind_mirror('mooncake_it.ssi_m', %s)", (invalid_generation,))
            except psycopg.errors.InvalidParameterValue:
                pass
            else:
                raise AssertionError("binding must require a PostgreSQL-managed generation")
        checkpoint("new bindings require the generation issued for a managed mirror")
        with psycopg.connect(autocommit=True) as other:
            for session in (conn, other):
                session.execute("BEGIN ISOLATION LEVEL SERIALIZABLE")
            conn.execute("SELECT val FROM mooncake_it.ssi WHERE id = 1")
            other.execute("SELECT val FROM mooncake_it.ssi WHERE id = 2")
            conn.execute("UPDATE mooncake_it.ssi SET val = 1 WHERE id = 2")
            conn.execute("DROP TABLE mooncake_it.ssi_m")
            other.execute("UPDATE mooncake_it.ssi SET val = 2 WHERE id = 1")
            other.execute("COMMIT")
            try:
                conn.execute("COMMIT")
            except psycopg.errors.SerializationFailure:
                pass
            else:
                raise AssertionError("expected the dropping transaction to fail serialization")
        conn.execute("CALL mooncake.create_snapshot('mooncake_it.ssi_m')")
        assert rows("SELECT * FROM mooncake_it.ssi_m ORDER BY id") == [(1, 2), (2, 0)]
        checkpoint("a serialization rollback preserves the original mirror and its replication")
        old_generation = rows("SELECT mooncake._generation('mooncake_it.ssi_m')")[0][0]
        conn.execute("DROP TABLE mooncake_it.ssi_m")
        conn.execute("CALL mooncake.create_table('mooncake_it.ssi_m', 'mooncake_it.ssi')")
        assert rows("SELECT mooncake._retire('mooncake_it.ssi_m', %s)", (old_generation,)) == [(True,)]
        assert rows("SELECT * FROM mooncake_it.ssi_m ORDER BY id") == [(1, 2), (2, 0)]
        conn.execute("VACUUM (ANALYZE) mooncake_it.ssi_m")
        conn.execute("DROP TABLE mooncake_it.ssi_m, mooncake_it.ssi")
        checkpoint("a delayed cleanup preserves a replacement mirror; VACUUM ANALYZE succeeds")
        conn.execute("""
            CREATE TABLE mooncake_it.source (
                id bigint PRIMARY KEY,
                category text,
                amount numeric(12,2),
                active boolean,
                happened_at timestamp,
                "MixedCase" text
            )
        """)
        conn.execute("""
            INSERT INTO mooncake_it.source
            SELECT i, 'group_' || (i % 7), i * 0.25, i % 2 = 0,
                   timestamp '2025-01-01' + i * interval '1 second',
                   CASE WHEN i % 3 = 0 THEN NULL ELSE '中文-' || i END
            FROM generate_series(1, 10000) i
        """)
        conn.execute("CALL mooncake.create_table('mooncake_it.mirror', 'mooncake_it.source')")
        compare()
        checkpoint("initial copy: 10000 rows, numeric, boolean, timestamp, Unicode, NULL, mixed-case column")

        plan = rows("EXPLAIN (FORMAT JSON) SELECT sum(amount) FROM mooncake_it.mirror")[0][0]
        assert "DuckDB" in json.dumps(plan), plan
        checkpoint("queries use the DuckDB execution plan")

        conn.execute("CALL mooncake.create_snapshot('mooncake_it.mirror')")
        conn.execute("""
            INSERT INTO mooncake_it.source
            SELECT i, 'new', i * 0.25, false, timestamp '2025-02-01', '新数据'
            FROM generate_series(10001, 15000) i
        """)
        conn.execute("UPDATE mooncake_it.source SET amount = -amount, category = 'changed' WHERE id % 5 = 0")
        conn.execute("DELETE FROM mooncake_it.source WHERE id % 11 = 0")
        compare()
        checkpoint("INSERT/UPDATE/DELETE across existing files and new data")

        for query in [
            "SELECT count(*) FROM {}",
            "SELECT count(amount), min(id), max(id), min(amount), max(amount) FROM {}",
            "SELECT count(*), sum(id), sum(amount) FROM {}",
            "SELECT id, amount FROM {} WHERE id < 12 OR id > 14990 ORDER BY id",
            "SELECT id FROM {} WHERE id BETWEEN 7000 AND 7100 AND amount < 0 ORDER BY id",
            "SELECT id FROM {} WHERE id > 999999 ORDER BY id",
            'SELECT id, "MixedCase" FROM {} WHERE "MixedCase" IS NULL ORDER BY id',
            "SELECT category, count(*), sum(amount) FROM {} GROUP BY category ORDER BY category",
            "SELECT id FROM {} WHERE id IN (1, 2, 100, 10000, 14999) ORDER BY id",
            "SELECT a.id, b.id FROM {0} a JOIN {0} b ON a.id = b.id + 1 WHERE a.id < 20 ORDER BY a.id",
            "SELECT a.id, b.id FROM {} a JOIN mooncake_it.lookup b ON a.id = b.id ORDER BY a.id",
        ]:
            if "lookup" in query:
                conn.execute("CREATE TABLE mooncake_it.lookup AS SELECT generate_series(1,100) AS id")
            compare(query)
        checkpoint("projection, aggregate, range/OR/IN/NULL/empty filters, and PostgreSQL table join")

        conn.execute("PREPARE mc_prepared(bigint) AS SELECT id, amount FROM mooncake_it.mirror WHERE id < $1 ORDER BY id")
        for limit in (10, 100, 10):
            assert rows(f"EXECUTE mc_prepared({limit})") == rows(
                "SELECT id, amount FROM mooncake_it.source WHERE id < %s ORDER BY id", (limit,)
            )
        conn.execute("UPDATE mooncake_it.source SET amount = 432.10 WHERE id = 1")
        assert rows("EXECUTE mc_prepared(10)") == rows("SELECT id, amount FROM mooncake_it.source WHERE id < 10 ORDER BY id")
        conn.execute("DEALLOCATE mc_prepared")
        checkpoint("prepared statements and freshness after repeated execution")

        conn.execute("BEGIN")
        conn.execute("INSERT INTO mooncake_it.source VALUES (20000, 'rollback', 1, false, NULL, NULL)")
        conn.execute("ROLLBACK")
        compare()
        checkpoint("rolled-back source changes stay absent")

        conn.execute("CALL mooncake.create_snapshot('mooncake_it.mirror')")
        compare()
        conn.execute("CALL mooncake.optimize_table('mooncake_it.mirror', 'full')")
        conn.execute("CALL mooncake.create_snapshot('mooncake_it.mirror')")
        compare()
        metadata = rows("SELECT \"table\", flush_lsn IS NOT NULL, iceberg_warehouse_location FROM mooncake.list_tables()")
        assert any(table == "mooncake_it.mirror" and flushed and location for table, flushed, location in metadata), metadata
        checkpoint("Iceberg snapshots, full compaction, persisted deletion vectors, and table metadata")

        # The session's WAL position advances even when a different table is
        # changed. Snapshot creation must still persist this table and return.
        conn.execute("INSERT INTO mooncake_it.source VALUES (20001, 'snapshot', 1, false, NULL, NULL)")
        conn.execute("INSERT INTO mooncake_it.lookup VALUES (20001)")
        conn.execute("CALL mooncake.create_snapshot('mooncake_it.mirror')")
        compare()
        checkpoint("snapshot after a commit to an unrelated table")

        conn.execute("CREATE TABLE mooncake_it.empty_source (id int PRIMARY KEY)")
        conn.execute("CALL mooncake.create_table('mooncake_it.empty_mirror', 'mooncake_it.empty_source')")
        assert rows("SELECT count(*) FROM mooncake_it.empty_mirror") == [(0,)]
        conn.execute("INSERT INTO mooncake_it.empty_source VALUES (1)")
        assert rows("SELECT * FROM mooncake_it.empty_mirror") == [(1,)]
        conn.execute("DELETE FROM mooncake_it.empty_source")
        assert rows("SELECT count(*) FROM mooncake_it.empty_mirror") == [(0,)]
        conn.execute("DROP TABLE mooncake_it.empty_mirror, mooncake_it.empty_source")
        checkpoint("empty table, first insert, and deleting all rows")

        conn.execute("CREATE TABLE mooncake_it.partition_source (id int PRIMARY KEY, label text) PARTITION BY RANGE (id)")
        conn.execute("CREATE TABLE mooncake_it.p0 PARTITION OF mooncake_it.partition_source FOR VALUES FROM (0) TO (50)")
        conn.execute("CREATE TABLE mooncake_it.p1 PARTITION OF mooncake_it.partition_source FOR VALUES FROM (50) TO (100)")
        conn.execute("CALL mooncake.create_table('mooncake_it.partition_mirror', 'mooncake_it.partition_source')")
        conn.execute("INSERT INTO mooncake_it.partition_source SELECT i, 'row-' || i FROM generate_series(0, 99) i")
        conn.execute("UPDATE mooncake_it.partition_source SET label = 'changed' WHERE id % 5 = 0")
        conn.execute("DELETE FROM mooncake_it.partition_source WHERE id > 90")
        for query in [
            "SELECT * FROM {} ORDER BY id",
            "SELECT count(*) FROM {} WHERE id < 25",
            "SELECT count(*) FROM {} WHERE id < 75",
            "SELECT count(*) FROM {} WHERE id < 25 OR id > 75",
        ]:
            assert rows(query.format("mooncake_it.partition_mirror")) == rows(query.format("mooncake_it.partition_source"))
        conn.execute("INSERT INTO mooncake_it.lookup VALUES (20002)")
        conn.execute("CALL mooncake.create_snapshot('mooncake_it.partition_mirror')")
        assert rows("SELECT * FROM mooncake_it.partition_mirror ORDER BY id") == rows(
            "SELECT * FROM mooncake_it.partition_source ORDER BY id"
        )
        conn.execute("DROP TABLE mooncake_it.partition_mirror, mooncake_it.partition_source")
        checkpoint("partition-root INSERT/UPDATE/DELETE, filtered counts, and snapshot after unrelated WAL")

        assert not rows(
            "SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace "
            "WHERE n.nspname = 'mooncake' AND p.proname = 'load_files'"
        )
        checkpoint("unimplemented mooncake.load_files procedure is removed")
        print("Restart PostgreSQL, then run this script with --after-restart.", flush=True)


if __name__ == "__main__":
    main()
