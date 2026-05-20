"""
VGM Scraper - Provenance-aware VGM catalog and on-demand retrieval system.

Architecture:
- Catalog Domain: Console → Game → Collection → Track
- Acquisition Domain: Sources → Resource Nodes → Provenance Events
- Retrieval: On-demand download with job tracking
- API: HTTP/JSON interface for player integration
"""

__version__ = "2.0.0"
