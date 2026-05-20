import re

from chiptunepalace.db.orm_stubs import DatabaseManager


class ConsoleCanonicalizer:
    """
    Canonical console resolver that merges regional/source aliases into one global console identity.
    """

    REGION_TOKENS = {
        "usa", "us", "u", "japan", "jp", "j", "europe", "eu", "eur", "e", "pal", "ntsc", "world", "w"
    }

    REPLACEMENTS = {
        "mega drive": "genesis",
        "megadrive": "genesis",
        "super famicom": "snes",
        "famicom": "nes",
        "nintendo entertainment system": "nes",
        "super nintendo entertainment system": "snes",
        "game boy color": "gbc",
        "game boy advance": "gba",
        "pc engine": "turbografx16",
        "turbo grafx 16": "turbografx16",
        "turbo grafx-16": "turbografx16",
    }

    def __init__(self, db_manager: DatabaseManager | None = None):
        self.db = db_manager or DatabaseManager()

    def normalize_name(self, name: str) -> str:
        text = (name or "").lower().strip()
        text = re.sub(r"\([^)]*\)", " ", text)
        text = re.sub(r"\[[^\]]*\]", " ", text)
        text = text.replace("-", " ")
        text = text.replace("/", " ")
        text = re.sub(r"[^a-z0-9\s]", " ", text)
        text = re.sub(r"\s+", " ", text).strip()

        for src, dst in self.REPLACEMENTS.items():
            text = re.sub(rf"\b{re.escape(src)}\b", dst, text)

        parts = [p for p in text.split() if p not in self.REGION_TOKENS]
        return " ".join(parts).strip()

    def slugify(self, normalized_name: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", normalized_name.strip().lower())
        slug = slug.strip("-")
        return slug or "unknown-console"

    def _default_display_name(self, normalized_name: str) -> str:
        parts = normalized_name.split()
        return " ".join(p.upper() if len(p) <= 3 else p.title() for p in parts) if parts else "Unknown Console"

    def resolve(self, raw_name: str, source: str = "unknown", region: str = "", confidence: float = 1.0) -> dict:
        normalized = self.normalize_name(raw_name)
        if not normalized:
            normalized = "unknown console"

        alias = self.db.get_alias_match(normalized)
        if alias:
            return alias["canonical_console"]

        slug = self.slugify(normalized)
        existing = self.db.get_canonical_console_by_slug(slug)
        if existing:
            self.db.upsert_console_alias(
                alias_name=raw_name or existing["display_name"],
                normalized_alias=normalized,
                canonical_console_id=existing["id"],
                source=source,
                region=region,
                confidence=confidence
            )
            return existing

        display_name = self._default_display_name(normalized)
        canonical_id = self.db.create_canonical_console(slug=slug, display_name=display_name)
        self.db.upsert_console_alias(
            alias_name=raw_name or display_name,
            normalized_alias=normalized,
            canonical_console_id=canonical_id,
            source=source,
            region=region,
            confidence=confidence
        )
        return self.db.get_canonical_console_by_slug(slug) or {
            "id": canonical_id,
            "slug": slug,
            "display_name": display_name,
            "maker": "",
            "generation": ""
        }
