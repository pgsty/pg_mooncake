# pg_mooncake

[![Website: mooncake.pgsty.com](https://img.shields.io/badge/Website-mooncake.pgsty.com-slategray?style=flat&logo=cilium&logoColor=white)](https://mooncake.pgsty.com/)
[![Docs: pg_mooncake](https://img.shields.io/badge/Docs-pg__mooncake-slategray?style=flat)](https://mooncake.pgsty.com/docs/)
[![Catalog: pg_mooncake](https://img.shields.io/badge/Catalog-pg__mooncake-%233E668F?style=flat&logo=postgresql&logoColor=white&labelColor=3E668F)](https://pgext.cloud/ext/pg_mooncake)
[![Version: v0.3.0](https://img.shields.io/badge/Version-v0.3.0-slategray?style=flat)](https://github.com/pgsty/pg_mooncake/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-slategray?style=flat&logo=opensourceinitiative&logoColor=green)](https://github.com/pgsty/pg_mooncake/blob/main/LICENSE)
[![GitHub Stars](https://img.shields.io/github/stars/pgsty/pg_mooncake?style=flat&logo=github&logoColor=black&color=slategray)](https://star-history.com/#pgsty/pg_mooncake&Date)
[![PostgreSQL: 14-18](https://img.shields.io/badge/PostgreSQL-14--18-%233E668F?style=flat&logo=postgresql&logoColor=white&labelColor=3E668F)](https://pgext.cloud/ext/pg_mooncake)

**`pg_mooncake`** is a PostgreSQL extension that creates a real-time columnstore mirror of your PostgreSQL tables in [Apache Iceberg][iceberg-link], enabling sub-second vectorized analytical queries powered by [`moonlink`][moonlink-link], [`duckdb_mooncake`][duckdb-mooncake-link], and [`pg_duckdb`][pgduckdb-link].

[Website](https://mooncake.pgsty.com/) | [Documentation][docs-link] | [moonlink][moonlink-link] | [duckdb_mooncake][duckdb-mooncake-link] | [Blog](https://mooncake.pgsty.com/blog/) | [PGEXT](https://pgext.cloud/ext/pg_mooncake) | [Releases](https://github.com/pgsty/pg_mooncake/releases) | [Issues][issues-link] | [Upstream](https://github.com/Mooncake-Labs/pg_mooncake)

---

## Mooncake Suite

`pg_mooncake` is the core PostgreSQL extension of the **Mooncake** family maintained by [PGSTY](https://pgsty.com):

- **[`pg_mooncake`](https://github.com/pgsty/pg_mooncake)** ([Docs](https://mooncake.pgsty.com/docs/intro/) / [Meta](https://pgext.cloud/ext/pg_mooncake)): PostgreSQL extension (`v0.3.0`, MIT) providing `mooncake.create_table()`, logical replication workers, and transparent query routing via `pg_duckdb` `1.2.0`.
- **[`moonlink`][moonlink-link]** ([Docs](https://mooncake.pgsty.com/docs/intro/moonlink/)): Rust real-time Iceberg v3 ingestion engine (`v0.0.1`, BSL-1.1 with `pg_mooncake` Linking & Distribution Exception; client crates MIT).
- **[`duckdb_mooncake`][duckdb-mooncake-link]** ([Docs](https://mooncake.pgsty.com/docs/intro/duckdb-mooncake/)): DuckDB `v2.0.0` storage & catalog scanner extension (`v0.0.2`, MIT) merging in-memory Arrow IPC buffers, Roaring deletion vectors, and flushed Parquet files with LSN snapshot consistency.

---

## Overview

**pg_mooncake** is a Postgres extension that creates a columnstore mirror of your Postgres tables in [Iceberg][iceberg-link], enabling fast analytics queries with sub-second freshness:
- **Real-time ingestion** powered by [moonlink][moonlink-link] for streaming and batched INSERT/UPDATE/DELETE.
- **Fast analytics** accelerated by [DuckDB][pgduckdb-link], ranking top 10 on [ClickBench][clickbench-link].
- **Postgres-native** allowing you to query a columnstore table just like a regular Postgres table.
- **Iceberg-native** making your data readily accessible by other query engines.

## Installation

For full installation instructions, see the [Installation Guide](https://mooncake.pgsty.com/docs/getting-started/).

### Option 1: Install via Native Linux Packages ([`pig`](https://pig.pgsty.com/))

On EL 8/9/10, Debian 12/13, and Ubuntu 22.04/24.04 (PostgreSQL 14–18), you can install pre-built native packages from the [Pigsty repository](https://pigsty.io/ext/e/pg_mooncake) (see package matrix on [pgext.cloud](https://pgext.cloud/ext/pg_mooncake)):

```bash
curl -fsSL https://repo.pigsty.io/pig | bash
pig repo add pgsql -u
pig ext add pg_mooncake pg_duckdb
```

Then configure `shared_preload_libraries` and `wal_level = logical` in `postgresql.conf` and restart PostgreSQL:

```ini
shared_preload_libraries = 'pg_duckdb,pg_mooncake'
wal_level = logical
```

### Option 2: Docker

The upstream image below is a legacy distribution. It does not contain this
fork's DuckDB 2.0 compatibility changes; use the native package or source build for those changes.
```bash
docker run --name mooncake --rm -e POSTGRES_PASSWORD=password mooncakelabs/pg_mooncake
```

This will start Postgres with pg_mooncake preinstalled. You can then connect to it using `psql` with the default user `postgres`:
```bash
docker exec -it mooncake psql -U postgres
```

### Option 3: From Source

This fork's **pg_mooncake 0.3.0** requires **pg_duckdb 1.2.0 and DuckDB 2.0.0**.
pg_mooncake has its own release version. `versions.json` records the dependency
tags, exact submodule commits, both DuckDB source revisions, and
pgrx/cargo-pgrx **0.19.3**. Builds check
these pins and use Cargo lockfiles; extension creation rejects a different
installed pg_duckdb version.
The DuckDB Mooncake extension must be rebuilt along with this upgrade: a binary
compiled for DuckDB 1.4.x cannot be loaded by DuckDB 2.0.

The dependencies are [duckdb_mooncake v0.0.2](https://github.com/pgsty/duckdb_mooncake/tree/v0.0.2)
and [Moonlink v0.0.1](https://github.com/pgsty/moonlink/tree/v0.0.1). Their Git
submodules remain pinned to the full commits recorded in `versions.json`; the
FFI client's Moonlink revision matches the server. For an existing checkout,
fetch these tags before running the version check:

```bash
git submodule sync --recursive
git submodule update --init --recursive
git -C duckdb_mooncake fetch origin tag v0.0.2
git -C moonlink fetch origin tag v0.0.1
```

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
The 0.3.0 release is covered by the
[EL10 / PostgreSQL 17 rebuild report](docs/pg-mooncake-0.3.0-validation.md).
The earlier [EL10 / PostgreSQL 17 report](docs/el10a-pg17-validation.md) covers
the same pgrx 0.19.3 dependency set under the former development version.
The [dependency audit](docs/dependency-audit-2026-11-05.md) records the security
updates and remaining advisories.

### Updating dependencies

For a new pg_duckdb release, choose the next pg_mooncake release version and
update `versions.json`, the submodule commits, the SQL version guard and the test
expectations together. The two PostgreSQL extensions have independent version
numbers. Both DuckDB submodules must match pg_duckdb's DuckDB
revision. Pin the DuckDB extension's Moonlink RPC client to the same Moonlink
commit as the server, tag each changed dependency, update its tag and commit in
`versions.json`, regenerate the affected Cargo lockfiles, then rerun
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

---

## Documentation

Full documentation is available at **[mooncake.pgsty.com/docs](https://mooncake.pgsty.com/docs/)**:

- **Getting Started**
  - [Installation & Quick Start](https://mooncake.pgsty.com/docs/getting-started/)
  - [Hello World Tutorial](https://mooncake.pgsty.com/docs/getting-started/hello-world/)
  - [Known Limitations](https://mooncake.pgsty.com/docs/getting-started/known-limitations/)
- **Architecture & Core Components**
  - [Welcome to Mooncake](https://mooncake.pgsty.com/docs/intro/)
  - [Architecture Overview](https://mooncake.pgsty.com/docs/intro/architecture/)
  - [Moonlink Engine (`v0.0.1`)](https://mooncake.pgsty.com/docs/intro/moonlink/)
  - [duckdb_mooncake Scanner (`v0.0.2`)](https://mooncake.pgsty.com/docs/intro/duckdb-mooncake/)
  - [v0.1 vs v0.2 / v0.3](https://mooncake.pgsty.com/docs/intro/0.1-vs-0.2/)
- **SQL & Configuration Reference**
  - [Reference Overview](https://mooncake.pgsty.com/docs/reference/)
  - [Create Columnstore Tables](https://mooncake.pgsty.com/docs/reference/create-columnstore/)
  - [Query Columnstore Tables](https://mooncake.pgsty.com/docs/reference/query-columnstore/)
  - [Iceberg & Object Storage](https://mooncake.pgsty.com/docs/reference/iceberg/)
  - [Query Existing Data Lakes](https://mooncake.pgsty.com/docs/reference/query-data-lake/)
- **Use Cases & Engineering Blog**
  - [Real-Time Analytics](https://mooncake.pgsty.com/docs/use-cases/real-time-analytics/) · [Postgres to Iceberg Lakehouse](https://mooncake.pgsty.com/docs/use-cases/lakehouse/) · [Table Archiving](https://mooncake.pgsty.com/docs/use-cases/archiving/) · [Logging & Time-Series](https://mooncake.pgsty.com/docs/use-cases/logging/)
  - [pg_mooncake v0.3.0 Release Notes](https://mooncake.pgsty.com/blog/release/pg-mooncake-0.3.0/) · [Adapting pg_mooncake to DuckDB 2.0 & PostgreSQL 18](https://mooncake.pgsty.com/blog/post/duckdb-2-adaptation/)
  - [About, Licensing & Attribution](https://mooncake.pgsty.com/docs/about/)

---

## License

This software is licensed under the **MIT License ([MIT][license-link])**.

- Copyright (c) 2024–2025 Mooncake Labs, Inc.
- Copyright (c) 2026 PGSTY PTE. LTD.
- Maintained by [Ruohang Feng](mailto:rh@vonng.com) @ [PGSTY](https://pgsty.com)

[clickbench-link]: https://mooncake.pgsty.com/blog/post/clickbench-v0.1/
[dockerfile-link]: https://github.com/pgsty/pg_mooncake/blob/main/Dockerfile
[docs-link]: https://mooncake.pgsty.com/docs/
[duckdb-install]: https://duckdb.org/docs/stable/dev/building/overview.html#prerequisites
[duckdb-mooncake-link]: https://github.com/pgsty/duckdb_mooncake
[iceberg-link]: https://iceberg.apache.org/
[issues-link]: https://github.com/pgsty/pg_mooncake/issues
[license-link]: https://github.com/pgsty/pg_mooncake/blob/main/LICENSE
[moonlink-link]: https://github.com/pgsty/moonlink
[pgduckdb-link]: https://github.com/duckdb/pg_duckdb
[pgrx-install]: https://github.com/pgcentralfoundation/pgrx?tab=readme-ov-file#getting-started
[rust-install]: https://www.rust-lang.org/tools/install
