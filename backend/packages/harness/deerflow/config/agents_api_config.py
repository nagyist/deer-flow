"""Configuration for the custom agents management API."""

from pydantic import BaseModel, ConfigDict, Field


class AgentsApiConfig(BaseModel):
    """Configuration for custom-agent and user-profile management routes."""

    model_config = ConfigDict(frozen=True)

    enabled: bool = Field(
        default=False,
        description=("Whether to expose the custom-agent management API over HTTP. When disabled, the gateway rejects read/write access to custom agent SOUL.md, config, and USER.md prompt-management routes."),
    )
