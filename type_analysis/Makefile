CC=clang++
C_CC=clang
Includes=`llvm-config-10 --cxxflags --ldflags`
Includes_2= 
LLVMLIBS=`llvm-config-10 --libs --system-libs`
CLANGLIBS=-Wno-unknown-warning-option -lclangTooling -lclangFrontendTool -lclangFrontend -lclangDriver -lclangSerialization -lclangCodeGen -lclangParse -lclangSema -lclangStaticAnalyzerFrontend -lclangStaticAnalyzerCheckers -lclangStaticAnalyzerCore -lclangAnalysis -lclangARCMigrate -lclangRewrite -lclangRewriteFrontend -lclangEdit -lclangAST -lclangASTMatchers -lclangApplyReplacements -lclangLex -lclangBasic -lclang

all: fieldandtypedumper malloctypedumper header_c header

run:
	./tool header.cpp

.PHONY: parser malloctypedumper clean run all

byte_reader: byte_rw.cpp
	$(CC) byte_rw.cpp -g -o byte_rw

fieldandtypedumper: clang_parser.cpp
	$(CC) $(Includes) clang_parser.cpp $(CLANGLIBS) $(LLVMLIBS) -g -o fieldandtypedumper

malloctypedumper: malloctypedumper.cpp
	# $(CC) $(Includes) -DMTDFNAME="\"_mm_malloc\"" -DDEBUG malloctypedumper.cpp $(CLANGLIBS) $(LLVMLIBS) -g -o malloctypedumper
	$(CC) $(Includes) -DMTDFNAME="\"malloc\"" -DDEBUG malloctypedumper.cpp $(CLANGLIBS) $(LLVMLIBS) -g -o malloctypedumper

replacer: source_replacements.cpp
	$(CC) $(Includes) source_replacements.cpp $(CLANGLIBS) $(LLVMLIBS) -g -o replacer

replacer_experimental: source_replacements.cpp
	$(CC) $(Includes) source_replacements.cpp $(CLANGLIBS) $(LLVMLIBS) -g -o replacer

header: header.cpp
	$(CC) /home/gspathak/sifter/type_analysis/header.cpp -g -o header -L../memhook/ -I../memhook/ -Wl,-rpath=../memhook/ -lmemhook -ldl

header_c: header.c
	$(C_CC) /home/gspathak/sifter/type_analysis/header.c -g -o header_c -L../memhook/ -I../memhook/ -Wl,-rpath=../memhook/ -lmemhook -ldl

clean:
	rm tool malloctypedumper replacer header header_c malloc_type_dump.txt info_dump binary_dump.txt fielddump.txt new_field_dump.txt new_fielddump.txt typedump.txt typeset_dump.txt fileset_dump.txt allocs.sqlite
