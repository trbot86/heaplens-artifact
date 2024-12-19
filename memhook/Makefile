CC=g++
CFLAGS= -fPIC -g -O2
Includes= /usr/lib/llvm-6.0/include/
Libs=
OBJ= memhook.o hash.o
DEPS=hash.h memhook.h memhook_interface.h memstamp.h memhook_xoshiro256p.h

ifdef MEMHOOK_ASCYLIB
	CFLAGS += -DMEMHOOK_ASCYLIB
endif

ifdef MEMHOOK_C_LOG
	CFLAGS += -DMEMHOOK_C_LOG
endif

ifdef USE_RALLOC
	CFLAGS += -DUSE_RALLOC
endif

libmemhook.so: $(OBJ)
	$(CC) -o $@ $^ -lrt -shared $(CFLAGS)

hash.o: hash.cpp $(DEPS)
	$(CC) -c -o $@ $< $(CFLAGS)

memhook.o: memhook.cpp $(DEPS)
	$(CC) -c -o $@ $< $(CFLAGS)

# %.o: %.c $(DEPS)
# 	$(CC) -c -o $@ $< $(CFLAGS)

# hash.o: hash.cpp hash.h
# 	$(CC) hash.cpp -shared -fPIC -g -lrt -O2 -c

hash_test: hash.cpp hash.h
	$(CC) hash.cpp -fPIC -g -lrt -pthread -O2 -o hash_test

# link:
# 	$(CC) memhook.cpp memalloc.cpp -pthread -Wall -g -o b.out

# db:
# 	$(CC) savetodb.cpp -lsqlite3 -g -o database.out

# prac:
# 	$(CC) a.cpp -I./ -L./ -Wl,-rpath=./ -pthread -lmemhook -g -o a.out

# sifter:
# 	$(CC) -W -Wall -fmessage-length=0 -Os -fomit-frame-pointer analyze.cpp -lsqlite3 -g -o sifter

install:
	cp libmemhook.so ../prac/setbench-master/lib
	cp memhook.h ../prac/setbench-master/microbench

clean:
	rm libmemhook.so *.o
