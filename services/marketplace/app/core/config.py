from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    database_url: str = "postgresql+asyncpg://marketplace:marketplace@localhost/marketplace"

    # JWT
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 30

    # Rate limiting
    order_rate_limit_minutes: int = 1

    # App
    app_title: str = "Marketplace API"
    app_version: str = "1.0.0"
    debug: bool = False


settings = Settings()
