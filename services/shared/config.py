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

    # Local model configuration (for extraction_provider="local")
    local_model_device: Literal["auto", "cuda", "cpu"] = Field(
        default="auto",
        description="Device for local model inference (auto=GPU if available, else CPU)",
    )
    local_model_precision: Literal["fp32", "fp16"] = Field(
        default="fp32",
        description="Model precision (fp16=half precision, faster but less accurate)",
    )
    local_model_warmup: bool = Field(
        default=True,
        description="Run warmup inference on model load to optimize first request",
    )


def get_settings() -> Settings:
    """Factory function to get settings instance.

    Returns:
        Configured Settings instance
    """
    return Settings()
