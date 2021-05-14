CC=clang++
C_CC=clang
Includes= /usr/lib/llvm-10/include/clang
Includes_2= 
Libs= /usr/lib/llvm-10/lib/
CLANGLIBS=-Wno-unknown-warning-option -lclangTooling -lclangFrontendTool -lclangFrontend -lclangDriver -lclangSerialization -lclangCodeGen -lclangParse -lclangSema -lclangStaticAnalyzerFrontend -lclangStaticAnalyzerCheckers -lclangStaticAnalyzerCore -lclangAnalysis -lclangARCMigrate -lclangRewrite -lclangRewriteFrontend -lclangEdit -lclangAST -lclangASTMatchers -lclangLex -lclangBasic -lclang

all: parser refactor replacer

run:
	./tool header.cpp

.PHONY: parser refactor clean run all

parser: clang_parser.cpp
	$(CC) `llvm-config-10 --cxxflags --ldflags` clang_parser.cpp $(CLANGLIBS) `llvm-config-10 --libs --system-libs` -g -o tool

refactor: source_refactor.cpp
	$(CC) `llvm-config-10 --cxxflags --ldflags` source_refactor.cpp $(CLANGLIBS) `llvm-config-10 --libs --system-libs` -g -o refactor

replacer: source_replacements.cpp
	$(CC) `llvm-config-10 --cxxflags --ldflags` source_replacements.cpp $(CLANGLIBS) `llvm-config-10 --libs --system-libs` -g -o replacer

replacer_experimental: source_replacements.cpp
	$(CC) `llvm-config-10 --cxxflags` -I/usr/lib/llvm-10/tools/clang/include -I/usr/lib/llvm-10/build/tools/clang/include source_replacements.cpp \
        -Wl,--start-group -lclangAST -lclangASTMatchers -lclangAnalysis -lclangBasic -lclangDriver -lclangEdit -lclangFrontend -lclangFrontendTool -lclangLex -lclangParse -lclangSema -lclangEdit -lclangRewrite -lclangRewriteFrontend -lclangStaticAnalyzerFrontend -lclangStaticAnalyzerCheckers -lclangStaticAnalyzerCore -lclangCrossTU -lclangIndex -lclangSerialization -lclangToolingCore -lclangTooling -lclangFormats -Wl,--end-group `llvm-config-10 --ldflags --libs --system-libs` -o replacer

header: header.cpp
	$(CC) header.cpp -o header

header_c: header.c
	$(C_CC) header.c -o header_c

clean:
	rm tool refactor replacer header header_c
