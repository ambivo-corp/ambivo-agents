# ambivo_agents/executors/docker_executor.py
"""
Docker executor for secure code execution.
"""

import os
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, Optional

from ..config.loader import get_config_section, load_config
from ..core.docker_shared import DockerSharedManager, get_shared_manager

try:
    import docker

    DOCKER_AVAILABLE = True
except ImportError:
    DOCKER_AVAILABLE = False


class DockerCodeExecutor:
    """Secure code execution using Docker containers"""

    def __init__(self, config: Dict[str, Any] = None):
        # Load from YAML if config not provided
        if config is None:
            try:
                full_config = load_config()
                config = get_config_section("docker", full_config)
            except Exception:
                config = {}

        self.config = config
        self.work_dir = config.get("work_dir", "/opt/ambivo/work_dir")
        self.docker_images = config.get("images", ["sgosain/amb-ubuntu-python-public-pod"])
        self.timeout = config.get("timeout", 60)
        self.memory_limit = config.get("memory_limit", "512m")
        self.default_image = (
            self.docker_images[0] if self.docker_images else "sgosain/amb-ubuntu-python-public-pod"
        )

        # Initialize Docker shared manager with configured base directory
        shared_base_dir = config.get("shared_base_dir", "./docker_shared")
        self.shared_manager = get_shared_manager(shared_base_dir)
        self.shared_manager.setup_directories()

        # Get agent-specific subdirectory names from config
        self.input_subdir = config.get("input_subdir", "code")
        self.output_subdir = config.get("output_subdir", "code")
        self.temp_subdir = config.get("temp_subdir", "code")
        self.handoff_subdir = config.get("handoff_subdir", "code")

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
            raise ImportError("Docker package is required but not installed")

        try:
            self.docker_client = docker.from_env()
            self.docker_client.ping()
            self.available = True
        except Exception as e:
            raise ConnectionError(f"Failed to connect to Docker: {e}")

    def execute_code(
        self,
        code: str,
        language: str = "python",
        files: Dict[str, str] = None,
        input_files: Dict[str, str] = None,
        use_shared_dirs: bool = True,
    ) -> Dict[str, Any]:
        """Execute code in Docker container with shared directory support"""
        try:
            if use_shared_dirs:
                # Use Docker shared directory structure
                return self._execute_code_with_shared_dirs(code, language, files, input_files)
            else:
                # Use legacy temporary directory approach
                return self._execute_code_legacy(code, language, files)
        except Exception as e:
            return {
                "success": False,
                "error": f"Code execution failed: {str(e)}",
                "language": language,
            }

    def _execute_code_with_shared_dirs(
        self,
        code: str,
        language: str,
        files: Dict[str, str] = None,
        input_files: Dict[str, str] = None,
    ) -> Dict[str, Any]:
        """Execute code using Docker shared directory structure"""

        # Prepare Docker volumes using shared manager
        volumes = self.shared_manager.get_docker_volumes()

        # Set up workspace directories
        workspace_input = self.shared_manager.get_container_path(self.input_subdir, "input")
        workspace_output = self.shared_manager.get_container_path(self.output_subdir, "output")
        workspace_temp = self.shared_manager.get_container_path(self.temp_subdir, "temp")

        # Copy input files to shared input directory
        if input_files:
            for filename, source_path in input_files.items():
                resolved_path = self.shared_manager.resolve_input_file(
                    source_path, self.input_subdir
                )
                if resolved_path:
                    self.shared_manager.copy_to_input(
                        str(resolved_path), self.input_subdir, filename
                    )

        # Create code file in temp directory
        if language == "python":
            code_file = self.temp_dir / "code.py"
            code_file.write_text(code)
            cmd = ["python", f"{workspace_temp}/code.py"]
        elif language == "bash":
            code_file = self.temp_dir / "script.sh"
            code_file.write_text(code)
            code_file.chmod(0o755)
            cmd = ["bash", f"{workspace_temp}/script.sh"]
        else:
            raise ValueError(f"Unsupported language: {language}")

        # Create additional files in temp directory
        if files:
            for filename, content in files.items():
                file_path = self.temp_dir / filename
                file_path.write_text(content)

        container_config = {
            "image": self.default_image,
            "command": cmd,
            "volumes": volumes,
            "working_dir": workspace_temp,
            "mem_limit": self.memory_limit,
            "network_disabled": True,
            "remove": True,
            "stdout": True,
            "stderr": True,
            "environment": {
                "DOCKER_INPUT_DIR": workspace_input,
                "DOCKER_OUTPUT_DIR": workspace_output,
                "DOCKER_TEMP_DIR": workspace_temp,
            },
        }

        start_time = time.time()
        container = self.docker_client.containers.run(**container_config)
        execution_time = time.time() - start_time

        output = container.decode("utf-8") if isinstance(container, bytes) else str(container)

        # List output files
        output_files = self.shared_manager.list_outputs(self.output_subdir)

        return {
            "success": True,
            "output": output,
            "execution_time": execution_time,
            "language": language,
            "output_files": output_files,
            "shared_manager": True,
            "directories": {
                "input": str(self.input_dir),
                "output": str(self.output_dir),
                "temp": str(self.temp_dir),
                "handoff": str(self.handoff_dir),
            },
        }

    def _execute_code_legacy(
        self, code: str, language: str, files: Dict[str, str] = None
    ) -> Dict[str, Any]:
        """Execute code using legacy temporary directory approach"""
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)

                if language == "python":
                    code_file = temp_path / "code.py"
                    code_file.write_text(code)
                    cmd = ["python", "/workspace/code.py"]
                elif language == "bash":
                    code_file = temp_path / "script.sh"
                    code_file.write_text(code)
                    cmd = ["bash", "/workspace/script.sh"]
                else:
                    raise ValueError(f"Unsupported language: {language}")

                if files:
                    for filename, content in files.items():
                        file_path = temp_path / filename
                        file_path.write_text(content)

                container_config = {
                    "image": self.default_image,
                    "command": cmd,
                    "volumes": {str(temp_path): {"bind": "/workspace", "mode": "rw"}},
                    "working_dir": "/workspace",
                    "mem_limit": self.memory_limit,
                    "network_disabled": True,
                    "remove": True,
                    "stdout": True,
                    "stderr": True,
                }

                start_time = time.time()
                container = self.docker_client.containers.run(**container_config)
                execution_time = time.time() - start_time

                output = (
                    container.decode("utf-8") if isinstance(container, bytes) else str(container)
                )

                return {
                    "success": True,
                    "output": output,
                    "execution_time": execution_time,
                    "language": language,
                    "shared_manager": False,
                }

        except docker.errors.ContainerError as e:
            return {
                "success": False,
                "error": f"Container error: {e.stderr.decode('utf-8') if e.stderr else 'Unknown error'}",
                "exit_code": e.exit_status,
                "language": language,
            }
        except Exception as e:
            return {"success": False, "error": str(e), "language": language}

    def execute_code_with_host_files(
        self,
        code: str,
        language: str = "python",
        host_input_dir: Optional[str] = None,
        host_output_dir: Optional[str] = None,
        files: Dict[str, str] = None,
    ) -> Dict[str, Any]:
        """
        Execute code in Docker container with access to host directories for file operations.
        This is essential for fallback scenarios where files need to be shared between agents.
        """
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)

                if language == "python":
                    code_file = temp_path / "code.py"
                    code_file.write_text(code)
                    cmd = ["python", "/workspace/code.py"]
                elif language == "bash":
                    code_file = temp_path / "script.sh"
                    code_file.write_text(code)
                    cmd = ["bash", "/workspace/script.sh"]
                else:
                    raise ValueError(f"Unsupported language: {language}")

                # Add any additional files to the temp directory
                if files:
                    for filename, content in files.items():
                        file_path = temp_path / filename
                        file_path.write_text(content)

                # Setup volume mounts
                volumes = {str(temp_path): {"bind": "/workspace", "mode": "rw"}}

                # Mount host input directory if provided (read-only for security)
                if host_input_dir and os.path.exists(host_input_dir):
                    volumes[os.path.abspath(host_input_dir)] = {"bind": "/host_input", "mode": "ro"}

                # Mount host output directory if provided (read-write for file creation)
                if host_output_dir:
                    # Create output directory if it doesn't exist
                    os.makedirs(host_output_dir, exist_ok=True)
                    volumes[os.path.abspath(host_output_dir)] = {
                        "bind": "/host_output",
                        "mode": "rw",
                    }

                container_config = {
                    "image": self.default_image,
                    "command": cmd,
                    "volumes": volumes,
                    "working_dir": "/workspace",
                    "mem_limit": self.memory_limit,
                    "network_disabled": True,
                    "remove": True,
                    "stdout": True,
                    "stderr": True,
                }

                start_time = time.time()
                container = self.docker_client.containers.run(**container_config)
                execution_time = time.time() - start_time

                output = (
                    container.decode("utf-8") if isinstance(container, bytes) else str(container)
                )

                return {
                    "success": True,
                    "output": output,
                    "execution_time": execution_time,
                    "language": language,
                    "host_input_dir": host_input_dir,
                    "host_output_dir": host_output_dir,
                }

        except docker.errors.ContainerError as e:
            return {
                "success": False,
                "error": f"Container error: {e.stderr.decode('utf-8') if e.stderr else 'Unknown error'}",
                "exit_code": e.exit_status,
                "language": language,
            }
        except Exception as e:
            return {"success": False, "error": str(e), "language": language}
