# DuckDB 2.0 validation on u24a / PostgreSQL 18

This is the historical validation of commit `24a5018a157a8e05b69d6c7492522164622535c9`
with pgrx 0.16.1 and pg_mooncake 0.2.0. Check out that commit and initialize its
submodules to reproduce it. The subsequent pgrx 0.19.3 / pg_mooncake 1.2.0 update
is covered by the [EL10 / PostgreSQL 17 report](el10a-pg17-validation.md);
the newer dependency set has not been revalidated on u24a in this round.

The updated source builds, installs and runs with pg_duckdb 1.2.0 and DuckDB
2.0.0 on Ubuntu 24.04 ARM64. The validation covers initial replication, continued
INSERT/UPDATE/DELETE replication, queries, snapshots, compaction, restart recovery
and cleanup. Rebuilding the old source without API changes is insufficient.

## Validated inputs

| Component | Version or revision |
| --- | --- |
| Container | `mooncake-u24a-pg18`, based on `pgsty/u24a:build` |
| Image ID | `sha256:a4fa63b43bba30fbab4d71d85bcff43a4b9bc95a539e7d6e15af4201c19c7b89` |
| OS / architecture | Ubuntu 24.04.5 / aarch64 |
| PostgreSQL | 18.6, `18.6-1.pgdg24.04+2` |
| Rust / cargo-pgrx | 1.99.0 / 0.16.1 |
| pg_mooncake | SQL extension version 0.2.0; changes based on `b7c67e0a08c11c45c4ac5cb5ec5ef231779c1db4` |
| pg_duckdb | 1.2.0, `8756099e267c47f0b86c24de4cf995327f1f4279` |
| DuckDB, in both submodules | 2.0.0, `d54cbbe3df17e8e5ce68312f483b4155836112aa` |
| [pgsty/duckdb_mooncake](https://github.com/pgsty/duckdb_mooncake/commit/1145d9141471bcef5ad7965671c2da454263b3c4) | `1145d9141471bcef5ad7965671c2da454263b3c4`; extension version v0.0.2 |
| [pgsty/moonlink](https://github.com/pgsty/moonlink/commit/b4a85e989ccd939ebe4f42918299b9f23a7c1d4c) | `b4a85e989ccd939ebe4f42918299b9f23a7c1d4c`, based on `c1a99ef01af878a5ffa77d1019ef4833a7907410` |

The Moonlink RPC client remains pinned to that server base revision; the fixes
do not change the protocol. The top-level Cargo.lock records resolved Rust
dependencies. The C++ build uses nanoarrow 0.7, Corrosion v0.5 and, when a suitable
system library is absent, CRoaring v5.5.4 with a checked SHA256.

## Changes required

- Adapt DuckDB storage registration, catalog identifiers, Arrow schema conversion,
  table functions, file lists and filters to the 2.0 APIs.
- Read Parquet statistics through the exported multi-file reader interface. The
  former direct ParquetReader dependency uses symbols that are no longer exported.
  Construct statistics entries outside the object-cache mutex to avoid reentrant
  cache locking while Parquet metadata is loaded.
- Build and install the matching C++ extension in a local extension repository;
  include it in the staged package alongside the PostgreSQL extension. Configure
  its location through `mooncake.extension_repository`.
- Fix Moonlink snapshot requests when the database WAL position advances because
  of an unrelated table. Replication progress must allow older committed data to
  flush and must notify requests even when no new commit arrives for that table.
- Set `REPLICA IDENTITY FULL` on existing source partitions as well as their root.
  Setting it only on the root left incomplete old rows in partition UPDATE events
  and caused a replication-worker panic.
- Return SQLSTATE `0A000` for `mooncake.load_files`: the bundled server's import
  handler is a no-op and previously reported success without ingesting anything.

## Results

| Check | Result |
| --- | --- |
| pg_duckdb, DuckDB Mooncake and pg_mooncake build/install | Passed |
| C++ extension symbol resolution against installed libduckdb | Passed; no unresolved symbols |
| Staged package | Contains both extensions; their binaries match installed files byte for byte |
| Existing SQL regression suite | 3/3 passed: setup, sanity, partitioned_table |
| Integration test before restart | All 11 checkpoints passed |
| Integration test after normal fast restart | Both checkpoints passed |
| Moonlink table-handler unit tests | 58 passed, 0 failed |

The integration test starts with 10,000 rows, adds 5,000 more and compares complete
rows with PostgreSQL heap tables after updates and deletes. It covers numeric,
boolean, timestamp, Unicode, NULL and mixed-case column names; range, OR, IN and
empty filters; aggregates; self joins and joins to PostgreSQL tables; prepared
statement freshness; rollback; empty tables; partitioned tables; and explicit
rejection of unsupported file imports. EXPLAIN confirms DuckDB execution.

Before restart, the source and mirror both had 13,638 rows, `sum(id) = 102302275`
and `sum(amount) = 15338271.35`. Parquet files, Iceberg JSON metadata and Avro
manifests were present on disk. After restart, full row comparison and further
INSERT/UPDATE/DELETE operations passed. Final cleanup left no Moonlink table
registrations or replication slots.

The two added snapshot tests timed out against the old implementation and passed
with the fix. The partition UPDATE failure was reproduced before the replica
identity fix and passed in the final integration run. An early exploratory
partition regression returned zero rows once; ten subsequent create/drop cycles
and the final clean-instance regression passed. This is not a concurrency or
stress-test qualification.

The final instance log contained no panic or segmentation fault. DROP cleanup
can log upstream lock timeouts and background retries; cleanup completed in the
validated run. These retries have not been redesigned here.

## Reproduction

Use a disposable PostgreSQL instance and the source dependencies in the README.
The validation used `/usr/lib/postgresql/18/bin/pg_config`, six build jobs and
`cargo-pgrx` 0.16.1. The image's installed `stable` toolchain reported Rust 1.99.0;
the repository also pins 1.99.0 in `rust-toolchain.toml`.

```bash
git submodule update --init --recursive
export PATH=/opt/pgrx-0.16.1/bin:$PATH
export RUSTUP_TOOLCHAIN=stable CARGO_BUILD_JOBS=6
export PGRX_PG_CONFIG_PATH=/usr/lib/postgresql/18/bin/pg_config
make pg_duckdb PG_CONFIG="$PGRX_PG_CONFIG_PATH" JOBS=6
make install PG_CONFIG="$PGRX_PG_CONFIG_PATH" PG_VERSION=pg18 JOBS=6
make package PG_CONFIG="$PGRX_PG_CONFIG_PATH" PG_VERSION=pg18 JOBS=6
```

The test container received a source archive without Git metadata. Its pg_duckdb
build additionally used `PG_DUCKDB_VERSION=v1.2.0` and
`-o .git/modules/third_party/duckdb/HEAD`. Such archive builds can leave Git-derived
version/source fields unknown; SQL extension versions, DuckDB's runtime version
and the source revisions above were checked separately.

The final instance used PGDATA `/work/pgdata-final` and this configuration:

```ini
shared_preload_libraries = 'pg_duckdb,pg_mooncake'
wal_level = logical
max_replication_slots = 32
max_wal_senders = 32
max_worker_processes = 16
port = 55432
listen_addresses = ''
unix_socket_directories = '/work/socket'
duckdb.allow_community_extensions = true
duckdb.allow_unsigned_extensions = true
mooncake.extension_repository = '/usr/share/postgresql/18/extension/pg_mooncake'
```

With the instance running and the disposable integration database initialized:

```bash
export PGHOST=/work/socket PGPORT=55432 PGUSER=postgres
make test PG_CONFIG="$PGRX_PG_CONFIG_PATH"
createdb mooncake_integration
PGDATABASE=mooncake_integration psql -c 'CREATE EXTENSION pg_mooncake CASCADE'
PGDATABASE=mooncake_integration python3 tests/integration.py
runuser -u postgres -- /usr/lib/postgresql/18/bin/pg_ctl \
    -D /work/pgdata-final -l /work/pgdata-final/server.log -m fast restart
PGDATABASE=mooncake_integration python3 tests/integration.py --after-restart
CARGO_TARGET_DIR="$PWD/target" cargo test \
    --manifest-path moonlink/Cargo.toml -p moonlink --lib table_handler::
LD_PRELOAD=/usr/lib/postgresql/18/lib/libduckdb.so ldd -r \
    /usr/share/postgresql/18/extension/pg_mooncake/v2.0.0/linux_arm64/mooncake.duckdb_extension
```

## Evidence and limits

Build/test logs are retained in the container under `/work/logs` and copied to
the ignored local directory `target/validation/u24a-pg18/`. The final PostgreSQL
log is copied there as `server-final.log`. Key files are `final-install.log`,
`package.log`, `regression-final.log`, `integration-final.log`,
`integration-restart.log`, `moonlink-snapshot-before.log`,
`moonlink-snapshot-after.log`, `versions-data-before-restart.log`,
`storage-files.txt` and `installed-sha256.txt`. Logs and binaries are not committed.
The staged installation tree remains in the container at
`/work/pg_mooncake/target/release/pg_mooncake-pg18/`.

This validates fresh installation with local storage on u24a / PostgreSQL 18.
It does not validate el10a, other PostgreSQL versions or architectures, S3,
in-place upgrades of existing data, crash recovery, or the legacy Dockerfile and
upstream Docker image. No RPM/DEB package or release has been published.
`load_files` is unimplemented; TRUNCATE replication is outside the supported
scope. Partitions added after mirror creation need `REPLICA IDENTITY FULL`
before receiving writes; automatic handling of later partition DDL is not
implemented by this change.
