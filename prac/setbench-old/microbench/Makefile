FLAGS =
LDFLAGS =
GPP = g++

### if libpapi is installed but you do not want to use it, invoke make with extra argument "has_libpapi=0"
has_libpapi=$(shell ./_check_lib.sh papi)
ifneq ($(has_libpapi), 0)
	FLAGS += -DUSE_PAPI
	LDFLAGS += -lpapi
endif

### if libnuma is installed but you do not want to use it, invoke make with extra argument "has_libnuma=0"
has_libnuma=$(shell ./_check_lib.sh numa)
ifneq ($(has_libnuma), 0)
	FLAGS += -DUSE_LIBNUMA
	LDFLAGS += -lnuma
endif

use_asan=0
ifneq ($(use_asan), 0)
	LDFLAGS += -fsanitize=address -static-libasan
endif

use_asserts=0
ifeq ($(use_asserts), 0)
	FLAGS += -DNDEBUG
endif

use_fopenmp=1
ifeq ($(use_fopenmp), 1)
	FLAGS += -fopenmp
endif

use_timelines=0
ifeq ($(use_timelines), 1)
	FLAGS += -DMEASURE_TIMELINE_STATS
endif

no_optimize=0
ifeq ($(no_optimize), 1)
	FLAGS += -O0
else
	FLAGS += -O3
endif

FLAGS += -DMAX_THREADS_POW2=8
FLAGS += -DCPU_FREQ_GHZ=2.1 #$(shell ./experiments/get_cpu_ghz.sh)
FLAGS += -DMEMORY_STATS=if\(1\) -DMEMORY_STATS2=if\(0\)
FLAGS += -std=c++14 -mcx16 -gdwarf
FLAGS += -fno-omit-frame-pointer
# FLAGS += -DCALL_DEBUG_GC
#FLAGS += -DNO_CLEANUP_AFTER_WORKLOAD ### avoid executing data structure destructors, to save teardown time at the end of each trial (useful with massive trees)
#FLAGS += -DRAPID_RECLAMATION
FLAGS += -DPREFILL_INSERTION_ONLY
#FLAGS += -DMEASURE_REBUILDING_TIME
# FLAGS += -DMEASURE_TIMELINE_STATS
FLAGS += -DUSE_TREE_STATS
#FLAGS += -DOVERRIDE_PRINT_STATS_ON_ERROR
#FLAGS += -Wno-format
FLAGS += $(xargs)

LDFLAGS += -L../../../memhook/ -Wl,-rpath=../../../memhook/ -I../../../memhook/
LDFLAGS += -L../lib
LDFLAGS += -I./ -I../ `find ../common -type d | sed s/^/-I/`
LDFLAGS += -lpthread -lmemhook
LDFLAGS += -ldl
LDFLAGS += -mrtm

bin_dir=bin
dir_guard:
	@mkdir -p $(bin_dir)


################################################################################
#### BEGIN check for proper git cloning WITH SUBMODULES
################################################################################
define submodules_err_msg=

================================================================================
==== ERROR: CANNOT FIND SUBMODULES                                          ====
================================================================================
==== You most likely used the wrong git clone command...                    ====
====                                                                        ====
==== Note that a special argument is needed for cloning:                    ====
====   git clone git@gitlab.com:trbot86/setbench.git --recurse-submodules   ====
================================================================================
endef
dir_exists_tools=$(shell if [ -d "../tools" ]; then echo 1 ; else echo 0 ; fi )
dir_exists_recordmgr=$(shell if [ -d "../common/recordmgr" ]; then echo 1 ; else echo 0 ; fi )
num_files_tools=$(shell ls ../tools | wc -l 2>/dev/null )
num_files_recordmgr=$(shell ls ../common/recordmgr | wc -l 2>/dev/null )
ifeq ($(dir_exists_tools),0)
    $(error $(submodules_err_msg))
endif
ifeq ($(dir_exists_recordmgr),0)
    $(error $(submodules_err_msg))
endif
ifeq ($(num_files_tools),0)
    $(error $(submodules_err_msg))
endif
ifeq ($(num_files_recordmgr),0)
    $(error $(submodules_err_msg))
endif
################################################################################
#### END check for proper git cloning WITH SUBMODULES
################################################################################



MINIMAL_BINS=$(patsubst ../ds/%/minimal_example.cpp,%.minimal,$(wildcard ../ds/*/minimal_example.cpp))
minimal_%: dir_guard
	$(GPP) $(FLAGS) ../ds/$(@:minimal_%=%)/minimal_example.cpp -o $(bin_dir)/$@ $(LDFLAGS)

DATA_STRUCTURES=$(patsubst ../ds/%/adapter.h,%,$(wildcard ../ds/*/adapter.h))
RECLAIMERS=debra none
POOLS=none
ALLOCATORS=new

#DATA_STRUCTURES=$(patsubst ../ds/%/adapter.h,%,$(wildcard ../ds/brown_ext_ist*/adapter.h))
#DATA_STRUCTURES+=$(patsubst ../ds/%/adapter.h,%,$(wildcard ../ds/bronson*/adapter.h))
#DATA_STRUCTURES+=$(patsubst ../ds/%/adapter.h,%,$(wildcard ../ds/natarajan*/adapter.h))

#$(info $(DATA_STRUCTURES))

define make-custom-target =
ubench_$(1).alloc_$(2).reclaim_$(3).pool_$(4).out: dir_guard
	$(GPP) ./main.cpp -o $(bin_dir)/ubench_$(1).alloc_$(2).reclaim_$(3).pool_$(4).out -I../ds/$1 -DDS_TYPENAME=$(1) -DRECLAIM_TYPE=$(3) -DPOOL_TYPE=$(4) $(FLAGS) $(LDFLAGS)
all:: ubench_$(1).alloc_$(2).reclaim_$(3).pool_$(4).out
endef

$(foreach ds,$(DATA_STRUCTURES),$(foreach alloc,$(ALLOCATORS),$(foreach reclaim,$(RECLAIMERS),$(foreach pool,$(POOLS),$(eval $(call make-custom-target,$(ds),$(alloc),$(reclaim),$(pool)))))))

clean:
	rm $(bin_dir)/*.out
