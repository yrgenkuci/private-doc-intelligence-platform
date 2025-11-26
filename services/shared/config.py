"""Shared configuration management for the platform.

Based on Pydantic Settings v2 best practices:
https://docs.pydantic.dev/latest/concepts/pydantic_settings/
"""

from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable support.

    All settings can be overridden via environment variables with the prefix 'APP_'.
    Example: APP_LOG_LEVEL=debug
    """

    model_config = SettingsConfigDict(
        env_prefix="APP_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    environment: Literal["development", "staging", "production"] = Field(
        default="development",
        description="Deployment environment",
    )
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO",
        description="Logging level",
    )

    # Service configuration
    service_name: str = Field(
        default="doc-intelligence-platform",
        description="Service identifier for metrics and logs",
    )
    service_version: str = Field(
        default="0.1.0",
        description="Service version",
    )

    # Extraction provider configuration
    extraction_provider: Literal["openai", "local"] = Field(
        default="openai",
        description=(
            "Extraction provider to use (openai for cloud API, local for self-hosted models)"
        ),
    )


def get_settings() -> Settings:
    """Factory function to get settings instance.

    Returns:
        Configured Settings instance
    """
    return Settings()
