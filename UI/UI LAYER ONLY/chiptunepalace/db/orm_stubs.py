import os
import hashlib
import datetime
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, text
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()

class Track(Base):
    __tablename__ = 'tracks'
    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String, nullable=False)
    artist = Column(String)
    console = Column(String)
    game = Column(String)
    file_path = Column(String, nullable=False)
    member_name = Column(String)
    fingerprint = Column(String)
    source_url = Column(String)
    format = Column(String)
    duration = Column(Float)
    added_at = Column(DateTime, default=datetime.datetime.utcnow)

class ScrapedPack(Base):
    __tablename__ = 'scraped_packs'
    id = Column(Integer, primary_key=True, autoincrement=True)
    console_name = Column(String, nullable=False)
    title = Column(String, nullable=False)
    url = Column(String, nullable=False)
    download_url = Column(String)
    source = Column(String)
    added_at = Column(DateTime, default=datetime.datetime.utcnow)

class Setting(Base):
    __tablename__ = 'settings'
    key = Column(String, primary_key=True)
    value = Column(String, nullable=False)

class PlaylistEntry(Base):
    __tablename__ = 'playlist'
    track_id = Column(Integer, ForeignKey('tracks.id'), primary_key=True)
    position = Column(Integer, primary_key=True)

class CanonicalConsole(Base):
    __tablename__ = 'canonical_consoles'
    id = Column(Integer, primary_key=True, autoincrement=True)
    slug = Column(String, nullable=False, unique=True)
    display_name = Column(String, nullable=False)
    maker = Column(String)
    generation = Column(String)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class ConsoleAlias(Base):
    __tablename__ = 'console_aliases'
    id = Column(Integer, primary_key=True, autoincrement=True)
    alias_name = Column(String, nullable=False)
    normalized_alias = Column(String, nullable=False)
    source = Column(String, nullable=False, default="unknown")
    region = Column(String)
    confidence = Column(Float, default=1.0)
    canonical_console_id = Column(Integer, ForeignKey('canonical_consoles.id'), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class DiscoveredNode(Base):
    __tablename__ = 'discovered_nodes'
    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String, nullable=False)
    node_type = Column(String, nullable=False)  # console|game|track|page
    url = Column(String, nullable=False)
    title = Column(String)
    parent_url = Column(String)
    confidence = Column(Float, default=0.0)
    last_seen_at = Column(DateTime, default=datetime.datetime.utcnow)

class DatabaseManager:
    """
    Manages the SQLite database using SQLAlchemy in WAL mode.
    Provides robust methods for indexing, querying, and duplicate avoidance.
    """
    def __init__(self, db_path='chiptunepalace/db/chiptunepalace.db'):
        # Normalize file path and handle absolute/relative path
        # In a development workspace context, check both local and absolute paths
        if not os.path.isabs(db_path):
            # Check if we are running from chiptunepalace parent directory
            # and resolve db path correctly
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            db_path = os.path.join(base_dir, db_path)
            
        db_dir = os.path.dirname(db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
            
        self.db_path = db_path
        
        # Initialize DebugService
        from chiptunepalace.services.debug_service import DebugService
        self.debug_service = DebugService()
        self.debug_service.log_info(f"DatabaseManager: Initializing database at path={db_path}")
        
        # SQLite connection URL
        self.engine = create_engine(f"sqlite:///{db_path}", connect_args={"timeout": 15})
        
        # Enable WAL mode
        with self.engine.connect() as conn:
            conn.execute(text("PRAGMA journal_mode=WAL;"))
            conn.commit()
            self.debug_service.log_info("DatabaseManager: WAL mode active.")
            
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def get_fingerprint(self, file_path: str) -> str | None:
        """Calculates MD5 hash of file content."""
        if not os.path.exists(file_path):
            return None
        hasher = hashlib.md5()
        try:
            with open(file_path, 'rb') as f:
                while chunk := f.read(8192):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except Exception as e:
            print(f"DatabaseManager: MD5 hash failed for {file_path}: {e}")
            return None

    def get_all_tracks(self) -> list:
        """Returns all tracks as a list of dicts."""
        session = self.Session()
        try:
            tracks = session.query(Track).order_by(Track.console, Track.game, Track.title).all()
            return [self._to_dict(t) for t in tracks]
        finally:
            session.close()

    def get_track_by_id(self, track_id: int) -> dict | None:
        """Returns details for a single track by its ID."""
        session = self.Session()
        try:
            track = session.query(Track).filter(Track.id == track_id).first()
            return self._to_dict(track) if track else None
        finally:
            session.close()

    def add_track(self, title: str, artist: str, file_path: str, **kwargs) -> int:
        """
        Adds a new track to the database, ensuring duplicate avoidance.
        If a duplicate is found (matching fingerprint or matching file_path + member_name),
        it returns the existing track's ID.
        """
        session = self.Session()
        try:
            fingerprint = kwargs.get('fingerprint')
            member_name = kwargs.get('member_name')
            
            # 1. De-duplicate by fingerprint (if provided)
            if fingerprint:
                existing = session.query(Track).filter(
                    Track.fingerprint == fingerprint,
                    Track.member_name == member_name
                ).first()
                if existing:
                    self.debug_service.log_info(f"DatabaseManager: Duplicate found by fingerprint! ID: {existing.id}")
                    print(f"DatabaseManager: Duplicate found by fingerprint! ID: {existing.id}")
                    # Update file path if it was empty or different (e.g. now local instead of online)
                    if file_path and existing.file_path != file_path:
                        existing.file_path = file_path
                        session.commit()
                    return existing.id

            # 2. De-duplicate by file_path + member_name
            existing = session.query(Track).filter(
                Track.file_path == file_path,
                Track.member_name == member_name
            ).first()
            if existing:
                self.debug_service.log_info(f"DatabaseManager: Duplicate found by file path & member! ID: {existing.id}")
                print(f"DatabaseManager: Duplicate found by file path & member! ID: {existing.id}")
                return existing.id

            # Create new track record
            new_track = Track(
                title=title,
                artist=artist,
                console=kwargs.get('console', 'Unknown Console'),
                game=kwargs.get('game', 'Unknown Game'),
                file_path=file_path,
                member_name=member_name,
                fingerprint=fingerprint,
                source_url=kwargs.get('source_url'),
                format=kwargs.get('format'),
                duration=kwargs.get('duration')
            )
            session.add(new_track)
            session.commit()
            self.debug_service.log_info(f"DatabaseManager: Added new track. Title: '{title}', Game: '{new_track.game}', ID: {new_track.id}")
            return new_track.id
        except Exception as e:
            session.rollback()
            self.debug_service.log_error(f"DatabaseManager: Failed to add track: {e}")
            print(f"DatabaseManager: Failed to add track: {e}")
            raise e
        finally:
            session.close()

    def _to_dict(self, track: Track) -> dict:
        return {
            'id': track.id,
            'title': track.title,
            'artist': track.artist,
            'console': track.console,
            'game': track.game,
            'file_path': track.file_path,
            'member_name': track.member_name,
            'fingerprint': track.fingerprint,
            'source_url': track.source_url,
            'format': track.format,
            'duration': track.duration,
            'added_at': track.added_at.isoformat() if track.added_at else None
        }

    def get_cached_packs(self, console_name: str) -> list:
        """Returns cached packs for a given console."""
        session = self.Session()
        try:
            packs = session.query(ScrapedPack).filter(ScrapedPack.console_name == console_name).order_by(ScrapedPack.title).all()
            return [{
                "title": p.title,
                "url": p.url,
                "download_url": p.download_url,
                "source": p.source
            } for p in packs]
        except Exception as e:
            self.debug_service.log_error(f"DatabaseManager: Failed to get cached packs for {console_name}: {e}")
            return []
        finally:
            session.close()

    def cache_packs(self, console_name: str, packs: list):
        """Caches game packs list in the database, overriding old cache entries."""
        session = self.Session()
        try:
            # Delete old entries to prevent duplicates and keep it clean
            session.query(ScrapedPack).filter(ScrapedPack.console_name == console_name).delete()
            for p in packs:
                entry = ScrapedPack(
                    console_name=console_name,
                    title=p.get("title", ""),
                    url=p.get("url", ""),
                    download_url=p.get("download_url", ""),
                    source=p.get("source", "")
                )
                session.add(entry)
            session.commit()
            self.debug_service.log_info(f"DatabaseManager: Cached {len(packs)} game packs for {console_name}.")
        except Exception as e:
            session.rollback()
            self.debug_service.log_error(f"DatabaseManager: Failed to cache packs for {console_name}: {e}")
        finally:
            session.close()

    def add_single_cached_pack(self, console_name: str, title: str, url: str, download_url: str, source: str):
        """Adds a single scraped pack to the database cache if it does not already exist."""
        session = self.Session()
        try:
            existing = session.query(ScrapedPack).filter(ScrapedPack.url == url).first()
            if not existing:
                entry = ScrapedPack(
                    console_name=console_name,
                    title=title,
                    url=url,
                    download_url=download_url,
                    source=source
                )
                session.add(entry)
                session.commit()
                self.debug_service.log_info(f"DatabaseManager: Cached single pack '{title}' under console '{console_name}'.")
        except Exception as e:
            session.rollback()
            self.debug_service.log_error(f"DatabaseManager: Failed to cache single pack for {console_name}: {e}")
        finally:
            session.close()

    def get_scraped_pack_by_name(self, console_name: str, title: str) -> dict | None:
        """Returns details for a scraped pack by console and title (game)."""
        session = self.Session()
        try:
            # Check exact match first
            entry = session.query(ScrapedPack).filter(
                ScrapedPack.console_name == console_name,
                ScrapedPack.title == title
            ).first()
            if not entry:
                # Fall back to case-insensitive substring match
                entry = session.query(ScrapedPack).filter(
                    ScrapedPack.console_name == console_name,
                    ScrapedPack.title.like(f"%{title}%")
                ).first()
            if entry:
                return {
                    "title": entry.title,
                    "url": entry.url,
                    "download_url": entry.download_url,
                    "source": entry.source
                }
            return None
        except Exception as e:
            self.debug_service.log_error(f"DatabaseManager: Failed to get scraped pack by name {title}: {e}")
            return None
        finally:
            session.close()

    # --- Canonical Console Registry ---
    def get_canonical_console_by_slug(self, slug: str) -> dict | None:
        session = self.Session()
        try:
            row = session.query(CanonicalConsole).filter(CanonicalConsole.slug == slug).first()
            if not row:
                return None
            return {
                "id": row.id,
                "slug": row.slug,
                "display_name": row.display_name,
                "maker": row.maker,
                "generation": row.generation
            }
        finally:
            session.close()

    def create_canonical_console(self, slug: str, display_name: str, maker: str = "", generation: str = "") -> int:
        session = self.Session()
        try:
            existing = session.query(CanonicalConsole).filter(CanonicalConsole.slug == slug).first()
            if existing:
                return existing.id
            row = CanonicalConsole(slug=slug, display_name=display_name, maker=maker, generation=generation)
            session.add(row)
            session.commit()
            return row.id
        finally:
            session.close()

    def get_alias_match(self, normalized_alias: str) -> dict | None:
        session = self.Session()
        try:
            row = session.query(ConsoleAlias).filter(ConsoleAlias.normalized_alias == normalized_alias).first()
            if not row:
                return None
            console = session.query(CanonicalConsole).filter(CanonicalConsole.id == row.canonical_console_id).first()
            if not console:
                return None
            return {
                "alias_name": row.alias_name,
                "normalized_alias": row.normalized_alias,
                "source": row.source,
                "region": row.region,
                "confidence": row.confidence,
                "canonical_console": {
                    "id": console.id,
                    "slug": console.slug,
                    "display_name": console.display_name,
                    "maker": console.maker,
                    "generation": console.generation
                }
            }
        finally:
            session.close()

    def upsert_console_alias(
        self,
        alias_name: str,
        normalized_alias: str,
        canonical_console_id: int,
        source: str = "unknown",
        region: str = "",
        confidence: float = 1.0
    ):
        session = self.Session()
        try:
            row = session.query(ConsoleAlias).filter(ConsoleAlias.normalized_alias == normalized_alias).first()
            if row:
                row.alias_name = alias_name
                row.source = source
                row.region = region
                row.confidence = confidence
                row.canonical_console_id = canonical_console_id
            else:
                row = ConsoleAlias(
                    alias_name=alias_name,
                    normalized_alias=normalized_alias,
                    source=source,
                    region=region,
                    confidence=confidence,
                    canonical_console_id=canonical_console_id
                )
                session.add(row)
            session.commit()
        finally:
            session.close()

    def list_canonical_consoles(self) -> list:
        session = self.Session()
        try:
            rows = session.query(CanonicalConsole).order_by(CanonicalConsole.display_name).all()
            return [{
                "id": r.id,
                "slug": r.slug,
                "display_name": r.display_name,
                "maker": r.maker,
                "generation": r.generation
            } for r in rows]
        finally:
            session.close()

    # --- Autonomous discovery graph ---
    def upsert_discovered_node(
        self,
        source: str,
        node_type: str,
        url: str,
        title: str = "",
        parent_url: str = "",
        confidence: float = 0.0
    ):
        session = self.Session()
        try:
            row = session.query(DiscoveredNode).filter(
                DiscoveredNode.source == source,
                DiscoveredNode.node_type == node_type,
                DiscoveredNode.url == url
            ).first()
            if row:
                row.title = title or row.title
                row.parent_url = parent_url or row.parent_url
                row.confidence = max(row.confidence or 0.0, confidence or 0.0)
                row.last_seen_at = datetime.datetime.utcnow()
            else:
                row = DiscoveredNode(
                    source=source,
                    node_type=node_type,
                    url=url,
                    title=title,
                    parent_url=parent_url,
                    confidence=confidence or 0.0
                )
                session.add(row)
            session.commit()
        finally:
            session.close()

    def reset_catalog_tables(self):
        """
        Clears catalog/discovery layers while preserving local track rows/files.
        """
        session = self.Session()
        try:
            session.query(ScrapedPack).delete()
            session.query(ConsoleAlias).delete()
            session.query(CanonicalConsole).delete()
            session.query(DiscoveredNode).delete()
            session.commit()
            self.debug_service.log_info("DatabaseManager: Catalog tables reset (scraped_packs, canonical_consoles, console_aliases, discovered_nodes).")
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
