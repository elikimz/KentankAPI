from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    APP_NAME: str = "Kentank API"
    VERSION: str = "1.0.0"
    DEBUG: bool = False
    DATABASE_URL: str = "sqlite+aiosqlite:///./kentank.db"
    CORS_ORIGINS: str = "http://localhost:5173"
    ADMIN_TOKEN: str = "change-me-in-production"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origins_list(self) -> list[str]:
        return [item.strip() for item in self.CORS_ORIGINS.split(',') if item.strip()]

@lru_cache
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
