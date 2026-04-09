# ambivo_agents/executors/youtube_executor.py
"""
YouTube Docker executor for downloading videos and audio from YouTube.
Uses yt-dlp for reliable downloads with built-in bot-detection handling.
"""

import asyncio
import json
import logging
import os
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


class YouTubeDockerExecutor:
    """Specialized Docker executor for YouTube downloads with yt-dlp"""

    def __init__(self, config: Dict[str, Any] = None):
        # Load from YAML if config not provided
        if config is None:
            try:
                full_config = load_config()
                config = get_config_section("youtube_download", full_config)
            except Exception:
                config = {}

        self.config = config
        self.work_dir = config.get("work_dir", "/opt/ambivo/work_dir")
        self.docker_image = config.get("docker_image", "sgosain/amb-ubuntu-python-public-pod")
        self.timeout = config.get("timeout", 600)  # 10 minutes for downloads
        self.memory_limit = config.get("memory_limit", "1g")

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
        self.input_subdir = config.get("input_subdir", "youtube")
        self.output_subdir = config.get("output_subdir", "youtube")
        self.temp_subdir = config.get("temp_subdir", "youtube")
        self.handoff_subdir = config.get("handoff_subdir", "youtube")

        # Set up proper directories using DockerSharedManager
        self.input_dir = self.shared_manager.get_host_path(self.input_subdir, "input")
        self.output_dir = self.shared_manager.get_host_path(self.output_subdir, "output")
        self.temp_dir = self.shared_manager.get_host_path(self.temp_subdir, "temp")
        self.handoff_dir = self.shared_manager.get_host_path(self.handoff_subdir, "handoff")

        self.default_audio_only = config.get("default_audio_only", True)

        # Ensure all directories exist
        self.input_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.handoff_dir.mkdir(parents=True, exist_ok=True)

        if not DOCKER_AVAILABLE:
            raise ImportError("Docker package is required for YouTube downloads")

        try:
            self.docker_client = docker.from_env()
            self.docker_client.ping()
            self.available = True
        except Exception as e:
            raise ConnectionError(f"Failed to connect to Docker for YouTube downloads: {e}")

    def download_youtube_video(
        self, url: str, audio_only: bool = None, output_filename: str = None
    ) -> Dict[str, Any]:
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

                # Create execution script
                execution_script = f"""#!/bin/bash
set -e
cd /workspace

echo "Starting YouTube download..."
echo "URL: {url}"
echo "Audio only: {audio_only}"

# Execute the download (yt-dlp should be pre-installed)
python download_youtube.py

echo "YouTube download completed successfully"
ls -la /workspace/output/
"""

                exec_script_file = temp_path / "run_download.sh"
                exec_script_file.write_text(execution_script)
                exec_script_file.chmod(0o755)

                # Build container environment — pass through cookie/auth env vars
                container_env = {"PYTHONUNBUFFERED": "1", "PYTHONPATH": "/workspace"}
                for key in ("YT_DLP_COOKIES_FILE", "YT_DLP_COOKIES_FROM_BROWSER", "YT_DLP_COOKIES_BASE64", "YT_DLP_PROXY"):
                    val = os.environ.get(key)
                    if val:
                        container_env[key] = val

                # Container configuration for YouTube downloads
                container_config = {
                    "image": self.docker_image,
                    "command": ["bash", "/workspace/run_download.sh"],
                    "volumes": {str(temp_path): {"bind": "/workspace", "mode": "rw"}},
                    "working_dir": "/workspace",
                    "mem_limit": self.memory_limit,
                    "network_disabled": False,  # Need network for YouTube downloads
                    "remove": True,
                    "stdout": True,
                    "stderr": True,
                    "environment": container_env,
                }

                start_time = time.time()

                try:
                    # Run with detach and enforce timeout
                    container_config["remove"] = False
                    container_config["detach"] = True
                    container = self.docker_client.containers.run(**container_config)
                    try:
                        exit_result = container.wait(timeout=self.timeout)
                        exit_code = exit_result.get("StatusCode", -1)
                        result = container.logs(stdout=True, stderr=True)
                    except Exception:
                        container.kill()
                        container.remove(force=True)
                        raise TimeoutError(f"YouTube download exceeded {self.timeout}s timeout")
                    finally:
                        try:
                            container.remove(force=True)
                        except Exception:
                            pass
                    execution_time = time.time() - start_time

                    output = result.decode("utf-8") if isinstance(result, bytes) else str(result)

                    if exit_code != 0:
                        logging.error(f"YouTube download container exited with code {exit_code}. Output:\n{output}")
                        return {
                            "success": False,
                            "error": f"Download failed (exit code {exit_code}): {output[:500]}",
                            "url": url,
                            "execution_time": execution_time,
                        }

                    # Check if output file was created
                    output_files = list(container_output.glob("*"))
                    output_info = {}

                    # Try to parse JSON result from the script output
                    try:
                        json_lines = []
                        capturing = False
                        for line in output.split("\n"):
                            if "DOWNLOAD RESULT:" in line:
                                capturing = True
                                continue
                            if capturing:
                                if line.strip().startswith("="):
                                    break
                                json_lines.append(line)
                        if json_lines:
                            download_result = json.loads("\n".join(json_lines))
                            output_info.update(download_result)
                    except (json.JSONDecodeError, ValueError) as e:
                        logging.warning(f"Failed to parse download metadata: {e}")

                    if output_files:
                        downloaded_file = output_files[0]  # Take first output file
                        output_info["filename"] = downloaded_file.name
                        output_info["size_bytes"] = downloaded_file.stat().st_size
                        output_info["path"] = str(downloaded_file)

                        # Move output file to agent output directory
                        shared_output = self.output_dir / downloaded_file.name
                        shutil.move(str(downloaded_file), str(shared_output))
                        output_info["final_path"] = str(shared_output)
                        output_info["shared_path"] = str(shared_output)

                        # Also copy to the shared directory for cross-agent access
                        try:
                            shared_copy = self.shared_manager.copy_to_shared(str(shared_output))
                            output_info["shared_dir_path"] = str(shared_copy)
                        except Exception as e:
                            logging.debug(f"Failed to copy to shared dir: {e}")

                        return {
                            "success": True,
                            "output": output,
                            "execution_time": execution_time,
                            "url": url,
                            "audio_only": audio_only,
                            "download_info": output_info,
                            "temp_dir": str(temp_path),
                            "shared_manager": True,
                        }
                    else:
                        logging.error(f"No output files found in {container_output}. Container output:\n{output}")
                        return {
                            "success": False,
                            "error": f"Download completed but no output files were produced. Container output: {output[:500]}",
                            "url": url,
                            "execution_time": execution_time,
                        }

                except Exception as container_error:
                    return {
                        "success": False,
                        "error": f"Container execution failed: {str(container_error)}",
                        "url": url,
                        "execution_time": time.time() - start_time,
                    }

        except Exception as e:
            return {
                "success": False,
                "error": f"YouTube download setup failed: {str(e)}",
                "url": url,
            }

    def _create_download_script(
        self, url: str, audio_only: bool, output_filename: str = None
    ) -> str:
        """Create the Python script for downloading from YouTube using yt-dlp"""

        script = f'''#!/usr/bin/env python3
"""
YouTube downloader script using yt-dlp
"""

import base64
import os
import json
import sys
import tempfile
from pathlib import Path

try:
    import yt_dlp
except ImportError as e:
    print(f"Import error: {{e}}", file=sys.stderr)
    print("yt-dlp not available in container. Install with: pip install yt-dlp", file=sys.stderr)
    sys.exit(1)


def sanitize_title(title: str) -> str:
    """Remove special characters from the title."""
    for ch in '\\\\/:*?"<>|':
        title = title.replace(ch, '_')
    sanitized = ''.join(c for c in title if c.isalnum() or c in ' -_')
    sanitized = ' '.join(sanitized.split())[:100]
    return sanitized if sanitized else 'youtube_download'


def resolve_cookies_file():
    """Resolve cookies file from env vars (file path or base64)."""
    path = os.environ.get("YT_DLP_COOKIES_FILE")
    if path and os.path.isfile(path):
        return path
    b64 = os.environ.get("YT_DLP_COOKIES_BASE64")
    if b64:
        content = base64.b64decode(b64)
        fd, tmp = tempfile.mkstemp(prefix="yt_cookies_", suffix=".txt")
        with os.fdopen(fd, "wb") as f:
            f.write(content)
        return tmp
    return None


if __name__ == '__main__':
    try:
        url = json.loads({json.dumps(json.dumps(url))})
        audio_only = {audio_only}
        output_dir = "/workspace/output"
        custom_filename = json.loads({json.dumps(json.dumps(output_filename)) if output_filename else '"null"'})

        print(f"Downloading from: {{url}}")
        print(f"Audio only: {{audio_only}}")
        print(f"Output directory: {{output_dir}}")

        cookies_file = resolve_cookies_file()
        proxy = os.environ.get("YT_DLP_PROXY")

        # Extract info first
        info_opts = {{"quiet": True, "no_warnings": True, "skip_download": True}}
        if cookies_file:
            info_opts["cookiefile"] = cookies_file
        if proxy:
            info_opts["proxy"] = proxy

        with yt_dlp.YoutubeDL(info_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        title = sanitize_title(info.get("title", "youtube_download"))
        duration = info.get("duration", 0)
        thumbnail_url = info.get("thumbnail", "")

        filename_base = sanitize_title(custom_filename) if custom_filename else title
        extension = "mp3" if audio_only else "mp4"
        filename = f"{{filename_base}}.{{extension}}"

        # Download options
        dl_opts = {{
            "quiet": True,
            "no_warnings": True,
            "paths": {{"home": output_dir}},
            "outtmpl": {{"default": filename}},
        }}
        if cookies_file:
            dl_opts["cookiefile"] = cookies_file
        if proxy:
            dl_opts["proxy"] = proxy

        if audio_only:
            dl_opts["format"] = "bestaudio/best"
            dl_opts["postprocessors"] = [{{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }}]
        else:
            dl_opts["format"] = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
            dl_opts["merge_output_format"] = "mp4"

        with yt_dlp.YoutubeDL(dl_opts) as ydl:
            ydl.download([url])

        # Find the output file
        file_path = os.path.join(output_dir, filename)
        if not os.path.exists(file_path):
            import glob
            matches = glob.glob(os.path.join(output_dir, f"{{filename_base}}.*"))
            if matches:
                file_path = matches[0]
                filename = os.path.basename(file_path)

        file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0

        result = {{
            "file_path": file_path,
            "title": title,
            "url": url,
            "thumbnail": thumbnail_url,
            "duration": duration,
            "file_size_bytes": file_size,
        }}

        print("\\n" + "="*50)
        print("DOWNLOAD RESULT:")
        print(json.dumps(result, indent=2))
        print("="*50)

    except Exception as e:
        print(f"Download failed: {{e}}", file=sys.stderr)
        sys.exit(1)
'''

        return script

    def get_video_info(self, url: str) -> Dict[str, Any]:
        """Get video information without downloading"""

        info_script = f"""#!/usr/bin/env python3
import base64
import json
import os
import sys
import tempfile

try:
    import yt_dlp
except ImportError as e:
    print(f"Error: yt-dlp not available: {{e}}", file=sys.stderr)
    sys.exit(1)

def resolve_cookies_file():
    path = os.environ.get("YT_DLP_COOKIES_FILE")
    if path and os.path.isfile(path):
        return path
    b64 = os.environ.get("YT_DLP_COOKIES_BASE64")
    if b64:
        content = base64.b64decode(b64)
        fd, tmp = tempfile.mkstemp(prefix="yt_cookies_", suffix=".txt")
        with os.fdopen(fd, "wb") as f:
            f.write(content)
        return tmp
    return None

try:
    opts = {{"quiet": True, "no_warnings": True, "skip_download": True}}
    cookies_file = resolve_cookies_file()
    if cookies_file:
        opts["cookiefile"] = cookies_file
    proxy = os.environ.get("YT_DLP_PROXY")
    if proxy:
        opts["proxy"] = proxy

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info("{url}", download=False)

    formats = info.get("formats") or []
    audio_formats = [f for f in formats if f.get("acodec") != "none" and f.get("vcodec") == "none"]
    video_formats = [f for f in formats if f.get("vcodec") != "none"]

    result = {{
        "title": info.get("title"),
        "duration": info.get("duration"),
        "views": info.get("view_count"),
        "thumbnail_url": info.get("thumbnail"),
        "description": (info.get("description") or "")[:500],
        "author": info.get("uploader") or info.get("channel"),
        "publish_date": info.get("upload_date"),
        "available_streams": {{
            "audio_streams": len(audio_formats),
            "video_streams": len(video_formats),
            "total_formats": len(formats),
        }}
    }}

    print(json.dumps(result, indent=2))

except Exception as e:
    print(f"Error getting video info: {{e}}", file=sys.stderr)
    sys.exit(1)
"""

        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)

                script_file = temp_path / "get_info.py"
                script_file.write_text(info_script)

                container_env = {"PYTHONUNBUFFERED": "1"}
                for key in ("YT_DLP_COOKIES_FILE",):
                    val = os.environ.get(key)
                    if val:
                        container_env[key] = val

                container_config = {
                    "image": self.docker_image,
                    "command": ["python", "/workspace/get_info.py"],
                    "volumes": {str(temp_path): {"bind": "/workspace", "mode": "rw"}},
                    "working_dir": "/workspace",
                    "mem_limit": self.memory_limit,
                    "network_disabled": False,
                    "remove": True,
                    "stdout": True,
                    "stderr": True,
                    "environment": container_env,
                }

                result = self.docker_client.containers.run(**container_config)
                output = result.decode("utf-8") if isinstance(result, bytes) else str(result)

                try:
                    video_info = json.loads(output.strip())
                    return {"success": True, "video_info": video_info, "url": url}
                except json.JSONDecodeError:
                    return {
                        "success": False,
                        "error": "Failed to parse video info",
                        "raw_output": output,
                    }

        except Exception as e:
            return {"success": False, "error": str(e), "url": url}
