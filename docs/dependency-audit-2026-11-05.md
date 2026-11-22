# Dependency audit, 2026-11-05

This update pins pgrx/cargo-pgrx 0.19.3 and aligns pg_mooncake's release version
with pg_duckdb 1.2.0. Cargo updates were selected from security advisories or
required by the pgrx migration. Arrow 55, Parquet 55, Delta Lake 0.28 and the
Iceberg revision retain their existing APIs.

The audit used cargo-audit 0.22.2 and RustSec database commit
`965bf9ad083b58e6340d65829d85217b18be9290` (updated November 3, 2026). All three
lockfiles were scanned without advisory ignores. Counts below are matches
against package versions, not unique CVEs or confirmed exploitable paths.

| Lockfile | Vulnerability matches before | After | Unsoundness warnings after |
| --- | ---: | ---: | ---: |
| Top-level PostgreSQL extension | 33 | 6 | 0 |
| Moonlink workspace | 46 | 15 | 0 |
| DuckDB extension's RPC client | 1 | 0 | 0 |

The residual counts are intentional disclosure, not a passing clean audit.
Unmaintained-crate warnings remain, including bincode and paste in the RPC client.
The existing Moonlink `deny.toml` ignore list was not used by these cargo-audit
runs and was not expanded.

## Changes selected

| Package | Previous | Locked version | Reason |
| --- | --- | --- | --- |
| pgrx family | 0.16.1 | 0.19.3 | Requested migration; cargo-pgrx must match |
| bytes | 1.10.1 | 1.11.1 | RUSTSEC-2026-0007 |
| crossbeam-epoch | 0.9.18 | 0.9.20 | RUSTSEC-2026-0204 |
| h2 | 0.4.12 | 0.4.16 | RUSTSEC-2026-0258 |
| lz4_flex | 0.11.5 | 0.11.6 | RUSTSEC-2026-0041 |
| quinn-proto | 0.11.13 | 0.11.18 | Six 2026 denial-of-service advisories |
| rustls | 0.23.31 | 0.23.46 | RUSTSEC-2026-0285, 0346, 0348, 0349 |
| rustls-webpki | 0.103.4 | 0.103.16 | Certificate / CRL validation advisories |
| webpki-roots | 1.0.2 | 1.0.10 | RUSTSEC-2026-0381 |
| time | 0.3.43 | 0.3.47 | RUSTSEC-2026-0009 |
| zstd / zstd-safe / zstd-sys | 0.13.3 / 7.2.4 / 2.0.15 | 0.13.4 / 7.4.0 / 2.1.2 | Streaming and memory-safety advisories |
| anyhow | 1.0.99 (FFI: 1.0.100) | 1.0.103 | RUSTSEC-2026-0190 |
| event-listener | 5.4.1 | 5.4.2 | RUSTSEC-2026-0221 |
| lru | 0.16.2 | 0.18.5 | RUSTSEC-2026-0002 and 0253; manifest floor 0.18.2 |
| memmap2 | 0.9.8 | 0.9.11 | RUSTSEC-2026-0186 |
| rand | 0.8.5 / 0.9.2 | 0.8.8 / 0.9.3 | RUSTSEC-2026-0097 |
| tokio | 1.48.0 | 1.51.6 | RUSTSEC-2026-0386; patched maintenance branch |
| rust_decimal | 1.37.2 | 1.43.0 | Removes the obsolete optional rkyv 0.7 dependency |
| aws-lc-rs / aws-lc-sys, workspace only | 1.13.3 / 0.30.0 | 1.19.0 / 0.47.0 | AWS-LC advisories in the workspace lockfile |
| serial_test, workspace only | 3.2.0 | 3.5.0 | Removes the unsound scc 2.4 dependency |

The lockfiles also contain the transitive changes required by these packages.
The LRU change crosses a 0.x minor boundary because the panic-safety repair is
only available from 0.18.2. See the [upstream advisory](https://rustsec.org/advisories/RUSTSEC-2026-0253.html).
The new pgrx no longer provides `pgrx_embed!`; its obsolete helper binary was
removed. The actual release build, schema generation and install were validated.

## Remaining findings

**quick-xml 0.37.5 and 0.38.3: four matches.** OpenDAL 0.54 and object_store 0.12
require these incompatible older series. The fixes for
[duplicate-attribute CPU exhaustion](https://rustsec.org/advisories/RUSTSEC-2026-0194.html)
and [namespace allocation exhaustion](https://rustsec.org/advisories/RUSTSEC-2026-0195.html)
start at 0.41.0. Their XML deserializers use `NsReader`, so these findings must
not be dismissed as automatically unreachable. The relevant consumers handle
remote-storage responses; this run validates local filesystem storage. Moving
OpenDAL/object_store across their API boundaries also affects the pinned
Iceberg/Delta Lake stack and needs separate migration and remote-storage tests.

**thrift 0.17.0: one match.** Parquet 55 and the pinned Iceberg crate require this
series. [RUSTSEC-2026-0435](https://rustsec.org/advisories/RUSTSEC-2026-0435.html)
affects `TBinaryInputProtocol::read_bytes/read_string` and is fixed from 0.23.0.
Inspection of the current Parquet reader found compact-protocol readers, not
that binary-protocol path. This is a scope observation, not a general exemption
for future callers. The advisory remains in the audit output.

**rsa 0.9.8: one match.** [RUSTSEC-2023-0071](https://rustsec.org/advisories/RUSTSEC-2023-0071.html)
has no patched release. It is retained in the lockfile's optional dependency
graph; `cargo tree --no-default-features --features pg17,bgworker -e normal,build
-i rsa@0.9.8` found no active path in the PostgreSQL build. Enabling other storage
or catalog features requires reassessment.

The full Moonlink workspace lockfile additionally contains h2 0.3, rustls 0.21,
rustls-webpki 0.101 and quick-xml 0.26 findings in optional dependencies. Those
versions are absent from the top-level extension lockfile. Their major-version
migrations were not folded into this PostgreSQL compatibility change.

## Reproduction and evidence

```bash
cargo audit --file Cargo.lock --json
cargo audit --file moonlink/Cargo.lock --json
cargo audit --file duckdb_mooncake/moonlink_ffi/Cargo.lock --json
```

The first two commands return a nonzero status because findings remain. Raw
before/after reports, old lockfiles and targeted update logs are retained in the
test container's `/work/logs` and the ignored local directory
`target/validation/el10a-pg17/`. Re-running against a newer advisory database may
produce different results; retain the database revision with each audit.

## Follow-up: pgrx 0.20.0, 2026-11-20

The pgrx upgrade used a targeted `cargo update -p pgrx --precise 0.20.0`.
The Moonlink workspace and FFI lockfiles retain their previous contents.
Both the previous top-level lockfile and the updated one were audited with
cargo-audit 0.22.2 against RustSec revision
`074ea9a7ed619f511b5b7374c7a97e98d1e98be4` (November 19, 2026), using
`--no-fetch --no-yanked --json` and no advisory ignores.

| Lockfile | Vulnerability matches | Unsoundness warnings |
| --- | ---: | ---: |
| Top-level before the pgrx upgrade | 18 | 2 |
| Top-level after the pgrx upgrade | 18 | 1 |
| Moonlink workspace | 27 | 2 |
| DuckDB extension's RPC client | 0 | 0 |

The top-level vulnerability matches are identical before and after the upgrade.
Compared with the November 5 database, the newer snapshot also reports findings
in libsqlite3-sys 0.30.1, openssl 0.10.73, quinn-proto 0.11.18 and quinn-udp
0.5.14. These findings remain unresolved. The required rustix update from
1.0.8 to 1.1.6 removes RUSTSEC-2026-0486; arrow-data 55.2.0 still has the
RUSTSEC-2026-0442 unsoundness warning. Unmaintained-crate warnings also remain.

Raw JSON reports, the prior top-level lockfile and a summary recording the
database revision are retained under the ignored local directory
`target/validation/pgrx-0.20-pg19/`. These scans did not check yanked releases.

## Follow-up: v0.3.1 / moonlink v0.3.0, 2026-11-22

Upgrading `moonlink` to `v0.3.0` (`dcf999a9`, Arrow/Parquet 56, removing
Delta Lake, DataFusion, Kafka, OpenTelemetry, REST/Glue catalogs and GCS) and
applying targeted lockfile updates (`openssl 0.10.82`, `openssl-sys 0.9.118`,
`rustix 1.1.6`, `spin 0.9.9`) was audited with `cargo-deny check advisories`:

| Lockfile | Vulnerability advisories | Unsoundness advisories |
| --- | ---: | ---: |
| Top-level `Cargo.lock` (`v0.3.1`) | 4 | 1 |
| `moonlink/Cargo.lock` (`v0.3.0`) | 0 | 4 |
| `duckdb_mooncake/moonlink_ffi/Cargo.lock` (`v0.0.3`) | 0 | 0 |

Remaining top-level vulnerabilities are all transitive dependencies constrained by
upstream crate major versions: `libsqlite3-sys` (`RUSTSEC-2026-0459`, via
`sqlx-sqlite 0.8.6`), `quick-xml 0.37.5` (`RUSTSEC-2026-0194`, `RUSTSEC-2026-0195`,
via `opendal 0.54.0`), and `thrift 0.17.0` (`RUSTSEC-2026-0435`, via
`parquet 56.2.1` / `iceberg 0.7.0`). `arrow-data 56.2.1` retains the
`RUSTSEC-2026-0442` unsoundness notice; unmaintained-crate notices (`bincode`,
`chrono`, `core2`, `paste`, `pin-utils`, `serde_cbor`) remain.
