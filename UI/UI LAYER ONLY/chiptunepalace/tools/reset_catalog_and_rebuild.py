import argparse

from chiptunepalace.db.orm_stubs import DatabaseManager
from chiptunepalace.services.console_canonicalizer import ConsoleCanonicalizer


def run(dry_run: bool = True):
    db = DatabaseManager()
    canon = ConsoleCanonicalizer(db_manager=db)

    all_tracks = db.get_all_tracks()
    total_tracks = len(all_tracks)
    distinct_raw_consoles = sorted({(t.get("console") or "Unknown Console") for t in all_tracks})

    mapping_preview = {}
    for raw in distinct_raw_consoles:
        normalized = canon.normalize_name(raw)
        slug = canon.slugify(normalized or "unknown console")
        mapping_preview[raw] = slug

    print("=== Catalog Reset + Canonical Rebuild ===")
    print(f"Tracks preserved: {total_tracks}")
    print(f"Distinct raw console labels: {len(distinct_raw_consoles)}")
    print("")
    print("Preview (raw -> canonical slug):")
    for raw, slug in mapping_preview.items():
        print(f"  - {raw} -> {slug}")

    if dry_run:
        print("")
        print("Dry run only. No changes were written.")
        return

    # 1) Reset catalog/discovery tables (keep tracks).
    db.reset_catalog_tables()

    # 2) Rebuild canonical registry + aliases from existing tracks.
    rebuilt = 0
    for raw in distinct_raw_consoles:
        canon.resolve(raw_name=raw, source="rebuild_from_tracks", confidence=1.0)
        rebuilt += 1

    print("")
    print("Catalog reset complete.")
    print(f"Canonical consoles rebuilt from tracks: {rebuilt}")


def main():
    parser = argparse.ArgumentParser(
        description="Reset catalog/discovery tables and rebuild canonical console registry from existing tracks."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply changes. If omitted, script runs in dry-run mode."
    )
    args = parser.parse_args()
    run(dry_run=not args.apply)


if __name__ == "__main__":
    main()
