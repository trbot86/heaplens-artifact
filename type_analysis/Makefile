CC=clang++-14
C_CC=clang-14
Includes=`llvm-config-14 --cxxflags --ldflags` -L/lib/llvm-10/lib -fno-rtti
Includes_2=
LLVMLIBS=`llvm-config-14 --libs --system-libs`
# CLANGLIBS=-Wno-unknown-warning-option -lclangTooling -lclangToolingInclusions -lclangFrontendTool -lclangFrontend -lclangDriver -lclangSerialization -lclangCodeGen -lclangParse -lclangSema -lclangStaticAnalyzerFrontend -lclangStaticAnalyzerCheckers -lclangStaticAnalyzerCore -lclangAnalysis -lclangARCMigrate -lclangApplyReplacements -lclangRewrite -lclangRewriteFrontend -lclangEdit -lclangAST -lclangASTMatchers -lclangLex -lclangBasic -lclang
CLANGLIBS=-Wno-unknown-warning-option -Wl,--start-group -lclangAnalysis -lclangApplyReplacements -lclangARCMigrate -lclangAST -lclangASTMatchers -lclangBasic -lclangChangeNamespace -lclangCodeGen -lclangCrossTU -lclangDaemon -lclangDriver -lclangDynamicASTMatchers -lclangEdit -lclangFormat -lclangFrontend -lclangFrontendTool -lclangHandleCXX -lclangIncludeFixer -lclangIncludeFixerPlugin -lclangIndex -lclangLex -lclangMove -lclangParse -lclangQuery -lclangReorderFields -lclangRewrite -lclangRewriteFrontend -lclangSema -lclangSerialization -lclangStaticAnalyzerCheckers -lclangStaticAnalyzerCore -lclangStaticAnalyzerFrontend -lclangTidy -lclangTidyAndroidModule -lclangTidyBoostModule -lclangTidyBugproneModule -lclangTidyCERTModule -lclangTidyCppCoreGuidelinesModule -lclangTidyFuchsiaModule -lclangTidyGoogleModule -lclangTidyHICPPModule -lclangTidyLLVMModule -lclangTidyMiscModule -lclangTidyModernizeModule -lclangTidyMPIModule -lclangTidyObjCModule -lclangTidyPerformanceModule -lclangTidyPlugin -lclangTidyReadabilityModule -lclangTidyUtils -lclangTooling -lclangToolingASTDiff -lclangToolingCore -lclangToolingInclusions -lclangToolingRefactoring -lfindAllSymbols -Wl,--end-group -lz -lcurses -pthread

all: fieldandtypedumper malloctypedumper header_c header

run:
	./tool header.cpp

.PHONY: parser malloctypedumper clean run all

# NEEDED
byte_reader: byte_rw.cpp
	$(CC) byte_rw.cpp -g -o bin/byte_rw -lpthread -lrt

SRCS := $(wildcard convert_to_db/*.cpp)
HEADERS := $(wildcard convert_to_db/*.hpp)

bin/convert_to_db: $(SRCS) $(HEADERS)
	g++ $(SRCS) -g -o bin/convert_to_db -lsqlite3 -lpthread

# NEEDED
fieldandtypedumper: clang_parser.cpp
	$(CC) $(Includes) clang_parser.cpp $(CLANGLIBS) $(LLVMLIBS) -g -o bin/fieldandtypedumper

# NEEDED
malloctypedumper: malloctypedumper.cpp
	# $(CC) $(Includes) -DMTDFNAME="\"_mm_malloc\"" -DDEBUG malloctypedumper.cpp $(CLANGLIBS) $(LLVMLIBS) -g -o malloctypedumper
	$(CC) $(Includes) -DMTDFNAME="\"malloc\"" -DDEBUG malloctypedumper.cpp $(CLANGLIBS) $(LLVMLIBS) -g -o bin/malloctypedumper

clean:
	rm bin/*
