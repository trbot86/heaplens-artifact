FROM node:18.18.2-bullseye-slim AS node
FROM ubuntu:22.04
ENV DEBIAN_FRONTEND=noninteractive NEXT_TELEMETRY_DISABLED=1 \
    OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 MPLBACKEND=Agg
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl wget gnupg lsb-release software-properties-common \
    build-essential cmake git patch pkg-config autoconf automake libtool \
    python3 python3-pip python3-venv python3-dev python3-yaml \
    clang-14 clang-tools-14 clang-tidy-14 llvm-14-dev libclang-14-dev \
    libclang-common-14-dev libclang-cpp14-dev libnuma-dev numactl \
    libsqlite3-dev sqlite3 libtbb-dev libgflags-dev libncurses-dev \
    zlib1g-dev libbz2-dev liblz4-dev libzstd-dev libsnappy-dev \
    libevent-dev libssl-dev libpcre3-dev libjemalloc-dev libmimalloc-dev \
    bear parallel time unzip zip dos2unix linux-tools-generic \
    && rm -rf /var/lib/apt/lists/*
# HeapLENS targets LLVM 14.0.6; Jammy's initial archive shipped 14.0.0.
RUN curl -fsSL https://apt.llvm.org/llvm-snapshot.gpg.key -o /tmp/llvm.key \
    && gpg --dearmor -o /usr/share/keyrings/llvm.gpg /tmp/llvm.key \
    && echo 'deb [signed-by=/usr/share/keyrings/llvm.gpg] https://apt.llvm.org/jammy/ llvm-toolchain-jammy-14 main' > /etc/apt/sources.list.d/llvm14.list \
    && apt-get update && apt-get install -y --no-install-recommends \
       clang-14 clang-tools-14 clang-tidy-14 llvm-14-dev libclang-14-dev libclang-cpp14-dev \
    && rm -rf /var/lib/apt/lists/*
RUN find /usr/lib/linux-tools -type f -name perf -exec ln -sf '{}' /usr/local/bin/perf \; \
    && python3 -m venv /opt/heaplens-python
ENV PATH="/opt/heaplens-python/bin:${PATH}"
RUN python3 -m pip install --no-cache-dir pip==24.2 setuptools==75.1.0 wheel==0.44.0 pybind11==2.13.6
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx
COPY sifter_vis_d3/server/requirements.txt /tmp/heaplens-requirements.txt
RUN python3 -m pip install --no-cache-dir -r /tmp/heaplens-requirements.txt
COPY sifter_vis_d3/sifter/package.json sifter_vis_d3/sifter/package-lock.json /opt/heaplens-ui/
RUN cd /opt/heaplens-ui && npm ci --no-audit --no-fund
RUN python3 -m pip install --no-cache-dir PyYAML==6.0.2 \
    && apt-get update && apt-get install -y --no-install-recommends bc \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /root/sifter
CMD ["bash"]
