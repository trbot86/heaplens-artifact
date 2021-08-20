CC=clang++
C_CC=clang
Includes=`llvm-config-10 --cxxflags --ldflags`
Includes_2= 
LLVMLIBS=`llvm-config-10 --libs --system-libs`
CLANGLIBS=-Wno-unknown-warning-option -lclangTooling -lclangFrontendTool -lclangFrontend -lclangDriver -lclangSerialization -lclangCodeGen -lclangParse -lclangSema -lclangStaticAnalyzerFrontend -lclangStaticAnalyzerCheckers -lclangStaticAnalyzerCore -lclangAnalysis -lclangARCMigrate -lclangRewrite -lclangRewriteFrontend -lclangEdit -lclangAST -lclangASTMatchers -lclangLex -lclangBasic -lclang

all: parser malloctypedumper header_c header

run:
	./tool header.cpp

.PHONY: parser malloctypedumper clean run all

parser: clang_parser.cpp
	$(CC) $(Includes) clang_parser.cpp $(CLANGLIBS) $(LLVMLIBS) -g -o tool

malloctypedumper: malloctypedumper.cpp
	$(CC) $(Includes) -DMTDFNAME="\"_mm_malloc\"" -DDEBUG malloctypedumper.cpp $(CLANGLIBS) $(LLVMLIBS) -g -o malloctypedumper

replacer: source_replacements.cpp
	$(CC) $(Includes) source_replacements.cpp $(CLANGLIBS) $(LLVMLIBS) -g -o replacer

replacer_experimental: source_replacements.cpp
	$(CC) $(Includes) source_replacements.cpp $(CLANGLIBS) $(LLVMLIBS) -g -o replacer

header: header.cpp
	$(CC) /home/gautam/Desktop/sifter/type_analysis/header.cpp -g -o header -L../memhook/ -I../memhook/ -Wl,-rpath=../memhook/ -lmemhook -ldl

header_c: header.c
	$(C_CC) /home/gautam/Desktop/sifter/type_analysis/header.c -g -o header_c -L../memhook/ -I../memhook/ -Wl,-rpath=../memhook/ -lmemhook -ldl

clean:
	rm tool malloctypedumper replacer header header_c
