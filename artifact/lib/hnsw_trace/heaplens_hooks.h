#pragma once

#include <stdint.h>
#include <stddef.h>
#include <stdlib.h>

#ifndef HEAPLENS_HNSW_LAYOUT_VARIANT
#define HEAPLENS_HNSW_LAYOUT_VARIANT 0
#endif

#if defined(HEAPLENS_ENABLE)
#include "memhook_interface.h"
#endif

namespace hnswlib {
namespace heaplens {

static const uint16_t kFileHnswAlg = 65001;
static const uint16_t kFileVisitedListPool = 65002;
static const uint16_t kFileBenchmark = 65003;

struct HeapLensHnswLevel0Slab {};
struct HeapLensHnswLevel0Element {};
struct HeapLensHnswLevel0LinkCount {};
struct HeapLensHnswLevel0Neighbors {};
struct HeapLensHnswVectorPayload {};
struct HeapLensHnswVectorSlab {};
struct HeapLensHnswLabel {};
struct HeapLensHnswLabelSlab {};
struct HeapLensHnswUpperLinksPointerTable {};
struct HeapLensHnswUpperLinksBlock {};
struct HeapLensHnswUpperLinkCount {};
struct HeapLensHnswUpperNeighbors {};
struct HeapLensHnswUpperPadding {};
struct HeapLensHnswVisitedList {};
struct HeapLensHnswVisitedMass {};
struct HeapLensBenchmarkInputData {};
struct HeapLensBenchmarkQueryIds {};
struct HeapLensBenchmarkQueryVectors {};

#if defined(HEAPLENS_ENABLE)

template <class Tag>
inline void *allocate(size_t size, uint16_t file_id, int line) {
    unit_log.file = file_id;
    unit_log.tindex_name = typetable.insert(&typeid(Tag));
    void *ptr = memhook_malloc(size, line, true);
    memhookCollector.copy(unit_log);
    return ptr;
}

template <class Tag>
inline void *allocate_aligned(size_t alignment, size_t size, uint16_t file_id, int line) {
    if (alignment < sizeof(void *)) {
        alignment = sizeof(void *);
    }
    void *ptr = NULL;
    if (posix_memalign(&ptr, alignment, size) != 0) {
        return NULL;
    }
    MEMHOOK_LOG_CPP_ALLOC_AT(ptr, size, typeid(Tag), file_id, line)
    return ptr;
}

inline void deallocate(void *ptr) {
    if (ptr == NULL) {
        return;
    }
    memhook_free(ptr, 0, false);
    memhookCollector.copy(unit_log);
}

template <class Tag>
inline void log_region(void *ptr, size_t size, uint16_t file_id, int line) {
    if (ptr == NULL || size == 0) {
        return;
    }
    MEMHOOK_LOG_CPP_ALLOC_AT(ptr, size, typeid(Tag), file_id, line)
}

#else

template <class Tag>
inline void *allocate(size_t size, uint16_t, int) {
    return malloc(size);
}

template <class Tag>
inline void *allocate_aligned(size_t alignment, size_t size, uint16_t, int) {
    if (alignment < sizeof(void *)) {
        alignment = sizeof(void *);
    }
    void *ptr = NULL;
    if (posix_memalign(&ptr, alignment, size) != 0) {
        return NULL;
    }
    return ptr;
}

inline void deallocate(void *ptr) {
    free(ptr);
}

template <class Tag>
inline void log_region(void *, size_t, uint16_t, int) {}

#endif

}  // namespace heaplens
}  // namespace hnswlib

#define HEAPLENS_ALLOC(TAG, SIZE, FILE_ID) \
    ::hnswlib::heaplens::allocate<::hnswlib::heaplens::TAG>((SIZE), (FILE_ID), __LINE__)

#define HEAPLENS_ALLOC_ALIGNED(TAG, ALIGNMENT, SIZE, FILE_ID) \
    ::hnswlib::heaplens::allocate_aligned<::hnswlib::heaplens::TAG>( \
        (ALIGNMENT), (SIZE), (FILE_ID), __LINE__)

#define HEAPLENS_FREE(PTR) \
    ::hnswlib::heaplens::deallocate((PTR))

#define HEAPLENS_LOG_REGION(TAG, PTR, SIZE, FILE_ID) \
    ::hnswlib::heaplens::log_region<::hnswlib::heaplens::TAG>( \
        reinterpret_cast<void *>(PTR), (SIZE), (FILE_ID), __LINE__)
