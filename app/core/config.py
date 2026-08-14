from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    APP_NAME: str = "Kentank API"
    VERSION: str = "1.0.0"
    DEBUG: bool = False
    DATABASE_URL: str = "sqlite+aiosqlite:///./kentank.db"
    CORS_ORIGINS: str = "http://localhost:5173,https://kentankclient.vercel.app"
    ADMIN_TOKEN: str = "change-me-in-production"
    SECRET_KEY: str = "change-me-in-production-secret"
    ADMIN_SETUP_TOKEN: str = "change-me-before-first-admin"
    WHATSAPP_NUMBER: str = "254700000000"
    BUSINESS_EMAIL: str = "hello@kentank.co.ke"
    BUSINESS_PHONE: str = "+254 700 000 000"
    BUSINESS_LOCATION: str = "Nairobi, Kenya"
    INITIAL_ADMIN_EMAIL: str = "elijahkimani1293@gmail.com"
    INITIAL_ADMIN_PASSWORD: str = "12345678"
    CLOUDINARY_CLOUD_NAME: str = ""
    CLOUDINARY_API_KEY: str = ""
    CLOUDINARY_API_SECRET: str = ""
    CLOUDINARY_FOLDER: str = "kentank/products"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origins_list(self) -> list[str]:
        return [item.strip() for item in self.CORS_ORIGINS.split(',') if item.strip()]

@lru_cache
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
