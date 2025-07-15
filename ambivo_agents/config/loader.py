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
    f"{ENV_PREFIX}AGENT_CAPABILITIES_ENABLE_KNOWLEDGE_BASE": (
        "agent_capabilities",
        "enable_knowledge_base",
    ),
    f"{ENV_PREFIX}ENABLE_KNOWLEDGE_BASE": (
        "agent_capabilities",
        "enable_knowledge_base",
    ),  # Alternative
    f"{ENV_PREFIX}AGENT_CAPABILITIES_ENABLE_WEB_SEARCH": (
        "agent_capabilities",
        "enable_web_search",
    ),
    f"{ENV_PREFIX}ENABLE_WEB_SEARCH": ("agent_capabilities", "enable_web_search"),  # Alternative
    f"{ENV_PREFIX}AGENT_CAPABILITIES_ENABLE_CODE_EXECUTION": (
        "agent_capabilities",
        "enable_code_execution",
    ),
    f"{ENV_PREFIX}ENABLE_CODE_EXECUTION": (
        "agent_capabilities",
        "enable_code_execution",
    ),  # Alternative
    f"{ENV_PREFIX}AGENT_CAPABILITIES_ENABLE_WEB_SCRAPING": (
        "agent_capabilities",
        "enable_web_scraping",
    ),
    f"{ENV_PREFIX}ENABLE_WEB_SCRAPING": (
        "agent_capabilities",
        "enable_web_scraping",
    ),  # Alternative
    f"{ENV_PREFIX}AGENT_CAPABILITIES_ENABLE_MEDIA_EDITOR": (
        "agent_capabilities",
        "enable_media_editor",
    ),
    f"{ENV_PREFIX}ENABLE_MEDIA_EDITOR": (
        "agent_capabilities",
        "enable_media_editor",
    ),  # Alternative
    f"{ENV_PREFIX}AGENT_CAPABILITIES_ENABLE_YOUTUBE_DOWNLOAD": (
        "agent_capabilities",
        "enable_youtube_download",
    ),
    f"{ENV_PREFIX}ENABLE_YOUTUBE_DOWNLOAD": (
        "agent_capabilities",
        "enable_youtube_download",
    ),  # Alternative
    f"{ENV_PREFIX}AGENT_CAPABILITIES_ENABLE_PROXY_MODE": (
        "agent_capabilities",
        "enable_proxy_mode",
    ),
    f"{ENV_PREFIX}ENABLE_PROXY_MODE": ("agent_capabilities", "enable_proxy_mode"),  # Alternative
    f"{ENV_PREFIX}AGENT_CAPABILITIES_ENABLE_FILE_PROCESSING": (
        "agent_capabilities",
        "enable_file_processing",
    ),
    f"{ENV_PREFIX}AGENT_CAPABILITIES_ENABLE_WEB_INGESTION": (
        "agent_capabilities",
        "enable_web_ingestion",
    ),
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
    f"{ENV_PREFIX}WEB_SCRAPING_PROXY_CONFIG_HTTP_PROXY": (
        "web_scraping",
        "proxy_config",
        "http_proxy",
    ),
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
    f"{ENV_PREFIX}YOUTUBE_DEFAULT_AUDIO_ONLY": (
        "youtube_download",
        "default_audio_only",
    ),  # Alternative
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
    
    # Consolidated Docker Configuration
    f"{ENV_PREFIX}DOCKER_SHARED_BASE_DIR": ("docker", "shared_base_dir"),
    f"{ENV_PREFIX}DOCKER_CONTAINER_MOUNTS_INPUT": ("docker", "container_mounts", "input"),
    f"{ENV_PREFIX}DOCKER_CONTAINER_MOUNTS_OUTPUT": ("docker", "container_mounts", "output"),
    f"{ENV_PREFIX}DOCKER_CONTAINER_MOUNTS_TEMP": ("docker", "container_mounts", "temp"),
    f"{ENV_PREFIX}DOCKER_CONTAINER_MOUNTS_HANDOFF": ("docker", "container_mounts", "handoff"),
    f"{ENV_PREFIX}DOCKER_CONTAINER_MOUNTS_WORK": ("docker", "container_mounts", "work"),
    f"{ENV_PREFIX}DOCKER_NETWORK_DISABLED": ("docker", "network_disabled"),
    f"{ENV_PREFIX}DOCKER_AUTO_REMOVE": ("docker", "auto_remove"),
    
    # Docker Agent Subdirectories (comma-separated lists)
    f"{ENV_PREFIX}DOCKER_AGENT_SUBDIRS_ANALYTICS": ("docker", "agent_subdirs", "analytics"),
    f"{ENV_PREFIX}DOCKER_AGENT_SUBDIRS_MEDIA": ("docker", "agent_subdirs", "media"),
    f"{ENV_PREFIX}DOCKER_AGENT_SUBDIRS_CODE": ("docker", "agent_subdirs", "code"),
    f"{ENV_PREFIX}DOCKER_AGENT_SUBDIRS_DATABASE": ("docker", "agent_subdirs", "database"),
    f"{ENV_PREFIX}DOCKER_AGENT_SUBDIRS_SCRAPER": ("docker", "agent_subdirs", "scraper"),
    # Service Configuration
    f"{ENV_PREFIX}SERVICE_MAX_SESSIONS": ("service", "max_sessions"),
    f"{ENV_PREFIX}SERVICE_LOG_LEVEL": ("service", "log_level"),
    f"{ENV_PREFIX}SERVICE_SESSION_TIMEOUT": ("service", "session_timeout"),
    f"{ENV_PREFIX}SERVICE_ENABLE_METRICS": ("service", "enable_metrics"),
    f"{ENV_PREFIX}SERVICE_LOG_TO_FILE": ("service", "log_to_file"),
    # Moderator Configuration
    f"{ENV_PREFIX}MODERATOR_DEFAULT_ENABLED_AGENTS": ("moderator", "default_enabled_agents"),
    f"{ENV_PREFIX}MODERATOR_ENABLED_AGENTS": ("moderator", "default_enabled_agents"),  # Alternative
    f"{ENV_PREFIX}MODERATOR_ROUTING_CONFIDENCE_THRESHOLD": (
        "moderator",
        "routing",
        "confidence_threshold",
    ),
    f"{ENV_PREFIX}MODERATOR_CONFIDENCE_THRESHOLD": (
        "moderator",
        "routing",
        "confidence_threshold",
    ),  # Alternative
    # API Agent Configuration
    f"{ENV_PREFIX}API_AGENT_AUTO_SAVE_LARGE_RESPONSES": ("api_agent", "auto_save_large_responses"),
    f"{ENV_PREFIX}API_AUTO_SAVE_LARGE_RESPONSES": ("api_agent", "auto_save_large_responses"),  # Alternative
    f"{ENV_PREFIX}API_AGENT_SIZE_THRESHOLD_KB": ("api_agent", "size_threshold_kb"),
    f"{ENV_PREFIX}API_SIZE_THRESHOLD_KB": ("api_agent", "size_threshold_kb"),  # Alternative
    f"{ENV_PREFIX}API_AGENT_OUTPUT_DIRECTORY": ("api_agent", "output_directory"),
    f"{ENV_PREFIX}API_OUTPUT_DIRECTORY": ("api_agent", "output_directory"),  # Alternative
    f"{ENV_PREFIX}API_AGENT_FILENAME_TEMPLATE": ("api_agent", "filename_template"),
    f"{ENV_PREFIX}API_FILENAME_TEMPLATE": ("api_agent", "filename_template"),  # Alternative
    f"{ENV_PREFIX}API_AGENT_DETECT_CONTENT_TYPE": ("api_agent", "detect_content_type"),
    f"{ENV_PREFIX}API_DETECT_CONTENT_TYPE": ("api_agent", "detect_content_type"),  # Alternative
    f"{ENV_PREFIX}API_AGENT_MAX_INLINE_SIZE_KB": ("api_agent", "max_inline_size_kb"),
    f"{ENV_PREFIX}API_MAX_INLINE_SIZE_KB": ("api_agent", "max_inline_size_kb"),  # Alternative
    f"{ENV_PREFIX}API_AGENT_CREATE_SUMMARY": ("api_agent", "create_summary"),
    f"{ENV_PREFIX}API_CREATE_SUMMARY": ("api_agent", "create_summary"),  # Alternative
    f"{ENV_PREFIX}API_AGENT_COMPRESS_JSON": ("api_agent", "compress_json"),
    f"{ENV_PREFIX}API_COMPRESS_JSON": ("api_agent", "compress_json"),  # Alternative
    f"{ENV_PREFIX}API_AGENT_ALLOWED_DOMAINS": ("api_agent", "allowed_domains"),
    f"{ENV_PREFIX}API_ALLOWED_DOMAINS": ("api_agent", "allowed_domains"),  # Alternative
    f"{ENV_PREFIX}API_AGENT_BLOCKED_DOMAINS": ("api_agent", "blocked_domains"),
    f"{ENV_PREFIX}API_BLOCKED_DOMAINS": ("api_agent", "blocked_domains"),  # Alternative
    f"{ENV_PREFIX}API_AGENT_TIMEOUT_SECONDS": ("api_agent", "timeout_seconds"),
    f"{ENV_PREFIX}API_TIMEOUT_SECONDS": ("api_agent", "timeout_seconds"),  # Alternative
    
    # Analytics Agent (Consolidated Docker Structure)
    f"{ENV_PREFIX}ANALYTICS_INPUT_SUBDIR": ("analytics", "input_subdir"),
    f"{ENV_PREFIX}ANALYTICS_OUTPUT_SUBDIR": ("analytics", "output_subdir"),
    f"{ENV_PREFIX}ANALYTICS_TEMP_SUBDIR": ("analytics", "temp_subdir"),
    f"{ENV_PREFIX}ANALYTICS_HANDOFF_SUBDIR": ("analytics", "handoff_subdir"),
    f"{ENV_PREFIX}ANALYTICS_DATABASE_HANDOFF_SOURCE": ("analytics", "database_handoff_source"),
    f"{ENV_PREFIX}ANALYTICS_TIMEOUT": ("analytics", "timeout"),
    f"{ENV_PREFIX}ANALYTICS_MEMORY_LIMIT": ("analytics", "memory_limit"),
    f"{ENV_PREFIX}ANALYTICS_MAX_FILE_SIZE_MB": ("analytics", "max_file_size_mb"),
    f"{ENV_PREFIX}ANALYTICS_MAX_ROWS_PREVIEW": ("analytics", "max_rows_preview"),
    f"{ENV_PREFIX}ANALYTICS_ENABLE_VISUALIZATIONS": ("analytics", "enable_visualizations"),
    f"{ENV_PREFIX}ANALYTICS_ENABLE_SQL_QUERIES": ("analytics", "enable_sql_queries"),
    f"{ENV_PREFIX}ANALYTICS_DOCKER_IMAGE": ("analytics", "docker_image"),
    
    # Code Executor Agent (Enhanced Fallback)
    f"{ENV_PREFIX}CODE_EXECUTOR_INPUT_SUBDIR": ("code_executor", "input_subdir"),
    f"{ENV_PREFIX}CODE_EXECUTOR_OUTPUT_SUBDIR": ("code_executor", "output_subdir"),
    f"{ENV_PREFIX}CODE_EXECUTOR_TEMP_SUBDIR": ("code_executor", "temp_subdir"),
    f"{ENV_PREFIX}CODE_EXECUTOR_HANDOFF_SUBDIR": ("code_executor", "handoff_subdir"),
    f"{ENV_PREFIX}CODE_EXECUTOR_ENHANCED_FALLBACK_ENABLED": ("code_executor", "enhanced_fallback_enabled"),
    f"{ENV_PREFIX}CODE_EXECUTOR_AUTO_DETECT_FILE_OPERATIONS": ("code_executor", "auto_detect_file_operations"),
    f"{ENV_PREFIX}CODE_EXECUTOR_FALLBACK_TIMEOUT": ("code_executor", "fallback_timeout"),
    f"{ENV_PREFIX}CODE_EXECUTOR_TIMEOUT": ("code_executor", "timeout"),
    f"{ENV_PREFIX}CODE_EXECUTOR_MEMORY_LIMIT": ("code_executor", "memory_limit"),
    f"{ENV_PREFIX}CODE_EXECUTOR_MAX_OUTPUT_SIZE_MB": ("code_executor", "max_output_size_mb"),
    f"{ENV_PREFIX}CODE_EXECUTOR_RESTRICTED_IMPORTS": ("code_executor", "restricted_imports"),
    f"{ENV_PREFIX}CODE_EXECUTOR_SANDBOX_MODE": ("code_executor", "sandbox_mode"),
    f"{ENV_PREFIX}CODE_EXECUTOR_ALLOW_NETWORK": ("code_executor", "allow_network"),
    f"{ENV_PREFIX}CODE_EXECUTOR_DOCKER_IMAGE": ("code_executor", "docker_image"),
    
    # Media Editor Agent (Consolidated Docker Structure)
    f"{ENV_PREFIX}MEDIA_EDITOR_INPUT_SUBDIR": ("media_editor", "input_subdir"),
    f"{ENV_PREFIX}MEDIA_EDITOR_OUTPUT_SUBDIR": ("media_editor", "output_subdir"),
    f"{ENV_PREFIX}MEDIA_EDITOR_TEMP_SUBDIR": ("media_editor", "temp_subdir"),
    f"{ENV_PREFIX}MEDIA_EDITOR_HANDOFF_SUBDIR": ("media_editor", "handoff_subdir"),
    f"{ENV_PREFIX}MEDIA_EDITOR_MAX_FILE_SIZE_GB": ("media_editor", "max_file_size_gb"),
    f"{ENV_PREFIX}MEDIA_EDITOR_MAX_CONCURRENT_JOBS": ("media_editor", "max_concurrent_jobs"),
    f"{ENV_PREFIX}MEDIA_EDITOR_FFMPEG_THREADS": ("media_editor", "ffmpeg_threads"),
    f"{ENV_PREFIX}MEDIA_EDITOR_ENABLE_GPU_ACCELERATION": ("media_editor", "enable_gpu_acceleration"),
    f"{ENV_PREFIX}MEDIA_EDITOR_MEMORY_LIMIT": ("media_editor", "memory_limit"),
    
    # Database Agent (Consolidated Docker Structure)
    f"{ENV_PREFIX}DATABASE_AGENT_LOCAL_EXPORT_DIR": ("database_agent", "local_export_dir"),
    f"{ENV_PREFIX}DATABASE_AGENT_HANDOFF_SUBDIR": ("database_agent", "handoff_subdir"),
    f"{ENV_PREFIX}DATABASE_AGENT_AUTO_COPY_TO_SHARED": ("database_agent", "auto_copy_to_shared"),
    f"{ENV_PREFIX}DATABASE_AGENT_STRICT_MODE": ("database_agent", "strict_mode"),
    f"{ENV_PREFIX}DATABASE_AGENT_MAX_RESULT_ROWS": ("database_agent", "max_result_rows"),
    f"{ENV_PREFIX}DATABASE_AGENT_QUERY_TIMEOUT": ("database_agent", "query_timeout"),
    f"{ENV_PREFIX}DATABASE_AGENT_ENABLE_ANALYTICS_HANDOFF": ("database_agent", "enable_analytics_handoff"),
    f"{ENV_PREFIX}DATABASE_AGENT_SUPPORTED_TYPES": ("database_agent", "supported_types"),
    
    # Web Scraping Agent (Consolidated Docker Structure)
    f"{ENV_PREFIX}WEB_SCRAPING_OUTPUT_SUBDIR": ("web_scraping", "output_subdir"),
    f"{ENV_PREFIX}WEB_SCRAPING_TEMP_SUBDIR": ("web_scraping", "temp_subdir"),
    f"{ENV_PREFIX}WEB_SCRAPING_HANDOFF_SUBDIR": ("web_scraping", "handoff_subdir"),
    f"{ENV_PREFIX}WEB_SCRAPING_DOCKER_MEMORY_LIMIT": ("web_scraping", "docker_memory_limit"),
    f"{ENV_PREFIX}WEB_SCRAPING_DOCKER_CLEANUP": ("web_scraping", "docker_cleanup"),
    
    # Cross-Agent Workflow Configurations
    f"{ENV_PREFIX}WORKFLOWS_DATABASE_TO_ANALYTICS_ENABLED": ("workflows", "database_to_analytics", "enabled"),
    f"{ENV_PREFIX}WORKFLOWS_DATABASE_TO_ANALYTICS_SOURCE_PATH": ("workflows", "database_to_analytics", "source_path"),
    f"{ENV_PREFIX}WORKFLOWS_DATABASE_TO_ANALYTICS_TARGET_PATH": ("workflows", "database_to_analytics", "target_path"),
    f"{ENV_PREFIX}WORKFLOWS_DATABASE_TO_ANALYTICS_AUTO_TRIGGER": ("workflows", "database_to_analytics", "auto_trigger"),
    f"{ENV_PREFIX}WORKFLOWS_DATABASE_TO_ANALYTICS_FILE_FORMATS": ("workflows", "database_to_analytics", "file_formats"),
    
    f"{ENV_PREFIX}WORKFLOWS_MEDIA_TO_HOST_ENABLED": ("workflows", "media_to_host", "enabled"),
    f"{ENV_PREFIX}WORKFLOWS_MEDIA_TO_HOST_SOURCE_PATH": ("workflows", "media_to_host", "source_path"),
    f"{ENV_PREFIX}WORKFLOWS_MEDIA_TO_HOST_TARGET_PATH": ("workflows", "media_to_host", "target_path"),
    f"{ENV_PREFIX}WORKFLOWS_MEDIA_TO_HOST_AUTO_COPY": ("workflows", "media_to_host", "auto_copy"),
    f"{ENV_PREFIX}WORKFLOWS_MEDIA_TO_HOST_FILE_FORMATS": ("workflows", "media_to_host", "file_formats"),
    
    f"{ENV_PREFIX}WORKFLOWS_CODE_EXECUTOR_FALLBACK_ENABLED": ("workflows", "code_executor_fallback", "enabled"),
    f"{ENV_PREFIX}WORKFLOWS_CODE_EXECUTOR_FALLBACK_INPUT_DETECTION": ("workflows", "code_executor_fallback", "input_detection"),
    f"{ENV_PREFIX}WORKFLOWS_CODE_EXECUTOR_FALLBACK_OUTPUT_ORGANIZATION": ("workflows", "code_executor_fallback", "output_organization"),
    f"{ENV_PREFIX}WORKFLOWS_CODE_EXECUTOR_FALLBACK_CLEANUP_TEMP": ("workflows", "code_executor_fallback", "cleanup_temp"),
    f"{ENV_PREFIX}WORKFLOWS_CODE_EXECUTOR_FALLBACK_PRESERVE_LOGS": ("workflows", "code_executor_fallback", "preserve_logs"),
    
    f"{ENV_PREFIX}WORKFLOWS_SCRAPER_TO_ANALYTICS_ENABLED": ("workflows", "scraper_to_analytics", "enabled"),
    f"{ENV_PREFIX}WORKFLOWS_SCRAPER_TO_ANALYTICS_SOURCE_PATH": ("workflows", "scraper_to_analytics", "source_path"),
    f"{ENV_PREFIX}WORKFLOWS_SCRAPER_TO_ANALYTICS_TARGET_PATH": ("workflows", "scraper_to_analytics", "target_path"),
    f"{ENV_PREFIX}WORKFLOWS_SCRAPER_TO_ANALYTICS_AUTO_CONVERT": ("workflows", "scraper_to_analytics", "auto_convert"),
    f"{ENV_PREFIX}WORKFLOWS_SCRAPER_TO_ANALYTICS_FILE_FORMATS": ("workflows", "scraper_to_analytics", "file_formats"),
    
    # Docker Directory Management
    f"{ENV_PREFIX}DOCKER_DIRECTORY_MANAGEMENT_AUTO_CREATE_STRUCTURE": ("docker_directory_management", "auto_create_structure"),
    f"{ENV_PREFIX}DOCKER_DIRECTORY_MANAGEMENT_CLEANUP_ON_EXIT": ("docker_directory_management", "cleanup_on_exit"),
    f"{ENV_PREFIX}DOCKER_DIRECTORY_MANAGEMENT_BACKUP_BEFORE_CLEANUP": ("docker_directory_management", "backup_before_cleanup"),
    f"{ENV_PREFIX}DOCKER_DIRECTORY_MANAGEMENT_MAX_TEMP_FILE_AGE_HOURS": ("docker_directory_management", "max_temp_file_age_hours"),
    f"{ENV_PREFIX}DOCKER_DIRECTORY_MANAGEMENT_DIRECTORY_PERMISSIONS": ("docker_directory_management", "directory_permissions"),
    f"{ENV_PREFIX}DOCKER_DIRECTORY_MANAGEMENT_FILE_PERMISSIONS": ("docker_directory_management", "file_permissions"),
    f"{ENV_PREFIX}DOCKER_DIRECTORY_MANAGEMENT_LOG_FILE_OPERATIONS": ("docker_directory_management", "log_file_operations"),
    f"{ENV_PREFIX}DOCKER_DIRECTORY_MANAGEMENT_TRACK_DISK_USAGE": ("docker_directory_management", "track_disk_usage"),
    f"{ENV_PREFIX}DOCKER_DIRECTORY_MANAGEMENT_MAX_SHARED_SIZE_GB": ("docker_directory_management", "max_shared_size_gb"),
    
    # Additional Agent Capabilities
    f"{ENV_PREFIX}AGENT_CAPABILITIES_ENABLE_API_AGENT": ("agent_capabilities", "enable_api_agent"),
    f"{ENV_PREFIX}AGENT_CAPABILITIES_ENABLE_ANALYTICS": ("agent_capabilities", "enable_analytics"),
    f"{ENV_PREFIX}AGENT_CAPABILITIES_ENABLE_DATABASE_AGENT": ("agent_capabilities", "enable_database_agent"),
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

    # Validate that we have minimum required configuration
    if not config.get("redis") or not config.get("llm"):
        missing = []
        if not config.get("redis"):
            missing.append("redis")
        if not config.get("llm"):
            missing.append("llm")
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
        with open(config_file, "r", encoding="utf-8") as f:
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
        elif (
            path[0] == "workflows"
            and final_key == "file_formats"
            and isinstance(value, str)
        ):
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

    # Set web scraping defaults
    if "web_scraping" in config:
        ws = config["web_scraping"]
        ws.setdefault("timeout", 120)
        ws.setdefault("proxy_enabled", False)
        ws.setdefault("docker_image", "sgosain/amb-ubuntu-python-public-pod")

    # Set YouTube download defaults
    if "youtube_download" in config:
        yt = config["youtube_download"]
        yt.setdefault("download_dir", "./youtube_downloads")
        yt.setdefault("timeout", 600)
        yt.setdefault("memory_limit", "1g")
        yt.setdefault("default_audio_only", True)
        yt.setdefault("docker_image", "sgosain/amb-ubuntu-python-public-pod")

    # Set media editor defaults
    if "media_editor" in config:
        me = config["media_editor"]
        me.setdefault("input_dir", "./examples/media_input")
        me.setdefault("output_dir", "./examples/media_output")
        me.setdefault("timeout", 300)
        me.setdefault("docker_image", "sgosain/amb-ubuntu-python-public-pod")
        me.setdefault("work_dir", "/opt/ambivo/work_dir")

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
        agent_subdirs.setdefault("analytics", ["input/analytics", "output/analytics", "temp/analytics", "handoff/analytics"])
        agent_subdirs.setdefault("media", ["input/media", "output/media", "temp/media", "handoff/media"])
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
    if "database_agent" in config:
        db_agent = config["database_agent"]
        db_agent.setdefault("local_export_dir", "./database_exports")
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
}

CONFIG_FLAG_TO_CAPABILITY = {
    "enable_web_scraping": "web_scraping",
    "enable_knowledge_base": "knowledge_base",
    "enable_web_search": "web_search",
    "enable_media_editor": "media_editor",
    "enable_youtube_download": "youtube_download",
    "enable_code_execution": "code_execution",
    "enable_proxy_mode": "proxy",
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
