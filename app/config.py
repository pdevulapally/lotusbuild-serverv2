"""The only place environment/secret values are read in this codebase.

Every other module imports `settings` from here — never read `os.environ`
directly elsewhere. New settings are added in the phase that first needs
them (see docs/ARCHITECTURE.md); fields are not pre-added speculatively.
"""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """No field below has a default. A missing environment variable must fail
    startup loudly, not silently fall back to a guessed value.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str
    log_level: str

    redis_url: str

    http_default_timeout_seconds: float
    circuit_breaker_fail_max: int
    circuit_breaker_reset_timeout_seconds: int


settings = Settings()
