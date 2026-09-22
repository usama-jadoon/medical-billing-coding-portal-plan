import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    APP_NAME: str = "Medical Billing & Coding Portal"
    APP_ENV: str = "development"
    DEBUG: bool = True
    PORT: int = 8000
    SECRET_KEY: str = "insecure-default-secret-key-change-in-production-for-jwt"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    # Database
    DATABASE_URL: str = Field(
        default="sqlite+aiosqlite:///./medical_coding.db",
        description="SQLAlchemy database connection string"
    )

    # Storage
    STORAGE_PROVIDER: str = "local"  # "local" or "s3"
    LOCAL_STORAGE_PATH: str = "./local_storage"
    S3_ENDPOINT: str = "http://localhost:9000"
    S3_ACCESS_KEY: str = "minioadmin"
    S3_SECRET_KEY: str = "minioadmin"
    S3_BUCKET: str = "medical-documents"
    S3_REGION: str = "us-east-1"

    # AI / LLM
    LLM_PROVIDER: str = "mock"  # "mock", "ollama", "openai"
    LLM_BASE_URL: str = "http://localhost:11434"
    LLM_API_KEY: str = ""
    LLM_MODEL: str = "llama3.2"

    # OCR
    OCR_PROVIDER: str = "local"  # "local", "mock"

    # CORS
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
