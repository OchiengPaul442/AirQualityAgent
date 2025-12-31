import logging
import os
from pathlib import Path
from urllib.parse import urlparse

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from src.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


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
    if os.name == 'nt' and db_path.startswith('/'):
        # Convert Docker-style paths to Windows relative paths
        # Strip leading / and convert /app/data -> ./data
        parts = db_path.lstrip('/').split('/')
        if parts[0] == 'app':
            # Docker path: /app/data/file.db -> ./data/file.db
            db_path = './' + '/'.join(parts[1:])
        else:
            # Other Unix paths: /some/path -> ./some/path
            db_path = './' + '/'.join(parts)
    
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
    
    # On Windows, convert Docker-style SQLite paths to Windows-compatible paths
    if os.name == 'nt' and db_url.startswith("sqlite:////"):
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
            "timeout": 30.0  # Increase timeout for busy databases
        }
    else:
        # PostgreSQL, MySQL, or other databases
        connect_args = {}
    
    # Create engine with conservative pool settings for SQLite
    if parsed.scheme == "sqlite":
        # SQLite doesn't benefit from connection pooling in multiprocess environments
        engine = create_engine(
            db_url,
            connect_args=connect_args,
            pool_pre_ping=True,
            pool_size=1,  # Single connection for SQLite
            max_overflow=0,  # No overflow connections
            echo=False
        )
    else:
        # Standard pooling for other databases
        engine = create_engine(
            db_url,
            connect_args=connect_args,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
            echo=False
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
