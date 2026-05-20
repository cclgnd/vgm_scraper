#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "psflib.h"
#include "psx.h"

#define PSFCORE_SAMPLE_RATE 44100
#define PSFCORE_CYCLES_PER_SAMPLE 768

typedef struct PsfCore {
    void *state;
    char base_dir[2048];
    char last_error[1024];
    int tell_ms;
} PsfCore;

static char g_last_error[1024];
static int g_initialized = 0;

static void set_error(PsfCore *core, const char *message) {
    if (!message) message = "unknown PSF error";
    if (core) {
        snprintf(core->last_error, sizeof(core->last_error), "%s", message);
    }
    snprintf(g_last_error, sizeof(g_last_error), "%s", message);
}

static void dirname_from_path(const char *path, char *out, size_t out_size) {
    const char *slash1 = strrchr(path, '/');
    const char *slash2 = strrchr(path, '\\');
    const char *slash = slash1 > slash2 ? slash1 : slash2;
    size_t len = slash ? (size_t)(slash - path) : 0;
    if (len >= out_size) len = out_size - 1;
    if (len > 0) memcpy(out, path, len);
    out[len] = '\0';
}

static void *cb_fopen(void *context, const char *path) {
    PsfCore *core = (PsfCore *)context;
    char resolved[4096];
    FILE *file;

    if (!path) return NULL;
    if ((strlen(path) > 2 && path[1] == ':') || path[0] == '/' || path[0] == '\\') {
        snprintf(resolved, sizeof(resolved), "%s", path);
    } else if (core && core->base_dir[0]) {
        snprintf(resolved, sizeof(resolved), "%s\\%s", core->base_dir, path);
    } else {
        snprintf(resolved, sizeof(resolved), "%s", path);
    }

    file = fopen(resolved, "rb");
    if (!file) set_error(core, "could not open PSF or companion library");
    return file;
}

static size_t cb_fread(void *buffer, size_t size, size_t count, void *handle) {
    return fread(buffer, size, count, (FILE *)handle);
}

static int cb_fseek(void *handle, int64_t offset, int whence) {
    return _fseeki64((FILE *)handle, offset, whence);
}

static int cb_fclose(void *handle) {
    return fclose((FILE *)handle);
}

static long cb_ftell(void *handle) {
    return (long)_ftelli64((FILE *)handle);
}

static int load_callback(void *context, const uint8_t *exe, size_t exe_size,
                         const uint8_t *reserved, size_t reserved_size) {
    PsfCore *core = (PsfCore *)context;
    (void)reserved;
    (void)reserved_size;
    if (!core || !core->state) {
        set_error(core, "PSF core state is not initialized");
        return -1;
    }
    if (!exe || exe_size == 0) {
        return 0;
    }
    if (psx_upload_psxexe(core->state, (void *)exe, (uint32)exe_size) != 0) {
        set_error(core, "psx_upload_psxexe failed");
        return -1;
    }
    return 0;
}

static void status_callback(void *context, const char *message) {
    set_error((PsfCore *)context, message);
}

__declspec(dllexport) int sp_psf_sample_rate(void) {
    return PSFCORE_SAMPLE_RATE;
}

__declspec(dllexport) const char *sp_psf_last_error(void) {
    return g_last_error;
}

__declspec(dllexport) int sp_psf_open(const char *path, void **out_handle) {
    PsfCore *core;
    uint32 state_size;
    psf_file_callbacks callbacks;
    int version;

    if (!out_handle) return -1;
    *out_handle = NULL;
    g_last_error[0] = '\0';
    fprintf(stderr, "psfcore: init\n");
    fflush(stderr);

    if (!g_initialized) {
        if (psx_init() != 0) {
            set_error(NULL, "psx_init failed");
            return -1;
        }
        g_initialized = 1;
    }

    core = (PsfCore *)calloc(1, sizeof(PsfCore));
    if (!core) {
        set_error(NULL, "out of memory allocating PSF handle");
        return -1;
    }

    state_size = psx_get_state_size(1);
    core->state = calloc(1, state_size);
    if (!core->state) {
        set_error(core, "out of memory allocating PSX state");
        free(core);
        return -1;
    }

    psx_clear_state(core->state, 1);
    dirname_from_path(path, core->base_dir, sizeof(core->base_dir));
    fprintf(stderr, "psfcore: loading psf\n");
    fflush(stderr);

    memset(&callbacks, 0, sizeof(callbacks));
    callbacks.path_separators = "/\\";
    callbacks.context = core;
    callbacks.fopen = cb_fopen;
    callbacks.fread = cb_fread;
    callbacks.fseek = cb_fseek;
    callbacks.fclose = cb_fclose;
    callbacks.ftell = cb_ftell;

    version = psf_load(path, &callbacks, 1, load_callback, core, NULL, NULL, 0, status_callback, core);
    fprintf(stderr, "psfcore: psf_load returned %d\n", version);
    fflush(stderr);
    if (version != 1) {
        if (!g_last_error[0]) set_error(core, "not a PSF1 file or PSF load failed");
        free(core->state);
        free(core);
        return -1;
    }

    *out_handle = core;
    return 0;
}

__declspec(dllexport) int sp_psf_render(void *handle, int frames, int16_t *stereo_out) {
    PsfCore *core = (PsfCore *)handle;
    uint32 samples;
    int produced = 0;

    if (!core || !core->state || !stereo_out || frames <= 0) return -1;

    while (produced < frames) {
        samples = (uint32)(frames - produced);
        int r = psx_execute(core->state, 0x70000000, stereo_out + (produced * 2), &samples, 0);
        if (r < -1) {
            set_error(core, "psx_execute failed");
            return -1;
        }
        if (samples == 0) break;
        produced += (int)samples;
        if (r == -1) break;
    }

    if (produced < frames) {
        memset(stereo_out + (produced * 2), 0, (size_t)(frames - produced) * 2 * sizeof(int16_t));
    }
    core->tell_ms += (produced * 1000) / PSFCORE_SAMPLE_RATE;
    return produced;
}

__declspec(dllexport) int sp_psf_tell_ms(void *handle) {
    PsfCore *core = (PsfCore *)handle;
    return core ? core->tell_ms : 0;
}

__declspec(dllexport) void sp_psf_close(void *handle) {
    PsfCore *core = (PsfCore *)handle;
    if (!core) return;
    free(core->state);
    free(core);
}
