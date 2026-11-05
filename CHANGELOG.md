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
