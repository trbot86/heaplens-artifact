#include "hnswlib/hnswlib.h"
#include "hnswlib/heaplens_hooks.h"

#include <algorithm>
#include <atomic>
#include <cerrno>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <exception>
#include <iostream>
#include <limits>
#include <memory>
#include <mutex>
#include <queue>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>

#if defined(__linux__)
#include <unistd.h>
#endif

namespace {

enum class QueryMode {
    Indexed,
    Random
};

struct Config {
    size_t elements;
    size_t dim;
    size_t queries;
    size_t warmup;
    size_t iterations;
    size_t k;
    size_t m;
    size_t ef_construction;
    size_t ef_search;
    size_t threads;
    size_t build_threads;
    uint64_t seed;
    QueryMode query_mode;

    Config()
        : elements(1000000),
          dim(128),
          queries(100000),
          warmup(10000),
          iterations(5),
          k(10),
          m(16),
          ef_construction(200),
          ef_search(64),
          threads(default_thread_count()),
          build_threads(0),
          seed(47),
          query_mode(QueryMode::Indexed) {}

    static size_t default_thread_count() {
        size_t threads = std::thread::hardware_concurrency();
        if (threads == 0) {
            return 16;
        }
        return std::min<size_t>(threads, 16);
    }
};

class Timer {
 public:
    Timer() : begin_(std::chrono::steady_clock::now()) {}

    double elapsed_seconds() const {
        const std::chrono::steady_clock::time_point end = std::chrono::steady_clock::now();
        return std::chrono::duration_cast<std::chrono::duration<double>>(end - begin_).count();
    }

    uint64_t elapsed_us() const {
        const std::chrono::steady_clock::time_point end = std::chrono::steady_clock::now();
        return static_cast<uint64_t>(
            std::chrono::duration_cast<std::chrono::microseconds>(end - begin_).count());
    }

 private:
    std::chrono::steady_clock::time_point begin_;
};

uint64_t now_us() {
    const std::chrono::steady_clock::time_point now = std::chrono::steady_clock::now();
    return static_cast<uint64_t>(
        std::chrono::duration_cast<std::chrono::microseconds>(now.time_since_epoch()).count());
}

size_t current_rss_bytes() {
#if defined(__linux__)
    long rss_pages = 0;
    FILE *fp = std::fopen("/proc/self/statm", "r");
    if (fp == nullptr) {
        return 0;
    }
    if (std::fscanf(fp, "%*s%ld", &rss_pages) != 1) {
        std::fclose(fp);
        return 0;
    }
    std::fclose(fp);
    return static_cast<size_t>(rss_pages) * static_cast<size_t>(sysconf(_SC_PAGESIZE));
#else
    return 0;
#endif
}

class Phase {
 public:
    explicit Phase(const std::string &name) : name_(name), timer_() {
        std::cout << "HEAPLENS_PHASE_BEGIN name=" << name_
                  << " ts_us=" << now_us()
                  << " rss_bytes=" << current_rss_bytes() << std::endl;
    }

    ~Phase() {
        std::cout << "HEAPLENS_PHASE_END name=" << name_
                  << " elapsed_us=" << timer_.elapsed_us()
                  << " ts_us=" << now_us()
                  << " rss_bytes=" << current_rss_bytes() << std::endl;
    }

 private:
    std::string name_;
    Timer timer_;
};

uint64_t splitmix64(uint64_t x) {
    x += UINT64_C(0x9e3779b97f4a7c15);
    x = (x ^ (x >> 30)) * UINT64_C(0xbf58476d1ce4e5b9);
    x = (x ^ (x >> 27)) * UINT64_C(0x94d049bb133111eb);
    return x ^ (x >> 31);
}

float unit_float(uint64_t x) {
    const uint32_t mantissa = static_cast<uint32_t>(splitmix64(x) >> 40);
    return static_cast<float>(mantissa) * (1.0f / 16777216.0f);
}

uint64_t mix_checksum(uint64_t current, uint64_t value) {
    current ^= splitmix64(value + UINT64_C(0x9e3779b97f4a7c15) + (current << 6) + (current >> 2));
    return current;
}

template <class Function>
void parallel_blocks(size_t start, size_t end, size_t requested_threads, Function fn) {
    if (end <= start) {
        return;
    }

    size_t threads = requested_threads;
    if (threads == 0) {
        threads = Config::default_thread_count();
    }

    const size_t count = end - start;
    threads = std::max<size_t>(1, std::min(threads, count));

    if (threads == 1) {
        fn(start, end, 0);
        return;
    }

    std::vector<std::thread> workers;
    workers.reserve(threads);
    std::exception_ptr first_exception = nullptr;
    std::mutex exception_mutex;

    for (size_t thread_id = 0; thread_id < threads; ++thread_id) {
        const size_t block_begin = start + (count * thread_id) / threads;
        const size_t block_end = start + (count * (thread_id + 1)) / threads;

        workers.push_back(std::thread([&, block_begin, block_end, thread_id] {
            try {
                fn(block_begin, block_end, thread_id);
            } catch (...) {
                std::lock_guard<std::mutex> lock(exception_mutex);
                if (!first_exception) {
                    first_exception = std::current_exception();
                }
            }
        }));
    }

    for (size_t i = 0; i < workers.size(); ++i) {
        workers[i].join();
    }

    if (first_exception) {
        std::rethrow_exception(first_exception);
    }
}

size_t parse_size(const std::string &text) {
    if (text.empty()) {
        throw std::invalid_argument("empty integer option");
    }

    std::string number = text;
    uint64_t multiplier = 1;
    const char suffix = number[number.size() - 1];
    if (suffix == 'k' || suffix == 'K') {
        multiplier = 1000;
        number.resize(number.size() - 1);
    } else if (suffix == 'm' || suffix == 'M') {
        multiplier = 1000 * 1000;
        number.resize(number.size() - 1);
    } else if (suffix == 'g' || suffix == 'G') {
        multiplier = 1000 * 1000 * 1000ULL;
        number.resize(number.size() - 1);
    }

    if (number.empty()) {
        throw std::invalid_argument("missing integer before suffix in option: " + text);
    }

    errno = 0;
    char *end = nullptr;
    const unsigned long long parsed = std::strtoull(number.c_str(), &end, 10);
    if (errno != 0 || end == number.c_str() || *end != '\0') {
        throw std::invalid_argument("invalid integer option: " + text);
    }
    if (parsed > std::numeric_limits<size_t>::max() / multiplier) {
        throw std::overflow_error("integer option is too large: " + text);
    }

    return static_cast<size_t>(parsed * multiplier);
}

uint64_t parse_u64(const std::string &text) {
    errno = 0;
    char *end = nullptr;
    const unsigned long long parsed = std::strtoull(text.c_str(), &end, 10);
    if (errno != 0 || end == text.c_str() || *end != '\0') {
        throw std::invalid_argument("invalid integer option: " + text);
    }
    return static_cast<uint64_t>(parsed);
}

bool option_value(int &i, int argc, char **argv, const std::string &arg,
                  const std::string &name, std::string *value) {
    const std::string long_name = "--" + name;
    const std::string prefix = long_name + "=";
    if (arg == long_name) {
        if (i + 1 >= argc) {
            throw std::invalid_argument("missing value for " + long_name);
        }
        *value = argv[++i];
        return true;
    }
    if (arg.compare(0, prefix.size(), prefix) == 0) {
        *value = arg.substr(prefix.size());
        return true;
    }
    return false;
}

void print_usage(const char *program) {
    std::cout
        << "Usage: " << program << " [options]\n"
        << "\n"
        << "Synthetic hnswlib benchmark with explicit HeapLENS phase markers.\n"
        << "\n"
        << "Options:\n"
        << "  --elements N            Indexed vectors, suffixes K/M/G accepted (default 1M)\n"
        << "  --dim N                 Vector dimension (default 128)\n"
        << "  --queries N             Unique query vectors or query ids (default 100000)\n"
        << "  --iterations N          Full query passes after warmup (default 5)\n"
        << "  --warmup N              Warmup searches before timing (default 10000)\n"
        << "  --threads N             Query/data-generation threads (default min(hardware concurrency, 16))\n"
        << "  --build-threads N       Index build threads (default --threads)\n"
        << "  --m N                   HNSW M parameter (default 16)\n"
        << "  --ef-construction N     HNSW ef_construction parameter (default 200)\n"
        << "  --ef-search N           HNSW ef search parameter (default 64)\n"
        << "  --k N                   Neighbors per query (default 10)\n"
        << "  --query-mode MODE       indexed or random (default indexed)\n"
        << "  --seed N                Deterministic data seed (default 47)\n"
        << "  --help                  Show this message\n";
}

Config parse_args(int argc, char **argv) {
    Config cfg;
    for (int i = 1; i < argc; ++i) {
        const std::string arg = argv[i];
        std::string value;

        if (arg == "--help" || arg == "-h") {
            print_usage(argv[0]);
            std::exit(0);
        } else if (option_value(i, argc, argv, arg, "elements", &value)) {
            cfg.elements = parse_size(value);
        } else if (option_value(i, argc, argv, arg, "dim", &value)) {
            cfg.dim = parse_size(value);
        } else if (option_value(i, argc, argv, arg, "queries", &value)) {
            cfg.queries = parse_size(value);
        } else if (option_value(i, argc, argv, arg, "iterations", &value)) {
            cfg.iterations = parse_size(value);
        } else if (option_value(i, argc, argv, arg, "warmup", &value)) {
            cfg.warmup = parse_size(value);
        } else if (option_value(i, argc, argv, arg, "threads", &value)) {
            cfg.threads = parse_size(value);
        } else if (option_value(i, argc, argv, arg, "build-threads", &value)) {
            cfg.build_threads = parse_size(value);
        } else if (option_value(i, argc, argv, arg, "m", &value)) {
            cfg.m = parse_size(value);
        } else if (option_value(i, argc, argv, arg, "ef-construction", &value)) {
            cfg.ef_construction = parse_size(value);
        } else if (option_value(i, argc, argv, arg, "ef-search", &value)) {
            cfg.ef_search = parse_size(value);
        } else if (option_value(i, argc, argv, arg, "k", &value)) {
            cfg.k = parse_size(value);
        } else if (option_value(i, argc, argv, arg, "seed", &value)) {
            cfg.seed = parse_u64(value);
        } else if (option_value(i, argc, argv, arg, "query-mode", &value)) {
            if (value == "indexed") {
                cfg.query_mode = QueryMode::Indexed;
            } else if (value == "random") {
                cfg.query_mode = QueryMode::Random;
            } else {
                throw std::invalid_argument("query-mode must be indexed or random");
            }
        } else {
            throw std::invalid_argument("unknown option: " + arg);
        }
    }

    if (cfg.build_threads == 0) {
        cfg.build_threads = cfg.threads;
    }

    return cfg;
}

size_t checked_mul(size_t a, size_t b, const std::string &name) {
    if (a != 0 && b > std::numeric_limits<size_t>::max() / a) {
        throw std::overflow_error(name + " size overflow");
    }
    return a * b;
}

void validate_config(const Config &cfg) {
    if (cfg.elements == 0 || cfg.dim == 0 || cfg.queries == 0 || cfg.iterations == 0 ||
        cfg.k == 0 || cfg.m == 0 || cfg.ef_construction == 0 || cfg.ef_search == 0 ||
        cfg.threads == 0 || cfg.build_threads == 0) {
        throw std::invalid_argument("all size/thread/HNSW parameters must be non-zero");
    }
    checked_mul(cfg.elements, cfg.dim, "data");
    checked_mul(cfg.queries, cfg.dim, "query");
    checked_mul(cfg.queries, cfg.iterations, "total query");
}

const char *query_mode_name(QueryMode mode) {
    return mode == QueryMode::Indexed ? "indexed" : "random";
}

void emit_config(const Config &cfg) {
    const size_t data_values = checked_mul(cfg.elements, cfg.dim, "data");
    const size_t data_bytes = checked_mul(data_values, sizeof(float), "data bytes");
    const size_t total_queries = checked_mul(cfg.queries, cfg.iterations, "total query");

    std::cout << "HEAPLENS_CONFIG"
              << " layout_variant=" << hnswlib::heaplens_hnsw_layout_variant()
              << " layout_name=" << hnswlib::heaplens_hnsw_layout_variant_name()
              << " elements=" << cfg.elements
              << " dim=" << cfg.dim
              << " queries=" << cfg.queries
              << " iterations=" << cfg.iterations
              << " total_queries=" << total_queries
              << " warmup=" << cfg.warmup
              << " threads=" << cfg.threads
              << " build_threads=" << cfg.build_threads
              << " m=" << cfg.m
              << " ef_construction=" << cfg.ef_construction
              << " ef_search=" << cfg.ef_search
              << " k=" << cfg.k
              << " query_mode=" << query_mode_name(cfg.query_mode)
              << " seed=" << cfg.seed
              << " input_data_bytes=" << data_bytes
              << std::endl;
}

void fill_vectors(std::vector<float> *values, size_t rows, size_t dim, uint64_t seed, size_t threads) {
    parallel_blocks(0, rows, threads, [&](size_t begin, size_t end, size_t /*thread_id*/) {
        for (size_t row = begin; row < end; ++row) {
            const size_t offset = row * dim;
            const uint64_t row_seed = seed ^ (static_cast<uint64_t>(row) * UINT64_C(0xd1b54a32d192ed03));
            for (size_t col = 0; col < dim; ++col) {
                (*values)[offset + col] =
                    unit_float(row_seed + static_cast<uint64_t>(col) * UINT64_C(0x9e3779b97f4a7c15));
            }
        }
    });
}

void fill_query_ids(std::vector<size_t> *query_ids, size_t elements, uint64_t seed) {
    for (size_t i = 0; i < query_ids->size(); ++i) {
        (*query_ids)[i] = static_cast<size_t>(
            splitmix64(seed + static_cast<uint64_t>(i) * UINT64_C(0xbf58476d1ce4e5b9)) %
            static_cast<uint64_t>(elements));
    }
}

struct QueryStats {
    uint64_t checksum;
    size_t queries;
    size_t results;
    size_t self_hits;
    double distance_sum;

    QueryStats() : checksum(0), queries(0), results(0), self_hits(0), distance_sum(0.0) {}
};

QueryStats run_searches(
    const Config &cfg,
    const hnswlib::HierarchicalNSW<float> &index,
    const std::vector<float> &data,
    const std::vector<size_t> &query_ids,
    const std::vector<float> &query_vectors,
    size_t total_queries) {
    std::vector<QueryStats> thread_stats(cfg.threads);

    parallel_blocks(0, total_queries, cfg.threads, [&](size_t begin, size_t end, size_t thread_id) {
        QueryStats local;

        for (size_t op = begin; op < end; ++op) {
            const size_t query_number = op % cfg.queries;
            const float *query = nullptr;
            hnswlib::labeltype expected_label = 0;
            bool has_expected_label = false;

            if (cfg.query_mode == QueryMode::Indexed) {
                const size_t row = query_ids[query_number];
                query = data.data() + row * cfg.dim;
                expected_label = static_cast<hnswlib::labeltype>(row);
                has_expected_label = true;
            } else {
                query = query_vectors.data() + query_number * cfg.dim;
            }

            std::priority_queue<std::pair<float, hnswlib::labeltype>> result =
                index.searchKnn(query, cfg.k);

            bool saw_expected_label = false;
            while (!result.empty()) {
                const float distance = result.top().first;
                const hnswlib::labeltype label = result.top().second;
                uint32_t distance_bits = 0;
                std::memcpy(&distance_bits, &distance, sizeof(distance_bits));

                local.checksum = mix_checksum(
                    local.checksum,
                    static_cast<uint64_t>(label) ^
                        (static_cast<uint64_t>(distance_bits) << 32) ^
                        static_cast<uint64_t>(local.results));
                local.distance_sum += static_cast<double>(distance);
                local.results++;

                if (has_expected_label && label == expected_label) {
                    saw_expected_label = true;
                }
                result.pop();
            }

            if (saw_expected_label) {
                local.self_hits++;
            }
            local.queries++;
        }

        thread_stats[thread_id] = local;
    });

    QueryStats total;
    for (size_t i = 0; i < thread_stats.size(); ++i) {
        total.checksum = mix_checksum(total.checksum, thread_stats[i].checksum + i);
        total.queries += thread_stats[i].queries;
        total.results += thread_stats[i].results;
        total.self_hits += thread_stats[i].self_hits;
        total.distance_sum += thread_stats[i].distance_sum;
    }

    return total;
}

}  // namespace

int main(int argc, char **argv) {
    try {
        Config cfg = parse_args(argc, argv);
        validate_config(cfg);
        emit_config(cfg);

        std::vector<float> data;
        {
            Phase phase("generate_data");
            const size_t data_values = checked_mul(cfg.elements, cfg.dim, "data");
            data.resize(data_values);
            HEAPLENS_LOG_REGION(HeapLensBenchmarkInputData,
                data.data(), data.size() * sizeof(float),
                ::hnswlib::heaplens::kFileBenchmark);
            fill_vectors(&data, cfg.elements, cfg.dim, cfg.seed, cfg.threads);
        }

        std::vector<size_t> query_ids;
        std::vector<float> query_vectors;
        if (cfg.query_mode == QueryMode::Indexed) {
            Phase phase("generate_query_ids");
            query_ids.resize(cfg.queries);
            HEAPLENS_LOG_REGION(HeapLensBenchmarkQueryIds,
                query_ids.data(), query_ids.size() * sizeof(size_t),
                ::hnswlib::heaplens::kFileBenchmark);
            fill_query_ids(&query_ids, cfg.elements, cfg.seed ^ UINT64_C(0x123456789abcdef0));
        } else {
            Phase phase("generate_queries");
            const size_t query_values = checked_mul(cfg.queries, cfg.dim, "query");
            query_vectors.resize(query_values);
            HEAPLENS_LOG_REGION(HeapLensBenchmarkQueryVectors,
                query_vectors.data(), query_vectors.size() * sizeof(float),
                ::hnswlib::heaplens::kFileBenchmark);
            fill_vectors(&query_vectors, cfg.queries, cfg.dim,
                         cfg.seed ^ UINT64_C(0xfedcba9876543210), cfg.threads);
        }

        hnswlib::L2Space space(cfg.dim);
        std::unique_ptr<hnswlib::HierarchicalNSW<float>> index;

        double build_seconds = 0.0;
        {
            Phase phase("build_index");
            Timer timer;
            index.reset(new hnswlib::HierarchicalNSW<float>(
                &space, cfg.elements, cfg.m, cfg.ef_construction, cfg.seed));
            parallel_blocks(0, cfg.elements, cfg.build_threads, [&](size_t begin, size_t end, size_t /*thread_id*/) {
                for (size_t row = begin; row < end; ++row) {
                    index->addPoint(data.data() + row * cfg.dim, static_cast<hnswlib::labeltype>(row));
                }
            });
            build_seconds = timer.elapsed_seconds();
        }

        std::cout << "HEAPLENS_RESULT phase=build"
                  << " seconds=" << build_seconds
                  << " inserts_per_second=" << static_cast<double>(cfg.elements) / build_seconds
                  << " elements=" << index->getCurrentElementCount()
                  << " rss_bytes=" << current_rss_bytes()
                  << std::endl;

        index->setEf(cfg.ef_search);

        if (cfg.warmup > 0) {
            Phase phase("warmup_search");
            QueryStats warmup = run_searches(cfg, *index, data, query_ids, query_vectors, cfg.warmup);
            std::cout << "HEAPLENS_RESULT phase=warmup"
                      << " queries=" << warmup.queries
                      << " results=" << warmup.results
                      << " checksum=" << warmup.checksum
                      << " rss_bytes=" << current_rss_bytes()
                      << std::endl;
        }

        const size_t total_queries = checked_mul(cfg.queries, cfg.iterations, "total query");
        QueryStats query_stats;
        double query_seconds = 0.0;
        {
            Phase phase("steady_search");
            Timer timer;
            query_stats = run_searches(cfg, *index, data, query_ids, query_vectors, total_queries);
            query_seconds = timer.elapsed_seconds();
        }

        const double qps = static_cast<double>(query_stats.queries) / query_seconds;
        const double us_per_query = 1000000.0 / qps;
        const double self_recall =
            cfg.query_mode == QueryMode::Indexed
                ? static_cast<double>(query_stats.self_hits) / static_cast<double>(query_stats.queries)
                : -1.0;

        std::cout << "HEAPLENS_RESULT phase=query"
                  << " seconds=" << query_seconds
                  << " queries=" << query_stats.queries
                  << " qps=" << qps
                  << " us_per_query=" << us_per_query
                  << " results=" << query_stats.results
                  << " checksum=" << query_stats.checksum
                  << " distance_sum=" << query_stats.distance_sum
                  << " self_recall_at_k=" << self_recall
                  << " rss_bytes=" << current_rss_bytes()
                  << std::endl;

        return 0;
    } catch (const std::exception &e) {
        std::cerr << "heaplens_hnsw_bench: " << e.what() << std::endl;
        return 1;
    }
}
