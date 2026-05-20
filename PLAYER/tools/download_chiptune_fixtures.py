from __future__ import annotations

import hashlib
import html.parser
import gzip
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import unquote, urljoin, urlparse
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "chiptunes"
MANIFEST = OUTPUT / "MANIFEST.json"
USER_AGENT = "SIMPLEPLAYER fixture downloader/0.1"
TARGET_COUNT = 10
MAX_PAGES_PER_EXTENSION = 350
PROJECT_AY_URL = "https://vgmrips.net/mirror/ProjectAY.zip"
DISCH_NSFE_URL = "https://disch.zophar.net/nsfe.php"


@dataclass(frozen=True)
class FixtureSource:
    extension: str
    base_url: str
    repository: str


SOURCES = [
    FixtureSource(".ay", "https://ftp.modland.com/pub/modules/AY%20Emul/", "Modland"),
    FixtureSource(".gbs", "https://ftp.modland.com/pub/modules/Gameboy%20Sound%20System/", "Modland"),
    FixtureSource(".gym", "https://ftp.modland.com/pub/modules/Megadrive%20GYM/", "Modland"),
    FixtureSource(".hes", "https://ftp.modland.com/pub/modules/HES/", "Modland"),
    FixtureSource(".kss", "https://ftp.modland.com/pub/modules/KSS/", "Modland"),
    FixtureSource(".nsf", "https://ftp.modland.com/pub/modules/Nintendo%20Sound%20Format/", "Modland"),
    FixtureSource(".nsfe", "https://ftp.modland.com/pub/modules/Nintendo%20Sound%20Format/", "Modland"),
    FixtureSource(".sap", "https://ftp.modland.com/pub/modules/Slight%20Atari%20Player/", "Modland"),
    FixtureSource(".spc", "https://ftp.modland.com/pub/modules/Nintendo%20SPC/", "Modland"),
    FixtureSource(".vgm", "https://ftp.modland.com/pub/modules/Video%20Game%20Music/", "Modland"),
    FixtureSource(".vgz", "https://ftp.modland.com/pub/modules/Video%20Game%20Music/", "Modland"),
]


class LinkParser(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        for name, value in attrs:
            if name.lower() == "href" and value:
                self.links.append(value)


def fetch_text(url: str) -> str:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


def fetch_bytes(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=60) as response:
        return response.read()


def same_tree(url: str, base: str) -> bool:
    parsed = urlparse(url)
    base_parsed = urlparse(base)
    return parsed.netloc == base_parsed.netloc and parsed.path.startswith(base_parsed.path)


def safe_filename(url: str, extension: str, index: int) -> str:
    name = Path(unquote(urlparse(url).path)).name
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", name).strip(" .")
    if not name.lower().endswith(extension):
        name += extension
    return f"{index:02d}_{name}"


def discover_files(source: FixtureSource, count: int = TARGET_COUNT) -> list[str]:
    wanted = source.extension.lower()
    queue: deque[str] = deque([source.base_url])
    seen_pages: set[str] = set()
    files: list[str] = []

    while queue and len(files) < count and len(seen_pages) < MAX_PAGES_PER_EXTENSION:
        page = queue.popleft()
        if page in seen_pages:
            continue
        seen_pages.add(page)

        try:
            parser = LinkParser()
            parser.feed(fetch_text(page))
        except Exception as exc:
            print(f"warn: cannot read index {page}: {exc}", file=sys.stderr)
            continue

        dirs: list[str] = []
        for href in parser.links:
            if href.startswith("?") or href in {"../", "/"}:
                continue
            absolute = urljoin(page, href)
            if not same_tree(absolute, source.base_url):
                continue
            clean_path = unquote(urlparse(absolute).path).lower()
            if clean_path.endswith(wanted):
                files.append(absolute)
                if len(files) >= count:
                    break
            elif href.endswith("/"):
                dirs.append(absolute)

        queue.extend(sorted(set(dirs)))
        time.sleep(0.05)

    return files


def download_one(source: FixtureSource, url: str, index: int) -> dict[str, object]:
    folder = OUTPUT / source.extension.lstrip(".")
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / safe_filename(url, source.extension, index)

    if path.exists() and path.stat().st_size > 0:
        data = path.read_bytes()
    else:
        data = fetch_bytes(url)
        path.write_bytes(data)

    return {
        "extension": source.extension,
        "repository": source.repository,
        "source_url": url,
        "path": str(path.relative_to(ROOT)).replace("\\", "/"),
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def download_source(source: FixtureSource) -> list[dict[str, object]]:
    print(f"discovering {source.extension} from {source.base_url}")
    urls = discover_files(source, count=80 if source.extension == ".vgz" else TARGET_COUNT)
    if len(urls) < TARGET_COUNT:
        print(f"warn: found only {len(urls)} file(s) for {source.extension}", file=sys.stderr)

    results: list[dict[str, object]] = []
    next_index = 1
    for url in urls:
        if len(results) >= TARGET_COUNT:
            break
        print(f"downloading {source.extension} {next_index}/{TARGET_COUNT}")
        result = download_one(source, url, next_index)
        if source.extension == ".vgz" and not libgme_can_render(ROOT / str(result["path"])):
            (ROOT / str(result["path"])).unlink(missing_ok=True)
            continue
        results.append(result)
        next_index += 1
    return results


def libgme_can_render(path: Path) -> bool:
    try:
        from simpleplayer.engines import GmeEngine

        engine = GmeEngine()
        try:
            engine.open(path)
            engine.render(1024)
            return True
        finally:
            engine.close()
    except Exception:
        return False


def add_record(records: list[dict[str, object]], extension: str, repository: str, source_url: str, path: Path, data: bytes) -> None:
    relative = str(path.relative_to(ROOT)).replace("\\", "/")
    records[:] = [record for record in records if record.get("path") != relative]
    records.append(
        {
            "extension": extension,
            "repository": repository,
            "source_url": source_url,
            "path": relative,
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        }
    )


def normalize_gym(records: list[dict[str, object]]) -> None:
    for record in list(records):
        if record["extension"] != ".gym":
            continue
        path = ROOT / str(record["path"])
        data = path.read_bytes()
        if not data.startswith(b"GYMX"):
            continue
        raw = __import__("zlib").decompress(data[428:])
        path.write_bytes(raw)
        add_record(
            records,
            ".gym",
            str(record["repository"]),
            f"{record['source_url']} (GYMX zlib payload normalized)",
            path,
            raw,
        )


def fill_project_ay(records: list[dict[str, object]]) -> None:
    if sum(1 for record in records if record["extension"] == ".ay") >= TARGET_COUNT:
        return

    archive = OUTPUT / "_ProjectAY.zip"
    archive.write_bytes(fetch_bytes(PROJECT_AY_URL))
    folder = OUTPUT / "ay"
    folder.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as zf:
        names = sorted(name for name in zf.namelist() if name.lower().endswith(".ay") and not name.endswith("/"))
        for index, name in enumerate(names[:TARGET_COUNT], start=1):
            data = zf.read(name)
            path = folder / f"{index:02d}_{Path(name).name}"
            path.write_bytes(data)
            add_record(records, ".ay", "Project AY via VGMRips mirror", f"{PROJECT_AY_URL}#{name}", path, data)
    archive.unlink(missing_ok=True)


def fill_nsfe(records: list[dict[str, object]]) -> None:
    if sum(1 for record in records if record["extension"] == ".nsfe") >= TARGET_COUNT:
        return

    if not shutil.which("7z"):
        print("warn: 7z not found; cannot extract Disch NSFe .rar fixtures", file=sys.stderr)
        return

    parser = LinkParser()
    parser.feed(fetch_text(DISCH_NSFE_URL))
    urls = [urljoin(DISCH_NSFE_URL, href) for href in parser.links if href.lower().endswith(".rar")][:TARGET_COUNT]
    folder = OUTPUT / "nsfe"
    folder.mkdir(parents=True, exist_ok=True)

    for index, url in enumerate(urls, start=1):
        rar_path = OUTPUT / f"_nsfe_{index:02d}.rar"
        rar_path.write_bytes(fetch_bytes(url))
        temp = Path(tempfile.mkdtemp(prefix="simpleplayer_nsfe_"))
        try:
            subprocess.run(["7z", "x", str(rar_path), f"-o{temp}", "-y"], check=True, stdout=subprocess.DEVNULL)
            candidates = sorted(temp.rglob("*.nsfe")) or sorted(temp.rglob("*.NSFE"))
            if not candidates:
                print(f"warn: no .nsfe found inside {url}", file=sys.stderr)
                continue
            data = candidates[0].read_bytes()
            path = folder / f"{index:02d}_{candidates[0].name}"
            path.write_bytes(data)
            add_record(records, ".nsfe", "Disch NSFe Archive", url, path, data)
        finally:
            rar_path.unlink(missing_ok=True)
            shutil.rmtree(temp, ignore_errors=True)


def derive_vgm(records: list[dict[str, object]]) -> None:
    if sum(1 for record in records if record["extension"] == ".vgm") >= TARGET_COUNT:
        return

    folder = OUTPUT / "vgm"
    folder.mkdir(parents=True, exist_ok=True)
    source_files = sorted((OUTPUT / "vgz").glob("*.vgz"))[:TARGET_COUNT]
    for index, vgz in enumerate(source_files, start=1):
        data = gzip.decompress(vgz.read_bytes())
        path = folder / f"{index:02d}_{vgz.stem}.vgm"
        path.write_bytes(data)
        add_record(records, ".vgm", "Derived losslessly from downloaded Modland VGZ", str(vgz.relative_to(ROOT)).replace("\\", "/"), path, data)


def main() -> int:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    all_results: list[dict[str, object]] = []
    failures: list[dict[str, str]] = []

    with ThreadPoolExecutor(max_workers=4) as executor:
        future_map = {executor.submit(download_source, source): source for source in SOURCES}
        for future in as_completed(future_map):
            source = future_map[future]
            try:
                all_results.extend(future.result())
            except Exception as exc:
                failures.append({"extension": source.extension, "error": str(exc)})

    fill_project_ay(all_results)
    fill_nsfe(all_results)
    normalize_gym(all_results)
    derive_vgm(all_results)

    by_extension: dict[str, int] = {}
    for item in all_results:
        by_extension[item["extension"]] = by_extension.get(item["extension"], 0) + 1

    manifest = {
        "created_by": "tools/download_chiptune_fixtures.py",
        "target_count_per_extension": TARGET_COUNT,
        "repositories": sorted({source.repository for source in SOURCES}),
        "counts": dict(sorted(by_extension.items())),
        "failures": failures,
        "notes": [
            "VGZ is gzipped VGM; .vgm fixtures may be derived losslessly from downloaded .vgz files to exercise raw VGM loading.",
            "GYM fixtures from GYMX containers may be normalized by inflating the zlib payload for libgme compatibility.",
            "Fixtures are for local development smoke tests of native emulated music formats.",
        ],
        "files": sorted(all_results, key=lambda item: (str(item["extension"]), str(item["path"]))),
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(json.dumps({"counts": manifest["counts"], "failures": failures}, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
