"""Factory for creating extraction providers based on configuration.

Implements Factory Pattern for provider selection with registry pattern for extensibility.

Based on:
- Factory Pattern: https://refactoring.guru/design-patterns/factory-method/python
- Registry Pattern: Python Cookbook 3rd Edition, Recipe 9.22

This allows dynamic provider selection via configuration while maintaining
type safety and enabling easy addition of new providers.
"""

import logging

from services.extraction.base import ExtractionProvider
from services.extraction.local_provider import LocalExtractionProvider
from services.extraction.ollama_provider import OllamaExtractionProvider
from services.extraction.openai_provider import OpenAIExtractionProvider
from services.shared.config import Settings

logger = logging.getLogger(__name__)


class ProviderRegistry:
    """Registry of available extraction providers.

    Maintains a mapping of provider names to their implementation classes.
    Supports runtime registration of new providers.
    """

    _providers: dict[str, type[ExtractionProvider]] = {
        "openai": OpenAIExtractionProvider,
        "local": LocalExtractionProvider,
        "ollama": OllamaExtractionProvider,
    }

    @classmethod
    def register(cls, name: str, provider_class: type[ExtractionProvider]) -> None:
        """Register a new provider.

        Args:
            name: Provider identifier (must match Settings.extraction_provider)
            provider_class: Provider class implementing ExtractionProvider interface
        """
        cls._providers[name] = provider_class
        logger.info(f"Registered extraction provider: {name}")

    @classmethod
    def get_provider_class(cls, name: str) -> type[ExtractionProvider]:
        """Get provider class by name.

        Args:
            name: Provider identifier

        Returns:
            Provider class implementing ExtractionProvider

        Raises:
            ValueError: If provider not found in registry
        """
        if name not in cls._providers:
            available = ", ".join(cls._providers.keys())
            raise ValueError(
                f"Unknown extraction provider: '{name}'. " f"Available providers: {available}"
            )
        return cls._providers[name]

    @classmethod
    def list_providers(cls) -> list[str]:
        """List all registered provider names.

        Returns:
            List of provider names
        """
        return list(cls._providers.keys())


def create_extraction_service(settings: Settings) -> ExtractionProvider:
    """Factory function to create extraction service based on configuration.

    Reads settings.extraction_provider and instantiates the appropriate provider.
    Logs warnings if the provider is not available (e.g., missing API key).

    Args:
        settings: Application settings with extraction_provider field

    Returns:
        Configured extraction provider instance

    Raises:
        ValueError: If configured provider is unknown

    Example:
        >>> settings = Settings(extraction_provider="openai")
        >>> provider = create_extraction_service(settings)
        >>> result = provider.extract_invoice_fields("Invoice text...")
    """
    provider_name = settings.extraction_provider
    provider_class = ProviderRegistry.get_provider_class(provider_name)

    # Instantiate provider
    provider = provider_class(settings)

    # Check availability and log warning if not configured
    if not provider.is_available():
        logger.warning(
            f"Extraction provider '{provider_name}' is not fully available. "
            f"Check configuration (e.g., API keys, model files)."
        )

    logger.info(f"Created extraction provider: {provider_name}")
    return provider
