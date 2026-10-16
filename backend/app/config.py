"""Centralised, typed application configuration.

Every other module reads configuration through `get_settings()` instead of
touching `os.environ` directly, so the rest of the codebase stays decoupled
from *how* configuration is sourced (env vars today, Secret Manager later).
"""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: Literal["local", "production"] = "local"

    google_cloud_project: str = ""
    firebase_project_id: str = ""

    gemini_model: str = "gemini-2.5-flash"

    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_success_url: str = "http://localhost:3000/dashboard?booking=success"
    stripe_cancel_url: str = "http://localhost:3000/dashboard?booking=cancelled"

    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""
    razorpay_webhook_secret: str = ""
    razorpay_callback_url: str = "http://localhost:3000/dashboard?booking=success"

    gst_currency: str = "INR"

    flight_data_provider: Literal["mock", "aviationstack", "amadeus"] = "mock"
    aviationstack_api_key: str = ""
    amadeus_api_key: str = ""
    amadeus_api_secret: str = ""
    amadeus_environment: Literal["test", "production"] = "test"

    cors_allow_origins: str = "http://localhost:3000"

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.cors_allow_origins.split(",") if o.strip()]

    @property
    def is_local(self) -> bool:
        return self.environment == "local"


@lru_cache
def get_settings() -> Settings:
    return Settings()
