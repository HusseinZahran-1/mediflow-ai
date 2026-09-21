from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_NAME: str = "MediFlow AI"
    APP_ENV: Literal["development", "test", "production"] = "development"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"
    DATABASE_URL: str = "postgresql+psycopg2://mediflow_user:change-me@db:5432/mediflow_db"
    JWT_SECRET_KEY: str = Field(default="development-only-change-this-secret-key-32chars")
    ACCESS_TOKEN_MINUTES: int = 30
    REFRESH_TOKEN_DAYS: int = 7
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"
    AUTO_CREATE_TABLES: bool = False
    SEED_ADMIN_EMAIL: str = "admin@mediflow.example.com"
    SEED_ADMIN_PASSWORD: str = "CHANGE_ME_BEFORE_SEEDING"
    SEED_DOCTOR_EMAIL: str = "doctor@mediflow.example.com"
    SEED_DOCTOR_PASSWORD: str = "MediFlowDoctor_2026_ChangeMe"
    HOSPITAL_NAME: str = "MediFlow Academic Hospital"
    AI_MODEL_PATH: str = "../ai/models/triage_pipeline.joblib"

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @model_validator(mode="after")
    def reject_placeholder_production_secrets(self):
        if self.APP_ENV == "production":
            if "change-this" in self.JWT_SECRET_KEY or len(self.JWT_SECRET_KEY) < 32:
                raise ValueError("A strong JWT_SECRET_KEY is required in production")
            if self.SEED_ADMIN_PASSWORD == "CHANGE_ME_BEFORE_SEEDING":
                raise ValueError("SEED_ADMIN_PASSWORD must be set in production")
            if "change-me" in self.DATABASE_URL or "replace-with" in self.DATABASE_URL:
                raise ValueError("A real DATABASE_URL is required in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
