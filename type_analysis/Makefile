CC=clang++-10
C_CC=clang-10
Includes=`llvm-config-10 --cxxflags --ldflags` -L/lib/llvm-10/lib -fno-rtti
Includes_2=
LLVMLIBS=`llvm-config-10 --libs --system-libs`
# CLANGLIBS=-Wno-unknown-warning-option -lclangTooling -lclangToolingInclusions -lclangFrontendTool -lclangFrontend -lclangDriver -lclangSerialization -lclangCodeGen -lclangParse -lclangSema -lclangStaticAnalyzerFrontend -lclangStaticAnalyzerCheckers -lclangStaticAnalyzerCore -lclangAnalysis -lclangARCMigrate -lclangApplyReplacements -lclangRewrite -lclangRewriteFrontend -lclangEdit -lclangAST -lclangASTMatchers -lclangLex -lclangBasic -lclang
CLANGLIBS=-Wno-unknown-warning-option -Wl,--start-group -lclangAnalysis -lclangApplyReplacements -lclangARCMigrate -lclangAST -lclangASTMatchers -lclangBasic -lclangChangeNamespace -lclangCodeGen -lclangCrossTU -lclangDaemon -lclangDriver -lclangDynamicASTMatchers -lclangEdit -lclangFormat -lclangFrontend -lclangFrontendTool -lclangHandleCXX -lclangIncludeFixer -lclangIncludeFixerPlugin -lclangIndex -lclangLex -lclangMove -lclangParse -lclangQuery -lclangReorderFields -lclangRewrite -lclangRewriteFrontend -lclangSema -lclangSerialization -lclangStaticAnalyzerCheckers -lclangStaticAnalyzerCore -lclangStaticAnalyzerFrontend -lclangTidy -lclangTidyAndroidModule -lclangTidyBoostModule -lclangTidyBugproneModule -lclangTidyCERTModule -lclangTidyCppCoreGuidelinesModule -lclangTidyFuchsiaModule -lclangTidyGoogleModule -lclangTidyHICPPModule -lclangTidyLLVMModule -lclangTidyMiscModule -lclangTidyModernizeModule -lclangTidyMPIModule -lclangTidyObjCModule -lclangTidyPerformanceModule -lclangTidyPlugin -lclangTidyReadabilityModule -lclangTidyUtils -lclangTooling -lclangToolingASTDiff -lclangToolingCore -lclangToolingInclusions -lclangToolingRefactoring -lfindAllSymbols -Wl,--end-group -lz -lcurses -pthread

all: fieldandtypedumper malloctypedumper header_c header

run:
	./tool header.cpp

.PHONY: parser malloctypedumper clean run all

# NEEDED
byte_reader: byte_rw.cpp
	$(CC) byte_rw.cpp -g -o bin/byte_rw -lpthread -lrt

convert_to_db: convert_to_db.cpp
	g++ convert_to_db.cpp -g -o bin/convert_to_db -lsqlite3

# NEEDED
fieldandtypedumper: clang_parser.cpp
	$(CC) $(Includes) -DMTDFNAME1="\"malloc\"" -DMTDFNAME2="\"realloc\"" -DMTDFNAME3="\"calloc\"" -DMTDFNAME4="\"reallocArray\"" -DMTDFNAME5="\"alloc\"" clang_parser.cpp $(CLANGLIBS) $(LLVMLIBS) -g -o bin/fieldandtypedumper

# NEEDED
malloctypedumper: malloctypedumper.cpp
	# $(CC) $(Includes) -DMTDFNAME="\"_mm_malloc\"" -DDEBUG malloctypedumper.cpp $(CLANGLIBS) $(LLVMLIBS) -g -o malloctypedumper
	$(CC) $(Includes) -DMTDFNAME="\"malloc\"" -DDEBUG malloctypedumper.cpp $(CLANGLIBS) $(LLVMLIBS) -g -o bin/malloctypedumper

replacer: source_replacements.cpp
	$(CC) $(Includes) -DMTDFNAME="\"malloc\"" source_replacements.cpp $(CLANGLIBS) $(LLVMLIBS) -g -o replacer

experimental: replacer_experimental.cpp
	$(CC) $(Includes) -DMTDFNAME="\"alloc\""  -DMTDFLEN="5" replacer_experimental.cpp $(CLANGLIBS) $(LLVMLIBS) -g -o experimental

2experimental: replacer_experimental2.cpp
	$(CC) $(Includes) -DMTDFNAME="\"alloc\""  -DMTDFLEN="5" replacer_experimental2.cpp $(CLANGLIBS) $(LLVMLIBS) -g -o 2experimental

ctdcheck: ChangeMallocCheck.cpp ChangeMallocCheck.h
	$(CC) $(Includes) -DMTDFNAME="\"alloc\""  -DMTDFLEN="5" ChangeMallocCheck.cpp $(CLANGLIBS) $(LLVMLIBS) -g -o ctdcheck

# TEST
header: header.cpp
	$(CC) /mnt/c/Users/Peach/OneDrive/Desktop/Programming/test_memvis/sifter/type_analysis/header.cpp -g -o header -L../memhook/ -I/mnt/c/Users/Peach/OneDrive/Desktop/Programming/test_memvis/sifter/type_analysis/ -I../memhook/ -Wl,-rpath=../memhook/ -lmemhook -ldl

# TEST
header_c: header.cpp
	$(C_CC) /mnt/c/Users/Peach/OneDrive/Desktop/Programming/test_memvis/sifter/type_analysis/header.c -g -o header_c -L../memhook/ -I/mnt/c/Users/Peach/OneDrive/Desktop/Programming/test_memvis/sifter/type_analysis/ -I../memhook/ -Wl,-rpath=../memhook/ -lmemhook -ldl

clean:
	rm byte_rw experimental 2experimental fieldandtypedumper tool malloctypedumper replacer header header_c malloc_type_dump.txt info_dump fielddump.txt new_field_dump.txt new_fielddump.txt typedump.txt fixes.yaml fix.yaml new_info_t_dump.txt *.pyc bin/*
