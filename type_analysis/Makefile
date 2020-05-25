CC=clang++
Includes= /usr/lib/llvm-6.0/include/
Libs= /usr/lib/llvm-6.0/lib/
CLANGLIBS = -Wno-unknown-warning-option -lclangTooling -lclangFrontendTool -lclangFrontend -lclangDriver -lclangSerialization -lclangCodeGen -lclangParse -lclangSema -lclangStaticAnalyzerFrontend -lclangStaticAnalyzerCheckers -lclangStaticAnalyzerCore -lclangAnalysis -lclangARCMigrate -lclangRewrite -lclangRewriteFrontend -lclangEdit -lclangAST -lclangASTMatchers -lclangLex -lclangBasic -lclang

all: parser refactor

run:
	./tool header.cpp

.PHONY: parser refactor visitor cursor clean run all

parser: clang_parser.cpp
	clang++ `llvm-config --cxxflags --ldflags` clang_parser.cpp $(CLANGLIBS) `llvm-config --libs --system-libs` -g -o tool

refactor: source_refactor.cpp
	clang++ `llvm-config --cxxflags --ldflags` source_refactor.cpp $(CLANGLIBS) `llvm-config --libs --system-libs` -g -o refactor

visitor:
	clang++ `llvm-config --cxxflags --ldflags` astvisitor.cpp $(CLANGLIBS) `llvm-config --libs --system-libs` -g -o visitor

cursor:
	clang++ `llvm-config --cxxflags --ldflags` astvisitor.cpp $(CLANGLIBS) `llvm-config --libs --system-libs` -g -o cursor

clean:
	rm clang_parser.out
	rm tool
	rm refactor
