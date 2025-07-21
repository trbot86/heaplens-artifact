CC=clang++-14
C_CC=clang-14
Includes=`llvm-config-14 --cxxflags --ldflags` -L/lib/llvm-10/lib -fno-rtti
Includes_2=
LLVMLIBS=`llvm-config-14 --libs --system-libs`
# CLANGLIBS=-Wno-unknown-warning-option -lclangTooling -lclangToolingInclusions -lclangFrontendTool -lclangFrontend -lclangDriver -lclangSerialization -lclangCodeGen -lclangParse -lclangSema -lclangStaticAnalyzerFrontend -lclangStaticAnalyzerCheckers -lclangStaticAnalyzerCore -lclangAnalysis -lclangARCMigrate -lclangApplyReplacements -lclangRewrite -lclangRewriteFrontend -lclangEdit -lclangAST -lclangASTMatchers -lclangLex -lclangBasic -lclang
CLANGLIBS=-Wno-unknown-warning-option -Wl,--start-group -lclangAnalysis -lclangApplyReplacements -lclangARCMigrate -lclangAST -lclangASTMatchers -lclangBasic -lclangChangeNamespace -lclangCodeGen -lclangCrossTU -lclangDaemon -lclangDriver -lclangDynamicASTMatchers -lclangEdit -lclangFormat -lclangFrontend -lclangFrontendTool -lclangHandleCXX -lclangIncludeFixer -lclangIncludeFixerPlugin -lclangIndex -lclangLex -lclangMove -lclangParse -lclangQuery -lclangReorderFields -lclangRewrite -lclangRewriteFrontend -lclangSema -lclangSerialization -lclangStaticAnalyzerCheckers -lclangStaticAnalyzerCore -lclangStaticAnalyzerFrontend -lclangTidy -lclangTidyAndroidModule -lclangTidyBoostModule -lclangTidyBugproneModule -lclangTidyCERTModule -lclangTidyCppCoreGuidelinesModule -lclangTidyFuchsiaModule -lclangTidyGoogleModule -lclangTidyHICPPModule -lclangTidyLLVMModule -lclangTidyMiscModule -lclangTidyModernizeModule -lclangTidyMPIModule -lclangTidyObjCModule -lclangTidyPerformanceModule -lclangTidyPlugin -lclangTidyReadabilityModule -lclangTidyUtils -lclangTooling -lclangToolingASTDiff -lclangToolingCore -lclangToolingInclusions -lclangToolingRefactoring -lfindAllSymbols -Wl,--end-group -lz -lcurses -pthread

all: fieldandtypedumper

.PHONY: parser clean run all

SRCS := $(wildcard convert_to_db/*.cpp)
HEADERS := $(wildcard convert_to_db/*.hpp)

TEST_DATA_DIR := convert_to_db/tests/test_data
TEST_SRCS := $(wildcard $(TEST_DATA_DIR)/*.cpp)
TEST_BINS := $(TEST_SRCS:.cpp=)

bin/convert_to_db: $(SRCS) $(HEADERS)
	g++ -std=c++17 $(SRCS) -g -o bin/convert_to_db -lsqlite3 -lpthread -ltbb

# NEEDED
fieldandtypedumper: clang_parser.cpp
	$(CC) $(Includes) clang_parser.cpp $(CLANGLIBS) $(LLVMLIBS) -g -o bin/fieldandtypedumper

# Target to build and run test data generators
prepare_test: $(TEST_BINS)
	@echo "Generating test data..."
	@parallel ::: $(TEST_BINS)

$(TEST_DATA_DIR)/%: $(TEST_DATA_DIR)/%.cpp
	g++ -std=c++17 $< -o $@ -lpthread

clean:
	rm bin/*
