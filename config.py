from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class MinScore(str, Enum):
    A = "A"
    B = "B"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Twelve Data
    twelvedata_api_key: str

    # Telegram
    telegram_bot_token: str
    telegram_chat_id: str

    # Scanner
    # Declared as Any so pydantic-settings does NOT try json.loads() on it —
    # for list[str] fields, pydantic-settings v2 attempts JSON decode before our
    # validator runs, breaking the simple PAIRS=EUR_USD,GBP_USD CSV format.
    # The field_validator below converts the raw string to list[str].
    pairs: Any = [
        "EUR_USD",
        "GBP_USD",
        "USD_JPY",
        "USD_CHF",
        "AUD_USD",
        "NZD_USD",
        "USD_CAD",
        "GBP_JPY",
        "EUR_JPY",
    ]
    min_score: MinScore = MinScore.A
    candle_buffer_size: int = Field(default=100, ge=10, le=500)

    @field_validator("pairs", mode="before")
    @classmethod
    def split_pairs(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            return [p.strip() for p in v.split(",") if p.strip()]
        return list(v)


settings = Settings()  # type: ignore[call-arg]
