# pg_mooncake

[![Website: mooncake.pgsty.com](https://img.shields.io/badge/Website-mooncake.pgsty.com-slategray?style=flat&logo=cilium&logoColor=white)](https://mooncake.pgsty.com/)
[![Docs: pg_mooncake](https://img.shields.io/badge/Docs-pg__mooncake-slategray?style=flat)](https://mooncake.pgsty.com/docs/)
[![Catalog: pg_mooncake](https://img.shields.io/badge/Catalog-pg__mooncake-%233E668F?style=flat&logo=postgresql&logoColor=white&labelColor=3E668F)](https://pgext.cloud/ext/pg_mooncake)
[![Version: v0.3.3](https://img.shields.io/badge/Version-v0.3.3-slategray?style=flat)](https://github.com/pgsty/pg_mooncake/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-slategray?style=flat&logo=opensourceinitiative&logoColor=green)](https://github.com/pgsty/pg_mooncake/blob/main/LICENSE)
[![GitHub Stars](https://img.shields.io/github/stars/pgsty/pg_mooncake?style=flat&logo=github&logoColor=black&color=slategray)](https://star-history.com/#pgsty/pg_mooncake&Date)
[![PostgreSQL: 15-19](https://img.shields.io/badge/PostgreSQL-15--19-%233E668F?style=flat&logo=postgresql&logoColor=white&labelColor=3E668F)](https://pgext.cloud/ext/pg_mooncake)

**`pg_mooncake`** is a PostgreSQL extension that creates a real-time columnstore mirror of your PostgreSQL tables in [Apache Iceberg][iceberg-link], enabling sub-second vectorized analytical queries powered by [`moonlink`][moonlink-link], [`duckdb_mooncake`][duckdb-mooncake-link], and [`pg_duckdb`][pgduckdb-link].

[Website](https://mooncake.pgsty.com/) | [Documentation][docs-link] | [moonlink][moonlink-link] | [duckdb_mooncake][duckdb-mooncake-link] | [Blog](https://mooncake.pgsty.com/blog/) | [PGEXT](https://pgext.cloud/ext/pg_mooncake) | [Releases](https://github.com/pgsty/pg_mooncake/releases) | [Issues][issues-link] | [Upstream](https://github.com/Mooncake-Labs/pg_mooncake)

---

## Mooncake Suite

`pg_mooncake` is the core PostgreSQL extension of the **Mooncake** family maintained by [PGSTY](https://pgsty.com):

- **[`pg_mooncake`](https://github.com/pgsty/pg_mooncake)** ([Docs](https://mooncake.pgsty.com/docs/intro/) / [Meta](https://pgext.cloud/ext/pg_mooncake)): PostgreSQL 15–19 extension (`v0.3.3`, MIT) providing `mooncake.create_table()`, logical replication workers, and transparent query routing via `pg_duckdb` `1.2.1`.
- **[`moonlink`][moonlink-link]** ([Docs](https://mooncake.pgsty.com/docs/intro/moonlink/)): Rust real-time Iceberg v3 ingestion engine (`v0.3.0-pgsty.2`, BSL-1.1 with `pg_mooncake` Linking & Distribution Exception; client crates MIT).
- **[`duckdb_mooncake`][duckdb-mooncake-link]** ([Docs](https://mooncake.pgsty.com/docs/intro/duckdb-mooncake/)): DuckDB `v2.0.1` storage & catalog scanner extension (`v0.0.5`, MIT) merging in-memory Arrow IPC buffers, Roaring deletion vectors, and flushed Parquet files with LSN snapshot consistency.

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

Check the [package matrix](https://pgext.cloud/ext/pg_mooncake) for the extension version available for your
distribution and PostgreSQL major. Install published packages from the [Pigsty repository](https://pigsty.io/ext/e/pg_mooncake):

```bash
curl -fsSL https://repo.pigsty.io/pig | bash
pig repo add pgsql -u
pig ext add pg_mooncake pg_duckdb
```

Before creating the extension, [configure PostgreSQL](#configure-postgresql) to load the scanner
shipped with the package. A fresh installation needs the local scanner repository and permission
to load its unsigned extension.

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

This fork's **pg_mooncake 0.3.3** requires **pg_duckdb 1.2.1 and DuckDB 2.0.1**.
pg_mooncake has its own release version. `versions.json` records the dependency
tags, exact submodule commits, both DuckDB source revisions, and
pgrx/cargo-pgrx **0.20.0**. Source builds require **Rust 1.99.1** or newer
and support **PostgreSQL 15–19**, with PostgreSQL 18 as the default target.
Build and deploy against matching PostgreSQL server and development packages.
For example, an extension built against the 18.7 headers can require `heap_datum_check`,
which the 18.6 server does not export. The Dockerfile installs the build headers' exact
Debian package version in the runtime image.
pgrx 0.20 no longer supports PostgreSQL 14; use the 0.3.0 release for PG14.
Builds check these pins and use Cargo lockfiles; extension creation rejects a
different installed pg_duckdb version.
The DuckDB Mooncake extension must be rebuilt along with this upgrade: a binary
compiled for DuckDB 1.4.x or 2.0.0 cannot be loaded by DuckDB 2.0.1.

The dependencies are `duckdb_mooncake v0.0.5` and `Moonlink v0.3.0-pgsty.2`. Their Git
submodules remain pinned to the full commits recorded in `versions.json`; the
FFI client's Moonlink revision matches the server. For an existing checkout,
fetch these tags before running the version check:

```bash
git submodule sync --recursive
git submodule update --init --recursive
git -C duckdb_mooncake fetch origin tag v0.0.5
git -C moonlink fetch origin tag v0.3.0-pgsty.2
git -C moonlink fetch origin tag v0.3.0
```

To build pg_mooncake, first install [Rust][rust-install], [pgrx][pgrx-install], and [the build tools for DuckDB][duckdb-install].
On Ubuntu 24.04, the additional native dependencies are:

```bash
sudo apt-get install build-essential cmake ninja-build pkg-config libclang-dev \
    libssl-dev libcurl4-openssl-dev liblz4-dev protobuf-compiler postgresql-server-dev-18
cargo install --locked cargo-pgrx --version 0.20.0
```

For EL10 / PostgreSQL 17, the equivalent native dependencies are:

```bash
sudo dnf install gcc gcc-c++ make cmake ninja-build pkgconf-pkg-config \
    clang-devel llvm-devel openssl-devel libcurl-devel lz4-devel \
    protobuf-compiler python3-pip postgresql17-devel
```

Clone the tagged release with its submodules:

```bash
git clone --recurse-submodules --branch v0.3.3 https://github.com/pgsty/pg_mooncake.git
cd pg_mooncake
```

Alternatively, download `pg_mooncake-0.3.3-source.tar.gz` and `SHA256SUMS` from the
[v0.3.3 release](https://github.com/pgsty/pg_mooncake/releases/tag/v0.3.3). This archive includes
the pinned submodule sources. GitHub's automatic source archives omit their contents.
On macOS, use `shasum -a 256 -c SHA256SUMS` for the checksum step.

```bash
sha256sum -c SHA256SUMS
tar -xzf pg_mooncake-0.3.3-source.tar.gz
cd pg_mooncake-0.3.3
```

To build and install for PostgreSQL 17 on EL10, run:
```bash
cargo pgrx init --pg17=/usr/pgsql-17/bin/pg_config
make check-versions
make pg_duckdb PG_VERSION=pg17 PG_CONFIG=/usr/pgsql-17/bin/pg_config JOBS=4
make install PG_VERSION=pg17 PG_CONFIG=/usr/pgsql-17/bin/pg_config JOBS=4
```

Skip `make pg_duckdb` only when the matching 1.2.1 binary is already installed.
For Ubuntu / PostgreSQL 18, use `pg18` and `/usr/lib/postgresql/18/bin/pg_config`.

For PostgreSQL 19, install its server development headers and select `pg19`:

```bash
cargo pgrx init --pg19=/usr/lib/postgresql/19/bin/pg_config
make check-versions
make pg_duckdb PG_VERSION=pg19 PG_CONFIG=/usr/lib/postgresql/19/bin/pg_config JOBS=4
make install PG_VERSION=pg19 PG_CONFIG=/usr/lib/postgresql/19/bin/pg_config JOBS=4
```

`make package PG_VERSION=pg19 PG_CONFIG=/usr/lib/postgresql/19/bin/pg_config`
stages the installation under `target/release/pg_mooncake-pg19/`.
The build target does not imply availability of pre-built PG19 packages;
check the package matrix linked above.

The install step also builds `mooncake.duckdb_extension` and installs a local
DuckDB extension repository under `$(pg_config --sharedir)/extension/pg_mooncake`.
CMake downloads pinned nanoarrow, Corrosion and CRoaring sources when needed.
The Rust RPC client and server use the same Moonlink commit. The patched server
retains earlier request numbers and adds requests for mirror registration and cleanup.
Fresh reads and snapshots use the WAL position of the mirror's source server.
Replication sets `REPLICA IDENTITY FULL` on existing leaf partitions before it starts.

`make package PG_VERSION=pg17 PG_CONFIG=/usr/pgsql-17/bin/pg_config` stages both
extensions under `target/release/pg_mooncake-pg17/`.

### Configure PostgreSQL

Run `pg_config --sharedir` from the target PostgreSQL installation and append `/extension/pg_mooncake`
to get the absolute scanner repository path. For example, on EL10 with PostgreSQL 17, set the
following in `postgresql.conf` and restart PostgreSQL:

```ini
duckdb.allow_unsigned_extensions = true
mooncake.extension_repository = '/usr/pgsql-17/share/extension/pg_mooncake'
# For physical backups or streaming standbys, set this before creating mirrors.
# mooncake.data_directory = '/var/lib/pgsql/17/mooncake'
shared_preload_libraries = 'pg_duckdb,pg_mooncake'
wal_level = logical
```

In a fresh session run `CREATE EXTENSION pg_mooncake CASCADE;`. The packaged scanner loads from
the configured local repository with `duckdb.allow_community_extensions` left at its default `off`.
Use a UTF-8 path for `mooncake.data_directory`. Relative paths are resolved from the PostgreSQL data directory.
Set `mooncake.data_directory` to a server-owned directory outside `$PGDATA`
(mode `0700` or `0750`) and back it up separately when using `pg_basebackup` or streaming standbys.
With a non-UTF-8 PostgreSQL data path, also set `duckdb.temporary_directory` and `duckdb.extension_directory`
to instance-owned, writable UTF-8 paths. See
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for lifecycle details.

### Upgrading a PGSTY 0.3.0 installation

PGSTY 0.3.0 uses Moonlink `b298ef74`, which can acknowledge source changes after writing its private `_wal`.
The new worker starts from Iceberg snapshots and the source replication slot. Perform these steps on **every
database with mirrors** before switching libraries.

1. Stop writers to every source, including remote sources. Record each mirror, source, connection settings and
   storage configuration. Keep a recoverable backup of the PostgreSQL cluster and the complete Moonlink directory.
2. On the **old binaries**, wait until each mirror matches its quiescent source. Compare all columns in both directions
   with `EXCEPT ALL` to include duplicates. For a remote source, compare consistent exports from both servers.
   In a fresh session call `CALL mooncake.create_snapshot('schema.mirror')` on each mirror. Record
   `commit_lsn` and `flush_lsn` from `mooncake.list_tables()` and verify that the snapshot covers the mirror's last
   data change. For an empty mirror, also check that its source is empty.
3. Stop PostgreSQL cleanly. After the checks in step 2, move the old `_wal` outside the active Moonlink directory
   and retain it with the backup. The new worker refuses a nonempty `_wal`. Install the matched PostgreSQL
   extension, pg_duckdb and scanner, start PostgreSQL, then run `ALTER EXTENSION pg_duckdb UPDATE TO '1.2.1'`
   and `ALTER EXTENSION pg_mooncake UPDATE TO '0.3.3'` in each database. Use a fresh session with the matching
   scanner repository. The SQL update checks the loaded scanner and removes `mooncake.load_files(text,text[])`.
4. Repeat the source/mirror comparison. Commit one identifiable change at the source, verify it in the mirror and
   take a new snapshot before resuming writers. If the old snapshot or source comparison cannot be established,
   retain the backup and rebuild the affected mirrors from their authoritative sources. If the new binaries
   already ran, a snapshot taken now cannot recover missing old WAL.

PGSTY 0.3.1 and 0.3.2 both have a direct SQL update to 0.3.3. Install the matching libraries and scanner,
restart PostgreSQL, and run `ALTER EXTENSION pg_mooncake UPDATE TO '0.3.3'` in each database. DuckDB may have cached scanner
v0.0.3 or v0.0.4 in its v2.0.1 directory. With the new local `mooncake.extension_repository` configured, refresh
the cached scanner before the update, then reconnect so the backend loads the new binary.

```sql
SELECT duckdb.raw_query(format('FORCE INSTALL mooncake FROM %L', current_setting('mooncake.extension_repository')));
```

After the update, take a fresh snapshot of each mirror before using it for a backup or migration.
An earlier worker could acknowledge a source commit before Iceberg had persisted it.

Before renaming or dropping a database with mirrors, drop its mirrors, commit and run
`SELECT mooncake._reconcile_drops()` there. These database operations require the worker to be available
to verify the registrations. After a server restart the RPC socket becomes ready when mirror recovery finishes.
On a smart shutdown, Moonlink stops serving mirrors and closes its source connections so PostgreSQL can
finish draining client sessions. Ordinary PostgreSQL sessions can finish their transactions. The next
startup replays any source commits made during the shutdown.

Run `CALL mooncake.create_table(...)` as a standalone command in a writable session.
It commits the mirror definition and its registration together in a separate destination transaction.

Each new mirror reserves a fresh local Iceberg table directory. Keep a custom warehouse outside the worker's
temporary and read-cache directories. If creation reports an occupied path, verify who owns it and preserve
any old data before moving it aside. Give separate deployments exclusive object-store table prefixes.

An external `mooncake.data_directory` needs its own backup. A restored physical copy must have a private
directory and correct Iceberg locations. Rebuild mirrors whose files were omitted. A logical dump of extension
objects does not capture Moonlink data or replication state. Protect source connection strings, server logs and
the SQLite metadata file. Roles with server-file access can read mirror files across tables. Use a separate
trust boundary for tenants requiring isolated mirror access.

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

The unimplemented `mooncake.load_files` procedure has been removed (matching
upstream 0.3.0). Direct writes (`INSERT`, `UPDATE`, `DELETE`, `MERGE`,
`TRUNCATE`, `COPY FROM`) and unsupported mirror DDL (`RENAME`, `SET SCHEMA`,
`SET ACCESS METHOD`, `ATTACH PARTITION`, `INHERIT`) are rejected with explicit
errors before reaching `pg_duckdb`. Partitions added while empty are followed;
attaching populated partitions, detaching/dropping partitions, or running
`TRUNCATE` / schema DDL on a source table transitions its mirror into an
isolated errored state (drop and re-create with `mooncake.create_table`).

For each supported PostgreSQL major, run the ten SQL regression suites, the version guard and both
integration phases with a server restart between them. To validate a storage upgrade, retain a mirror
created by the old binaries, including a deletion and a snapshot. Compare the source and mirror in both
directions before the first new write and again after a new snapshot and restart.

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
`make check-versions` and the build/integration tests. From the release commit, run
`python3 scripts/source_archive.py /path/to/pg_mooncake-VERSION-source.tar.gz` to export the
committed source trees, including nested submodules. Publish the archive with its SHA-256 checksum.

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
  - [Moonlink Engine](https://mooncake.pgsty.com/docs/intro/moonlink/)
  - [duckdb_mooncake Scanner](https://mooncake.pgsty.com/docs/intro/duckdb-mooncake/)
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
