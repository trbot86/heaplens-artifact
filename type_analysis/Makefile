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
TEST_BINS := $(patsubst %.cpp, %.gen, $(TEST_SRCS))

RUN_TEST_SRC := convert_to_db/tests/run_test.cpp
RUN_TEST_BIN := convert_to_db/tests/run_test
SRCS_TO_TEST := convert_to_db/io_handler.cpp

bin/convert_to_db: $(SRCS) $(HEADERS)
	g++ -std=c++17 $(SRCS) -g -o bin/convert_to_db -lsqlite3 -lpthread -ltbb

# NEEDED
fieldandtypedumper: clang_parser.cpp
	$(CC) $(Includes) clang_parser.cpp $(CLANGLIBS) $(LLVMLIBS) -g -o bin/fieldandtypedumper

$(TEST_DATA_DIR)/%.gen: $(TEST_DATA_DIR)/%.cpp
	g++ -std=c++17 -g -I../memhook/ $< -o $@ -L../memhook/ -Wl,-rpath=../memhook/ -lmemhook -ldl

build_test_binds: $(TEST_BINS)

# Target to build and run test data generators
prepare_test: $(TEST_BINS)
	@echo "Removing old test data..."
	@rm -f $(TEST_DATA_DIR)/*.txt
	@echo "Generating test data..."
	@parallel --halt now,fail=1 --lb --jobs 0 ' \
		BIN={}; \
		BASE=$$(basename $$BIN .gen); \
		MEMHOOK_OUTPUT_DUMP_FILE=$(TEST_DATA_DIR)/$${BASE}_dump.txt \
		MEMHOOK_OUTPUT_TYPE_FILE=$(TEST_DATA_DIR)/$${BASE}_type.txt \
		MEMHOOK_OUTPUT_FILE_FILE=$(TEST_DATA_DIR)/$${BASE}_file.txt \
		./$$BIN' ::: $(TEST_BINS)

PRINT_WARNING ?= 0

# Target to build the run_test binary
$(RUN_TEST_BIN): $(RUN_TEST_SRC) $(SRCS_TO_TEST)
	$(CXX) -I./convert_to_db/ -std=c++17 -DSELECT_TEST="\"$(SELECT_TEST)\"" -DPRINT_WARNING=$(PRINT_WARNING) -g -o $@ $^ -lsqlite3 -lpthread -ltbb

# Target to build and run the tests
run_tests: $(RUN_TEST_BIN)
	@echo "Running tests..."
	@./$(RUN_TEST_BIN)

clean:
	rm -f bin/* $(TEST_DATA_DIR)/*.gen $(RUN_TEST_BIN)
