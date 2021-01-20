# For more information, installation and usage, visit the SetBench Wiki!
https://gitlab.com/trbot86/setbench/wikis/home

Note that cloning this repo is complicated by the existence of *submodules*:

```
git clone git@gitlab.com:trbot86/setbench.git --recurse-submodules
```

## Setting up SetBench on a clean install of Ubuntu 20.04

Installing necessary build tools, libraries and python packages:
```
sudo apt install build-essential make g++ git libnuma-dev numactl python3 python3-pip
pip3 install numpy matplotlib pandas seaborn
```

Installing LibPAPI (needed for per-operation cache-miss counts, cycle counts, etc.):
```
git clone https://bitbucket.org/icl/papi.git
cd papi/src
./configure
sudo sh -c "echo 2 > /proc/sys/kernel/perf_event_paranoid"
./configure
make
make test
sudo make install
sudo ldconfig
```

Clone and build SetBench:
```
git clone git@gitlab.com:trbot86/setbench.git --recurse-submodules
cd setbench/microbench
make -j all
cd ../macrobench
./compile.sh
```
For more instructions see the SetBench Wiki, as well as `setbench/microbench_experiments/example/instructions_data.ipynb` (a Jupyter notebook tutorial that we recommend opening in VSCode).