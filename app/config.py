"""The only place environment/secret values are read in this codebase.

Every other module imports `settings` from here — never read `os.environ`
directly elsewhere. New settings are added in the phase that first needs
them (see docs/ARCHITECTURE.md); fields are not pre-added speculatively.
"""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"
    log_level: str = "INFO"

    redis_url: str = "redis://localhost:6379/0"

    http_default_timeout_seconds: float = 10.0
    circuit_breaker_fail_max: int = 5
    circuit_breaker_reset_timeout_seconds: int = 30


settings = Settings()
