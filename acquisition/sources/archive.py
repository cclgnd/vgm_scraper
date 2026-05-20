"""
Internet Archive source adapter.
https://archive.org - Massive digital library with game music collections.
"""

from vgm_scraper.acquisition.sources.base import BaseSource, DiscoveredResource


class ArchiveOrgSource(BaseSource):
    name = "archive"
    base_url = "https://archive.org"
    source_type = "web"

    def discover(self, max_depth: int = 3) -> list[DiscoveredResource]:
        results = []
        url = f"{self.base_url}/advancedsearch.php?q=mediatype:audio+AND+(game+music+OR+chiptune+OR+vgm)&fl[]=identifier,title,creator&sort[]=addeddate+desc&rows=100&output=json"
        resp = self.session.get(url)
        if not resp:
            return []
        try:
            data = resp.json()
            docs = data.get("response", {}).get("docs", [])
            for doc in docs:
                identifier = doc.get("identifier", "")
                title = doc.get("title", identifier)
                if isinstance(title, list):
                    title = title[0]
                results.append(DiscoveredResource(
                    title=title,
                    url=f"{self.base_url}/details/{identifier}",
                    download_url=f"{self.base_url}/download/{identifier}",
                    node_type="pack",
                    metadata={"creator": doc.get("creator", "")},
                ))
        except Exception:
            pass
        return results

    def search(self, query: str) -> list[DiscoveredResource]:
        import urllib.parse
        url = f"{self.base_url}/advancedsearch.php?q={urllib.parse.quote(query)}+AND+mediatype:audio&fl[]=identifier,title,creator&rows=100&output=json"
        resp = self.session.get(url)
        if not resp:
            return []
        try:
            data = resp.json()
            docs = data.get("response", {}).get("docs", [])
            results = []
            for doc in docs:
                identifier = doc.get("identifier", "")
                title = doc.get("title", identifier)
                if isinstance(title, list):
                    title = title[0]
                results.append(DiscoveredResource(
                    title=title,
                    url=f"{self.base_url}/details/{identifier}",
                    download_url=f"{self.base_url}/download/{identifier}",
                    node_type="pack",
                    metadata={"creator": doc.get("creator", "")},
                ))
            return results
        except Exception:
            return []
