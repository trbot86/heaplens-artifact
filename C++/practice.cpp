#include <iostream>
#include <thread>
#include <cstdlib>
#include <unistd.h>
#include <experimental/source_location>
#include <execinfo.h>
#include <cxxabi.h>

#define FUNC 2

// void* operator new (std::size_t size) __attribute__((always_inline));
void atexit_handler();
// void printstacktrace(FILE* fd = stderr);

void atexit_handler() {
    std::cout << "exit_handler_called " << std::endl;
}

struct info_t {
    unsigned int line;
    uint64_t timestamp;
    size_t size;
    void* addr;
};

void thread_call_handler() {
    std::cout << std::this_thread::get_id() << " :thread" << std::endl;
    for(int i = 0;i < 2;i++) {
        sleep(1);
    }
}

void testfunc() {
    int* n = new int(6);
    return;
}

static inline void print_stacktrace(FILE *out = stderr, unsigned int max_frames = 63)
{
    fprintf(out, "stack trace:\n");

    // storage array for stack trace address data
    void* addrlist[max_frames+1];

    // retrieve current stack addresses
    int addrlen = backtrace(addrlist, sizeof(addrlist) / sizeof(void*));

    if (addrlen == 0) {
	fprintf(out, "  <empty, possibly corrupt>\n");
	return;
    }

    // resolve addresses into strings containing "filename(function+address)",
    // this array must be free()-ed
    char** symbollist = backtrace_symbols(addrlist, addrlen);

    // allocate string which will be filled with the demangled function name
    size_t funcnamesize = 256;
    char* funcname = (char*)malloc(funcnamesize);

    // iterate over the returned symbol lines. skip the first, it is the
    // address of this function.
    for (int i = 1; i < addrlen; i++)
    {
	char *begin_name = 0, *begin_offset = 0, *end_offset = 0;

	// find parentheses and +address offset surrounding the mangled name:
	// ./module(function+0x15c) [0x8048a6d]
	for (char *p = symbollist[i]; *p; ++p)
	{
	    if (*p == '(')
		begin_name = p;
	    else if (*p == '+')
		begin_offset = p;
	    else if (*p == ')' && begin_offset) {
		end_offset = p;
		break;
	    }
	}

	if (begin_name && begin_offset && end_offset
	    && begin_name < begin_offset)
	{
	    *begin_name++ = '\0';
	    *begin_offset++ = '\0';
	    *end_offset = '\0';

	    // mangled name is now in [begin_name, begin_offset) and caller
	    // offset in [begin_offset, end_offset). now apply
	    // __cxa_demangle():

	    int status;
	    char* ret = abi::__cxa_demangle(begin_name,
					    funcname, &funcnamesize, &status);
	    if (status == 0) {
		funcname = ret; // use possibly realloc()-ed string
		fprintf(out, "  %s : %s+%s\n",
			symbollist[i], funcname, begin_offset);
	    }
	    else {
		// demangling failed. Output function name as a C function with
		// no arguments.
		fprintf(out, "  %s : %s()+%s\n",
			symbollist[i], begin_name, begin_offset);
	    }
	}
	else
	{
	    // couldn't parse the line? print the whole line.
	    fprintf(out, "  %s\n", symbollist[i]);
	}
    }

    free(funcname);
    free(symbollist);
}

void* operator new (std::size_t size) {
    // print_stacktrace();
    // std::experimental::source_location loc = std::experimental::source_location::current();
    // std::cout << loc.line() << std::endl;
    return std::malloc(size);
}

template <typename T>
void* malloc(size_t size) {
    std::cout << "malloc called " << typeid(T).name() << std::endl;
    return (T*)std::malloc(size);
}

int main() {
malloc (sizeof(int));

return 0;
}