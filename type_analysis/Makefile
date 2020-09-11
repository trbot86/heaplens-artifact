CC=clang++-6.0
Includes= /usr/lib/llvm-6.0/include/
Libs= /usr/lib/llvm-6.0/lib/
CLANGLIBS = -Wno-unknown-warning-option -lclangTooling -lclangFrontendTool -lclangFrontend -lclangDriver -lclangSerialization -lclangCodeGen -lclangParse -lclangSema -lclangStaticAnalyzerFrontend -lclangStaticAnalyzerCheckers -lclangStaticAnalyzerCore -lclangAnalysis -lclangARCMigrate -lclangRewrite -lclangRewriteFrontend -lclangEdit -lclangAST -lclangASTMatchers -lclangLex -lclangBasic -lclang

all: parser refactor

run:
	./tool header.cpp

.PHONY: parser refactor clean run all

parser: clang_parser.cpp
	$(CC) `llvm-config-6.0 --cxxflags --ldflags` clang_parser.cpp $(CLANGLIBS) `llvm-config-6.0 --libs --system-libs` -g -o tool

refactor: source_refactor.cpp
	$(CC) `llvm-config-6.0 --cxxflags --ldflags` source_refactor.cpp $(CLANGLIBS) `llvm-config-6.0 --libs --system-libs` -g -o refactor

clean:
	rm tool refactor
