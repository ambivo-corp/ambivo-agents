# ambivo_agents/config/loader.py
"""
Enhanced configuration loader for ambivo_agents.
Supports both YAML file and environment variables for configuration.
YAML file is now OPTIONAL when environment variables are provided.
"""

import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Union, List

# Try to import yaml, but make it optional
try:
    import yaml

    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False


class ConfigurationError(Exception):
    """Raised when configuration is missing or invalid."""
    pass


# Environment variable prefix for all ambivo_agents settings
ENV_PREFIX = "AMBIVO_AGENTS_"

# Environment variable mapping for configuration sections
ENV_VARIABLE_MAPPING = {
    # Redis Configuration
    f"{ENV_PREFIX}REDIS_HOST": ("redis", "host"),
    f"{ENV_PREFIX}REDIS_PORT": ("redis", "port"),
    f"{ENV_PREFIX}REDIS_PASSWORD": ("redis", "password"),
    f"{ENV_PREFIX}REDIS_DB": ("redis", "db"),

    # LLM Configuration
    f"{ENV_PREFIX}LLM_PREFERRED_PROVIDER": ("llm", "preferred_provider"),
    f"{ENV_PREFIX}LLM_TEMPERATURE": ("llm", "temperature"),
    f"{ENV_PREFIX}LLM_MAX_TOKENS": ("llm", "max_tokens"),
    f"{ENV_PREFIX}LLM_OPENAI_API_KEY": ("llm", "openai_api_key"),
    f"{ENV_PREFIX}OPENAI_API_KEY": ("llm", "openai_api_key"),  # Alternative
    f"{ENV_PREFIX}LLM_ANTHROPIC_API_KEY": ("llm", "anthropic_api_key"),
    f"{ENV_PREFIX}ANTHROPIC_API_KEY": ("llm", "anthropic_api_key"),  # Alternative
    f"{ENV_PREFIX}LLM_VOYAGE_API_KEY": ("llm", "voyage_api_key"),
    f"{ENV_PREFIX}VOYAGE_API_KEY": ("llm", "voyage_api_key"),  # Alternative
    f"{ENV_PREFIX}LLM_AWS_ACCESS_KEY_ID": ("llm", "aws_access_key_id"),
    f"{ENV_PREFIX}AWS_ACCESS_KEY_ID": ("llm", "aws_access_key_id"),  # Alternative
    f"{ENV_PREFIX}LLM_AWS_SECRET_ACCESS_KEY": ("llm", "aws_secret_access_key"),
    f"{ENV_PREFIX}AWS_SECRET_ACCESS_KEY": ("llm", "aws_secret_access_key"),  # Alternative
    f"{ENV_PREFIX}LLM_AWS_REGION": ("llm", "aws_region"),
    f"{ENV_PREFIX}AWS_REGION": ("llm", "aws_region"),  # Alternative

    # Agent Capabilities
    f"{ENV_PREFIX}AGENT_CAPABILITIES_ENABLE_KNOWLEDGE_BASE": ("agent_capabilities", "enable_knowledge_base"),
    f"{ENV_PREFIX}ENABLE_KNOWLEDGE_BASE": ("agent_capabilities", "enable_knowledge_base"),  # Alternative
    f"{ENV_PREFIX}AGENT_CAPABILITIES_ENABLE_WEB_SEARCH": ("agent_capabilities", "enable_web_search"),
    f"{ENV_PREFIX}ENABLE_WEB_SEARCH": ("agent_capabilities", "enable_web_search"),  # Alternative
    f"{ENV_PREFIX}AGENT_CAPABILITIES_ENABLE_CODE_EXECUTION": ("agent_capabilities", "enable_code_execution"),
    f"{ENV_PREFIX}ENABLE_CODE_EXECUTION": ("agent_capabilities", "enable_code_execution"),  # Alternative
    f"{ENV_PREFIX}AGENT_CAPABILITIES_ENABLE_WEB_SCRAPING": ("agent_capabilities", "enable_web_scraping"),
    f"{ENV_PREFIX}ENABLE_WEB_SCRAPING": ("agent_capabilities", "enable_web_scraping"),  # Alternative
    f"{ENV_PREFIX}AGENT_CAPABILITIES_ENABLE_MEDIA_EDITOR": ("agent_capabilities", "enable_media_editor"),
    f"{ENV_PREFIX}ENABLE_MEDIA_EDITOR": ("agent_capabilities", "enable_media_editor"),  # Alternative
    f"{ENV_PREFIX}AGENT_CAPABILITIES_ENABLE_YOUTUBE_DOWNLOAD": ("agent_capabilities", "enable_youtube_download"),
    f"{ENV_PREFIX}ENABLE_YOUTUBE_DOWNLOAD": ("agent_capabilities", "enable_youtube_download"),  # Alternative
    f"{ENV_PREFIX}AGENT_CAPABILITIES_ENABLE_PROXY_MODE": ("agent_capabilities", "enable_proxy_mode"),
    f"{ENV_PREFIX}ENABLE_PROXY_MODE": ("agent_capabilities", "enable_proxy_mode"),  # Alternative
    f"{ENV_PREFIX}AGENT_CAPABILITIES_ENABLE_FILE_PROCESSING": ("agent_capabilities", "enable_file_processing"),
    f"{ENV_PREFIX}AGENT_CAPABILITIES_ENABLE_WEB_INGESTION": ("agent_capabilities", "enable_web_ingestion"),
    f"{ENV_PREFIX}AGENT_CAPABILITIES_ENABLE_API_CALLS": ("agent_capabilities", "enable_api_calls"),

    # Web Search Configuration
    f"{ENV_PREFIX}WEB_SEARCH_BRAVE_API_KEY": ("web_search", "brave_api_key"),
    f"{ENV_PREFIX}BRAVE_API_KEY": ("web_search", "brave_api_key"),  # Alternative
    f"{ENV_PREFIX}WEB_SEARCH_AVESAPI_API_KEY": ("web_search", "avesapi_api_key"),
    f"{ENV_PREFIX}AVES_API_KEY": ("web_search", "avesapi_api_key"),  # Alternative
    f"{ENV_PREFIX}WEB_SEARCH_DEFAULT_MAX_RESULTS": ("web_search", "default_max_results"),
    f"{ENV_PREFIX}WEB_SEARCH_MAX_RESULTS": ("web_search", "default_max_results"),  # Alternative

    # Knowledge Base Configuration
    f"{ENV_PREFIX}KNOWLEDGE_BASE_QDRANT_URL": ("knowledge_base", "qdrant_url"),
    f"{ENV_PREFIX}QDRANT_URL": ("knowledge_base", "qdrant_url"),  # Alternative
    f"{ENV_PREFIX}KNOWLEDGE_BASE_QDRANT_API_KEY": ("knowledge_base", "qdrant_api_key"),
    f"{ENV_PREFIX}QDRANT_API_KEY": ("knowledge_base", "qdrant_api_key"),  # Alternative
    f"{ENV_PREFIX}KNOWLEDGE_BASE_CHUNK_SIZE": ("knowledge_base", "chunk_size"),
    f"{ENV_PREFIX}KB_CHUNK_SIZE": ("knowledge_base", "chunk_size"),  # Alternative
    f"{ENV_PREFIX}KNOWLEDGE_BASE_SIMILARITY_TOP_K": ("knowledge_base", "similarity_top_k"),
    f"{ENV_PREFIX}KB_SIMILARITY_TOP_K": ("knowledge_base", "similarity_top_k"),  # Alternative
    f"{ENV_PREFIX}DEFAULT_COLLECTION_PREFIX": ("knowledge_base", "default_collection_prefix"),

    # Web Scraping Configuration
    f"{ENV_PREFIX}WEB_SCRAPING_PROXY_CONFIG_HTTP_PROXY": ("web_scraping", "proxy_config", "http_proxy"),
    f"{ENV_PREFIX}SCRAPER_PROXY": ("web_scraping", "proxy_config", "http_proxy"),  # Alternative
    f"{ENV_PREFIX}WEB_SCRAPING_PROXY_ENABLED": ("web_scraping", "proxy_enabled"),
    f"{ENV_PREFIX}SCRAPER_PROXY_ENABLED": ("web_scraping", "proxy_enabled"),  # Alternative
    f"{ENV_PREFIX}WEB_SCRAPING_TIMEOUT": ("web_scraping", "timeout"),
    f"{ENV_PREFIX}SCRAPER_TIMEOUT": ("web_scraping", "timeout"),  # Alternative
    f"{ENV_PREFIX}WEB_SCRAPING_DOCKER_IMAGE": ("web_scraping", "docker_image"),

    # YouTube Download Configuration
    f"{ENV_PREFIX}YOUTUBE_DOWNLOAD_DOWNLOAD_DIR": ("youtube_download", "download_dir"),
    f"{ENV_PREFIX}YOUTUBE_DOWNLOAD_DIR": ("youtube_download", "download_dir"),  # Alternative
    f"{ENV_PREFIX}YOUTUBE_DOWNLOAD_DEFAULT_AUDIO_ONLY": ("youtube_download", "default_audio_only"),
    f"{ENV_PREFIX}YOUTUBE_DEFAULT_AUDIO_ONLY": ("youtube_download", "default_audio_only"),  # Alternative
    f"{ENV_PREFIX}YOUTUBE_DOWNLOAD_TIMEOUT": ("youtube_download", "timeout"),
    f"{ENV_PREFIX}YOUTUBE_TIMEOUT": ("youtube_download", "timeout"),  # Alternative
    f"{ENV_PREFIX}YOUTUBE_DOWNLOAD_DOCKER_IMAGE": ("youtube_download", "docker_image"),

    # Media Editor Configuration
    f"{ENV_PREFIX}MEDIA_EDITOR_INPUT_DIR": ("media_editor", "input_dir"),
    f"{ENV_PREFIX}MEDIA_INPUT_DIR": ("media_editor", "input_dir"),  # Alternative
    f"{ENV_PREFIX}MEDIA_EDITOR_OUTPUT_DIR": ("media_editor", "output_dir"),
    f"{ENV_PREFIX}MEDIA_OUTPUT_DIR": ("media_editor", "output_dir"),  # Alternative
    f"{ENV_PREFIX}MEDIA_EDITOR_TIMEOUT": ("media_editor", "timeout"),
    f"{ENV_PREFIX}MEDIA_TIMEOUT": ("media_editor", "timeout"),  # Alternative
    f"{ENV_PREFIX}MEDIA_EDITOR_DOCKER_IMAGE": ("media_editor", "docker_image"),

    # Docker Configuration
    f"{ENV_PREFIX}DOCKER_MEMORY_LIMIT": ("docker", "memory_limit"),
    f"{ENV_PREFIX}DOCKER_TIMEOUT": ("docker", "timeout"),
    f"{ENV_PREFIX}DOCKER_IMAGES": ("docker", "images"),
    f"{ENV_PREFIX}DOCKER_IMAGE": ("docker", "images"),  # Alternative - will be converted to list
    f"{ENV_PREFIX}DOCKER_WORK_DIR": ("docker", "work_dir"),

    # Service Configuration
    f"{ENV_PREFIX}SERVICE_MAX_SESSIONS": ("service", "max_sessions"),
    f"{ENV_PREFIX}SERVICE_LOG_LEVEL": ("service", "log_level"),
    f"{ENV_PREFIX}SERVICE_SESSION_TIMEOUT": ("service", "session_timeout"),
    f"{ENV_PREFIX}SERVICE_ENABLE_METRICS": ("service", "enable_metrics"),
    f"{ENV_PREFIX}SERVICE_LOG_TO_FILE": ("service", "log_to_file"),

    # Moderator Configuration
    f"{ENV_PREFIX}MODERATOR_DEFAULT_ENABLED_AGENTS": ("moderator", "default_enabled_agents"),
    f"{ENV_PREFIX}MODERATOR_ENABLED_AGENTS": ("moderator", "default_enabled_agents"),  # Alternative
    f"{ENV_PREFIX}MODERATOR_ROUTING_CONFIDENCE_THRESHOLD": ("moderator", "routing", "confidence_threshold"),
    f"{ENV_PREFIX}MODERATOR_CONFIDENCE_THRESHOLD": ("moderator", "routing", "confidence_threshold"),  # Alternative
}

# Required environment variables for minimal configuration
REQUIRED_ENV_VARS = [
    f"{ENV_PREFIX}REDIS_HOST",
    f"{ENV_PREFIX}REDIS_PORT",
]

# At least one LLM provider is required
LLM_PROVIDER_ENV_VARS = [
    f"{ENV_PREFIX}LLM_OPENAI_API_KEY",
    f"{ENV_PREFIX}OPENAI_API_KEY",
    f"{ENV_PREFIX}LLM_ANTHROPIC_API_KEY",
    f"{ENV_PREFIX}ANTHROPIC_API_KEY",
    f"{ENV_PREFIX}LLM_AWS_ACCESS_KEY_ID",
    f"{ENV_PREFIX}AWS_ACCESS_KEY_ID"
]


def load_config(config_path: str = None, use_env_vars: bool = None) -> Dict[str, Any]:
    """
    Load configuration with OPTIONAL YAML file support.

    Priority order:
    1. Environment variables (if detected or use_env_vars=True)
    2. YAML file (if available and no env vars)
    3. Minimal defaults (if nothing else available)

    Args:
        config_path: Optional path to config file
        use_env_vars: Force use of environment variables. If None, auto-detects.

    Returns:
        Configuration dictionary

    Raises:
        ConfigurationError: If no valid configuration found
    """

    config = {}
    config_source = ""

    # Auto-detect if we should use environment variables
    if use_env_vars is None:
        use_env_vars = _has_env_vars()

    if use_env_vars:
        # PRIMARY: Try environment variables first
        try:
            config = _load_config_from_env()
            config_source = "environment variables"
            logging.info("✅ Configuration loaded from environment variables")

            # Validate env config
            _validate_config(config)

            # Add config source metadata
            config['_config_source'] = config_source
            return config

        except ConfigurationError as e:
            if _has_minimal_env_vars():
                # If we have some env vars but they're incomplete, raise error
                raise ConfigurationError(f"Incomplete environment variable configuration: {e}")
            else:
                # Fall back to YAML file
                logging.warning(f"Environment variable config incomplete: {e}")
                use_env_vars = False

    if not use_env_vars:
        # FALLBACK: Try YAML file
        try:
            yaml_config = _load_config_from_yaml(config_path)
            if config:
                # Merge env vars with YAML (env vars take precedence)
                config = _merge_configs(yaml_config, config)
                config_source = "YAML file + environment variables"
            else:
                config = yaml_config
                config_source = "YAML file"

            logging.info(f"✅ Configuration loaded from {config_source}")

        except ConfigurationError as e:
            if config:
                # We have partial env config, use it even if YAML failed
                logging.warning(f"YAML config failed, using environment variables: {e}")
                config_source = "environment variables (partial)"
            else:
                # No config at all - use minimal defaults
                logging.warning(f"Both environment variables and YAML failed: {e}")
                config = _get_minimal_defaults()
                config_source = "minimal defaults"

    if not config:
        raise ConfigurationError(
            "No configuration found. Please either:\n"
            "1. Set environment variables with AMBIVO_AGENTS_ prefix, OR\n"
            "2. Create agent_config.yaml in your project directory\n\n"
            f"Required environment variables: {REQUIRED_ENV_VARS + ['At least one of: ' + str(LLM_PROVIDER_ENV_VARS)]}"
        )

    # Add metadata about config source
    config['_config_source'] = config_source

    return config


def _has_env_vars() -> bool:
    """Check if ANY ambivo agents environment variables are set."""
    return any(os.getenv(env_var) for env_var in ENV_VARIABLE_MAPPING.keys())


def _has_minimal_env_vars() -> bool:
    """Check if minimal required environment variables are set."""
    # Check if we have Redis config
    has_redis = any(os.getenv(var) for var in REQUIRED_ENV_VARS)

    # Check if we have at least one LLM provider
    has_llm = any(os.getenv(var) for var in LLM_PROVIDER_ENV_VARS)

    return has_redis and has_llm


def _load_config_from_env() -> Dict[str, Any]:
    """Load configuration from environment variables."""
    config = {}

    # Process all mapped environment variables
    for env_var, config_path in ENV_VARIABLE_MAPPING.items():
        value = os.getenv(env_var)
        if value is not None:
            _set_nested_value(config, config_path, _convert_env_value(value))

    # Set defaults for sections that exist
    _set_env_config_defaults(config)

    # Validate that we have minimum required configuration
    if not config.get('redis') or not config.get('llm'):
        missing = []
        if not config.get('redis'):
            missing.append('redis')
        if not config.get('llm'):
            missing.append('llm')
        raise ConfigurationError(f"Missing required sections from environment variables: {missing}")

    return config


def _load_config_from_yaml(config_path: str = None) -> Dict[str, Any]:
    """Load configuration from YAML file."""
    if not YAML_AVAILABLE:
        raise ConfigurationError("PyYAML is required to load YAML configuration files")

    if config_path:
        config_file = Path(config_path)
    else:
        config_file = _find_config_file()

    if not config_file or not config_file.exists():
        raise ConfigurationError(
            f"agent_config.yaml not found{' at ' + str(config_path) if config_path else ' in current or parent directories'}. "
            "Either create this file or use environment variables."
        )

    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        if not config:
            raise ConfigurationError("agent_config.yaml is empty or contains invalid YAML")

        _validate_config(config)
        return config

    except yaml.YAMLError as e:
        raise ConfigurationError(f"Invalid YAML in agent_config.yaml: {e}")
    except Exception as e:
        raise ConfigurationError(f"Failed to load agent_config.yaml: {e}")


def _get_minimal_defaults() -> Dict[str, Any]:
    """Get minimal default configuration when nothing else is available."""
    return {
        'redis': {
            'host': 'localhost',
            'port': 6379,
            'db': 0,
            'password': None
        },
        'llm': {
            'preferred_provider': 'openai',
            'temperature': 0.7,
            'max_tokens': 4000
        },
        'agent_capabilities': {
            'enable_knowledge_base': False,
            'enable_web_search': False,
            'enable_code_execution': True,
            'enable_file_processing': False,
            'enable_web_ingestion': False,
            'enable_api_calls': False,
            'enable_web_scraping': False,
            'enable_proxy_mode': True,
            'enable_media_editor': False,
            'enable_youtube_download': False
        },
        'service': {
            'enable_metrics': True,
            'log_level': 'INFO',
            'max_sessions': 100,
            'session_timeout': 3600
        },
        'moderator': {
            'default_enabled_agents': ['assistant']
        },
        'docker': {
            'images': ['sgosain/amb-ubuntu-python-public-pod'],
            'memory_limit': '512m',
            'timeout': 60,
            'work_dir': '/opt/ambivo/work_dir'
        }
    }


def _set_nested_value(config: Dict[str, Any], path: tuple, value: Any) -> None:
    """Set a nested value in configuration dictionary."""
    current = config

    # Navigate to the parent of the target key
    for key in path[:-1]:
        if key not in current:
            current[key] = {}
        current = current[key]

    # Handle special cases
    final_key = path[-1]

    if final_key == "images" and isinstance(value, str):
        # Docker images should be a list
        current[final_key] = [value]
    elif final_key == "default_enabled_agents" and isinstance(value, str):
        # Moderator enabled agents should be a list
        current[final_key] = [agent.strip() for agent in value.split(",")]
    else:
        current[final_key] = value


def _convert_env_value(value: str) -> Union[str, int, float, bool]:
    """Convert environment variable string to appropriate type."""
    if not value:
        return None

    # Boolean conversion
    if value.lower() in ('true', 'yes', '1', 'on'):
        return True
    elif value.lower() in ('false', 'no', '0', 'off'):
        return False

    # Integer conversion
    try:
        if '.' not in value and value.lstrip('-').isdigit():
            return int(value)
    except ValueError:
        pass

    # Float conversion
    try:
        return float(value)
    except ValueError:
        pass

    # String (default)
    return value


def _set_env_config_defaults(config: Dict[str, Any]) -> None:
    """Set default values for configuration sections when using environment variables."""

    # Set Redis defaults
    if 'redis' in config:
        config['redis'].setdefault('db', 0)

    # Set LLM defaults
    if 'llm' in config:
        config['llm'].setdefault('temperature', 0.5)
        config['llm'].setdefault('max_tokens', 4000)
        config['llm'].setdefault('preferred_provider', 'openai')

    # Set agent capabilities defaults
    if 'agent_capabilities' in config:
        caps = config['agent_capabilities']
        caps.setdefault('enable_file_processing', True)
        caps.setdefault('enable_web_ingestion', True)
        caps.setdefault('enable_api_calls', True)
        caps.setdefault('enable_agent_collaboration', True)
        caps.setdefault('enable_result_synthesis', True)
        caps.setdefault('enable_multi_source_validation', True)
        caps.setdefault('max_concurrent_operations', 5)
        caps.setdefault('operation_timeout_seconds', 30)
        caps.setdefault('max_memory_usage_mb', 500)

    # Set web search defaults
    if 'web_search' in config:
        ws = config['web_search']
        ws.setdefault('default_max_results', 10)
        ws.setdefault('search_timeout_seconds', 10)
        ws.setdefault('enable_caching', True)
        ws.setdefault('cache_ttl_minutes', 30)

    # Set knowledge base defaults
    if 'knowledge_base' in config:
        kb = config['knowledge_base']
        kb.setdefault('chunk_size', 1024)
        kb.setdefault('chunk_overlap', 20)
        kb.setdefault('similarity_top_k', 5)
        kb.setdefault('vector_size', 1536)
        kb.setdefault('distance_metric', 'cosine')
        kb.setdefault('default_collection_prefix', '')
        kb.setdefault('max_file_size_mb', 50)

    # Set web scraping defaults
    if 'web_scraping' in config:
        ws = config['web_scraping']
        ws.setdefault('timeout', 120)
        ws.setdefault('proxy_enabled', False)
        ws.setdefault('docker_image', 'sgosain/amb-ubuntu-python-public-pod')

    # Set YouTube download defaults
    if 'youtube_download' in config:
        yt = config['youtube_download']
        yt.setdefault('download_dir', './youtube_downloads')
        yt.setdefault('timeout', 600)
        yt.setdefault('memory_limit', '1g')
        yt.setdefault('default_audio_only', True)
        yt.setdefault('docker_image', 'sgosain/amb-ubuntu-python-public-pod')

    # Set media editor defaults
    if 'media_editor' in config:
        me = config['media_editor']
        me.setdefault('input_dir', './examples/media_input')
        me.setdefault('output_dir', './examples/media_output')
        me.setdefault('timeout', 300)
        me.setdefault('docker_image', 'sgosain/amb-ubuntu-python-public-pod')
        me.setdefault('work_dir', '/opt/ambivo/work_dir')

    # Set Docker defaults
    if 'docker' in config:
        docker = config['docker']
        docker.setdefault('memory_limit', '512m')
        docker.setdefault('timeout', 60)
        docker.setdefault('work_dir', '/opt/ambivo/work_dir')
        if 'images' not in docker:
            docker['images'] = ['sgosain/amb-ubuntu-python-public-pod']

    # Set service defaults
    if 'service' in config:
        service = config['service']
        service.setdefault('max_sessions', 100)
        service.setdefault('session_timeout', 3600)
        service.setdefault('log_level', 'INFO')
        service.setdefault('log_to_file', False)
        service.setdefault('enable_metrics', True)

    # Set moderator defaults
    if 'moderator' in config:
        mod = config['moderator']
        if 'default_enabled_agents' not in mod:
            # Set default based on what's enabled
            enabled_agents = ['assistant']
            if config.get('agent_capabilities', {}).get('enable_knowledge_base'):
                enabled_agents.append('knowledge_base')
            if config.get('agent_capabilities', {}).get('enable_web_search'):
                enabled_agents.append('web_search')
            if config.get('agent_capabilities', {}).get('enable_youtube_download'):
                enabled_agents.append('youtube_download')
            if config.get('agent_capabilities', {}).get('enable_media_editor'):
                enabled_agents.append('media_editor')
            if config.get('agent_capabilities', {}).get('enable_web_scraping'):
                enabled_agents.append('web_scraper')
            mod['default_enabled_agents'] = enabled_agents

        # Set routing defaults
        if 'routing' not in mod:
            mod['routing'] = {}
        mod['routing'].setdefault('confidence_threshold', 0.6)
        mod['routing'].setdefault('enable_multi_agent', True)
        mod['routing'].setdefault('fallback_agent', 'assistant')
        mod['routing'].setdefault('max_routing_attempts', 3)

    # Set memory management defaults
    config.setdefault('memory_management', {
        'compression': {'enabled': True, 'algorithm': 'lz4', 'compression_level': 1},
        'cache': {'enabled': True, 'max_size': 1000, 'ttl_seconds': 300},
        'backup': {'enabled': True, 'interval_minutes': 60, 'backup_directory': './backups'}
    })


def _merge_configs(yaml_config: Dict[str, Any], env_config: Dict[str, Any]) -> Dict[str, Any]:
    """Merge YAML and environment configurations (env takes precedence)."""

    def deep_merge(base: dict, override: dict) -> dict:
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    return deep_merge(yaml_config, env_config)


def _find_config_file() -> Optional[Path]:
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
    """Validate that required configuration sections exist."""
    required_sections = ['redis', 'llm']
    missing_sections = []

    for section in required_sections:
        if section not in config:
            missing_sections.append(section)

    if missing_sections:
        raise ConfigurationError(
            f"Required configuration sections missing: {missing_sections}. "
            "Please check your configuration."
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
    """Get a specific configuration section."""
    if config is None:
        config = load_config()

    if section not in config:
        # Return empty dict instead of raising error to allow graceful fallback
        logging.warning(f"Configuration section '{section}' not found")
        return {}

    return config[section]


# Environment variable convenience functions
def print_env_var_template():
    """Print a template of all available environment variables."""
    print("# Ambivo Agents Environment Variables Template")
    print("# Copy and customize these environment variables as needed")
    print("# All variables use the AMBIVO_AGENTS_ prefix")
    print()

    sections = {}
    for env_var, path in ENV_VARIABLE_MAPPING.items():
        section = path[0]
        if section not in sections:
            sections[section] = []
        sections[section].append(env_var)

    for section, vars in sections.items():
        print(f"# {section.upper()} Configuration")
        for var in sorted(vars):
            print(f"# export {var}=your_value_here")
        print()


def get_current_config_source() -> str:
    """Get the source of the current configuration."""
    try:
        config = load_config()
        return config.get('_config_source', 'unknown')
    except:
        return 'none'


# Backward compatibility - keep existing functions
CAPABILITY_TO_AGENT_TYPE = {
    'assistant': 'assistant',
    'code_execution': 'code_executor',
    'proxy': 'proxy',
    'web_scraping': 'web_scraper',
    'knowledge_base': 'knowledge_base',
    'web_search': 'web_search',
    'media_editor': 'media_editor',
    'youtube_download': 'youtube_download'
}

CONFIG_FLAG_TO_CAPABILITY = {
    'enable_web_scraping': 'web_scraping',
    'enable_knowledge_base': 'knowledge_base',
    'enable_web_search': 'web_search',
    'enable_media_editor': 'media_editor',
    'enable_youtube_download': 'youtube_download',
    'enable_code_execution': 'code_execution',
    'enable_proxy_mode': 'proxy'
}


def validate_agent_capabilities(config: Dict[str, Any] = None) -> Dict[str, bool]:
    """Validate and return available agent capabilities based on configuration."""
    if config is None:
        config = load_config()

    capabilities = {
        'assistant': True,
        'code_execution': True,
        'moderator': True,
        'proxy': True,
    }

    agent_caps = config.get('agent_capabilities', {})

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

    capabilities['youtube_download'] = (
            agent_caps.get('enable_youtube_download', False) and
            'youtube_download' in config
    )

    return capabilities


def get_available_agent_types(config: Dict[str, Any] = None) -> Dict[str, bool]:
    """Get available agent types based on capabilities."""
    try:
        capabilities = validate_agent_capabilities(config)
        agent_types = {}
        for capability, agent_type in CAPABILITY_TO_AGENT_TYPE.items():
            agent_types[agent_type] = capabilities.get(capability, False)
        return agent_types
    except Exception as e:
        logging.error(f"Error getting available agent types: {e}")
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


def get_enabled_capabilities(config: Dict[str, Any] = None) -> List[str]:
    """Get list of enabled capability names."""
    capabilities = validate_agent_capabilities(config)
    return [cap for cap, enabled in capabilities.items() if enabled]


def get_available_agent_type_names(config: Dict[str, Any] = None) -> List[str]:
    """Get list of available agent type names."""
    agent_types = get_available_agent_types(config)
    return [agent_type for agent_type, available in agent_types.items() if available]


def capability_to_agent_type(capability: str) -> str:
    """Convert capability name to agent type name."""
    return CAPABILITY_TO_AGENT_TYPE.get(capability, capability)


def agent_type_to_capability(agent_type: str) -> str:
    """Convert agent type name to capability name."""
    reverse_mapping = {v: k for k, v in CAPABILITY_TO_AGENT_TYPE.items()}
    return reverse_mapping.get(agent_type, agent_type)


def debug_env_vars():
    """Debug function to print all AMBIVO_AGENTS_ environment variables."""
    print("🔍 AMBIVO_AGENTS Environment Variables Debug")
    print("=" * 50)

    env_vars = {k: v for k, v in os.environ.items() if k.startswith('AMBIVO_AGENTS_')}

    if not env_vars:
        print("❌ No AMBIVO_AGENTS_ environment variables found")
        return

    print(f"✅ Found {len(env_vars)} environment variables:")
    for key, value in sorted(env_vars.items()):
        # Mask sensitive values
        if any(sensitive in key.lower() for sensitive in ['key', 'password', 'secret']):
            masked_value = value[:8] + "..." if len(value) > 8 else "***"
            print(f"  {key} = {masked_value}")
        else:
            print(f"  {key} = {value}")

    print("\n🔧 Configuration loading test:")
    try:
        config = load_config()
        print(f"✅ Config loaded successfully from: {config.get('_config_source', 'unknown')}")
        print(f"📊 Sections: {list(config.keys())}")
    except Exception as e:
        print(f"❌ Config loading failed: {e}")


def check_config_health() -> Dict[str, Any]:
    """Check the health of the current configuration."""
    health = {
        'config_loaded': False,
        'config_source': 'none',
        'redis_configured': False,
        'llm_configured': False,
        'agents_enabled': [],
        'errors': []
    }

    try:
        config = load_config()
        health['config_loaded'] = True
        health['config_source'] = config.get('_config_source', 'unknown')

        # Check Redis
        redis_config = config.get('redis', {})
        if redis_config.get('host') and redis_config.get('port'):
            health['redis_configured'] = True
        else:
            health['errors'].append('Redis not properly configured')

        # Check LLM
        llm_config = config.get('llm', {})
        if any(key in llm_config for key in ['openai_api_key', 'anthropic_api_key', 'aws_access_key_id']):
            health['llm_configured'] = True
        else:
            health['errors'].append('No LLM provider configured')

        # Check enabled agents
        capabilities = validate_agent_capabilities(config)
        health['agents_enabled'] = [cap for cap, enabled in capabilities.items() if enabled]

    except Exception as e:
        health['errors'].append(f"Configuration error: {e}")

    return health