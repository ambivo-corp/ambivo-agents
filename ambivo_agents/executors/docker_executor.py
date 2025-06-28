# ambivo_agents/executors/docker_executor.py
"""
Docker executor for secure code execution.
"""

import time
import tempfile
from pathlib import Path
from typing import Dict, Any

from ..config.loader import load_config, get_config_section

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
                config = get_config_section('docker', full_config)
            except Exception:
                config = {}

        self.config = config
        self.work_dir = config.get("work_dir", '/opt/ambivo/work_dir')
        self.docker_images = config.get("images", ["sgosain/amb-ubuntu-python-public-pod"])
        self.timeout = config.get("timeout", 60)
        self.memory_limit = config.get("memory_limit", "512m")
        self.default_image = self.docker_images[0] if self.docker_images else "sgosain/amb-ubuntu-python-public-pod"

        if not DOCKER_AVAILABLE:
            raise ImportError("Docker package is required but not installed")

        try:
            self.docker_client = docker.from_env()
            self.docker_client.ping()
            self.available = True
        except Exception as e:
            raise ConnectionError(f"Failed to connect to Docker: {e}")

    def execute_code(self, code: str, language: str = "python", files: Dict[str, str] = None) -> Dict[str, Any]:
        """Execute code in Docker container"""
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
                    'image': self.default_image,
                    'command': cmd,
                    'volumes': {str(temp_path): {'bind': '/workspace', 'mode': 'rw'}},
                    'working_dir': '/workspace',
                    'mem_limit': self.memory_limit,
                    'network_disabled': True,
                    'remove': True,
                    'stdout': True,
                    'stderr': True
                }

                start_time = time.time()
                container = self.docker_client.containers.run(**container_config)
                execution_time = time.time() - start_time

                output = container.decode('utf-8') if isinstance(container, bytes) else str(container)

                return {
                    'success': True,
                    'output': output,
                    'execution_time': execution_time,
                    'language': language
                }

        except docker.errors.ContainerError as e:
            return {
                'success': False,
                'error': f"Container error: {e.stderr.decode('utf-8') if e.stderr else 'Unknown error'}",
                'exit_code': e.exit_status,
                'language': language
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'language': language
            }
