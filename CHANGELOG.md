## 0.3.1 (2026-11-22)
### Changed
- Upgrade `pg_duckdb` to `1.2.1` / DuckDB `v2.0.1`, `duckdb_mooncake` to `v0.0.3`, and `moonlink` to `v0.3.0` (syncing upstream `Mooncake-Labs/moonlink` `v0.3-dev` @ `dcf999a9`, removing unused Delta/DataFusion/Kafka/OTEL/REST/GCS/WAL dependencies and upgrading Arrow/Parquet to `56`).
- Upgrade `pgrx`/`cargo-pgrx` to `0.20.0` and require Rust `1.99.1` or newer.
- Support PostgreSQL 15–19 source builds; remove PG14 following pgrx's support policy. PG18 remains the default target.
- Remove the unimplemented `mooncake.load_files` procedure and switch table identifier parsing to PostgreSQL's native `parse_ident` rules with unquoted `schema.table` Moonlink keys.
- Start the `moonlink` background worker at `BgWorkerStartTime::RecoveryFinished` (skipping standbys until promotion) inside a signal-isolated thread, restarting automatically on non-shutdown `SIGTERM`.
- Modernize `Dockerfile` and `.dockerignore` for submodule builds with local DuckDB extension staging and external `mooncake.data_directory`.
### Added
- Add the `pg19` Cargo feature and adapt `TableAmRoutine` callbacks (`src/table.rs`) and `planner_hook` (`src/mirror_writes.rs`) to PostgreSQL 19.
- Absorb upstream `pg_mooncake` 0.3 hardening (PR #207):
  - `mooncake.data_directory` postmaster GUC with directory validation and `moonlink.lock` exclusive locking (enabling `pg_basebackup` and standbys, portable on Linux and macOS).
  - `src/mirror_writes.rs`: `planner_hook` and `ProcessUtility_hook` guards rejecting `INSERT`, `UPDATE`, `DELETE`, `MERGE`, `TRUNCATE`, `COPY FROM`, `RENAME`, `SET SCHEMA`, `SET ACCESS METHOD`, `ATTACH PARTITION`, and `INHERIT` on mirror tables.
  - `src/drop_tracking.rs`: `object_access_hook` + transaction pre-commit drop tracking with `ROLLBACK TO SAVEPOINT` safety, `PREPARE TRANSACTION` rejection, 30s timeout warning fallback, and zero Moonlink contact when dropping regular tables.
  - Automatic RPC stream reconnection after Moonlink restarts, OID-checked rollback on failed `create_table`, password-redacted libpq connection errors, and `shared_preload_libraries` enforcement.
  - Expanded 10-suite `pg_regress` regression harness (`setup`, `sanity`, `partitioned_table`, `partitioned_existing`, `drop`, `writes`, `identifiers`, `renames`, `freshness`, `data_directory`) and [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).
- Export `PGRX_PG_CONFIG_PATH` from `PG_CONFIG` across `Makefile` targets (`install`, `package`, `run`) and check `rust-postgres` revision parity in `scripts/check_versions.py`.
### Validation
- macOS ARM64: PG15.20, PG18.6 and PG19.0 builds with `bgworker`, SQL generation and pgrx package staging passed (identical SQL and control outputs across targets).
- PostgreSQL 19.0 release build/package/install with `pg_duckdb 1.2.1` / DuckDB `v2.0.1` / `duckdb_mooncake v0.0.3` / `moonlink v0.3.0`: 10/10 `pg_regress` suites, 3/3 version-guard checks, 11 integration checkpoints, 2 fast-restart/cleanup checkpoints, and external `mooncake.data_directory` + `pg_basebackup -Ft` passed with zero leftover slots or server panics.
- Security audit: `moonlink` workspace drops from 27 to 0 vulnerability advisories; top-level `Cargo.lock` drops from 18 to 4 residual upstream-pinned vulnerabilities (`libsqlite3-sys`, `quick-xml`, `thrift`) after patching `openssl` (`0.10.82`), `rustix` (`1.1.6`), and `spin` (`0.9.9`). See [the dependency audit](docs/dependency-audit-2026-11-05.md#follow-up-v031--moonlink-v030-2026-11-22).

## 0.3.0 (2026-11-05)
### Changed
- Require pg_duckdb 1.2.0 / DuckDB 2.0.0 and pin pgrx/cargo-pgrx to 0.19.3.
- Use pg_mooncake's own release version; the previous 1.2.0 development version was not a pg_mooncake release.
- Pin duckdb_mooncake v0.0.2 and Moonlink v0.0.1 to their full Git commits, with matching RPC client/server sources.
- Build and package the local DuckDB extension alongside the PostgreSQL extension, enforcing Cargo lockfiles.
- Apply targeted Rust dependency security fixes; remaining advisories are recorded in the dependency audit.
### Fixed
- Adapt the DuckDB extension to DuckDB 2.0 APIs and exported Parquet statistics interfaces.
- Advance pending Moonlink snapshots after unrelated WAL progress and set full replica identity on existing leaf partitions.
- Reject incompatible pg_duckdb versions and report unimplemented file imports explicitly.
### Validation
- EL10 ARM64 / PostgreSQL 17: build, package, install, 3 SQL regressions, 3 version-guard checks, 11 integration checkpoints and 2 restart/cleanup checkpoints passed. See [the validation report](docs/pg-mooncake-0.3.0-validation.md).

## 0.1.2 (2025-02-11)
### Added
- Support NOT NULL constraint (#116)
### Fixed
- Manully load iceberg extension since it's not autoloadable in DuckDB v1.1.3
- Fix use-after-free bug when reading statistics
- Allow non-superusers to set maximum_memory and maximum_threads
- Fix ALTER TABLE ... SET ACCESS METHOD DEFAULT (#115)

## 0.1.1 (2025-01-29)
### Added
- Preload pg_mooncake in Docker image
- Add a command to reset DuckDB
- Expose GUCs to set maximum memory and threads DuckDB can use
### Fixed
- Fix DuckDB extension autoloading (#99)
- Fix query failure involving subplans (#100)
- Suppress unnecessary default value error on Postgres heap tables

## 0.1.0 (2025-01-10)
### Added
- Transactional INSERT, SELECT, UPDATE, DELETE, and COPY
- JOIN with regular Postgres heap tables
- Load Parquet, CSV, and JSON files into columnstore tables
- Read existing Iceberg and Delta Lake tables
- File statistics and skipping
- Write Delta Lake tables
