import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from slowapi import Limiter
from slowapi.util import get_remote_address

from infrastructure.database.database import Base, engine, ensure_database_directory
from interfaces.rest_api.error_handlers import register_error_handlers
from interfaces.rest_api.routes import router
from shared.config.settings import get_settings


# Configure logging based on environment
def setup_logging():
    """Configure logging levels based on environment."""
    settings = get_settings()  # Get settings inside function
    log_level = logging.WARNING if settings.ENVIRONMENT == "production" else logging.WARNING

    # Configure root logger
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),  # Console output
        ],
    )

    # Set specific log levels for different components
    if settings.ENVIRONMENT == "production":
        # In production, reduce noise from libraries
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)
        logging.getLogger("sqlalchemy").setLevel(logging.WARNING)
        # Only log errors and warnings from providers, not debug info
        logging.getLogger("core.providers").setLevel(logging.WARNING)
    else:
        # In development, also reduce noise from libraries
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)
        logging.getLogger("sqlalchemy").setLevel(logging.WARNING)
        logging.getLogger("openai").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)
        # Only log errors and warnings from providers, not debug info
        logging.getLogger("core.providers").setLevel(logging.WARNING)


setup_logging()

logger = logging.getLogger(__name__)

settings = get_settings()

# Rate limiting configuration
# Global limits: 100 requests per minute, 1000 per hour per IP
# Individual endpoints can override with stricter limits
# Only use Redis if explicitly enabled, otherwise use in-memory storage
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["100/minute", "1000/hour"],
    headers_enabled=True,  # Add rate limit info to response headers
    storage_uri=(
        f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}"
        if settings.REDIS_ENABLED
        else "memory://"
    ),
)


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

# Add rate limiting (commented out due to compatibility issues with Python 3.13)
# app.state.limiter = limiter
# app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
# app.add_middleware(SlowAPIMiddleware)

# Configure CORS middleware
cors_methods = (
    ["*"]
    if settings.CORS_ALLOW_METHODS == "*"
    else [m.strip() for m in settings.CORS_ALLOW_METHODS.split(",")]
)
cors_headers = (
    ["*"]
    if settings.CORS_ALLOW_HEADERS == "*"
    else [h.strip() for h in settings.CORS_ALLOW_HEADERS.split(",")]
)

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
    allowed_hosts=["*"] if settings.ENVIRONMENT == "development" else settings.allowed_hosts_list,
)


# Add security and performance headers
@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)

    # Security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'"
    )
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

    # Performance headers
    response.headers["X-Response-Time"] = str(getattr(request.state, "response_time", 0))

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
