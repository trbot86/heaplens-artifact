CC=clang++
C_CC=clang
Includes=`llvm-config --cxxflags --ldflags` -L/lib/llvm-10/lib -fno-rtti
Includes_2= 
LLVMLIBS=`llvm-config --libs --system-libs`
# CLANGLIBS=-Wno-unknown-warning-option -lclangTooling -lclangToolingInclusions -lclangFrontendTool -lclangFrontend -lclangDriver -lclangSerialization -lclangCodeGen -lclangParse -lclangSema -lclangStaticAnalyzerFrontend -lclangStaticAnalyzerCheckers -lclangStaticAnalyzerCore -lclangAnalysis -lclangARCMigrate -lclangApplyReplacements -lclangRewrite -lclangRewriteFrontend -lclangEdit -lclangAST -lclangASTMatchers -lclangLex -lclangBasic -lclang
CLANGLIBS=-Wno-unknown-warning-option -Wl,--start-group -lclangAnalysis -lclangApplyReplacements -lclangARCMigrate -lclangAST -lclangASTMatchers -lclangBasic -lclangChangeNamespace -lclangCodeGen -lclangCrossTU -lclangDaemon -lclangDriver -lclangDynamicASTMatchers -lclangEdit -lclangFormat -lclangFrontend -lclangFrontendTool -lclangHandleCXX -lclangIncludeFixer -lclangIncludeFixerPlugin -lclangIndex -lclangLex -lclangMove -lclangParse -lclangQuery -lclangReorderFields -lclangRewrite -lclangRewriteFrontend -lclangSema -lclangSerialization -lclangStaticAnalyzerCheckers -lclangStaticAnalyzerCore -lclangStaticAnalyzerFrontend -lclangTidy -lclangTidyAndroidModule -lclangTidyBoostModule -lclangTidyBugproneModule -lclangTidyCERTModule -lclangTidyCppCoreGuidelinesModule -lclangTidyFuchsiaModule -lclangTidyGoogleModule -lclangTidyHICPPModule -lclangTidyLLVMModule -lclangTidyMiscModule -lclangTidyModernizeModule -lclangTidyMPIModule -lclangTidyObjCModule -lclangTidyPerformanceModule -lclangTidyPlugin -lclangTidyReadabilityModule -lclangTidyUtils -lclangTooling -lclangToolingASTDiff -lclangToolingCore -lclangToolingInclusions -lclangToolingRefactoring -lfindAllSymbols -Wl,--end-group -lz -lcurses -pthread

all: fieldandtypedumper malloctypedumper header_c header

run:
	./tool header.cpp

.PHONY: parser malloctypedumper clean run all

byte_reader: byte_rw.cpp
	$(CC) byte_rw.cpp -g -o byte_rw

fieldandtypedumper: clang_parser.cpp
	$(CC) $(Includes) -DMTDFNAME1="\"malloc\"" -DMTDFNAME2="\"realloc\"" -DMTDFNAME3="\"calloc\"" -DMTDFNAME4="\"reallocArray\"" -DMTDFNAME5="\"alloc\"" clang_parser.cpp $(CLANGLIBS) $(LLVMLIBS) -g -o fieldandtypedumper

malloctypedumper: malloctypedumper.cpp
	# $(CC) $(Includes) -DMTDFNAME="\"_mm_malloc\"" -DDEBUG malloctypedumper.cpp $(CLANGLIBS) $(LLVMLIBS) -g -o malloctypedumper
	$(CC) $(Includes) -DMTDFNAME="\"alloc\"" -DDEBUG malloctypedumper.cpp $(CLANGLIBS) $(LLVMLIBS) -g -o malloctypedumper

replacer: source_replacements.cpp
	$(CC) $(Includes) -DMTDFNAME="\"malloc\"" source_replacements.cpp $(CLANGLIBS) $(LLVMLIBS) -g -o replacer

experimental: replacer_experimental.cpp
	$(CC) $(Includes) -DMTDFNAME="\"alloc\""  -DMTDFLEN="5" replacer_experimental.cpp $(CLANGLIBS) $(LLVMLIBS) -g -o experimental

2experimental: replacer_experimental2.cpp
	$(CC) $(Includes) -DMTDFNAME="\"alloc\""  -DMTDFLEN="5" replacer_experimental2.cpp $(CLANGLIBS) $(LLVMLIBS) -g -o 2experimental
	
ctdcheck: ChangeMallocCheck.cpp ChangeMallocCheck.h
	$(CC) $(Includes) -DMTDFNAME="\"alloc\""  -DMTDFLEN="5" ChangeMallocCheck.cpp $(CLANGLIBS) $(LLVMLIBS) -g -o ctdcheck

header: header.cpp
	$(CC) /home/gspathak/sifter/type_analysis/header.cpp -g -o header -L../memhook/ -I../memhook/ -Wl,-rpath=../memhook/ -lmemhook -ldl

header_c: header.cpp
	$(C_CC) /home/gspathak/sifter/type_analysis/header.c -g -o header_c -L../memhook/ -I../memhook/ -Wl,-rpath=../memhook/ -lmemhook -ldl

clean:
	rm tool malloctypedumper replacer header header_c malloc_type_dump.txt info_dump binary_dump.txt fielddump.txt new_field_dump.txt new_fielddump.txt typedump.txt typeset_dump.txt fileset_dump.txt allocs.sqlite fixes.yaml