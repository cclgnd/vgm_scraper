import requests
from urllib.parse import quote
from PySide6.QtCore import QThread, Signal
from chiptunepalace.services.track_service import TrackService
from chiptunepalace.services.console_canonicalizer import ConsoleCanonicalizer
from chiptunepalace.services.discovery_crawler import DiscoveryCrawler

class ScraperThread(QThread):
    """
    Background thread for executing scraping tasks without blocking the UI.
    """
    task_finished = Signal(object) # Can emit list of results or other objects
    error = Signal(str)

    def __init__(self, task_fn, *args, **kwargs):
        super().__init__()
        self.task_fn = task_fn
        self.args = args
        self.kwargs = kwargs

    def run(self):
        try:
            results = self.task_fn(*self.args, **self.kwargs)
            self.task_finished.emit(results)
        except Exception as e:
            self.error.emit(str(e))


class RandomizerThread(QThread):
    """
    Background thread that selects a random console, then a random pack,
    and then a random track across the entire online catalog + local library.
    """
    task_finished = Signal(dict)
    error = Signal(str)

    def __init__(self, scraper, track_service):
        super().__init__()
        self.scraper = scraper
        self.track_service = track_service

    def run(self):
        try:
            import random
            
            # 1. Fetch consoles
            consoles = self.scraper.get_consoles()
            if not consoles:
                raise Exception("Failed to load systems catalog.")
                
            # Pick a random system
            console = random.choice(consoles)
            console_name = console["name"]
            console_url = console["url"]
            
            # 2. Fetch packs for the selected system
            packs = self.scraper.get_packs_by_console(console_url)
            if not packs:
                raise Exception(f"No game albums found in system: {console_name}")
                
            # Pick a random album/pack
            pack = random.choice(packs)
            pack_title = pack["title"]
            pack_url = pack["url"]
            download_url = pack.get("download_url", pack_url)
            source = pack.get("source", "VGMRips")
            
            # 3. Check if local tracks exist in the database for this game pack
            local_tracks = self.track_service.get_tracks_by_console_and_game(console_name, pack_title)
            
            if local_tracks:
                # Pick a local track!
                track = random.choice(local_tracks)
                self.task_finished.emit({
                    "type": "local",
                    "track_id": track["id"],
                    "title": track["title"],
                    "console": console_name,
                    "game": pack_title
                })
            elif source == "ModArchive":
                # ModArchive tracks are the pack itself (single tracker module)
                self.task_finished.emit({
                    "type": "online",
                    "title": pack_title,
                    "console": "ModArchive",
                    "game": pack_title,
                    "pack_url": pack_url,
                    "download_url": download_url,
                    "source": source
                })
            else:
                # Scrape the tracks list for this online pack
                tracks = self.scraper.get_tracks_in_pack(pack_url)
                if not tracks:
                    # Fallback to streaming the whole pack ZIP
                    tracks = [{"title": pack_title}]
                    
                track = random.choice(tracks)
                self.task_finished.emit({
                    "type": "online",
                    "title": track["title"],
                    "console": console_name,
                    "game": pack_title,
                    "pack_url": pack_url,
                    "download_url": download_url,
                    "source": source
                })
        except Exception as e:
            self.error.emit(str(e))


class WebScraperService:
    """
    Handles the adaptive scraping of music metadata from external sources.
    """
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
        self.libretro_base = "https://raw.githubusercontent.com/libretro-thumbnails"
        self._zophar_download_urls = {}
        self.canonicalizer = ConsoleCanonicalizer()
        self.discovery_crawler = DiscoveryCrawler(db_manager=self.canonicalizer.db, session=self.session)
        # Mapping common names to Libretro names
        self.system_map = {
            "SNES": "Nintendo - Super Nintendo Entertainment System",
            "NES": "Nintendo - Nintendo Entertainment System",
            "GENESIS": "Sega - Mega Drive - Genesis",
            "GAMEBOY": "Nintendo - Game Boy",
            "GB": "Nintendo - Game Boy",
            "GBA": "Nintendo - Game Boy Advance",
            "MASTERSYSTEM": "Sega - Master System - Mark III",
            "PCENGINE": "NEC - PC Engine - TurboGrafx 16",
            "PLAYSTATION": "Sony - PlayStation"
        }

    def get_consoles(self) -> list:
        """
        Fetches the list of popular consoles from VGMRips and custom directories.
        Formats all names to follow the "Maker Console name" structure.
        """
        import requests
        import re
        from bs4 import BeautifulSoup
        
        url = "https://vgmrips.net/packs/systems"
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            maker_map = {
                "sega": "Sega",
                "nintendo": "Nintendo",
                "nec": "NEC",
                "sharp": "Sharp",
                "ibm": "IBM",
                "snk": "SNK",
                "capcom": "Capcom",
                "atari": "Atari",
                "commodore": "Commodore",
                "sinclair": "Sinclair",
                "apple": "Apple",
                "microsoft": "Microsoft",
                "sony": "Sony",
                "bandai": "Bandai",
                "konami": "Konami",
                "namco": "Namco",
                "taito": "Taito",
                "toaplan": "Toaplan",
                "hudson": "Hudson",
                "fujitsu": "Fujitsu",
                "seibu": "Seibu",
                "cave": "Cave",
                "tandy-corporation": "Tandy",
                "nec-home-electronics": "NEC",
                "snk-playmore": "SNK",
                "bandai-namco": "Namco",
                "commodore-business-machines": "Commodore"
            }
            
            consoles = []
            # 1. Fetch VGMRips Consoles
            for a in soup.find_all('a', href=re.compile(r'/packs/system/')):
                name = a.text.strip()
                href = a.get('href')
                if name and not name.isdigit() and "PACKS" not in name.upper():
                    if not href.startswith('http'):
                        href = "https://vgmrips.net" + href
                    
                    # Deduce maker from URL slug
                    maker_name = ""
                    match = re.search(r'/packs/system/([^/]+)/', href)
                    if match:
                        maker_slug = match.group(1).lower()
                        if maker_slug not in ["other", "various"]:
                            maker_name = maker_map.get(maker_slug, maker_slug.title())
                    
                    # Normalize console name to "Maker Console name"
                    formatted_name = name
                    if maker_name and not name.lower().startswith(maker_name.lower()):
                        formatted_name = f"{maker_name} {name}"
                        
                    consoles.append({"name": formatted_name, "url": href})

            # De-duplicate
            unique_consoles = []
            seen = set()
            for c in consoles:
                if c['name'] not in seen:
                    unique_consoles.append(c)
                    seen.add(c['name'])

            # Slice VGMRips to top 50 systems to save memory/speed, and append custom platforms
            unique_consoles = unique_consoles[:50]

            # 2. Add some ModArchive "Genres" to catalog
            unique_consoles.append({"name": "MODARCHIVE: CHIPTUNE", "url": "https://modarchive.org/index.php?request=view_genres&query=14"})
            unique_consoles.append({"name": "MODARCHIVE: DEMO", "url": "https://modarchive.org/index.php?request=view_genres&query=18"})
            unique_consoles.append({"name": "MODARCHIVE: KEYGEN", "url": "https://modarchive.org/index.php?request=view_genres&query=57"})

            # 3. Add Zophar Console Directories (with "Maker Console name" structure!)
            unique_consoles.append({"name": "Sega Saturn (ZOPHAR)", "url": "https://www.zophar.net/music/sega-saturn-ssf"})
            unique_consoles.append({"name": "Nintendo 64 (ZOPHAR)", "url": "https://www.zophar.net/music/nintendo-64-usf"})
            unique_consoles.append({"name": "Sony PlayStation (ZOPHAR)", "url": "https://www.zophar.net/music/playstation-psf"})
            unique_consoles.append({"name": "Sega Dreamcast (ZOPHAR)", "url": "https://www.zophar.net/music/sega-dreamcast-dsf"})

            # 4. Global canonicalization + de-duplication
            canonical_map = {}
            for c in unique_consoles:
                canonical = self.canonicalizer.resolve(c.get("name", ""), source="scraper_seed")
                slug = canonical["slug"]
                if slug not in canonical_map:
                    canonical_map[slug] = {
                        "name": canonical["display_name"],
                        "url": c.get("url", "")
                    }

            return list(canonical_map.values())
        except Exception as e:
            print(f"Catalog Scraper Error: {e}")
            return []

    def discover_consoles_autonomous(self, source: str, seed_url: str) -> list:
        """
        Autonomous discovery entrypoint.
        Crawls and canonicalizes discovered console links from a source seed page.
        """
        discovered = self.discovery_crawler.discover_console_links(source=source, seed_url=seed_url)
        merged = {}
        for node in discovered:
            canonical = self.canonicalizer.resolve(node.title, source=source, confidence=node.confidence)
            slug = canonical["slug"]
            if slug not in merged:
                merged[slug] = {"name": canonical["display_name"], "url": node.url}
        return list(merged.values())

    def get_packs_by_console(self, console_url: str) -> list:
        """
        Fetches all music packs for a specific console or genre.
        Supports VGMRips, ModArchive, and Zophar URLs.
        """
        if "modarchive.org" in console_url:
            return self._search_modarchive_by_url(console_url)
        elif "zophar.net" in console_url:
            return self._get_zophar_packs(console_url)
        return self._get_vgmrips_packs(console_url)

    def _get_vgmrips_packs(self, console_url: str) -> list:
        import requests
        from bs4 import BeautifulSoup
        
        results = []
        max_pages = 50  # Scrape up to 50 pages to get the full complete catalog of all games per console!
        
        for page in range(1, max_pages + 1):
            page_url = console_url
            if page > 1:
                if "?" in console_url:
                    page_url = f"{console_url}&p={page}"
                else:
                    page_url = f"{console_url}?p={page}"
            
            try:
                response = self.session.get(page_url, timeout=10)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, 'html.parser')
                
                page_results = []
                for h2 in soup.find_all('h2', class_='title'):
                    links = h2.find_all('a')
                    if len(links) >= 3:
                        title = links[1].text.strip()
                        detail_url = links[1].get('href')
                        zip_url = links[2].get('href')
                        
                        if detail_url and ('.zip' in zip_url.lower()):
                            if not detail_url.startswith('http'):
                                detail_url = "https://vgmrips.net" + detail_url
                            if not zip_url.startswith('http'):
                                zip_url = "https://vgmrips.net" + zip_url
                            page_results.append({
                                "title": title,
                                "url": detail_url,
                                "download_url": zip_url,
                                "source": "VGMRips"
                            })
                
                if not page_results:
                    break  # No more results, stop paging early
                    
                results.extend(page_results)
                
            except Exception as e:
                print(f"Pack Scraper Error on page {page}: {e}")
                break
                
        return results

    def _search_modarchive_by_url(self, url: str) -> list:
        import requests
        from bs4 import BeautifulSoup
        import re
        
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            results = []
            for a in soup.find_all('a', href=re.compile(r'moduleid=\d+')):
                href = a.get('href')
                if 'downloads.php' in href:
                    title_link = a.find_next('a', class_='standard-link')
                    title = title_link.text.strip() if title_link else "Unknown Module"
                    
                    if not href.startswith('http'):
                        href = "https://api.modarchive.org/" + href.split('/')[-1] if 'api' not in href else "https://api.modarchive.org/" + href
                    
                    results.append({
                        "title": title,
                        "url": href,
                        "source": "ModArchive"
                    })
            return results
        except Exception as e:
            print(f"ModArchive Pack Scraper Error: {e}")
            return []

    def get_tracks_in_pack(self, pack_url: str) -> list:
        """
        Fetches individual track names from a pack's detail page.
        Supports both VGMRips and Zophar.
        """
        if "vgmrips.net" in pack_url:
            return self._get_vgmrips_tracks(pack_url)
        elif "zophar.net" in pack_url:
            return self._get_zophar_tracks(pack_url)
        return []

    def _get_vgmrips_tracks(self, pack_url: str) -> list:
        import requests
        from bs4 import BeautifulSoup
        try:
            response = self.session.get(pack_url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            tracks = []
            for td in soup.find_all('td', class_='title'):
                name = td.text.strip()
                if name:
                    tracks.append({"title": name})
            return tracks
        except Exception as e:
            print(f"VGMRips Track Scraper Error: {e}")
            return []

    def _get_zophar_packs(self, console_url: str) -> list:
        import requests
        from bs4 import BeautifulSoup
        try:
            response = self.session.get(console_url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            results = []
            for td in soup.find_all('td', class_='name'):
                a = td.find('a')
                if a and a.get('href'):
                    title = a.text.strip()
                    href = a.get('href')
                    if not href.startswith('http'):
                        href = "https://www.zophar.net" + href
                    results.append({
                        "title": title,
                        "url": href,
                        "download_url": href, # Resolved dynamically on request
                        "source": "Zophar"
                    })
            return results
        except Exception as e:
            print(f"Zophar Pack Scraper Error: {e}")
            return []

    def _get_zophar_tracks(self, pack_url: str) -> list:
        import requests
        from bs4 import BeautifulSoup
        try:
            response = self.session.get(pack_url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            tracks = []
            for tr in soup.find_all('tr', class_='trackrow'):
                td_name = tr.find('td', class_='name')
                if td_name:
                    name = td_name.text.strip()
                    if name:
                        tracks.append({"title": name})
                        
            zip_links = []
            for a in soup.find_all('a', href=True):
                href = a.get('href')
                if ('/download_file/' in href) or any(href.lower().endswith(ext) for ext in ['.zip', '.7z', '.rar', '.gz']):
                    zip_links.append((a.text.strip(), href))
                    
            if zip_links:
                emu_link = None
                # Prioritize original emulation/chiptune format (e.g. USF, SPC, NSF, GBS, etc)
                for text, href in zip_links:
                    text_lower = text.lower()
                    href_lower = href.lower()
                    if 'original' in text_lower or 'emu' in text_lower or 'original' in href_lower or 'emu' in href_lower:
                        emu_link = href
                        break
                if not emu_link:
                    # Next prioritize zip/7z/rar files (avoiding MP3)
                    for text, href in zip_links:
                        text_lower = text.lower()
                        if 'mp3' not in text_lower:
                            emu_link = href
                            break
                if not emu_link:
                    emu_link = zip_links[0][1]
                    
                if emu_link and not emu_link.startswith('http'):
                    emu_link = "https://www.zophar.net" + emu_link
                    
                self._zophar_download_urls[pack_url] = emu_link
                
            return tracks
        except Exception as e:
            print(f"Zophar Track Scraper Error: {e}")
            return []

    def get_resolved_zophar_download_url(self, pack_url: str) -> str:
        if pack_url in self._zophar_download_urls:
            return self._zophar_download_urls[pack_url]
        self._get_zophar_tracks(pack_url)
        return self._zophar_download_urls.get(pack_url, pack_url)

    def get_artwork(self, console_name: str, game_name: str) -> dict:
        """
        Attempts to find cover art and screenshot from Libretro Thumbnails.
        """
        system = self.system_map.get(console_name.upper(), console_name)
        # Libretro uses special characters encoding (e.g. # -> %23)
        safe_game = quote(game_name)
        
        urls = {
            "boxart": f"{self.libretro_base}/{system}/master/Named_Boxarts/{safe_game}.png",
            "screenshot": f"{self.libretro_base}/{system}/master/Named_Snaps/{safe_game}.png"
        }
        return urls

    def search_online(self, query: str) -> list:
        """
        Searches multiple online repositories and returns a combined list of results.
        """
        results = []
        
        # 1. Search VGMRips
        try:
            results.extend(self._search_vgmrips(query))
        except Exception as e:
            print(f"VGMRips Search Error: {e}")
            
        # 2. Search ModArchive
        try:
            results.extend(self._search_modarchive(query))
        except Exception as e:
            print(f"ModArchive Search Error: {e}")
            
        # 3. Search Project 2612
        try:
            results.extend(self._search_project2612(query))
        except Exception as e:
            print(f"Project 2612 Search Error: {e}")
            
        return results

    def _search_project2612(self, query: str) -> list:
        import requests
        from bs4 import BeautifulSoup
        url = f"http://project2612.org/search.php?query={query}"
        response = self.session.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        results = []
        # Project 2612 search results are usually in a table
        for a in soup.find_all('a', href=lambda x: x and 'details.php?id=' in x):
            title = a.text.strip()
            detail_url = "http://project2612.org/" + a.get('href')
            # Extract ID to build download link (usually download.php?id=...)
            import re
            match = re.search(r'id=(\d+)', detail_url)
            if match:
                track_id = match.group(1)
                zip_url = f"http://project2612.org/download.php?id={track_id}"
                results.append({
                    "title": title,
                    "url": zip_url,
                    "artist": "Sega Genesis",
                    "source": "Project2612",
                    "console_name": "Sega Mega Drive / Genesis",
                    "console_url": "https://vgmrips.net/packs/system/sega/genesis"
                })
        return results

    def _search_vgmrips(self, query: str) -> list:
        import requests
        from bs4 import BeautifulSoup
        import re
        
        url = f"https://vgmrips.net/packs/search?q={query}"
        response = self.session.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        results = []
        
        # Check if the search redirected to a single pack details page
        if "/packs/pack/" in response.url:
            title = ""
            h1 = soup.find('h1')
            if h1:
                title = h1.text.strip()
            else:
                title = soup.title.text.strip().split(' vgm music')[0]
                
            zip_url = ""
            for a in soup.find_all('a'):
                href = a.get('href', '')
                if a.text.strip() == "Download" and ('.zip' in href.lower()):
                    if not href.startswith('http'):
                        href = "https://vgmrips.net" + href
                    zip_url = href
                    break
            
            # Find the system console links from single pack page
            system_name = "Various"
            system_url = ""
            sys_link = soup.find('a', href=re.compile(r'/packs/system/'))
            if sys_link:
                system_name = sys_link.text.strip()
                system_url = sys_link.get('href')
                if not system_url.startswith('http'):
                    system_url = "https://vgmrips.net" + system_url

            if title and zip_url:
                results.append({
                    "title": title,
                    "url": response.url,
                    "download_url": zip_url,
                    "artist": "Various",
                    "source": "VGMRips",
                    "console_name": system_name,
                    "console_url": system_url
                })
            return results

        # Otherwise, parse standard search results list
        for h2 in soup.find_all('h2', class_='title'):
            links = h2.find_all('a')
            if len(links) >= 3:
                system_name = links[0].text.strip()
                system_url = links[0].get('href')
                title = links[1].text.strip()
                detail_url = links[1].get('href')
                zip_url = links[2].get('href')
                
                if detail_url and ('.zip' in zip_url.lower()):
                    if not detail_url.startswith('http'):
                        detail_url = "https://vgmrips.net" + detail_url
                    if not zip_url.startswith('http'):
                        zip_url = "https://vgmrips.net" + zip_url
                    if system_url and not system_url.startswith('http'):
                        system_url = "https://vgmrips.net" + system_url
                        
                    results.append({
                        "title": title,
                        "url": detail_url,
                        "download_url": zip_url,
                        "artist": "Various",
                        "source": "VGMRips",
                        "console_name": system_name,
                        "console_url": system_url
                    })
        return results

    def _search_modarchive(self, query: str) -> list:
        import requests
        from bs4 import BeautifulSoup
        
        # ModArchive search URL
        url = f"https://modarchive.org/index.php?request=search&query={query}&submit=Find&search_type=filename_or_songtitle"
        response = self.session.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        results = []
        # Results are typically in <tr> elements within a table
        # We look for links to downloads.php?moduleid=...
        import re
        for a in soup.find_all('a', href=re.compile(r'moduleid=\d+')):
            href = a.get('href')
            if 'downloads.php' in href:
                title_link = a.find_next('a', class_='standard-link')
                if title_link:
                    title = title_link.text.strip()
                else:
                    title = a.get('title', 'Unknown Module')
                
                # Normalize URL
                if not href.startswith('http'):
                    href = "https://api.modarchive.org/" + href.split('/')[-1] if 'api' not in href else "https://api.modarchive.org/" + href
                
                results.append({
                    "title": title,
                    "url": href,
                    "artist": "Module Artist",
                    "source": "ModArchive",
                    "console_name": "MODARCHIVE: CHIPTUNE",
                    "console_url": "https://modarchive.org/index.php?request=view_genres&query=14"
                })
        return results[:20] # Limit results

    def discover_music_sources(self):
        """
        Identifies potential reliable sources for music metadata.
        """
        return ["VGMdb", "ModArchive", "Project2612"]

    def scrape_metadata_for_file(self, file_path: str) -> dict:
        """
        Attempts to find metadata for a given chiptune file by filename or tags.
        Uses regex patterns to extract Artist and Title.
        """
        import os
        import re
        filename = os.path.basename(file_path)
        name_no_ext = os.path.splitext(filename)[0]
        
        # Patterns to try
        patterns = [
            r'^(?P<artist>.+?)\s*-\s*(?P<title>.+)$',      # Artist - Title
            r'^(?P<title>.+?)\s*\((?P<artist>.+)\)$',    # Title (Artist)
            r'^(?P<artist>.+?)\s*-\s*(?P<album>.+?)\s*-\s*(?P<title>.+)$', # Artist - Album - Title
        ]
        
        metadata = {
            "title": name_no_ext,
            "artist": "Unknown Artist",
            "album": "Unknown Album",
            "genre": "Chiptune"
        }
        
        for p in patterns:
            match = re.match(p, name_no_ext)
            if match:
                res = match.groupdict()
                metadata.update(res)
                break
                
        print(f"AdaptiveScraper: Parsed {filename} -> {metadata['artist']} - {metadata['title']}")
        return metadata

    def scrape_artist_info(self, artist_name: str, source: str) -> dict:
        print(f"Scraping {artist_name} from {source}...")
        # Placeholder for API calls
        return {
            "tracks": [],
            "genres": ["Chiptune"],
            "metadata_source": source
        }

    def integrate_metadata(self, file_path: str, scraped_data: dict):
        """
        Updates the database with scraped info.
        """
        # Implementation would call track_service.update_track or similar
        print(f"Integrating metadata for {file_path}")
        return True
