# ambivo_agents/executors/youtube_executor.py
"""
YouTube Docker executor for downloading videos and audio from YouTube.
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


class YouTubeDockerExecutor:
    """Specialized Docker executor for YouTube downloads with pytubefix"""

    def __init__(self, config: Dict[str, Any] = None):
        # Load from YAML if config not provided
        if config is None:
            try:
                full_config = load_config()
                config = get_config_section('youtube_download', full_config)
            except Exception:
                config = {}

        self.config = config
        self.work_dir = config.get("work_dir", '/opt/ambivo/work_dir')
        self.docker_image = config.get("docker_image", "sgosain/amb-ubuntu-python-public-pod")
        self.timeout = config.get("timeout", 600)  # 10 minutes for downloads
        self.memory_limit = config.get("memory_limit", "1g")

        # YouTube specific directories
        self.download_dir = Path(config.get("download_dir", "./youtube_downloads"))
        self.default_audio_only = config.get("default_audio_only", True)

        # Ensure directories exist
        self.download_dir.mkdir(exist_ok=True)

        if not DOCKER_AVAILABLE:
            raise ImportError("Docker package is required for YouTube downloads")

        try:
            self.docker_client = docker.from_env()
            self.docker_client.ping()
            self.available = True
        except Exception as e:
            raise ConnectionError(f"Failed to connect to Docker for YouTube downloads: {e}")

    def download_youtube_video(self,
                               url: str,
                               audio_only: bool = None,
                               output_filename: str = None) -> Dict[str, Any]:
        """
        Download video or audio from YouTube URL

        Args:
            url: YouTube URL to download
            audio_only: If True, download only audio. If False, download video
            output_filename: Custom filename (optional)
        """
        if audio_only is None:
            audio_only = self.default_audio_only

        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)

                # Create output directory in temp
                container_output = temp_path / "output"
                container_output.mkdir()

                # Create the YouTube download script
                download_script = self._create_download_script(url, audio_only, output_filename)

                script_file = temp_path / "download_youtube.py"
                script_file.write_text(download_script)

                # Create execution script (no pip install needed)
                execution_script = f"""#!/bin/bash
set -e
cd /workspace

echo "Starting YouTube download..."
echo "URL: {url}"
echo "Audio only: {audio_only}"

# Execute the download directly (pytubefix should be pre-installed)
python download_youtube.py

echo "YouTube download completed successfully"
ls -la /workspace/output/
"""

                exec_script_file = temp_path / "run_download.sh"
                exec_script_file.write_text(execution_script)
                exec_script_file.chmod(0o755)

                # Container configuration for YouTube downloads
                container_config = {
                    'image': self.docker_image,
                    'command': ["bash", "/workspace/run_download.sh"],
                    'volumes': {str(temp_path): {'bind': '/workspace', 'mode': 'rw'}},
                    'working_dir': '/workspace',
                    'mem_limit': self.memory_limit,
                    'network_disabled': False,  # Need network for YouTube downloads
                    'remove': True,
                    'stdout': True,
                    'stderr': True,
                    'environment': {
                        'PYTHONUNBUFFERED': '1',
                        'PYTHONPATH': '/workspace'
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
                        downloaded_file = output_files[0]  # Take first output file
                        output_info = {
                            'filename': downloaded_file.name,
                            'size_bytes': downloaded_file.stat().st_size,
                            'path': str(downloaded_file)
                        }

                        # Move output file to permanent location
                        permanent_output = self.download_dir / downloaded_file.name
                        shutil.move(str(downloaded_file), str(permanent_output))
                        output_info['final_path'] = str(permanent_output)

                        # Try to parse JSON result from the script output
                        try:
                            # Look for JSON in the output
                            for line in output.split('\n'):
                                if line.strip().startswith('{') and 'file_path' in line:
                                    download_result = json.loads(line.strip())
                                    output_info.update(download_result)
                                    break
                        except:
                            pass  # JSON parsing failed, use basic info

                    return {
                        'success': True,
                        'output': output,
                        'execution_time': execution_time,
                        'url': url,
                        'audio_only': audio_only,
                        'download_info': output_info,
                        'temp_dir': str(temp_path)
                    }

                except Exception as container_error:
                    return {
                        'success': False,
                        'error': f"Container execution failed: {str(container_error)}",
                        'url': url,
                        'execution_time': time.time() - start_time
                    }

        except Exception as e:
            return {
                'success': False,
                'error': f"YouTube download setup failed: {str(e)}",
                'url': url
            }

    def _create_download_script(self, url: str, audio_only: bool, output_filename: str = None) -> str:
        """Create the Python script for downloading from YouTube"""

        script = f'''#!/usr/bin/env python3
"""
YouTube downloader script using pytubefix
"""

import os
import json
import sys
from pathlib import Path

# Import required modules (should be pre-installed in container)
try:
    from pydantic import BaseModel, Field
    from pytubefix import YouTube
    from pytubefix.cli import on_progress
except ImportError as e:
    print(f"Import error: {{e}}", file=sys.stderr)
    print("Required packages not available in container", file=sys.stderr)
    sys.exit(1)


class DownloadResult(BaseModel):
    file_path: str = Field(..., description="Path where the downloaded file is stored.")
    title: str = Field(..., description="Sanitized title of the YouTube video.")
    url: str = Field(..., description="Original URL of the YouTube video.")
    thumbnail: str = Field(..., description="Thumbnail URL of the YouTube video.")
    duration: int = Field(..., description="Duration of the video in seconds.")
    file_size_bytes: int = Field(..., description="Size of the downloaded file in bytes.")


def sanitize_title(title: str) -> str:
    """Remove special characters from the title."""
    # Remove/replace problematic characters
    title = title.replace('/', '_')
    title = title.replace('\\\\', '_')
    title = title.replace(':', '_')
    title = title.replace('*', '_')
    title = title.replace('?', '_')
    title = title.replace('"', '_')
    title = title.replace('<', '_')
    title = title.replace('>', '_')
    title = title.replace('|', '_')

    # Keep only alphanumeric, spaces, hyphens, underscores
    sanitized = ''.join(c for c in title if c.isalnum() or c in ' -_')

    # Remove extra spaces and limit length
    sanitized = ' '.join(sanitized.split())[:100]

    return sanitized if sanitized else 'youtube_download'


def download_yt(url: str, audio_only: bool = True, output_dir: str = ".", custom_filename: str = None) -> DownloadResult:
    """Download audio or video from a YouTube URL."""
    try:
        # Create YouTube object
        yt = YouTube(url, on_progress_callback=on_progress)

        # Get video info
        title = sanitize_title(yt.title)
        duration = yt.length
        thumbnail_url = yt.thumbnail_url

        # Use custom filename if provided
        filename_base = custom_filename if custom_filename else title
        filename_base = sanitize_title(filename_base)

        if audio_only:
            # Get audio stream
            stream = yt.streams.filter(only_audio=True).first()
            if not stream:
                stream = yt.streams.get_audio_only()

            extension = "mp3"
            filename = filename_base + "." + extension
            file_path = stream.download(output_path=output_dir, filename=filename)
        else:
            # Get highest resolution video stream
            stream = yt.streams.get_highest_resolution()
            if not stream:
                stream = yt.streams.filter(progressive=True, file_extension='mp4').first()

            extension = "mp4"
            filename = filename_base + "." + extension
            file_path = stream.download(output_path=output_dir, filename=filename)

        # Get file size
        file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0

        return DownloadResult(
            file_path=file_path,
            title=title,
            url=url,
            thumbnail=thumbnail_url,
            duration=duration,
            file_size_bytes=file_size
        )

    except Exception as e:
        print(f"Error downloading {{url}}: {{e}}", file=sys.stderr)
        raise


if __name__ == '__main__':
    try:
        url = "{url}"
        audio_only = {audio_only}  # This will be True or False, not string
        output_dir = "/workspace/output"
        custom_filename = {f'"{output_filename}"' if output_filename else 'None'}

        print(f"Downloading from: {{url}}")
        print(f"Audio only: {{audio_only}}")
        print(f"Output directory: {{output_dir}}")

        # Perform download
        result = download_yt(
            url=url,
            audio_only=audio_only,
            output_dir=output_dir,
            custom_filename=custom_filename
        )

        # Output result as JSON for parsing
        print("\\n" + "="*50)
        print("DOWNLOAD RESULT:")
        print(result.model_dump_json(indent=2))
        print("="*50)

    except Exception as e:
        print(f"Download failed: {{e}}", file=sys.stderr)
        sys.exit(1)
'''

        return script

    def get_video_info(self, url: str) -> Dict[str, Any]:
        """Get video information without downloading"""

        info_script = f'''#!/usr/bin/env python3
import json
import sys

try:
    from pytubefix import YouTube
except ImportError as e:
    print(f"Error: pytubefix not available: {{e}}", file=sys.stderr)
    sys.exit(1)

try:
    yt = YouTube("{url}")

    info = {{
        "title": yt.title,
        "duration": yt.length,
        "views": yt.views,
        "thumbnail_url": yt.thumbnail_url,
        "description": yt.description[:500] + "..." if len(yt.description) > 500 else yt.description,
        "author": yt.author,
        "publish_date": yt.publish_date.isoformat() if yt.publish_date else None,
        "available_streams": {{
            "audio_streams": len(yt.streams.filter(only_audio=True)),
            "video_streams": len(yt.streams.filter(progressive=True)),
            "highest_resolution": str(yt.streams.get_highest_resolution()),
            "audio_only": str(yt.streams.get_audio_only())
        }}
    }}

    print(json.dumps(info, indent=2))

except Exception as e:
    print(f"Error getting video info: {{e}}", file=sys.stderr)
    sys.exit(1)
'''

        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)

                script_file = temp_path / "get_info.py"
                script_file.write_text(info_script)

                container_config = {
                    'image': self.docker_image,
                    'command': ["python", "/workspace/get_info.py"],
                    'volumes': {str(temp_path): {'bind': '/workspace', 'mode': 'rw'}},
                    'working_dir': '/workspace',
                    'mem_limit': self.memory_limit,
                    'network_disabled': False,
                    'remove': True,
                    'stdout': True,
                    'stderr': True
                }

                result = self.docker_client.containers.run(**container_config)
                output = result.decode('utf-8') if isinstance(result, bytes) else str(result)

                try:
                    video_info = json.loads(output.strip())
                    return {
                        'success': True,
                        'video_info': video_info,
                        'url': url
                    }
                except json.JSONDecodeError:
                    return {
                        'success': False,
                        'error': 'Failed to parse video info',
                        'raw_output': output
                    }

        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'url': url
            }