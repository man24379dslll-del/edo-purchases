import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Строка подключения к Supabase Postgres.
    # Взять в Supabase: Project Settings → Database → Connection string (URI, режим "Transaction pooler" для Railway).
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:password@localhost:5432/postgres",
    )
    jwt_secret: str = os.getenv("JWT_SECRET", "change-me-in-production")
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))
    cors_origins: list[str] = os.getenv("CORS_ORIGINS", "*").split(",")


settings = Settings()
