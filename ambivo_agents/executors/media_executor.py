# ambivo_agents/executors/media_executor.py
"""
Media Docker executor for FFmpeg operations.
"""

import asyncio
import json
import time
import tempfile
import shutil
from pathlib import Path
from typing import Dict, Any

from ..config.loader import load_config, get_config_section

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
                config = get_config_section('media_editor', full_config)
            except Exception:
                config = {}

        self.config = config
        self.work_dir = config.get("work_dir", '/opt/ambivo/work_dir')
        self.docker_image = config.get("docker_image", "sgosain/amb-ubuntu-python-public-pod")
        self.timeout = config.get("timeout", 300)  # 5 minutes for media processing
        self.memory_limit = config.get("memory_limit", "2g")

        # Media specific directories
        self.input_dir = Path(config.get("input_dir", "./media_input"))
        self.output_dir = Path(config.get("output_dir", "./media_output"))

        # Ensure directories exist
        self.input_dir.mkdir(exist_ok=True)
        self.output_dir.mkdir(exist_ok=True)

        if not DOCKER_AVAILABLE:
            raise ImportError("Docker package is required for media processing")

        try:
            self.docker_client = docker.from_env()
            self.docker_client.ping()
            self.available = True
        except Exception as e:
            raise ConnectionError(f"Failed to connect to Docker for media processing: {e}")

    def execute_ffmpeg_command(self,
                               ffmpeg_command: str,
                               input_files: Dict[str, str] = None,
                               output_filename: str = None,
                               work_files: Dict[str, str] = None) -> Dict[str, Any]:
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
                        if Path(host_path).exists():
                            dest_path = container_input / container_name
                            shutil.copy2(host_path, dest_path)
                            file_mapping[container_name] = f"/workspace/input/{container_name}"
                        else:
                            return {
                                'success': False,
                                'error': f'Input file not found: {host_path}',
                                'command': ffmpeg_command
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
                    final_command = final_command.replace("${OUTPUT}", f"/workspace/output/{output_filename}")

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
                    'image': self.docker_image,
                    'command': ["bash", "/workspace/process_media.sh"],
                    'volumes': {str(temp_path): {'bind': '/workspace', 'mode': 'rw'}},
                    'working_dir': '/workspace',
                    'mem_limit': self.memory_limit,
                    'network_disabled': True,
                    'remove': True,
                    'stdout': True,
                    'stderr': True,
                    'environment': {
                        'FFMPEG_PATH': '/usr/bin/ffmpeg',
                        'FFPROBE_PATH': '/usr/bin/ffprobe'
                    }
                }

                start_time = time.time()

                try:
                    result = self.docker_client.containers.run(**container_config)
                    execution_time = time.time() - start_time

                    output = result.decode('utf-8') if isinstance(result, bytes) else str(result)

                    # Check if output file was created
                    output_files = list(container_output.glob("*"))
                    output_info = {}

                    if output_files:
                        output_file = output_files[0]  # Take first output file
                        output_info = {
                            'filename': output_file.name,
                            'size_bytes': output_file.stat().st_size,
                            'path': str(output_file)
                        }

                        # Move output file to permanent location
                        permanent_output = self.output_dir / output_file.name
                        shutil.move(str(output_file), str(permanent_output))
                        output_info['final_path'] = str(permanent_output)

                    return {
                        'success': True,
                        'output': output,
                        'execution_time': execution_time,
                        'command': final_command,
                        'output_file': output_info,
                        'temp_dir': str(temp_path)
                    }

                except Exception as container_error:
                    return {
                        'success': False,
                        'error': f"Container execution failed: {str(container_error)}",
                        'command': final_command,
                        'execution_time': time.time() - start_time
                    }

        except Exception as e:
            return {
                'success': False,
                'error': f"Media processing setup failed: {str(e)}",
                'command': ffmpeg_command
            }

    def get_media_info(self, file_path: str) -> Dict[str, Any]:
        """Get media file information using ffprobe"""

        if not Path(file_path).exists():
            return {
                'success': False,
                'error': f'File not found: {file_path}'
            }

        # Use ffprobe to get media information
        ffprobe_command = (
            f"ffprobe -v quiet -print_format json -show_format -show_streams "
            f"${{input_file}}"
        )

        result = self.execute_ffmpeg_command(
            ffmpeg_command=ffprobe_command,
            input_files={'input_file': file_path}
        )

        if result['success']:
            try:
                # Parse JSON output from ffprobe
                media_info = json.loads(result['output'].split('\n')[-2])  # Get JSON from output
                return {
                    'success': True,
                    'media_info': media_info,
                    'file_path': file_path
                }
            except:
                return {
                    'success': True,
                    'raw_output': result['output'],
                    'file_path': file_path
                }

        return result