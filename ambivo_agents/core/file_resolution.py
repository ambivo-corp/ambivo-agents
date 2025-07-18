"""
Universal File Resolution for All Agents
Provides consistent file path resolution based on shared_base_dir configuration
"""

from pathlib import Path
from typing import List, Optional, Union

from ..config.loader import get_config_section
from .docker_shared import get_shared_manager


def resolve_agent_file_path(
    filename: str, 
    agent_type: str = "code", 
    priority_subdirs: Optional[List[str]] = None
) -> Optional[Path]:
    """
    Universal file resolution for all agents using shared_base_dir configuration.
    
    Args:
        filename: Name or relative path of file to find
        agent_type: Agent type (analytics, media, code, database, scraper, etc.)
        priority_subdirs: Optional list of subdirectories to check first
    
    Returns:
        Resolved Path object if file exists, None otherwise
        
    Resolution Priority:
        1. Priority subdirs (if provided)
        2. Agent-specific input directory: {shared_base_dir}/input/{agent_type}/
        3. Agent-specific handoff directory: {shared_base_dir}/handoff/{agent_type}/
        4. Current working directory
        5. Legacy fallback directories from config
        6. Generic shared input: {shared_base_dir}/input/
        7. Generic shared directory: {shared_base_dir}/
    """
    try:
        # Get configuration
        docker_config = get_config_section("docker") or {}
        shared_base_dir = docker_config.get("shared_base_dir", "./docker_shared")
        legacy_fallback_dirs = docker_config.get("legacy_fallback_dirs", ["docker_shared/input", "docker_shared"])
        
        # Get shared manager
        shared_manager = get_shared_manager(shared_base_dir, legacy_fallback_dirs)
        
        # If it's already an absolute path and exists, return it
        if Path(filename).is_absolute() and Path(filename).exists():
            return Path(filename)
        
        # Build search locations in priority order
        search_locations = []
        
        # 1. Priority subdirs (if provided)
        if priority_subdirs:
            for subdir in priority_subdirs:
                base_path = Path(shared_base_dir) / subdir
                search_locations.extend([
                    base_path / filename,
                    base_path / Path(filename).name,
                ])
        
        # 2. Agent-specific input directory (highest standard priority)
        agent_input_path = Path(shared_base_dir) / "input" / agent_type
        search_locations.extend([
            agent_input_path / filename,
            agent_input_path / Path(filename).name,
        ])
        
        # 3. Agent-specific handoff directory (for workflow handoffs)
        agent_handoff_path = Path(shared_base_dir) / "handoff" / agent_type
        search_locations.extend([
            agent_handoff_path / filename,
            agent_handoff_path / Path(filename).name,
        ])
        
        # 4. Current working directory
        search_locations.extend([
            Path(filename),
            Path(filename).resolve(),
        ])
        
        # 5. Legacy fallback directories (configurable)
        for legacy_dir in legacy_fallback_dirs:
            legacy_path = Path(legacy_dir)
            search_locations.extend([
                legacy_path / filename,
                legacy_path / Path(filename).name,
            ])
        
        # 6. Generic shared input directory
        shared_input_path = Path(shared_base_dir) / "input"
        search_locations.extend([
            shared_input_path / filename,
            shared_input_path / Path(filename).name,
        ])
        
        # 7. Generic shared directory (last resort)
        shared_base_path = Path(shared_base_dir)
        search_locations.extend([
            shared_base_path / filename,
            shared_base_path / Path(filename).name,
        ])
        
        # Search for file in order of priority
        for location in search_locations:
            if location.exists() and location.is_file():
                return location.resolve()
        
        return None
        
    except Exception:
        # Fallback to simple path resolution
        if Path(filename).exists():
            return Path(filename)
        return None


def get_agent_type_from_config(agent_name: str) -> str:
    """
    Get the agent type from configuration for file resolution.
    
    Args:
        agent_name: Name of the agent (e.g., "AnalyticsAgent", "MediaEditorAgent")
    
    Returns:
        Agent type string for directory resolution
    """
    # Mapping from agent class names to directory types
    agent_type_mapping = {
        "AnalyticsAgent": "analytics",
        "MediaEditorAgent": "media", 
        "CodeExecutorAgent": "code",
        "DatabaseAgent": "database",
        "WebScraperAgent": "scraper",
        "KnowledgeBaseAgent": "code",  # KB uses 'code' subdirs
        "AssistantAgent": "code",      # Assistant uses 'code' subdirs
        "APIAgent": "code",            # API agent uses 'code' subdirs
        "ModeratorAgent": "code",      # Moderator uses 'code' subdirs
        "WebSearchAgent": "code",      # Web search uses 'code' subdirs
        "YouTubeDownloadAgent": "media"  # YouTube uses 'media' subdirs
    }
    
    return agent_type_mapping.get(agent_name, "code")  # Default to 'code'


def get_agent_specific_subdirs(agent_type: str) -> List[str]:
    """
    Get agent-specific subdirectories from configuration.
    
    Args:
        agent_type: Agent type (analytics, media, code, etc.)
    
    Returns:
        List of subdirectories to check for this agent type
    """
    try:
        docker_config = get_config_section("docker") or {}
        agent_subdirs = docker_config.get("agent_subdirs", {})
        return agent_subdirs.get(agent_type, [])
    except Exception:
        return []