# pg_mooncake 1.2.0: EL10 ARM64 / PostgreSQL 17 validation

On November 5, 2026, the pinned source built, installed, packaged and passed the
functional and restart checks below on EL10 ARM64 / PostgreSQL 17. This run uses
pgrx 0.19.3 and the security updates recorded in the
[dependency audit](dependency-audit-2026-11-05.md).

## Inputs and pinning

| Component | Validated input |
| --- | --- |
| OS / architecture | Rocky Linux 10.2 / aarch64 |
| Container | `mooncake-el10a-pg17`, based on `pgsty/el10a:build` |
| Image ID | `sha256:f71371835a90e9dd99ea700c3d1385204e26d7d6d017fc3fb64ef46fd5df21c9` |
| PostgreSQL | 17.11; `/usr/pgsql-17/bin/pg_config` |
| Rust | 1.99.0 |
| pgrx and cargo-pgrx | Exactly 0.19.3 |
| pg_mooncake / pg_duckdb SQL versions | Both 1.2.0 |
| pg_duckdb | v1.2.0, `8756099e267c47f0b86c24de4cf995327f1f4279` |
| Both DuckDB source trees | v2.0.0, `d54cbbe3df17e8e5ce68312f483b4155836112aa` |
| duckdb_mooncake | `49765a369ad88986916ce53c969ed2ce4ba66fac`; component version v0.0.2 |
| Moonlink server and RPC client | `b298ef7444890e3c8af5544e350232518bcfd8e5`; component version 0.0.1 |

Git submodule entries and `versions.json` record immutable source revisions.
`make check-versions` verifies versions, the CLI, both DuckDB revisions and the
RPC client/server revision. pg_mooncake's version follows pg_duckdb; Moonlink and
the DuckDB extension retain their component versions with exact commit pins.

The PostgreSQL control-file dependency cannot express a version constraint, so
the bootstrap SQL explicitly requires pg_duckdb 1.2.0. This checks installation
compatibility; it does not prevent a later administrator from independently
upgrading pg_duckdb. Upgrade the pair and their matching DuckDB extension together.

Rust dependency resolution is fixed by the three Cargo lockfiles. The pgrx
commands pass `--cargo=--locked`; Corrosion builds the FFI crate with `LOCKED`.
The obsolete `pgrx_embed!` helper was removed for pgrx 0.19.3.

## Results

| Validation | Result |
| --- | --- |
| pg_duckdb source build and install | Passed |
| pg_mooncake release build and SQL generation with pgrx 0.19.3 | Passed |
| DuckDB Mooncake C++ / Rust FFI build | Passed |
| `make install` and `make package`, PG17 | Passed |
| Installed versus staged `.so`, control, SQL and DuckDB extension | All four match byte for byte |
| Dynamic C++ symbols against installed libduckdb | No unresolved symbols |
| Source version pins and cargo-pgrx version | Passed |
| SQL version enforcement | Rejects 1.1.3 and 1.3.0; accepts 1.2.0 |
| Existing SQL regression suite | 3/3 passed |
| Moonlink table-handler unit tests with updated dependencies | 58/58 passed |
| End-to-end test before restart | All 11 checkpoints passed |
| Normal fast restart and subsequent replication / cleanup | Both checkpoints passed |

The version-enforcement test temporarily changes extension catalog metadata
inside a transaction and confirms that the guard rejects installation. The
failed transaction restores the real 1.2.0 catalog entry. It does not attempt to
load binaries from an incompatible DuckDB release.

The integration test checks 10,000 initial rows, then another 5,000 inserts and
updates/deletes against a PostgreSQL heap oracle. Coverage includes numeric,
boolean, timestamps, Unicode, NULL, mixed-case names, filters, aggregates, self
joins, PostgreSQL joins, prepared statements, rollback, empty tables, partitioned
tables, snapshots, compaction, deletion handling and unsupported file imports.

Before restart, both tables had 13,638 rows, `sum(id) = 102302275`, and
`sum(amount) = 15338271.35`. Parquet files and Iceberg JSON/Avro metadata were
present. After restart, complete rows still matched; further INSERT/UPDATE/DELETE
and snapshot operations succeeded. Final cleanup left zero Moonlink table
registrations and zero replication slots.

The PostgreSQL collector log contains expected version/import rejection errors,
DROP cleanup lock timeouts and retries for objects already removed, and connection
termination from the requested fast restart. No panic or segmentation fault was
found. The existing cleanup retry behavior has not been redesigned.

## Reproduction

Install the native dependencies listed in the README and cargo-pgrx 0.19.3.
Initialize submodules, then run:

```bash
export RUSTUP_TOOLCHAIN=stable CARGO_BUILD_JOBS=4
export PGRX_PG_CONFIG_PATH=/usr/pgsql-17/bin/pg_config
rustc --version                       # validated: 1.99.0
make check-versions
make pg_duckdb PG_CONFIG="$PGRX_PG_CONFIG_PATH" PG_VERSION=pg17 JOBS=4
make install PG_CONFIG="$PGRX_PG_CONFIG_PATH" PG_VERSION=pg17 JOBS=4
make package PG_CONFIG="$PGRX_PG_CONFIG_PATH" PG_VERSION=pg17 JOBS=4
```

This container used a source archive without `.git`. For that archive build,
pg_duckdb's make invocation also supplied `PG_DUCKDB_VERSION=v1.2.0` and
`-o .git/modules/third_party/duckdb/HEAD`. Git-derived build metadata can be
unknown in archive builds; source pins and SQL/runtime versions were checked
separately. The local checkout passed the Git revision checks, and hashes of 22
selected build inputs and test sources matched the validated container.

The disposable cluster used UTF8 encoding, locale C, PGDATA `/work/pgdata-final`
and these settings:

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
mooncake.extension_repository = '/usr/pgsql-17/share/extension/pg_mooncake'
```

With the instance running and psycopg 3 available:

```bash
export PATH=/usr/pgsql-17/bin:$PATH
export PGHOST=/work/socket PGPORT=55432 PGUSER=postgres
make test PG_CONFIG="$PGRX_PG_CONFIG_PATH"
createdb mooncake_version_guard
PGDATABASE=mooncake_version_guard python3 tests/version_guard.py
createdb mooncake_integration
PGDATABASE=mooncake_integration psql -c 'CREATE EXTENSION pg_mooncake CASCADE'
PGDATABASE=mooncake_integration python3 tests/integration.py --pg-major 17
runuser -u postgres -- pg_ctl -D /work/pgdata-final \
    -l /work/pgdata-final/server.log -m fast restart
PGDATABASE=mooncake_integration python3 tests/integration.py --pg-major 17 --after-restart
CARGO_TARGET_DIR="$PWD/target" cargo test --locked \
    --manifest-path moonlink/Cargo.toml -p moonlink --lib table_handler::
```

## Evidence and limits

Logs are retained at `/work/logs` in the container and in the ignored local
directory `target/validation/el10a-pg17/`. The PostgreSQL collector logs are
copied there under `postgres-log/`; `server-final.log` records the collector
startup. Key evidence includes `regression-final.log`, `version-guard.log`,
`integration-final.log`, `integration-restart.log`, `moonlink-tests.log`,
`package-compare.log`, `installed-sha256.txt`, `cleanup-final.log`, and the audit
JSON files. The staged installation tree is
`/work/pg_mooncake/target/release/pg_mooncake-pg17/`.

This run validates a fresh local-storage installation. The earlier u24a/PG18
result used a different dependency set and remains a historical result. S3,
other platform combinations, in-place upgrade from pg_mooncake 0.2.0, crash
recovery, concurrent stress and the legacy Dockerfile were not validated here.
No 0.2.0-to-1.2.0 SQL migration, RPM/DEB release or container release is supplied.
`load_files` and TRUNCATE replication remain unsupported, and new partitions
still require full replica identity before writes. Residual dependency findings
are detailed in the audit report and must not be described as a clean scan.
