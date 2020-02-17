CC=g++
Includes=
Libs=
.PHONY: clean

all:
	(cd memhook && make all)
	(cd type_analysis && make refactor)

clean:
	rm memhook/libmemhook.so info_t_dump.txt type_analysis/refactor