# ambivo_agents/executors/media_local_executor.py
"""
Local media executor — runs ffmpeg/ffprobe directly via subprocess
(no Docker required).  Drop-in replacement for MediaDockerExecutor when
``docker.use_docker`` is ``false``.
"""

import logging
import shlex
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Dict

from ..config.loader import get_config_section, load_config
from ..core.docker_shared import get_shared_manager

logger = logging.getLogger(__name__)


class MediaLocalExecutor:
    """Media processing executor using local ffmpeg (no Docker)."""

    def __init__(self, config: Dict[str, Any] = None):
        if config is None:
            try:
                full_config = load_config()
                config = get_config_section("media_editor", full_config)
            except Exception:
                config = {}

        self.config = config
        self.timeout = config.get("timeout", 300)

        # Shared directory setup (same layout as Docker executor)
        try:
            full_config = load_config()
            docker_config = get_config_section("docker", full_config)
        except Exception:
            docker_config = {}
        shared_base_dir = docker_config.get("shared_base_dir", "./docker_shared")
        self.shared_manager = get_shared_manager(shared_base_dir)
        self.shared_manager.setup_directories()

        self.input_subdir = config.get("input_subdir", "media")
        self.output_subdir = config.get("output_subdir", "media")
        self.temp_subdir = config.get("temp_subdir", "media")
        self.handoff_subdir = config.get("handoff_subdir", "media")

        self.input_dir = self.shared_manager.get_host_path(self.input_subdir, "input")
        self.output_dir = self.shared_manager.get_host_path(self.output_subdir, "output")
        self.temp_dir = self.shared_manager.get_host_path(self.temp_subdir, "temp")
        self.handoff_dir = self.shared_manager.get_host_path(self.handoff_subdir, "handoff")

        for d in (self.input_dir, self.output_dir, self.temp_dir, self.handoff_dir):
            d.mkdir(parents=True, exist_ok=True)

        # Verify ffmpeg is available locally
        self.ffmpeg_path = shutil.which("ffmpeg")
        self.ffprobe_path = shutil.which("ffprobe")
        if not self.ffmpeg_path:
            raise FileNotFoundError(
                "ffmpeg is required for local media processing but was not found on PATH. "
                "Install it with: apt-get install ffmpeg (Linux) / brew install ffmpeg (macOS)"
            )

        self.available = True

    # -----------------------------------------------------------------
    # Command validation (same as Docker executor)
    # -----------------------------------------------------------------

    def _validate_ffmpeg_command(self, command: str) -> str:
        """Validate and sanitize FFmpeg command to prevent injection."""
        dangerous_patterns = [
            ";", "&&", "||", "$(", "`", "|", ">", ">>", "<", "\n", "\r",
            "\\x", "\\0", "\\u", "$((", "#{", "%(",
        ]
        for pattern in dangerous_patterns:
            if pattern in command:
                raise ValueError(f"Unsafe character sequence in FFmpeg command: {repr(pattern)}")
        cmd_stripped = command.strip()
        if not cmd_stripped.startswith(("ffmpeg ", "ffprobe ", "ffmpeg\t", "ffprobe\t")):
            raise ValueError("Command must start with ffmpeg or ffprobe")
        return command

    def _is_path_allowed(self, resolved_path: Path) -> bool:
        """Check if path is within allowed base directories."""
        allowed_bases = [
            self.input_dir, self.output_dir, self.temp_dir,
            self.handoff_dir, Path(tempfile.gettempdir()),
        ]
        for base in allowed_bases:
            try:
                resolved_path.relative_to(base.resolve())
                return True
            except ValueError:
                continue
        return False

    def resolve_input_file(self, file_path: str) -> Path | None:
        """Resolve an input file path, searching known directories."""
        p = Path(file_path)
        if p.exists():
            return p.resolve()
        # Search in known input directories
        for search_dir in (self.input_dir, self.handoff_dir, self.output_dir):
            candidate = search_dir / p.name
            if candidate.exists():
                return candidate.resolve()
        return None

    # -----------------------------------------------------------------
    # Public API — matches MediaDockerExecutor interface
    # -----------------------------------------------------------------

    def execute_ffmpeg_command(
        self,
        ffmpeg_command: str,
        input_files: Dict[str, str] = None,
        output_filename: str = None,
        work_files: Dict[str, str] = None,
    ) -> Dict[str, Any]:
        """Execute ffmpeg command locally via subprocess."""
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                local_input = temp_path / "input"
                local_output = temp_path / "output"
                local_input.mkdir()
                local_output.mkdir()

                # Resolve and copy input files
                file_mapping = {}
                if input_files:
                    for container_name, host_path in input_files.items():
                        resolved_path = self.resolve_input_file(host_path)
                        if resolved_path and resolved_path.exists():
                            dest_path = local_input / container_name
                            shutil.copy2(resolved_path, dest_path)
                            file_mapping[container_name] = str(dest_path)
                        else:
                            search_dirs = [str(self.input_dir), str(self.handoff_dir)]
                            return {
                                "success": False,
                                "error": f"Input file not found: {host_path}\nSearched in: {', '.join(search_dirs)}",
                                "command": ffmpeg_command,
                                "searched_locations": search_dirs,
                            }

                # Write work files
                if work_files:
                    for name, content in work_files.items():
                        (temp_path / name).write_text(content)

                # Substitute placeholders in the command
                final_command = ffmpeg_command
                for container_name, local_path in file_mapping.items():
                    final_command = final_command.replace(f"${{{container_name}}}", local_path)

                if output_filename:
                    output_filename = Path(output_filename).name
                    final_command = final_command.replace(
                        "${OUTPUT}", str(local_output / output_filename)
                    )

                final_command = self._validate_ffmpeg_command(final_command)

                start_time = time.time()

                # Run ffmpeg as a subprocess
                try:
                    proc = subprocess.run(
                        shlex.split(final_command),
                        capture_output=True,
                        timeout=self.timeout,
                        cwd=str(temp_path),
                    )
                    execution_time = time.time() - start_time
                    output_text = proc.stdout.decode("utf-8", errors="replace")
                    stderr_text = proc.stderr.decode("utf-8", errors="replace")
                    combined_output = output_text + "\n" + stderr_text

                    if proc.returncode != 0:
                        return {
                            "success": False,
                            "error": f"ffmpeg exited with code {proc.returncode}: {stderr_text[:500]}",
                            "command": final_command,
                            "execution_time": execution_time,
                        }
                except subprocess.TimeoutExpired:
                    return {
                        "success": False,
                        "error": f"Media processing exceeded {self.timeout}s timeout",
                        "command": final_command,
                        "execution_time": time.time() - start_time,
                    }

                # Collect output files
                output_files = list(local_output.glob("*"))
                output_info = {}

                if output_files:
                    output_file = output_files[0]
                    output_info = {
                        "filename": output_file.name,
                        "size_bytes": output_file.stat().st_size,
                        "path": str(output_file),
                    }
                    permanent_output = self.output_dir / output_file.name
                    shutil.move(str(output_file), str(permanent_output))
                    output_info["final_path"] = str(permanent_output)

                return {
                    "success": True,
                    "output": combined_output,
                    "execution_time": execution_time,
                    "command": final_command,
                    "output_file": output_info,
                    "temp_dir": str(temp_path),
                }

        except Exception as e:
            return {
                "success": False,
                "error": f"Media processing setup failed: {str(e)}",
                "command": ffmpeg_command,
            }

    def get_media_info(self, file_path: str) -> Dict[str, Any]:
        """Get media file information using ffprobe (locally)."""
        resolved = self.resolve_input_file(file_path)
        if not resolved or not resolved.exists():
            return {"success": False, "error": f"File not found: {file_path}"}

        try:
            import json as _json
            proc = subprocess.run(
                [
                    self.ffprobe_path or "ffprobe",
                    "-v", "quiet",
                    "-print_format", "json",
                    "-show_format",
                    "-show_streams",
                    str(resolved),
                ],
                capture_output=True,
                timeout=30,
            )
            info = _json.loads(proc.stdout)
            return {"success": True, "info": info, "file_path": str(resolved)}
        except Exception as e:
            return {"success": False, "error": str(e)}
