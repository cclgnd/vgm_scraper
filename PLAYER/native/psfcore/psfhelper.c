#include <stdint.h>
#include <stdio.h>
#include <string.h>

int sp_psf_open(const char *path, void **out_handle);
int sp_psf_render(void *handle, int frames, int16_t *stereo_out);
void sp_psf_close(void *handle);
const char *sp_psf_last_error(void);

#define FRAMES_PER_CHUNK 1024
#define MAX_INIT_SILENCE_CHUNKS 100

static int is_silent(const int16_t *samples, int count) {
    for (int i = 0; i < count; i++) {
        if (samples[i] != 0) return 0;
    }
    return 1;
}

int main(int argc, char **argv) {
    void *handle = NULL;
    int16_t buffer[FRAMES_PER_CHUNK * 2];
    int quiet_chunks = 0;
    int init_silence_chunks = 0;
    int started = 0;

    if (argc < 2) {
        fprintf(stderr, "usage: psfhelper.exe file.psf\n");
        return 2;
    }

    fprintf(stderr, "psfhelper: opening %s\n", argv[1]);
    fflush(stderr);
    if (sp_psf_open(argv[1], &handle) != 0) {
        fprintf(stderr, "%s\n", sp_psf_last_error());
        return 1;
    }
    fprintf(stderr, "psfhelper: open ok\n");
    fflush(stderr);

    for (;;) {
        int got = sp_psf_render(handle, FRAMES_PER_CHUNK, buffer);
        if (got < 0) {
            fprintf(stderr, "%s\n", sp_psf_last_error());
            sp_psf_close(handle);
            return 1;
        }
        if (got == 0) {
            quiet_chunks++;
            if (quiet_chunks > 16) break;
        } else {
            quiet_chunks = 0;
        }

        if (!started) {
            if (!is_silent(buffer, FRAMES_PER_CHUNK * 2)) {
                started = 1;
            } else if (init_silence_chunks < MAX_INIT_SILENCE_CHUNKS) {
                init_silence_chunks++;
                continue;
            } else {
                started = 1;
            }
        }

        if (fwrite(buffer, sizeof(int16_t) * 2, FRAMES_PER_CHUNK, stdout) != FRAMES_PER_CHUNK) {
            break;
        }
        fflush(stdout);
    }

    sp_psf_close(handle);
    return 0;
}
