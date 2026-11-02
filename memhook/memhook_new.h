#ifndef HEAPLENS_MEMHOOK_NEW_H
#define HEAPLENS_MEMHOOK_NEW_H

// Capture the bound at its original evaluation position and with its original
// signedness. In particular, do not turn a negative bound into an unsigned one
// before the language's own new[] checks. The stamp reads the saved count only
// after construction, irrespective of operator* operand evaluation order.
template <class N>
inline N memhook_capture_extent(size_t& count, N value) {
    count = static_cast<size_t>(value);
    return value;
}
struct MemPlacementArrayStamp : MemStamp {
    const size_t& count;
    MemPlacementArrayStamp(uint16_t f, int l, const size_t& n)
        : MemStamp(f, l), count(n) {}
};
template <class T>
inline T* operator*(const MemPlacementArrayStamp& stamp, T* p) {
    memhook_info_t enclosing = unit_log;
    if (stamp.count <= static_cast<size_t>(-1) / sizeof(T))
        memhook_record_alloc(p, stamp.count * sizeof(T), typeid(T), stamp.filename, stamp.lineNum);
    unit_log = enclosing;
    return p;
}

// The annotator adds this argument only to standard global allocating new
// expressions. Log the compiler-supplied allocation extent before invoking any
// constructors, so nested construction cannot overwrite pending metadata.
// Keep standard placement-new syntax unchanged: replacing its allocation
// function can introduce an array cookie and change the supplied-storage ABI.
template <class T> struct MemhookNew {
    uint16_t file;
    int line;
    MemhookNew(uint16_t f, int l) : file(f), line(l) {}
    void record(void* p, size_t size) const {
        memhook_record_alloc(p, size, typeid(T), file, line);
    }
};

template <class T>
inline void* operator new(size_t size, const MemhookNew<T>& site) {
    void* p = ::operator new(size);
    site.record(p, size);
    return p;
}
template <class T>
inline void* operator new[](size_t size, const MemhookNew<T>& site) {
    void* p = ::operator new[](size);
    site.record(p, size);
    return p;
}
template <class T>
inline void* operator new(size_t size, const MemhookNew<T>& site,
                          const std::nothrow_t& tag) noexcept {
    void* p = ::operator new(size, tag);
    site.record(p, size);
    return p;
}
template <class T>
inline void* operator new[](size_t size, const MemhookNew<T>& site,
                            const std::nothrow_t& tag) noexcept {
    void* p = ::operator new[](size, tag);
    site.record(p, size);
    return p;
}

// Matching placement-delete overloads are used if a constructor throws.
template <class T>
inline void operator delete(void* p, const MemhookNew<T>&) noexcept {
    ::operator delete(p);
}
template <class T>
inline void operator delete[](void* p, const MemhookNew<T>&) noexcept {
    ::operator delete[](p);
}
template <class T>
inline void operator delete(void* p, const MemhookNew<T>&,
                            const std::nothrow_t& tag) noexcept {
    ::operator delete(p, tag);
}
template <class T>
inline void operator delete[](void* p, const MemhookNew<T>&,
                              const std::nothrow_t& tag) noexcept {
    ::operator delete[](p, tag);
}

#if defined(__cpp_aligned_new)
template <class T>
inline void* operator new(size_t size, std::align_val_t align,
                          const MemhookNew<T>& site) {
    void* p = ::operator new(size, align);
    site.record(p, size);
    return p;
}
template <class T>
inline void* operator new[](size_t size, std::align_val_t align,
                            const MemhookNew<T>& site) {
    void* p = ::operator new[](size, align);
    site.record(p, size);
    return p;
}
template <class T>
inline void* operator new(size_t size, std::align_val_t align,
                          const MemhookNew<T>& site,
                          const std::nothrow_t& tag) noexcept {
    void* p = ::operator new(size, align, tag);
    site.record(p, size);
    return p;
}
template <class T>
inline void* operator new[](size_t size, std::align_val_t align,
                            const MemhookNew<T>& site,
                            const std::nothrow_t& tag) noexcept {
    void* p = ::operator new[](size, align, tag);
    site.record(p, size);
    return p;
}
template <class T>
inline void operator delete(void* p, std::align_val_t align,
                            const MemhookNew<T>&) noexcept {
    ::operator delete(p, align);
}
template <class T>
inline void operator delete[](void* p, std::align_val_t align,
                              const MemhookNew<T>&) noexcept {
    ::operator delete[](p, align);
}
template <class T>
inline void operator delete(void* p, std::align_val_t align,
                            const MemhookNew<T>&, const std::nothrow_t& tag) noexcept {
    ::operator delete(p, align, tag);
}
template <class T>
inline void operator delete[](void* p, std::align_val_t align,
                              const MemhookNew<T>&, const std::nothrow_t& tag) noexcept {
    ::operator delete[](p, align, tag);
}
#endif
#endif
