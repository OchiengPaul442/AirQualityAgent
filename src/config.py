from functools import lru_cache

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

# Load environment variables from .env.local or .env
load_dotenv(dotenv_path=".env.local")
load_dotenv()  # Fallback to .env


class Settings(BaseSettings):
    # AI Model Configuration
    # Single flexible configuration for the active model
    AI_API_KEY: str = ""
    AI_MODEL: str = "gemini-2.5-flash"  # Default model
    AI_PROVIDER: str = "gemini"  # gemini, openai, ollama, openrouter, deepseek, kimi

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

    # API Configuration
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Air Quality AI Agent API"

    # Air Quality Data Sources
    WAQI_API_KEY: str = ""  # World Air Quality Index API key
    AIRQO_API_TOKEN: str = ""  # AirQo Analytics API token

    # Data Source Configuration
    ENABLED_DATA_SOURCES: str = "waqi,airqo,openmeteo"

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

    # Redis Configuration
    REDIS_ENABLED: bool = False
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: str = ""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache
def get_settings():
    return Settings()
