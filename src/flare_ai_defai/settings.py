"""
Settings Configuration Module

This module defines the configuration settings for the AI Agent API
using Pydantic's BaseSettings. It handles environment variables and
provides default values for various service configurations.

The settings can be overridden by environment variables or through a .env file.
Environment variables take precedence over values defined in the .env file.
"""

import structlog
from pydantic_settings import BaseSettings, SettingsConfigDict
import os

logger = structlog.get_logger(__name__)


class Settings(BaseSettings):
    """
    Application settings model that provides configuration for all components.
    """

    # Flag to enable/disable attestation simulation
    simulate_attestation: bool = False
    # Restrict backend listener to specific IPs
    cors_origins: list[str] = ["*"]
    # API key for accessing Google's Gemini AI service
    gemini_api_key: str = ""
    # The Gemini model identifier to use
    gemini_model: str = "gemini-2.0-pro"
    # API version to use at the backend
    api_version: str = "v1"
    # URL for the Flare Network RPC provider
    web3_provider_url: str = "https://coston2-api.flare.network/ext/C/rpc"
    # URL for the Flare Network block explorer
    web3_explorer_url: str = "https://coston2-explorer.flare.network/"

    # Main Net
    web3_provider_url: str = "https://flare-api.flare.network/ext/C/rpc"
    web3_explorer_url: str = "https://flare-explorer.flare.network/"

    qdrant_url: str = "http://localhost"
    qdrant_port: int = 6333
    qdrant_api_key: str = ""  # Leave this empty for local development without authentication
    flare_private_key: str | None = None

    model_config = SettingsConfigDict(
        # This enables .env file support
        env_file=".env",
        # If .env file is not found, don't raise an error
        env_file_encoding="utf-8",
        # Optional: you can also specify multiple .env files
        extra="ignore",
    )


# Create a global settings instance
settings = Settings()
logger.debug("settings", settings=settings.model_dump())
