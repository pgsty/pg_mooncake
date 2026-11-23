PG_VERSION ?= pg18
PG_CONFIG ?= $(shell cargo pgrx info pg-config $(PG_VERSION))
PGRX_PG_CONFIG_PATH ?= $(PG_CONFIG)
ifneq ($(filter format install package pg_duckdb run test,$(MAKECMDGOALS)),)
export PG_CONFIG PGRX_PG_CONFIG_PATH
endif
JOBS ?= 4
DUCKDB_VERSION := v2.0.1
export DUCKDB_COMMIT = $(shell python3 -c 'import json; print(json.load(open("versions.json"))["duckdb"]["revision"])')
MOONCAKE_BUILD := duckdb_mooncake/build/release
MOONCAKE_REPOSITORY ?= $(shell $(PG_CONFIG) --sharedir)/extension/pg_mooncake
PACKAGE_DIR ?= $(CURDIR)/target/release/pg_mooncake-$(PG_VERSION)
PGRX_FLAGS = --no-default-features --features $(PG_VERSION),bgworker --pg-config $(PG_CONFIG) --cargo=--locked
REGRESS_DB ?= mooncake_regress
MAKEFLAGS += --no-print-directory

.PHONY: help clean check-versions duckdb_mooncake format install install-duckdb-mooncake package pg_duckdb run test

help:
	@echo "Usage: make <COMMAND> [OPTIONS]"
	@echo ""
	@echo "Commands:"
	@echo "  run           Build and run pg_mooncake for development"
	@echo "  install       Build and install pg_mooncake"
	@echo "  pg_duckdb     Build and install pg_duckdb"
	@echo "  duckdb_mooncake Build the DuckDB 2.0 Mooncake extension"
	@echo "  install-duckdb-mooncake Install it into a local extension repository"
	@echo "  package       Build an installation package for release"
	@echo "  format        Format the codebase"
	@echo "  test          Run SQL regressions against a configured test server"
	@echo "  clean         Remove build artifacts"
	@echo ""
	@echo "Options:"
	@echo "  PG_VERSION    pg15, pg16, pg17, pg18 (default), or pg19"

clean:
	@cargo clean

check-versions:
	python3 scripts/check_versions.py --check-toolchain

duckdb_mooncake: check-versions
	cmake -S duckdb_mooncake/duckdb -B $(MOONCAKE_BUILD) -G Ninja \
		-DCMAKE_BUILD_TYPE=Release -DOVERRIDE_GIT_DESCRIBE=$(DUCKDB_VERSION) \
		-DDUCKDB_EXTENSION_CONFIGS=$(CURDIR)/duckdb_mooncake/extension_config.cmake \
		-DEXTENSION_STATIC_BUILD=0 -DBUILD_UNITTESTS=OFF -DBUILD_SHELL=OFF
	cmake --build $(MOONCAKE_BUILD) --target mooncake_loadable_extension --parallel $(JOBS)

install-duckdb-mooncake: duckdb_mooncake
	install -d "$(DESTDIR)$(MOONCAKE_REPOSITORY)/$(DUCKDB_VERSION)/$$(cat $(MOONCAKE_BUILD)/duckdb_platform_out)"
	install -m 644 $(MOONCAKE_BUILD)/extension/mooncake/mooncake.duckdb_extension \
		"$(DESTDIR)$(MOONCAKE_REPOSITORY)/$(DUCKDB_VERSION)/$$(cat $(MOONCAKE_BUILD)/duckdb_platform_out)/"

format:
	@cargo fmt
	@cargo clippy

install: install-duckdb-mooncake
	@cargo pgrx install --release $(PGRX_FLAGS)

package: duckdb_mooncake
	@set -eu; mkdir -p "$(dir $(PACKAGE_DIR))"; \
	stage=$$(mktemp -d "$(dir $(PACKAGE_DIR)).pg_mooncake.XXXXXX"); \
	trap 'rm -rf "$$stage"' EXIT; \
	cargo pgrx package $(PGRX_FLAGS) --out-dir "$$stage"; \
	repository="$$stage$(MOONCAKE_REPOSITORY)/$(DUCKDB_VERSION)/$$(cat $(MOONCAKE_BUILD)/duckdb_platform_out)"; \
	install -d "$$repository"; \
	install -m 644 "$(MOONCAKE_BUILD)/extension/mooncake/mooncake.duckdb_extension" "$$repository/"; \
	python3 -c 'import os, sys; os.rename(sys.argv[1], sys.argv[2])' "$$stage" "$(PACKAGE_DIR)"

ifeq ($(wildcard pg_duckdb/.git),)
PG_DUCKDB_SOURCE_FLAGS = -o .git/modules/third_party/duckdb/HEAD \
	PG_DUCKDB_VERSION=$(shell python3 -c 'import json; print(json.load(open("versions.json"))["pg_duckdb"]["version"])')
endif

pg_duckdb: check-versions
	@$(MAKE) -C pg_duckdb $(PG_DUCKDB_SOURCE_FLAGS) install -j$(JOBS)

run: pg_duckdb install-duckdb-mooncake
	@cargo pgrx run $(PG_VERSION) --install-only --no-default-features --features $(PG_VERSION),bgworker --cargo=--locked
	@cargo pgrx start $(PG_VERSION) \
		--postgresql-conf "shared_preload_libraries=pg_duckdb,pg_mooncake" \
		--postgresql-conf "wal_level=logical" --postgresql-conf "duckdb.allow_community_extensions=true" \
		--postgresql-conf "duckdb.allow_unsigned_extensions=true" --postgresql-conf "mooncake.extension_repository=$(MOONCAKE_REPOSITORY)"
	@cargo pgrx connect $(PG_VERSION)

REGRESS_TESTS ?= setup sanity partitioned_table partitioned_existing drop writes identifiers renames freshness data_directory

test:
	mkdir -p target/regress
	$(shell $(PG_CONFIG) --pkglibdir)/pgxs/src/test/regress/pg_regress \
		--inputdir=tests/pg_regress --outputdir=target/regress \
		--load-extension=pg_duckdb --dbname=$(REGRESS_DB) $(REGRESS_TESTS)
