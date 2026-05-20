#include <stdlib.h>

void* operator new(size_t size) {
    return malloc(size);
}

// void* operator new(unsigned int size) {
//     return malloc(size);
// }

void operator delete(void* ptr) noexcept {
    free(ptr);
}

void* operator new[](size_t size) {
    return malloc(size);
}

// void* operator new[](unsigned int size) {
//     return malloc(size);
// }

void operator delete[](void* ptr) noexcept {
    free(ptr);
}

// C++14
void operator delete(void* ptr, size_t size) noexcept {
    free(ptr);
}

void operator delete[](void* ptr, size_t size) noexcept {
    free(ptr);
}
