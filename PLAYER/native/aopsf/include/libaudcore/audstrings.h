#pragma once

#include <cctype>
#include <cstring>

static inline int strcmp_nocase(const char * a, const char * b)
{
    if (!a || !b)
        return a == b ? 0 : (a ? 1 : -1);

    while (*a && *b)
    {
        const int ca = std::tolower(static_cast<unsigned char>(*a));
        const int cb = std::tolower(static_cast<unsigned char>(*b));
        if (ca != cb)
            return ca - cb;
        ++a;
        ++b;
    }

    return std::tolower(static_cast<unsigned char>(*a)) - std::tolower(static_cast<unsigned char>(*b));
}
