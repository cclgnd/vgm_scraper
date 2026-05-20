"""
Source registry for acquisition domain.
"""

from vgm_scraper.acquisition.sources.vgmrips import VGMRipsSource
from vgm_scraper.acquisition.sources.modarchive import ModArchiveSource
from vgm_scraper.acquisition.sources.zophar import ZopharSource
from vgm_scraper.acquisition.sources.project2612 import Project2612Source
from vgm_scraper.acquisition.sources.hcs64 import Hcs64Source
from vgm_scraper.acquisition.sources.snesmusic import SNESmusicSource
from vgm_scraper.acquisition.sources.opengameart import OpenGameArtSource
from vgm_scraper.acquisition.sources.vgmdb import VGMdbSource
from vgm_scraper.acquisition.sources.archive import ArchiveOrgSource
from vgm_scraper.acquisition.sources.dynamic import DynamicSource

SOURCE_CLASSES = {
    "vgmrips": VGMRipsSource,
    "modarchive": ModArchiveSource,
    "zophar": ZopharSource,
    "project2612": Project2612Source,
    "hcs64": Hcs64Source,
    "snesmusic": SNESmusicSource,
    "opengameart": OpenGameArtSource,
    "vgmdb": VGMdbSource,
    "archive": ArchiveOrgSource,
}

SOURCE_NAMES = list(SOURCE_CLASSES.keys())


def get_source(name: str, session, db):
    cls = SOURCE_CLASSES.get(name)
    if not cls:
        raise ValueError(f"Unknown source: {name}. Available: {SOURCE_NAMES}")
    return cls(session, db)


def get_all_static_sources(session, db):
    """Get all hardcoded source adapters."""
    return [cls(session, db) for cls in SOURCE_CLASSES.values()]


def get_dynamic_sources(session, db):
    """Get all discovered active sites as dynamic source adapters."""
    sites = db.get_active_sites()
    sources = []
    for site in sites:
        try:
            src = DynamicSource(session, db, site)
            sources.append(src)
        except Exception:
            pass
    return sources


def get_all_sources(session, db):
    """Get all sources: static + discovered dynamic."""
    return get_all_static_sources(session, db) + get_dynamic_sources(session, db)
