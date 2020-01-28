// #include <clang-c/Index.h>

// #include <iostream>
// #include <string>

// using namespace std;

// string getCursorKindName( CXCursorKind cursorKind )
// {
//   CXString kindName  = clang_getCursorKindSpelling( cursorKind );
//   string result = clang_getCString( kindName );

//   clang_disposeString( kindName );
//   return result;
// }

// string getCursorSpelling( CXCursor cursor )
// {
//   CXString cursorSpelling = clang_getCursorSpelling( cursor );
//   string result      = clang_getCString( cursorSpelling );

//   clang_disposeString( cursorSpelling );
//   return result;
// }

// void getScope(CXCursor pc) {
//     CXCursorKind parentKind = clang_getCursorKind(clang_getCursorSemanticParent(pc));

//     if(parentKind == CXCursor_VarDecl) {
//       CXSourceRange range = clang_getCursorExtent(pc);
//       CXSourceLocation loc = clang_getRangeStart(range);
//       CXSourceLocation endloc = clang_getRangeEnd(range);

//       unsigned int line, column, offset;
//       clang_getExpansionLocation(loc, NULL, &line, &column, &offset);
//       cout << line << " " << column << " " << offset << endl;
//       clang_getExpansionLocation(endloc, NULL, &line, &column, &offset);
//       cout << line << " " << column << " " << offset << endl;
//     }

//     cout << getCursorKindName(parentKind) << endl;
// }

// CXChildVisitResult visitor( CXCursor cursor, CXCursor pc, CXClientData clientData )
// {
//   CXSourceLocation location = clang_getCursorLocation( cursor );
//   if( clang_Location_isFromMainFile( location ) == 0 )
//     return CXChildVisit_Continue;

//   CXCursorKind cursorKind = clang_getCursorKind( cursor );

//   if(cursorKind == CXCursor_CXXNewExpr) {
//     // clang_get
//   }

//   unsigned int curLevel  = *( reinterpret_cast<unsigned int*>( clientData ) );
//   unsigned int nextLevel = curLevel + 1;

//   std::cout << std::string( curLevel, '-' ) << " " << getCursorKindName(
//   cursorKind ) << " (" << getCursorSpelling( cursor ) << ")\n";

//   clang_visitChildren( cursor,
//                        visitor,
//                        &nextLevel ); 

//   return CXChildVisit_Continue;
// }

// int main( int argc, char** argv )
// {
//   if( argc < 2 )
//     return -1;

//   const char const* args[] = {"-fno-delayed-template-parsing"};
//   CXIndex index        = clang_createIndex( 0, 1 );
//   CXTranslationUnit tu = clang_createTranslationUnitFromSourceFile( index, argv[1] , 1 , args, 0 , NULL);

//   if( !tu )
//     return -1;

//   CXCursor rootCursor  = clang_getTranslationUnitCursor( tu );

//   unsigned int treeLevel = 0;

//   clang_visitChildren( rootCursor, visitor, &treeLevel );

//   clang_disposeTranslationUnit( tu );
//   clang_disposeIndex( index );

//   return 0;
// }

#include <clang-c/Index.h>

#include <iostream>

CXChildVisitResult visitor(CXCursor cursor, CXCursor, CXClientData) {
  CXCursorKind kind = clang_getCursorKind(cursor);

  // Consider functions and methods
  if (kind == CXCursorKind::CXCursor_FunctionDecl ||
      kind == CXCursorKind::CXCursor_CXXMethod) {
    auto cursorName = clang_getCursorDisplayName(cursor);

    // Print if function/method starts with doSomething
    auto cursorNameStr = std::string(clang_getCString(cursorName));
    if (cursorNameStr.find("doSomething") == 0) {
      // Get the source locatino
      CXSourceRange range = clang_getCursorExtent(cursor);
      CXSourceLocation location = clang_getRangeStart(range);

      CXFile file;
      unsigned line;
      unsigned column;
      clang_getFileLocation(location, &file, &line, &column, nullptr);

      auto fileName = clang_getFileName(file);

      std::cout << "Found call to " << clang_getCString(cursorName) << " at "
                << line << ":" << column << " in " << clang_getCString(fileName)
                << std::endl;

      clang_disposeString(fileName);
    }

    clang_disposeString(cursorName);
  }

  return CXChildVisit_Recurse;
}

int main(int argc, char **argv) {
  if (argc < 2) {
    return 1;
  }

  // Command line arguments required for parsing the TU
  constexpr const char *ARGUMENTS[] = {};

  // Create an index with excludeDeclsFromPCH = 1, displayDiagnostics = 0
  CXIndex index = clang_createIndex(1, 0);

  // Speed up parsing by skipping function bodies
  CXTranslationUnit translationUnit = clang_parseTranslationUnit(
      index, argv[1], ARGUMENTS, std::extent<decltype(ARGUMENTS)>::value,
      nullptr, 0, CXTranslationUnit_SkipFunctionBodies);

  // Visit all the nodes in the AST
  CXCursor cursor = clang_getTranslationUnitCursor(translationUnit);
  clang_visitChildren(cursor, visitor, 0);

  // Release memory
  clang_disposeTranslationUnit(translationUnit);
  clang_disposeIndex(index);

  return 0;
}