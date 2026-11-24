## 0.3.4 (unreleased)

- Accept pg_duckdb 1.2.1 and later on installation and upgrade. The reference build uses pg_duckdb 1.2.2 with DuckDB 2.0.1. Operators choosing a newer engine must supply a compatible build of scanner v0.0.5.
- Build pg_duckdb with the pinned module version in both Git checkouts and source archives.
- Provide direct SQL upgrades from PGSTY 0.3.0 through 0.3.3. Existing 0.3.2 and 0.3.3 mirror registrations are preserved.
- Document how to flush the last source change before retiring the 0.3.0 worker's private WAL.

## 0.3.3 (2026-11-23)

- Use Moonlink `v0.3.0-pgsty.2`. A forced snapshot could report a source commit before Iceberg persisted it. Take a fresh snapshot with the updated worker before using it as a backup or migration boundary.
- Pin scanner `v0.0.5` to the same Moonlink revision. The direct update from 0.3.2 checks the loaded scanner and preserves existing mirror registrations.

## 0.3.2 (2026-11-23)

- Match the PG18 runtime package to the build headers. New mirror bindings require the generation returned by the create operation. Only the upgrade script imports historical registrations.
- Add direct updates from 0.3.0 and 0.3.1. Check the loaded scanner, bind existing mirrors and remove the old `load_files` entry point. The upgrade procedure includes a snapshot and comparison on the old worker before retaining its `_wal` offline.
- Bind each PG mirror to a Moonlink generation. Committed drops and interrupted creates can be reconciled after restart. A stale cleanup request cannot remove a replacement generation.
- Use scanner v0.0.4 with independent scan connections. Reads and snapshots that require freshness use the source server's WAL position.
- Close Moonlink's source connections when PostgreSQL enters smart shutdown so locally mirrored tables do not keep the postmaster waiting.
- Document the local scanner settings for a fresh installation. Ship a source archive with all pinned submodules and support building pg_duckdb from the unpacked archive.
- Upgrade the storage stack to Iceberg 0.11, Arrow/Parquet 58.4.2 and SQLx 0.9.1. The November 23 audit found zero vulnerability and unsoundness matches in all three lockfiles and default graphs. Strict default-graph checks report five, three and two unmaintained dependencies for pg_mooncake, Moonlink and FFI respectively. See [the dependency audit](docs/dependency-audit-2026-11-05.md).

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
  - Mirror drops use a pre-commit callback and an `sql_drop` event trigger.
  - Expanded 10-suite `pg_regress` regression harness (`setup`, `sanity`, `partitioned_table`, `partitioned_existing`, `drop`, `writes`, `identifiers`, `renames`, `freshness`, `data_directory`) and [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).
- Export `PGRX_PG_CONFIG_PATH` from `PG_CONFIG` across `Makefile` targets (`install`, `package`, `run`) and check `rust-postgres` revision parity in `scripts/check_versions.py`.
### Validation
- macOS ARM64: PG15.20, PG18.6 and PG19.0 builds with `bgworker`, SQL generation and pgrx package staging passed (identical SQL and control outputs across targets).
- The 0.3.1 integration script did not independently check that the postmaster had restarted between phases. Counts for the patched dependency graph are recorded under 0.3.2.

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
