#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <stdint.h>

#ifdef _WIN32
#include <fcntl.h>
#include <io.h>
#include <windows.h>
#endif

typedef int32_t int32;
typedef uint32_t uint32;
typedef uint16_t uint16;
typedef uint8_t uint8;
typedef uint64_t uint64;

extern "C" {
int32 qsf_start(uint8 *buffer, uint32 length);
int32 qsf_sample(void *sample);
int32 qsf_stop(void);

uint8 qsf_memory_read(uint16 addr);
uint8 qsf_memory_readop(uint16 addr);
uint8 qsf_memory_readport(uint16 addr);
void qsf_memory_write(uint16 addr, uint8 data);
void qsf_memory_writeport(uint16 addr, uint8 data);

uint8 memory_read(uint16 addr) { return qsf_memory_read(addr); }
uint8 memory_readop(uint16 addr) { return qsf_memory_readop(addr); }
uint8 memory_readport(uint16 addr) { return qsf_memory_readport(addr); }
void memory_write(uint16 addr, uint8 data) { qsf_memory_write(addr, data); }
void memory_writeport(uint16 addr, uint8 data) { qsf_memory_writeport(addr, data); }
}

static char g_base_dir[4096];

static void *load_file_to_buffer(const char *path, unsigned *out_size)
{
    FILE *f = fopen(path, "rb");
    if (!f)
        return nullptr;

    fseek(f, 0, SEEK_END);
    long size = ftell(f);
    fseek(f, 0, SEEK_SET);

    if (size <= 0)
    {
        fclose(f);
        return nullptr;
    }

    void *buf = malloc(size);
    if (!buf)
    {
        fclose(f);
        return nullptr;
    }

    size_t read = fread(buf, 1, size, f);
    fclose(f);

    if ((long)read != size)
    {
        free(buf);
        return nullptr;
    }

    if (out_size)
        *out_size = (unsigned)size;
    return buf;
}

extern "C" int ao_get_lib(const char *filename, uint8 **buffer, uint64 *length)
{
    std::fprintf(stderr, "aoqsf: library requested: '%s'\n", filename);
    char path[4096];
    snprintf(path, sizeof(path), "%s/%s", g_base_dir, filename);
    unsigned size = 0;
    void *buf = load_file_to_buffer(path, &size);
    if (!buf) {
        std::fprintf(stderr, "aoqsf: failed to load library '%s'\n", path);
        return 0; // AO_FAIL
    }
    *buffer = (uint8 *)buf;
    *length = size;
    return 1; // AO_SUCCESS
}

static void extract_base_dir(const char *path, char *out, size_t out_size)
{
    const char *last_sep = nullptr;
    const char *p = path;
    while (*p)
    {
        if (*p == '\\' || *p == '/')
            last_sep = p;
        p++;
    }

    if (last_sep)
    {
        size_t len = last_sep - path;
        if (len >= out_size)
            len = out_size - 1;
        memcpy(out, path, len);
        out[len] = '\0';
    }
    else
    {
        out[0] = '.';
        out[1] = '\0';
    }
}

static volatile bool g_stop = false;

static void write_pcm(const void *data, int bytes)
{
    if (!data || bytes <= 0)
        return;

    const char *cursor = static_cast<const char *>(data);
    int remaining = bytes;
    while (remaining > 0 && !g_stop)
    {
        const int written = static_cast<int>(std::fwrite(cursor, 1, remaining, stdout));
        if (written <= 0)
        {
            g_stop = true;
            return;
        }
        cursor += written;
        remaining -= written;
    }
    std::fflush(stdout);
}

int main(int argc, char **argv)
{
#ifdef _WIN32
    _setmode(_fileno(stdout), _O_BINARY);
#endif

    if (argc < 2)
    {
        std::fprintf(stderr, "usage: aoqsf_helper <file.qsf|miniqsf>\n");
        return 2;
    }

    const char *input_path = argv[1];

    // Convert to absolute path if relative
    char abs_path[4096];
#ifdef _WIN32
    if (!GetFullPathNameA(input_path, sizeof(abs_path), abs_path, nullptr))
    {
        strncpy(abs_path, input_path, sizeof(abs_path) - 1);
        abs_path[sizeof(abs_path) - 1] = '\0';
    }
#else
    if (input_path[0] == '/')
    {
        strncpy(abs_path, input_path, sizeof(abs_path) - 1);
        abs_path[sizeof(abs_path) - 1] = '\0';
    }
    else
    {
        char cwd[4096];
        if (getcwd(cwd, sizeof(cwd)))
        {
            snprintf(abs_path, sizeof(abs_path), "%s/%s", cwd, input_path);
        }
        else
        {
            strncpy(abs_path, input_path, sizeof(abs_path) - 1);
            abs_path[sizeof(abs_path) - 1] = '\0';
        }
    }
#endif

    extract_base_dir(abs_path, g_base_dir, sizeof(g_base_dir));

    unsigned file_size = 0;
    void *file_buf = load_file_to_buffer(abs_path, &file_size);
    if (!file_buf)
    {
        std::fprintf(stderr, "aoqsf: failed to load %s (abs: %s)\n", input_path, abs_path);
        return 3;
    }

    int result = qsf_start((uint8 *)file_buf, file_size);
    if (result != 1)
    {
        std::fprintf(stderr, "aoqsf: failed to initialize playback\n");
        free(file_buf);
        return 3;
    }

    free(file_buf);

    short buffer[2];

    while (!g_stop)
    {
        int generated = qsf_sample(buffer);
        if (generated != 1)
            break;

        write_pcm(buffer, 2 * sizeof(short));
    }

    qsf_stop();
    return 0;
}
