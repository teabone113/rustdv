# Reproducible environment for Rust for RTL Verification:
# Rust toolchain + Icarus Verilog + Verilator + Python.
#
# Used by the Codespaces devcontainer (.devcontainer/devcontainer.json)
# and for local work:
#
#   docker build -t rustdv -f docker/Dockerfile .
#   docker run -it --rm -v "$PWD":/work -w /work rustdv bash
#   python3 output/regression/regress.py
#
# CI uses the same pinned Verilator installer (see .github/workflows/ci.yml).

FROM rust:1-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
        iverilog \
        autoconf \
        flex \
        bison \
        help2man \
        pkg-config \
        libfl-dev \
        zlib1g-dev \
        liblz4-dev \
        curl \
        ca-certificates \
        make \
        g++ \
        python3 \
        git \
    && rm -rf /var/lib/apt/lists/*

COPY ci/install-verilator.sh /usr/local/src/install-verilator.sh
RUN bash /usr/local/src/install-verilator.sh /usr/local

# Sanity: every tool the regression system reaches for.
RUN cargo --version && rustc --version && iverilog -V | head -1 \
    && verilator --version && python3 --version
