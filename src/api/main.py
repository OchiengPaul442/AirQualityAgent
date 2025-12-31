import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.api.routes import router
from src.config import get_settings
from src.db.database import Base, engine, ensure_database_directory
from src.db.models import ChatMessage, ChatSession  # Import models for SQLAlchemy metadata

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan event handler.
    Handles startup and shutdown events properly.
    """
    # Startup: Create tables only once (not per worker)
    try:
        # Ensure database directory exists with proper permissions
        ensure_database_directory()
        
        # Create tables if they don't exist
        Base.metadata.create_all(bind=engine, checkfirst=True)
        logger.info("✓ Database tables initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        # Don't crash the app, continue with degraded functionality
    
    yield
    
    # Shutdown: Cleanup resources
    logger.info("Shutting down...")


app = FastAPI(
    title=settings.PROJECT_NAME, 
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan
)

app.include_router(router, prefix=settings.API_V1_STR)


@app.get("/health")
async def health_check():
    return {"status": "ok", "version": "1.0.0"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
