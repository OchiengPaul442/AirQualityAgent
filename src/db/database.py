import logging
import os
import re
from pathlib import Path
from urllib.parse import quote, urlparse

from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from src.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def parse_database_url_smart(db_url: str) -> str:
    """
    Intelligently parse database URLs, handling passwords with special characters like @.

    Standard URL parsing fails when passwords contain @ symbols because @ is used as
    the delimiter between user info and host. This function detects and fixes such cases.

    Examples:
        postgresql://user:pass@word@host:5432/db -> correctly parsed
        postgresql://user:pass%40word@host:5432/db -> already URL-encoded, works fine
    """
    if not db_url or "://" not in db_url:
        return db_url

    # If URL is already properly encoded (contains %40 for @), use standard parsing
    if "%40" in db_url:
        return db_url

    # Check if this looks like a malformed URL due to @ in password
    # Pattern: scheme://user:password@host:port/db where password might contain @
    match = re.match(r"^([^:]+)://([^:@]+):([^@]+)@([^:]+)(?::(\d+))?(?:/(.+))?$", db_url)

    if not match:
        # Standard URL, use as-is
        return db_url

    scheme, user, password_part, host_part, port, path = match.groups()

    # Check if host_part contains @, which indicates password had @ symbol
    if "@" in host_part:
        # Split host_part at the last @ to separate actual host from password remainder
        host_parts = host_part.rsplit("@", 1)
        if len(host_parts) == 2:
            password_remainder, actual_host = host_parts
            full_password = password_part + "@" + password_remainder

            # Reconstruct URL with properly encoded password
            encoded_password = quote(full_password, safe="")
            reconstructed = f"{scheme}://{user}:{encoded_password}@{actual_host}"
            if port:
                reconstructed += f":{port}"
            if path:
                reconstructed += f"/{path}"

            logger.info(
                f"Fixed malformed database URL (password contained @): {db_url} -> {reconstructed}"
            )
            return reconstructed

    # URL appears normal
    return db_url


def get_sqlite_path(db_url: str) -> str | None:
    """
    Extract file path from SQLite URL.
    Returns None if not a file-based SQLite database.
    """
    if not db_url.startswith("sqlite"):
        return None

    if ":memory:" in db_url:
        return None

    # Extract file path from SQLite URL
    # Format: sqlite:///path/to/file.db or sqlite:////absolute/path/to/file.db
    db_path = db_url.replace("sqlite:///", "")

    # Handle absolute paths (four slashes -> starts with /)
    if db_url.startswith("sqlite:////"):
        db_path = "/" + db_path

    # On Windows, convert Unix-style absolute paths to Windows-style
    # /app/data/file.db -> ./data/file.db (relative to current directory)
    if os.name == "nt" and db_path.startswith("/"):
        # Convert Docker-style paths to Windows relative paths
        # Strip leading / and convert /app/data -> ./data
        parts = db_path.lstrip("/").split("/")
        if parts[0] == "app":
            # Docker path: /app/data/file.db -> ./data/file.db
            db_path = "./" + "/".join(parts[1:])
        else:
            # Other Unix paths: /some/path -> ./some/path
            db_path = "./" + "/".join(parts)

    return db_path


def ensure_database_directory():
    """
    Ensure database directory exists with proper permissions.
    Called during app startup to prevent multiprocess race conditions.
    """
    db_url = settings.DATABASE_URL
    db_path = get_sqlite_path(db_url)

    if not db_path:
        return  # Not a file-based SQLite database

    db_dir = os.path.dirname(db_path)
    if not db_dir:
        return  # No directory component

    try:
        # Create directory with full permissions
        Path(db_dir).mkdir(parents=True, exist_ok=True, mode=0o777)

        # Ensure directory is writable (important for Docker)
        if not os.access(db_dir, os.W_OK):
            logger.warning(f"Directory {db_dir} is not writable, attempting to fix permissions")
            try:
                os.chmod(db_dir, 0o777)
            except Exception as chmod_error:
                logger.error(f"Failed to fix directory permissions: {chmod_error}")

        logger.info(f"✓ Database directory ready: {db_dir}")
    except Exception as e:
        logger.error(f"Failed to create database directory {db_dir}: {e}")
        raise


# Initialize database with proper directory handling
def init_database_engine():
    """
    Initialize database engine with proper setup.
    Handles SQLite directory creation and connection parameters.
    Supports PostgreSQL, MongoDB (via SQLAlchemy), and SQLite.
    """
    db_url = settings.DATABASE_URL

    # Intelligently parse database URL to handle passwords with @ symbols
    db_url = parse_database_url_smart(db_url)

    # On Windows, convert Docker-style SQLite paths to Windows-compatible paths
    if os.name == "nt" and db_url.startswith("sqlite:////"):
        db_path = get_sqlite_path(db_url)
        if db_path:
            # Reconstruct the URL with the corrected path
            db_url = f"sqlite:///{db_path}"

    # Parse database URL to check if it's SQLite
    parsed = urlparse(db_url)

    if parsed.scheme == "sqlite":
        # SQLite-specific connection args
        connect_args = {
            "check_same_thread": False,
            "timeout": 60.0,  # Increase timeout for busy databases
        }
    else:
        # PostgreSQL, MySQL, or other databases
        connect_args = {}

    # Create engine with appropriate pool settings
    if parsed.scheme == "sqlite":
        # Use NullPool for SQLite to avoid connection pool issues
        # Each request gets its own connection
        engine = create_engine(
            db_url,
            connect_args=connect_args,
            poolclass=NullPool,  # No connection pooling for SQLite
            echo=False,
        )

        # Enable WAL mode for better concurrency
        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_conn, connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=60000")  # 60 seconds
            cursor.close()

        logger.info("✓ SQLite engine configured with NullPool and WAL mode for better concurrency")
    else:
        # Standard pooling for other databases
        engine = create_engine(
            db_url,
            connect_args=connect_args,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20,
            pool_timeout=60,
            pool_recycle=3600,
            echo=False,
        )

    logger.info(f"✓ Database engine initialized: {parsed.scheme}://{parsed.netloc or 'localhost'}")
    return engine


# Initialize engine
engine = init_database_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
