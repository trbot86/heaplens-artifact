FROM ubuntu:18.04

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
                                            libelf-dev


COPY . /root/sifter
WORKDIR /root/sifter

RUN git clone --depth 1 https://git.kernel.org/pub//scm/linux/kernel/git/torvalds/linux.git
WORKDIR /root/sifter/linux/tools/perf
RUN make NO_LIBTRACEEVENT=1
RUN cp perf /usr/bin
WORKDIR /root/sifter
RUN rm -rf linux

RUN chmod +x llvm.sh
RUN ./llvm.sh 10
RUN locale-gen en_US.UTF-8
RUN pip3 install --upgrade pip
RUN pip3 install cmake==3.14.3
RUN ln /usr/local/bin/cmake /usr/bin/cmake

# WORKDIR clang-tidy-standalone
# RUN mkdir build
# WORKDIR build
# RUN cmake ..
# RUN cmake --build .

# ENV PATH="${PATH}:/root/sifter/clang+llvm-10.0.0-x86_64-linux-gnu-ubuntu-18.04/bin"

# RUN echo "/root/sifter/clang+llvm-10.0.0-x86_64-linux-gnu-ubuntu-18.04/lib" >> /etc/ld.so.conf.d/llvmlibs.conf
# RUN ldconfig

# RUN echo "alias python=python3" >> ~/.bash_aliases
# RUN source ~/.bash_aliases