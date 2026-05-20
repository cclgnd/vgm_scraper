/* vgm_helper: streams VGM/VGZ/S98/DRO/GYM audio as raw 16-bit stereo PCM to stdout */
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cstdint>
#include <vector>
#include <filesystem>

#ifdef _WIN32
#include <fcntl.h>
#include <io.h>
#endif

#include "player/playerbase.hpp"
#include "player/vgmplayer.hpp"
#include "player/s98player.hpp"
#include "player/droplayer.hpp"
#include "player/gymplayer.hpp"
#include "player/playera.hpp"
#include "utils/DataLoader.h"
#include "utils/FileLoader.h"
#include "emu/EmuStructs.h"

#define BUFFER_LEN 1024
#define SAMPLE_RATE 44100
#define BIT_DEPTH 16
#define DEFAULT_LOOPS 2
#define FADE_SECONDS 8.0

static void pack_uint16le(uint8_t *d, uint16_t n) {
    d[0] = (uint8_t)(n);
    d[1] = (uint8_t)(n >> 8);
}

static void pack_uint32le(uint8_t *d, uint32_t n) {
    d[0] = (uint8_t)(n);
    d[1] = (uint8_t)(n >> 8);
    d[2] = (uint8_t)(n >> 16);
    d[3] = (uint8_t)(n >> 24);
}

static int write_wav_header(FILE *f, unsigned int totalFrames) {
    unsigned int dataSize = totalFrames * (BIT_DEPTH / 8) * 2;
    uint8_t tmp[4];
    static const char guid_trailer[] = "\x00\x00\x00\x00\x10\x00\x80\x00\x00\xAA\x00\x38\x9B\x71";

    if (fwrite("RIFF", 1, 4, f) != 4) return 0;
    pack_uint32le(tmp, 4 + (8 + dataSize) + (8 + 40));
    if (fwrite(tmp, 1, 4, f) != 4) return 0;
    if (fwrite("WAVE", 1, 4, f) != 4) return 0;
    if (fwrite("fmt ", 1, 4, f) != 4) return 0;
    pack_uint32le(tmp, 40);
    if (fwrite(tmp, 1, 4, f) != 4) return 0;
    pack_uint16le(tmp, 0xFFFE);
    if (fwrite(tmp, 1, 2, f) != 2) return 0;
    pack_uint16le(tmp, 2);
    if (fwrite(tmp, 1, 2, f) != 2) return 0;
    pack_uint32le(tmp, SAMPLE_RATE);
    if (fwrite(tmp, 1, 4, f) != 4) return 0;
    pack_uint32le(tmp, SAMPLE_RATE * 2 * (BIT_DEPTH / 8));
    if (fwrite(tmp, 1, 4, f) != 4) return 0;
    pack_uint16le(tmp, 2 * (BIT_DEPTH / 8));
    if (fwrite(tmp, 1, 2, f) != 2) return 0;
    pack_uint16le(tmp, BIT_DEPTH);
    if (fwrite(tmp, 1, 2, f) != 2) return 0;
    pack_uint16le(tmp, 22);
    if (fwrite(tmp, 1, 2, f) != 2) return 0;
    pack_uint16le(tmp, BIT_DEPTH);
    if (fwrite(tmp, 1, 2, f) != 2) return 0;
    pack_uint32le(tmp, 3);
    if (fwrite(tmp, 1, 4, f) != 4) return 0;
    pack_uint16le(tmp, 1);
    if (fwrite(tmp, 1, 2, f) != 2) return 0;
    if (fwrite(guid_trailer, 1, 14, f) != 14) return 0;
    if (fwrite("data", 1, 4, f) != 4) return 0;
    pack_uint32le(tmp, dataSize);
    if (fwrite(tmp, 1, 4, f) != 4) return 0;
    return 1;
}



int main(int argc, char **argv) {
#ifdef _WIN32
    _setmode(_fileno(stdout), _O_BINARY);
#endif

    if (argc < 2) {
        fprintf(stderr, "usage: vgm_helper.exe <file.vgm|file.vgz|file.s98|file.dro|file.gym> [-wav]\n");
        return 2;
    }

    const char *input_path = argv[1];
    bool wav_mode = (argc >= 3 && strcmp(argv[2], "-wav") == 0);

    PlayerA player;
    player.RegisterPlayerEngine(new VGMPlayer);
    player.RegisterPlayerEngine(new S98Player);
    player.RegisterPlayerEngine(new DROPlayer);
    player.RegisterPlayerEngine(new GYMPlayer);

    if (player.SetOutputSettings(SAMPLE_RATE, 2, BIT_DEPTH, BUFFER_LEN)) {
        fprintf(stderr, "vgm_helper: unsupported sample rate / bps\n");
        return 1;
    }

    {
        PlayerA::Config pCfg = player.GetConfiguration();
        pCfg.masterVol = 0x10000;
        pCfg.loopCount = DEFAULT_LOOPS;
        pCfg.fadeSmpls = (UINT32)(SAMPLE_RATE * FADE_SECONDS);
        pCfg.endSilenceSmpls = 0;
        pCfg.pbSpeed = 1.0;
        player.SetConfiguration(pCfg);
    }

    DATA_LOADER *loader = FileLoader_Init(input_path);
    if (loader == NULL) {
        fprintf(stderr, "vgm_helper: failed to create FileLoader for %s\n", input_path);
        return 1;
    }

    DataLoader_SetPreloadBytes(loader, 0x100);
    if (DataLoader_Load(loader)) {
        fprintf(stderr, "vgm_helper: failed to load %s\n", input_path);
        DataLoader_Deinit(loader);
        return 1;
    }

    if (player.LoadFile(loader)) {
        fprintf(stderr, "vgm_helper: failed to parse %s\n", input_path);
        DataLoader_Deinit(loader);
        return 1;
    }

    PlayerBase *plr = player.GetPlayer();
    fprintf(stderr, "vgm_helper: loaded %s (%s)\n", input_path, plr->GetPlayerName());

    {
        PLR_SONG_INFO songInfo;
        plr->GetSongInfo(songInfo);
        std::vector<PLR_DEV_INFO> devInfList;
        plr->GetSongDeviceInfo(devInfList);
        fprintf(stderr, "vgm_helper: devices: %u\n", (unsigned)devInfList.size());
        for (size_t i = 0; i < devInfList.size(); i++) {
            const PLR_DEV_INFO &di = devInfList[i];
            fprintf(stderr, "  dev[%zu]: type=0x%02X core=0x%08X clk=%u vol=0x%X parent=%u\n",
                i, (unsigned)di.type, (unsigned)di.core,
                (unsigned)(di.devCfg ? di.devCfg->clock : 0),
                (unsigned)di.volume, (unsigned)di.parentIdx);
        }
    }

    if (plr->GetPlayerType() == FCC_VGM) {
        VGMPlayer *vgmplay = dynamic_cast<VGMPlayer *>(plr);
        player.SetLoopCount(vgmplay->GetModifiedLoopCount(DEFAULT_LOOPS));
    }

    player.Start();

    unsigned int totalFrames = plr->Tick2Sample(plr->GetTotalPlayTicks(DEFAULT_LOOPS));
    if (plr->GetLoopTicks() > 0) {
        totalFrames += player.GetFadeSamples();
    }

    fprintf(stderr, "vgm_helper: %u frames (%.2fs)\n", totalFrames, plr->Sample2Second(totalFrames));

    if (wav_mode) {
        write_wav_header(stdout, totalFrames);
    }

    uint8_t *packed = (uint8_t *)malloc(sizeof(int32_t) * 2 * BUFFER_LEN);
    if (!packed) {
        fprintf(stderr, "vgm_helper: out of memory\n");
        return 1;
    }

    unsigned int remaining = totalFrames;
    while (remaining > 0) {
        unsigned int cur = (BUFFER_LEN < remaining) ? BUFFER_LEN : remaining;
        memset(packed, 0, sizeof(int32_t) * 2 * BUFFER_LEN);
        player.Render(cur * ((BIT_DEPTH / 8) * 2), packed);
        if (fwrite(packed, 4, cur, stdout) != cur) {
            break;
        }
        fflush(stdout);
        remaining -= cur;
    }

    free(packed);
    player.Stop();
    player.UnloadFile();
    player.UnregisterAllPlayers();
    DataLoader_Deinit(loader);

    return 0;
}
