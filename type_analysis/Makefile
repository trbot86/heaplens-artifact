CC=clang++
C_CC=clang
Includes=`llvm-config --cxxflags --ldflags` -L/lib/llvm-10/lib -fno-rtti
Includes_2= 
LLVMLIBS=`llvm-config --libs --system-libs`
# CLANGLIBS=-Wno-unknown-warning-option -lclangTooling -lclangToolingInclusions -lclangFrontendTool -lclangFrontend -lclangDriver -lclangSerialization -lclangCodeGen -lclangParse -lclangSema -lclangStaticAnalyzerFrontend -lclangStaticAnalyzerCheckers -lclangStaticAnalyzerCore -lclangAnalysis -lclangARCMigrate -lclangApplyReplacements -lclangRewrite -lclangRewriteFrontend -lclangEdit -lclangAST -lclangASTMatchers -lclangLex -lclangBasic -lclang
CLANGLIBS=-Wno-unknown-warning-option -Wl,--start-group -lclangAnalysis -lclangApplyReplacements -lclangARCMigrate -lclangAST -lclangASTMatchers -lclangBasic -lclangChangeNamespace -lclangCodeGen -lclangCrossTU -lclangDaemon -lclangDriver -lclangDynamicASTMatchers -lclangEdit -lclangFormat -lclangFrontend -lclangFrontendTool -lclangHandleCXX -lclangIncludeFixer -lclangIncludeFixerPlugin -lclangIndex -lclangLex -lclangMove -lclangParse -lclangQuery -lclangReorderFields -lclangRewrite -lclangRewriteFrontend -lclangSema -lclangSerialization -lclangStaticAnalyzerCheckers -lclangStaticAnalyzerCore -lclangStaticAnalyzerFrontend -lclangTidy -lclangTidyAndroidModule -lclangTidyBoostModule -lclangTidyBugproneModule -lclangTidyCERTModule -lclangTidyCppCoreGuidelinesModule -lclangTidyFuchsiaModule -lclangTidyGoogleModule -lclangTidyHICPPModule -lclangTidyLLVMModule -lclangTidyMiscModule -lclangTidyModernizeModule -lclangTidyMPIModule -lclangTidyObjCModule -lclangTidyPerformanceModule -lclangTidyPlugin -lclangTidyReadabilityModule -lclangTidyUtils -lclangTooling -lclangToolingASTDiff -lclangToolingCore -lclangToolingInclusions -lclangToolingRefactoring -lfindAllSymbols -lLLVMAArch64AsmParser -lLLVMAArch64CodeGen -lLLVMAArch64Desc -lLLVMAArch64Disassembler -lLLVMAArch64Info -lLLVMAArch64Utils -lLLVMAMDGPUAsmParser -lLLVMAMDGPUCodeGen -lLLVMAMDGPUDesc -lLLVMAMDGPUDisassembler -lLLVMAMDGPUInfo -lLLVMAMDGPUUtils -lLLVMAnalysis -lLLVMARMAsmParser -lLLVMARMCodeGen -lLLVMARMDesc -lLLVMARMDisassembler -lLLVMARMInfo -lLLVMARMUtils -lLLVMAsmParser -lLLVMBinaryFormat -lLLVMBitReader -lLLVMBitWriter -lLLVMBPFAsmParser -lLLVMBPFCodeGen -lLLVMBPFDesc -lLLVMBPFDisassembler -lLLVMBPFInfo -lLLVMCodeGen -lLLVMCore -lLLVMCoroutines -lLLVMCoverage -lLLVMDebugInfoCodeView -lLLVMDebugInfoDWARF -lLLVMDebugInfoMSF -lLLVMDebugInfoPDB -lLLVMDemangle -lLLVMDlltoolDriver -lLLVMExecutionEngine -lLLVMFuzzMutate -lLLVMGlobalISel -lLLVMHexagonAsmParser -lLLVMHexagonCodeGen -lLLVMHexagonDesc -lLLVMHexagonDisassembler -lLLVMHexagonInfo -lLLVMInstCombine -lLLVMInstrumentation -lLLVMInterpreter -lLLVMipo -lLLVMIRReader -lLLVMLanaiAsmParser -lLLVMLanaiCodeGen -lLLVMLanaiDesc -lLLVMLanaiDisassembler -lLLVMLanaiInfo -lLLVMLibDriver -lLLVMLineEditor -lLLVMLinker -lLLVMLTO -lLLVMMC -lLLVMMCDisassembler -lLLVMMCJIT -lLLVMMCParser -lLLVMMipsAsmParser -lLLVMMipsCodeGen -lLLVMMipsDesc -lLLVMMipsDisassembler -lLLVMMipsInfo -lLLVMMIRParser -lLLVMMSP430CodeGen -lLLVMMSP430Desc -lLLVMMSP430Info -lLLVMNVPTXCodeGen -lLLVMNVPTXDesc -lLLVMNVPTXInfo -lLLVMObjCARCOpts -lLLVMObject -lLLVMObjectYAML -lLLVMOption -lLLVMOrcJIT -lLLVMPasses -lLLVMPowerPCAsmParser -lLLVMPowerPCCodeGen -lLLVMPowerPCDesc -lLLVMPowerPCDisassembler -lLLVMPowerPCInfo -lLLVMProfileData -lLLVMRuntimeDyld -lLLVMScalarOpts -lLLVMSelectionDAG -lLLVMSparcAsmParser -lLLVMSparcCodeGen -lLLVMSparcDesc -lLLVMSparcDisassembler -lLLVMSparcInfo -lLLVMSupport -lLLVMSymbolize -lLLVMSystemZAsmParser -lLLVMSystemZCodeGen -lLLVMSystemZDesc -lLLVMSystemZDisassembler -lLLVMSystemZInfo -lLLVMTableGen -lLLVMTarget -lLLVMTransformUtils -lLLVMVectorize -lLLVMWindowsManifest -lLLVMX86AsmParser -lLLVMX86CodeGen -lLLVMX86Desc -lLLVMX86Disassembler -lLLVMX86Info -lLLVMX86Utils -lLLVMXCoreCodeGen -lLLVMXCoreDesc -lLLVMXCoreDisassembler -lLLVMXCoreInfo -lLLVMXRay -Wl,--end-group -lz -lcurses -pthread

all: fieldandtypedumper malloctypedumper header_c header

run:
	./tool header.cpp

.PHONY: parser malloctypedumper clean run all

byte_reader: byte_rw.cpp
	$(CC) byte_rw.cpp -g -o byte_rw

fieldandtypedumper: clang_parser.cpp
	$(CC) $(Includes) clang_parser.cpp $(CLANGLIBS) $(LLVMLIBS) -g -o fieldandtypedumper

malloctypedumper: malloctypedumper.cpp
	# $(CC) $(Includes) -DMTDFNAME="\"_mm_malloc\"" -DDEBUG malloctypedumper.cpp $(CLANGLIBS) $(LLVMLIBS) -g -o malloctypedumper
	$(CC) $(Includes) -DMTDFNAME="\"malloc\"" -DDEBUG malloctypedumper.cpp $(CLANGLIBS) $(LLVMLIBS) -g -o malloctypedumper

replacer: source_replacements.cpp
	$(CC) $(Includes) source_replacements.cpp $(CLANGLIBS) $(LLVMLIBS) -g -o replacer

header: header.cpp
	$(CC) /home/gspathak/sifter/type_analysis/header.cpp -g -o header -L../memhook/ -I../memhook/ -Wl,-rpath=../memhook/ -lmemhook -ldl

header_c: header.c
	$(C_CC) /home/gspathak/sifter/type_analysis/header.c -g -o header_c -L../memhook/ -I../memhook/ -Wl,-rpath=../memhook/ -lmemhook -ldl

clean:
	rm tool malloctypedumper replacer header header_c malloc_type_dump.txt info_dump binary_dump.txt fielddump.txt new_field_dump.txt new_fielddump.txt typedump.txt typeset_dump.txt fileset_dump.txt allocs.sqlite