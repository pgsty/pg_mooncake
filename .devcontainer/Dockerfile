FROM mcr.microsoft.com/devcontainers/rust:1-bookworm@sha256:99196945fec17043ebd2d802b01c9700a68e51722a009612fbc3ab31c1cf325d

RUN apt update \
 && apt install -y \
    bison \
    cmake \
    flex \
    libclang-dev \
    libcurl4-openssl-dev \
    libicu-dev \
    liblz4-dev \
    libreadline-dev \
    libssl-dev \
    mold \
    ninja-build \
    protobuf-compiler \
    zlib1g-dev \
 && rm -rf /var/lib/apt/lists/* \
 && ln -sf /usr/bin/mold /usr/bin/ld

USER vscode

RUN rustup toolchain install 1.99.1 --component clippy --component rustfmt \
 && cargo +1.99.1 install --locked cargo-pgrx@0.20.0 \
 && cargo +1.99.1 pgrx init --pg18 download

RUN git init -q "$HOME/vcpkg" \
 && git -C "$HOME/vcpkg" fetch --depth=1 https://github.com/microsoft/vcpkg.git ce613c41372b23b1f51333815feb3edd87ef8a8b \
 && git -C "$HOME/vcpkg" checkout --detach FETCH_HEAD \
 && "$HOME/vcpkg/bootstrap-vcpkg.sh" -disableMetrics

ENV VCPKG_TOOLCHAIN_PATH=/home/vscode/vcpkg/scripts/buildsystems/vcpkg.cmake

RUN wget -P "$HOME" https://raw.githubusercontent.com/cmrschwarz/rust-prettifier-for-lldb/c97ed7a6305725655fe3b636509cc639dce31890/rust_prettifier_for_lldb.py
