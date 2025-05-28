FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get upgrade -y && apt-get install -y \
                                            build-essential \
                                            make \
                                            g++ \
                                            git \
                                            time \
                                            libnuma-dev \
                                            numactl \
                                            dos2unix \
                                            parallel \
                                            python3 \
                                            python3-pip \
                                            python3-yaml \
                                            zip \
                                            bear \
                                            vim \
                                            clang-14 \
                                            clang-tools-14 \
                                            clang-14-doc \
                                            libclang-common-14-dev \
                                            libclang-14-dev \
                                            libclang1-14 \
                                            clang-format-14 \
                                            python3-clang-14 \
                                            clangd-14 \
                                            clang-tidy-14 \
                                            zlib1g-dev \
                                            lsb-release \
                                            wget \
                                            software-properties-common \
                                            gnupg \
                                            locales \
                                            sqlite3 \
                                            libsqlite3-dev \
                                            libncurses-dev \
                                            pkg-config \
                                            flex \
                                            bison \
                                            libelf-dev \
                                            # linux-tools-common \
                                            # linux-tools-generic \
                                            # linux-tools-`uname -r` \
                                            autoconf

COPY . /root/sifter
WORKDIR /root/sifter

RUN git clone --depth 1 https://git.kernel.org/pub//scm/linux/kernel/git/torvalds/linux.git
WORKDIR /root/sifter/linux/tools/perf
RUN make NO_LIBTRACEEVENT=1
RUN cp perf /usr/bin
WORKDIR /root/sifter
RUN rm -rf linux

RUN chmod +x llvm.sh
RUN ./llvm.sh 14
RUN locale-gen en_US.UTF-8
RUN pip3 install --upgrade pip
RUN pip3 install cmake==3.22.1
RUN ln /usr/local/bin/cmake /usr/bin/cmake