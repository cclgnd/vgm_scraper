#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

#ifdef _WIN32
#include <fcntl.h>
#include <io.h>
#endif

#include "usf/usf.h"
#include "psflib.h"

unsigned char *state = 0;

static unsigned long length_ms = 0;
static unsigned long fade_ms = 0;
static int track_length_set = 0;

static volatile int g_stop = 0;

static void *stdio_fopen(void *context, const char *path)
{
    return fopen(path, "rb");
}

static size_t stdio_fread(void *p, size_t size, size_t count, void *f)
{
    return fread(p, size, count, (FILE *)f);
}

static int stdio_fseek(void *f, int64_t offset, int whence)
{
    return fseek((FILE *)f, (long)offset, whence);
}

static int stdio_fclose(void *f)
{
    return fclose((FILE *)f);
}

static long stdio_ftell(void *f)
{
    return ftell((FILE *)f);
}

static psf_file_callbacks stdio_callbacks = {
    "\\/:",
    NULL,
    stdio_fopen,
    stdio_fread,
    stdio_fseek,
    stdio_fclose,
    stdio_ftell
};

static int usf_loader(void *context, const uint8_t *exe, size_t exe_size,
                      const uint8_t *reserved, size_t reserved_size)
{
    if (exe && exe_size > 0) return -1;
    return usf_upload_section(state, reserved, reserved_size);
}

#define BORK_TIME 0xC0CAC01A

static unsigned long parse_time_crap(const char *input)
{
    unsigned long value = 0;
    unsigned long multiplier = 1000;
    const char *ptr = input;
    unsigned long colon_count = 0;

    while (*ptr && ((*ptr >= '0' && *ptr <= '9') || *ptr == ':')) {
        colon_count += (*ptr == ':');
        ++ptr;
    }
    if (colon_count > 2) return BORK_TIME;
    if (*ptr && *ptr != '.' && *ptr != ',') return BORK_TIME;
    if (*ptr) ++ptr;
    while (*ptr && *ptr >= '0' && *ptr <= '9') ++ptr;
    if (*ptr) return BORK_TIME;

    ptr = strrchr(input, ':');
    if (!ptr)
        ptr = input;
    for (;;) {
        char *end;
        if (ptr != input) ++ptr;
        if (multiplier == 1000) {
            double temp = strtod(ptr, &end);
            if (temp >= 60.0) return BORK_TIME;
            value = (long)(temp * 1000.0f);
        } else {
            unsigned long temp = strtoul(ptr, &end, 10);
            if (temp >= 60 && multiplier < 3600000) return BORK_TIME;
            value += temp * multiplier;
        }
        if (ptr == input) break;
        ptr -= 2;
        while (ptr > input && *ptr != ':') --ptr;
        multiplier *= 60;
    }

    return value;
}

static int usf_info(void *context, const char *name, const char *value)
{
    if (!strcasecmp(name, "length")) {
        unsigned long t = parse_time_crap(value);
        if (t != BORK_TIME) {
            length_ms = t;
            track_length_set = 1;
        }
    } else if (!strcasecmp(name, "fade")) {
        unsigned long t = parse_time_crap(value);
        if (t != BORK_TIME) fade_ms = t;
    }
    return 0;
}

static void print_message(void *unused, const char *message)
{
    fputs(message, stderr);
}

static void write_pcm(const void *data, int bytes)
{
    if (!data || bytes <= 0) return;
    const char *cursor = (const char *)data;
    int remaining = bytes;
    while (remaining > 0 && !g_stop) {
        int written = (int)fwrite(cursor, 1, remaining, stdout);
        if (written <= 0) {
            g_stop = 1;
            return;
        }
        cursor += written;
        remaining -= written;
    }
}

int main(int argc, char **argv)
{
#ifdef _WIN32
    _setmode(_fileno(stdout), _O_BINARY);
#endif

    if (argc < 2) {
        fprintf(stderr, "usage: aousf_helper <file.usf|mini.usf>\n");
        return 2;
    }

    state = (unsigned char *)malloc(usf_get_state_size());
    if (!state) {
        fprintf(stderr, "aousf: out of memory\n");
        return 3;
    }

    usf_clear(state);

    if (psf_load(argv[1], &stdio_callbacks, 0x21, usf_loader, 0, usf_info, 0, 1, print_message, 0) <= 0) {
        fprintf(stderr, "aousf: failed to load %s\n", argv[1]);
        free(state);
        return 3;
    }

    usf_set_hle_audio(state, 1);

    if (!track_length_set || length_ms == 0) {
        length_ms = 180000;
    }
    if (fade_ms == 0) {
        fade_ms = 5000;
    }

    int32_t length_to_render = (int32_t)(length_ms * 441 / 10);
    int32_t fade_total = (int32_t)(fade_ms * 441 / 10);

    int16_t sample_buffer[2048];

    while (length_to_render > 0 && !g_stop) {
        int32_t samples_todo = length_to_render;
        if (samples_todo > 1024)
            samples_todo = 1024;

        usf_render_resampled(state, sample_buffer, samples_todo, 44100);
        write_pcm(sample_buffer, samples_todo * 4);

        length_to_render -= samples_todo;
    }

    while (fade_total > 0 && !g_stop) {
        int32_t samples_todo = fade_total;
        if (samples_todo > 1024)
            samples_todo = 1024;

        usf_render_resampled(state, sample_buffer, samples_todo, 44100);

        int32_t i;
        for (i = 0; i < samples_todo; ++i) {
            int64_t vol = (int64_t)(fade_total - i) * 32767 / fade_total;
            sample_buffer[i * 2 + 0] = (int16_t)((int64_t)sample_buffer[i * 2 + 0] * vol / 32767);
            sample_buffer[i * 2 + 1] = (int16_t)((int64_t)sample_buffer[i * 2 + 1] * vol / 32767);
        }

        write_pcm(sample_buffer, samples_todo * 4);
        fade_total -= samples_todo;
    }

    usf_shutdown(state);
    free(state);
    return 0;
}
