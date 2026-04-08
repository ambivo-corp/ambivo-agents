# ambivo_agents/executors/__init__.py
from .docker_executor import DockerCodeExecutor
from .media_executor import MediaDockerExecutor
from .youtube_executor import YouTubeDockerExecutor
from .code_execution_policy import CodeExecutionPolicy, CodeValidator, ValidationResult

# Local executors — imported conditionally to avoid hard dependency on Docker
try:
    from .local_code_executor import LocalCodeExecutor
except ImportError:
    LocalCodeExecutor = None

try:
    from .media_local_executor import MediaLocalExecutor
except ImportError:
    MediaLocalExecutor = None

try:
    from .youtube_local_executor import YouTubeLocalExecutor
except ImportError:
    YouTubeLocalExecutor = None

__all__ = [
    "DockerCodeExecutor",
    "MediaDockerExecutor",
    "YouTubeDockerExecutor",
    "LocalCodeExecutor",
    "MediaLocalExecutor",
    "YouTubeLocalExecutor",
    "CodeExecutionPolicy",
    "CodeValidator",
    "ValidationResult",
]
