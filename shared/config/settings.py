from functools import lru_cache

from dotenv import load_dotenv
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv(dotenv_path=".env.local")
load_dotenv()


class Settings(BaseSettings):
    # AI Configuration
    AI_API_KEY: str = ""
    AI_MODEL: str = "gemini-1.5-flash"
    AI_PROVIDER: str = "gemini"
    AI_MAX_TOKENS: int = 2048
    AI_RESPONSE_TEMPERATURE: float = 0.3
    AI_RESPONSE_TOP_P: float = 0.9
    AI_RESPONSE_STYLE: str = "general"

    # Provider URLs
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    DASHSCOPE_API_KEY: str = ""

    # Database
    DATABASE_URL: str = "sqlite:///./data/chat_sessions.db"

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def validate_database_url(cls, v):
        return "sqlite:///./data/chat_sessions.db" if not v or not v.strip() else v

    # API Configuration
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "Aeris-AQ - Air Quality AI Assistant API"
    ENVIRONMENT: str = "development"

    # Session Configuration
    MAX_MESSAGES_PER_SESSION: int = 100
    SESSION_LIMIT_WARNING_THRESHOLD: int = 90
    DISABLE_SESSION_LIMIT: bool = True

    # Data Sources
    WAQI_API_KEY: str = ""
    AIRQO_API_TOKEN: str = ""
    ENABLED_DATA_SOURCES: str = "waqi,airqo,openmeteo,carbon_intensity,defra,uba,nsw"

    # Cache
    CACHE_TTL_SECONDS: int = 3600
    CACHE_RESPONSE_TTL_SECONDS: int = 3600

    # Style Presets (per role)
    MAX_TOKENS_EXECUTIVE: int = 1000
    MAX_TOKENS_TECHNICAL: int = 1500
    MAX_TOKENS_GENERAL: int = 1200
    MAX_TOKENS_SIMPLE: int = 800
    MAX_TOKENS_POLICY: int = 1500

    TEMPERATURE_EXECUTIVE: float = 0.3
    TEMPERATURE_TECHNICAL: float = 0.4
    TEMPERATURE_GENERAL: float = 0.5
    TEMPERATURE_SIMPLE: float = 0.6
    TEMPERATURE_POLICY: float = 0.35

    TOP_P_EXECUTIVE: float = 0.85
    TOP_P_TECHNICAL: float = 0.88
    TOP_P_GENERAL: float = 0.9
    TOP_P_SIMPLE: float = 0.92
    TOP_P_POLICY: float = 0.87

    # Image Upload
    SUPPORT_IMAGE_UPLOAD: bool = True
    MAX_IMAGE_SIZE_MB: int = 10
    ALLOWED_IMAGE_FORMATS: str = "jpg,jpeg,png,gif,webp,bmp"
    VISION_CAPABLE_MODELS: str = "gemini:gemini-1.5-flash,gemini:gemini-1.5-pro,gemini:gemini-2.0-flash,openai:gpt-4-vision-preview,openai:gpt-4-turbo,openai:gpt-4o,openai:gpt-4o-mini"

    # Cost Optimization
    ENABLE_COST_OPTIMIZATION: bool = True
    MAX_TOKENS_PER_SESSION: int = 100000

    # Reasoning
    ENABLE_REASONING_DISPLAY: bool = True
    REASONING_STYLE: str = "human"

    # Document Processing
    DOCUMENT_MAX_LENGTH_PDF: int = 50000
    DOCUMENT_MAX_LENGTH_CSV: int = 50000
    DOCUMENT_MAX_LENGTH_EXCEL: int = 100000
    DOCUMENT_PREVIEW_ROWS_CSV: int = 200
    DOCUMENT_PREVIEW_ROWS_EXCEL: int = 100
    AGENT_MAX_DOC_LENGTH: int = 100000

    # Redis
    REDIS_ENABLED: bool = False
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: str = ""

    # CORS
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173"
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: str = "*"
    CORS_ALLOW_HEADERS: str = "*"

    @property
    def cors_origins_list(self) -> list[str]:
        if self.CORS_ORIGINS == "*":
            return ["*"]
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def allowed_hosts_list(self) -> list[str]:
        if self.CORS_ORIGINS == "*":
            return ["*"]
        hosts = []
        for origin in self.CORS_ORIGINS.split(","):
            origin = origin.strip()
            if origin == "*":
                return ["*"]
            if "://" in origin:
                origin = origin.split("://", 1)[1]
            if "/" in origin:
                origin = origin.split("/", 1)[0]
            if ":" in origin:
                origin = origin.split(":", 1)[0]
            if origin and origin not in hosts:
                hosts.append(origin)
        return hosts

    @property
    def vision_capable_models_list(self) -> list[tuple[str, str]]:
        models = []
        for item in self.VISION_CAPABLE_MODELS.split(","):
            if ":" in item.strip():
                provider, model = item.strip().split(":", 1)
                models.append((provider.strip(), model.strip()))
        return models

    def is_vision_capable(self, provider: str, model: str) -> bool:
        return (provider.lower(), model.lower()) in [
            (p.lower(), m.lower()) for p, m in self.vision_capable_models_list
        ]

    @property
    def allowed_image_formats_list(self) -> list[str]:
        return [fmt.strip().lower() for fmt in self.ALLOWED_IMAGE_FORMATS.split(",") if fmt.strip()]

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings():
    return Settings()
