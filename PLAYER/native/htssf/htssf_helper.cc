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

#include "psflib.h"
#include "sega.h"

static std::filesystem::path g_base_dir;
static volatile bool g_stop = false;

static bool is_silent(const char * data, int bytes)
{
    const int16_t * samples = reinterpret_cast<const int16_t *>(data);
    int count = bytes / sizeof(int16_t);
    for (int i = 0; i < count; i++) {
        if (samples[i] != 0) return false;
    }
    return true;
}

static const int MAX_INIT_SILENCE_BYTES = 264600;
static int init_silence_skipped = 0;
static bool started = false;

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

struct sdsf_load_state
{
    std::vector<uint8_t> data;
};

static int sdsf_load(void * context, const uint8_t * exe, size_t exe_size,
                     const uint8_t * reserved, size_t reserved_size)
{
    if (exe_size < 4) return -1;

    sdsf_load_state * state = static_cast<sdsf_load_state *>(context);
    std::vector<uint8_t> & dst = state->data;

    if (dst.size() < 4)
    {
        dst.resize(exe_size);
        std::memcpy(dst.data(), exe, exe_size);
        return 0;
    }

    uint32_t dst_start = *(uint32_t *)(dst.data());
    uint32_t src_start = *(uint32_t *)(const_cast<uint8_t *>(exe));

    dst_start &= 0x7FFFFF;
    src_start &= 0x7FFFFF;

    uint32_t dst_len = static_cast<uint32_t>(dst.size() - 4);
    uint32_t src_len = static_cast<uint32_t>(exe_size - 4);

    if (dst_len > 0x800000) dst_len = 0x800000;
    if (src_len > 0x800000) src_len = 0x800000;

    if (src_start < dst_start)
    {
        uint32_t diff = dst_start - src_start;
        dst.resize(dst_len + 4 + diff);
        std::memmove(dst.data() + 4 + diff, dst.data() + 4, dst_len);
        std::memset(dst.data() + 4, 0, diff);
        dst_len += diff;
        dst_start = src_start;
        *(uint32_t *)(dst.data()) = dst_start;
    }

    if ((src_start + src_len) > (dst_start + dst_len))
    {
        uint32_t diff = (src_start + src_len) - (dst_start + dst_len);
        dst.resize(dst_len + 4 + diff);
        std::memset(dst.data() + 4 + dst_len, 0, diff);
        dst_len += diff;
    }

    std::memcpy(dst.data() + 4 + (src_start - dst_start), exe + 4, src_len);
    return 0;
}

static void * psf_file_fopen(void * context, const char * path)
{
    (void)context;
    std::filesystem::path p(path);
    if (p.is_relative())
        p = g_base_dir / p;

    FILE * f = std::fopen(p.string().c_str(), "rb");
    return static_cast<void *>(f);
}

static size_t psf_file_fread(void * buffer, size_t size, size_t count, void * handle)
{
    return std::fread(buffer, size, count, static_cast<FILE *>(handle));
}

static int psf_file_fseek(void * handle, int64_t offset, int whence)
{
#ifdef _WIN32
    return _fseeki64(static_cast<FILE *>(handle), offset, whence);
#else
    return std::fseeko(static_cast<FILE *>(handle), offset, whence);
#endif
}

static int psf_file_fclose(void * handle)
{
    return std::fclose(static_cast<FILE *>(handle));
}

static long psf_file_ftell(void * handle)
{
    return std::ftell(static_cast<FILE *>(handle));
}

static const psf_file_callbacks psf_file_system = {
    "\\/|:",
    nullptr,
    psf_file_fopen,
    psf_file_fread,
    psf_file_fseek,
    psf_file_fclose,
    psf_file_ftell
};

static void write_pcm(const void * data, int bytes)
{
    if (!data || bytes <= 0)
        return;

    if (!started) {
        if (!is_silent(static_cast<const char *>(data), bytes)) {
            started = true;
        } else if (init_silence_skipped + bytes < MAX_INIT_SILENCE_BYTES) {
            init_silence_skipped += bytes;
            return;
        } else {
            started = true;
        }
    }

    const char * cursor = static_cast<const char *>(data);
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
}

int main(int argc, char ** argv)
{
#ifdef _WIN32
    _setmode(_fileno(stdout), _O_BINARY);
#endif

    if (argc < 2)
    {
        std::fprintf(stderr, "usage: htssf_helper <file.ssf|minissf|dsf|minidsf>\n");
        return 2;
    }

    const std::filesystem::path input_path = std::filesystem::absolute(argv[1]);
    g_base_dir = input_path.parent_path();

    if (sega_init() != 0)
    {
        std::fprintf(stderr, "htssf: sega_init failed\n");
        return 3;
    }

    sdsf_load_state load_state;

    int version = psf_load(
        input_path.string().c_str(),
        &psf_file_system,
        0,
        sdsf_load,
        &load_state,
        nullptr,
        nullptr,
        0,
        nullptr,
        nullptr
    );

    if (version != 0x11 && version != 0x12)
    {
        std::fprintf(stderr, "htssf: not a SSF/DSF file (version 0x%02x)\n", version);
        return 4;
    }

    if (load_state.data.empty() || load_state.data.size() < 4)
    {
        std::fprintf(stderr, "htssf: no program data loaded\n");
        return 5;
    }

    uint8_t emu_version = (version == 0x11) ? 1 : 2;

    uint32_t state_size = sega_get_state_size(emu_version);
    void * state = std::malloc(state_size);
    if (!state)
    {
        std::fprintf(stderr, "htssf: out of memory for emulator state\n");
        return 6;
    }

    sega_clear_state(state, emu_version);
    sega_enable_dry(state, 1);
    sega_enable_dsp(state, 1);
    sega_enable_dsp_dynarec(state, 0);

    uint32_t start = *(uint32_t *)(load_state.data.data());
    uint32_t length = static_cast<uint32_t>(load_state.data.size());
    uint32_t max_length = (version == 0x12) ? 0x800000 : 0x80000;

    if ((start + (length - 4)) > max_length)
        length = max_length - start + 4;

    if (sega_upload_program(state, load_state.data.data(), length) != 0)
    {
        std::fprintf(stderr, "htssf: sega_upload_program failed\n");
        std::free(state);
        return 7;
    }

    int16_t sample_buffer[2048 * 2];

    while (!g_stop)
    {
        uint32_t samples = 2048;
        int rtn = sega_execute(state, 0x7FFFFFFF, sample_buffer, &samples);
        if (rtn < 0 || samples == 0)
            break;

        write_pcm(sample_buffer, static_cast<int>(samples * 2 * sizeof(int16_t)));
    }

    std::free(state);
    return 0;
}
