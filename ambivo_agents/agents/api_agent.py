# ambivo_agents/agents/api_agent.py - Comprehensive API Agent with Security and Resilience
"""
Comprehensive API Agent that can invoke REST APIs with full HTTP method support,
authentication handling, retry logic, and security features.
"""

import asyncio
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import time
import urllib.parse
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple, Union

import httpx
import yaml
from bs4 import BeautifulSoup

from ..config.loader import get_config_section, load_config
from ..core.base import (
    AgentMessage,
    AgentRole,
    AgentTool,
    BaseAgent,
    ExecutionContext,
    MessageType,
    StreamChunk,
    StreamSubType,
)
from ..core.history import ContextType, WebAgentHistoryMixin


class HTTPMethod(Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"


class AuthType(Enum):
    NONE = "none"
    BEARER = "bearer"
    BASIC = "basic"
    API_KEY = "api_key"
    OAUTH2 = "oauth2"
    CUSTOM = "custom"


@dataclass
class OutputConfig:
    """
    Configuration for handling large API responses
    
    File Output Settings:
    - auto_save_large_responses: Automatically save responses exceeding size threshold
    - size_threshold_kb: Response size threshold in KB to trigger file saving
    - output_directory: Directory to save response files (default: ./api_responses)
    - filename_template: Template for generated filenames with placeholders
    - detect_content_type: Automatically detect JSON/XML/HTML and choose appropriate extension
    - max_inline_size_kb: Maximum size to display inline before truncating
    """
    
    auto_save_large_responses: bool = True
    size_threshold_kb: int = 50  # 50KB threshold
    output_directory: str = "./api_responses"
    filename_template: str = "response_{timestamp}_{domain}_{method}"
    detect_content_type: bool = True
    max_inline_size_kb: int = 5  # 5KB max inline display
    create_summary: bool = True  # Create summary for saved files
    compress_json: bool = False  # Whether to pretty-print JSON or compress it


@dataclass
class SecurityConfig:
    """
    Security configuration for API calls
    
    Domain Security:
    - allowed_domains=None (default): Allow ALL domains except those in blocked_domains
    - allowed_domains=[list]: Restrict to ONLY the specified domains (more secure)
    - blocked_domains: Always blocked, regardless of allowed_domains setting
    
    Default behavior allows all external APIs while blocking local network access.
    For production environments, consider setting specific allowed_domains.
    """

    allowed_domains: Optional[List[str]] = None  # None = allow all (except blocked)
    blocked_domains: Optional[List[str]] = field(default_factory=lambda: ["localhost", "127.0.0.1", "0.0.0.0"])
    allowed_methods: Optional[List[HTTPMethod]] = None
    blocked_methods: Optional[List[HTTPMethod]] = None
    max_redirects: int = 5
    verify_ssl: bool = True
    timeout_seconds: int = 30
    max_response_size: int = 50 * 1024 * 1024  # 50MB

    # Safety timeout settings
    default_timeout_seconds: int = 8  # Default safe timeout
    max_safe_timeout: int = 8  # Maximum timeout without Docker
    force_docker_above_timeout: bool = True  # Force Docker for longer timeouts
    docker_image: str = "sgosain/amb-ubuntu-python-public-pod"


@dataclass
class RetryConfig:
    """Retry configuration with exponential backoff"""

    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True
    retry_on_status: List[int] = field(default_factory=lambda: [429, 500, 502, 503, 504])


@dataclass
class AuthConfig:
    """Authentication configuration"""

    auth_type: AuthType = AuthType.NONE
    token: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    api_key: Optional[str] = None
    api_key_header: str = "X-API-Key"

    # Pre-fetch auth configuration
    pre_auth_url: Optional[str] = None
    pre_auth_method: HTTPMethod = HTTPMethod.POST
    pre_auth_payload: Optional[Dict[str, Any]] = None
    pre_auth_headers: Optional[Dict[str, str]] = None
    token_path: str = "access_token"  # JSON path to extract token
    token_prefix: str = "Bearer"


@dataclass
class APIRequest:
    """API request specification"""

    url: str
    method: HTTPMethod = HTTPMethod.GET
    headers: Optional[Dict[str, str]] = None
    params: Optional[Dict[str, Any]] = None
    data: Optional[Union[Dict[str, Any], str, bytes]] = None
    json_data: Optional[Dict[str, Any]] = None
    auth_config: Optional[AuthConfig] = None
    timeout: Optional[int] = None


@dataclass
class APIResponse:
    """API response data structure"""

    status_code: int
    headers: Dict[str, str]
    content: Union[str, bytes]
    json_data: Optional[Dict[str, Any]] = None
    url: str = ""
    method: str = ""
    duration_ms: float = 0
    attempt_number: int = 1
    error: Optional[str] = None


@dataclass
class APIEndpoint:
    """Parsed API endpoint information"""

    path: str
    method: HTTPMethod
    description: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)
    headers: Dict[str, str] = field(default_factory=dict)
    body_schema: Optional[Dict[str, Any]] = None
    response_schema: Optional[Dict[str, Any]] = None
    auth_required: bool = False
    example_request: Optional[Dict[str, Any]] = None
    example_response: Optional[Dict[str, Any]] = None


@dataclass
class PostmanCollection:
    """Postman collection structure"""

    name: str = ""
    description: str = ""
    variables: Dict[str, str] = field(default_factory=dict)
    auth: Dict[str, Any] = field(default_factory=dict)
    items: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class APIDocumentation:
    """Parsed API documentation structure"""

    base_url: str = ""
    title: str = ""
    version: str = ""
    description: str = ""
    auth_info: Dict[str, Any] = field(default_factory=dict)
    endpoints: List[APIEndpoint] = field(default_factory=list)
    schemas: Dict[str, Any] = field(default_factory=dict)
    examples: Dict[str, Any] = field(default_factory=dict)
    source_type: str = "openapi"  # openapi, html, postman


class APIAgent(BaseAgent, WebAgentHistoryMixin):
    """
    Comprehensive API Agent with security, resilience, and authentication features.
    Supports all HTTP methods, pre-fetch authentication, retry logic, and security controls.
    """

    def __init__(
        self,
        agent_id: str,
        memory_manager=None,
        llm_service=None,
        execution_context: Optional[ExecutionContext] = None,
        system_message: Optional[str] = None,
        security_config: Optional[SecurityConfig] = None,
        retry_config: Optional[RetryConfig] = None,
        output_config: Optional[OutputConfig] = None,
        auto_configure: bool = True,
        **kwargs,
    ):
        # Load configuration
        if auto_configure:
            config = load_config()
            api_config = get_config_section("api_agent", config)

            # Initialize security config from configuration
            if security_config is None:
                security_config = SecurityConfig(
                    allowed_domains=api_config.get("allowed_domains"),  # None = allow all domains (except blocked)
                    blocked_domains=api_config.get(
                        "blocked_domains", ["localhost", "127.0.0.1", "0.0.0.0"]
                    ),
                    allowed_methods=[
                        HTTPMethod(m)
                        for m in api_config.get(
                            "allowed_methods", ["GET", "POST", "PUT", "PATCH", "DELETE"]
                        )
                    ],
                    blocked_methods=[HTTPMethod(m) for m in api_config.get("blocked_methods", [])],
                    verify_ssl=api_config.get("verify_ssl", True),
                    timeout_seconds=api_config.get("timeout_seconds", 30),
                    max_response_size=api_config.get("max_response_size", 50 * 1024 * 1024),
                    # Safety timeout settings
                    default_timeout_seconds=api_config.get("default_timeout_seconds", 8),
                    max_safe_timeout=api_config.get("max_safe_timeout", 8),
                    force_docker_above_timeout=api_config.get("force_docker_above_timeout", True),
                    docker_image=api_config.get(
                        "docker_image", "sgosain/amb-ubuntu-python-public-pod"
                    ),
                )

            # Initialize retry config from configuration
            if retry_config is None:
                retry_config = RetryConfig(
                    max_retries=api_config.get("max_retries", 3),
                    base_delay=api_config.get("base_delay", 1.0),
                    max_delay=api_config.get("max_delay", 60.0),
                )

            # Initialize output config from configuration
            if output_config is None:
                output_config = OutputConfig(
                    auto_save_large_responses=api_config.get("auto_save_large_responses", True),
                    size_threshold_kb=api_config.get("size_threshold_kb", 10),
                    output_directory=api_config.get("output_directory", "./api_responses"),
                    filename_template=api_config.get("filename_template", "response_{timestamp}_{domain}_{method}"),
                    detect_content_type=api_config.get("detect_content_type", True),
                    max_inline_size_kb=api_config.get("max_inline_size_kb", 5),
                    create_summary=api_config.get("create_summary", True),
                    compress_json=api_config.get("compress_json", False),
                )

        # Use default system message if none provided
        if system_message is None:
            system_message = self._get_default_system_message()

        super().__init__(
            agent_id=agent_id,
            role=AgentRole.ASSISTANT,
            memory_manager=memory_manager,
            llm_service=llm_service,
            execution_context=execution_context,
            system_message=system_message,
            auto_configure=auto_configure,
            **kwargs,
        )

        self.security_config = security_config or SecurityConfig()
        self.retry_config = retry_config or RetryConfig()
        self.output_config = output_config or OutputConfig()
        self.auth_tokens_cache: Dict[str, Tuple[str, datetime]] = {}
        self.logger = logging.getLogger(__name__)

        # Initialize HTTP client with safe default timeout
        self.client = httpx.AsyncClient(
            verify=self.security_config.verify_ssl,
            timeout=self.security_config.default_timeout_seconds,  # Use safe default
            follow_redirects=True,
            max_redirects=self.security_config.max_redirects,
        )

        # API Documentation cache
        self.api_docs_cache: Dict[str, APIDocumentation] = {}
        self.parsed_endpoints_cache: Dict[str, List[APIEndpoint]] = {}

    def _get_default_system_message(self) -> str:
        """Get the default system message for the API agent"""
        return """You are an intelligent API Agent specialized in making HTTP requests to REST APIs with advanced documentation parsing capabilities. Your capabilities include:

1. **HTTP Methods**: Support for GET, POST, PUT, PATCH, DELETE, HEAD, and OPTIONS
2. **Authentication**: Bearer tokens, Basic auth, API keys, OAuth2, and pre-fetch authentication
3. **Security**: Domain filtering, method restrictions, SSL verification, and payload validation
4. **Resilience**: Automatic retries with exponential backoff, error handling, and timeouts
5. **Response Processing**: JSON parsing, content analysis, structured output, and automatic file saving for large responses
6. **Documentation Intelligence**: Parse API docs (OpenAPI/Swagger, HTML, JSON) and discover endpoints
7. **Smart API Discovery**: Automatically find and call the correct endpoints based on user requests

**Documentation Parsing Capabilities**:
- Parse OpenAPI/Swagger specifications (JSON/YAML)
- Extract endpoints from HTML documentation pages
- Parse Postman collections and extract request details
- Understand API schemas, parameters, and authentication requirements
- Discover endpoint patterns and generate appropriate requests
- Cache parsed documentation for efficient reuse

**Intelligent API Interaction**:
- When given a documentation URL, fetch and parse it to understand available endpoints
- Automatically construct API requests based on parsed documentation
- Match user requests to appropriate endpoints using semantic understanding
- Use provided authentication tokens with discovered endpoints
- Validate requests against parsed schemas when available

**Usage Patterns**:
- "Read docs at URL and call the contacts API" → Parse docs, find contacts endpoint, make request
- "Use token X to get user profile from API Y" → Parse API Y docs, find profile endpoint, authenticate with token X
- "Call the create user endpoint with these details" → Find create user endpoint, construct proper request

**Security Guidelines**:
- Always validate URLs and reject requests to local/private networks unless explicitly allowed
- Respect method restrictions and authentication requirements from parsed documentation
- Never log or expose sensitive authentication data
- Validate all input parameters against parsed schemas
- Enforce 8-second default timeout for safety
- Execute longer timeout requests in isolated Docker containers for security

**Large Response Handling**:
- Automatically detect large API responses (configurable threshold, default: 50KB)
- Save large responses to files with appropriate extensions (.json, .xml, .html, .txt)
- Generate intelligent filenames with timestamps, domains, and HTTP methods
- Create summary files with metadata and content previews
- Display truncated inline previews while providing file paths for full content
- Support for pretty-printed JSON formatting and content type detection

**Documentation Analysis Process**:
1. Fetch documentation from provided URL
2. Detect format (OpenAPI, Swagger, HTML, etc.)
3. Parse and extract endpoint information
4. Cache parsed data for reuse
5. Match user requests to appropriate endpoints
6. Construct and execute API calls with proper authentication

Always prioritize security and follow the configured restrictions. Use your intelligence to understand API documentation and make appropriate calls based on user requests. When responses are large, I will automatically save them to files for better handling and provide you with both a preview and the file location."""

    def _detect_content_type(self, content: str, headers: Dict[str, str]) -> str:
        """Detect content type for appropriate file extension"""
        content_type = headers.get("content-type", "").lower()
        
        # Check explicit content-type header first
        if "application/json" in content_type:
            return "json"
        elif "application/xml" in content_type or "text/xml" in content_type:
            return "xml"
        elif "text/html" in content_type:
            return "html"
        elif "text/csv" in content_type:
            return "csv"
        elif "text/plain" in content_type:
            return "txt"
        
        # Fallback: analyze content structure
        content_stripped = content.strip()
        if content_stripped.startswith(("{", "[")):
            try:
                json.loads(content_stripped)
                return "json"
            except:
                pass
        
        if content_stripped.startswith("<?xml") or content_stripped.startswith("<"):
            return "xml" if "<?xml" in content_stripped else "html"
        
        return "txt"

    def _generate_filename(self, url: str, method: str, content_type: str) -> str:
        """Generate filename for saved response"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Extract domain from URL
        try:
            parsed_url = urllib.parse.urlparse(url)
            domain = parsed_url.netloc.replace(".", "_")
        except:
            domain = "unknown"
        
        # Use template from config
        filename = self.output_config.filename_template.format(
            timestamp=timestamp,
            domain=domain,
            method=method.lower()
        )
        
        # Add appropriate extension
        extension = content_type if content_type in ["json", "xml", "html", "csv", "txt"] else "txt"
        return f"{filename}.{extension}"

    def _should_save_to_file(self, content: str) -> bool:
        """Determine if response should be saved to file"""
        if not self.output_config.auto_save_large_responses:
            return False
        
        content_size_kb = len(content.encode('utf-8')) / 1024
        return content_size_kb > self.output_config.size_threshold_kb

    async def _save_response_to_file(self, content: str, url: str, method: str, headers: Dict[str, str]) -> Tuple[str, str]:
        """Save large response to file and return file path and summary"""
        try:
            # Ensure output directory exists
            output_dir = Path(self.output_config.output_directory)
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Detect content type and generate filename
            content_type = self._detect_content_type(content, headers)
            filename = self._generate_filename(url, method, content_type)
            file_path = output_dir / filename
            
            # Format content based on type
            if content_type == "json" and not self.output_config.compress_json:
                try:
                    # Pretty print JSON
                    parsed_json = json.loads(content)
                    formatted_content = json.dumps(parsed_json, indent=2, ensure_ascii=False)
                except:
                    formatted_content = content
            else:
                formatted_content = content
            
            # Save to file
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(formatted_content)
            
            # Create summary
            content_size_kb = len(content.encode('utf-8')) / 1024
            summary = f"""📁 Response saved to file: {file_path}
📊 Size: {content_size_kb:.1f} KB
🌐 URL: {url}
🔧 Method: {method}
📄 Type: {content_type.upper()}
⏰ Timestamp: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}"""
            
            if self.output_config.create_summary:
                # Save summary file too
                summary_path = output_dir / f"{filename}.summary.txt"
                with open(summary_path, 'w', encoding='utf-8') as f:
                    f.write(summary)
                    f.write(f"\n\n=== Content Preview (first 500 chars) ===\n")
                    f.write(content[:500] + "..." if len(content) > 500 else content)
            
            return str(file_path), summary
            
        except Exception as e:
            self.logger.error(f"Failed to save response to file: {e}")
            return "", f"❌ Failed to save response to file: {str(e)}"

    def _get_inline_content_preview(self, content: str, content_type: str) -> str:
        """Get truncated content for inline display"""
        max_size_bytes = self.output_config.max_inline_size_kb * 1024
        
        if len(content.encode('utf-8')) <= max_size_bytes:
            return content
        
        # Truncate content but try to keep it valid
        truncated = content[:max_size_bytes]
        
        if content_type == "json":
            # Try to truncate at a reasonable JSON boundary
            last_brace = truncated.rfind('}')
            last_bracket = truncated.rfind(']')
            if last_brace > 0 or last_bracket > 0:
                cut_point = max(last_brace, last_bracket) + 1
                truncated = truncated[:cut_point]
        
        return truncated + f"\n\n... (truncated {len(content) - len(truncated)} characters)"

    async def cleanup_session(self):
        """Clean up resources"""
        if hasattr(self, "client") and self.client:
            await self.client.aclose()
        await super().cleanup_session()

    def _validate_security(self, request: APIRequest) -> Tuple[bool, Optional[str]]:
        """Validate request against security configuration"""
        # Parse URL to get domain
        try:
            parsed_url = urllib.parse.urlparse(request.url)
            domain = parsed_url.netloc.lower()
        except Exception as e:
            return False, f"Invalid URL format: {str(e)}"

        # Check blocked domains
        if self.security_config.blocked_domains:
            for blocked in self.security_config.blocked_domains:
                if blocked.lower() in domain:
                    return False, f"Domain {domain} is blocked"

        # Check allowed domains (if specified)
        if self.security_config.allowed_domains:
            allowed = False
            for allowed_domain in self.security_config.allowed_domains:
                if allowed_domain.lower() in domain:
                    allowed = True
                    break
            if not allowed:
                return False, f"Domain {domain} is not in allowed list"

        # Check blocked methods
        if (
            self.security_config.blocked_methods
            and request.method in self.security_config.blocked_methods
        ):
            return False, f"HTTP method {request.method.value} is blocked"

        # Check allowed methods (if specified)
        if (
            self.security_config.allowed_methods
            and request.method not in self.security_config.allowed_methods
        ):
            return False, f"HTTP method {request.method.value} is not allowed"

        # Additional security checks
        if parsed_url.scheme not in ["http", "https"]:
            return False, f"Unsupported URL scheme: {parsed_url.scheme}"

        return True, None

    async def _get_auth_token(self, auth_config: AuthConfig) -> Optional[str]:
        """Get authentication token, with pre-fetch support"""
        if not auth_config.pre_auth_url:
            return auth_config.token

        # Check cache first
        cache_key = hashlib.md5(auth_config.pre_auth_url.encode()).hexdigest()
        if cache_key in self.auth_tokens_cache:
            token, expires = self.auth_tokens_cache[cache_key]
            if datetime.now() < expires:
                return token

        # Perform pre-auth request
        try:
            headers = auth_config.pre_auth_headers or {}
            if auth_config.pre_auth_method == HTTPMethod.POST:
                headers.setdefault("Content-Type", "application/x-www-form-urlencoded")

            response = await self.client.request(
                method=auth_config.pre_auth_method.value,
                url=auth_config.pre_auth_url,
                headers=headers,
                data=auth_config.pre_auth_payload,
            )

            if response.status_code == 200:
                token_data = response.json()
                # Extract token using path (supports nested keys like "data.access_token")
                token = self._extract_json_path(token_data, auth_config.token_path)

                if token:
                    # Cache token for 50 minutes (assume 1-hour expiry)
                    expires = datetime.now() + timedelta(minutes=50)
                    self.auth_tokens_cache[cache_key] = (token, expires)
                    return token

        except Exception as e:
            self.logger.error(f"Failed to obtain auth token: {str(e)}")

        return None

    def _extract_json_path(self, data: Dict[str, Any], path: str) -> Optional[str]:
        """Extract value from JSON using dot notation path"""
        try:
            current = data
            for key in path.split("."):
                current = current[key]
            return str(current) if current is not None else None
        except (KeyError, TypeError):
            return None

    async def _prepare_request_headers(self, request: APIRequest) -> Dict[str, str]:
        """Prepare headers with authentication"""
        headers = request.headers.copy() if request.headers else {}

        if request.auth_config:
            auth = request.auth_config

            if auth.auth_type == AuthType.BEARER:
                token = await self._get_auth_token(auth)
                if token:
                    headers["Authorization"] = f"{auth.token_prefix} {token}"

            elif auth.auth_type == AuthType.API_KEY:
                if auth.api_key:
                    headers[auth.api_key_header] = auth.api_key

            elif auth.auth_type == AuthType.BASIC and auth.username and auth.password:
                import base64

                credentials = f"{auth.username}:{auth.password}"
                encoded = base64.b64encode(credentials.encode()).decode()
                headers["Authorization"] = f"Basic {encoded}"

        return headers

    async def _make_request_with_retry(self, request: APIRequest) -> APIResponse:
        """Make HTTP request with retry logic"""
        attempt = 0
        last_exception = None

        while attempt <= self.retry_config.max_retries:
            attempt += 1
            start_time = time.time()

            try:
                # Prepare headers
                headers = await self._prepare_request_headers(request)

                # Prepare request kwargs
                kwargs = {
                    "method": request.method.value,
                    "url": request.url,
                    "headers": headers,
                    "timeout": request.timeout or self.security_config.timeout_seconds,
                }

                if request.params:
                    kwargs["params"] = request.params

                if request.json_data:
                    kwargs["json"] = request.json_data
                elif request.data:
                    kwargs["data"] = request.data

                # Make request
                response = await self.client.request(**kwargs)
                duration_ms = (time.time() - start_time) * 1000

                # Prepare response object
                try:
                    json_data = response.json()
                except:
                    json_data = None

                api_response = APIResponse(
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    content=response.text,
                    json_data=json_data,
                    url=str(response.url),
                    method=request.method.value,
                    duration_ms=duration_ms,
                    attempt_number=attempt,
                )

                # Check if we should retry based on status code
                if (
                    response.status_code in self.retry_config.retry_on_status
                    and attempt <= self.retry_config.max_retries
                ):
                    raise httpx.HTTPStatusError(
                        message=f"HTTP {response.status_code}",
                        request=response.request,
                        response=response,
                    )

                return api_response

            except Exception as e:
                last_exception = e
                duration_ms = (time.time() - start_time) * 1000

                # If this is the last attempt, return error response
                if attempt > self.retry_config.max_retries:
                    return APIResponse(
                        status_code=0,
                        headers={},
                        content="",
                        error=str(e),
                        url=request.url,
                        method=request.method.value,
                        duration_ms=duration_ms,
                        attempt_number=attempt,
                    )

                # Calculate retry delay
                delay = min(
                    self.retry_config.base_delay
                    * (self.retry_config.exponential_base ** (attempt - 1)),
                    self.retry_config.max_delay,
                )

                if self.retry_config.jitter:
                    import random

                    delay *= 0.5 + random.random() * 0.5

                self.logger.warning(
                    f"Request failed (attempt {attempt}), retrying in {delay:.2f}s: {str(e)}"
                )
                await asyncio.sleep(delay)

        # Should not reach here, but return error response just in case
        return APIResponse(
            status_code=0,
            headers={},
            content="",
            error=str(last_exception) if last_exception else "Unknown error",
            url=request.url,
            method=request.method.value,
            duration_ms=0,
            attempt_number=attempt,
        )

    async def make_api_request(self, request: APIRequest) -> APIResponse:
        """Main method to make API requests with full security and retry logic"""
        # Validate security
        is_valid, error_message = self._validate_security(request)
        if not is_valid:
            return APIResponse(
                status_code=0,
                headers={},
                content="",
                error=f"Security validation failed: {error_message}",
                url=request.url,
                method=request.method.value,
            )

        # Apply timeout safety logic
        request_timeout = request.timeout or self.security_config.timeout_seconds

        # Safety check: enforce 8-second default timeout
        if request_timeout > self.security_config.max_safe_timeout:
            if self.security_config.force_docker_above_timeout:
                # For longer timeouts, execute in Docker for safety
                self.logger.warning(
                    f"Timeout {request_timeout}s exceeds safe limit {self.security_config.max_safe_timeout}s. "
                    "Executing in Docker for safety."
                )
                return await self._execute_api_request_in_docker(request, request_timeout)
            else:
                # Cap timeout to safe limit
                self.logger.warning(
                    f"Timeout {request_timeout}s exceeds safe limit. Capping to {self.security_config.max_safe_timeout}s."
                )
                request.timeout = self.security_config.max_safe_timeout
        else:
            # Use safe timeout
            request.timeout = min(request_timeout, self.security_config.default_timeout_seconds)

        # Make request with retry logic
        return await self._make_request_with_retry(request)

    async def _execute_api_request_in_docker(
        self, request: APIRequest, timeout_seconds: int
    ) -> APIResponse:
        """Execute API request in Docker container for safety with longer timeouts"""
        try:
            import docker

            # Create Python script to execute the API request
            python_script = self._generate_api_request_script(request, timeout_seconds)

            # Connect to Docker
            client = docker.from_env()

            # Run the API request in Docker container
            self.logger.info(f"🐳 Executing API request in Docker with {timeout_seconds}s timeout")

            container = client.containers.run(
                image=self.security_config.docker_image,
                command=["python", "-c", python_script],
                detach=True,
                remove=True,
                network_mode="bridge",  # Allow network access but isolated
                mem_limit="512m",  # Memory limit
                cpu_quota=50000,  # CPU limit (50% of one core)
                environment={"PYTHONUNBUFFERED": "1"},
            )

            # Wait for container to complete with timeout
            start_time = time.time()
            try:
                # Add extra 10 seconds to container timeout to account for startup
                container_timeout = timeout_seconds + 10
                exit_code = container.wait(timeout=container_timeout)
                duration_ms = (time.time() - start_time) * 1000

                # Get container logs (output)
                logs = container.logs().decode("utf-8")

                # Parse the response from container output
                return self._parse_docker_api_response(logs, request, duration_ms)

            except docker.errors.ContainerError as e:
                return APIResponse(
                    status_code=0,
                    headers={},
                    content="",
                    error=f"Docker container error: {str(e)}",
                    url=request.url,
                    method=request.method.value,
                    duration_ms=(time.time() - start_time) * 1000,
                )

        except ImportError:
            # Docker not available, fall back to capped timeout
            self.logger.error(
                "Docker not available for safe long-timeout execution. Using capped timeout."
            )
            request.timeout = self.security_config.max_safe_timeout
            return await self._make_request_with_retry(request)

        except Exception as e:
            self.logger.error(f"Failed to execute API request in Docker: {str(e)}")
            return APIResponse(
                status_code=0,
                headers={},
                content="",
                error=f"Docker execution failed: {str(e)}",
                url=request.url,
                method=request.method.value,
                duration_ms=0,
            )

    def _generate_api_request_script(self, request: APIRequest, timeout_seconds: int) -> str:
        """Generate Python script to execute API request in Docker"""
        # Prepare authentication headers
        headers = {}
        if request.auth_config:
            if request.auth_config.auth_type == AuthType.BEARER and request.auth_config.token:
                headers["Authorization"] = (
                    f"{request.auth_config.token_prefix} {request.auth_config.token}"
                )
            elif request.auth_config.auth_type == AuthType.API_KEY and request.auth_config.api_key:
                headers[request.auth_config.api_key_header] = request.auth_config.api_key

        if request.headers:
            headers.update(request.headers)

        # Generate script
        script = f"""
import requests
import json
import time
import sys

try:
    start_time = time.time()
    
    # Request configuration
    url = {repr(request.url)}
    method = {repr(request.method.value)}
    headers = {repr(headers)}
    params = {repr(request.params) if request.params else 'None'}
    json_data = {repr(request.json_data) if request.json_data else 'None'}
    data = {repr(request.data) if request.data else 'None'}
    timeout = {timeout_seconds}
    
    # Make the request
    response = requests.request(
        method=method,
        url=url,
        headers=headers if headers else None,
        params=params,
        json=json_data,
        data=data,
        timeout=timeout,
        verify={repr(self.security_config.verify_ssl)}
    )
    
    duration_ms = (time.time() - start_time) * 1000
    
    # Prepare response data
    result = {{
        'status_code': response.status_code,
        'headers': dict(response.headers),
        'content': response.text,
        'url': response.url,
        'duration_ms': duration_ms,
        'error': None
    }}
    
    # Try to parse JSON
    try:
        result['json_data'] = response.json()
    except:
        result['json_data'] = None
    
    # Output result as JSON
    print("DOCKER_API_RESPONSE_START")
    print(json.dumps(result))
    print("DOCKER_API_RESPONSE_END")
    
except Exception as e:
    # Output error
    error_result = {{
        'status_code': 0,
        'headers': {{}},
        'content': '',
        'url': {repr(request.url)},
        'duration_ms': (time.time() - start_time) * 1000 if 'start_time' in locals() else 0,
        'error': str(e),
        'json_data': None
    }}
    
    print("DOCKER_API_RESPONSE_START")
    print(json.dumps(error_result))
    print("DOCKER_API_RESPONSE_END")
    sys.exit(1)
"""
        return script

    def _parse_docker_api_response(
        self, logs: str, request: APIRequest, duration_ms: float
    ) -> APIResponse:
        """Parse API response from Docker container logs"""
        try:
            # Extract response JSON from logs
            start_marker = "DOCKER_API_RESPONSE_START"
            end_marker = "DOCKER_API_RESPONSE_END"

            start_idx = logs.find(start_marker)
            end_idx = logs.find(end_marker)

            if start_idx == -1 or end_idx == -1:
                raise Exception("Could not find response markers in Docker output")

            # Extract JSON response
            json_start = start_idx + len(start_marker)
            response_json = logs[json_start:end_idx].strip()

            # Parse response data
            response_data = json.loads(response_json)

            return APIResponse(
                status_code=response_data.get("status_code", 0),
                headers=response_data.get("headers", {}),
                content=response_data.get("content", ""),
                json_data=response_data.get("json_data"),
                url=response_data.get("url", request.url),
                method=request.method.value,
                duration_ms=response_data.get("duration_ms", duration_ms),
                error=response_data.get("error"),
            )

        except Exception as e:
            return APIResponse(
                status_code=0,
                headers={},
                content="",
                error=f"Failed to parse Docker response: {str(e)}. Logs: {logs[:500]}",
                url=request.url,
                method=request.method.value,
                duration_ms=duration_ms,
            )

    async def parse_api_documentation(self, doc_url: str) -> APIDocumentation:
        """Parse API documentation from a URL and extract endpoint information"""
        # Check cache first
        if doc_url in self.api_docs_cache:
            self.logger.info(f"Using cached documentation for {doc_url}")
            return self.api_docs_cache[doc_url]

        try:
            # Fetch documentation
            response = await self.client.get(doc_url)
            if response.status_code != 200:
                raise Exception(f"Failed to fetch documentation: HTTP {response.status_code}")

            content = response.text
            content_type = response.headers.get("content-type", "").lower()

            # Determine documentation format and parse accordingly
            api_doc = APIDocumentation()

            if "json" in content_type or doc_url.endswith(".json"):
                # Check if it's a Postman collection first
                try:
                    data = json.loads(content)
                    if self._is_postman_collection(data):
                        api_doc = await self._parse_postman_collection(content, doc_url)
                    else:
                        api_doc = await self._parse_openapi_json(content, doc_url)
                except json.JSONDecodeError:
                    api_doc = await self._parse_with_llm(content, doc_url)
            elif "yaml" in content_type or doc_url.endswith((".yaml", ".yml")):
                api_doc = await self._parse_openapi_yaml(content, doc_url)
            elif "html" in content_type or doc_url.endswith(".html"):
                api_doc = await self._parse_html_documentation(content, doc_url)
            else:
                # Use LLM to parse unknown format
                api_doc = await self._parse_with_llm(content, doc_url)

            # Cache the parsed documentation
            self.api_docs_cache[doc_url] = api_doc
            self.logger.info(f"Successfully parsed and cached documentation for {doc_url}")

            return api_doc

        except Exception as e:
            self.logger.error(f"Failed to parse API documentation from {doc_url}: {str(e)}")
            raise

    def _is_postman_collection(self, data: Dict[str, Any]) -> bool:
        """Check if JSON data is a Postman collection"""
        return (
            data.get("info", {}).get("schema")
            and "postman" in data.get("info", {}).get("schema", "").lower()
        ) or (
            "item" in data
            and isinstance(data.get("item"), list)
            and data.get("info", {}).get("name")
        )

    async def _parse_postman_collection(self, content: str, base_url: str) -> APIDocumentation:
        """Parse Postman collection and extract API endpoints"""
        try:
            collection_data = json.loads(content)

            # Extract basic collection info
            info = collection_data.get("info", {})
            collection = PostmanCollection(
                name=info.get("name", "Postman Collection"),
                description=info.get("description", ""),
                variables=self._extract_postman_variables(collection_data),
                auth=collection_data.get("auth", {}),
                items=collection_data.get("item", []),
            )

            # Extract base URL from variables or first request
            base_api_url = self._extract_base_url_from_collection(collection)

            # Create API documentation
            api_doc = APIDocumentation(
                base_url=base_api_url,
                title=collection.name,
                description=collection.description,
                auth_info=self._extract_postman_auth_info(collection.auth),
                source_type="postman",
            )

            # Extract endpoints from collection items
            endpoints = []
            self._extract_endpoints_from_items(collection.items, endpoints, collection)
            api_doc.endpoints = endpoints

            return api_doc

        except json.JSONDecodeError as e:
            raise Exception(f"Invalid JSON in Postman collection: {str(e)}")

    def _extract_postman_variables(self, collection_data: Dict[str, Any]) -> Dict[str, str]:
        """Extract variables from Postman collection"""
        variables = {}

        # Collection-level variables
        for var in collection_data.get("variable", []):
            if isinstance(var, dict):
                key = var.get("key", "")
                value = var.get("value", "")
                if key:
                    variables[key] = value

        return variables

    def _extract_base_url_from_collection(self, collection: PostmanCollection) -> str:
        """Extract base URL from Postman collection"""
        # Check variables for common base URL patterns
        for key, value in collection.variables.items():
            if key.lower() in ["baseurl", "base_url", "url", "host", "server"]:
                return value

        # Look for URL in first request
        if collection.items:
            first_item = collection.items[0]
            if "request" in first_item:
                request = first_item["request"]
                url = request.get("url", {})
                if isinstance(url, dict):
                    host = url.get("host", [])
                    protocol = url.get("protocol", "https")
                    if host:
                        host_str = ".".join(host) if isinstance(host, list) else str(host)
                        return f"{protocol}://{host_str}"
                elif isinstance(url, str):
                    # Extract base URL from full URL
                    import urllib.parse

                    parsed = urllib.parse.urlparse(url)
                    return f"{parsed.scheme}://{parsed.netloc}"

        return ""

    def _extract_postman_auth_info(self, auth_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract authentication info from Postman collection"""
        if not auth_data:
            return {}

        auth_type = auth_data.get("type", "")
        auth_info = {"type": auth_type}

        if auth_type == "bearer":
            bearer_data = auth_data.get("bearer", [])
            for item in bearer_data:
                if item.get("key") == "token":
                    auth_info["token_variable"] = item.get("value", "")
            auth_info["type"] = "bearer"
            auth_info["header"] = "Authorization"

        elif auth_type == "apikey":
            apikey_data = auth_data.get("apikey", [])
            for item in apikey_data:
                if item.get("key") == "key":
                    auth_info["api_key_variable"] = item.get("value", "")
                elif item.get("key") == "in":
                    auth_info["location"] = item.get("value", "header")
            auth_info["type"] = "api_key"

        elif auth_type == "basic":
            auth_info["type"] = "basic"
            auth_info["header"] = "Authorization"

        return auth_info

    def _extract_endpoints_from_items(
        self,
        items: List[Dict[str, Any]],
        endpoints: List[APIEndpoint],
        collection: PostmanCollection,
        folder_path: str = "",
    ):
        """Recursively extract endpoints from Postman collection items"""
        for item in items:
            if "item" in item:
                # This is a folder, recurse into it
                folder_name = item.get("name", "")
                new_path = f"{folder_path}/{folder_name}" if folder_path else folder_name
                self._extract_endpoints_from_items(item["item"], endpoints, collection, new_path)

            elif "request" in item:
                # This is a request item
                endpoint = self._create_endpoint_from_postman_request(item, collection, folder_path)
                if endpoint:
                    endpoints.append(endpoint)

    def _create_endpoint_from_postman_request(
        self, item: Dict[str, Any], collection: PostmanCollection, folder_path: str = ""
    ) -> Optional[APIEndpoint]:
        """Create APIEndpoint from Postman request item"""
        try:
            request = item["request"]

            # Extract method
            method = HTTPMethod(request.get("method", "GET").upper())

            # Extract URL path
            url = request.get("url", {})
            path = ""

            if isinstance(url, dict):
                path_list = url.get("path", [])
                if path_list:
                    path = "/" + "/".join(str(p) for p in path_list)

                # Extract query parameters
                query_params = {}
                for query in url.get("query", []):
                    if query.get("disabled") != True:
                        key = query.get("key", "")
                        description = query.get("description", "")
                        query_params[key] = {
                            "type": "string",
                            "required": False,
                            "description": description,
                            "location": "query",
                        }

            elif isinstance(url, str):
                # Parse URL string
                import urllib.parse

                parsed = urllib.parse.urlparse(url)
                path = parsed.path

                # Parse query parameters
                query_params = {}
                for key, values in urllib.parse.parse_qs(parsed.query).items():
                    query_params[key] = {
                        "type": "string",
                        "required": False,
                        "description": f"Query parameter {key}",
                        "location": "query",
                    }

            # Extract headers
            headers = {}
            for header in request.get("header", []):
                if header.get("disabled") != True:
                    key = header.get("key", "")
                    description = header.get("description", "")
                    headers[key] = description or f"Header {key}"

            # Extract body/data for POST requests
            body_schema = None
            example_request = None

            if "body" in request:
                body = request["body"]
                if body.get("mode") == "raw":
                    try:
                        raw_data = body.get("raw", "")
                        if raw_data:
                            example_request = json.loads(raw_data)
                            # Create a simple schema from the example
                            body_schema = self._create_schema_from_example(example_request)
                    except json.JSONDecodeError:
                        pass
                elif body.get("mode") == "formdata":
                    form_data = {}
                    for form_item in body.get("formdata", []):
                        if form_item.get("disabled") != True:
                            key = form_item.get("key", "")
                            form_data[key] = form_item.get("value", "")
                    if form_data:
                        example_request = form_data

            # Combine path and query parameters
            all_parameters = {**query_params}

            # Create endpoint
            endpoint = APIEndpoint(
                path=path,
                method=method,
                description=item.get("name", "") + (f" ({folder_path})" if folder_path else ""),
                parameters=all_parameters,
                headers=headers,
                body_schema=body_schema,
                example_request=example_request,
                auth_required=bool(collection.auth or request.get("auth")),
            )

            return endpoint

        except Exception as e:
            self.logger.warning(f"Failed to parse Postman request item: {str(e)}")
            return None

    def _create_schema_from_example(self, example: Any) -> Dict[str, Any]:
        """Create a simple JSON schema from an example object"""
        if isinstance(example, dict):
            properties = {}
            for key, value in example.items():
                properties[key] = self._get_type_from_value(value)
            return {"type": "object", "properties": properties}
        elif isinstance(example, list):
            if example:
                return {"type": "array", "items": self._create_schema_from_example(example[0])}
            return {"type": "array"}
        else:
            return self._get_type_from_value(example)

    def _get_type_from_value(self, value: Any) -> Dict[str, str]:
        """Get JSON schema type from a Python value"""
        if isinstance(value, bool):
            return {"type": "boolean"}
        elif isinstance(value, int):
            return {"type": "integer"}
        elif isinstance(value, float):
            return {"type": "number"}
        elif isinstance(value, str):
            return {"type": "string"}
        elif isinstance(value, list):
            return {"type": "array"}
        elif isinstance(value, dict):
            return {"type": "object"}
        else:
            return {"type": "string"}

    async def _parse_openapi_json(self, content: str, base_url: str) -> APIDocumentation:
        """Parse OpenAPI/Swagger JSON specification"""
        try:
            spec = json.loads(content)
            return self._extract_openapi_info(spec, base_url)
        except json.JSONDecodeError as e:
            raise Exception(f"Invalid JSON in OpenAPI spec: {str(e)}")

    async def _parse_openapi_yaml(self, content: str, base_url: str) -> APIDocumentation:
        """Parse OpenAPI/Swagger YAML specification"""
        try:
            spec = yaml.safe_load(content)
            return self._extract_openapi_info(spec, base_url)
        except yaml.YAMLError as e:
            raise Exception(f"Invalid YAML in OpenAPI spec: {str(e)}")

    def _extract_openapi_info(self, spec: Dict[str, Any], base_url: str) -> APIDocumentation:
        """Extract information from OpenAPI/Swagger specification"""
        # Extract basic info
        info = spec.get("info", {})
        servers = spec.get("servers", [])

        # Determine base URL
        api_base_url = ""
        if servers:
            api_base_url = servers[0].get("url", "")
        elif "host" in spec:
            scheme = spec.get("schemes", ["https"])[0]
            api_base_url = f"{scheme}://{spec['host']}{spec.get('basePath', '')}"

        api_doc = APIDocumentation(
            base_url=api_base_url,
            title=info.get("title", ""),
            version=info.get("version", ""),
            description=info.get("description", ""),
            auth_info=self._extract_auth_info(spec),
            schemas=spec.get("components", {}).get("schemas", {}) or spec.get("definitions", {}),
        )

        # Extract endpoints
        paths = spec.get("paths", {})
        for path, path_info in paths.items():
            for method, method_info in path_info.items():
                if method.upper() in ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]:
                    endpoint = self._create_endpoint_from_openapi(
                        path, method.upper(), method_info, spec
                    )
                    api_doc.endpoints.append(endpoint)

        return api_doc

    def _extract_auth_info(self, spec: Dict[str, Any]) -> Dict[str, Any]:
        """Extract authentication information from OpenAPI spec"""
        auth_info = {}

        # OpenAPI 3.0 security schemes
        components = spec.get("components", {})
        security_schemes = components.get("securitySchemes", {})

        # OpenAPI 2.0 security definitions
        if not security_schemes:
            security_schemes = spec.get("securityDefinitions", {})

        for name, scheme in security_schemes.items():
            auth_type = scheme.get("type", "")
            if auth_type == "http":
                auth_info[name] = {
                    "type": "bearer" if scheme.get("scheme") == "bearer" else "basic",
                    "header": scheme.get("bearerFormat", "Authorization"),
                }
            elif auth_type == "apiKey":
                auth_info[name] = {
                    "type": "api_key",
                    "header": scheme.get("name", "X-API-Key"),
                    "location": scheme.get("in", "header"),
                }
            elif auth_type == "oauth2":
                auth_info[name] = {"type": "oauth2", "flows": scheme.get("flows", {})}

        return auth_info

    def _create_endpoint_from_openapi(
        self, path: str, method: str, method_info: Dict[str, Any], spec: Dict[str, Any]
    ) -> APIEndpoint:
        """Create APIEndpoint from OpenAPI method information"""
        # Extract parameters
        parameters = {}
        for param in method_info.get("parameters", []):
            param_name = param.get("name", "")
            param_info = {
                "type": param.get("type", ""),
                "required": param.get("required", False),
                "description": param.get("description", ""),
                "location": param.get("in", "query"),  # query, path, header, etc.
            }
            parameters[param_name] = param_info

        # Extract request body schema
        body_schema = None
        request_body = method_info.get("requestBody")
        if request_body:
            content = request_body.get("content", {})
            if "application/json" in content:
                body_schema = content["application/json"].get("schema")

        # Extract response schema
        response_schema = None
        responses = method_info.get("responses", {})
        if "200" in responses:
            response_content = responses["200"].get("content", {})
            if "application/json" in response_content:
                response_schema = response_content["application/json"].get("schema")

        return APIEndpoint(
            path=path,
            method=HTTPMethod(method),
            description=method_info.get("summary", "") or method_info.get("description", ""),
            parameters=parameters,
            body_schema=body_schema,
            response_schema=response_schema,
            auth_required=bool(method_info.get("security")),
        )

    async def _parse_html_documentation(self, content: str, base_url: str) -> APIDocumentation:
        """Parse HTML documentation page using BeautifulSoup and LLM"""
        soup = BeautifulSoup(content, "html.parser")

        # Extract basic information
        title = soup.find("title")
        title_text = title.text.strip() if title else "API Documentation"

        # Try to find API base URL in the content
        api_base_url = self._extract_base_url_from_html(soup, base_url)

        # Extract text content for LLM analysis
        text_content = soup.get_text(separator=" ", strip=True)

        # Use LLM to parse the HTML content
        return await self._parse_with_llm(text_content, base_url, title_text, api_base_url)

    def _extract_base_url_from_html(self, soup: BeautifulSoup, doc_url: str) -> str:
        """Extract API base URL from HTML documentation"""
        # Look for common patterns
        patterns = [
            r"https?://[^/\s]+/api",
            r"https?://api\.[^/\s]+",
            r"Base URL[:\s]+([^\s<]+)",
            r"API endpoint[:\s]+([^\s<]+)",
        ]

        text = soup.get_text()
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                if match.groups():
                    return match.group(1)
                else:
                    return match.group(0)

        # Fallback: derive from documentation URL
        parsed_url = urllib.parse.urlparse(doc_url)
        return f"{parsed_url.scheme}://{parsed_url.netloc}/api"

    async def _parse_with_llm(
        self, content: str, base_url: str, title: str = "", api_base_url: str = ""
    ) -> APIDocumentation:
        """Use LLM to parse documentation content"""
        if not self.llm_service:
            raise Exception("LLM service not available for documentation parsing")

        # Limit content size for LLM processing
        max_content_length = 8000
        if len(content) > max_content_length:
            content = content[:max_content_length] + "... [content truncated]"

        prompt = f"""
        Analyze this API documentation and extract endpoint information in JSON format.

        Documentation Title: {title}
        Documentation URL: {base_url}
        Suggested API Base URL: {api_base_url}

        Documentation Content:
        {content}

        Please extract the following information and respond ONLY with valid JSON:
        {{
            "base_url": "API base URL",
            "title": "API title",
            "description": "API description",
            "auth_info": {{
                "type": "bearer|api_key|basic|oauth2",
                "header": "Authorization header name",
                "description": "Auth description"
            }},
            "endpoints": [
                {{
                    "path": "/endpoint/path",
                    "method": "GET|POST|PUT|DELETE|PATCH",
                    "description": "Endpoint description",
                    "parameters": {{
                        "param_name": {{
                            "type": "string|integer|boolean",
                            "required": true|false,
                            "description": "Parameter description",
                            "location": "query|path|header|body"
                        }}
                    }},
                    "auth_required": true|false,
                    "example_request": {{"key": "value"}},
                    "example_response": {{"key": "value"}}
                }}
            ]
        }}

        Focus on extracting practical endpoint information that can be used to make API calls.
        If authentication is mentioned, include details about how to use tokens/keys.
        """

        try:
            response = await self.llm_service.generate_response(
                [
                    {
                        "role": "system",
                        "content": "You are an expert at parsing API documentation. Always respond with valid JSON only.",
                    },
                    {"role": "user", "content": prompt},
                ]
            )

            # Extract JSON from response
            json_match = re.search(r"\{.*\}", response, re.DOTALL)
            if json_match:
                parsed_data = json.loads(json_match.group())
                return self._create_api_doc_from_llm_response(parsed_data)
            else:
                raise Exception("LLM did not return valid JSON")

        except Exception as e:
            self.logger.error(f"LLM parsing failed: {str(e)}")
            # Return basic documentation structure
            return APIDocumentation(
                base_url=api_base_url or base_url,
                title=title or "API Documentation",
                description="Documentation parsed from " + base_url,
            )

    def _create_api_doc_from_llm_response(self, data: Dict[str, Any]) -> APIDocumentation:
        """Create APIDocumentation from LLM parsed data"""
        api_doc = APIDocumentation(
            base_url=data.get("base_url", ""),
            title=data.get("title", ""),
            description=data.get("description", ""),
            auth_info=data.get("auth_info", {}),
        )

        # Convert endpoint data to APIEndpoint objects
        for endpoint_data in data.get("endpoints", []):
            try:
                endpoint = APIEndpoint(
                    path=endpoint_data.get("path", ""),
                    method=HTTPMethod(endpoint_data.get("method", "GET")),
                    description=endpoint_data.get("description", ""),
                    parameters=endpoint_data.get("parameters", {}),
                    auth_required=endpoint_data.get("auth_required", False),
                    example_request=endpoint_data.get("example_request"),
                    example_response=endpoint_data.get("example_response"),
                )
                api_doc.endpoints.append(endpoint)
            except Exception as e:
                self.logger.warning(f"Failed to parse endpoint: {str(e)}")

        return api_doc

    async def find_endpoint_for_request(
        self, api_doc: APIDocumentation, user_request: str
    ) -> Optional[APIEndpoint]:
        """Use LLM to find the best matching endpoint for a user request"""
        if not self.llm_service or not api_doc.endpoints:
            return None

        # Create endpoint descriptions for LLM
        endpoints_desc = []
        for i, endpoint in enumerate(api_doc.endpoints):
            desc = f"{i}: {endpoint.method.value} {endpoint.path} - {endpoint.description}"
            if endpoint.parameters:
                params = ", ".join(endpoint.parameters.keys())
                desc += f" (params: {params})"
            endpoints_desc.append(desc)

        prompt = f"""
        Given these available API endpoints and a user request, select the best matching endpoint.

        Available endpoints:
        {chr(10).join(endpoints_desc)}

        User request: "{user_request}"

        Respond with ONLY the endpoint number (0-{len(api_doc.endpoints)-1}) that best matches the user's request.
        If no endpoint matches well, respond with "none".
        """

        try:
            response = await self.llm_service.generate_response(
                [
                    {
                        "role": "system",
                        "content": "You are an expert at matching user requests to API endpoints. Respond with only the endpoint number.",
                    },
                    {"role": "user", "content": prompt},
                ]
            )

            response = response.strip().lower()
            if response == "none":
                return None

            try:
                endpoint_index = int(response)
                if 0 <= endpoint_index < len(api_doc.endpoints):
                    return api_doc.endpoints[endpoint_index]
            except ValueError:
                pass

        except Exception as e:
            self.logger.error(f"Failed to find matching endpoint: {str(e)}")

        return None

    async def construct_api_request_from_docs(
        self,
        api_doc: APIDocumentation,
        endpoint: APIEndpoint,
        user_request: str,
        auth_token: str = None,
    ) -> APIRequest:
        """Construct an APIRequest from documentation and user request"""
        # Build full URL
        full_url = api_doc.base_url.rstrip("/") + "/" + endpoint.path.lstrip("/")

        # Set up authentication
        auth_config = None
        if auth_token and (endpoint.auth_required or api_doc.auth_info):
            auth_info = api_doc.auth_info
            if auth_info.get("type") == "bearer":
                auth_config = AuthConfig(
                    auth_type=AuthType.BEARER, token=auth_token, token_prefix="Bearer"
                )
            elif auth_info.get("type") == "api_key":
                auth_config = AuthConfig(
                    auth_type=AuthType.API_KEY,
                    api_key=auth_token,
                    api_key_header=auth_info.get("header", "X-API-Key"),
                )

        # Extract parameters from user request using LLM if needed
        params = {}
        json_data = None

        if endpoint.parameters and self.llm_service:
            params = await self._extract_parameters_from_request(endpoint, user_request)

        return APIRequest(
            url=full_url,
            method=endpoint.method,
            params=params,
            json_data=json_data,
            auth_config=auth_config,
        )

    async def _extract_parameters_from_request(
        self, endpoint: APIEndpoint, user_request: str
    ) -> Dict[str, Any]:
        """Extract parameter values from user request using LLM"""
        if not self.llm_service:
            return {}

        # Create parameter descriptions
        param_descriptions = []
        for name, info in endpoint.parameters.items():
            desc = f"{name} ({info.get('type', 'string')}): {info.get('description', '')}"
            if info.get("required"):
                desc += " [REQUIRED]"
            param_descriptions.append(desc)

        prompt = f"""
        Extract parameter values from this user request for the API endpoint.

        Endpoint: {endpoint.method.value} {endpoint.path}
        Description: {endpoint.description}

        Available parameters:
        {chr(10).join(param_descriptions)}

        User request: "{user_request}"

        Respond with JSON containing only the parameter values mentioned or implied in the user request:
        {{"param_name": "value", "other_param": 123}}

        If no parameters can be extracted, respond with {{}}.
        """

        try:
            response = await self.llm_service.generate_response(
                [
                    {
                        "role": "system",
                        "content": "You are an expert at extracting API parameters from user requests. Always respond with valid JSON.",
                    },
                    {"role": "user", "content": prompt},
                ]
            )

            json_match = re.search(r"\{.*\}", response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())

        except Exception as e:
            self.logger.error(f"Failed to extract parameters: {str(e)}")

        return {}

    def _parse_llm_intent(self, message: str) -> Optional[APIRequest]:
        """Parse LLM message to extract API request details"""
        # This is a simplified parser - in practice, you might use the LLM to parse this
        patterns = {
            "url": r"(?:GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\s+([^\s]+)",
            "method": r"(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)",
            "headers": r"(?:header|headers?):\s*({[^}]+}|\S+:\s*\S+)",
            "data": r"(?:data|body|payload):\s*({[^}]+})",
            "params": r"(?:params|query):\s*({[^}]+})",
            "bearer_token": r"(?:Bearer\s+token|with\s+Bearer\s+token)\s+([^\s]+)",
        }

        # Extract URL and method
        url_match = re.search(patterns["url"], message, re.IGNORECASE)
        method_match = re.search(patterns["method"], message, re.IGNORECASE)

        if not url_match:
            return None

        url = url_match.group(1)
        method = HTTPMethod(method_match.group(1).upper()) if method_match else HTTPMethod.GET

        # Add https:// protocol if missing
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url

        # Extract Bearer token
        auth_config = None
        bearer_match = re.search(patterns["bearer_token"], message, re.IGNORECASE)
        if bearer_match:
            token = bearer_match.group(1)
            auth_config = AuthConfig(
                auth_type=AuthType.BEARER,
                token=token,
                token_prefix="Bearer"
            )

        # Extract other components
        headers = None
        json_data = None
        params = None

        try:
            headers_match = re.search(patterns["headers"], message, re.IGNORECASE)
            if headers_match:
                headers_str = headers_match.group(1)
                if headers_str.startswith("{"):
                    headers = json.loads(headers_str)

            data_match = re.search(patterns["data"], message, re.IGNORECASE)
            if data_match:
                json_data = json.loads(data_match.group(1))

            params_match = re.search(patterns["params"], message, re.IGNORECASE)
            if params_match:
                params = json.loads(params_match.group(1))

        except json.JSONDecodeError:
            pass

        return APIRequest(
            url=url, 
            method=method, 
            headers=headers, 
            json_data=json_data, 
            params=params,
            auth_config=auth_config,
            timeout=8  # Use safe timeout by default
        )

    async def process_message(
        self, message: Union[str, AgentMessage], context: Optional[Dict[str, Any]] = None
    ) -> AgentMessage:
        """Process incoming message with intelligent documentation parsing and API calls"""
        try:
            # Handle both string and AgentMessage inputs for compatibility
            if isinstance(message, AgentMessage):
                message_text = message.content
                # Use message metadata if available
                if context is None:
                    context = message.metadata or {}
            else:
                message_text = message

            # Check if this is a documentation parsing + API call request
            doc_and_api_request = await self._parse_documentation_request(message_text)

            if doc_and_api_request:
                return await self._handle_documentation_api_request(
                    doc_and_api_request, message_text, context, message
                )

            # Try to parse as direct API request
            api_request = self._parse_llm_intent(message_text)

            if api_request:
                # Make the API request
                response = await self.make_api_request(api_request)

                # Format response
                if response.error:
                    content = f"❌ API Request Failed: {response.error}"
                else:
                    content = f"✅ API Response (HTTP {response.status_code}):\n"
                    content += f"URL: {response.url}\n"
                    content += f"Duration: {response.duration_ms:.0f}ms\n"

                    # Handle response content with file output support
                    if response.json_data:
                        json_content = json.dumps(response.json_data, indent=2)
                        
                        if self._should_save_to_file(json_content):
                            file_path, file_summary = await self._save_response_to_file(
                                json_content, response.url, "GET", response.headers  # Default to GET for non-streaming
                            )
                            
                            if file_path:
                                content += f"\n{file_summary}\n\n"
                                preview_content = self._get_inline_content_preview(json_content, "json")
                                content += f"JSON Response Preview:\n```json\n{preview_content}\n```"
                            else:
                                content += f"JSON Response:\n```json\n{json_content}\n```"
                        else:
                            content += f"JSON Response:\n```json\n{json_content}\n```"
                    else:
                        response_content = response.content
                        
                        if self._should_save_to_file(response_content):
                            file_path, file_summary = await self._save_response_to_file(
                                response_content, response.url, "GET", response.headers
                            )
                            
                            if file_path:
                                content += f"\n{file_summary}\n\n"
                                content_type = self._detect_content_type(response_content, response.headers)
                                preview_content = self._get_inline_content_preview(response_content, content_type)
                                content += f"Content Preview:\n```{content_type}\n{preview_content}\n```"
                            else:
                                content += f"Content: {response_content[:1000]}{'...' if len(response_content) > 1000 else ''}"
                        else:
                            content += f"Content: {response_content[:1000]}{'...' if len(response_content) > 1000 else ''}"

                return self.create_response(
                    content=content,
                    recipient_id=self.context.user_id,
                    message_type=MessageType.AGENT_RESPONSE,
                    metadata={
                        "api_response": response,
                        "status_code": response.status_code,
                        "duration_ms": response.duration_ms,
                    },
                )
            else:
                # Use LLM to understand the request
                # Prepare context with recipient_id
                llm_context = context.copy() if context else {}
                if isinstance(message, AgentMessage):
                    llm_context["recipient_id"] = message.sender_id
                else:
                    llm_context["recipient_id"] = self.context.user_id

                return await self._process_with_llm(message_text, llm_context)

        except Exception as e:
            self.logger.error(f"Error processing message: {str(e)}")
            return self.create_response(
                content=f"Error processing API request: {str(e)}",
                recipient_id=self.context.user_id,
                message_type=MessageType.ERROR,
                metadata={"error": str(e)},
            )

    async def _parse_documentation_request(self, message: str) -> Optional[Dict[str, Any]]:
        """Parse requests that involve reading documentation and making API calls"""
        message_lower = message.lower()

        # Look for patterns indicating documentation + API request
        doc_patterns = [
            r"read\s+(?:docs?|documentation)\s+(?:at\s+|from\s+)?([^\s]+)",
            r"parse\s+(?:docs?|documentation)\s+(?:at\s+|from\s+)?([^\s]+)",
            r"(?:docs?|documentation)\s+(?:at\s+|from\s+)?([^\s]+)",
            r"check\s+(?:docs?|documentation)\s+(?:at\s+|from\s+)?([^\s]+)",
        ]

        doc_url = None
        for pattern in doc_patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                doc_url = match.group(1)
                break

        if not doc_url:
            return None

        # Look for authentication token
        token_patterns = [
            r"(?:token|key|auth(?:orization)?)[:\s]+([^\s]+)",
            r"use\s+(?:token|key)\s+([^\s]+)",
            r"with\s+(?:token|key)\s+([^\s]+)",
        ]

        token = None
        for pattern in token_patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                token = match.group(1)
                break

        # Look for specific API request
        api_request_patterns = [
            r"(?:call|invoke|use|get|fetch)\s+(?:the\s+)?([^.]+?)(?:\s+(?:api|endpoint))",
            r"(?:api|endpoint)\s+(?:for\s+)?([^.]+)",
            r"then\s+([^.]+?)(?:\s+(?:api|endpoint|call))?",
            r"and\s+(?:then\s+)?(?:call|get|fetch|use)\s+(?:the\s+)?([^.]+?)(?:\s+(?:api|endpoint))?",
            r"and\s+(?:with\s+token\s+\w+\s+)?([^.]+?)(?:\s+(?:api|endpoint))?$",
            r"to\s+(?:call|get|fetch|list)\s+([^.]+?)(?:\s+(?:api|endpoint))?",
        ]

        api_request_description = None
        for pattern in api_request_patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                api_request_description = match.group(1).strip()
                break

        if doc_url and api_request_description:
            return {
                "doc_url": doc_url,
                "token": token,
                "api_request": api_request_description,
                "full_message": message,
            }

        return None

    async def _handle_documentation_api_request(
        self,
        request_info: Dict[str, Any],
        original_message: str,
        context: Optional[Dict[str, Any]],
        message_obj: Union[str, AgentMessage],
    ) -> AgentMessage:
        """Handle requests that involve reading docs and making API calls"""
        doc_url = request_info["doc_url"]
        token = request_info.get("token")
        api_request_desc = request_info["api_request"]

        try:
            # Step 1: Parse the documentation
            status_msg = f"📚 Reading API documentation from {doc_url}..."
            self.logger.info(status_msg)

            api_doc = await self.parse_api_documentation(doc_url)

            if not api_doc.endpoints:
                # Determine recipient_id from original message if available
                recipient_id = "user"  # Default fallback
                if isinstance(message_obj, AgentMessage):
                    recipient_id = message_obj.sender_id

                return self.create_response(
                    content=f"❌ No API endpoints found in documentation at {doc_url}",
                    recipient_id=recipient_id,
                    message_type=MessageType.ERROR,
                    metadata={"error": "No endpoints found"},
                )

            # Step 2: Find the matching endpoint
            endpoint = await self.find_endpoint_for_request(api_doc, api_request_desc)

            if not endpoint:
                # List available endpoints for user
                endpoint_list = []
                for ep in api_doc.endpoints[:10]:  # Limit to first 10
                    endpoint_list.append(f"- {ep.method.value} {ep.path}: {ep.description}")

                content = f"❌ Could not find matching endpoint for '{api_request_desc}'\n\n"
                content += f"📋 Available endpoints in {api_doc.title}:\n"
                content += "\n".join(endpoint_list)
                if len(api_doc.endpoints) > 10:
                    content += f"\n... and {len(api_doc.endpoints) - 10} more endpoints"

                # Determine recipient_id from original message if available
                recipient_id = "user"  # Default fallback
                if isinstance(message_obj, AgentMessage):
                    recipient_id = message_obj.sender_id

                return self.create_response(
                    content=content,
                    recipient_id=recipient_id,
                    message_type=MessageType.AGENT_RESPONSE,
                    metadata={"api_doc": api_doc, "endpoints_found": len(api_doc.endpoints)},
                )

            # Step 3: Construct the API request
            api_request = await self.construct_api_request_from_docs(
                api_doc, endpoint, api_request_desc, token
            )

            # Step 4: Make the API call
            self.logger.info(f"🚀 Making API call to {endpoint.method.value} {endpoint.path}")
            response = await self.make_api_request(api_request)

            # Step 5: Format the response
            if response.error:
                content = f"❌ API Request Failed: {response.error}\n\n"
                content += f"📋 Attempted: {endpoint.method.value} {api_request.url}"
            else:
                content = f"✅ Successfully called {api_doc.title} API!\n\n"
                content += f"📡 **Endpoint**: {endpoint.method.value} {endpoint.path}\n"
                content += f"📄 **Description**: {endpoint.description}\n"
                content += f"🔗 **URL**: {response.url}\n"
                content += f"⏱️ **Duration**: {response.duration_ms:.0f}ms\n"
                content += f"📊 **Status**: HTTP {response.status_code}\n\n"

                if response.json_data:
                    content += f"📦 **JSON Response**:\n```json\n{json.dumps(response.json_data, indent=2)}\n```"
                else:
                    content += f"📄 **Content**: {response.content[:1000]}{'...' if len(response.content) > 1000 else ''}"

            # Determine recipient_id from original message if available
            recipient_id = "user"  # Default fallback
            if isinstance(message_obj, AgentMessage):
                recipient_id = message_obj.sender_id

            return self.create_response(
                content=content,
                recipient_id=recipient_id,
                message_type=MessageType.AGENT_RESPONSE,
                metadata={
                    "api_doc": api_doc,
                    "endpoint": endpoint,
                    "api_response": response,
                    "status_code": response.status_code,
                    "duration_ms": response.duration_ms,
                    "doc_parsing_success": True,
                },
            )

        except Exception as e:
            self.logger.error(f"Error in documentation API request: {str(e)}")
            # Determine recipient_id from original message if available
            recipient_id = "user"  # Default fallback
            if isinstance(message_obj, AgentMessage):
                recipient_id = message_obj.sender_id

            return self.create_response(
                content=f"❌ Error processing documentation request: {str(e)}\n\n"
                f"I tried to:\n1. Read docs from: {doc_url}\n"
                f"2. Find endpoint for: {api_request_desc}\n"
                f"3. Make API call with token: {'Yes' if token else 'No'}",
                recipient_id=recipient_id,
                message_type=MessageType.ERROR,
                metadata={"error": str(e), "doc_url": doc_url},
            )

    async def process_message_stream(
        self, message: Union[str, AgentMessage], context: Optional[Dict[str, Any]] = None
    ) -> AsyncIterator[StreamChunk]:
        """Process message with streaming support for both direct API calls and documentation parsing"""
        yield StreamChunk(
            text="🔄 Processing API request...",
            sub_type=StreamSubType.STATUS,
            metadata={"status": "processing"},
        )

        try:
            # Handle both string and AgentMessage inputs for compatibility
            if isinstance(message, AgentMessage):
                message_text = message.content
                # Use message metadata if available
                if context is None:
                    context = message.metadata or {}
            else:
                message_text = message

            # Check if this is a documentation parsing + API call request
            doc_and_api_request = await self._parse_documentation_request(message_text)

            if doc_and_api_request:
                # Stream the documentation parsing workflow
                async for chunk in self._handle_documentation_api_request_stream(
                    doc_and_api_request, message_text, context, message
                ):
                    yield chunk
                return

            # Try to parse as direct API request
            api_request = self._parse_llm_intent(message_text)

            if api_request:
                yield StreamChunk(
                    text=f"📡 Making {api_request.method.value} request to {api_request.url}",
                    sub_type=StreamSubType.STATUS,
                )

                response = await self.make_api_request(api_request)

                if response.error:
                    yield StreamChunk(
                        text=f"❌ Request failed: {response.error}",
                        sub_type=StreamSubType.ERROR,
                        metadata={"error": response.error},
                    )
                else:
                    yield StreamChunk(
                        text=f"✅ Success! HTTP {response.status_code} ({response.duration_ms:.0f}ms)",
                        sub_type=StreamSubType.STATUS,
                    )

                    if response.json_data:
                        yield StreamChunk(
                            text=f"📦 **JSON Response**:\n```json\n{json.dumps(response.json_data, indent=2)}\n```",
                            sub_type=StreamSubType.CONTENT,
                            metadata={"content_type": "json"},
                        )
                    else:
                        yield StreamChunk(
                            text=f"📄 **Content**: {response.content}",
                            sub_type=StreamSubType.CONTENT,
                            metadata={"content_type": "text"},
                        )
            else:
                # Stream LLM response
                # Prepare context with recipient_id
                llm_context = context.copy() if context else {}
                if isinstance(message, AgentMessage):
                    llm_context["recipient_id"] = message.sender_id
                else:
                    llm_context["recipient_id"] = self.context.user_id

                async for chunk in self._process_with_llm_stream(message_text, llm_context):
                    yield chunk

        except Exception as e:
            yield StreamChunk(
                text=f"Error: {str(e)}",
                sub_type=StreamSubType.ERROR,
                metadata={"error": str(e)},
            )

    async def _handle_documentation_api_request_stream(
        self,
        request_info: Dict[str, Any],
        original_message: str,
        context: Optional[Dict[str, Any]],
        message_obj: Union[str, AgentMessage],
    ) -> AsyncIterator[StreamChunk]:
        """Stream the documentation parsing and API call workflow"""
        doc_url = request_info["doc_url"]
        token = request_info.get("token")
        api_request_desc = request_info["api_request"]

        try:
            # Step 1: Parse the documentation
            yield StreamChunk(
                text=f"📚 Reading API documentation from {doc_url}...",
                sub_type=StreamSubType.STATUS,
                metadata={"step": "parsing_documentation"},
            )

            api_doc = await self.parse_api_documentation(doc_url)

            if not api_doc.endpoints:
                yield StreamChunk(
                    text=f"❌ No API endpoints found in documentation at {doc_url}",
                    sub_type=StreamSubType.ERROR,
                    metadata={"error": "No endpoints found"},
                )
                return

            yield StreamChunk(
                text=f"✅ Found {len(api_doc.endpoints)} endpoints in {api_doc.title}",
                sub_type=StreamSubType.STATUS,
                metadata={"endpoints_found": len(api_doc.endpoints)},
            )

            # Step 2: Find the matching endpoint
            yield StreamChunk(
                text=f"🔍 Finding endpoint for: '{api_request_desc}'...",
                sub_type=StreamSubType.STATUS,
                metadata={"step": "finding_endpoint"},
            )

            endpoint = await self.find_endpoint_for_request(api_doc, api_request_desc)

            if not endpoint:
                # List available endpoints for user
                endpoint_list = []
                for ep in api_doc.endpoints[:5]:  # Limit to first 5 for streaming
                    endpoint_list.append(f"- {ep.method.value} {ep.path}: {ep.description}")

                yield StreamChunk(
                    text=f"❌ Could not find matching endpoint for '{api_request_desc}'",
                    sub_type=StreamSubType.ERROR,
                    metadata={"available_endpoints": len(api_doc.endpoints)},
                )

                yield StreamChunk(
                    text=f"📋 Available endpoints in {api_doc.title}:\n" + "\n".join(endpoint_list),
                    sub_type=StreamSubType.CONTENT,
                    metadata={"content_type": "endpoint_list"},
                )

                if len(api_doc.endpoints) > 5:
                    yield StreamChunk(
                        text=f"... and {len(api_doc.endpoints) - 5} more endpoints",
                        sub_type=StreamSubType.STATUS,
                    )
                return

            yield StreamChunk(
                text=f"✅ Found matching endpoint: {endpoint.method.value} {endpoint.path}",
                sub_type=StreamSubType.STATUS,
                metadata={"endpoint": f"{endpoint.method.value} {endpoint.path}"},
            )

            # Step 3: Construct the API request
            yield StreamChunk(
                text=f"🔧 Constructing API request with authentication...",
                sub_type=StreamSubType.STATUS,
                metadata={"step": "constructing_request"},
            )

            api_request = await self.construct_api_request_from_docs(
                api_doc, endpoint, api_request_desc, token
            )

            # Step 4: Make the API call
            yield StreamChunk(
                text=f"🚀 Making API call to {endpoint.method.value} {endpoint.path}",
                sub_type=StreamSubType.STATUS,
                metadata={"step": "making_api_call"},
            )

            response = await self.make_api_request(api_request)

            # Step 5: Stream the response
            if response.error:
                yield StreamChunk(
                    text=f"❌ API Request Failed: {response.error}",
                    sub_type=StreamSubType.ERROR,
                    metadata={"error": response.error, "endpoint": f"{endpoint.method.value} {endpoint.path}"},
                )
                yield StreamChunk(
                    text=f"📋 Attempted: {endpoint.method.value} {api_request.url}",
                    sub_type=StreamSubType.STATUS,
                )
            else:
                yield StreamChunk(
                    text=f"✅ Successfully called {api_doc.title} API!",
                    sub_type=StreamSubType.STATUS,
                    metadata={"success": True, "status_code": response.status_code},
                )

                # Stream endpoint details
                yield StreamChunk(
                    text=f"📡 **Endpoint**: {endpoint.method.value} {endpoint.path}",
                    sub_type=StreamSubType.CONTENT,
                )

                yield StreamChunk(
                    text=f"📄 **Description**: {endpoint.description}",
                    sub_type=StreamSubType.CONTENT,
                )

                yield StreamChunk(
                    text=f"🔗 **URL**: {response.url}",
                    sub_type=StreamSubType.CONTENT,
                )

                yield StreamChunk(
                    text=f"⏱️ **Duration**: {response.duration_ms:.0f}ms",
                    sub_type=StreamSubType.CONTENT,
                )

                yield StreamChunk(
                    text=f"📊 **Status**: HTTP {response.status_code}",
                    sub_type=StreamSubType.CONTENT,
                )

                # Stream response data with file output support
                if response.json_data:
                    # Convert JSON data to string for file operations
                    json_content = json.dumps(response.json_data, indent=2)
                    
                    # Check if we should save to file
                    if self._should_save_to_file(json_content):
                        file_path, file_summary = await self._save_response_to_file(
                            json_content, response.url, endpoint.method.value, response.headers
                        )
                        
                        if file_path:
                            # Provide file saved notification
                            yield StreamChunk(
                                text=file_summary,
                                sub_type=StreamSubType.STATUS,
                                metadata={"file_saved": True, "file_path": file_path, "content_type": "json"},
                            )
                            
                            # Show truncated preview
                            preview_content = self._get_inline_content_preview(json_content, "json")
                            yield StreamChunk(
                                text=f"📦 **JSON Response Preview**:\n```json\n{preview_content}\n```",
                                sub_type=StreamSubType.CONTENT,
                                metadata={"content_type": "json", "truncated": True, "file_path": file_path},
                            )
                        else:
                            # Fallback to full content if file save failed
                            yield StreamChunk(
                                text=f"📦 **JSON Response**:\n```json\n{json_content}\n```",
                                sub_type=StreamSubType.CONTENT,
                                metadata={"content_type": "json", "data": response.json_data},
                            )
                    else:
                        # Small response - show inline
                        yield StreamChunk(
                            text=f"📦 **JSON Response**:\n```json\n{json_content}\n```",
                            sub_type=StreamSubType.CONTENT,
                            metadata={"content_type": "json", "data": response.json_data},
                        )
                else:
                    # Handle non-JSON content
                    content = response.content
                    
                    # Check if we should save to file
                    if self._should_save_to_file(content):
                        file_path, file_summary = await self._save_response_to_file(
                            content, response.url, endpoint.method.value, response.headers
                        )
                        
                        if file_path:
                            # Provide file saved notification
                            yield StreamChunk(
                                text=file_summary,
                                sub_type=StreamSubType.STATUS,
                                metadata={"file_saved": True, "file_path": file_path, "content_type": "text"},
                            )
                            
                            # Show truncated preview
                            content_type = self._detect_content_type(content, response.headers)
                            preview_content = self._get_inline_content_preview(content, content_type)
                            yield StreamChunk(
                                text=f"📄 **Content Preview**:\n```{content_type}\n{preview_content}\n```",
                                sub_type=StreamSubType.CONTENT,
                                metadata={"content_type": content_type, "truncated": True, "file_path": file_path},
                            )
                        else:
                            # Fallback to truncated content if file save failed
                            content_preview = content[:1000]
                            if len(content) > 1000:
                                content_preview += "..."
                            yield StreamChunk(
                                text=f"📄 **Content**: {content_preview}",
                                sub_type=StreamSubType.CONTENT,
                                metadata={"content_type": "text"},
                            )
                    else:
                        # Small response - show inline (limited preview)
                        content_preview = content[:1000]
                        if len(content) > 1000:
                            content_preview += "..."
                        yield StreamChunk(
                            text=f"📄 **Content**: {content_preview}",
                            sub_type=StreamSubType.CONTENT,
                            metadata={"content_type": "text"},
                        )

        except Exception as e:
            yield StreamChunk(
                text=f"❌ Error processing documentation request: {str(e)}",
                sub_type=StreamSubType.ERROR,
                metadata={"error": str(e), "doc_url": doc_url},
            )

            yield StreamChunk(
                text=f"I tried to:\n1. Read docs from: {doc_url}\n2. Find endpoint for: {api_request_desc}\n3. Make API call with token: {'Yes' if token else 'No'}",
                sub_type=StreamSubType.STATUS,
            )

    async def _process_with_llm(
        self, message: str, context: Optional[Dict[str, Any]] = None
    ) -> AgentMessage:
        """Process message using LLM when direct parsing fails"""
        # Add conversation context
        messages = [
            {"role": "system", "content": self.system_message},
            {"role": "user", "content": message},
        ]

        # Add conversation history
        if hasattr(self, "memory_manager") and self.memory_manager:
            history = await self.get_conversation_history(limit=5)
            for msg in history[-5:]:
                role = "assistant" if msg.get("role") == "agent" else "user"
                messages.insert(-1, {"role": role, "content": msg.get("content", "")})

        try:
            response = await self.llm_service.generate_response(messages)
            return self.create_response(
                content=response,
                recipient_id=context.get("recipient_id", "user"),
                message_type=MessageType.AGENT_RESPONSE,
                metadata={"llm_processed": True},
            )
        except Exception as e:
            return self.create_response(
                content=f"Failed to process request with LLM: {str(e)}",
                recipient_id=context.get("recipient_id", "user"),
                message_type=MessageType.ERROR,
                metadata={"error": str(e)},
            )

    async def _process_with_llm_stream(
        self, message: str, context: Optional[Dict[str, Any]] = None
    ) -> AsyncIterator[StreamChunk]:
        """Process message using LLM with streaming"""
        messages = [
            {"role": "system", "content": self.system_message},
            {"role": "user", "content": message},
        ]

        try:
            if hasattr(self.llm_service, 'generate_response_stream'):
                async for chunk in self.llm_service.generate_response_stream(messages):
                    yield StreamChunk(text=chunk, sub_type=StreamSubType.CONTENT)
            else:
                # Fallback to non-streaming LLM response
                response = await self.llm_service.generate_response(messages)
                yield StreamChunk(text=response, sub_type=StreamSubType.CONTENT)
        except Exception as e:
            yield StreamChunk(
                text=f"LLM processing error: {str(e)}",
                sub_type=StreamSubType.ERROR,
                metadata={"error": str(e)},
            )
