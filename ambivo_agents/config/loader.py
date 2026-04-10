# ambivo_agents/config/loader.py
"""
Enhanced configuration loader for ambivo_agents.
Supports both YAML file and environment variables for configuration.
YAML file is now OPTIONAL when environment variables are provided.
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)

# Try to import yaml, but make it optional
try:
    import yaml

    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False


class ConfigurationError(Exception):
    """Raised when required configuration is missing, incomplete, or invalid."""

    pass


# Environment variable prefix for all ambivo_agents settings
ENV_PREFIX = "AMBIVO_AGENTS_"

# Environment variable mapping — minimal set for v2.0.0
ENV_VARIABLE_MAPPING = {
    # LLM Configuration
    f"{ENV_PREFIX}LLM_PREFERRED_PROVIDER": ("llm", "preferred_provider"),
    f"{ENV_PREFIX}LLM_TEMPERATURE": ("llm", "temperature"),
    f"{ENV_PREFIX}OPENAI_API_KEY": ("llm", "openai_api_key"),
    f"{ENV_PREFIX}ANTHROPIC_API_KEY": ("llm", "anthropic_api_key"),
    f"{ENV_PREFIX}AWS_ACCESS_KEY_ID": ("llm", "aws_access_key_id"),
    f"{ENV_PREFIX}AWS_SECRET_ACCESS_KEY": ("llm", "aws_secret_access_key"),
    f"{ENV_PREFIX}AWS_REGION": ("llm", "aws_region"),
    # Agent Capabilities
    f"{ENV_PREFIX}ENABLE_KNOWLEDGE_BASE": ("agent_capabilities", "enable_knowledge_base"),
    f"{ENV_PREFIX}ENABLE_WEB_SEARCH": ("agent_capabilities", "enable_web_search"),
    f"{ENV_PREFIX}ENABLE_WEB_SCRAPING": ("agent_capabilities", "enable_web_scraping"),
    # Web Search
    f"{ENV_PREFIX}BRAVE_API_KEY": ("web_search", "brave_api_key"),
    f"{ENV_PREFIX}AVESAPI_API_KEY": ("web_search", "avesapi_api_key"),
    # Web Scraping
    f"{ENV_PREFIX}SCRAPING_PROVIDER": ("web_scraping", "scraping", "provider"),
    f"{ENV_PREFIX}JINA_API_KEY": ("web_scraping", "scraping", "jina_api_key"),
    f"{ENV_PREFIX}FIRECRAWL_API_KEY": ("web_scraping", "scraping", "firecrawl_api_key"),
    f"{ENV_PREFIX}SCRAPING_TIMEOUT": ("web_scraping", "timeout"),
    # Knowledge Base (optional)
    f"{ENV_PREFIX}QDRANT_URL": ("knowledge_base", "qdrant_url"),
    f"{ENV_PREFIX}QDRANT_API_KEY": ("knowledge_base", "qdrant_api_key"),
    # Redis (optional)
    f"{ENV_PREFIX}REDIS_HOST": ("redis", "host"),
    f"{ENV_PREFIX}REDIS_PORT": ("redis", "port"),
    f"{ENV_PREFIX}REDIS_PASSWORD": ("redis", "password"),
    # Service
    f"{ENV_PREFIX}LOG_LEVEL": ("service", "log_level"),
    # Gather Agent Configuration (Natural language parsing and submission)
    f"{ENV_PREFIX}GATHER_ENABLE_NATURAL_LANGUAGE_PARSING": (
        "gather",
        "enable_natural_language_parsing",
    ),
    f"{ENV_PREFIX}GATHER_SUBMISSION_ENDPOINT": ("gather", "submission_endpoint"),
    f"{ENV_PREFIX}GATHER_SUBMISSION_METHOD": ("gather", "submission_method"),
    f"{ENV_PREFIX}GATHER_MEMORY_TTL_SECONDS": ("gather", "memory_ttl_seconds"),
    # Agent Enablement Configuration (New - all used)
    f"{ENV_PREFIX}MODERATOR_ENABLED": ("agents", "moderator", "enabled"),
    f"{ENV_PREFIX}WEB_SCRAPER_ENABLED": ("agents", "web_scraper", "enabled"),
    # File Access Security Configuration (New feature - used)
    f"{ENV_PREFIX}FILE_ACCESS_RESTRICTED_DIRS": (
        "security",
        "file_access",
        "restricted_directories",
    ),
}

# No env vars are strictly required — YAML config or sensible defaults are used
REQUIRED_ENV_VARS = []

# At least one LLM provider is required
LLM_PROVIDER_ENV_VARS = [
    f"{ENV_PREFIX}LLM_OPENAI_API_KEY",
    f"{ENV_PREFIX}OPENAI_API_KEY",
    f"{ENV_PREFIX}LLM_ANTHROPIC_API_KEY",
    f"{ENV_PREFIX}ANTHROPIC_API_KEY",
    f"{ENV_PREFIX}LLM_AWS_ACCESS_KEY_ID",
    f"{ENV_PREFIX}AWS_ACCESS_KEY_ID",
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
            # logging.info("Configuration loaded from environment variables")

            # Validate env config
            _validate_config(config)

            # Add config source metadata
            config["_config_source"] = config_source
            return config

        except ConfigurationError as e:
            if _has_minimal_env_vars():
                # If we have some env vars but they're incomplete, raise error
                raise ConfigurationError(f"Incomplete environment variable configuration: {e}") from e
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

            # logging.info(f"Configuration loaded from {config_source}")

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
    config["_config_source"] = config_source

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

    # Provide defaults for missing required sections
    if not config.get("redis"):
        config["redis"] = {"host": "localhost", "port": 6379, "db": 0, "password": None}
        logger.warning(
            "Redis configuration not found in environment variables. Using defaults: redis://localhost:6379/0"
        )

    if not config.get("llm"):
        config["llm"] = {"preferred_provider": "openai", "temperature": 0.7}
        logger.warning(
            "LLM configuration not found in environment variables. Using defaults (API keys still required)"
        )

    # Note: This allows the system to start with defaults even if API keys aren't set,
    # but the agents will fail gracefully when actually trying to use missing API keys

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

    # Warn if config file is world-readable (contains credentials)
    try:
        file_mode = config_file.stat().st_mode
        if file_mode & 0o004:  # world-readable
            logger.warning(
                f"Config file {config_file} is world-readable (mode {oct(file_mode)}). "
                "This file contains credentials and should be restricted (e.g., chmod 600)."
            )
    except OSError:
        pass

    try:
        with open(config_file, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        if not config:
            raise ConfigurationError("agent_config.yaml is empty or contains invalid YAML")

        # Apply defaults to YAML configuration
        _set_env_config_defaults(config)
        _validate_config(config)
        return config

    except yaml.YAMLError as e:
        raise ConfigurationError(f"Invalid YAML in agent_config.yaml: {e}") from e
    except Exception as e:
        raise ConfigurationError(f"Failed to load agent_config.yaml: {e}") from e


def _get_minimal_defaults() -> Dict[str, Any]:
    """Get minimal default configuration when nothing else is available."""
    return {
        "redis": {"host": "localhost", "port": 6379, "db": 0, "password": None},
        "llm": {"preferred_provider": "openai", "temperature": 0.7},
        "agent_capabilities": {
            "enable_knowledge_base": False,
            "enable_web_search": False,
            "enable_web_scraping": False,
        },
        "service": {
            "log_level": "INFO",
            "max_sessions": 100,
            "session_timeout": 3600,
        },
        "agents": {
            "moderator": {"enabled": True},
            "web_scraper": {"enabled": True},
        },
        "moderator": {"default_enabled_agents": ["assistant"]},
    }


def _set_nested_value(config: Dict[str, Any], path: tuple, value: Any) -> None:
    """Set a nested value in configuration dictionary."""
    current = config

    # Navigate to the parent of the target key
    for key in path[:-1]:
        if key not in current:
            current[key] = {}
        current = current[key]

    final_key = path[-1]

    # Handle special cases for different sections
    if len(path) >= 1:
        # Docker images handling
        if path[0] == "docker" and final_key == "images" and isinstance(value, str):
            current[final_key] = [value]
            return

        # Docker agent subdirs handling (comma-separated lists)
        elif (
            path[0] == "docker"
            and len(path) >= 3
            and path[1] == "agent_subdirs"
            and isinstance(value, str)
        ):
            current[final_key] = [subdir.strip() for subdir in value.split(",")]
            return

        # Workflow file formats handling (comma-separated lists)
        elif path[0] == "workflows" and final_key == "file_formats" and isinstance(value, str):
            current[final_key] = [fmt.strip() for fmt in value.split(",")]
            return

        # Security restricted directories handling (comma-separated lists)
        elif (
            path[0] == "security"
            and len(path) >= 3
            and path[1] == "file_access"
            and final_key == "restricted_directories"
            and isinstance(value, str)
        ):
            current[final_key] = [dir_path.strip() for dir_path in value.split(",")]
            return

        # Moderator enabled agents handling
        elif (
            path[0] == "moderator"
            and final_key == "default_enabled_agents"
            and isinstance(value, str)
        ):
            current[final_key] = [agent.strip() for agent in value.split(",")]
            return

    # Default handling
    current[final_key] = value


def _convert_env_value(value: str) -> Union[str, int, float, bool]:
    """Convert environment variable string to appropriate type."""
    if not value:
        return None

    # Boolean conversion
    if value.lower() in ("true", "yes", "1", "on"):
        return True
    elif value.lower() in ("false", "no", "0", "off"):
        return False

    # Integer conversion
    try:
        if "." not in value and value.lstrip("-").isdigit():
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
    if "redis" in config:
        config["redis"].setdefault("db", 0)

    # Set LLM defaults
    if "llm" in config:
        config["llm"].setdefault("temperature", 0.5)
        config["llm"].setdefault("preferred_provider", "openai")

    # Set agent capabilities defaults
    if "agent_capabilities" in config:
        caps = config["agent_capabilities"]
        caps.setdefault("enable_file_processing", True)
        caps.setdefault("enable_web_ingestion", True)
        caps.setdefault("enable_api_calls", True)

    # Set web search defaults
    if "web_search" in config:
        ws = config["web_search"]
        ws.setdefault("default_max_results", 10)
        ws.setdefault("search_timeout_seconds", 10)
        ws.setdefault("enable_caching", True)
        ws.setdefault("cache_ttl_minutes", 30)

    # Set knowledge base defaults
    if "knowledge_base" in config:
        kb = config["knowledge_base"]
        kb.setdefault("chunk_size", 1024)
        kb.setdefault("chunk_overlap", 20)
        kb.setdefault("similarity_top_k", 5)
        kb.setdefault("vector_size", 1536)
        kb.setdefault("distance_metric", "cosine")
        kb.setdefault("default_collection_prefix", "")
        kb.setdefault("max_file_size_mb", 50)

    # Set web scraping defaults with Docker-accessible directories
    if "web_scraping" in config:
        ws = config["web_scraping"]
        ws.setdefault("timeout", 120)
        ws.setdefault("proxy_enabled", False)
        ws.setdefault("docker_image", "sgosain/amb-ubuntu-python-public-pod")
        ws.setdefault("output_dir", "./scraper_output") # Docker-accessible with shared volume
        ws.setdefault("docker_shared_mode", True) # Enable Docker volume sharing

    # Set agents defaults
    if "agents" not in config:
        config["agents"] = {}

    agents = config["agents"]
    agents.setdefault("moderator", {}).setdefault("enabled", True)
    agents.setdefault("web_scraper", {}).setdefault("enabled", True)

    # Set security defaults - file access restrictions
    if "security" not in config:
        config["security"] = {}

    security = config["security"]
    if "file_access" not in security:
        security["file_access"] = {}

    file_access = security["file_access"]
    # Default restricted directories - common sensitive locations
    file_access.setdefault(
        "restricted_directories",
        [
            "/etc", # System configuration files
            "/root", # Root user home directory
            "/var/log", # System logs
            "/proc", # Process filesystem
            "/sys", # System filesystem
            "/dev", # Device files
            "/boot", # Boot files
            "~/.ssh", # SSH keys
            "~/.aws", # AWS credentials
            "~/.config", # User configuration files
            "/usr/bin", # System binaries
            "/usr/sbin", # System admin binaries
        ],
    )

    # Set Docker defaults
    if "docker" in config:
        docker = config["docker"]
        docker.setdefault("memory_limit", "512m")
        docker.setdefault("timeout", 60)
        docker.setdefault("work_dir", "/opt/ambivo/work_dir")
        if "images" not in docker:
            docker["images"] = ["sgosain/amb-ubuntu-python-public-pod"]

        # Consolidated Docker structure defaults
        docker.setdefault("shared_base_dir", "./docker_shared")
        docker.setdefault(
            "legacy_fallback_dirs", ["docker_shared/input", "docker_shared"]
        ) # Use docker_shared structure consistently
        # Agent subdirs defaults
        if "agent_subdirs" not in docker:
            docker["agent_subdirs"] = {}
        agent_subdirs = docker["agent_subdirs"]
        agent_subdirs.setdefault(
            "analytics",
            ["input/analytics", "output/analytics", "temp/analytics", "handoff/analytics"],
        )
        agent_subdirs.setdefault(
            "media", ["input/media", "output/media", "temp/media", "handoff/media"]
        )
        agent_subdirs.setdefault("code", ["input/code", "output/code", "temp/code", "handoff/code"])
        agent_subdirs.setdefault("database", ["handoff/database"])
        agent_subdirs.setdefault("scraper", ["output/scraper", "temp/scraper", "handoff/scraper"])

    # Set service defaults
    if "service" in config:
        service = config["service"]
        service.setdefault("max_sessions", 100)
        service.setdefault("session_timeout", 3600)
        service.setdefault("log_level", "INFO")
        service.setdefault("log_to_file", False)

    # Add this to the _set_env_config_defaults function

    # Set moderator defaults
    if "moderator" in config:
        mod = config["moderator"]
        if "default_enabled_agents" not in mod:
            # Set default based on what's enabled
            enabled_agents = ["assistant"]
            if config.get("agent_capabilities", {}).get("enable_knowledge_base"):
                enabled_agents.append("knowledge_base")
            if config.get("agent_capabilities", {}).get("enable_web_search"):
                enabled_agents.append("web_search")
            if config.get("agent_capabilities", {}).get("enable_web_scraping"):
                enabled_agents.append("web_scraper")
            mod["default_enabled_agents"] = enabled_agents

        # Set routing defaults
        if "routing" not in mod:
            mod["routing"] = {}
        mod["routing"].setdefault("confidence_threshold", 0.6)
        mod["routing"].setdefault("enable_multi_agent", True)
        mod["routing"].setdefault("fallback_agent", "assistant")
        mod["routing"].setdefault("max_routing_attempts", 3)

    # Set memory management defaults
    config.setdefault(
        "memory_management",
        {
            "compression": {"enabled": True, "algorithm": "lz4", "compression_level": 1},
            "cache": {"enabled": True, "max_size": 1000, "ttl_seconds": 300},
            "backup": {"enabled": True, "interval_minutes": 60, "backup_directory": "./backups"},
        },
    )

    # Set workflow persistence defaults
    if "workflow_persistence" not in config:
        config["workflow_persistence"] = {}

    workflow_persistence = config["workflow_persistence"]
    workflow_persistence.setdefault("backend", "sqlite")

    # SQLite defaults
    if "sqlite" not in workflow_persistence:
        workflow_persistence["sqlite"] = {}
    sqlite_config = workflow_persistence["sqlite"]
    sqlite_config.setdefault("database_path", "./data/workflow_state.db")
    sqlite_config.setdefault("enable_wal", True)
    sqlite_config.setdefault("timeout", 30.0)
    sqlite_config.setdefault("auto_vacuum", True)
    sqlite_config.setdefault("journal_mode", "WAL")

    # Tables defaults
    if "tables" not in sqlite_config:
        sqlite_config["tables"] = {}
    tables = sqlite_config["tables"]
    tables.setdefault("conversations", "workflow_conversations")
    tables.setdefault("steps", "workflow_steps")
    tables.setdefault("checkpoints", "workflow_checkpoints")
    tables.setdefault("sessions", "workflow_sessions")

    # Retention defaults
    if "retention" not in sqlite_config:
        sqlite_config["retention"] = {}
    retention = sqlite_config["retention"]
    retention.setdefault("conversation_ttl", 2592000) # 30 days
    retention.setdefault("checkpoint_ttl", 604800) # 7 days
    retention.setdefault("session_ttl", 86400) # 24 hours
    retention.setdefault("cleanup_interval", 3600) # 1 hour

    # Redis defaults
    if "redis" not in workflow_persistence:
        workflow_persistence["redis"] = {}
    redis_config = workflow_persistence["redis"]
    redis_config.setdefault("host", "localhost")
    redis_config.setdefault("port", 6379)
    redis_config.setdefault("db", 2)
    redis_config.setdefault("password", None)
    redis_config.setdefault("ssl", False)
    redis_config.setdefault("session_ttl", 3600)

    # File storage defaults
    if "file" not in workflow_persistence:
        workflow_persistence["file"] = {}
    file_config = workflow_persistence["file"]
    file_config.setdefault("storage_directory", "./data/workflow_states")
    file_config.setdefault("compression", True)
    file_config.setdefault("encryption", False)
    file_config.setdefault("max_file_size", 10485760) # 10MB

    # General persistence defaults
    if "general" not in workflow_persistence:
        workflow_persistence["general"] = {}
    general_config = workflow_persistence["general"]
    general_config.setdefault("auto_checkpoint", True)
    general_config.setdefault("checkpoint_interval", 30)
    general_config.setdefault("max_checkpoints_per_session", 100)
    general_config.setdefault("enable_compression", True)
    general_config.setdefault("enable_encryption", False)
    general_config.setdefault("encryption_key", None)


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
    required_sections = ["redis", "llm"]
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
    redis_config = config["redis"]
    required_redis_fields = ["host", "port"]
    missing_redis_fields = [field for field in required_redis_fields if field not in redis_config]

    if missing_redis_fields:
        raise ConfigurationError(
            f"Required Redis configuration fields missing: {missing_redis_fields}"
        )

    # Validate LLM config
    llm_config = config["llm"]
    has_api_key = any(
        key in llm_config for key in ["openai_api_key", "anthropic_api_key", "aws_access_key_id"]
    )

    if not has_api_key:
        raise ConfigurationError(
            "At least one LLM provider API key is required in llm configuration. "
            "Supported providers: openai_api_key, anthropic_api_key, aws_access_key_id"
        )


def get_config_section(section: str, config: Dict[str, Any] = None) -> Dict[str, Any]:
    """Get a specific top-level section from the configuration.

    Args:
        section: Name of the configuration section (e.g., ``"llm"``, ``"redis"``).
        config: Pre-loaded config dict. If None, calls ``load_config()``.

    Returns:
        The section dict, or an empty dict if the section does not exist.
    """
    if config is None:
        config = load_config()

    if section not in config:
        # Return empty dict instead of raising error to allow graceful fallback
        logging.warning(f"Configuration section '{section}' not found")
        return {}

    return config[section]


def is_docker_enabled(config: Dict[str, Any] = None) -> bool:
    """Check if Docker execution is enabled.

    Reads ``docker.use_docker`` from config (YAML or ENV).  Defaults to
    ``True`` so existing deployments are unaffected.  Set to ``false`` via
    YAML (``docker.use_docker: false``) or ENV
    (``AMBIVO_AGENTS_DOCKER_USE_DOCKER=false``) to run executors locally.

    This is intended for deployments inside the fat Docker image
    (sgosain/amb-ubuntu-python-public-pod) on platforms like Railway
    where Docker-in-Docker is not available.
    """
    if config is None:
        config = load_config()
    docker_section = config.get("docker", {})
    val = docker_section.get("use_docker", True)
    if isinstance(val, str):
        return val.lower() not in ("false", "0", "no")
    return bool(val)


# Environment variable convenience functions
def print_env_var_template():
    """Print a template of all available ``AMBIVO_AGENTS_`` environment variables to stdout."""
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
    """Get the source that the current configuration was loaded from.

    Returns:
        Source description string (e.g., ``"YAML file"``, ``"environment variables"``).
    """
    try:
        config = load_config()
        return config.get("_config_source", "unknown")
    except Exception as e:
        logging.debug(f"Failed to get current config source: {e}")
        return "none"


# Backward compatibility - keep existing functions
CAPABILITY_TO_AGENT_TYPE = {
    "assistant": "assistant",
    "proxy": "proxy",
    "web_scraping": "web_scraper",
    "knowledge_base": "knowledge_base",
    "web_search": "web_search",
    "gather": "gather_agent",
}

CONFIG_FLAG_TO_CAPABILITY = {
    "enable_web_scraping": "web_scraping",
    "enable_knowledge_base": "knowledge_base",
    "enable_web_search": "web_search",
    "enable_proxy_mode": "proxy",
    "enable_gather": "gather",
}


def validate_agent_capabilities(config: Dict[str, Any] = None) -> Dict[str, bool]:
    """Determine which agent capabilities are enabled based on configuration.

    Checks both the ``agent_capabilities`` flags and whether the corresponding
    configuration sections exist.

    Args:
        config: Pre-loaded config dict. If None, calls ``load_config()``.

    Returns:
        Dict mapping capability names to boolean enabled status.
    """
    if config is None:
        config = load_config()

    capabilities = {
        "assistant": True,
        "moderator": True,
        "proxy": True,
    }

    agent_caps = config.get("agent_capabilities", {})

    capabilities["web_scraping"] = (
        agent_caps.get("enable_web_scraping", False) and "web_scraping" in config
    )
    capabilities["knowledge_base"] = (
        agent_caps.get("enable_knowledge_base", False) and "knowledge_base" in config
    )
    capabilities["web_search"] = (
        agent_caps.get("enable_web_search", False) and "web_search" in config
    )
    capabilities["gather"] = agent_caps.get("enable_gather", False) and "gather" in config

    return capabilities


def get_available_agent_types(config: Dict[str, Any] = None) -> Dict[str, bool]:
    """Get available agent types mapped from capability flags.

    Args:
        config: Pre-loaded config dict. If None, calls ``load_config()``.

    Returns:
        Dict mapping agent type names to boolean availability.
    """
    try:
        capabilities = validate_agent_capabilities(config)
        agent_types = {}
        for capability, agent_type in CAPABILITY_TO_AGENT_TYPE.items():
            agent_types[agent_type] = capabilities.get(capability, False)
        return agent_types
    except Exception as e:
        logging.error(f"Error getting available agent types: {e}")
        return {
            "assistant": True,
            "proxy": True,
            "knowledge_base": False,
            "web_scraper": False,
            "web_search": False,
        }


def get_enabled_capabilities(config: Dict[str, Any] = None) -> List[str]:
    """Get names of all capabilities that are currently enabled.

    Args:
        config: Pre-loaded config dict. If None, calls ``load_config()``.

    Returns:
        List of enabled capability name strings.
    """
    capabilities = validate_agent_capabilities(config)
    return [cap for cap, enabled in capabilities.items() if enabled]


def get_available_agent_type_names(config: Dict[str, Any] = None) -> List[str]:
    """Get names of agent types that are currently available.

    Args:
        config: Pre-loaded config dict. If None, calls ``load_config()``.

    Returns:
        List of available agent type name strings.
    """
    agent_types = get_available_agent_types(config)
    return [agent_type for agent_type, available in agent_types.items() if available]


def capability_to_agent_type(capability: str) -> str:
    """Convert a capability name to its corresponding agent type name.

    Args:
        capability: Capability name (e.g., ``"web_scraping"``).

    Returns:
        Agent type name (e.g., ``"web_scraper"``), or the input unchanged
        if no mapping exists.
    """
    return CAPABILITY_TO_AGENT_TYPE.get(capability, capability)


def agent_type_to_capability(agent_type: str) -> str:
    """Convert an agent type name to its corresponding capability name.

    Args:
        agent_type: Agent type name (e.g., ``"web_scraper"``).

    Returns:
        Capability name (e.g., ``"web_scraping"``), or the input unchanged
        if no mapping exists.
    """
    reverse_mapping = {v: k for k, v in CAPABILITY_TO_AGENT_TYPE.items()}
    return reverse_mapping.get(agent_type, agent_type)


def debug_env_vars():
    """Print all ``AMBIVO_AGENTS_`` environment variables and test config loading.

    Masks sensitive values (keys, passwords, secrets) in the output.
    """
    print(" AMBIVO_AGENTS Environment Variables Debug")
    print("=" * 50)

    env_vars = {k: v for k, v in os.environ.items() if k.startswith("AMBIVO_AGENTS_")}

    if not env_vars:
        print(" No AMBIVO_AGENTS_ environment variables found")
        return

    print(f" Found {len(env_vars)} environment variables:")
    for key, value in sorted(env_vars.items()):
        # Mask sensitive values
        if any(sensitive in key.lower() for sensitive in ["key", "password", "secret"]):
            masked_value = value[:8] + "..." if len(value) > 8 else "***"
            print(f" {key} = {masked_value}")
        else:
            print(f" {key} = {value}")

    print("\n Configuration loading test:")
    try:
        config = load_config()
        print(f" Config loaded successfully from: {config.get('_config_source', 'unknown')}")
        print(f" Sections: {list(config.keys())}")
    except Exception as e:
        print(f" Config loading failed: {e}")


def check_config_health() -> Dict[str, Any]:
    """Check the health of the current configuration."""
    health = {
        "config_loaded": False,
        "config_source": "none",
        "redis_configured": False,
        "llm_configured": False,
        "agents_enabled": [],
        "errors": [],
    }

    try:
        config = load_config()
        health["config_loaded"] = True
        health["config_source"] = config.get("_config_source", "unknown")

        # Check Redis
        redis_config = config.get("redis", {})
        if redis_config.get("host") and redis_config.get("port"):
            health["redis_configured"] = True
        else:
            health["errors"].append("Redis not properly configured")

        # Check LLM
        llm_config = config.get("llm", {})
        if any(
            key in llm_config
            for key in ["openai_api_key", "anthropic_api_key", "aws_access_key_id"]
        ):
            health["llm_configured"] = True
        else:
            health["errors"].append("No LLM provider configured")

        # Check enabled agents
        capabilities = validate_agent_capabilities(config)
        health["agents_enabled"] = [cap for cap, enabled in capabilities.items() if enabled]

    except Exception as e:
        health["errors"].append(f"Configuration error: {e}")

    return health
