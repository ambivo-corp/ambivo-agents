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
    """Raised when configuration is missing or invalid."""

    pass


# Environment variable prefix for all ambivo_agents settings
ENV_PREFIX = "AMBIVO_AGENTS_"

# Environment variable mapping for configuration sections
# Environment variable mapping for configuration sections
# Only includes variables that are actually used in the codebase
ENV_VARIABLE_MAPPING = {
    # Redis Configuration (Core - all used)
    f"{ENV_PREFIX}REDIS_HOST": ("redis", "host"),
    f"{ENV_PREFIX}REDIS_PORT": ("redis", "port"),
    f"{ENV_PREFIX}REDIS_PASSWORD": ("redis", "password"),
    f"{ENV_PREFIX}REDIS_DB": ("redis", "db"),
    # LLM Configuration (Core - all used)
    f"{ENV_PREFIX}LLM_PREFERRED_PROVIDER": ("llm", "preferred_provider"),
    f"{ENV_PREFIX}LLM_TEMPERATURE": ("llm", "temperature"),
    f"{ENV_PREFIX}LLM_OPENAI_API_KEY": ("llm", "openai_api_key"),
    f"{ENV_PREFIX}LLM_ANTHROPIC_API_KEY": ("llm", "anthropic_api_key"),
    f"{ENV_PREFIX}LLM_VOYAGE_API_KEY": ("llm", "voyage_api_key"),
    f"{ENV_PREFIX}LLM_AWS_ACCESS_KEY_ID": ("llm", "aws_access_key_id"),
    f"{ENV_PREFIX}LLM_AWS_SECRET_ACCESS_KEY": ("llm", "aws_secret_access_key"),
    f"{ENV_PREFIX}LLM_AWS_REGION": ("llm", "aws_region"),
    # Agent Capabilities (Used by ModeratorAgent)
    f"{ENV_PREFIX}AGENT_CAPABILITIES_ENABLE_KNOWLEDGE_BASE": (
        "agent_capabilities",
        "enable_knowledge_base",
    ),
    f"{ENV_PREFIX}AGENT_CAPABILITIES_ENABLE_WEB_SEARCH": (
        "agent_capabilities",
        "enable_web_search",
    ),
    f"{ENV_PREFIX}AGENT_CAPABILITIES_ENABLE_CODE_EXECUTION": (
        "agent_capabilities",
        "enable_code_execution",
    ),
    f"{ENV_PREFIX}AGENT_CAPABILITIES_ENABLE_FILE_PROCESSING": (
        "agent_capabilities",
        "enable_file_processing",
    ),
    f"{ENV_PREFIX}AGENT_CAPABILITIES_ENABLE_WEB_INGESTION": (
        "agent_capabilities",
        "enable_web_ingestion",
    ),
    f"{ENV_PREFIX}AGENT_CAPABILITIES_ENABLE_API_CALLS": ("agent_capabilities", "enable_api_calls"),
    f"{ENV_PREFIX}AGENT_CAPABILITIES_ENABLE_WEB_SCRAPING": (
        "agent_capabilities",
        "enable_web_scraping",
    ),
    f"{ENV_PREFIX}AGENT_CAPABILITIES_ENABLE_PROXY_MODE": (
        "agent_capabilities",
        "enable_proxy_mode",
    ),
    f"{ENV_PREFIX}AGENT_CAPABILITIES_ENABLE_MEDIA_EDITOR": (
        "agent_capabilities",
        "enable_media_editor",
    ),
    f"{ENV_PREFIX}AGENT_CAPABILITIES_ENABLE_YOUTUBE_DOWNLOAD": (
        "agent_capabilities",
        "enable_youtube_download",
    ),
    f"{ENV_PREFIX}AGENT_CAPABILITIES_ENABLE_API_AGENT": ("agent_capabilities", "enable_api_agent"),
    f"{ENV_PREFIX}AGENT_CAPABILITIES_ENABLE_ANALYTICS": ("agent_capabilities", "enable_analytics"),
    f"{ENV_PREFIX}AGENT_CAPABILITIES_ENABLE_DATABASE_AGENT": (
        "agent_capabilities",
        "enable_database_agent",
    ),
    # Web Search Configuration (Only API keys used)
    f"{ENV_PREFIX}WEB_SEARCH_BRAVE_API_KEY": ("web_search", "brave_api_key"),
    f"{ENV_PREFIX}WEB_SEARCH_AVESAPI_API_KEY": ("web_search", "avesapi_api_key"),
    # Knowledge Base Configuration (Core settings only)
    f"{ENV_PREFIX}KNOWLEDGE_BASE_QDRANT_URL": ("knowledge_base", "qdrant_url"),
    f"{ENV_PREFIX}KNOWLEDGE_BASE_QDRANT_API_KEY": ("knowledge_base", "qdrant_api_key"),
    f"{ENV_PREFIX}KNOWLEDGE_BASE_CHUNK_SIZE": ("knowledge_base", "chunk_size"),
    f"{ENV_PREFIX}KNOWLEDGE_BASE_CHUNK_OVERLAP": ("knowledge_base", "chunk_overlap"),
    f"{ENV_PREFIX}KNOWLEDGE_BASE_SIMILARITY_TOP_K": ("knowledge_base", "similarity_top_k"),
    f"{ENV_PREFIX}KNOWLEDGE_BASE_VECTOR_SIZE": ("knowledge_base", "vector_size"),
    f"{ENV_PREFIX}KNOWLEDGE_BASE_DISTANCE_METRIC": ("knowledge_base", "distance_metric"),
    f"{ENV_PREFIX}KNOWLEDGE_BASE_DEFAULT_COLLECTION_PREFIX": (
        "knowledge_base",
        "default_collection_prefix",
    ),
    # YouTube Download Configuration (Used settings only)
    f"{ENV_PREFIX}YOUTUBE_DOWNLOAD_DOWNLOAD_DIR": ("youtube_download", "download_dir"),
    f"{ENV_PREFIX}YOUTUBE_DOWNLOAD_DEFAULT_AUDIO_ONLY": ("youtube_download", "default_audio_only"),
    f"{ENV_PREFIX}YOUTUBE_DOWNLOAD_TIMEOUT": ("youtube_download", "timeout"),
    f"{ENV_PREFIX}YOUTUBE_DOWNLOAD_DOCKER_IMAGE": ("youtube_download", "docker_image"),
    f"{ENV_PREFIX}YOUTUBE_DOWNLOAD_MEMORY_LIMIT": ("youtube_download", "memory_limit"),
    # Media Editor Configuration (Basic settings only)
    f"{ENV_PREFIX}MEDIA_EDITOR_INPUT_DIR": ("media_editor", "input_dir"),
    f"{ENV_PREFIX}MEDIA_EDITOR_OUTPUT_DIR": ("media_editor", "output_dir"),
    f"{ENV_PREFIX}MEDIA_EDITOR_TIMEOUT": ("media_editor", "timeout"),
    f"{ENV_PREFIX}MEDIA_EDITOR_DOCKER_IMAGE": ("media_editor", "docker_image"),
    f"{ENV_PREFIX}MEDIA_EDITOR_MEMORY_LIMIT": ("media_editor", "memory_limit"),
    f"{ENV_PREFIX}MEDIA_EDITOR_MAX_FILE_SIZE_GB": ("media_editor", "max_file_size_gb"),
    f"{ENV_PREFIX}MEDIA_EDITOR_MAX_CONCURRENT_JOBS": ("media_editor", "max_concurrent_jobs"),
    # Code Executor Configuration (Basic settings only)
    f"{ENV_PREFIX}CODE_EXECUTOR_DOCKER_IMAGE": ("code_executor", "docker_image"),
    f"{ENV_PREFIX}CODE_EXECUTOR_TIMEOUT": ("code_executor", "timeout"),
    f"{ENV_PREFIX}CODE_EXECUTOR_MEMORY_LIMIT": ("code_executor", "memory_limit"),
    f"{ENV_PREFIX}CODE_EXECUTOR_SANDBOX_MODE": ("code_executor", "sandbox_mode"),
    f"{ENV_PREFIX}CODE_EXECUTOR_ALLOW_NETWORK": ("code_executor", "allow_network"),
    # Analytics Configuration (Basic settings only)
    f"{ENV_PREFIX}ANALYTICS_DOCKER_IMAGE": ("analytics", "docker_image"),
    f"{ENV_PREFIX}ANALYTICS_TIMEOUT": ("analytics", "timeout"),
    f"{ENV_PREFIX}ANALYTICS_MEMORY_LIMIT": ("analytics", "memory_limit"),
    # API Agent Configuration (Security settings used)
    f"{ENV_PREFIX}API_AGENT_ALLOWED_DOMAINS": ("api_agent", "allowed_domains"),
    f"{ENV_PREFIX}API_AGENT_BLOCKED_DOMAINS": ("api_agent", "blocked_domains"),
    f"{ENV_PREFIX}API_AGENT_ALLOWED_METHODS": ("api_agent", "allowed_methods"),
    f"{ENV_PREFIX}API_AGENT_VERIFY_SSL": ("api_agent", "verify_ssl"),
    f"{ENV_PREFIX}API_AGENT_TIMEOUT_SECONDS": ("api_agent", "timeout_seconds"),
    f"{ENV_PREFIX}API_AGENT_MAX_SAFE_TIMEOUT": ("api_agent", "max_safe_timeout"),
    f"{ENV_PREFIX}API_AGENT_FORCE_DOCKER_ABOVE_TIMEOUT": (
        "api_agent",
        "force_docker_above_timeout",
    ),
    f"{ENV_PREFIX}API_AGENT_DOCKER_IMAGE": ("api_agent", "docker_image"),
    # Web Scraping Configuration (Basic Docker/proxy settings)
    f"{ENV_PREFIX}WEB_SCRAPING_DOCKER_IMAGE": ("web_scraping", "docker_image"),
    f"{ENV_PREFIX}WEB_SCRAPING_PROXY_ENABLED": ("web_scraping", "proxy_enabled"),
    f"{ENV_PREFIX}WEB_SCRAPING_TIMEOUT": ("web_scraping", "timeout"),
    f"{ENV_PREFIX}WEB_SCRAPING_DOCKER_MEMORY_LIMIT": ("web_scraping", "docker_memory_limit"),
    f"{ENV_PREFIX}WEB_SCRAPING_PROXY_HTTP": ("web_scraping", "proxy_config", "http_proxy"),
    # Database Agent Configuration (Basic settings only)
    f"{ENV_PREFIX}DATABASE_AGENT_STRICT_MODE": ("database_agent", "strict_mode"),
    f"{ENV_PREFIX}DATABASE_AGENT_MAX_RESULT_ROWS": ("database_agent", "max_result_rows"),
    f"{ENV_PREFIX}DATABASE_AGENT_QUERY_TIMEOUT": ("database_agent", "query_timeout"),
    f"{ENV_PREFIX}DATABASE_AGENT_LOCAL_EXPORT_DIR": ("database_agent", "local_export_dir"),
    f"{ENV_PREFIX}DATABASE_AGENT_ENABLE_ANALYTICS_HANDOFF": (
        "database_agent",
        "enable_analytics_handoff",
    ),
    f"{ENV_PREFIX}DATABASE_AGENT_AUTO_COPY_TO_SHARED": ("database_agent", "auto_copy_to_shared"),
    f"{ENV_PREFIX}DATABASE_AGENT_SUPPORTED_TYPES": ("database_agent", "supported_types"),
    # Docker Configuration (Core infrastructure)
    f"{ENV_PREFIX}DOCKER_IMAGES": ("docker", "images"),
    f"{ENV_PREFIX}DOCKER_MEMORY_LIMIT": ("docker", "memory_limit"),
    f"{ENV_PREFIX}DOCKER_TIMEOUT": ("docker", "timeout"),
    f"{ENV_PREFIX}DOCKER_WORK_DIR": ("docker", "work_dir"),
    f"{ENV_PREFIX}DOCKER_SHARED_BASE_DIR": ("docker", "shared_base_dir"),
    f"{ENV_PREFIX}DOCKER_LEGACY_FALLBACK_DIRS": ("docker", "legacy_fallback_dirs"),
    # Agent Subdirs Configuration (For consistent file resolution)
    f"{ENV_PREFIX}DOCKER_AGENT_SUBDIRS_ANALYTICS": ("docker", "agent_subdirs", "analytics"),
    f"{ENV_PREFIX}DOCKER_AGENT_SUBDIRS_MEDIA": ("docker", "agent_subdirs", "media"),
    f"{ENV_PREFIX}DOCKER_AGENT_SUBDIRS_CODE": ("docker", "agent_subdirs", "code"),
    f"{ENV_PREFIX}DOCKER_AGENT_SUBDIRS_DATABASE": ("docker", "agent_subdirs", "database"),
    f"{ENV_PREFIX}DOCKER_AGENT_SUBDIRS_SCRAPER": ("docker", "agent_subdirs", "scraper"),
    # Service Configuration (All used)
    f"{ENV_PREFIX}SERVICE_LOG_LEVEL": ("service", "log_level"),
    f"{ENV_PREFIX}SERVICE_MAX_SESSIONS": ("service", "max_sessions"),
    f"{ENV_PREFIX}SERVICE_SESSION_TIMEOUT": ("service", "session_timeout"),
    f"{ENV_PREFIX}SERVICE_LOG_TO_FILE": ("service", "log_to_file"),
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
    f"{ENV_PREFIX}ANALYTICS_ENABLED": ("agents", "analytics", "enabled"),
    f"{ENV_PREFIX}CODE_EXECUTOR_ENABLED": ("agents", "code_executor", "enabled"),
    f"{ENV_PREFIX}YOUTUBE_DOWNLOAD_ENABLED": ("agents", "youtube_download", "enabled"),
    f"{ENV_PREFIX}MEDIA_EDITOR_ENABLED": ("agents", "media_editor", "enabled"),
    f"{ENV_PREFIX}WEB_SCRAPER_ENABLED": ("agents", "web_scraper", "enabled"),
    # File Access Security Configuration (New feature - used)
    f"{ENV_PREFIX}FILE_ACCESS_RESTRICTED_DIRS": (
        "security",
        "file_access",
        "restricted_directories",
    ),
    # Workflow Persistence Configuration (New feature)
    f"{ENV_PREFIX}WORKFLOW_PERSISTENCE_BACKEND": ("workflow_persistence", "backend"),
    f"{ENV_PREFIX}WORKFLOW_PERSISTENCE_SQLITE_DATABASE_PATH": (
        "workflow_persistence",
        "sqlite",
        "database_path",
    ),
    f"{ENV_PREFIX}WORKFLOW_PERSISTENCE_SQLITE_ENABLE_WAL": (
        "workflow_persistence",
        "sqlite",
        "enable_wal",
    ),
    f"{ENV_PREFIX}WORKFLOW_PERSISTENCE_SQLITE_TIMEOUT": (
        "workflow_persistence",
        "sqlite",
        "timeout",
    ),
    f"{ENV_PREFIX}WORKFLOW_PERSISTENCE_SQLITE_AUTO_VACUUM": (
        "workflow_persistence",
        "sqlite",
        "auto_vacuum",
    ),
    f"{ENV_PREFIX}WORKFLOW_PERSISTENCE_SQLITE_JOURNAL_MODE": (
        "workflow_persistence",
        "sqlite",
        "journal_mode",
    ),
    f"{ENV_PREFIX}WORKFLOW_PERSISTENCE_GENERAL_AUTO_CHECKPOINT": (
        "workflow_persistence",
        "general",
        "auto_checkpoint",
    ),
    f"{ENV_PREFIX}WORKFLOW_PERSISTENCE_GENERAL_CHECKPOINT_INTERVAL": (
        "workflow_persistence",
        "general",
        "checkpoint_interval",
    ),
    f"{ENV_PREFIX}WORKFLOW_PERSISTENCE_GENERAL_MAX_CHECKPOINTS_PER_SESSION": (
        "workflow_persistence",
        "general",
        "max_checkpoints_per_session",
    ),
    f"{ENV_PREFIX}WORKFLOW_PERSISTENCE_GENERAL_ENABLE_COMPRESSION": (
        "workflow_persistence",
        "general",
        "enable_compression",
    ),
    f"{ENV_PREFIX}WORKFLOW_PERSISTENCE_GENERAL_ENABLE_ENCRYPTION": (
        "workflow_persistence",
        "general",
        "enable_encryption",
    ),
    f"{ENV_PREFIX}WORKFLOW_PERSISTENCE_REDIS_HOST": ("workflow_persistence", "redis", "host"),
    f"{ENV_PREFIX}WORKFLOW_PERSISTENCE_REDIS_PORT": ("workflow_persistence", "redis", "port"),
    f"{ENV_PREFIX}WORKFLOW_PERSISTENCE_REDIS_DB": ("workflow_persistence", "redis", "db"),
    f"{ENV_PREFIX}WORKFLOW_PERSISTENCE_REDIS_SESSION_TTL": (
        "workflow_persistence",
        "redis",
        "session_ttl",
    ),
    f"{ENV_PREFIX}WORKFLOW_PERSISTENCE_FILE_STORAGE_DIRECTORY": (
        "workflow_persistence",
        "file",
        "storage_directory",
    ),
    f"{ENV_PREFIX}WORKFLOW_PERSISTENCE_FILE_COMPRESSION": (
        "workflow_persistence",
        "file",
        "compression",
    ),
    f"{ENV_PREFIX}WORKFLOW_PERSISTENCE_FILE_ENCRYPTION": (
        "workflow_persistence",
        "file",
        "encryption",
    ),
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
            # logging.info("✅ Configuration loaded from environment variables")

            # Validate env config
            _validate_config(config)

            # Add config source metadata
            config["_config_source"] = config_source
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

            # logging.info(f"✅ Configuration loaded from {config_source}")

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
        config["llm"] = {"preferred_provider": "openai", "temperature": 0.7, "max_tokens": 4000}
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
        raise ConfigurationError(f"Invalid YAML in agent_config.yaml: {e}")
    except Exception as e:
        raise ConfigurationError(f"Failed to load agent_config.yaml: {e}")


def _get_minimal_defaults() -> Dict[str, Any]:
    """Get minimal default configuration when nothing else is available."""
    return {
        "redis": {"host": "localhost", "port": 6379, "db": 0, "password": None},
        "llm": {"preferred_provider": "openai", "temperature": 0.7, "max_tokens": 4000},
        "agent_capabilities": {
            "enable_knowledge_base": False,
            "enable_web_search": False,
            "enable_code_execution": True,
            "enable_file_processing": False,
            "enable_web_ingestion": False,
            "enable_api_calls": False,
            "enable_web_scraping": False,
            "enable_proxy_mode": True,
            "enable_media_editor": False,
            "enable_youtube_download": False,
        },
        "service": {
            "enable_metrics": True,
            "log_level": "INFO",
            "max_sessions": 100,
            "session_timeout": 3600,
        },
        "agents": {
            "moderator": {
                "enabled": True,  # ModeratorAgent enabled by default
            },
            "analytics": {
                "enabled": True,  # AnalyticsAgent enabled by default when Docker available
            },
            "code_executor": {
                "enabled": True,  # CodeExecutorAgent enabled by default when Docker available
            },
            "youtube_download": {
                "enabled": True,  # YouTubeDownloadAgent enabled by default when Docker available
            },
            "media_editor": {
                "enabled": True,  # MediaEditorAgent enabled by default when Docker available
            },
            "web_scraper": {
                "enabled": True,  # WebScraperAgent enabled by default when Docker available
            },
        },
        "moderator": {"default_enabled_agents": ["assistant"]},
        "docker": {
            "images": ["sgosain/amb-ubuntu-python-public-pod"],
            "memory_limit": "512m",
            "timeout": 60,
            "work_dir": "/opt/ambivo/work_dir",
        },
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

        # Database agent supported types handling (comma-separated lists)
        elif (
            path[0] == "database_agent"
            and final_key == "supported_types"
            and isinstance(value, str)
        ):
            current[final_key] = [db_type.strip() for db_type in value.split(",")]
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
        config["llm"].setdefault("max_tokens", 4000)
        config["llm"].setdefault("preferred_provider", "openai")

    # Set agent capabilities defaults
    if "agent_capabilities" in config:
        caps = config["agent_capabilities"]
        caps.setdefault("enable_file_processing", True)
        caps.setdefault("enable_web_ingestion", True)
        caps.setdefault("enable_api_calls", True)
        caps.setdefault("enable_agent_collaboration", True)
        caps.setdefault("enable_result_synthesis", True)
        caps.setdefault("enable_multi_source_validation", True)
        caps.setdefault("max_concurrent_operations", 5)
        caps.setdefault("operation_timeout_seconds", 30)
        caps.setdefault("max_memory_usage_mb", 500)

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
        ws.setdefault("output_dir", "./scraper_output")  # Docker-accessible with shared volume
        ws.setdefault("docker_shared_mode", True)  # Enable Docker volume sharing

    # Set YouTube download defaults with Docker-accessible directories
    if "youtube_download" in config:
        yt = config["youtube_download"]
        yt.setdefault("download_dir", "./youtube_downloads")  # Docker-accessible with shared volume
        yt.setdefault("timeout", 600)
        yt.setdefault("memory_limit", "1g")
        yt.setdefault("default_audio_only", True)
        yt.setdefault("docker_image", "sgosain/amb-ubuntu-python-public-pod")
        yt.setdefault("docker_shared_mode", True)  # Enable Docker volume sharing

    # Set media editor defaults with Docker-accessible directories
    if "media_editor" in config:
        me = config["media_editor"]
        me.setdefault("input_dir", "./media_input")  # Docker-accessible with shared volume
        me.setdefault("output_dir", "./media_output")  # Docker-accessible with shared volume
        me.setdefault("timeout", 300)
        me.setdefault("docker_image", "sgosain/amb-ubuntu-python-public-pod")
        me.setdefault("work_dir", "/opt/ambivo/work_dir")
        me.setdefault("docker_shared_mode", True)  # Enable Docker volume sharing

    # Set agents defaults - ensure all agents are enabled by default when Docker available
    if "agents" not in config:
        config["agents"] = {}

    agents = config["agents"]
    agents.setdefault("moderator", {}).setdefault("enabled", True)
    agents.setdefault("analytics", {}).setdefault(
        "enabled", True
    )  # Default to True when Docker available
    agents.setdefault("code_executor", {}).setdefault(
        "enabled", True
    )  # Default to True when Docker available
    agents.setdefault("youtube_download", {}).setdefault(
        "enabled", True
    )  # Default to True when Docker available
    agents.setdefault("media_editor", {}).setdefault(
        "enabled", True
    )  # Default to True when Docker available
    agents.setdefault("web_scraper", {}).setdefault(
        "enabled", True
    )  # Default to True when Docker available

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
            "/etc",  # System configuration files
            "/root",  # Root user home directory
            "/var/log",  # System logs
            "/proc",  # Process filesystem
            "/sys",  # System filesystem
            "/dev",  # Device files
            "/boot",  # Boot files
            "~/.ssh",  # SSH keys
            "~/.aws",  # AWS credentials
            "~/.config",  # User configuration files
            "/usr/bin",  # System binaries
            "/usr/sbin",  # System admin binaries
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
        )  # Use docker_shared structure consistently
        docker.setdefault("network_disabled", True)
        docker.setdefault("auto_remove", True)

        # Container mounts defaults
        if "container_mounts" not in docker:
            docker["container_mounts"] = {}
        container_mounts = docker["container_mounts"]
        container_mounts.setdefault("input", "/docker_shared/input")
        container_mounts.setdefault("output", "/docker_shared/output")
        container_mounts.setdefault("temp", "/docker_shared/temp")
        container_mounts.setdefault("handoff", "/docker_shared/handoff")
        container_mounts.setdefault("work", "/docker_shared/work")

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
        service.setdefault("enable_metrics", True)

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
            if config.get("agent_capabilities", {}).get("enable_youtube_download"):
                enabled_agents.append("youtube_download")
            if config.get("agent_capabilities", {}).get("enable_media_editor"):
                enabled_agents.append("media_editor")
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

    # Set Analytics Agent defaults (consolidated structure)
    if "analytics" in config:
        analytics = config["analytics"]
        analytics.setdefault("docker_image", "sgosain/amb-ubuntu-python-public-pod")
        analytics.setdefault("input_subdir", "analytics")
        analytics.setdefault("output_subdir", "analytics")
        analytics.setdefault("temp_subdir", "analytics")
        analytics.setdefault("handoff_subdir", "analytics")
        analytics.setdefault("database_handoff_source", "database")
        analytics.setdefault("timeout", 120)
        analytics.setdefault("memory_limit", "2g")
        analytics.setdefault("max_file_size_mb", 100)
        analytics.setdefault("max_rows_preview", 1000)
        analytics.setdefault("enable_visualizations", True)
        analytics.setdefault("enable_sql_queries", True)

    # Set Code Executor defaults (enhanced fallback)
    if "code_executor" in config:
        code_exec = config["code_executor"]
        code_exec.setdefault("docker_image", "sgosain/amb-ubuntu-python-public-pod")
        code_exec.setdefault("input_subdir", "code")
        code_exec.setdefault("output_subdir", "code")
        code_exec.setdefault("temp_subdir", "code")
        code_exec.setdefault("handoff_subdir", "code")
        code_exec.setdefault("enhanced_fallback_enabled", True)
        code_exec.setdefault("auto_detect_file_operations", True)
        code_exec.setdefault("fallback_timeout", 120)
        code_exec.setdefault("timeout", 120)
        code_exec.setdefault("memory_limit", "2g")
        code_exec.setdefault("max_output_size_mb", 50)
        code_exec.setdefault("restricted_imports", True)
        code_exec.setdefault("sandbox_mode", True)
        code_exec.setdefault("allow_network", False)

    # Set Database Agent defaults (consolidated structure)
    if "database_agent" not in config:
        config["database_agent"] = {}
    db_agent = config["database_agent"]

    # Use configured docker shared base directory for exports
    docker_config = config.get("docker", {})
    shared_base_dir = docker_config.get("shared_base_dir", "./docker_shared")
    default_export_dir = f"{shared_base_dir}/output/database"

    db_agent.setdefault("local_export_dir", default_export_dir)
    db_agent.setdefault("handoff_subdir", "database")
    db_agent.setdefault("auto_copy_to_shared", True)
    db_agent.setdefault("strict_mode", True)
    db_agent.setdefault("max_result_rows", 1000)
    db_agent.setdefault("query_timeout", 30)
    db_agent.setdefault("enable_analytics_handoff", True)
    db_agent.setdefault("supported_types", ["mongodb", "mysql", "postgresql"])

    # Set Workflow defaults
    if "workflows" in config:
        workflows = config["workflows"]

        # Database to Analytics workflow
        if "database_to_analytics" not in workflows:
            workflows["database_to_analytics"] = {}
        db_analytics = workflows["database_to_analytics"]
        db_analytics.setdefault("enabled", True)
        db_analytics.setdefault("source_path", "database")
        db_analytics.setdefault("target_path", "database")
        db_analytics.setdefault("auto_trigger", True)
        db_analytics.setdefault("file_formats", [".csv", ".xlsx", ".json"])

        # Code Executor fallback workflow
        if "code_executor_fallback" not in workflows:
            workflows["code_executor_fallback"] = {}
        code_fallback = workflows["code_executor_fallback"]
        code_fallback.setdefault("enabled", True)
        code_fallback.setdefault("input_detection", True)
        code_fallback.setdefault("output_organization", True)
        code_fallback.setdefault("cleanup_temp", True)
        code_fallback.setdefault("preserve_logs", True)

    # Set Docker Directory Management defaults
    if "docker_directory_management" in config:
        dir_mgmt = config["docker_directory_management"]
        dir_mgmt.setdefault("auto_create_structure", True)
        dir_mgmt.setdefault("cleanup_on_exit", False)
        dir_mgmt.setdefault("backup_before_cleanup", True)
        dir_mgmt.setdefault("max_temp_file_age_hours", 24)
        dir_mgmt.setdefault("directory_permissions", "755")
        dir_mgmt.setdefault("file_permissions", "644")
        dir_mgmt.setdefault("log_file_operations", True)
        dir_mgmt.setdefault("track_disk_usage", True)
        dir_mgmt.setdefault("max_shared_size_gb", 10)

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
    retention.setdefault("conversation_ttl", 2592000)  # 30 days
    retention.setdefault("checkpoint_ttl", 604800)  # 7 days
    retention.setdefault("session_ttl", 86400)  # 24 hours
    retention.setdefault("cleanup_interval", 3600)  # 1 hour

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
    file_config.setdefault("max_file_size", 10485760)  # 10MB

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
        return config.get("_config_source", "unknown")
    except:
        return "none"


# Backward compatibility - keep existing functions
CAPABILITY_TO_AGENT_TYPE = {
    "assistant": "assistant",
    "code_execution": "code_executor",
    "proxy": "proxy",
    "web_scraping": "web_scraper",
    "knowledge_base": "knowledge_base",
    "web_search": "web_search",
    "media_editor": "media_editor",
    "youtube_download": "youtube_download",
    "gather": "gather_agent",
}

CONFIG_FLAG_TO_CAPABILITY = {
    "enable_web_scraping": "web_scraping",
    "enable_knowledge_base": "knowledge_base",
    "enable_web_search": "web_search",
    "enable_media_editor": "media_editor",
    "enable_youtube_download": "youtube_download",
    "enable_code_execution": "code_execution",
    "enable_proxy_mode": "proxy",
    "enable_gather": "gather",
}


def validate_agent_capabilities(config: Dict[str, Any] = None) -> Dict[str, bool]:
    """Validate and return available agent capabilities based on configuration."""
    if config is None:
        config = load_config()

    capabilities = {
        "assistant": True,
        "code_execution": True,
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

    capabilities["media_editor"] = (
        agent_caps.get("enable_media_editor", False) and "media_editor" in config
    )

    capabilities["youtube_download"] = (
        agent_caps.get("enable_youtube_download", False) and "youtube_download" in config
    )

    capabilities["gather"] = agent_caps.get("enable_gather", False) and "gather" in config

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
            "assistant": True,
            "code_executor": True,
            "proxy": True,
            "knowledge_base": False,
            "web_scraper": False,
            "web_search": False,
            "media_editor": False,
            "youtube_download": False,
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

    env_vars = {k: v for k, v in os.environ.items() if k.startswith("AMBIVO_AGENTS_")}

    if not env_vars:
        print("❌ No AMBIVO_AGENTS_ environment variables found")
        return

    print(f"✅ Found {len(env_vars)} environment variables:")
    for key, value in sorted(env_vars.items()):
        # Mask sensitive values
        if any(sensitive in key.lower() for sensitive in ["key", "password", "secret"]):
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
