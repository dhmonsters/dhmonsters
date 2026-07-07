# 애플리케이션 설정을 정의하고 환경변수로부터 읽어옵니다.
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "shorts-growth-agent"
    database_url: str = "sqlite:///./data/shorts_agent.db"
    storage_root: Path = Path("./storage")
    youtube_api_key: str = ""
    ffmpeg_path: str = "ffmpeg"

    model_config = SettingsConfigDict(env_file=".env", env_prefix="SHORTS_")


@lru_cache
def get_settings() -> Settings:
    return Settings()
