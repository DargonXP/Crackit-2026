import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv("DATABASE_URL", "")
    jwt_secret: str = os.getenv("JWT_SECRET", "")
    jwt_refresh_secret: str = os.getenv("JWT_REFRESH_SECRET", "")
    access_token_expire_minutes: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15"))
    refresh_token_expire_days: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))
    cors_origins_raw: str = os.getenv(
        "CORS_ORIGINS", "http://localhost:3000,https://your-frontend.example.com"
    )

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins_raw.split(",") if origin.strip()]


settings = Settings()
