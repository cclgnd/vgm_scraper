#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <string>

#ifdef _WIN32
#include <fcntl.h>
#include <io.h>
#endif

#include "types.h"

int sndSamplesPerSec = 44100;
int sndNumChannels = 2;
int sndBitsPerSample = 16;
int cpupercent = 0;

int defvolume = 1000;
int relvolume = 1000;
int TrackLength = 0;
int FadeLength = 0;
int IgnoreTrackLength = 0;
int DefaultLength = 150000;
int playforever = 0;
int fileoutput = 0;
int TrailingSilence = 1000;
int DetectSilence = 0;
int silencedetected = 0;
int silencelength = 5;
int CliOnly = 0;
int noinfo = 0;
int deflen = 120;
int deffade = 4;
int decode_pos_ms = 0;
int end_of_track = 0;

extern "C" {
int GSFRun(char *);
void GSFClose(void);
BOOL EmulationLoop(void);
extern unsigned short soundFinalWave[2304];
extern int soundBufferLen;
extern int emulating;
}

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

static const int MAX_INIT_SILENCE_BYTES = 882000;
static int init_silence_skipped = 0;
static bool started = false;

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

extern "C" void writeSound(void)
{
    if (soundBufferLen > 0)
    {
        write_pcm(soundFinalWave, soundBufferLen * 2);
    }
}

int main(int argc, char ** argv)
{
#ifdef _WIN32
    _setmode(_fileno(stdout), _O_BINARY);
#endif

    if (argc < 2)
    {
        std::fprintf(stderr, "usage: aogsf_helper <file.gsf|minigsf>\n");
        return 2;
    }

    const std::filesystem::path input_path = std::filesystem::absolute(argv[1]);
    std::filesystem::current_path(input_path.parent_path());

    if (!GSFRun(const_cast<char *>(input_path.string().c_str())))
    {
        std::fprintf(stderr, "aogsf: failed to load %s\n", input_path.string().c_str());
        return 3;
    }

    while (emulating && !g_stop)
    {
        EmulationLoop();
    }

    GSFClose();
    return 0;
}
