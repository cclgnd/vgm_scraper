#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <string>
#include <vector>

#ifdef _WIN32
#include <fcntl.h>
#include <io.h>
#endif

#include "ao.h"
#include "psx.h"

bool stop_flag = false;

static std::filesystem::path g_base_dir;

static std::vector<char> read_file(const std::filesystem::path & path)
{
    std::ifstream file(path, std::ios::binary);
    if (!file)
        return {};

    file.seekg(0, std::ios::end);
    const std::streamoff size = file.tellg();
    file.seekg(0, std::ios::beg);

    if (size <= 0)
        return {};

    std::vector<char> data(static_cast<size_t>(size));
    file.read(data.data(), size);
    if (!file)
        return {};
    return data;
}

Index<char> ao_get_lib(char * filename)
{
    if (!filename || !*filename)
        return Index<char>();

    std::filesystem::path lib_path(filename);
    if (lib_path.is_relative())
        lib_path = g_base_dir / lib_path;

    return Index<char>(read_file(lib_path));
}

static void write_pcm(const void * data, int bytes)
{
    if (!data || bytes <= 0)
        return;

    const char * cursor = static_cast<const char *>(data);
    int remaining = bytes;
    while (remaining > 0)
    {
        const int written = static_cast<int>(std::fwrite(cursor, 1, remaining, stdout));
        if (written <= 0)
        {
            stop_flag = true;
            return;
        }
        cursor += written;
        remaining -= written;
    }
}

int main(int argc, char ** argv)
{
#ifdef _WIN32
    _setmode(_fileno(stdout), _O_BINARY);
#endif

    if (argc < 2)
    {
        std::fprintf(stderr, "usage: aopsf2_helper <file.psf2|minipsf2>\n");
        return 2;
    }

    const std::filesystem::path input_path = std::filesystem::absolute(argv[1]);
    g_base_dir = input_path.parent_path();

    std::vector<char> data = read_file(input_path);
    if (data.empty())
    {
        std::fprintf(stderr, "aopsf2: unable to read input file\n");
        return 3;
    }

    if (data.size() < 4 || std::memcmp(data.data(), "PSF\002", 4) != 0)
    {
        std::fprintf(stderr, "aopsf2: only PSF2 is supported by this helper\n");
        return 4;
    }

    if (psf2_start(reinterpret_cast<uint8_t *>(data.data()), static_cast<uint32_t>(data.size())) != AO_SUCCESS)
    {
        std::fprintf(stderr, "aopsf2: psf2_start failed\n");
        return 5;
    }

    const int result = psf2_execute(write_pcm);
    psf2_stop();
    return result == AO_SUCCESS ? 0 : 6;
}
