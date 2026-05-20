#include <cstdio>
#include <cstdlib>
#include <cstring>

#ifdef _WIN32
#include <fcntl.h>
#include <io.h>
#include <windows.h>
#endif

extern "C" {
int xsf_start(void *pfile, unsigned bytes);
int xsf_gen(void *pbuffer, unsigned samples);
void xsf_term(void);
int xsf_get_lib(char *pfilename, void **ppbuffer, unsigned *plength);
extern unsigned long dwChannelMute;
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

int xsf_get_lib(char *pfilename, void **ppbuffer, unsigned *plength)
{
    char path[4096];
    snprintf(path, sizeof(path), "%s\\%s", g_base_dir, pfilename);

    void *buf = load_file_to_buffer(path, plength);
    if (buf)
    {
        *ppbuffer = buf;
        return 1;
    }
    return 0;
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
        std::fprintf(stderr, "usage: vio2sf_helper <file.2sf|mini2sf>\n");
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
        std::fprintf(stderr, "vio2sf: failed to load %s (abs: %s)\n", input_path, abs_path);
        return 3;
    }

    int result = xsf_start(file_buf, file_size);
    if (!result)
    {
        std::fprintf(stderr, "vio2sf: failed to initialize playback\n");
        free(file_buf);
        return 3;
    }

    free(file_buf);

    const int samples_per_chunk = 1024;
    short buffer[1024 * 2];

    // Skip initial silence by consuming samples until we get a chunk with mostly non-zero output
    // or until we've consumed a reasonable amount (5 seconds at 44100 Hz)
    const int max_silence_samples = 44100 * 5;
    int consumed_silence = 0;
    bool found_audio = false;

    while (!g_stop && consumed_silence < max_silence_samples)
    {
        int generated = xsf_gen(buffer, samples_per_chunk);
        if (generated <= 0)
            break;

        consumed_silence += generated;

        // Check if this chunk has mostly non-zero samples (>50%)
        int non_zero_count = 0;
        for (int i = 0; i < generated * 2; i++)
        {
            if (buffer[i] != 0)
                non_zero_count++;
        }

        if (non_zero_count > generated) // More than 50% non-zero
        {
            // Output this chunk and break out of silence skip
            write_pcm(buffer, generated * 2 * sizeof(short));
            found_audio = true;
            break;
        }
    }

    if (!found_audio)
    {
        // File is completely silent, just exit
        xsf_term();
        return 0;
    }

    // Continue normal playback
    while (!g_stop)
    {
        int generated = xsf_gen(buffer, samples_per_chunk);
        if (generated <= 0)
            break;

        write_pcm(buffer, generated * 2 * sizeof(short));
    }

    xsf_term();
    return 0;
}
