#!/usr/bin/env python3
"""Check the release's dependency versions and exact Git revisions."""

import argparse
import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]


def capture(path, pattern):
    match = re.search(pattern, (ROOT / path).read_text(), re.MULTILINE)
    if not match:
        raise ValueError(f"missing version in {path}")
    return match.group(1)


def require(actual, expected, label):
    if actual != expected:
        raise ValueError(f"{label}: expected {expected}, found {actual}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-toolchain", action="store_true")
    args = parser.parse_args()
    versions = json.loads((ROOT / "versions.json").read_text())
    release = versions["pg_mooncake"]
    pg_duckdb_version = versions["pg_duckdb"]["version"]
    require(capture("Cargo.toml", r'^version = "([^"]+)"'), release, "pg_mooncake")
    require(capture("Cargo.toml", r'^pgrx = "=([^"]+)"'), versions["pgrx"], "pgrx pin")
    require(capture("pg_duckdb/pg_duckdb.control", r"^default_version = '([^']+)'"), pg_duckdb_version, "pg_duckdb")
    require(capture("src/sql/bootstrap.sql", r"installed_version IS DISTINCT FROM '([^']+)'"), pg_duckdb_version, "SQL dependency check")
    require(capture("src/sql/bootstrap.sql", r"RAISE EXCEPTION 'pg_mooncake ([^']+); installed version"), f"{release} requires pg_duckdb {pg_duckdb_version}", "SQL version message")
    require(capture("Makefile", r'^DUCKDB_VERSION := (.+)$'), versions["duckdb"]["version"], "DuckDB build version")
    require(capture("duckdb_mooncake/extension_config.cmake", r'EXTENSION_VERSION (\S+)'), versions["duckdb_mooncake"]["version"], "DuckDB Mooncake version")
    require(capture("moonlink/Cargo.toml", r'^version = "([^"]+)"'), versions["moonlink"]["version"], "Moonlink version")
    require(capture("duckdb_mooncake/moonlink_ffi/Cargo.toml", r'moonlink_rpc = .*rev = "([^"]+)"'), versions["moonlink"]["revision"], "RPC client/server revision")
    for component in ("duckdb_mooncake", "moonlink"):
        require(versions[component]["tag"], "v" + versions[component]["version"].removeprefix("v"), f"{component} release tag")

    for component in ("pg_mooncake", "pgrx", "pgrx-bindgen", "pgrx-macros", "pgrx-pg-config", "pgrx-pg-sys", "pgrx-sql-entity-graph"):
        expected = release if component == "pg_mooncake" else versions["pgrx"]
        require(capture("Cargo.lock", rf'^name = "{component}"\nversion = "([^"]+)"'), expected, f"Cargo.lock {component}")

    if args.check_toolchain:
        cli = subprocess.check_output(["cargo", "pgrx", "--version"], cwd=ROOT, text=True).strip().split()[-1]
        require(cli, versions["pgrx"], "cargo-pgrx")
    revisions = {name: versions[name]["revision"] for name in ("pg_duckdb", "duckdb_mooncake", "moonlink")}
    revisions.update({path: versions["duckdb"]["revision"] for path in ("pg_duckdb/third_party/duckdb", "duckdb_mooncake/duckdb")})
    if (ROOT / ".git").exists():
        for path, expected in revisions.items():
            # Require the submodule itself; git otherwise searches parent directories.
            if not (ROOT / path / ".git").exists():
                raise ValueError(f"uninitialized submodule: {path}")
            actual = subprocess.check_output(["git", "-C", str(ROOT / path), "rev-parse", "HEAD"], text=True).strip()
            require(actual, expected, path)
        for component in ("duckdb_mooncake", "moonlink"):
            tag = versions[component]["tag"]
            actual = subprocess.check_output(["git", "-C", str(ROOT / component), "rev-parse", f"refs/tags/{tag}^{{commit}}"], text=True).strip()
            require(actual, versions[component]["revision"], f"{component} {tag}")
    else:
        print("Source archive: Git revisions cannot be checked; use the recorded source manifest.")
    print(f"Version checks passed: pg_mooncake {release}, pg_duckdb {pg_duckdb_version}, pgrx {versions['pgrx']}.")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, subprocess.CalledProcessError, FileNotFoundError) as exc:
        sys.exit(str(exc))
