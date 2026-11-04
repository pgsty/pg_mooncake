<div align=center>
<h1 align=center>pg_mooncake 🥮</h1>
<h4 align=center>Real-time analytics on Postgres tables</h4>

[![][docs-shield]][docs-link]
[![][license-shield]][license-link]
[![][slack-shield]][slack-link]
[![][x-shield]][x-link]
</div>

## Overview

**pg_mooncake** is a Postgres extension that creates a columnstore mirror of your Postgres tables in [Iceberg][iceberg-link], enabling fast analytics queries with sub-second freshness:
- **Real-time ingestion** powered by [moonlink][moonlink-link] for streaming and batched INSERT/UPDATE/DELETE.
- **Fast analytics** accelerated by [DuckDB][pgduckdb-link], ranking top 10 on [ClickBench][clickbench-link].
- **Postgres-native** allowing you to query a columnstore table just like a regular Postgres table.
- **Iceberg-native** making your data readily accessible by other query engines.

## Installation

### Option 1: Docker

The upstream image below is a legacy distribution. It does not contain this
fork's DuckDB 2.0 compatibility changes; use the source build for those changes.
```bash
docker run --name mooncake --rm -e POSTGRES_PASSWORD=password mooncakelabs/pg_mooncake
```

This will start Postgres with pg_mooncake preinstalled. You can then connect to it using `psql` with the default user `postgres`:
```bash
docker exec -it mooncake psql -U postgres
```

### Option 2: From Source

This fork's **pg_mooncake 1.2.0** requires **pg_duckdb 1.2.0 and DuckDB 2.0.0**.
Its release version follows pg_duckdb. `versions.json` records the exact submodule
commits, both DuckDB source revisions, and pgrx/cargo-pgrx **0.19.3**. Builds check
these pins and use Cargo lockfiles; extension creation rejects a different
installed pg_duckdb version.
The DuckDB Mooncake extension must be rebuilt along with this upgrade: a binary
compiled for DuckDB 1.4.x cannot be loaded by DuckDB 2.0.

To build pg_mooncake, first install [Rust][rust-install], [pgrx][pgrx-install], and [the build tools for DuckDB][duckdb-install].
On Ubuntu 24.04, the additional native dependencies are:

```bash
sudo apt-get install build-essential cmake ninja-build pkg-config libclang-dev \
    libssl-dev libcurl4-openssl-dev liblz4-dev protobuf-compiler postgresql-server-dev-18
cargo install --locked cargo-pgrx --version 0.19.3
```

For EL10 / PostgreSQL 17, the equivalent native dependencies are:

```bash
sudo dnf install gcc gcc-c++ make cmake ninja-build pkgconf-pkg-config \
    clang-devel llvm-devel openssl-devel libcurl-devel lz4-devel \
    protobuf-compiler python3-pip postgresql17-devel
```

Then, clone the repository:
```bash
git clone --recurse-submodules https://github.com/pgsty/pg_mooncake.git
cd pg_mooncake
```

To build and install for PostgreSQL 17 on EL10, run:
```bash
cargo pgrx init --pg17=/usr/pgsql-17/bin/pg_config
make check-versions
make pg_duckdb PG_VERSION=pg17 PG_CONFIG=/usr/pgsql-17/bin/pg_config JOBS=4
make install PG_VERSION=pg17 PG_CONFIG=/usr/pgsql-17/bin/pg_config JOBS=4
```

Skip `make pg_duckdb` only when the matching 1.2.0 binary is already installed.
For Ubuntu / PostgreSQL 18, use `pg18` and `/usr/lib/postgresql/18/bin/pg_config`.

The install step also builds `mooncake.duckdb_extension` and installs a local
DuckDB extension repository under `$(pg_config --sharedir)/extension/pg_mooncake`.
CMake downloads pinned nanoarrow, Corrosion and CRoaring sources when needed.
The Rust RPC client is pinned to the server's base Moonlink revision. This fork
also includes a Moonlink fix for snapshot requests whose database LSN is ahead
of the last change to the mirrored table, and sets `REPLICA IDENTITY FULL` on
existing leaf partitions before replication starts. The RPC protocol is unchanged.

`make package PG_VERSION=pg17 PG_CONFIG=/usr/pgsql-17/bin/pg_config` stages both
extensions under `target/release/pg_mooncake-pg17/`.

Finally, configure PostgreSQL and restart it. On EL10 with PostgreSQL 17:
```ini
duckdb.allow_community_extensions = true
duckdb.allow_unsigned_extensions = true
mooncake.extension_repository = '/usr/pgsql-17/share/extension/pg_mooncake'
shared_preload_libraries = 'pg_duckdb,pg_mooncake'
wal_level = logical
```

The unsigned-extension setting is required for the locally built DuckDB extension.
Set `mooncake.extension_repository` to the matching installation path if your
PostgreSQL installation uses a different prefix. When this setting is absent,
extension creation retains the upstream behavior of using the community repository.

The existing [Dockerfile][dockerfile-link] describes the legacy upstream build
and has not been validated for this fork.

### Testing the source build

Use a disposable database on a PostgreSQL instance configured as above. Run the
existing SQL regression suite with `pg_regress`, then the integration test
(Python 3 and `psycopg` 3 are required):

```bash
export PGHOST=/var/run/postgresql PGPORT=5432 PGUSER=postgres
make test PG_CONFIG=/usr/pgsql-17/bin/pg_config
createdb mooncake_version_guard
PGDATABASE=mooncake_version_guard python3 tests/version_guard.py
createdb mooncake_integration
PGDATABASE=mooncake_integration psql -c 'CREATE EXTENSION pg_mooncake CASCADE'
PGDATABASE=mooncake_integration python3 tests/integration.py --pg-major 17
# Restart the test PostgreSQL instance, then:
PGDATABASE=mooncake_integration python3 tests/integration.py --pg-major 17 --after-restart
```

The integration test compares the mirror with PostgreSQL heap tables before and
after changes, snapshots, compaction and restart. It also checks filtered scans,
aggregates, joins, prepared statements, empty tables and cleanup.

`mooncake.load_files` is unimplemented in the bundled Moonlink source. This fork
returns `FEATURE_NOT_SUPPORTED` instead of silently acknowledging an import.
Partitions added after mirror creation must also have `REPLICA IDENTITY FULL`
set before they receive writes; automatic handling of later partition DDL is
not covered by this validation.
`TRUNCATE` replication is also outside the supported/tested scope. The validation
targets are EL10 ARM64 with PostgreSQL 17 and the earlier Ubuntu 24.04 ARM64 /
PostgreSQL 18 run; each report identifies the exact source and dependency versions
tested. Other combinations require their own validation.

See the [u24a / PostgreSQL 18 validation report](docs/duckdb-2-validation.md)
for pinned revisions, test results, reproduction commands and remaining limits.
The current pgrx 0.19.3 release is covered by the
[EL10 / PostgreSQL 17 report](docs/el10a-pg17-validation.md) and the
[dependency audit](docs/dependency-audit-2026-11-05.md).

### Updating dependencies

For a new pg_duckdb release, advance pg_mooncake's version with it, update
`versions.json`, the submodule commits, the SQL version guard and the test
expectations together. Both DuckDB submodules must match pg_duckdb's DuckDB
revision. Pin the DuckDB extension's Moonlink RPC client to the same Moonlink
commit as the server, regenerate the affected Cargo lockfiles, then rerun
`make check-versions` and the build/integration tests. Source archives lack Git
metadata, so their commit pins must be verified before archiving.

Audit the top-level, Moonlink workspace and FFI lockfiles before dependency
updates. Prefer fixes within the existing compatibility range; record remaining
advisories and the reason for any larger migration. Do not replace a vulnerability
review with an unrestricted `cargo update`.

## Quick Start

First, create the pg_mooncake extension:
```sql
CREATE EXTENSION pg_mooncake CASCADE;
```

Next, create a regular Postgres table `trades`:
```sql
CREATE TABLE trades(
  id bigint PRIMARY KEY,
  symbol text,
  time timestamp,
  price real
);
```

Then, create a columnstore mirror `trades_iceberg` that stays in sync with `trades`:
```sql
CALL mooncake.create_table('trades_iceberg', 'trades');
```

Now, insert some data into `trades`:
```sql
INSERT INTO trades VALUES
  (1,  'AMD', '2024-06-05 10:00:00', 119),
  (2, 'AMZN', '2024-06-05 10:05:00', 207),
  (3, 'AAPL', '2024-06-05 10:10:00', 203),
  (4, 'AMZN', '2024-06-05 10:15:00', 210);
```

Finally, query `trades_iceberg` to see that it reflects the up-to-date state of `trades`:
```sql
SELECT avg(price) FROM trades_iceberg WHERE symbol = 'AMZN';
```

## Contributing

pg_mooncake is an open-source project maintained by [Mooncake Labs][mooncake-link] and licensed under the [MIT License][license-link]. We'd love your help to make it even better! Join [our Slack][slack-link], participate in [discussions][discussions-link], open [issues][issues-link] to report bugs or suggest features, contribute code and documentation, or help us improve the project in any way. All contributions are welcome! 🥮

[clickbench-link]: https://www.mooncake.dev/blog/clickbench-v0.1
[discussions-link]: https://github.com/Mooncake-Labs/pg_mooncake/discussions
[dockerfile-link]: https://github.com/Mooncake-Labs/pg_mooncake/blob/main/Dockerfile
[docs-link]: https://docs.mooncake.dev/
[docs-shield]: https://img.shields.io/badge/docs-mooncake?logo=readthedocs&logoColor=white
[duckdb-install]: https://duckdb.org/docs/stable/dev/building/overview.html#prerequisites
[iceberg-link]: https://iceberg.apache.org/
[issues-link]: https://github.com/Mooncake-Labs/pg_mooncake/issues
[license-link]: https://github.com/Mooncake-Labs/pg_mooncake/blob/main/LICENSE
[license-shield]: https://img.shields.io/badge/License-MIT-blue
[mooncake-link]: https://mooncake.dev/
[moonlink-link]: https://github.com/Mooncake-Labs/moonlink
[pgduckdb-link]: https://github.com/duckdb/pg_duckdb
[pgrx-install]: https://github.com/pgcentralfoundation/pgrx?tab=readme-ov-file#getting-started
[rust-install]: https://www.rust-lang.org/tools/install
[slack-link]: https://join.slack.com/t/mooncake-devs/shared_invite/zt-2sepjh5hv-rb9jUtfYZ9bvbxTCUrsEEA
[slack-shield]: https://img.shields.io/badge/Mooncake%20Devs-purple?logo=slack
[x-link]: https://x.com/mooncakelabs
[x-shield]: https://img.shields.io/twitter/url?label=%40mooncakelabs&url=https%3A%2F%2Fx.com%2Fmooncakelabs
