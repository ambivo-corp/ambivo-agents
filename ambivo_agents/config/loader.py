# ambivo_agents/config/loader.py
"""
Configuration loader for ambivo_agents.
All configurations must be sourced from agent_config.yaml - no defaults.
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any


class ConfigurationError(Exception):
    """Raised when configuration is missing or invalid."""
    pass


def load_config(config_path: str = None) -> Dict[str, Any]:
    """
    Load configuration from agent_config.yaml.

    Args:
        config_path: Optional path to config file. If None, searches for agent_config.yaml
                    in current directory and parent directories.

    Returns:
        Configuration dictionary

    Raises:
        ConfigurationError: If config file is not found or invalid
    """
    if config_path:
        config_file = Path(config_path)
    else:
        # Search for agent_config.yaml starting from current directory
        config_file = _find_config_file()

    if not config_file or not config_file.exists():
        raise ConfigurationError(
            "agent_config.yaml not found. This file is required for ambivo_agents to function. "
            "Please create agent_config.yaml in your project root or specify the path explicitly."
        )

    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        if not config:
            raise ConfigurationError("agent_config.yaml is empty or contains invalid YAML")

        # Validate required sections
        _validate_config(config)

        return config

    except yaml.YAMLError as e:
        raise ConfigurationError(f"Invalid YAML in agent_config.yaml: {e}")
    except Exception as e:
        raise ConfigurationError(f"Failed to load agent_config.yaml: {e}")


def _find_config_file() -> Path:
    """Find agent_config.yaml in current directory or parent directories."""
    current_dir = Path.cwd()

    # Check current directory first
    config_file = current_dir / "agent_config.yaml"
    if config_file.exists():
        return config_file

    # Check parent directories
    for parent in current_dir.parents:
        config_file = parent / "agent_config.yaml"
        if config_file.exists():
            return config_file

    return None


def _validate_config(config: Dict[str, Any]) -> None:
    """
    Validate that required configuration sections exist.

    Args:
        config: Configuration dictionary

    Raises:
        ConfigurationError: If required sections are missing
    """
    required_sections = ['redis', 'llm']
    missing_sections = []

    for section in required_sections:
        if section not in config:
            missing_sections.append(section)

    if missing_sections:
        raise ConfigurationError(
            f"Required configuration sections missing: {missing_sections}. "
            "Please check your agent_config.yaml file."
        )

    # Validate Redis config
    redis_config = config['redis']
    required_redis_fields = ['host', 'port']
    missing_redis_fields = [field for field in required_redis_fields if field not in redis_config]

    if missing_redis_fields:
        raise ConfigurationError(
            f"Required Redis configuration fields missing: {missing_redis_fields}"
        )

    # Validate LLM config
    llm_config = config['llm']
    has_api_key = any(key in llm_config for key in [
        'openai_api_key', 'anthropic_api_key', 'aws_access_key_id'
    ])

    if not has_api_key:
        raise ConfigurationError(
            "At least one LLM provider API key is required in llm configuration. "
            "Supported providers: openai_api_key, anthropic_api_key, aws_access_key_id"
        )


def get_config_section(section: str, config: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Get a specific configuration section.

    Args:
        section: Section name (e.g., 'redis', 'llm', 'web_scraping')
        config: Optional config dict. If None, loads from file.

    Returns:
        Configuration section dictionary

    Raises:
        ConfigurationError: If section is not found
    """
    if config is None:
        config = load_config()

    if section not in config:
        raise ConfigurationError(f"Configuration section '{section}' not found in agent_config.yaml")

    return config[section]


# Centralized capability and agent type mapping - UPDATED WITH YOUTUBE
CAPABILITY_TO_AGENT_TYPE = {
    'assistant': 'assistant',
    'code_execution': 'code_executor',
    'proxy': 'proxy',
    'web_scraping': 'web_scraper',
    'knowledge_base': 'knowledge_base',
    'web_search': 'web_search',
    'media_editor': 'media_editor',
    'youtube_download': 'youtube_download'  # NEW
}

CONFIG_FLAG_TO_CAPABILITY = {
    'enable_web_scraping': 'web_scraping',
    'enable_knowledge_base': 'knowledge_base',
    'enable_web_search': 'web_search',
    'enable_media_editor': 'media_editor',
    'enable_youtube_download': 'youtube_download',  # NEW
    'enable_code_execution': 'code_execution',
    'enable_proxy_mode': 'proxy'
}


def validate_agent_capabilities(config: Dict[str, Any] = None) -> Dict[str, bool]:
    """
    Validate and return available agent capabilities based on configuration.

    This is the SINGLE SOURCE OF TRUTH for capability checking.

    Args:
        config: Optional config dict. If None, loads from file.

    Returns:
        Dictionary of capability_name -> enabled status
    """
    if config is None:
        config = load_config()

    # Always available capabilities
    capabilities = {
        'assistant': True,  # Always available
        'code_execution': True,  # Always available with Docker
        'proxy': True,  # Always available
    }

    # Get agent_capabilities section
    agent_caps = config.get('agent_capabilities', {})

    # Check optional capabilities based on both flag AND config section existence
    capabilities['web_scraping'] = (
            agent_caps.get('enable_web_scraping', False) and
            'web_scraping' in config
    )

    capabilities['knowledge_base'] = (
            agent_caps.get('enable_knowledge_base', False) and
            'knowledge_base' in config
    )

    capabilities['web_search'] = (
            agent_caps.get('enable_web_search', False) and
            'web_search' in config
    )

    capabilities['media_editor'] = (
            agent_caps.get('enable_media_editor', False) and
            'media_editor' in config
    )

    # YouTube download capability
    capabilities['youtube_download'] = (
            agent_caps.get('enable_youtube_download', False) and
            'youtube_download' in config
    )

    return capabilities


def get_available_agent_types(config: Dict[str, Any] = None) -> Dict[str, bool]:
    """
    Get available agent types based on capabilities.

    This maps capabilities to agent type names consistently.

    Args:
        config: Optional config dict. If None, loads from file.

    Returns:
        Dictionary of agent_type_name -> available status
    """
    try:
        capabilities = validate_agent_capabilities(config)

        # Map capabilities to agent types using centralized mapping
        agent_types = {}
        for capability, agent_type in CAPABILITY_TO_AGENT_TYPE.items():
            agent_types[agent_type] = capabilities.get(capability, False)

        return agent_types

    except Exception as e:
        import logging
        logging.error(f"Error getting available agent types: {e}")
        # Safe fallback
        return {
            'assistant': True,
            'code_executor': True,
            'proxy': True,
            'knowledge_base': False,
            'web_scraper': False,
            'web_search': False,
            'media_editor': False,
            'youtube_download': False
        }


def get_enabled_capabilities(config: Dict[str, Any] = None) -> list[str]:
    """
    Get list of enabled capability names.

    Args:
        config: Optional config dict. If None, loads from file.

    Returns:
        List of enabled capability names
    """
    capabilities = validate_agent_capabilities(config)
    return [cap for cap, enabled in capabilities.items() if enabled]


def get_available_agent_type_names(config: Dict[str, Any] = None) -> list[str]:
    """
    Get list of available agent type names.

    Args:
        config: Optional config dict. If None, loads from file.

    Returns:
        List of available agent type names
    """
    agent_types = get_available_agent_types(config)
    return [agent_type for agent_type, available in agent_types.items() if available]


def capability_to_agent_type(capability: str) -> str:
    """Convert capability name to agent type name."""
    return CAPABILITY_TO_AGENT_TYPE.get(capability, capability)


def agent_type_to_capability(agent_type: str) -> str:
    """Convert agent type name to capability name."""
    reverse_mapping = {v: k for k, v in CAPABILITY_TO_AGENT_TYPE.items()}
    return reverse_mapping.get(agent_type, agent_type)