#include "CLI11.hpp"
#include "sampler.hpp"

int main(int argc, char* argv[]) {
    CLI::App app{"Samples a set of pages from the memory events " \
                "produced by the instrumented application."};
    argv = app.ensure_utf8(argv);

    std::string perf_filename;
    std::string field_filename;
    double hitm_cutoff = 0.0;
    double sample_portion = 1.0;
    size_t page_size = 4096;
    size_t cache_line_size = 64;
    size_t num_pages_per_type = 1;
    size_t num_buckets = 3000;
    size_t frag_gran = 0;
    size_t num_threads = 1;

    app.add_option("-p,--perf-file", perf_filename,
        "The name of a file produced by perf c2c");
    app.add_option("-f,--field-dump", field_filename,
        "The name of a file containing field information");
    app.add_option("-c,--hitm-cutoff", hitm_cutoff,
        "A lower bound on the hitm value of a record in the perf file " \
        "(default 0.0)");
    app.add_option("-s,--sample", sample_portion,
        "Portion of memory pages sampled from log (default 1.0)");
    app.add_option("--page-size", page_size,
        "Size of a memory page in bytes (default 4096)");
    app.add_option("--cacheline-size", cache_line_size,
        "Size of a cache line in bytes (default 64)");
    app.add_option("-t,--num-pages-per-type", num_pages_per_type,
        "For each type, select at least this many pages containing " \
        "at least one allocation of that type (default 1)");
    app.add_option("-b,--num-buckets", num_buckets,
        "The number of discrete 'buckets' into which the timeline " \
        "will be divided. Higher values results in a more detailed " \
        "memory consumption graph, but also a larger database " \
        "(default 3000)");
    app.add_option("-r,--fragmentation", frag_gran,
        "The granularity at which fragmentation should be computed " \
        "(default 0, meaning fragmentation is not computed)");
    app.add_option("-j,--threads", num_threads,
        "The number of threads to use (default 1, multithreading not " \
        "currently implemented)");

    CLI11_PARSE(app, argc, argv);

    Sampler s{};
    if (!perf_filename.empty())
        s.note_perf_addrs(perf_filename, page_size, cache_line_size, hitm_cutoff);
    s.sample_pages_and_record_stats(page_size, num_pages_per_type, 
                                    cache_line_size, num_buckets, sample_portion);
    if (!field_filename.empty())
        s.record_fields(field_filename);
    if (frag_gran > 0)
        s.output_frag(frag_gran);
}