# ambivo_agents/executors/local_code_executor.py
"""
Local code executor — runs Python/Bash via subprocess in a temporary directory
(no Docker required).  Drop-in replacement for DockerCodeExecutor when
``docker.use_docker`` is ``false``.

Security note: this executor does NOT provide the same sandboxing guarantees
as Docker.  It uses a temporary working directory and a subprocess timeout,
but the code runs with the same permissions as the host process.  This is
acceptable for trusted agent-generated code in controlled environments
(e.g., Railway, internal servers) but should not be used for arbitrary
user-submitted code in multi-tenant deployments.
"""

import logging
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, Optional

from ..config.loader import get_config_section, load_config
from ..core.docker_shared import get_shared_manager

logger = logging.getLogger(__name__)


class LocalCodeExecutor:
    """Code executor using local subprocess (no Docker)."""

    def __init__(self, config: Dict[str, Any] = None):
        if config is None:
            try:
                full_config = load_config()
                config = get_config_section("docker", full_config)
            except Exception:
                config = {}

        self.config = config
        self.timeout = config.get("timeout", 60)
        self.allow_network = config.get("allow_network", False)

        # Shared directory setup (same layout as Docker executor)
        shared_base_dir = config.get("shared_base_dir", "./docker_shared")
        self.shared_manager = get_shared_manager(shared_base_dir)
        self.shared_manager.setup_directories()

        self.input_subdir = config.get("input_subdir", "code")
        self.output_subdir = config.get("output_subdir", "code")
        self.temp_subdir = config.get("temp_subdir", "code")
        self.handoff_subdir = config.get("handoff_subdir", "code")

        self.input_dir = self.shared_manager.get_host_path(self.input_subdir, "input")
        self.output_dir = self.shared_manager.get_host_path(self.output_subdir, "output")
        self.temp_dir = self.shared_manager.get_host_path(self.temp_subdir, "temp")
        self.handoff_dir = self.shared_manager.get_host_path(self.handoff_subdir, "handoff")

        for d in (self.input_dir, self.output_dir, self.temp_dir, self.handoff_dir):
            d.mkdir(parents=True, exist_ok=True)

        self.available = True

    # -----------------------------------------------------------------
    # Public API — matches DockerCodeExecutor interface
    # -----------------------------------------------------------------

    def execute_code(
        self,
        code: str,
        language: str = "python",
        files: Dict[str, str] = None,
        input_files: Dict[str, str] = None,
        use_shared_dirs: bool = True,
    ) -> Dict[str, Any]:
        """Execute code locally via subprocess with policy validation."""
        # Validate code against execution policy before running
        try:
            from .code_execution_policy import CodeExecutionPolicy, CodeValidator
            policy = CodeExecutionPolicy.from_config()
            validator = CodeValidator(policy)
            result = validator.validate(code, language)
            if not result.allowed:
                logger.warning(f"Code blocked by execution policy: {result}")
                return {
                    "success": False,
                    "error": f"Code blocked by execution policy: {'; '.join(result.violations)}",
                    "language": language,
                    "policy_violations": result.violations,
                }
            if policy.log_all_executions:
                logger.info(f"Code execution validated ({language}, policy={result.policy_name})")
        except ImportError:
            pass  # Policy module not available, proceed without validation

        try:
            if use_shared_dirs:
                return self._execute_with_shared_dirs(code, language, files, input_files)
            else:
                return self._execute_in_tempdir(code, language, files)
        except Exception as e:
            return {
                "success": False,
                "error": f"Code execution failed: {str(e)}",
                "language": language,
            }

    def execute_code_with_host_files(
        self,
        code: str,
        language: str = "python",
        host_files: Dict[str, str] = None,
        output_dir: str = None,
    ) -> Dict[str, Any]:
        """Execute code with explicit host file paths."""
        return self._execute_in_tempdir(code, language, host_files)

    # -----------------------------------------------------------------
    # Internal
    # -----------------------------------------------------------------

    def _execute_with_shared_dirs(
        self,
        code: str,
        language: str,
        files: Dict[str, str] = None,
        input_files: Dict[str, str] = None,
    ) -> Dict[str, Any]:
        """Execute code using the shared directory structure."""
        # Copy input files
        if input_files:
            for filename, source_path in input_files.items():
                resolved = self.shared_manager.resolve_input_file(source_path, self.input_subdir)
                if resolved:
                    self.shared_manager.copy_to_input(str(resolved), self.input_subdir, filename)

        # Write code to temp dir
        if language == "python":
            code_file = self.temp_dir / "code.py"
            code_file.write_text(code)
            cmd = ["python", str(code_file)]
        elif language == "bash":
            code_file = self.temp_dir / "script.sh"
            code_file.write_text(code)
            code_file.chmod(0o755)
            cmd = ["bash", str(code_file)]
        else:
            raise ValueError(f"Unsupported language: {language}")

        # Write additional files
        if files:
            for filename, content in files.items():
                (self.temp_dir / filename).write_text(content)

        env = os.environ.copy()
        env.update({
            "DOCKER_INPUT_DIR": str(self.input_dir),
            "DOCKER_OUTPUT_DIR": str(self.output_dir),
            "DOCKER_TEMP_DIR": str(self.temp_dir),
        })

        start_time = time.time()
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                timeout=self.timeout,
                cwd=str(self.temp_dir),
                env=env,
            )
            execution_time = time.time() - start_time
            output = proc.stdout.decode("utf-8", errors="replace")
            stderr = proc.stderr.decode("utf-8", errors="replace")

            if proc.returncode != 0:
                return {
                    "success": False,
                    "error": f"Exit code {proc.returncode}: {stderr[:500]}",
                    "output": output + "\n" + stderr,
                    "execution_time": execution_time,
                    "language": language,
                }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": f"Code execution exceeded {self.timeout}s timeout",
                "execution_time": time.time() - start_time,
                "language": language,
            }

        output_files = self.shared_manager.list_outputs(self.output_subdir)

        return {
            "success": True,
            "output": output + ("\n" + stderr if stderr else ""),
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

    def _execute_in_tempdir(
        self,
        code: str,
        language: str,
        files: Dict[str, str] = None,
    ) -> Dict[str, Any]:
        """Execute code in a fresh temporary directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            if language == "python":
                code_file = temp_path / "code.py"
                code_file.write_text(code)
                cmd = ["python", str(code_file)]
            elif language == "bash":
                code_file = temp_path / "script.sh"
                code_file.write_text(code)
                code_file.chmod(0o755)
                cmd = ["bash", str(code_file)]
            else:
                raise ValueError(f"Unsupported language: {language}")

            if files:
                for filename, content in files.items():
                    (temp_path / filename).write_text(content)

            start_time = time.time()
            try:
                proc = subprocess.run(
                    cmd,
                    capture_output=True,
                    timeout=self.timeout,
                    cwd=str(temp_path),
                )
                execution_time = time.time() - start_time
                output = proc.stdout.decode("utf-8", errors="replace")
                stderr = proc.stderr.decode("utf-8", errors="replace")
            except subprocess.TimeoutExpired:
                return {
                    "success": False,
                    "error": f"Execution exceeded {self.timeout}s timeout",
                    "execution_time": time.time() - start_time,
                    "language": language,
                }

            output_files = [str(f) for f in temp_path.glob("*") if f.is_file() and f.name not in ("code.py", "script.sh")]

            return {
                "success": proc.returncode == 0,
                "output": output + ("\n" + stderr if stderr else ""),
                "execution_time": execution_time,
                "language": language,
                "output_files": output_files,
                "error": stderr[:500] if proc.returncode != 0 else None,
            }
