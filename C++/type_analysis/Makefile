CC=clang++
Includes= /usr/lib/llvm-6.0/include/
Libs= /usr/lib/llvm-6.0/lib/
CLANGLIBS=`llvm-config --cxxflags --ldflags` -lclang -lLLVM
CLANGLIBS2 = -lclangTooling -lclangFrontendTool -lclangFrontend -lclangDriver -lclangSerialization -lclangCodeGen -lclangParse -lclangSema -lclangStaticAnalyzerFrontend -lclangStaticAnalyzerCheckers -lclangStaticAnalyzerCore -lclangAnalysis -lclangARCMigrate -lclangRewrite -lclangRewriteFrontend -lclangEdit -lclangAST -lclangASTMatchers -lclangLex -lclangBasic -lclang

run:
	./tool header.cpp

all: clang_parser.cpp
	clang++ `llvm-config --cxxflags --ldflags` clang_parser.cpp $(CLANGLIBS2) `llvm-config --libs --system-libs` -g -o tool

refactor: source_refactor.cpp
	clang++ `llvm-config --cxxflags --ldflags` source_refactor.cpp $(CLANGLIBS2) `llvm-config --libs --system-libs` -g -o refactor

visitor:
	clang++ `llvm-config --cxxflags --ldflags` astvisitor.cpp $(CLANGLIBS2) `llvm-config --libs --system-libs` -g -o visitor

cursor:
	clang++ `llvm-config --cxxflags --ldflags` astvisitor.cpp $(CLANGLIBS2) `llvm-config --libs --system-libs` -g -o cursor

clean:
	rm clang_parser.out
	rm tool
	rm refactor