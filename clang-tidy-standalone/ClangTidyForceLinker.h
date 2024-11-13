//===- ClangTidyForceLinker.h - clang-tidy --------------------------------===//
//
// Part of the LLVM Project, under the Apache License v2.0 with LLVM Exceptions.
// See https://llvm.org/LICENSE.txt for license information.
// SPDX-License-Identifier: Apache-2.0 WITH LLVM-exception
//
//===----------------------------------------------------------------------===//

#ifndef LLVM_CLANG_TOOLS_EXTRA_CLANG_TIDY_CLANGTIDYFORCELINKER_H
#define LLVM_CLANG_TOOLS_EXTRA_CLANG_TIDY_CLANGTIDYFORCELINKER_H

#include <clang/Config/config.h>
#include "llvm/Support/Compiler.h"

namespace clang {
namespace tidy {

// This anchor is used to force the linker to link the AbseilModule.
volatile int AbseilModuleAnchorSource = 0;
static int LLVM_ATTRIBUTE_UNUSED AbseilModuleAnchorDestination =
    AbseilModuleAnchorSource;

// This anchor is used to force the linker to link the AlteraModule.
volatile int AlteraModuleAnchorSource = 0;
static int LLVM_ATTRIBUTE_UNUSED AlteraModuleAnchorDestination =
    AlteraModuleAnchorSource;

// This anchor is used to force the linker to link the AndroidModule.
volatile int AndroidModuleAnchorSource = 0;
static int LLVM_ATTRIBUTE_UNUSED AndroidModuleAnchorDestination =
    AndroidModuleAnchorSource;

// This anchor is used to force the linker to link the BoostModule.
volatile int BoostModuleAnchorSource = 0;
static int LLVM_ATTRIBUTE_UNUSED BoostModuleAnchorDestination =
    BoostModuleAnchorSource;

// This anchor is used to force the linker to link the BugproneModule.
volatile int BugproneModuleAnchorSource = 0;
static int LLVM_ATTRIBUTE_UNUSED BugproneModuleAnchorDestination =
    BugproneModuleAnchorSource;

// This anchor is used to force the linker to link the CERTModule.
volatile int CERTModuleAnchorSource = 0;
static int LLVM_ATTRIBUTE_UNUSED CERTModuleAnchorDestination =
    CERTModuleAnchorSource;

// This anchor is used to force the linker to link the ConcurrencyModule.
volatile int ConcurrencyModuleAnchorSource = 0;
static int LLVM_ATTRIBUTE_UNUSED ConcurrencyModuleAnchorDestination =
    ConcurrencyModuleAnchorSource;

// This anchor is used to force the linker to link the CppCoreGuidelinesModule.
volatile int CppCoreGuidelinesModuleAnchorSource = 0;
static int LLVM_ATTRIBUTE_UNUSED CppCoreGuidelinesModuleAnchorDestination =
    CppCoreGuidelinesModuleAnchorSource;

// This anchor is used to force the linker to link the DarwinModule.
volatile int DarwinModuleAnchorSource = 0;
static int LLVM_ATTRIBUTE_UNUSED DarwinModuleAnchorDestination =
    DarwinModuleAnchorSource;

// This anchor is used to force the linker to link the FuchsiaModule.
volatile int FuchsiaModuleAnchorSource = 0;
static int LLVM_ATTRIBUTE_UNUSED FuchsiaModuleAnchorDestination =
    FuchsiaModuleAnchorSource;

// This anchor is used to force the linker to link the GoogleModule.
volatile int GoogleModuleAnchorSource = 0;
static int LLVM_ATTRIBUTE_UNUSED GoogleModuleAnchorDestination =
    GoogleModuleAnchorSource;

// This anchor is used to force the linker to link the HICPPModule.
volatile int HICPPModuleAnchorSource = 0;
static int LLVM_ATTRIBUTE_UNUSED HICPPModuleAnchorDestination =
    HICPPModuleAnchorSource;

// This anchor is used to force the linker to link the LinuxKernelModule.
volatile int LinuxKernelModuleAnchorSource = 0;
static int LLVM_ATTRIBUTE_UNUSED LinuxKernelModuleAnchorDestination =
    LinuxKernelModuleAnchorSource;

// This anchor is used to force the linker to link the LLVMModule.
volatile int LLVMModuleAnchorSource = 0;
static int LLVM_ATTRIBUTE_UNUSED LLVMModuleAnchorDestination =
    LLVMModuleAnchorSource;

// This anchor is used to force the linker to link the LLVMLibcModule.
volatile int LLVMLibcModuleAnchorSource = 0;
static int LLVM_ATTRIBUTE_UNUSED LLVMLibcModuleAnchorDestination =
    LLVMLibcModuleAnchorSource;

// This anchor is used to force the linker to link the MiscModule.
extern volatile int MiscModuleAnchorSource;
static int LLVM_ATTRIBUTE_UNUSED MiscModuleAnchorDestination =
    MiscModuleAnchorSource;

// This anchor is used to force the linker to link the ModernizeModule.
volatile int ModernizeModuleAnchorSource = 0;
static int LLVM_ATTRIBUTE_UNUSED ModernizeModuleAnchorDestination =
    ModernizeModuleAnchorSource;

// This anchor is used to force the linker to link the MPIModule.
volatile int MPIModuleAnchorSource = 0;
static int LLVM_ATTRIBUTE_UNUSED MPIModuleAnchorDestination =
    MPIModuleAnchorSource;

// This anchor is used to force the linker to link the ObjCModule.
volatile int ObjCModuleAnchorSource = 0;
static int LLVM_ATTRIBUTE_UNUSED ObjCModuleAnchorDestination =
    ObjCModuleAnchorSource;

// This anchor is used to force the linker to link the OpenMPModule.
volatile int OpenMPModuleAnchorSource = 0;
static int LLVM_ATTRIBUTE_UNUSED OpenMPModuleAnchorDestination =
    OpenMPModuleAnchorSource;

// This anchor is used to force the linker to link the PerformanceModule.
volatile int PerformanceModuleAnchorSource = 0;
static int LLVM_ATTRIBUTE_UNUSED PerformanceModuleAnchorDestination =
    PerformanceModuleAnchorSource;

// This anchor is used to force the linker to link the PortabilityModule.
volatile int PortabilityModuleAnchorSource = 0;
static int LLVM_ATTRIBUTE_UNUSED PortabilityModuleAnchorDestination =
    PortabilityModuleAnchorSource;

// This anchor is used to force the linker to link the ReadabilityModule.
volatile int ReadabilityModuleAnchorSource = 0;
static int LLVM_ATTRIBUTE_UNUSED ReadabilityModuleAnchorDestination =
    ReadabilityModuleAnchorSource;

// This anchor is used to force the linker to link the ZirconModule.
volatile int ZirconModuleAnchorSource = 0;
static int LLVM_ATTRIBUTE_UNUSED ZirconModuleAnchorDestination =
    ZirconModuleAnchorSource;

} // namespace tidy
} // namespace clang

#endif
