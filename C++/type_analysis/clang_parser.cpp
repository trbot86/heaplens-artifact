/**
 *  Basic workflow:
 *  -1) Did a basic parse of the source, printed all AST nodes
 *  and their types.
 *  2) Did a search for all recordDecl nodes, made a list of
 *  that and printed it.
 *  3) Looked for all new, malloc allocations and printed their
 *  types.
 *  4) Decided the layout of the typetable data structure, and
 *  how to add to it using new, malloc parsing.
*/

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

#include <iostream>
#include <string>
#include <bits/stdc++.h>
// #include <clang/AST/AST.h>
// #include <clang/AST/ASTConsumer.h>
// #include <clang/AST/ASTContext.h>
// #include <clang/AST/RecursiveASTVisitor.h>
// #include <clang/Driver/Options.h>
// #include <clang/Frontend/ASTConsumers.h>
// #include <clang/Frontend/CompilerInstance.h>
// #include <clang/Frontend/FrontendActions.h>
// #include <clang/Rewrite/Core/Rewriter.h>
#include <clang/Tooling/CommonOptionsParser.h>
#include <clang/Tooling/Tooling.h>

#include <clang/ASTMatchers/ASTMatchers.h>
#include <clang/ASTMatchers/ASTMatchFinder.h>

using namespace std;
using namespace llvm;
using namespace clang;
using namespace clang::ast_matchers;
using namespace clang::tooling;

static llvm::cl::OptionCategory MyToolCategory("my-tool options");

set<string> typenameset;

StatementMatcher LoopMatcher =
  forStmt(hasLoopInit(declStmt(hasSingleDecl(varDecl(
    hasInitializer(integerLiteral(equals(0)))))))).bind("forLoop");

DeclarationMatcher classMatcher = 
  cxxRecordDecl().bind("class");

class ClassnamePrinter : public MatchFinder::MatchCallback {
  public :
    virtual void run(const MatchFinder::MatchResult &Result) {
      const RecordDecl* rd = Result.Nodes.getNodeAs<clang::RecordDecl>("class");
      
      // ASTContext *Context = Result.Context;
      
      // SourceManager& sm(Context->getSourceManager());
      
      // if(sm.isInMainFile(sm.getExpansionLoc(rd->getLocStart()))) {
        cout << rd->getDeclName().getAsString() << endl;
        typenameset.insert(rd->getDeclName().getAsString());
      // }
    }
};

int main(int argc, const char **argv) {
  CommonOptionsParser OptionsParser(argc, argv, MyToolCategory);
  
  ClangTool Tool(OptionsParser.getCompilations(),
                 OptionsParser.getSourcePathList());

  ClassnamePrinter cp;

  MatchFinder Finder;
  
  Finder.addMatcher(classMatcher, &cp);

  Tool.run(newFrontendActionFactory(&Finder).get());
  
  ofstream file;
  file.open("typedump.txt");

  for(auto i = typenameset.begin();i != typenameset.end();++i) {
    file << *i << endl;
  }

  file.close();
  return 0;
}