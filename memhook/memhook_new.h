#ifndef HEAPLENS_MEMHOOK_NEW_H
#define HEAPLENS_MEMHOOK_NEW_H

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
