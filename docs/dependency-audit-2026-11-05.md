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
