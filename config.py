"""
Configuration and constants for VGM Scraper.
"""

import os

# Database path (inside the vgm_scraper package directory)
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB_PATH = os.path.join(PROJECT_DIR, "vgm_scraper.db")
DEFAULT_DOWNLOAD_DIR = os.path.join(PROJECT_DIR, "vgm_downloads")

# Request settings
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
REQUEST_TIMEOUT = 30
REQUEST_RETRIES = 3
REQUEST_DELAY = 1.0  # seconds between requests to be polite

# Concurrent download settings
MAX_CONCURRENT_DOWNLOADS = 5
DOWNLOAD_CHUNK_SIZE = 8192

# ============================================
# SYNTH-ONLY FORMATS (no MP3/WAV/FLAC)
# Only chiptune/synthesized sound chip formats
# ============================================

SYNTH_FORMATS = {
    # VGM format family (sound chip logs)
    ".vgm", ".vgz",
    # Nintendo
    ".nsf", ".nsfe",   # NES
    ".spc", ".zst",    # SNES
    ".gbs",            # Game Boy
    ".kss", ".kssz",   # MSX
    ".hes", ".hesz",   # PC Engine
    ".gb", ".gbr",     # Game Boy ROM
    ".sap",            # Atari XL/XE
    ".ay",             # ZX Spectrum/Amstrad
    ".ym",             # Atari ST
    ".c00", ".m00",    # VIC-20
    ".sid",            # Commodore 64
    # Sega
    ".gym",            # Genesis/Mega Drive
    ".sms",            # Master System
    ".sg",             # SG-1000
    # Sony
    ".psf", ".psflib", ".minipsf",   # PlayStation
    ".psf2", ".minipsf2",            # PlayStation 2
    ".ssf", ".minissf", ".ssflib",   # Saturn
    ".dsf", ".minidsf", ".dsflib",   # Dreamcast
    # Nintendo portable
    ".usf", ".miniusf", ".usflib",   # N64
    ".gsf", ".minigsf", ".gsflib",   # GBA
    ".2sf", ".min2sf", ".2sflib",    # NDS
    # Other
    ".xsf", ".minixsf",              # PS2 (alternative)
    ".qsf", ".miniqsf", ".qsflib",   # Capcom QSound
    ".x68", ".x68z",                 # X68000
    ".mdx", ".mdxz",                 # FM Towns
    ".pce", ".pcez",                 # PC Engine (alt)
    ".sgb", ".sgbz",                 # Super Game Boy
    # Tracker modules (synthesized, not samples)
    ".mod", ".xm", ".s3m", ".it",
    ".mtm", ".669", ".far", ".ult",
    ".stm", ".med", ".okt", ".ptm",
    ".mpt", ".dmf", ".dsm", ".amf",
    ".ams", ".gdm", ".m15", ".wow",
    ".rad", ".imf", ".j2b", ".mms",
    ".mo3", ".mt2", ".mfx", ".pp10",
    ".ppm", ".psm", ".sfx", ".stx",
    ".symmod", ".tcb", ".umx",
}

# Archive formats that may contain synth files
ARCHIVE_EXTENSIONS = {".zip", ".7z", ".rar", ".tar.gz", ".tar.bz2"}

# Explicitly excluded formats (recorded/sampled audio, not synth)
EXCLUDED_FORMATS = {".mp3", ".wav", ".flac", ".ogg", ".aac", ".m4a", ".wma", ".aiff", ".aif", ".ape", ".opus", ".mka", ".ac3", ".dts"}

# All recognized audio formats (synth only)
AUDIO_EXTENSIONS = SYNTH_FORMATS

# ============================================
# CONSOLE WHITELIST & CANONICAL NAMES
# Each console has a canonical (Brand + Full Name) and aliases.
# Canonical names are always the longest, most descriptive form.
# ============================================

CONSOLE_CANONICAL = {
    # Nintendo
    "nes": {
        "canonical": "Nintendo Entertainment System",
        "aliases": ["nes", "famicom", "nintendo entertainment system", "family computer", "nintendo family computer"],
        "maker": "Nintendo",
    },
    "snes": {
        "canonical": "Nintendo Super Nintendo Entertainment System",
        "aliases": ["snes", "super nintendo", "super famicom", "super nintendo entertainment system", "nintendo super nintendo"],
        "maker": "Nintendo",
    },
    "gameboy": {
        "canonical": "Nintendo Game Boy",
        "aliases": ["game boy", "gameboy", "gb", "nintendo game boy"],
        "maker": "Nintendo",
    },
    "gbc": {
        "canonical": "Nintendo Game Boy Color",
        "aliases": ["game boy color", "gbc", "nintendo game boy color"],
        "maker": "Nintendo",
    },
    "gba": {
        "canonical": "Nintendo Game Boy Advance",
        "aliases": ["game boy advance", "gba", "nintendo game boy advance"],
        "maker": "Nintendo",
    },
    "n64": {
        "canonical": "Nintendo 64",
        "aliases": ["nintendo 64", "n64"],
        "maker": "Nintendo",
    },
    "nds": {
        "canonical": "Nintendo DS",
        "aliases": ["nintendo ds", "nds", "nintendo dual screen"],
        "maker": "Nintendo",
    },
    "3ds": {
        "canonical": "Nintendo 3DS",
        "aliases": ["nintendo 3ds", "3ds"],
        "maker": "Nintendo",
    },
    "gamecube": {
        "canonical": "Nintendo GameCube",
        "aliases": ["gamecube", "nintendo gamecube", "gc"],
        "maker": "Nintendo",
    },
    "wii": {
        "canonical": "Nintendo Wii",
        "aliases": ["wii", "nintendo wii"],
        "maker": "Nintendo",
    },

    # Sega
    "sms": {
        "canonical": "Sega Master System",
        "aliases": ["sega master system", "master system", "sms"],
        "maker": "Sega",
    },
    "genesis": {
        "canonical": "Sega Genesis",
        "aliases": ["sega genesis", "genesis", "mega drive", "sega mega drive", "megadrive", "sega mega drive / genesis"],
        "maker": "Sega",
    },
    "saturn": {
        "canonical": "Sega Saturn",
        "aliases": ["sega saturn", "saturn"],
        "maker": "Sega",
    },
    "dreamcast": {
        "canonical": "Sega Dreamcast",
        "aliases": ["sega dreamcast", "dreamcast"],
        "maker": "Sega",
    },
    "sg1000": {
        "canonical": "Sega SG-1000",
        "aliases": ["sg-1000", "sega sg-1000"],
        "maker": "Sega",
    },
    "gamegear": {
        "canonical": "Sega Game Gear",
        "aliases": ["game gear", "sega game gear", "gg"],
        "maker": "Sega",
    },

    # Sony
    "ps1": {
        "canonical": "Sony PlayStation",
        "aliases": ["playstation", "ps1", "psx", "sony playstation"],
        "maker": "Sony",
    },
    "ps2": {
        "canonical": "Sony PlayStation 2",
        "aliases": ["playstation 2", "ps2", "sony playstation 2"],
        "maker": "Sony",
    },
    "ps3": {
        "canonical": "Sony PlayStation 3",
        "aliases": ["playstation 3", "ps3", "sony playstation 3"],
        "maker": "Sony",
    },
    "psp": {
        "canonical": "Sony PlayStation Portable",
        "aliases": ["psp", "playstation portable", "sony psp"],
        "maker": "Sony",
    },

    # NEC
    "pce": {
        "canonical": "NEC PC Engine",
        "aliases": ["pc engine", "pce", "nec pc engine", "turbografx-16", "turbografx", "nec turbografx-16"],
        "maker": "NEC",
    },
    "pcfx": {
        "canonical": "NEC PC-FX",
        "aliases": ["pc-fx", "pcfx", "nec pc-fx"],
        "maker": "NEC",
    },
    "pc88": {
        "canonical": "NEC PC-8801",
        "aliases": ["pc-88", "pc88", "nec pc-8801", "pc-8801"],
        "maker": "NEC",
    },
    "pc98": {
        "canonical": "NEC PC-9801",
        "aliases": ["pc-98", "pc98", "nec pc-9801", "pc-9801"],
        "maker": "NEC",
    },

    # Commodore
    "c64": {
        "canonical": "Commodore 64",
        "aliases": ["commodore 64", "c64", "c=64"],
        "maker": "Commodore",
    },
    "vic20": {
        "canonical": "Commodore VIC-20",
        "aliases": ["vic-20", "vic20", "commodore vic-20"],
        "maker": "Commodore",
    },
    "amiga": {
        "canonical": "Commodore Amiga",
        "aliases": ["amiga", "commodore amiga"],
        "maker": "Commodore",
    },

    # Other
    "msx": {
        "canonical": "MSX",
        "aliases": ["msx", "ascii msx", "microsoft msx"],
        "maker": "Microsoft/ASCII",
    },
    "msx2": {
        "canonical": "MSX2",
        "aliases": ["msx2", "ascii msx2"],
        "maker": "Microsoft/ASCII",
    },
    "x68k": {
        "canonical": "Sharp X68000",
        "aliases": ["x68000", "x68k", "sharp x68000"],
        "maker": "Sharp",
    },
    "fmtowns": {
        "canonical": "Fujitsu FM Towns",
        "aliases": ["fm towns", "fmtowns", "fujitsu fm towns"],
        "maker": "Fujitsu",
    },
    "arcade": {
        "canonical": "Arcade",
        "aliases": ["arcade", "arcade machine"],
        "maker": "Various",
    },
    "zxspectrum": {
        "canonical": "Sinclair ZX Spectrum",
        "aliases": ["zx spectrum", "zxspectrum", "spectrum", "sinclair zx spectrum"],
        "maker": "Sinclair",
    },
    "atari2600": {
        "canonical": "Atari 2600",
        "aliases": ["atari 2600", "atari2600", "vcs"],
        "maker": "Atari",
    },
    "atari7800": {
        "canonical": "Atari 7800",
        "aliases": ["atari 7800", "atari7800"],
        "maker": "Atari",
    },
    "atarist": {
        "canonical": "Atari ST",
        "aliases": ["atari st", "atarist"],
        "maker": "Atari",
    },
    "atari8bit": {
        "canonical": "Atari 8-Bit",
        "aliases": ["atari 8-bit", "atari 8bit", "atari xl", "atari xe"],
        "maker": "Atari",
    },
    "atarilynx": {
        "canonical": "Atari Lynx",
        "aliases": ["atari lynx", "atarilynx", "lynx"],
        "maker": "Atari",
    },
    "wonderswan": {
        "canonical": "Bandai WonderSwan",
        "aliases": ["wonderswan", "bandai wonderswan", "ws"],
        "maker": "Bandai",
    },
    "neogeo": {
        "canonical": "SNK Neo Geo",
        "aliases": ["neo geo", "neogeo", "snk neo geo"],
        "maker": "SNK",
    },
    "ngp": {
        "canonical": "SNK Neo Geo Pocket",
        "aliases": ["neo geo pocket", "ngp", "snk neo geo pocket"],
        "maker": "SNK",
    },
    "xbox": {
        "canonical": "Microsoft Xbox",
        "aliases": ["xbox", "microsoft xbox"],
        "maker": "Microsoft",
    },
    "xbox360": {
        "canonical": "Microsoft Xbox 360",
        "aliases": ["xbox 360", "xbox360", "microsoft xbox 360"],
        "maker": "Microsoft",
    },
    "ibmpc": {
        "canonical": "IBM PC/AT",
        "aliases": ["ibm pc", "ibm pc/at", "pc", "dos", "ms-dos", "ibm pc/at"],
        "maker": "IBM",
    },
    "cdi": {
        "canonical": "Philips CD-i",
        "aliases": ["cd-i", "cdi", "philips cd-i"],
        "maker": "Philips",
    },
    "sharpx1": {
        "canonical": "Sharp X1",
        "aliases": ["x1", "sharp x1"],
        "maker": "Sharp",
    },
    "windows": {
        "canonical": "Microsoft Windows",
        "aliases": ["windows", "microsoft windows", "pc windows"],
        "maker": "Microsoft",
    },
    "n3ds": {
        "canonical": "Nintendo 3DS",
        "aliases": ["nintendo 3ds", "3ds"],
        "maker": "Nintendo",
    },
}


SUPPORTED_CONSOLES = tuple(CONSOLE_CANONICAL.keys())


def normalize_console_name(name: str) -> tuple[str, str]:
    """Normalize a console name to (canonical_name, slug).

    Kept for older call sites. The implementation imports lazily so config can
    remain the source of console definitions without creating an import cycle.
    """
    from vgm_scraper.acquisition.console_classifier import normalize_console_name as _normalize

    return _normalize(name)

# Tracker/module formats (for ModArchive-style sources)
TRACKER_FORMATS = {".mod", ".xm", ".s3m", ".it", ".mtm", ".669", ".far", ".ult", ".stm", ".med", ".okt", ".ptm", ".mpt", ".dmf", ".dsm", ".amf", ".ams", ".gdm", ".m15", ".wow", ".rad", ".imf", ".j2b", ".mms", ".mo3", ".mt2", ".mfx", ".pp10", ".ppm", ".psm", ".sfx", ".stx", ".symmod", ".tcb", ".umx"}

# API settings
API_HOST = "127.0.0.1"
API_PORT = 8765

# Discovery settings
DISCOVERY_MAX_DEPTH = 1
DISCOVERY_CANDIDATE_THRESHOLD = 0.3
DISCOVERY_ACTIVE_THRESHOLD = 0.5
DISCOVERY_REVISIT_INTERVAL = 86400  # 24 hours in seconds
