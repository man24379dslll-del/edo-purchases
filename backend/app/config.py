import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Строка подключения к Postgres (Supabase или Railway).
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:password@localhost:5432/postgres",
    )
    jwt_secret: str = os.getenv("JWT_SECRET", "change-me-in-production")
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))

    # ВАЖНО: тип поля — обычная строка, а не list[str]. Pydantic Settings
    # для полей типа list/dict пытается распарсить переменную окружения как
    # JSON, а не как строку с запятыми — с "*" или доменом это падает с
    # SettingsError при старте приложения. Поэтому парсим сами через property.
    cors_origins: str = os.getenv("CORS_ORIGINS", "*")

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    # Папка для хранения загруженных файлов (договоры, закупки и т.д.).
    # ВАЖНО на Railway: файловая система контейнера эфемерна — без подключённого
    # Volume файлы пропадут при следующем деплое. См. README, раздел "Файлы".
    upload_dir: str = os.getenv("UPLOAD_DIR", "./uploads")
    max_upload_mb: int = int(os.getenv("MAX_UPLOAD_MB", "20"))


settings = Settings()