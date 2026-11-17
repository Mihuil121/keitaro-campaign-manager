import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    keitaro_url: str = os.getenv("KEITARO_URL", "https://tlgk.host").rstrip("/")
    keitaro_api_key: str = os.getenv("KEITARO_API_KEY", "")
    default_domain: str = os.getenv("KEITARO_DEFAULT_DOMAIN", "")
    default_group: str = os.getenv("KEITARO_DEFAULT_GROUP", "")
    default_source: str = os.getenv("KEITARO_DEFAULT_SOURCE", "")
    # префикс имён кампаний, напр. test_ivanov_
    campaign_prefix: str = os.getenv("CAMPAIGN_PREFIX", "").strip()
    safe_redirect_url: str = os.getenv("SAFE_REDIRECT_URL", "https://google.com")
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./app.db")
    cors_origins: tuple[str, ...] = tuple(
        o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",") if o.strip()
    )

    @property
    def api_base(self) -> str:
        return f"{self.keitaro_url}/admin_api/v1"


settings = Settings()
