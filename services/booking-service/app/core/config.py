from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+asyncpg://bookinguser:bookingpass@localhost/bookingdb"

    # gRPC
    flight_service_url: str = "flight-service:50051"
    grpc_api_key: str = "change-me-secret"

    # Circuit Breaker
    cb_failure_threshold: int = 5
    cb_recovery_timeout: float = 30.0

    # Retry
    retry_max_attempts: int = 3

    # App
    app_title: str = "Booking Service API"
    app_version: str = "1.0.0"
    debug: bool = False


settings = Settings()
