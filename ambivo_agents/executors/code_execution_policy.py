# ambivo_agents/executors/code_execution_policy.py
"""
Code Execution Safety Policy for AI-generated code.

Configurable guardrails that apply to BOTH Docker and local execution.
Controls what AI-generated code is allowed to do before it runs.

Configuration via YAML (agent_config.yaml):
    code_execution_policy:
      allow_network: false
      allow_file_write: true
      allow_subprocess: false
      allow_system_commands: false
      max_execution_time: 60
      max_output_size_bytes: 10485760  # 10MB
      blocked_imports: ["os.system", "subprocess", "shutil.rmtree"]
      blocked_builtins: ["exec", "eval", "compile", "__import__"]
      allowed_directories: ["./docker_shared", "/tmp"]
      require_review: false

Or via ENV:
    AMBIVO_AGENTS_CODE_EXECUTION_POLICY_ALLOW_NETWORK=false
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


@dataclass
class CodeExecutionPolicy:
    """Defines what AI-generated code is allowed to do.

    Defaults are conservative — safe for most deployments.
    """

    # --- Network ---
    allow_network: bool = False  # Blocks socket, urllib, requests in code

    # --- File system ---
    allow_file_write: bool = True  # Allow writing to allowed_directories
    allow_file_delete: bool = False  # Block os.remove, shutil.rmtree
    allowed_directories: List[str] = field(
        default_factory=lambda: ["./docker_shared", "/tmp"]
    )

    # --- Process ---
    allow_subprocess: bool = False  # Block subprocess, os.system, os.popen
    allow_system_commands: bool = False  # Block os.system, os.exec*

    # --- Dangerous builtins ---
    allow_eval: bool = False  # Block eval(), exec(), compile()
    allow_dynamic_import: bool = False  # Block __import__()

    # --- Resource limits ---
    max_execution_time: int = 60  # Seconds
    max_output_size_bytes: int = 10_485_760  # 10MB
    max_memory_mb: int = 512

    # --- Import restrictions ---
    blocked_imports: List[str] = field(
        default_factory=lambda: [
            "subprocess",
            "shutil.rmtree",
            "os.system",
            "os.popen",
            "os.exec",
            "ctypes",
            "multiprocessing",
            "signal",
        ]
    )
    blocked_builtins: List[str] = field(
        default_factory=lambda: ["exec", "eval", "compile", "__import__"]
    )

    # --- Review gate ---
    require_review: bool = False  # If True, code must be approved before execution
    log_all_executions: bool = True  # Log every code execution for audit

    @classmethod
    def from_config(cls, config: Dict[str, Any] = None) -> "CodeExecutionPolicy":
        """Create policy from config dict (YAML section or ENV-derived)."""
        if config is None:
            try:
                from ..config.loader import get_config_section
                config = get_config_section("code_execution_policy")
            except Exception:
                config = {}

        kwargs = {}
        for field_name in cls.__dataclass_fields__:
            if field_name in config:
                kwargs[field_name] = config[field_name]
        return cls(**kwargs)

    @classmethod
    def permissive(cls) -> "CodeExecutionPolicy":
        """Factory: permissive policy for trusted environments."""
        return cls(
            allow_network=True,
            allow_file_write=True,
            allow_file_delete=True,
            allow_subprocess=True,
            allow_system_commands=False,  # Still block os.system
            allow_eval=False,  # Still block eval
            allow_dynamic_import=True,
            max_execution_time=300,
            blocked_imports=["ctypes", "signal"],
            blocked_builtins=["exec", "compile"],
        )

    @classmethod
    def strict(cls) -> "CodeExecutionPolicy":
        """Factory: strict policy for multi-tenant or untrusted environments."""
        return cls(
            allow_network=False,
            allow_file_write=False,
            allow_file_delete=False,
            allow_subprocess=False,
            allow_system_commands=False,
            allow_eval=False,
            allow_dynamic_import=False,
            max_execution_time=30,
            max_memory_mb=256,
            require_review=True,
        )


class CodeValidator:
    """Validates AI-generated code against a CodeExecutionPolicy before execution."""

    def __init__(self, policy: CodeExecutionPolicy = None):
        self.policy = policy or CodeExecutionPolicy()

    def validate(self, code: str, language: str = "python") -> "ValidationResult":
        """Validate code against policy. Returns ValidationResult."""
        violations = []

        if language == "python":
            violations.extend(self._check_python(code))
        elif language == "bash":
            violations.extend(self._check_bash(code))

        return ValidationResult(
            allowed=len(violations) == 0,
            violations=violations,
            policy_name=self._policy_name(),
        )

    def _check_python(self, code: str) -> List[str]:
        violations = []

        # Check blocked imports
        import_pattern = re.compile(
            r'(?:^|\n)\s*(?:import|from)\s+([\w.]+)', re.MULTILINE
        )
        imports = import_pattern.findall(code)
        for imp in imports:
            for blocked in self.policy.blocked_imports:
                if imp == blocked or imp.startswith(blocked + "."):
                    violations.append(f"Blocked import: {imp}")

        # Check blocked builtins
        for builtin in self.policy.blocked_builtins:
            pattern = re.compile(rf'\b{re.escape(builtin)}\s*\(')
            if pattern.search(code):
                violations.append(f"Blocked builtin: {builtin}()")

        # Check subprocess usage
        if not self.policy.allow_subprocess:
            subprocess_patterns = [
                r'subprocess\.',
                r'os\.system\s*\(',
                r'os\.popen\s*\(',
                r'os\.exec\w*\s*\(',
                r'Popen\s*\(',
            ]
            for pattern in subprocess_patterns:
                if re.search(pattern, code):
                    violations.append(f"Subprocess/system call not allowed: {pattern}")

        # Check network usage
        if not self.policy.allow_network:
            network_patterns = [
                r'import\s+socket',
                r'import\s+urllib',
                r'import\s+requests',
                r'import\s+httpx',
                r'import\s+aiohttp',
                r'urlopen\s*\(',
                r'\.get\s*\(\s*["\']https?://',
            ]
            for pattern in network_patterns:
                if re.search(pattern, code):
                    violations.append(f"Network access not allowed: {pattern}")

        # Check file deletion
        if not self.policy.allow_file_delete:
            delete_patterns = [
                r'os\.remove\s*\(',
                r'os\.unlink\s*\(',
                r'shutil\.rmtree\s*\(',
                r'Path\(.*\)\.unlink\s*\(',
            ]
            for pattern in delete_patterns:
                if re.search(pattern, code):
                    violations.append(f"File deletion not allowed: {pattern}")

        # Check eval/exec
        if not self.policy.allow_eval:
            for func in ["eval", "exec", "compile"]:
                if re.search(rf'\b{func}\s*\(', code):
                    violations.append(f"Dynamic code execution not allowed: {func}()")

        return violations

    def _check_bash(self, code: str) -> List[str]:
        violations = []

        # Check dangerous commands
        if not self.policy.allow_system_commands:
            dangerous = [
                r'\brm\s+-rf\b',
                r'\bdd\s+',
                r'\bmkfs\b',
                r'\bchmod\s+777\b',
                r'\bchown\b',
                r'\bsudo\b',
                r'\bkill\b',
                r'\bpkill\b',
            ]
            for pattern in dangerous:
                if re.search(pattern, code):
                    violations.append(f"Dangerous command not allowed: {pattern}")

        # Check network access
        if not self.policy.allow_network:
            network_cmds = [r'\bcurl\b', r'\bwget\b', r'\bnc\b', r'\bnetcat\b']
            for pattern in network_cmds:
                if re.search(pattern, code):
                    violations.append(f"Network command not allowed: {pattern}")

        # Check subprocess spawning
        if not self.policy.allow_subprocess:
            spawn_patterns = [r'\bnohup\b', r'\b&\s*$', r'\bscreen\b', r'\btmux\b']
            for pattern in spawn_patterns:
                if re.search(pattern, code):
                    violations.append(f"Background process not allowed: {pattern}")

        return violations

    def _policy_name(self) -> str:
        if not self.policy.allow_network and not self.policy.allow_subprocess:
            return "strict"
        elif self.policy.allow_network and self.policy.allow_subprocess:
            return "permissive"
        return "default"


@dataclass
class ValidationResult:
    """Result of code validation."""
    allowed: bool
    violations: List[str]
    policy_name: str = "default"

    def __str__(self):
        if self.allowed:
            return f"Code allowed (policy: {self.policy_name})"
        return (
            f"Code blocked (policy: {self.policy_name}): "
            + "; ".join(self.violations)
        )
