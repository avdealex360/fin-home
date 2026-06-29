from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_user: str = "budget"
    app_password: str = "change-me"
    app_secret: str = "change-me"
    database_url: str = "sqlite:///./data/budget.db"
    telegram_bot_token: str = ""
    telegram_allowed_ids: str = ""
    app_base_url: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
