from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+asyncpg://flightuser:flightpass@localhost/flightdb"
    grpc_port: int = 50051
    grpc_api_key: str = "change-me-secret"
    redis_sentinel_hosts: str = "redis-sentinel:26379"  # comma-separated host:port
    redis_sentinel_master: str = "mymaster"
    redis_ttl_seconds: int = 300
    debug: bool = False


settings = Settings()
