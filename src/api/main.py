import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from src.api.error_handlers import register_error_handlers
from src.api.routes import router
from src.config import get_settings
from src.db.database import Base, engine, ensure_database_directory


# Configure logging based on environment
def setup_logging():
    """Configure logging levels based on environment."""
    log_level = logging.INFO if settings.ENVIRONMENT == "production" else logging.DEBUG

    # Configure root logger
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),  # Console output
        ]
    )

    # Set specific log levels for different components
    if settings.ENVIRONMENT == "production":
        # In production, reduce noise from libraries
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)
        logging.getLogger("sqlalchemy").setLevel(logging.WARNING)
        # Only log errors and warnings from providers, not debug info
        logging.getLogger("src.services.providers").setLevel(logging.WARNING)
    else:
        # In development, allow more detailed logging
        logging.getLogger("src.services.providers").setLevel(logging.INFO)

setup_logging()

logger = logging.getLogger(__name__)

settings = get_settings()

# Rate limiting configuration
limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute", "1000/hour"])


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
    lifespan=lifespan,
)

# Add rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# Configure CORS middleware
cors_methods = ["*"] if settings.CORS_ALLOW_METHODS == "*" else [m.strip() for m in settings.CORS_ALLOW_METHODS.split(",")]
cors_headers = ["*"] if settings.CORS_ALLOW_HEADERS == "*" else [h.strip() for h in settings.CORS_ALLOW_HEADERS.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=cors_methods,
    allow_headers=cors_headers,
)

logger.info(f"CORS enabled for origins: {settings.cors_origins_list}")

# Security middleware
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"] if settings.ENVIRONMENT == "development" else settings.cors_origins_list,
)

# Add security headers
@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)

    # Security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

    return response

# Register global error handlers for better error messages
register_error_handlers(app)

app.include_router(router, prefix=settings.API_V1_STR)


@app.get("/health")
async def health_check():
    return {"status": "ok", "version": "1.0.0"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
