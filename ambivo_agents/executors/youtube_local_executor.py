# ambivo_agents/executors/youtube_local_executor.py
"""
Local YouTube executor — downloads videos/audio using yt-dlp directly
(no Docker required).  Drop-in replacement for YouTubeDockerExecutor when
``docker.use_docker`` is ``false``.
"""

import base64
import json
import logging
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Dict

from ..config.loader import get_config_section, load_config
from ..core.docker_shared import get_shared_manager

logger = logging.getLogger(__name__)

try:
    import yt_dlp

    YT_DLP_AVAILABLE = True
except ImportError:
    YT_DLP_AVAILABLE = False


class YouTubeLocalExecutor:
    """YouTube downloader that runs yt-dlp in-process (no Docker)."""

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

        if not YT_DLP_AVAILABLE:
            raise ImportError(
                "yt-dlp package is required for local YouTube downloads. "
                "Install it with: pip install yt-dlp"
            )

        self.available = True

    # -----------------------------------------------------------------
    # yt-dlp option helpers
    # -----------------------------------------------------------------

    def _get_cookies_file(self) -> str | None:
        """Resolve a cookies file path from env vars.

        Supports three modes (checked in order):
          1. YT_DLP_COOKIES_FILE  — path to an existing Netscape cookies.txt
          2. YT_DLP_COOKIES_BASE64 — base64-encoded cookies.txt content
             (decoded once and written to a temp file that lives for the
              lifetime of this executor instance)
          3. YT_DLP_COOKIES_FROM_BROWSER — browser name (local dev only)
        """
        # Already resolved?
        if hasattr(self, "_cookies_path") and self._cookies_path:
            if os.path.isfile(self._cookies_path):
                return self._cookies_path

        # 1. Explicit file path
        path = os.environ.get("YT_DLP_COOKIES_FILE")
        if path and os.path.isfile(path):
            self._cookies_path = path
            return path

        # 2. Base64-encoded content → write to temp file
        b64 = os.environ.get("YT_DLP_COOKIES_BASE64")
        if b64:
            try:
                content = base64.b64decode(b64)
                fd, tmp_path = tempfile.mkstemp(prefix="yt_cookies_", suffix=".txt")
                with os.fdopen(fd, "wb") as f:
                    f.write(content)
                self._cookies_path = tmp_path
                logger.info(f"Wrote cookies from YT_DLP_COOKIES_BASE64 to {tmp_path}")
                return tmp_path
            except Exception as e:
                logger.warning(f"Failed to decode YT_DLP_COOKIES_BASE64: {e}")

        self._cookies_path = None
        return None

    def _base_opts(self, output_dir: str, filename_template: str = None) -> dict:
        """Build base yt-dlp options with cookie/auth support."""
        opts = {
            "quiet": True,
            "no_warnings": True,
            "paths": {"home": output_dir},
            "socket_timeout": 30,
        }
        if filename_template:
            opts["outtmpl"] = {"default": filename_template}

        # Cookie-based auth (most reliable for servers)
        cookies_file = self._get_cookies_file()
        cookies_browser = os.environ.get("YT_DLP_COOKIES_FROM_BROWSER")
        if cookies_file:
            opts["cookiefile"] = cookies_file
        elif cookies_browser:
            opts["cookiesfrombrowser"] = (cookies_browser,)

        # Proxy support (e.g. "socks5://user:pass@host:port" or "http://host:port")
        proxy = os.environ.get("YT_DLP_PROXY")
        if proxy:
            opts["proxy"] = proxy

        return opts

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
            # First extract info to get metadata
            info_opts = self._base_opts(str(self.output_dir))
            info_opts["skip_download"] = True
            with yt_dlp.YoutubeDL(info_opts) as ydl:
                info = ydl.extract_info(url, download=False)

            title = self._sanitize_title(info.get("title", "youtube_download"))
            duration = info.get("duration", 0)
            thumbnail_url = info.get("thumbnail", "")

            filename_base = self._sanitize_title(output_filename) if output_filename else title
            extension = "mp3" if audio_only else "mp4"
            filename = f"{filename_base}.{extension}"

            # Download
            dl_opts = self._base_opts(str(self.output_dir), filename)
            if audio_only:
                dl_opts["format"] = "bestaudio/best"
                dl_opts["postprocessors"] = [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }]
            else:
                dl_opts["format"] = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
                dl_opts["merge_output_format"] = "mp4"

            with yt_dlp.YoutubeDL(dl_opts) as ydl:
                ydl.download([url])

            file_path = str(self.output_dir / filename)
            # yt-dlp may adjust the extension; try to find the actual file
            if not os.path.exists(file_path):
                # Look for any file matching the base name
                matches = list(self.output_dir.glob(f"{filename_base}.*"))
                if matches:
                    file_path = str(matches[0])
                    filename = matches[0].name

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
            opts = self._base_opts(str(self.temp_dir))
            opts["skip_download"] = True
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)

            formats = []
            for f in (info.get("formats") or []):
                formats.append({
                    "format_id": f.get("format_id"),
                    "ext": f.get("ext"),
                    "resolution": f.get("resolution"),
                    "abr": f.get("abr"),
                    "fps": f.get("fps"),
                    "vcodec": f.get("vcodec"),
                    "acodec": f.get("acodec"),
                })

            return {
                "success": True,
                "title": info.get("title"),
                "duration": info.get("duration"),
                "thumbnail": info.get("thumbnail"),
                "author": info.get("uploader") or info.get("channel"),
                "views": info.get("view_count"),
                "streams": formats,
            }
        except Exception as e:
            return {"success": False, "error": str(e), "url": url}

    def download_playlist(self, url: str, audio_only: bool = None, max_videos: int = 10) -> Dict[str, Any]:
        """Download videos from a YouTube playlist."""
        try:
            # Extract playlist info first
            opts = self._base_opts(str(self.temp_dir))
            opts["skip_download"] = True
            opts["extract_flat"] = True
            with yt_dlp.YoutubeDL(opts) as ydl:
                playlist_info = ydl.extract_info(url, download=False)

            playlist_title = playlist_info.get("title", "Unknown Playlist")
            entries = list(playlist_info.get("entries") or [])
            total_videos = len(entries)

            results = []
            for entry in entries[:max_videos]:
                video_url = entry.get("url") or f"https://www.youtube.com/watch?v={entry.get('id')}"
                result = self.download_youtube_video(video_url, audio_only=audio_only)
                results.append(result)

            return {
                "success": True,
                "playlist_title": playlist_title,
                "total_videos": total_videos,
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
