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
                                            clang-14 \
                                            libllvm-14-ocaml-dev \
                                            libllvm14 \
                                            llvm-14 \
                                            llvm-14-dev \
                                            llvm-14-doc \
                                            llvm-14-examples \
                                            llvm-14-runtime \
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
RUN ./llvm.sh 14
RUN locale-gen en_US.UTF-8
RUN pip3 install --upgrade pip
RUN pip3 install cmake==3.22.1
RUN ln /usr/local/bin/cmake /usr/bin/cmake