# ambivo_agents/executors/media_executor.py
"""
Media Docker executor for FFmpeg operations.
"""

import asyncio
import json
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any, Dict

from ..config.loader import get_config_section, load_config
from ..core.docker_shared import DockerSharedManager, get_shared_manager

try:
    import docker

    DOCKER_AVAILABLE = True
except ImportError:
    DOCKER_AVAILABLE = False


class MediaDockerExecutor:
    """Specialized Docker executor for media processing with ffmpeg"""

    def __init__(self, config: Dict[str, Any] = None):
        # Load from YAML if config not provided
        if config is None:
            try:
                full_config = load_config()
                config = get_config_section("media_editor", full_config)
            except Exception:
                config = {}

        self.config = config
        self.work_dir = config.get("work_dir", "/opt/ambivo/work_dir")
        self.docker_image = config.get("docker_image", "sgosain/amb-ubuntu-python-public-pod")
        self.timeout = config.get("timeout", 300)  # 5 minutes for media processing
        self.memory_limit = config.get("memory_limit", "2g")

        # Initialize Docker shared manager with configured base directory
        try:
            full_config = load_config()
            docker_config = get_config_section("docker", full_config)
        except Exception:
            docker_config = {}
        shared_base_dir = docker_config.get("shared_base_dir", "./docker_shared")
        self.shared_manager = get_shared_manager(shared_base_dir)
        self.shared_manager.setup_directories()

        # Get agent-specific subdirectory names from config
        self.input_subdir = config.get("input_subdir", "media")
        self.output_subdir = config.get("output_subdir", "media")
        self.temp_subdir = config.get("temp_subdir", "media")
        self.handoff_subdir = config.get("handoff_subdir", "media")

        # Set up proper directories using DockerSharedManager
        self.input_dir = self.shared_manager.get_host_path(self.input_subdir, "input")
        self.output_dir = self.shared_manager.get_host_path(self.output_subdir, "output")
        self.temp_dir = self.shared_manager.get_host_path(self.temp_subdir, "temp")
        self.handoff_dir = self.shared_manager.get_host_path(self.handoff_subdir, "handoff")

        # Ensure all directories exist
        self.input_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.handoff_dir.mkdir(parents=True, exist_ok=True)

        if not DOCKER_AVAILABLE:
            raise ImportError("Docker package is required for media processing")

        try:
            self.docker_client = docker.from_env()
            self.docker_client.ping()
            self.available = True
        except Exception as e:
            raise ConnectionError(f"Failed to connect to Docker for media processing: {e}")

    def resolve_input_file(self, filename: str) -> Path:
        """
        Resolve input file path by checking multiple locations

        Args:
            filename: File name or path to resolve

        Returns:
            Path object if file exists, None otherwise
        """
        # If it's already an absolute path and exists, return it
        if Path(filename).is_absolute() and Path(filename).exists():
            return Path(filename)

        # Check various possible locations in order of priority
        search_locations = [
            # 1. Docker shared input directory (highest priority)
            self.input_dir / filename,
            self.input_dir / Path(filename).name,
            # 2. Relative to current directory
            Path(filename),
            Path(filename).resolve(),
            # 4. Other docker shared directories (for workflow handoffs)
            self.handoff_dir / filename,
            self.handoff_dir / Path(filename).name,
            # 5. Cross-agent handoff directories (for workflow integration)
            self.shared_manager.get_host_path("youtube", "handoff") / filename,
            self.shared_manager.get_host_path("youtube", "handoff") / Path(filename).name,
            self.shared_manager.get_host_path("youtube", "output") / filename,
            self.shared_manager.get_host_path("youtube", "output") / Path(filename).name,
            self.shared_manager.get_host_path("analytics", "handoff") / filename,
            self.shared_manager.get_host_path("analytics", "handoff") / Path(filename).name,
            self.shared_manager.get_host_path("code", "handoff") / filename,
            self.shared_manager.get_host_path("code", "handoff") / Path(filename).name,
        ]

        for location in search_locations:
            if location.exists():
                return location

        return None

    def execute_ffmpeg_command(
        self,
        ffmpeg_command: str,
        input_files: Dict[str, str] = None,
        output_filename: str = None,
        work_files: Dict[str, str] = None,
    ) -> Dict[str, Any]:
        """
        Execute ffmpeg command in Docker container

        Args:
            ffmpeg_command: FFmpeg command to execute
            input_files: Dict of {container_path: host_path} for input files
            output_filename: Expected output filename
            work_files: Additional working files needed
        """
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)

                # Create input and output directories in temp
                container_input = temp_path / "input"
                container_output = temp_path / "output"
                container_input.mkdir()
                container_output.mkdir()

                # Copy input files to temp directory
                file_mapping = {}
                if input_files:
                    for container_name, host_path in input_files.items():
                        # Try to resolve the file path using our search logic
                        resolved_path = self.resolve_input_file(host_path)

                        if resolved_path and resolved_path.exists():
                            dest_path = container_input / container_name
                            shutil.copy2(resolved_path, dest_path)
                            file_mapping[container_name] = f"/workspace/input/{container_name}"
                        else:
                            # Provide helpful error message with search locations
                            search_dirs = [
                                str(self.input_dir),
                                str(self.handoff_dir),
                                "Current directory",
                            ]
                            return {
                                "success": False,
                                "error": f"Input file not found: {host_path}\nSearched in: {', '.join(search_dirs)}",
                                "command": ffmpeg_command,
                                "searched_locations": search_dirs,
                            }

                # Copy additional work files
                if work_files:
                    for container_name, content in work_files.items():
                        work_file = temp_path / container_name
                        work_file.write_text(content)

                # Prepare the ffmpeg command with proper paths
                final_command = ffmpeg_command
                for container_name, container_path in file_mapping.items():
                    final_command = final_command.replace(f"${{{container_name}}}", container_path)

                # Add output path
                if output_filename:
                    final_command = final_command.replace(
                        "${OUTPUT}", f"/workspace/output/{output_filename}"
                    )

                # Create execution script
                script_content = f"""#!/bin/bash
set -e
cd /workspace

echo "FFmpeg version:"
ffmpeg -version | head -1

echo "Starting media processing..."
echo "Command: {final_command}"

# Execute the command
{final_command}

echo "Media processing completed successfully"
ls -la /workspace/output/
"""

                script_file = temp_path / "process_media.sh"
                script_file.write_text(script_content)
                script_file.chmod(0o755)

                # Container configuration for media processing
                container_config = {
                    "image": self.docker_image,
                    "command": ["bash", "/workspace/process_media.sh"],
                    "volumes": {str(temp_path): {"bind": "/workspace", "mode": "rw"}},
                    "working_dir": "/workspace",
                    "mem_limit": self.memory_limit,
                    "network_disabled": True,
                    "remove": True,
                    "stdout": True,
                    "stderr": True,
                    "environment": {
                        "FFMPEG_PATH": "/usr/bin/ffmpeg",
                        "FFPROBE_PATH": "/usr/bin/ffprobe",
                    },
                }

                start_time = time.time()

                try:
                    result = self.docker_client.containers.run(**container_config)
                    execution_time = time.time() - start_time

                    output = result.decode("utf-8") if isinstance(result, bytes) else str(result)

                    # Check if output file was created
                    output_files = list(container_output.glob("*"))
                    output_info = {}

                    if output_files:
                        output_file = output_files[0]  # Take first output file
                        output_info = {
                            "filename": output_file.name,
                            "size_bytes": output_file.stat().st_size,
                            "path": str(output_file),
                        }

                        # Move output file to permanent location
                        permanent_output = self.output_dir / output_file.name
                        shutil.move(str(output_file), str(permanent_output))
                        output_info["final_path"] = str(permanent_output)

                    return {
                        "success": True,
                        "output": output,
                        "execution_time": execution_time,
                        "command": final_command,
                        "output_file": output_info,
                        "temp_dir": str(temp_path),
                    }

                except Exception as container_error:
                    return {
                        "success": False,
                        "error": f"Container execution failed: {str(container_error)}",
                        "command": final_command,
                        "execution_time": time.time() - start_time,
                    }

        except Exception as e:
            return {
                "success": False,
                "error": f"Media processing setup failed: {str(e)}",
                "command": ffmpeg_command,
            }

    def get_media_info(self, file_path: str) -> Dict[str, Any]:
        """Get media file information using ffprobe"""

        if not Path(file_path).exists():
            return {"success": False, "error": f"File not found: {file_path}"}

        # Use ffprobe to get media information
        ffprobe_command = (
            f"ffprobe -v quiet -print_format json -show_format -show_streams " f"${{input_file}}"
        )

        result = self.execute_ffmpeg_command(
            ffmpeg_command=ffprobe_command, input_files={"input_file": file_path}
        )

        if result["success"]:
            try:
                # Parse JSON output from ffprobe
                media_info = json.loads(result["output"].split("\n")[-2])  # Get JSON from output
                return {"success": True, "media_info": media_info, "file_path": file_path}
            except:
                return {"success": True, "raw_output": result["output"], "file_path": file_path}

        return result
