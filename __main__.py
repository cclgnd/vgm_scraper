"""
VGM Scraper CLI - Standalone command-line interface.

Usage:
    python -m vgm_scraper list-sources
    python -m vgm_scraper crawl --source vgmrips
    python -m vgm_scraper crawl-url --url https://example.com/music
    python -m vgm_scraper crawl --all-sources
    python -m vgm_scraper scan --dir /path/to/music
    python -m vgm_scraper discover
    python -m vgm_scraper discover --continuous
    python -m vgm_scraper list-sites
    python -m vgm_scraper retrieve --track-id 123
    python -m vgm_scraper process-jobs
    python -m vgm_scraper search --query "Sonic"
    python -m vgm_scraper tree
    python -m vgm_scraper stats
    python -m vgm_scraper api-start
"""

import argparse
import json
import logging
import os
import sys
import time

from vgm_scraper.config import DEFAULT_DOWNLOAD_DIR, DEFAULT_DB_PATH, API_HOST, API_PORT
from vgm_scraper.core import ScraperSession
from vgm_scraper.db.manager import DatabaseManager
from vgm_scraper.catalog.library import LibraryManager
from vgm_scraper.acquisition.crawler import WebCrawler
from vgm_scraper.acquisition.local_scanner import LocalScanner
from vgm_scraper.acquisition.retrieval import RetrievalManager
from vgm_scraper.acquisition.discovery import DiscoveryEngine
from vgm_scraper.acquisition.sources import get_source, get_all_sources, get_dynamic_sources
from vgm_scraper.acquisition.sources.dynamic import DynamicSource
from vgm_scraper.api.server import APIServer


def setup_logging(verbose: bool = False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def init_components(args):
    """Initialize all components."""
    db = DatabaseManager(args.db)
    session = ScraperSession()
    library = LibraryManager(db)
    retrieval = RetrievalManager(db, args.download_dir)
    return db, session, library, retrieval


def cmd_list_sources(args):
    db, session, library, retrieval = init_components(args)
    sources = get_all_sources(session, db)
    print(f"\nAvailable sources ({len(sources)}):")
    print("-" * 50)
    for src in sources:
        print(f"  {src.name:15s}  {src.base_url}")
    print()


def cmd_crawl(args):
    db, session, library, retrieval = init_components(args)
    crawler = WebCrawler(db, session)

    if args.all_sources:
        sources = get_all_sources(session, db)
    else:
        sources = [get_source(args.source, session, db)]

    total = 0
    for src in sources:
        print(f"\nCrawling {src.name}...")
        count = crawler.crawl_source(src, max_depth=args.max_depth)
        print(f"  Discovered {count} resources")
        total += count

    print(f"\nTotal resources discovered: {total}\n")


def cmd_crawl_url(args):
    """Crawl any URL with the generic site-neutral scraper."""
    db, session, library, retrieval = init_components(args)
    crawler = WebCrawler(db, session)
    site_id = db.add_discovered_site(
        url=args.url,
        name=args.name or args.url,
        discovered_from="manual",
        confidence=1.0,
        status="active",
    )
    db.update_site_status(
        site_id,
        status="active",
        profile_json=json.dumps({
            "base_url": args.url,
            "version": 2,
            "scraper": "generic",
            "max_pages": args.max_pages,
        }),
    )
    site = db.get_site_by_url(args.url)
    source = DynamicSource(session, db, site)
    print(f"\nCrawling generic URL {args.url}...")
    count = crawler.crawl_source(source, max_depth=args.max_depth)
    print(f"  Discovered {count} online resources")
    print()


def cmd_scan(args):
    db, session, library, retrieval = init_components(args)
    scanner = LocalScanner(db)

    print(f"\nScanning {args.dir}...")
    results = scanner.scan_directory(args.dir, source_name="local")

    for r in results:
        print(f"  {r['path']} ({len(r['files'])} files, confidence: {r['confidence']:.2f})")
        for ev in r['evidence']:
            print(f"    - {ev}")

    print(f"\nTotal folders scanned: {len(results)}\n")


def cmd_retrieve(args):
    db, session, library, retrieval = init_components(args)

    result = retrieval.request_track(args.track_id)
    print(f"\nTrack {args.track_id} request:")
    print(f"  Status: {result['status']}")
    if result.get("local_path"):
        print(f"  Local path: {result['local_path']}")
    if result.get("job_id"):
        print(f"  Job ID: {result['job_id']}")
    if result.get("message"):
        print(f"  Message: {result['message']}")
    print()


def cmd_process_jobs(args):
    db, session, library, retrieval = init_components(args)

    print("\nProcessing pending retrieval jobs...")
    results = retrieval.process_pending_jobs()

    for r in results:
        print(f"  Job {r['job_id']}: {r['status']}")
        if r.get("local_path"):
            print(f"    Path: {r['local_path']}")
        if r.get("error"):
            print(f"    Error: {r['error']}")

    print(f"\nProcessed {len(results)} jobs\n")


def cmd_search(args):
    db, session, library, retrieval = init_components(args)

    results = library.search(args.query)
    print(f"\nSearch results for '{args.query}' ({len(results)} found):")
    for r in results:
        data = r["data"]
        print(f"  [{r['type']}] {data.get('display_name') or data.get('title', 'Unknown')}")
    print()


def cmd_tree(args):
    db, session, library, retrieval = init_components(args)

    tree = library.get_full_tree()
    for console in tree:
        print(f"\n{console['display_name']}")
        for game in console.get("games", []):
            print(f"  {game['title']}")
            for coll in game.get("collections", []):
                print(f"    [{coll['title']}]")
                for track in coll.get("tracks", []):
                    avail = "[+]" if track.get("is_locally_available") else "[ ]"
                    print(f"      {avail} {track['title']}")
    print()


def cmd_stats(args):
    db, session, library, retrieval = init_components(args)
    stats = db.get_stats()

    print(f"\nVGM Scraper Statistics")
    print(f"{'='*40}")
    print(f"  Catalog Domain:")
    print(f"    Consoles:           {stats['consoles']}")
    print(f"    Games:              {stats['games']}")
    print(f"    Collections:        {stats['collections']}")
    print(f"    Tracks:             {stats['tracks']}")
    print(f"  Acquisition Domain:")
    print(f"    Sources:            {stats['sources']}")
    print(f"    Resource nodes:     {stats['resource_nodes']}")
    print(f"  Discovery:")
    print(f"    Discovered sites:   {stats['discovered_sites']}")
    print(f"    Active sites:       {stats['active_sites']}")
    print(f"    Candidates:         {stats['candidate_sites']}")
    print(f"  Retrieval:")
    print(f"    Pending jobs:       {stats['retrieval_jobs_pending']}")
    print(f"    Completed jobs:     {stats['retrieval_jobs_completed']}")
    print(f"  Local files:          {stats['local_files']}")
    print(f"  Audition events:      {stats['audition_events']}")
    print(f"{'='*40}\n")


def cmd_reset_db(args):
    if not args.yes:
        print("Refusing to reset database without --yes.")
        print("This deletes database records only; downloaded files are not removed.")
        return

    db, session, library, retrieval = init_components(args)
    stats = db.reset_database()
    print("\nDatabase reset complete.")
    print("Downloaded files on disk were not deleted.")
    print(f"Catalog now has {stats['consoles']} consoles, {stats['games']} games, {stats['tracks']} tracks.")
    print()


def cmd_audition_queue(args):
    db, session, library, retrieval = init_components(args)
    items = db.get_audition_queue(status=args.status, limit=args.limit)

    print(f"\nAudition queue: {args.status} ({len(items)} shown)")
    print(f"{'='*80}")
    for item in items:
        title = item.get("track_title") or item.get("game_title") or f"resource:{item.get('resource_id')}"
        console = item.get("console_name") or "Unknown Console"
        source = item.get("source_name") or "unknown"
        print(f"  [{item['event_id']}] {console} / {title}")
        print(f"      source={source} game_id={item.get('game_id')} track_id={item.get('track_id')}")
        if item.get("local_path"):
            print(f"      local={item['local_path']}")
    print()


def cmd_audition_stats(args):
    db, session, library, retrieval = init_components(args)
    print("\nAudition Status Counts")
    print("=" * 40)
    for row in db.get_audition_status_counts():
        print(f"  {row['status']:18s} {row['count']}")

    print("\nAudition By Source")
    print("=" * 40)
    for row in db.get_audition_source_stats():
        print(f"  {row['source']:18s} {row['status']:18s} {row['count']}")
    print()


def cmd_discover(args):
    db, session, library, retrieval = init_components(args)
    engine = DiscoveryEngine(db, session)

    if args.continuous:
        print("Starting continuous discovery (Ctrl+C to stop)...")
        engine.start_continuous(interval=args.interval)
        try:
            while True:
                time.sleep(5)
                sites = db.get_discovered_sites()
                active = [s for s in sites if s["status"] == "active"]
                candidates = [s for s in sites if s["status"] == "candidate"]
                print(f"\r  Sites: {len(active)} active, {len(candidates)} candidates", end="", flush=True)
        except KeyboardInterrupt:
            engine.stop_continuous()
            print("\nDiscovery stopped.")
    else:
        print("Running discovery pass...")
        candidates = engine.discover_once(max_sites=args.max_sites)
        print(f"\nFound {len(candidates)} candidate sites:")
        for c in candidates:
            status = "ACTIVE" if c.confidence >= 0.7 else "candidate"
            print(f"  [{status}] {c.name or c.url} (score: {c.confidence:.2f})")
            if c.evidence:
                for ev in c.evidence[:3]:
                    print(f"    - {ev}")
        print()


def cmd_list_sites(args):
    db, session, library, retrieval = init_components(args)
    sites = db.get_discovered_sites()

    if not sites:
        print("No discovered sites yet. Run 'discover' to start.")
        return

    print(f"\nDiscovered Sites ({len(sites)}):")
    print(f"{'='*80}")
    for s in sites:
        status = s["status"].upper()
        profile = "yes" if s.get("profile_json") else "no"
        print(f"  [{status:10s}] {s['name'] or s['url']}")
        print(f"               URL: {s['url']}")
        print(f"               Confidence: {s['confidence']:.2f} | Profile: {profile} | Items: {s['items_found']}")
        if s.get("discovered_from"):
            print(f"               Found from: {s['discovered_from']}")
        print()


def cmd_api_start(args):
    db, session, library, retrieval = init_components(args)

    # Start background discovery if requested
    if args.discover:
        from vgm_scraper.acquisition.discovery import DiscoveryEngine
        engine = DiscoveryEngine(db, session)
        engine.start_continuous(interval=3600)
        print("Background discovery started.")

    server = APIServer(db, library, retrieval, host=args.host, port=args.port)
    server.start()
    print(f"API server running at http://{args.host}:{args.port}")
    print("Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        server.stop()
        print("\nAPI server stopped.")


def cmd_gui(args):
    """Launch the GUI."""
    from vgm_scraper.gui import main as gui_main
    gui_main()


def main():
    parser = argparse.ArgumentParser(
        prog="vgm_scraper",
        description="VGM Scraper - Provenance-aware VGM catalog and on-demand retrieval system",
    )
    parser.add_argument("--db", default=DEFAULT_DB_PATH, help="SQLite database path")
    parser.add_argument("--download-dir", default=DEFAULT_DOWNLOAD_DIR, help="Download directory")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")

    sub = parser.add_subparsers(dest="command", help="Available commands")

    sub.add_parser("list-sources", help="List all available sources")

    p = sub.add_parser("crawl", help="Crawl web sources")
    p.add_argument("--source", help="Source to crawl")
    p.add_argument("--all-sources", action="store_true", help="Crawl all sources")
    p.add_argument("--max-depth", type=int, default=3, help="Max crawl depth")

    p = sub.add_parser("crawl-url", help="Crawl any URL with the generic scraper")
    p.add_argument("--url", required=True, help="URL to crawl")
    p.add_argument("--name", default="", help="Optional source name")
    p.add_argument("--max-depth", type=int, default=2, help="Max link depth")
    p.add_argument("--max-pages", type=int, default=100, help="Max pages to inspect")

    p = sub.add_parser("scan", help="Scan local directory")
    p.add_argument("--dir", required=True, help="Directory to scan")

    p = sub.add_parser("retrieve", help="Request track retrieval")
    p.add_argument("--track-id", type=int, required=True, help="Track ID")

    sub.add_parser("process-jobs", help="Process pending retrieval jobs")

    p = sub.add_parser("search", help="Search catalog")
    p.add_argument("--query", required=True, help="Search query")

    sub.add_parser("tree", help="Show catalog tree")

    p = sub.add_parser("discover", help="Discover new VGM repositories")
    p.add_argument("--continuous", action="store_true", help="Run continuous background discovery")
    p.add_argument("--interval", type=int, default=3600, help="Seconds between discovery passes")
    p.add_argument("--max-sites", type=int, default=20, help="Max sites to discover per pass")

    sub.add_parser("list-sites", help="List discovered sites")

    sub.add_parser("stats", help="Show statistics")

    p = sub.add_parser("reset-db", help="Reset all database records but keep downloaded files")
    p.add_argument("--yes", action="store_true", help="Confirm destructive database reset")

    p = sub.add_parser("audition-queue", help="Show files/games waiting for audition")
    p.add_argument("--status", default="needs_audition", help="Audition status to show")
    p.add_argument("--limit", type=int, default=50, help="Max rows to show")

    sub.add_parser("audition-stats", help="Show audition status/source summary")

    sub.add_parser("gui", help="Launch the GUI")

    p = sub.add_parser("api-start", help="Start API server")
    p.add_argument("--host", default="127.0.0.1", help="API host")
    p.add_argument("--port", type=int, default=8765, help="API port")
    p.add_argument("--discover", action="store_true", help="Start background discovery with API server")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    setup_logging(args.verbose)

    commands = {
        "list-sources": cmd_list_sources,
        "crawl": cmd_crawl,
        "crawl-url": cmd_crawl_url,
        "scan": cmd_scan,
        "retrieve": cmd_retrieve,
        "process-jobs": cmd_process_jobs,
        "search": cmd_search,
        "tree": cmd_tree,
        "discover": cmd_discover,
        "list-sites": cmd_list_sites,
        "stats": cmd_stats,
        "reset-db": cmd_reset_db,
        "audition-queue": cmd_audition_queue,
        "audition-stats": cmd_audition_stats,
        "gui": cmd_gui,
        "api-start": cmd_api_start,
    }

    commands[args.command](args)


if __name__ == "__main__":
    main()
