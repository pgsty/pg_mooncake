#!/usr/bin/env python3
"""Exercise the pg_duckdb runtime minimum in an empty disposable database."""

import psycopg


if not __debug__:
    raise RuntimeError("Run the version guard with Python assertions enabled")

with psycopg.connect(autocommit=True) as conn:
    conn.execute("CREATE EXTENSION pg_duckdb")
    lookup = "SELECT extversion FROM pg_extension WHERE extname = %s"
    installed = conn.execute(lookup, ("pg_duckdb",)).fetchone()[0]
    cases = (
        ("1.1.99", False), ("1.2.0", False), ("1.2.1-rc.1+build.2", False),
        ("devel", False), ("1.2", False),
        ("1.2.1", True), ("1.2.1+build.2", True), ("1.2.2-rc.1", True),
        ("1.2.2", True), ("1.2.10", True), ("1.10.0", True), ("2.0.0", True),
    )
    for version, accepted in cases:
        # Exercise the SQL check with the real binary; roll back the catalog edit
        # and CREATE EXTENSION even when the candidate version is accepted.
        try:
            with conn.transaction(force_rollback=True):
                conn.execute("UPDATE pg_extension SET extversion = %s WHERE extname = 'pg_duckdb'", (version,))
                conn.execute("CREATE EXTENSION pg_mooncake")
        except psycopg.errors.FeatureNotSupported as exc:
            assert not accepted and "requires pg_duckdb 1.2.1 or newer" in str(exc), exc
        else:
            assert accepted, f"pg_duckdb {version} should have been rejected"
        assert conn.execute(lookup, ("pg_duckdb",)).fetchone() == (installed,)
        assert conn.execute(lookup, ("pg_mooncake",)).fetchone() is None
        print(f"PASS: catalog version {version} {'accepted' if accepted else 'rejected'}", flush=True)
    conn.execute("CREATE EXTENSION pg_mooncake")
    assert conn.execute(lookup, ("pg_mooncake",)).fetchone() == ("0.3.4",)
    print(f"PASS: pg_mooncake 0.3.4 installed with pg_duckdb {installed}", flush=True)
    conn.execute("DROP EXTENSION pg_mooncake CASCADE")
    conn.execute("DROP EXTENSION pg_duckdb")
