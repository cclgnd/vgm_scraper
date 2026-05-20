"""
Acquisition domain - manages discovery, tracking, and retrieval of resources.
"""

from vgm_scraper.acquisition.crawler import WebCrawler
from vgm_scraper.acquisition.local_scanner import LocalScanner
from vgm_scraper.acquisition.downloader import Downloader
from vgm_scraper.acquisition.retrieval import RetrievalManager
