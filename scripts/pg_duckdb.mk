PG_DUCKDB_VERSION := $(shell python3 -c 'import json; print(json.load(open("../versions.json"))["pg_duckdb"]["version"])')
# PGXS has already copied PG_CPPFLAGS into CPPFLAGS when the upstream object rule runs.
src/pgduckdb.o src/pgduckdb.bc: override CPPFLAGS += -DPG_DUCKDB_VERSION='"$(PG_DUCKDB_VERSION)"'
src/pgduckdb.o src/pgduckdb.bc: ../versions.json ../scripts/pg_duckdb.mk
