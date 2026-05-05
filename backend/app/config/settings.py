"""
Application configuration using Pydantic Settings.
Loads and validates environment variables from .env file.
"""
from typing import List
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file="../.env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        # Prevent recursion in repr
        arbitrary_types_allowed=True,
    )
    
    # Application Settings
    app_name: str = Field(default="BizClone", alias="APP_NAME")
    app_version: str = Field(default="1.0.0", alias="APP_VERSION")
    environment: str = Field(default="development", alias="ENVIRONMENT")
    debug: bool = Field(default=True, alias="DEBUG")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    
    # Server Configuration
    host: str = Field(default="0.0.0.0", alias="HOST")
    port: int = Field(default=8000, alias="PORT")
    workers: int = Field(default=4, alias="WORKERS")
    
    # Database Configuration
    database_url: str = Field(
        default="postgresql://bizclone_user:bizclone_pass@localhost:5432/bizclone_db",
        alias="DATABASE_URL"
    )
    db_echo: bool = Field(default=False, alias="DB_ECHO")
    db_pool_size: int = Field(default=5, alias="DB_POOL_SIZE")
    db_max_overflow: int = Field(default=10, alias="DB_MAX_OVERFLOW")
    
    # Redis Configuration
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    redis_max_connections: int = Field(default=10, alias="REDIS_MAX_CONNECTIONS")
    
    # Celery Configuration
    celery_broker_url: str = Field(default="redis://localhost:6379/0", alias="CELERY_BROKER_URL")
    celery_result_backend: str = Field(default="redis://localhost:6379/1", alias="CELERY_RESULT_BACKEND")
    
    # OpenAI Configuration (used for entity extraction, RAG)
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL")
    openai_max_tokens: int = Field(default=500, alias="OPENAI_MAX_TOKENS")
    openai_temperature: float = Field(default=0.7, alias="OPENAI_TEMPERATURE")

    # Groq Configuration (low-cost intent classification)
    groq_api_key: str = Field(default="", alias="GROQ_API_KEY")
    groq_model: str = Field(default="llama-3.3-70b-versatile", alias="GROQ_MODEL")
    
    # ElevenLabs Configuration
    elevenlabs_api_key: str = Field(default="", alias="ELEVENLABS_API_KEY")
    elevenlabs_voice_id: str = Field(default="", alias="ELEVENLABS_VOICE_ID")
    use_local_tts: bool = Field(default=False, alias="USE_LOCAL_TTS")
    
    # Whisper Configuration
    whisper_model: str = Field(default="base", alias="WHISPER_MODEL")
    whisper_device: str = Field(default="cpu", alias="WHISPER_DEVICE")
    whisper_language: str = Field(default="en", alias="WHISPER_LANGUAGE")
    
    # ChromaDB Configuration
    chroma_persist_directory: str = Field(default="./data/chroma", alias="CHROMA_PERSIST_DIRECTORY")
    chroma_collection_name: str = Field(default="plumber_knowledge", alias="CHROMA_COLLECTION_NAME")
    
    # Business Configuration
    business_name: str = Field(default="QuickFix Plumbing", alias="BUSINESS_NAME")
    business_phone: str = Field(default="", alias="BUSINESS_PHONE")
    business_email: str = Field(default="", alias="BUSINESS_EMAIL")
    business_hours_start: str = Field(default="08:00", alias="BUSINESS_HOURS_START")
    business_hours_end: str = Field(default="18:00", alias="BUSINESS_HOURS_END")
    business_timezone: str = Field(default="America/New_York", alias="BUSINESS_TIMEZONE")
    
    # Scheduling Configuration
    appointment_duration_minutes: int = Field(default=60, alias="APPOINTMENT_DURATION_MINUTES")
    appointment_buffer_minutes: int = Field(default=15, alias="APPOINTMENT_BUFFER_MINUTES")
    max_daily_appointments: int = Field(default=8, alias="MAX_DAILY_APPOINTMENTS")
    
    # Escalation Configuration
    emergency_email: str = Field(default="", alias="EMERGENCY_EMAIL")
    emergency_phone: str = Field(default="", alias="EMERGENCY_PHONE")
    emergency_keywords: str = Field(default="leak,flooding,burst,emergency,urgent,water everywhere", alias="EMERGENCY_KEYWORDS")
    
    # Google Calendar (optional; leave empty to skip calendar integration)
    google_credentials_file: str = Field(
        default="",
        alias="GOOGLE_CREDENTIALS_FILE"
    )
    google_target_calendar: str = Field(
        default="primary",
        alias="GOOGLE_TARGET_CALENDAR"
    )

    # File Storage
    recordings_dir: str = Field(default="./data/recordings", alias="RECORDINGS_DIR")
    transcripts_dir: str = Field(default="./data/transcripts", alias="TRANSCRIPTS_DIR")
    logs_dir: str = Field(default="./logs", alias="LOGS_DIR")
    
    # Security
    secret_key: str = Field(default="change-this-secret-key", alias="SECRET_KEY")
    api_key_header: str = Field(default="X-API-Key", alias="API_KEY_HEADER")
    allowed_origins: str = Field(default="http://localhost:3000,http://localhost:8000", alias="ALLOWED_ORIGINS")
    
    # Rate Limiting
    rate_limit_per_minute: int = Field(default=60, alias="RATE_LIMIT_PER_MINUTE")
    rate_limit_per_hour: int = Field(default=1000, alias="RATE_LIMIT_PER_HOUR")
    
    # Monitoring
    sentry_dsn: str = Field(default="", alias="SENTRY_DSN")
    enable_metrics: bool = Field(default=True, alias="ENABLE_METRICS")
    
    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        v_upper = v.upper()
        if v_upper not in valid_levels:
            raise ValueError(f"Log level must be one of {valid_levels}")
        return v_upper
    
    def get_emergency_keywords_list(self) -> List[str]:
        """Get emergency keywords as a list."""
        return [kw.strip().lower() for kw in self.emergency_keywords.split(",")]
    
    def get_allowed_origins_list(self) -> List[str]:
        """Get allowed origins as a list."""
        return [origin.strip() for origin in self.allowed_origins.split(",")]

    def __repr__(self) -> str:
        """Custom repr to prevent recursion."""
        return f"<Settings(environment={self.environment}, debug={self.debug})>"


# Global settings instance - use lazy initialization to prevent recursion during import
_settings: Settings | None = None


def get_settings() -> Settings:
    """Get or create the global settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


# For backward compatibility, create a proxy that lazily initializes
class SettingsProxy:
    """Proxy object that lazily initializes settings on first access."""

    def __getattr__(self, name: str):
        return getattr(get_settings(), name)

    def __repr__(self) -> str:
        try:
            return repr(get_settings())
        except:
            return "<Settings(not initialized)>"


settings = SettingsProxy()

