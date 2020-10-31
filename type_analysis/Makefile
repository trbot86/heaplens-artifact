CC=clang++-6.0
Includes= /usr/lib/llvm-6.0/include/
Libs= /usr/lib/llvm-6.0/lib/
CLANGLIBS=-Wno-unknown-warning-option -lclangTooling -lclangFrontendTool -lclangFrontend -lclangDriver -lclangSerialization -lclangCodeGen -lclangParse -lclangSema -lclangStaticAnalyzerFrontend -lclangStaticAnalyzerCheckers -lclangStaticAnalyzerCore -lclangAnalysis -lclangARCMigrate -lclangRewrite -lclangRewriteFrontend -lclangEdit -lclangAST -lclangASTMatchers -lclangLex -lclangBasic -lclang

all: parser refactor replacer

run:
	./tool header.cpp

.PHONY: parser refactor clean run all

parser: clang_parser.cpp
	$(CC) `llvm-config-6.0 --cxxflags --ldflags` clang_parser.cpp $(CLANGLIBS) `llvm-config-6.0 --libs --system-libs` -g -o tool

refactor: source_refactor.cpp
	$(CC) `llvm-config-6.0 --cxxflags --ldflags` source_refactor.cpp $(CLANGLIBS) `llvm-config-6.0 --libs --system-libs` -g -o refactor

replacer: source_replacements.cpp
	$(CC) `llvm-config-6.0 --cxxflags --ldflags` source_replacements.cpp $(CLANGLIBS) `llvm-config-6.0 --libs --system-libs` -g -o replacer

replacer_experimental: source_replacements.cpp
	$(CC) `llvm-config-6.0 --cxxflags` -I/usr/lib/llvm-6.0/tools/clang/include -I/usr/lib/llvm-6.0/build/tools/clang/include source_replacements.cpp \
        -Wl,--start-group -lclangAST -lclangASTMatchers -lclangAnalysis -lclangBasic -lclangDriver -lclangEdit -lclangFrontend -lclangFrontendTool -lclangLex -lclangParse -lclangSema -lclangEdit -lclangRewrite -lclangRewriteFrontend -lclangStaticAnalyzerFrontend -lclangStaticAnalyzerCheckers -lclangStaticAnalyzerCore -lclangCrossTU -lclangIndex -lclangSerialization -lclangToolingCore -lclangTooling -lclangFormat -Wl,--end-group `llvm-config-6.0 --ldflags --libs --system-libs` -o replacer

clean:
	rm tool refactor
