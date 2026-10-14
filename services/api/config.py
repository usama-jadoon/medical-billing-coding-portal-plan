import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    POLICY_SYNC_ENABLED: bool = False
    CMS_POLICY_SYNC_ENABLED: bool = False
    CMS_REFERENCE_DB: str = ''
    TESSERACT_CMD: str = 'tesseract'
    OCR_MAX_PAGES: int = 50
    OCR_MAX_PIXELS: int = 20000000
    OCR_TIMEOUT_SECONDS: int = 60
    POLICY_SYNC_CRON: str = '0 0 * * *'
    POLICY_CACHE_TTL_HOURS: int = 24
    MCA_CODE_API_PROVIDER: str = 'findacode'
    MCA_CODE_API_BASE_URL: str = 'https://api.findacode.com/v1'
    # Explicit normalization adapter endpoints; base URL alone is not a contract.
    MCA_CODE_API_VALIDITY_URL: str = ''
    MCA_CODE_API_CATALOG_URL: str = ''
    MCA_CODE_API_KEY: str = ''
    MCA_CODE_API_SECRET: str = ''
    CMS_COVERAGE_API_BASE_URL: str = 'https://api.coverage.cms.gov'
    DEFAULT_MAC_JURISDICTION: str = 'JH'
    DEFAULT_DME_MAC_JURISDICTION: str = 'JC'
    DEFAULT_STATE_CODE: str = 'TX'
    # CMS accepts numeric contractor/state IDs, not jurisdiction abbreviations.
    CMS_CONTRACTOR_ID: int | None = None
    CMS_STATE_ID: int | None = None
    PAYER_POLICY_FEEDS_JSON: str = '[]'
    APP_NAME: str = "Medical Billing & Coding Portal"
    APP_ENV: str = "development"
    DEBUG: bool = True
    PORT: int = 8000
    SECRET_KEY: str = "insecure-default-secret-key-change-in-production-for-jwt"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    STEP_UP_MAX_AGE_SECONDS: int = 300
    OWNER_TOTP_SECRET: str = ""

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
    OWNER_EMAIL: str = ""
    QUEUE_BACKEND: str = "sync"  # sync for local demo, outbox for durable worker

    # CORS
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
