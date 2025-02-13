from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import AnyUrl, Field, ValidationError, field_validator
from typing import List, Optional
import logging

class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    # Application configuration
    app_env: str = "development"
    port: int = 8000
    log_level: str = "INFO"
    request_timeout: int = 30
    
    # ChromaDB configuration
    chroma_host: str = "chromadb"
    chroma_port: int = 8000
    chroma_collection: str = "conversations"
    chroma_cache_size: int = 1000
    
    # Ollama configuration
    ollama_host: AnyUrl = "http://ollama:11434"
    embedding_model: str = "nomic-embed-text"
    llm_model: str = "deepseek-r1:14b"
    
    # Rate limiting
    max_requests_per_minute: int = 60
    concurrent_streams_limit: int = 10
    
    # CORS
    cors_origins: List[str] = Field(default=["http://localhost:3000", "http://localhost:8000"])
    
    # Security
    api_key: Optional[str] = None
    
    @field_validator("app_env")
    def validate_env(cls, v):
        if v not in {"development", "production", "staging"}:
            raise ValueError("Invalid APP_ENV value")
        return v
    
    @field_validator("log_level")
    def validate_log_level(cls, v):
        v = v.upper()
        if v not in logging._nameToLevel:
            raise ValueError(f"Invalid log level: {v}")
        return v
    
    @field_validator("cors_origins", mode="before")
    def split_cors_origins(cls, v):
        if isinstance(v, str):
            return v.split(",")
        return v
    
    @property
    def is_production(self):
        return self.app_env == "production"

# Singleton settings instance
try:
    settings = AppSettings()
except ValidationError as e:
    raise RuntimeError(f"Invalid environment configuration: {e}") from e

def configure_logging():
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    logging.captureWarnings(True)

# Example usage:
# from core.config import settings
# print(settings.ollama_host) 