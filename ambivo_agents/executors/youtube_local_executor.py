# ambivo_agents/executors/youtube_local_executor.py
"""
Local YouTube executor — downloads videos/audio using pytubefix directly
(no Docker required).  Drop-in replacement for YouTubeDockerExecutor when
``docker.use_docker`` is ``false``.
"""

import json
import logging
import os
import shutil
import time
from pathlib import Path
from typing import Any, Dict

from ..config.loader import get_config_section, load_config
from ..core.docker_shared import get_shared_manager

logger = logging.getLogger(__name__)

try:
    from pytubefix import YouTube
    from pytubefix.cli import on_progress

    PYTUBEFIX_AVAILABLE = True
except ImportError:
    PYTUBEFIX_AVAILABLE = False


class YouTubeLocalExecutor:
    """YouTube downloader that runs pytubefix in-process (no Docker)."""

    def __init__(self, config: Dict[str, Any] = None):
        if config is None:
            try:
                full_config = load_config()
                config = get_config_section("youtube_download", full_config)
            except Exception:
                config = {}

        self.config = config
        self.timeout = config.get("timeout", 600)
        self.default_audio_only = config.get("default_audio_only", True)

        # Shared directory setup (same layout as Docker executor)
        try:
            full_config = load_config()
            docker_config = get_config_section("docker", full_config)
        except Exception:
            docker_config = {}
        shared_base_dir = docker_config.get("shared_base_dir", "./docker_shared")
        self.shared_manager = get_shared_manager(shared_base_dir)
        self.shared_manager.setup_directories()

        self.input_subdir = config.get("input_subdir", "youtube")
        self.output_subdir = config.get("output_subdir", "youtube")
        self.temp_subdir = config.get("temp_subdir", "youtube")
        self.handoff_subdir = config.get("handoff_subdir", "youtube")

        self.input_dir = self.shared_manager.get_host_path(self.input_subdir, "input")
        self.output_dir = self.shared_manager.get_host_path(self.output_subdir, "output")
        self.temp_dir = self.shared_manager.get_host_path(self.temp_subdir, "temp")
        self.handoff_dir = self.shared_manager.get_host_path(self.handoff_subdir, "handoff")

        for d in (self.input_dir, self.output_dir, self.temp_dir, self.handoff_dir):
            d.mkdir(parents=True, exist_ok=True)

        if not PYTUBEFIX_AVAILABLE:
            raise ImportError(
                "pytubefix package is required for local YouTube downloads. "
                "Install it with: pip install pytubefix"
            )

        self.available = True

    # -----------------------------------------------------------------
    # Public API — matches YouTubeDockerExecutor interface
    # -----------------------------------------------------------------

    def download_youtube_video(
        self, url: str, audio_only: bool = None, output_filename: str = None
    ) -> Dict[str, Any]:
        """Download video or audio from YouTube URL (locally, no Docker)."""
        if audio_only is None:
            audio_only = self.default_audio_only

        start_time = time.time()
        try:
            yt = YouTube(url, on_progress_callback=on_progress)
            title = self._sanitize_title(yt.title)
            duration = yt.length
            thumbnail_url = yt.thumbnail_url

            filename_base = self._sanitize_title(output_filename) if output_filename else title
            output_dir_str = str(self.output_dir)

            if audio_only:
                stream = yt.streams.filter(only_audio=True).first()
                if not stream:
                    stream = yt.streams.get_audio_only()
                extension = "mp3"
            else:
                stream = yt.streams.get_highest_resolution()
                if not stream:
                    stream = yt.streams.filter(progressive=True, file_extension="mp4").first()
                extension = "mp4"

            if not stream:
                return {
                    "success": False,
                    "error": "No suitable stream found for this video",
                    "url": url,
                    "execution_time": time.time() - start_time,
                }

            filename = f"{filename_base}.{extension}"
            file_path = stream.download(output_path=output_dir_str, filename=filename)
            file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0

            output_info = {
                "filename": Path(file_path).name,
                "size_bytes": file_size,
                "path": file_path,
                "final_path": file_path,
                "shared_path": file_path,
                "title": title,
                "url": url,
                "thumbnail": thumbnail_url,
                "duration": duration,
                "file_size_bytes": file_size,
            }

            # Copy to shared dir for cross-agent access
            try:
                shared_copy = self.shared_manager.copy_to_shared(file_path)
                output_info["shared_dir_path"] = str(shared_copy)
            except Exception as e:
                logger.debug(f"Failed to copy to shared dir: {e}")

            execution_time = time.time() - start_time
            logger.info(f"Downloaded YouTube {'audio' if audio_only else 'video'}: {title} ({file_size} bytes, {execution_time:.1f}s)")

            return {
                "success": True,
                "output": f"Downloaded: {title}",
                "execution_time": execution_time,
                "url": url,
                "audio_only": audio_only,
                "download_info": output_info,
                "shared_manager": True,
            }

        except Exception as e:
            logger.error(f"YouTube download failed: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"YouTube download failed: {str(e)}",
                "url": url,
                "execution_time": time.time() - start_time,
            }

    def get_video_info(self, url: str) -> Dict[str, Any]:
        """Get video information without downloading."""
        try:
            yt = YouTube(url)
            streams = []
            for s in yt.streams:
                streams.append({
                    "itag": s.itag,
                    "mime_type": s.mime_type,
                    "resolution": getattr(s, "resolution", None),
                    "abr": getattr(s, "abr", None),
                    "fps": getattr(s, "fps", None),
                    "type": s.type,
                })
            return {
                "success": True,
                "title": yt.title,
                "duration": yt.length,
                "thumbnail": yt.thumbnail_url,
                "author": yt.author,
                "views": yt.views,
                "streams": streams,
            }
        except Exception as e:
            return {"success": False, "error": str(e), "url": url}

    def download_playlist(self, url: str, audio_only: bool = None, max_videos: int = 10) -> Dict[str, Any]:
        """Download videos from a YouTube playlist."""
        try:
            from pytubefix import Playlist

            playlist = Playlist(url)
            results = []
            for i, video_url in enumerate(playlist.video_urls[:max_videos]):
                result = self.download_youtube_video(video_url, audio_only=audio_only)
                results.append(result)
            return {
                "success": True,
                "playlist_title": playlist.title,
                "total_videos": len(playlist.video_urls),
                "downloaded": len(results),
                "results": results,
            }
        except Exception as e:
            return {"success": False, "error": str(e), "url": url}

    # -----------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------

    @staticmethod
    def _sanitize_title(title: str) -> str:
        """Remove special characters from the title."""
        for ch in r'\/:"*?<>|':
            title = title.replace(ch, "_")
        sanitized = "".join(c for c in title if c.isalnum() or c in " -_")
        sanitized = " ".join(sanitized.split())[:100]
        return sanitized if sanitized else "youtube_download"
