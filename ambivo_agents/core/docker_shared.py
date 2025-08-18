#!/usr/bin/env python3
"""
Docker Shared Directory Manager for consolidated file sharing across agents
"""

import os
import shutil
from pathlib import Path
from typing import Dict, Optional, List, Tuple
import logging

logger = logging.getLogger(__name__)


class DockerSharedManager:
    """
    Centralized manager for Docker-shared directory structure
    Used by all agents to ensure consistent file sharing
    """

    def __init__(
        self, base_dir: str = "./docker_shared", legacy_fallback_dirs: Optional[List[str]] = None
    ):
        self.base_dir = Path(base_dir).resolve()
        self.container_base = "/docker_shared"

        # Configurable legacy fallback directories (instead of hardcoded "examples")
        self.legacy_fallback_dirs = [Path(d) for d in (legacy_fallback_dirs or [])]

        # Define standard subdirectories
        self.subdirs = {
            "input": self.base_dir / "input",
            "output": self.base_dir / "output",
            "temp": self.base_dir / "temp",
            "handoff": self.base_dir / "handoff",
            "work": self.base_dir / "work",
        }

        # Agent-specific subdirectories (from agent_config.yaml)
        self.agent_subdirs = {
            "analytics": [
                "input/analytics",
                "output/analytics",
                "temp/analytics",
                "handoff/analytics",
            ],
            "media": ["input/media", "output/media", "temp/media", "handoff/media"],
            "code": ["input/code", "output/code", "temp/code", "handoff/code"],
            "database": ["handoff/database"],  # Database only needs handoff
            "scraper": ["output/scraper", "temp/scraper", "handoff/scraper"],
            "youtube": [
                "output/youtube",
                "temp/youtube",
                "handoff/youtube",
            ],  # YouTube download outputs
        }

    def setup_directories(self) -> bool:
        """Create all required directories"""
        try:
            logger.info(f"Setting up consolidated Docker directories at {self.base_dir}")

            # Create base directories
            for name, path in self.subdirs.items():
                path.mkdir(parents=True, exist_ok=True)
                logger.debug(f"Created base directory: {path}")

            # Create agent-specific subdirectories
            for agent, paths in self.agent_subdirs.items():
                for subpath in paths:
                    full_path = self.base_dir / subpath
                    full_path.mkdir(parents=True, exist_ok=True)
                    logger.debug(f"Created agent directory: {full_path}")

            logger.info("Docker shared directory structure created successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to create Docker shared directories: {e}")
            return False

    def get_host_path(self, agent: str, area: str) -> Path:
        """Get host filesystem path for agent and area"""
        return self.base_dir / area / agent

    def get_container_path(self, agent: str, area: str) -> str:
        """Get container path for agent and area"""
        return f"{self.container_base}/{area}/{agent}"

    def get_docker_volumes(self) -> Dict[str, Dict[str, str]]:
        """Get Docker volume mount configuration"""
        return {
            str(self.subdirs["input"]): {"bind": f"{self.container_base}/input", "mode": "ro"},
            str(self.subdirs["output"]): {"bind": f"{self.container_base}/output", "mode": "rw"},
            str(self.subdirs["temp"]): {"bind": f"{self.container_base}/temp", "mode": "rw"},
            str(self.subdirs["handoff"]): {"bind": f"{self.container_base}/handoff", "mode": "rw"},
            str(self.subdirs["work"]): {"bind": f"{self.container_base}/work", "mode": "rw"},
        }

    def copy_to_input(self, source_file: str, agent: str, filename: Optional[str] = None) -> Path:
        """Copy file to agent's input directory"""
        if filename is None:
            filename = os.path.basename(source_file)

        input_dir = self.get_host_path(agent, "input")
        input_dir.mkdir(parents=True, exist_ok=True)

        dest_path = input_dir / filename
        shutil.copy2(source_file, dest_path)
        logger.info(f"Copied {source_file} → {dest_path}")
        return dest_path

    def copy_to_handoff(
        self, source_file: str, from_agent: str, to_agent: str, filename: Optional[str] = None
    ) -> Path:
        """Copy file from one agent to another via handoff directory"""
        if filename is None:
            filename = os.path.basename(source_file)

        # Use from_agent's handoff directory
        handoff_dir = self.get_host_path(from_agent, "handoff")
        handoff_dir.mkdir(parents=True, exist_ok=True)

        dest_path = handoff_dir / filename
        shutil.copy2(source_file, dest_path)
        logger.info(f"Handoff: {source_file} → {dest_path} (from {from_agent} to {to_agent})")
        return dest_path

    def list_outputs(self, agent: str) -> List[str]:
        """List all output files for an agent"""
        output_dir = self.get_host_path(agent, "output")
        if output_dir.exists():
            return [f.name for f in output_dir.iterdir() if f.is_file()]
        return []

    def list_handoffs(self, agent: str) -> List[str]:
        """List all handoff files for an agent"""
        handoff_dir = self.get_host_path(agent, "handoff")
        if handoff_dir.exists():
            return [f.name for f in handoff_dir.iterdir() if f.is_file()]
        return []

    def get_latest_output(self, agent: str, file_extension: Optional[str] = None) -> Optional[Path]:
        """Get the most recently created output file for an agent"""
        output_dir = self.get_host_path(agent, "output")
        if not output_dir.exists():
            return None

        files = [f for f in output_dir.iterdir() if f.is_file()]
        if file_extension:
            files = [f for f in files if f.suffix.lower() == file_extension.lower()]

        if not files:
            return None

        # Return the most recently modified file
        return max(files, key=lambda f: f.stat().st_mtime)

    def cleanup_temp_files(self, max_age_hours: int = 24) -> int:
        """Clean up temporary files older than specified hours"""
        import time

        temp_dir = self.subdirs["temp"]
        if not temp_dir.exists():
            return 0

        current_time = time.time()
        max_age_seconds = max_age_hours * 3600
        cleaned_count = 0

        for file_path in temp_dir.rglob("*"):
            if file_path.is_file():
                file_age = current_time - file_path.stat().st_mtime
                if file_age > max_age_seconds:
                    try:
                        file_path.unlink()
                        cleaned_count += 1
                        logger.debug(f"Cleaned up old temp file: {file_path}")
                    except Exception as e:
                        logger.warning(f"Failed to clean up {file_path}: {e}")

        logger.info(f"Cleaned up {cleaned_count} temporary files older than {max_age_hours} hours")
        return cleaned_count

    def get_disk_usage(self) -> Dict[str, int]:
        """Get disk usage statistics for the shared directory"""

        def get_dir_size(path: Path) -> int:
            total = 0
            if path.exists():
                for file_path in path.rglob("*"):
                    if file_path.is_file():
                        total += file_path.stat().st_size
            return total

        return {
            "total_bytes": get_dir_size(self.base_dir),
            "input_bytes": get_dir_size(self.subdirs["input"]),
            "output_bytes": get_dir_size(self.subdirs["output"]),
            "temp_bytes": get_dir_size(self.subdirs["temp"]),
            "handoff_bytes": get_dir_size(self.subdirs["handoff"]),
            "work_bytes": get_dir_size(self.subdirs["work"]),
        }

    def resolve_input_file(
        self, filename: str, agent: str, legacy_dirs: Optional[List[Path]] = None
    ) -> Optional[Path]:
        """
        Resolve input file path by checking multiple locations in order of priority
        Similar to MediaDockerExecutor.resolve_input_file but generalized for all agents

        Args:
            filename: File name or path to resolve
            agent: Agent name for directory structure
            legacy_dirs: List of legacy directories to check for backward compatibility

        Returns:
            Path object if file exists, None otherwise
        """
        # If it's already an absolute path and exists, return it
        if Path(filename).is_absolute() and Path(filename).exists():
            return Path(filename)

        # Check various possible locations in order of priority
        search_locations = [
            # 1. Docker shared input directory (highest priority)
            self.get_host_path(agent, "input") / filename,
            self.get_host_path(agent, "input") / Path(filename).name,
            # 2. Docker shared handoff directory (for workflow handoffs)
            self.get_host_path(agent, "handoff") / filename,
            self.get_host_path(agent, "handoff") / Path(filename).name,
            # 3. Relative to current directory
            Path(filename),
            Path(filename).resolve(),
        ]

        # 4. Legacy fallback directories (configurable)
        for legacy_dir in self.legacy_fallback_dirs:
            search_locations.extend(
                [
                    legacy_dir / filename,
                    legacy_dir / Path(filename).name,
                ]
            )

        # 5. Add legacy directories if provided
        if legacy_dirs:
            for legacy_dir in legacy_dirs:
                search_locations.extend(
                    [
                        legacy_dir / filename,
                        legacy_dir / Path(filename).name,
                    ]
                )

        for location in search_locations:
            if location.exists():
                logger.debug(f"Resolved {filename} to {location}")
                return location

        logger.warning(f"Could not resolve input file: {filename}")
        return None

    def prepare_agent_environment(
        self, agent: str, input_files: Optional[List[str]] = None
    ) -> Tuple[str, str]:
        """
        Prepare Docker environment for an agent
        Returns: (input_container_path, output_container_path)
        """
        # Ensure agent directories exist
        for area in ["input", "output", "temp", "handoff"]:
            agent_dir = self.get_host_path(agent, area)
            agent_dir.mkdir(parents=True, exist_ok=True)

        # Copy input files if provided
        if input_files:
            for file_path in input_files:
                resolved_path = self.resolve_input_file(file_path, agent)
                if resolved_path:
                    self.copy_to_input(str(resolved_path), agent)
                else:
                    logger.warning(f"Input file not found: {file_path}")

        # Return container paths
        input_path = self.get_container_path(agent, "input")
        output_path = self.get_container_path(agent, "output")

        logger.info(
            f"Prepared Docker environment for {agent}: input={input_path}, output={output_path}"
        )
        return input_path, output_path


# Global shared manager instance
_shared_manager = None


def get_shared_manager(
    base_dir: str = "./docker_shared", legacy_fallback_dirs: Optional[List[str]] = None
) -> DockerSharedManager:
    """Get the global Docker shared manager instance"""
    global _shared_manager
    if _shared_manager is None or str(_shared_manager.base_dir) != os.path.abspath(base_dir):
        # Include examples directory as default fallback for backward compatibility
        default_fallbacks = ["examples"] if legacy_fallback_dirs is None else legacy_fallback_dirs
        _shared_manager = DockerSharedManager(base_dir, default_fallbacks)
        _shared_manager.setup_directories()
    return _shared_manager


def reset_shared_manager():
    """Reset the global shared manager (useful for testing)"""
    global _shared_manager
    _shared_manager = None
