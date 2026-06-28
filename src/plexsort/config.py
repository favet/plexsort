from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    plex_url: str = Field(default="", alias="PLEX_URL")
    plex_token: str = Field(default="", alias="PLEX_TOKEN")
    plex_library: str = Field(default="Movies", alias="PLEX_LIBRARY")
    database_url: str = Field(
        default="postgresql://plexsort:plexsort@localhost:5432/plexsort",
        alias="DATABASE_URL",
    )
    omdb_api_key: str = Field(default="", alias="OMDB_API_KEY")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()

