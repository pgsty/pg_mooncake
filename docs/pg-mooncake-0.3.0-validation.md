# pg_mooncake 0.3.0: dependency tags and EL10 ARM64 / PostgreSQL 17 build

On November 5, 2026, pg_mooncake 0.3.0 built, packaged, installed and passed the
checks below in `mooncake-el10a-pg17`. This changes the extension's own version
from the former 1.2.0 development version to 0.3.0. Its pg_duckdb dependency
remains exactly 1.2.0.

## Published dependency tags

The following annotated tags were pushed to the pgsty forks and their remote
commit targets were verified. They identify the existing validated source;
neither dependency needed another code change for this release.

| Component | Tag | Commit |
| --- | --- | --- |
| [Moonlink](https://github.com/pgsty/moonlink/tree/v0.0.1) | `v0.0.1` | `b298ef7444890e3c8af5544e350232518bcfd8e5` |
| [duckdb_mooncake](https://github.com/pgsty/duckdb_mooncake/tree/v0.0.2) | `v0.0.2` | `49765a369ad88986916ce53c969ed2ce4ba66fac` |

The submodule commits and FFI client's `rev` remain fixed to these full SHAs.
`versions.json` now also records the tags. `make check-versions` validates the
tags against their commits, checks pg_mooncake and pg_duckdb versions separately,
and verifies pgrx/cargo-pgrx 0.19.3, the SQL guard and both DuckDB source revisions.

## Build and runtime results

The reused build container runs Rocky Linux 10.2 / aarch64, PostgreSQL 17.11,
Rust 1.99.0 and cargo-pgrx 0.19.3. This was an incremental release rebuild using
the existing native and Cargo dependency caches. The two dependency source
commits and all third-party Cargo package versions are unchanged from the
[earlier validation](el10a-pg17-validation.md).

| Check | Result |
| --- | --- |
| Local Git revisions, dependency tags and toolchain pins | Passed |
| Local source versus container | All 437 selected files match SHA-256: both dependency repositories' tracked files plus ten root build/test inputs |
| CMake / locked Rust FFI build target | Passed |
| pg_mooncake 0.3.0 release build and SQL generation | Passed |
| `make package` and `make install` for PG17 | Passed |
| Installed versus packaged library, control, SQL and DuckDB extension | All four match byte for byte |
| Generated control / SQL | `default_version = '0.3.0'`; `pg_mooncake--0.3.0.sql` requires pg_duckdb 1.2.0 |
| SQL regression suite | 3/3 passed |
| Version guard | Rejects pg_duckdb 1.1.3 and 1.3.0; installs pg_mooncake 0.3.0 with pg_duckdb 1.2.0 |
| Integration before restart | All 11 checkpoints passed |
| Fast restart, continued replication and cleanup | Both checkpoints passed |
| Runtime versions | pg_mooncake 0.3.0; pg_duckdb 1.2.0; DuckDB v2.0.0; loaded Mooncake extension v0.0.2 |
| Final cleanup | Zero Moonlink table registrations and zero replication slots |
| PostgreSQL collector log | No panic or segmentation-fault matches |

The integration suite covers initial copy, INSERT/UPDATE/DELETE, comparisons
against PostgreSQL heap tables, filters, joins, prepared statements, rollback,
snapshots, compaction, unrelated WAL progress, empty and partitioned tables,
and explicit rejection of unimplemented file imports. The unchanged Moonlink
unit tests were not repeated; the earlier run passed 58/58 table-handler tests.

## Reproduction and evidence

From the local Git checkout, initialize submodules, fetch the two tags as
described in the README, and run `make check-versions`. In the existing container:

```bash
cd /work/pg_mooncake
export RUSTUP_TOOLCHAIN=stable CARGO_BUILD_JOBS=4
export PGRX_PG_CONFIG_PATH=/usr/pgsql-17/bin/pg_config
make package PG_CONFIG="$PGRX_PG_CONFIG_PATH" PG_VERSION=pg17 JOBS=4 \
    PACKAGE_DIR="$PWD/target/release/pg_mooncake-0.3.0-pg17"
# Stop the disposable PostgreSQL instance before replacing its loaded library.
make install PG_CONFIG="$PGRX_PG_CONFIG_PATH" PG_VERSION=pg17 JOBS=4
# Start the instance again, with the settings in the earlier validation report.
export PATH=/usr/pgsql-17/bin:$PATH
export PGHOST=/work/socket PGPORT=55432 PGUSER=postgres
make test PG_CONFIG="$PGRX_PG_CONFIG_PATH" REGRESS_DB=mooncake_030_regress
createdb mooncake_030_guard
PGDATABASE=mooncake_030_guard /opt/mooncake-test/bin/python tests/version_guard.py
createdb mooncake_030_integration
PGDATABASE=mooncake_030_integration psql -c 'CREATE EXTENSION pg_mooncake CASCADE'
PGDATABASE=mooncake_030_integration /opt/mooncake-test/bin/python tests/integration.py --pg-major 17
runuser -u postgres -- pg_ctl -D /work/pgdata-final \
    -l /work/pgdata-final/server.log -m fast -w restart
PGDATABASE=mooncake_030_integration /opt/mooncake-test/bin/python tests/integration.py --pg-major 17 --after-restart
```

The container has no Git metadata. Source hashes were checked against the local
checkout, whose tag and commit checks passed. The source manifest checksum is
`95301d4fcce71d986b8a9ec49d2bdcc9841daa00fedff842f35a5d3aa7505e98`.
Python tests use the existing `/opt/mooncake-test` virtual environment with
psycopg 3.3.8; the system Python lacks psycopg.

The staged installation tree is
`/work/pg_mooncake/target/release/pg_mooncake-0.3.0-pg17/` in the container.
Logs and checksums are under `/work/logs/pg-mooncake-0.3.0/`, with local copies
in the ignored `target/validation/pg-mooncake-0.3.0/` directory. These include
`build-package.log`, `install.log`, `source-sha256.txt`, `source-compare.log`,
`package-compare.log`, `installed-sha256.txt`, `regression.log`,
`version-guard.log`, `integration.log`, `integration-restart.log`, and
`runtime-and-cleanup.json`.

This validates a fresh local-storage installation of 0.3.0. In-place upgrades
from 0.2.0 or the development 1.2.0 build are not provided or tested. The earlier
limits for S3, crash recovery, stress, TRUNCATE and newly added partitions still
apply. No RPM/DEB or container image was published. The
[dependency audit](dependency-audit-2026-11-05.md) remains applicable; this version
change does not remove its residual advisories.
