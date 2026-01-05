from functools import lru_cache

from dotenv import load_dotenv
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load environment variables from .env.local or .env
load_dotenv(dotenv_path=".env.local")
load_dotenv()  # Fallback to .env


class Settings(BaseSettings):
    # AI Model Configuration
    # Single flexible configuration for the active model
    AI_API_KEY: str = ""
    AI_MODEL: str = "gemini-1.5-flash"  # Default model
    AI_PROVIDER: str = "openai"  # gemini, openai, ollama, openrouter, deepseek, kimi

    # Provider-specific base URLs
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OPENAI_BASE_URL: str = (
        "https://api.openai.com/v1"  # Can be changed to OpenRouter, DeepSeek, or Kimi
    )

    # Common OpenAI-compatible providers:
    # - OpenRouter: https://openrouter.ai/api/v1
    # - DeepSeek: https://api.deepseek.com/v1
    # - Kimi (Moonshot): https://api.moonshot.cn/v1
    # For these providers, set AI_PROVIDER=openai and update OPENAI_BASE_URL

    # Database Configuration
    # Default to SQLite in ./data directory (Docker-friendly)
    DATABASE_URL: str = "sqlite:///./data/chat_sessions.db"

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def validate_database_url(cls, v):
        if not v or v.strip() == "":
            return "sqlite:///./data/chat_sessions.db"
        return v

    # API Configuration
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "AERIS-AQ - Air Quality AI Assistant API"
    ENVIRONMENT: str = "development"  # development, production, testing

    # Air Quality Data Sources
    WAQI_API_KEY: str = ""  # World Air Quality Index API key
    AIRQO_API_TOKEN: str = ""  # AirQo Analytics API token

    # Data Source Configuration
    ENABLED_DATA_SOURCES: str = "waqi,airqo,openmeteo,carbon_intensity,defra,uba,nsw"

    # Cache Configuration
    CACHE_TTL_SECONDS: int = 3600

    # AI Response Configuration
    # Temperature: Controls response creativity/randomness (0.0-1.0)
    # - 0.0-0.3: Highly focused, deterministic, best for factual/technical content
    # - 0.4-0.7: Balanced, professional, suitable for general audiences
    # - 0.8-1.0: Creative, varied, better for exploratory discussions
    AI_RESPONSE_TEMPERATURE: float = 0.5

    # Top-p (nucleus sampling): Controls diversity (0.0-1.0)
    # - Lower values (0.7-0.9): More focused, consistent responses
    # - Higher values (0.95-1.0): More diverse vocabulary and phrasing
    AI_RESPONSE_TOP_P: float = 0.9

    # Response Style: Preset configurations for different audiences
    # Options: executive, technical, general, simple, policy
    # - executive: Concise, data-driven, action-oriented for senior leaders
    # - technical: Detailed, precise, includes technical terminology
    # - general: Professional but accessible for all audiences
    # - simple: Clear, straightforward language for public understanding
    # - policy: Formal, evidence-based for government/policy makers
    AI_RESPONSE_STYLE: str = "general"

    # AI Token Limits
    AI_MAX_TOKENS: int = 16384  # Maximum tokens for AI responses - increased for comprehensive outputs

    # Document Processing Limits
    DOCUMENT_MAX_LENGTH_PDF: int = 50000  # Max characters for PDF processing
    DOCUMENT_MAX_LENGTH_CSV: int = 50000  # Max characters for CSV processing
    DOCUMENT_MAX_LENGTH_EXCEL: int = 100000  # Max characters for Excel processing
    DOCUMENT_PREVIEW_ROWS_CSV: int = 200  # Max preview rows for CSV
    DOCUMENT_PREVIEW_ROWS_EXCEL: int = 100  # Max preview rows per Excel sheet

    # Agent Document Limits
    AGENT_MAX_DOC_LENGTH: int = 100000  # Max document content length in agent

    # Redis Configuration
    REDIS_ENABLED: bool = False
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: str = ""

    # CORS Configuration
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173"  # Comma-separated list of allowed origins
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: str = "*"  # Comma-separated list or "*"
    CORS_ALLOW_HEADERS: str = "*"  # Comma-separated list or "*"

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS_ORIGINS string into a list of allowed origins."""
        if self.CORS_ORIGINS == "*":
            return ["*"]
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


@lru_cache
def get_settings():
    return Settings()
