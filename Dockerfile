# PostgreSQL 18 with pg_duckdb 1.2.1, duckdb_mooncake v0.0.3, and pg_mooncake 0.3.1.
# Initialize submodules before building: git submodule update --init --recursive
FROM postgres:18 AS build

ARG PG_CONFIG=/usr/lib/postgresql/18/bin/pg_config

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
    postgresql-server-dev-18 \
    protobuf-compiler \
    python3 \
 && rm -rf /var/lib/apt/lists/*

RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal

ENV PATH="/root/.cargo/bin:$PATH"

WORKDIR /pg_mooncake

COPY rust-toolchain.toml ./
RUN rustup toolchain install

COPY Cargo.toml Cargo.lock Makefile pg_mooncake.control versions.json ./
COPY scripts scripts
RUN pgrx_version=$(sed -n 's/^pgrx = "=\{0,1\}\(.*\)"/\1/p' Cargo.toml) \
 && cargo install --locked "cargo-pgrx@$pgrx_version" \
 && cargo pgrx init --pg18 "$PG_CONFIG"

COPY pg_duckdb pg_duckdb
RUN mkdir -p pg_duckdb/.git/modules/third_party/duckdb \
 && touch pg_duckdb/.git/modules/third_party/duckdb/HEAD \
 && make -C pg_duckdb install -j"$(nproc)" PG_CONFIG="$PG_CONFIG"

COPY duckdb_mooncake duckdb_mooncake
COPY moonlink moonlink
COPY src src
RUN make package PG_VERSION=pg18 PG_CONFIG="$PG_CONFIG" JOBS="$(nproc)"

FROM postgres:18

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
    ca-certificates \
    libcurl4t64 \
    liblz4-1 \
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
