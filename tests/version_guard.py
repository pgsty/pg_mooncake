#!/usr/bin/env python3
"""Verify exact pg_duckdb version enforcement in an empty disposable database."""

import psycopg


with psycopg.connect(autocommit=True) as conn:
    conn.execute("CREATE EXTENSION pg_duckdb")
    for version in ("1.1.3", "1.3.0"):
        # Simulate extension catalog drift inside a transaction; the failed
        # CREATE EXTENSION rolls back both the catalog edit and installation.
        try:
            with conn.transaction():
                conn.execute(
                    "UPDATE pg_extension SET extversion = %s WHERE extname = 'pg_duckdb'",
                    (version,),
                )
                conn.execute("CREATE EXTENSION pg_mooncake")
                raise AssertionError(f"pg_duckdb {version} must be rejected")
        except psycopg.errors.FeatureNotSupported as exc:
            assert "requires pg_duckdb 1.2.0" in str(exc), exc
        assert conn.execute("SELECT extversion FROM pg_extension WHERE extname = 'pg_duckdb'").fetchone() == ("1.2.0",)
        assert not conn.execute("SELECT 1 FROM pg_extension WHERE extname = 'pg_mooncake'").fetchall()
        print(f"PASS: pg_duckdb {version} rejected; catalog restored", flush=True)
    conn.execute("CREATE EXTENSION pg_mooncake")
    assert conn.execute("SELECT extversion FROM pg_extension WHERE extname = 'pg_mooncake'").fetchone() == ("1.2.0",)
    print("PASS: pg_mooncake 1.2.0 installed with pg_duckdb 1.2.0", flush=True)
    conn.execute("DROP EXTENSION pg_mooncake CASCADE")
    conn.execute("DROP EXTENSION pg_duckdb")
