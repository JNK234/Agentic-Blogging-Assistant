# ABOUTME: Configuration management for MCP server using pydantic-settings
# ABOUTME: Loads settings from environment variables with MCP_ prefix

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal


class MCPServerSettings(BaseSettings):
    """MCP Server configuration settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="MCP_",
        case_sensitive=False,
        extra="ignore"
    )

    # Backend API configuration
    backend_url: str = "http://localhost:8000"

    # Server identity
    server_name: str = "blog-assistant"

    # Logging configuration
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"


# Singleton instance for global access
settings = MCPServerSettings()
