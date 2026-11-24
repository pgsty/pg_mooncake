# PostgreSQL 18 with the dependency versions in versions.json.
# Initialize submodules before building: git submodule update --init --recursive
FROM postgres:18.7-bookworm@sha256:194e55feb2597b1465dbee81cc9fd8d204566cd2eb42c8d22fd6c931a38781b1 AS postgres-base

FROM postgres-base AS build

ARG PG_CONFIG=/usr/lib/postgresql/18/bin/pg_config
ARG JOBS=4

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
    build-essential \
    ca-certificates \
    clang \
    cmake \
    curl \
    git \
    libclang-dev \
    libcurl4-openssl-dev \
    libicu-dev \
    liblz4-dev \
    libssl-dev \
    libxml2-dev \
    ninja-build \
    pkg-config \
    "postgresql-server-dev-18=${PG_VERSION}" \
    protobuf-compiler \
    python3 \
 && rm -rf /var/lib/apt/lists/*

RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal

ENV PATH="/root/.cargo/bin:$PATH"

WORKDIR /pg_mooncake

COPY rust-toolchain.toml ./
RUN rustup toolchain install

COPY Cargo.toml Cargo.lock Makefile pg_mooncake.control versions.json .gitmodules ./
COPY scripts scripts
RUN pgrx_version=$(sed -n 's/^pgrx = "=\{0,1\}\(.*\)"/\1/p' Cargo.toml) \
 && cargo install --locked "cargo-pgrx@$pgrx_version" \
 && cargo pgrx init --pg18 "$PG_CONFIG"

COPY pg_duckdb pg_duckdb
RUN test -f pg_duckdb/third_party/duckdb/CMakeLists.txt \
 && DUCKDB_COMMIT="$(python3 -c 'import json; print(json.load(open("versions.json"))["duckdb"]["revision"])')" \
    make -C pg_duckdb -f Makefile -f ../scripts/pg_duckdb.mk -o .git/modules/third_party/duckdb/HEAD \
    install -j"$JOBS" PG_CONFIG="$PG_CONFIG"

COPY duckdb_mooncake duckdb_mooncake
COPY moonlink moonlink
COPY src src
COPY sql sql
RUN make package PG_VERSION=pg18 PG_CONFIG="$PG_CONFIG" JOBS="$JOBS"

FROM postgres-base

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
    ca-certificates \
    libcurl4 \
    liblz4-1 \
 && test "$(dpkg-query -W -f='${Version}' postgresql-18)" = "$PG_VERSION" \
 && rm -rf /var/lib/apt/lists/*

COPY --from=build /usr/lib/postgresql/18/lib/pg_duckdb.so /usr/lib/postgresql/18/lib/libduckdb.so /usr/lib/postgresql/18/lib/
COPY --from=build /usr/share/postgresql/18/extension/pg_duckdb* /usr/share/postgresql/18/extension/
COPY --from=build /pg_mooncake/target/release/pg_mooncake-pg18/ /

RUN install -d -o postgres -g postgres /var/lib/postgresql/18 \
 && install -d -o postgres -g postgres -m 0700 /var/lib/postgresql/18/mooncake \
 && cat >> /usr/share/postgresql/postgresql.conf.sample <<EOF
duckdb.allow_community_extensions = true
duckdb.allow_unsigned_extensions = true
mooncake.extension_repository = '/usr/share/postgresql/18/extension/pg_mooncake'
mooncake.data_directory = '/var/lib/postgresql/18/mooncake'
shared_preload_libraries = 'pg_duckdb,pg_mooncake'
wal_level = logical
EOF
