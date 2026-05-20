from __future__ import annotations

import hashlib
import html.parser
import json
import shutil
import subprocess
import tempfile
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "chiptunes"
MANIFEST = OUTPUT / "MANIFEST.json"
TARGET_COUNT = 10
USER_AGENT = "SIMPLEPLAYER future fixture downloader/0.1"


@dataclass(frozen=True)
class ArchiveSource:
    name: str
    priority_group: str
    base_url: str
    wanted_extensions: tuple[str, ...]
    archive_limit: int = 16


SOURCES = [
    ArchiveSource("PSF", "32-bit consoles", "https://psf.joshw.info/", (".psf", ".minipsf")),
    ArchiveSource("PSF2", "32-bit consoles", "https://psf2.joshw.info/", (".psf2", ".minipsf2")),
    ArchiveSource("GSF", "32-bit consoles", "https://gsf.joshw.info/", (".gsf", ".minigsf")),
    ArchiveSource("2SF", "32-bit handhelds", "https://2sf.joshw.info/", (".2sf", ".mini2sf")),
    ArchiveSource("USF", "64-bit consoles", "https://usf.joshw.info/", (".usf", ".miniusf", ".usfmini")),
    ArchiveSource("SSF", "arcade and similar", "https://ssf.joshw.info/", (".ssf", ".minissf")),
    ArchiveSource("DSF", "arcade and similar", "https://dsf.joshw.info/", (".dsf", ".minidsf")),
    ArchiveSource("QSF", "arcade and similar", "https://ftp.modland.com/pub/modules/Capcom%20Q-Sound%20Format/", (".qsf", ".miniqsf")),
]


class LinkParser(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        href = dict(attrs).get("href")
        if href:
            self.links.append(href)


def fetch(url: str) -> bytes:
    with urlopen(Request(url, headers={"User-Agent": USER_AGENT}), timeout=90) as response:
        return response.read()


def fetch_text(url: str) -> str:
    return fetch(url).decode("utf-8", errors="replace")


def same_tree(url: str, base: str) -> bool:
    parsed = urlparse(url)
    base_parsed = urlparse(base)
    return parsed.netloc == base_parsed.netloc and parsed.path.startswith(base_parsed.path)


def list_archive_urls(source: ArchiveSource) -> list[str]:
    queue: deque[str] = deque([source.base_url])
    seen_pages: set[str] = set()
    urls: list[str] = []

    while queue and len(urls) < source.archive_limit and len(seen_pages) < 80:
        page = queue.popleft()
        if page in seen_pages:
            continue
        seen_pages.add(page)

        parser = LinkParser()
        parser.feed(fetch_text(page))
        for href in parser.links:
            if href.startswith("?") or href.startswith("../") or href == "/":
                continue
            absolute = urljoin(page, href)
            if not same_tree(absolute, source.base_url):
                continue
            suffix = Path(unquote(urlparse(absolute).path)).suffix.lower()
            if suffix in {".7z", ".zip", ".rar"}:
                urls.append(absolute)
                if len(urls) >= source.archive_limit:
                    break
            elif href.endswith("/"):
                queue.append(absolute)
    return urls


def extract_archive(archive_path: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    subprocess.run(["7z", "x", str(archive_path), f"-o{destination}", "-y"], check=True, stdout=subprocess.DEVNULL)


def extension_folder(extension: str) -> Path:
    return OUTPUT / extension.lstrip(".")


def copy_candidate(source: ArchiveSource, candidate: Path, source_url: str, index: int) -> dict[str, object]:
    extension = candidate.suffix.lower()
    folder = extension_folder(extension)
    folder.mkdir(parents=True, exist_ok=True)
    safe_name = candidate.name.replace(":", "_")
    target = folder / f"{index:02d}_{safe_name}"
    data = candidate.read_bytes()
    target.write_bytes(data)
    return {
        "extension": extension,
        "priority_group": source.priority_group,
        "backend": source.name,
        "repository": "JoshW" if "joshw.info" in source.base_url else "Modland",
        "source_url": source_url,
        "path": str(target.relative_to(ROOT)).replace("\\", "/"),
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def collect_source(source: ArchiveSource) -> list[dict[str, object]]:
    if not shutil.which("7z"):
        raise RuntimeError("7z is required to extract future fixture archives.")

    print(f"collecting {source.name} from {source.base_url}")
    counts: defaultdict[str, int] = defaultdict(int)
    records: list[dict[str, object]] = []
    archive_urls = list_archive_urls(source)
    scratch = OUTPUT / "_downloads" / source.name.lower()
    scratch.mkdir(parents=True, exist_ok=True)

    for archive_number, archive_url in enumerate(archive_urls, start=1):
        if all(counts[extension] >= TARGET_COUNT for extension in source.wanted_extensions):
            break
        archive_name = Path(unquote(urlparse(archive_url).path)).name
        archive_path = scratch / f"{archive_number:02d}_{archive_name}"
        if not archive_path.exists():
            print(f"  downloading archive {archive_number}")
            archive_path.write_bytes(fetch(archive_url))

        temp = Path(tempfile.mkdtemp(prefix=f"simpleplayer_{source.name.lower()}_"))
        try:
            extract_archive(archive_path, temp)
            for extension in source.wanted_extensions:
                if counts[extension] >= TARGET_COUNT:
                    continue
                candidates = sorted(
                    path for path in temp.rglob("*") if path.is_file() and path.suffix.lower() == extension
                )
                for candidate in candidates:
                    if counts[extension] >= TARGET_COUNT:
                        break
                    counts[extension] += 1
                    records.append(copy_candidate(source, candidate, archive_url, counts[extension]))
        finally:
            shutil.rmtree(temp, ignore_errors=True)

    for extension in source.wanted_extensions:
        if counts[extension] < TARGET_COUNT:
            print(f"warn: {source.name} produced {counts[extension]}/{TARGET_COUNT} for {extension}")
    return records


def main() -> int:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    all_records: list[dict[str, object]] = []
    failures: list[dict[str, str]] = []

    for source in SOURCES:
        try:
            all_records.extend(collect_source(source))
        except Exception as exc:
            failures.append({"source": source.name, "error": str(exc)})

    counts: dict[str, int] = {}
    for record in all_records:
        counts[record["extension"]] = counts.get(record["extension"], 0) + 1

    manifest = {
        "created_by": "tools/download_future_fixtures.py",
        "target_count_per_extension": TARGET_COUNT,
        "implementation_priority": [
            "32-bit consoles: PSF/PSF2/GSF",
            "64-bit consoles: USF",
            "Arcade and similar: SSF/DSF/QSF/Hoot/MAME-style backends",
        ],
        "counts": dict(sorted(counts.items())),
        "failures": failures,
        "notes": [
            "These fixtures are staged for future backend development and are not expected to play until their backends are implemented.",
            "PSF-family mini formats often require sibling library files; tests should use files from the same extracted set or staged folder.",
            "Use for local development smoke tests; review archive redistribution terms before bundling publicly.",
        ],
        "files": sorted(all_records, key=lambda item: (str(item["priority_group"]), str(item["extension"]), str(item["path"]))),
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"counts": manifest["counts"], "failures": failures}, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
