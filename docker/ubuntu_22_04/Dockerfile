FROM ubuntu:22.04

ENV DEBIAN_FRONTEND noninteractive

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
                                            clang-10 \
                                            clang-tools-10 \
                                            clang-10-doc \
                                            libclang-common-10-dev \
                                            libclang-10-dev \
                                            libclang1-10 \
                                            clang-format-10 \
                                            python3-clang-10 \
                                            clangd-10 \
                                            clang-tidy-10 \
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
                                            linux-tools-common \
                                            linux-tools-generic \
                                            linux-tools-`uname -r` \
                                            autoconf

COPY . /root/sifter
WORKDIR /root/sifter

RUN chmod +x llvm.sh
RUN ./llvm.sh 10
RUN locale-gen en_US.UTF-8
RUN pip3 install --upgrade pip
RUN pip3 install cmake==3.14.3
RUN ln /usr/local/bin/cmake /usr/bin/cmake