"""Subagent registry for managing available subagents."""

import logging
from dataclasses import replace

from deerflow.config.app_config import AppConfig
from deerflow.sandbox.security import is_host_bash_allowed
from deerflow.subagents.builtins import BUILTIN_SUBAGENTS
from deerflow.subagents.config import SubagentConfig

logger = logging.getLogger(__name__)


def _build_custom_subagent_config(name: str, app_config: AppConfig) -> SubagentConfig | None:
    """Build a SubagentConfig from config.yaml custom_agents section.

    Args:
        name: The name of the custom subagent.
        app_config: The resolved application config.

    Returns:
        SubagentConfig if found in custom_agents, None otherwise.
    """
    custom = app_config.subagents.custom_agents.get(name)
    if custom is None:
        return None

    return SubagentConfig(
        name=name,
        description=custom.description,
        system_prompt=custom.system_prompt,
        tools=custom.tools,
        disallowed_tools=custom.disallowed_tools,
        skills=custom.skills,
        model=custom.model,
        max_turns=custom.max_turns,
        timeout_seconds=custom.timeout_seconds,
    )


def get_subagent_config(name: str, app_config: AppConfig) -> SubagentConfig | None:
    """Get a subagent configuration by name, with config.yaml overrides applied.

    Resolution order (mirrors Codex's config layering):
    1. Built-in subagents (general-purpose, bash)
    2. Custom subagents from config.yaml custom_agents section
    3. Per-agent overrides from config.yaml agents section (timeout, max_turns, model, skills)
    """
    config = BUILTIN_SUBAGENTS.get(name)
    if config is None:
        config = _build_custom_subagent_config(name, app_config)
    if config is None:
        return None

    sub_config = app_config.subagents
    overrides: dict = {}

    # Timeout: subagents config supplies effective per-agent override or global default.
    effective_timeout = sub_config.get_timeout_for(name)
    if effective_timeout != config.timeout_seconds:
        logger.debug("Subagent '%s': timeout overridden (%ss -> %ss)", name, config.timeout_seconds, effective_timeout)
        overrides["timeout_seconds"] = effective_timeout

    # Max turns: subagents config supplies effective per-agent override or global default
    # (falls back to ``config.max_turns`` when no override is configured).
    effective_max_turns = sub_config.get_max_turns_for(name, config.max_turns)
    if effective_max_turns != config.max_turns:
        logger.debug("Subagent '%s': max_turns overridden (%s -> %s)", name, config.max_turns, effective_max_turns)
        overrides["max_turns"] = effective_max_turns

    # Model: per-agent override only (no global default for model)
    effective_model = sub_config.get_model_for(name)
    if effective_model is not None and effective_model != config.model:
        logger.debug("Subagent '%s': model overridden (%s -> %s)", name, config.model, effective_model)
        overrides["model"] = effective_model

    # Skills: per-agent override only (no global default for skills)
    effective_skills = sub_config.get_skills_for(name)
    if effective_skills is not None and effective_skills != config.skills:
        logger.debug("Subagent '%s': skills overridden (%s -> %s)", name, config.skills, effective_skills)
        overrides["skills"] = effective_skills

    if overrides:
        config = replace(config, **overrides)

    return config


def list_subagents(app_config: AppConfig) -> list[SubagentConfig]:
    """List all available subagent configurations (with config.yaml overrides applied).

    Returns:
        List of all registered SubagentConfig instances (built-in + custom).
    """
    configs: list[SubagentConfig] = []
    for name in get_subagent_names(app_config):
        config = get_subagent_config(name, app_config)
        if config is not None:
            configs.append(config)
    return configs


def get_subagent_names(app_config: AppConfig) -> list[str]:
    """Get all available subagent names (built-in + custom).

    Returns:
        List of subagent names.
    """
    names = list(BUILTIN_SUBAGENTS.keys())

    for custom_name in app_config.subagents.custom_agents:
        if custom_name not in names:
            names.append(custom_name)

    return names


def get_available_subagent_names(app_config: AppConfig) -> list[str]:
    """Get subagent names that should be exposed to the active runtime.

    Returns:
        List of subagent names visible to the current sandbox configuration.
    """
    names = get_subagent_names(app_config)
    try:
        host_bash_allowed = is_host_bash_allowed(app_config)
    except Exception:
        logger.debug("Could not determine host bash availability; exposing all subagents")
        return names

    if not host_bash_allowed:
        names = [name for name in names if name != "bash"]
    return names
