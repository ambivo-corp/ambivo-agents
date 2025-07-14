#!/usr/bin/env python3
"""
Enhanced Ambivo Agents CLI with Full Environment Variable Support - Version 1.1

This version properly integrates with your loader.py environment variable system
and maintains session history through agent caching.

Author: Hemant Gosain 'Sunny'
Company: Ambivo
Email: sgosain@ambivo.com
License: MIT
"""

import asyncio
import json
import logging
import os
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union

import click
import yaml

# Import agents directly using clean imports
from ambivo_agents import (
    AnalyticsAgent,
    APIAgent,
    AssistantAgent,
    CodeExecutorAgent,
    KnowledgeBaseAgent,
    MediaEditorAgent,
    WebScraperAgent,
    WebSearchAgent,
    YouTubeDownloadAgent,
)

# Import AgentSession with fallback
try:
    from ambivo_agents import AgentSession

    AGENT_SESSION_AVAILABLE = True
except ImportError:
    try:
        from ambivo_agents.core.base import AgentSession

        AGENT_SESSION_AVAILABLE = True
    except ImportError:
        AGENT_SESSION_AVAILABLE = False
        AgentSession = None

# ✅ ENHANCED: Import your loader.py for proper ENV support
try:
    from ambivo_agents.config.loader import ConfigurationError, get_config_section, load_config

    LOADER_AVAILABLE = True
    print("✅ Using ambivo_agents configuration loader with environment variable support")
except ImportError:
    LOADER_AVAILABLE = False
    print("⚠️  ambivo_agents.config.loader not available - using fallback configuration")

# Fallback to service for complex routing if needed
try:
    from ambivo_agents.services import create_agent_service

    SERVICE_AVAILABLE = True
except ImportError:
    SERVICE_AVAILABLE = False


# Import ModeratorAgent for enhanced routing
try:
    from ambivo_agents.agents.moderator import ModeratorAgent
    from ambivo_agents.core.base import AgentContext

    MODERATOR_AVAILABLE = True
except ImportError as e:
    MODERATOR_AVAILABLE = False
    ModeratorAgent = None


class EnhancedConfigManager:
    """Enhanced configuration manager that properly uses your loader.py system"""

    def __init__(self, config_path: Optional[str] = None, use_env_vars: Optional[bool] = None):
        self.config_path = config_path
        self.use_env_vars = use_env_vars
        self.config = None
        self.config_source = "unknown"

        self._load_configuration()

    def _load_configuration(self):
        """Load configuration using your loader.py system with full ENV support"""

        if LOADER_AVAILABLE:
            # ✅ USE YOUR LOADER.PY - Supports ENV vars + YAML + defaults
            try:
                self.config = load_config(
                    config_path=self.config_path, use_env_vars=self.use_env_vars
                )
                self.config_source = self.config.get("_config_source", "loader.py")

                print(f"✅ Configuration loaded via loader.py from: {self.config_source}")

                # Show what type of config was loaded
                if "environment variables" in self.config_source:
                    print("🌍 Using environment variables (AMBIVO_AGENTS_ prefix)")
                elif "YAML" in self.config_source:
                    print(f"📄 Using YAML file: {self.config_path or 'auto-detected'}")
                elif "defaults" in self.config_source:
                    print("⚙️  Using minimal defaults")

                return

            except ConfigurationError as e:
                print(f"❌ Configuration error: {e}")
                print("💡 Falling back to create agent_config.yaml...")
                self._prompt_for_config_creation()

            except Exception as e:
                print(f"⚠️  Unexpected error with loader.py: {e}")
                print("💡 Using fallback configuration system...")
                self._use_fallback_config()
        else:
            # Fallback to basic config if loader.py not available
            self._use_fallback_config()

    def _use_fallback_config(self):
        """Fallback configuration system"""
        self.config = self._get_default_config()
        self.config_source = "fallback_defaults"

        # Try to load agent_config.yaml if it exists
        possible_paths = [
            "./agent_config.yaml",
            "./agent_config.yml",
            "~/.ambivo/agent_config.yaml",
        ]

        for path_str in possible_paths:
            path = Path(path_str).expanduser()
            if path.exists():
                try:
                    with open(path, "r") as f:
                        file_config = yaml.safe_load(f)
                        if file_config:
                            self._merge_config(self.config, file_config)
                            self.config_source = f"fallback_yaml:{path}"
                            print(f"📄 Loaded YAML config: {path}")
                            return
                except Exception as e:
                    print(f"⚠️  Warning loading {path}: {e}")

        # Prompt for config creation if none found
        if not any(Path(p).expanduser().exists() for p in possible_paths):
            self._prompt_for_config_creation()

    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration structure"""
        return {
            "cli": {
                "version": "1.1.0",
                "default_mode": "shell",
                "auto_session": True,
                "session_prefix": "ambivo",
                "verbose": False,
                "theme": "default",
            },
            "agents": {
                "youtube": {"default_audio_only": True, "output_directory": "./downloads"},
                "media": {"supported_formats": ["mp4", "avi", "mov", "mp3", "wav"]},
                "web_search": {"default_max_results": 5},
                "moderator": {"enabled": MODERATOR_AVAILABLE},
            },
            "agent_capabilities": {
                "enable_knowledge_base": True,
                "enable_web_search": True,
                "enable_code_execution": True,
                "enable_media_editor": True,
                "enable_youtube_download": True,
                "enable_web_scraping": True,
                "enable_proxy_mode": True,
                "enable_api_agent": True,
            },
            "session": {"auto_cleanup": True, "session_timeout": 3600},
            "mcp": {
                "enabled": False,
                "server": {"enabled": False, "name": "ambivo-agents"},
                "client": {"enabled": False},
            },
            "_config_source": "defaults",
        }

    def _prompt_for_config_creation(self):
        """Prompt user to create agent_config.yaml with environment variable info"""
        print("\n📋 No configuration found!")
        print("💡 You can configure Ambivo Agents in two ways:")
        print("   1. 📄 Create agent_config.yaml file")
        print("   2. 🌍 Set environment variables with AMBIVO_AGENTS_ prefix")
        print()
        print("🌍 Environment Variable Examples:")
        print("   export AMBIVO_AGENTS_REDIS_HOST=localhost")
        print("   export AMBIVO_AGENTS_REDIS_PORT=6379")
        print("   export AMBIVO_AGENTS_OPENAI_API_KEY=your_key_here")
        print("   export AMBIVO_AGENTS_ENABLE_WEB_SEARCH=true")
        print("   export AMBIVO_AGENTS_MCP_ENABLED=true")
        print()

        if click.confirm("📄 Create sample agent_config.yaml file?"):
            config_path = "./agent_config.yaml"
            if self.save_sample_config(config_path):
                print(f"✅ Created: {config_path}")
                print("💡 Edit this file to customize settings")
                print("🌍 Environment variables will override YAML settings")
                self.config_path = config_path

                # Reload with the new file
                if LOADER_AVAILABLE:
                    try:
                        self.config = load_config(config_path)
                        self.config_source = self.config.get("_config_source", "created_yaml")
                    except:
                        pass
            else:
                print("❌ Failed to create config file")
        else:
            print("💡 Continuing with defaults")
            print("🌍 Set environment variables to configure the system")

    def _merge_config(self, base: Dict, override: Dict):
        """Recursively merge configuration dictionaries"""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._merge_config(base[key], value)
            else:
                base[key] = value

    def get(self, path: str, default=None):
        """Get configuration value using dot notation"""
        if not self.config:
            return default

        keys = path.split(".")
        current = self.config

        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return default

        return current

    def save_sample_config(self, path: str):
        """Save a sample configuration file with MCP support"""
        sample_config = {
            "redis": {"host": "localhost", "port": 6379, "db": 0, "password": None},
            "llm": {
                "preferred_provider": "openai",
                "temperature": 0.7,
                "max_tokens": 4000,
                "openai_api_key": "your_openai_api_key_here",
                "anthropic_api_key": "your_anthropic_api_key_here",
            },
            "agent_capabilities": {
                "enable_knowledge_base": True,
                "enable_web_search": True,
                "enable_code_execution": True,
                "enable_media_editor": True,
                "enable_youtube_download": True,
                "enable_web_scraping": True,
                "enable_proxy_mode": True,
                "enable_api_agent": True,
            },
            "web_search": {"brave_api_key": "your_brave_api_key_here", "default_max_results": 10},
            "knowledge_base": {
                "qdrant_url": "your_qdrant_url_here",
                "qdrant_api_key": "your_qdrant_api_key_here",
                "chunk_size": 1024,
                "similarity_top_k": 5,
            },
            "mcp": {
                "enabled": False,
                "server": {
                    "enabled": False,
                    "name": "ambivo-agents",
                    "version": "1.0.0",
                    "stdio": True,
                },
                "client": {
                    "enabled": False,
                    "auto_connect_servers": ["filesystem", "github", "sqlite"],
                },
                "external_servers": {
                    "filesystem": {
                        "command": "npx",
                        "args": ["@modelcontextprotocol/server-filesystem", "/allowed/path"],
                        "capabilities": ["file_read", "file_write"],
                    },
                    "github": {
                        "command": "npx",
                        "args": ["@modelcontextprotocol/server-github"],
                        "capabilities": ["repo_access", "issue_management"],
                        "env": {"GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_TOKEN}"},
                    },
                },
            },
            "service": {"max_sessions": 100, "log_level": "INFO"},
        }

        try:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w") as f:
                # Write comments and config
                f.write("# Ambivo Agents Configuration\n")
                f.write(
                    "# Environment variables with AMBIVO_AGENTS_ prefix will override these settings\n"
                )
                f.write("# Example: export AMBIVO_AGENTS_REDIS_HOST=localhost\n")
                f.write("# Example: export AMBIVO_AGENTS_OPENAI_API_KEY=your_key_here\n\n")

                yaml.dump(sample_config, f, default_flow_style=False, indent=2)
            return True
        except Exception as e:
            print(f"❌ Failed to save sample config: {e}")
            return False


class AmbivoAgentsCLI:
    """Enhanced CLI with agent caching, session management, and full ENV support"""

    def __init__(self, config_manager: EnhancedConfigManager):
        self.config = config_manager
        self.user_id = "cli_user"
        self.tenant_id = "cli_tenant"
        self.session_metadata = {
            "cli_session": True,
            "version": self.config.get("cli.version", "1.1.0"),
            "mode": "shell_default",
            "config_source": self.config.config_source,
        }
        self.session_file = Path.home() / ".ambivo_agents_session"

        # ✅ AGENT CACHING SYSTEM - Preserves session history
        self._session_agents: Dict[str, Tuple[Any, Any]] = {}
        self._agent_creation_lock = asyncio.Lock()

        # MCP integration
        self.mcp_server = None
        self.mcp_client = None

        self._ensure_auto_session()

        # Check import status
        if not AGENT_SESSION_AVAILABLE:
            if self.config.get("cli.verbose", False):
                print("⚠️  Warning: AgentSession not available - some features may be limited")

    def _ensure_auto_session(self):
        """Automatically create a session if none exists and auto_session is enabled"""
        if self.config.get("cli.auto_session", True):
            current_session = self.get_current_session()
            if not current_session:
                session_id = str(uuid.uuid4())
                self.set_current_session(session_id)
                if self.config.get("cli.verbose", False):
                    print(f"🔄 Auto-created session: {session_id}")

    def get_current_session(self) -> Optional[str]:
        """Get the currently active session from file"""
        try:
            if self.session_file.exists():
                return self.session_file.read_text().strip()
        except Exception:
            pass
        return None

    def set_current_session(self, session_id: str):
        """Set the current session and save to file"""
        try:
            self.session_file.write_text(session_id)
            return True
        except Exception as e:
            print(f"❌ Failed to save session: {e}")
            return False

    def clear_current_session(self):
        """Clear the current session"""
        try:
            if self.session_file.exists():
                self.session_file.unlink()
            return True
        except Exception as e:
            print(f"❌ Failed to clear session: {e}")
            return False

    async def get_or_create_agent(
        self, agent_class, session_id: str = None, additional_metadata: Dict[str, Any] = None
    ):
        """
        ✅ ENHANCED: Get existing agent from cache or create new one
        This ensures agents are reused within sessions, preserving conversation history
        """
        if session_id is None:
            session_id = self.get_current_session()

        if not session_id:
            raise ValueError("No session ID available for agent creation")

        # Create cache key: agent_class + session_id
        cache_key = f"{agent_class.__name__}_{session_id}"

        async with self._agent_creation_lock:
            # ✅ CHECK CACHE FIRST - Reuses existing agents
            if cache_key in self._session_agents:
                agent, context = self._session_agents[cache_key]
                if self.config.get("cli.verbose", False):
                    print(f"🔄 Reusing cached {agent_class.__name__} (ID: {agent.agent_id})")
                    print(f"   📚 Agent retains conversation history and memory")
                return agent, context

            # Create new agent only if not in cache
            if self.config.get("cli.verbose", False):
                print(f"🆕 Creating new {agent_class.__name__} for session {session_id[:8]}...")

            metadata = {**self.session_metadata}
            if additional_metadata:
                metadata.update(additional_metadata)

            metadata["config"] = {
                "agent_type": agent_class.__name__,
                "configured": True,
                "cached": True,
                "session_id": session_id,
                "config_source": self.config.config_source,
            }

            # Use consistent agent_id based on session + agent type
            consistent_agent_id = f"{agent_class.__name__.lower()}_{session_id}"

            agent, context = agent_class.create(
                agent_id=consistent_agent_id,
                user_id=self.user_id,
                tenant_id=self.tenant_id,
                session_metadata=metadata,
                session_id=session_id,
                conversation_id=session_id,
            )

            # ✅ CACHE THE AGENT - Will be reused for subsequent calls
            self._session_agents[cache_key] = (agent, context)

            if self.config.get("cli.verbose", False):
                print(f"✅ Cached {agent_class.__name__} (ID: {agent.agent_id})")
                print(f"📊 Total cached agents: {len(self._session_agents)}")
                print(f"💾 Agent will retain memory across commands")

            return agent, context

    def clear_session_agents(self, session_id: str = None):
        """Clear cached agents for a specific session"""
        if session_id is None:
            session_id = self.get_current_session()

        if not session_id:
            return

        keys_to_remove = [key for key in self._session_agents.keys() if key.endswith(session_id)]

        for key in keys_to_remove:
            agent, context = self._session_agents[key]

            if self.config.get("cli.verbose", False):
                print(f"🗑️  Removing cached agent: {agent.agent_id}")

            try:
                asyncio.create_task(agent.cleanup_session())
            except Exception as e:
                print(f"⚠️  Warning during agent cleanup: {e}")

            del self._session_agents[key]

        if keys_to_remove and self.config.get("cli.verbose", False):
            print(f"🧹 Cleared {len(keys_to_remove)} agents for session {session_id[:8]}...")

    def clear_all_agents(self):
        """Clear all cached agents"""
        if self.config.get("cli.verbose", False):
            print(f"🧹 Clearing all {len(self._session_agents)} cached agents...")

        for key, (agent, context) in self._session_agents.items():
            try:
                asyncio.create_task(agent.cleanup_session())
            except Exception as e:
                print(f"⚠️  Warning during agent cleanup: {e}")

        self._session_agents.clear()

    def get_cached_agents_info(self) -> Dict[str, Any]:
        """Get information about cached agents"""
        info = {"total_agents": len(self._session_agents), "agents": []}

        for key, (agent, context) in self._session_agents.items():
            agent_info = {
                "cache_key": key,
                "agent_id": agent.agent_id,
                "agent_type": agent.__class__.__name__,
                "session_id": context.session_id,
                "created_at": context.created_at.isoformat(),
                "memory_available": hasattr(agent, "memory") and agent.memory is not None,
                "config_source": self.config.config_source,
            }
            info["agents"].append(agent_info)

        return info

    async def smart_message_routing(self, message: str) -> str:
        """
        ✅ ENHANCED: Smart routing with agent caching and full config support
        Uses cached agents to preserve conversation history across commands
        """
        message_lower = message.lower()
        current_session = self.get_current_session()

        if not current_session:
            raise ValueError("No active session for message processing")

        # If ModeratorAgent is available and enabled, use it for routing
        if MODERATOR_AVAILABLE and self.config.get("agents.moderator.enabled", False):
            return await self._route_with_moderator(message, current_session)

        # Otherwise use built-in routing logic with cached agents
        return await self._route_with_builtin_logic(message, current_session)

    async def _route_with_moderator(self, message: str, session_id: str) -> str:
        """Route message using ModeratorAgent (cached)"""
        try:
            # ✅ USE CACHED MODERATOR AGENT
            agent, context = await self.get_or_create_agent(
                ModeratorAgent, session_id, {"operation": "moderated_routing"}
            )

            response = await agent.chat(message)
            return response
        except Exception as e:
            # Fallback to built-in routing
            print(f"⚠️  ModeratorAgent routing failed, using fallback: {e}")
            return await self._route_with_builtin_logic(message, session_id)

    def _detect_code_execution_request(self, message: str) -> bool:
        """
        Enhanced detection for code execution requests

        Called by: _route_with_builtin_logic()
        Returns: True if message indicates code execution intent
        """
        message_lower = message.lower()

        # Strong code execution indicators with regex
        strong_patterns = [
            r"write.*code.*(?:execute|run)",  # "write code to ... then execute"
            r"(?:execute|run).*code",  # "execute code" or "run code"
            r"code.*(?:then|and).*(?:execute|run)",  # "code then execute"
            r"python.*(?:execute|run)",  # "python ... execute"
            r"write.*python.*(?:execute|run)",  # "write python ... execute"
            r"create.*code.*(?:execute|run)",  # "create code ... execute"
        ]

        # Check regex patterns first (strongest indicators)
        import re

        for pattern in strong_patterns:
            if re.search(pattern, message_lower):
                return True

        # Check keyword combinations (moderate indicators)
        has_write = any(word in message_lower for word in ["write", "create", "generate", "make"])
        has_code = any(word in message_lower for word in ["code", "script", "python", "program"])
        has_execute = any(
            word in message_lower for word in ["execute", "run", "test", "show result"]
        )

        # If all three present, it's definitely a code execution request
        return has_write and has_code and has_execute

    def _detect_api_request(self, message: str) -> bool:
        """
        Enhanced detection for API requests and documentation parsing
        
        Called by: _route_with_builtin_logic()
        Returns: True if message indicates API request intent
        """
        message_lower = message.lower()
        
        # Strong API indicators with regex
        strong_patterns = [
            r"(?:get|post|put|patch|delete|head|options)\s+https?://",  # HTTP method + URL
            r"api\s+call",  # "api call"
            r"call.*api",  # "call ... api"
            r"make.*(?:api|request)",  # "make api" or "make request"
            r"(?:read|parse).*(?:documentation|docs).*(?:api|call)",  # documentation parsing
            r"(?:documentation|docs).*(?:then|and).*(?:call|api|get)",  # docs then call
            r"postman.*collection",  # Postman collection
            r"openapi|swagger",  # OpenAPI/Swagger documentation
            r"rest.*api",  # REST API
            r"http.*(?:request|call)",  # HTTP request/call
        ]
        
        # Check regex patterns first (strongest indicators)
        import re
        
        for pattern in strong_patterns:
            if re.search(pattern, message_lower):
                return True
        
        # Check for URLs (moderate indicator)
        url_patterns = [
            r"https?://[^\s]+",  # Any HTTP/HTTPS URL
        ]
        
        has_url = any(re.search(pattern, message_lower) for pattern in url_patterns)
        
        # Check keyword combinations
        has_api = any(word in message_lower for word in ["api", "endpoint", "request", "call"])
        has_doc = any(word in message_lower for word in ["documentation", "docs", "postman", "swagger", "openapi"])
        has_http = any(word in message_lower for word in ["get", "post", "put", "patch", "delete", "http", "https"])
        has_action = any(word in message_lower for word in ["call", "invoke", "use", "fetch", "retrieve"])
        
        # Strong combinations that indicate API intent
        if has_doc and (has_api or has_action):  # Documentation + API/action
            return True
        if has_url and (has_api or has_http):  # URL + API/HTTP method
            return True
        if has_api and has_action:  # API + action word
            return True
        
        return False

    def _detect_analytics_request(self, message: str) -> bool:
        """
        Enhanced detection for analytics and data analysis requests
        
        Called by: _route_with_builtin_logic()
        Returns: True if message indicates analytics/data analysis intent
        """
        message_lower = message.lower()
        
        # Strong analytics indicators with regex
        strong_patterns = [
            r"(?:load|import|read|analyze|process).*(?:csv|excel|xls|xlsx|data|dataset)",  # Data loading
            r"(?:analyze|analysis).*(?:data|dataset|file)",  # Data analysis
            r"(?:create|generate|show).*(?:chart|graph|plot|visualization)",  # Visualization
            r"(?:sql|query).*(?:data|dataset|table)",  # SQL queries
            r"(?:schema|structure|columns).*(?:data|dataset|table)",  # Schema exploration
            r"(?:statistics|stats|summary).*(?:data|dataset)",  # Statistical analysis
            r"duckdb.*(?:query|analyze|load)",  # DuckDB specific
        ]
        
        # Check regex patterns first (strongest indicators)
        import re
        
        for pattern in strong_patterns:
            if re.search(pattern, message_lower):
                return True
        
        # Check for file extensions in message
        file_extensions = [".csv", ".xlsx", ".xls"]
        has_data_file = any(ext in message_lower for ext in file_extensions)
        
        # Check keyword combinations
        has_data = any(word in message_lower for word in ["data", "dataset", "csv", "excel", "spreadsheet"])
        has_analysis = any(word in message_lower for word in ["analyze", "analysis", "chart", "graph", "plot", "visualize", "statistics", "summary"])
        has_sql = any(word in message_lower for word in ["sql", "query", "select", "from", "where", "group by"])
        has_schema = any(word in message_lower for word in ["schema", "structure", "columns", "fields", "describe"])
        
        # Strong combinations that indicate analytics intent
        if has_data_file:  # File extension found
            return True
        if has_data and has_analysis:  # Data + analysis keywords
            return True
        if has_data and has_sql:  # Data + SQL keywords
            return True
        if has_data and has_schema:  # Data + schema keywords
            return True
        if any(word in message_lower for word in ["duckdb", "analytics", "dataframe", "pandas"]):  # Direct analytics tools
            return True
        
        return False

    async def _route_with_builtin_logic(self, message: str, session_id: str) -> str:
        """Built-in routing logic using cached agents"""
        """Built-in routing logic using cached agents - ENHANCED WITH CODE DETECTION"""
        message_lower = message.lower()

        if self._detect_code_execution_request(message):
            # ✅ ROUTE TO CODE EXECUTOR AGENT
            agent, context = await self.get_or_create_agent(
                CodeExecutorAgent, session_id, {"operation": "code_execution"}
            )

            try:
                # Let CodeExecutorAgent handle both writing AND executing
                from ambivo_agents.core.base import AgentMessage, MessageType

                agent_message = AgentMessage(
                    id=f"msg_{str(uuid.uuid4())[:8]}",
                    sender_id="cli_user",
                    recipient_id=agent.agent_id,
                    content=message,
                    message_type=MessageType.USER_INPUT,
                    session_id=context.session_id,
                    conversation_id=context.conversation_id,
                )

                response_message = await agent.process_message(
                    agent_message, context.to_execution_context()
                )
                return f"{response_message.content}\n\n🔧 *Processed by CodeExecutorAgent with code execution capabilities*"

            except Exception as e:
                return f"❌ Error in code execution: {str(e)}"

        # API Agent Detection - for API calls and documentation parsing
        elif self._detect_api_request(message):
            # ✅ ROUTE TO API AGENT
            agent, context = await self.get_or_create_agent(
                APIAgent, session_id, {"operation": "api_request"}
            )

            try:
                from ambivo_agents.core.base import AgentMessage, MessageType

                agent_message = AgentMessage(
                    id=f"msg_{str(uuid.uuid4())[:8]}",
                    sender_id="cli_user",
                    recipient_id=agent.agent_id,
                    content=message,
                    message_type=MessageType.USER_INPUT,
                    session_id=context.session_id,
                    conversation_id=context.conversation_id,
                )

                response_message = await agent.process_message(
                    agent_message, context.to_execution_context()
                )
                return f"{response_message.content}\n\n🌐 *Processed by APIAgent with intelligent documentation parsing*"

            except Exception as e:
                return f"❌ Error in API request: {str(e)}"

        # Analytics Agent Detection - for data analysis and visualization
        elif self._detect_analytics_request(message):
            # ✅ ROUTE TO ANALYTICS AGENT
            agent, context = await self.get_or_create_agent(
                AnalyticsAgent, session_id, {"operation": "data_analysis"}
            )

            try:
                from ambivo_agents.core.base import AgentMessage, MessageType

                agent_message = AgentMessage(
                    id=f"msg_{str(uuid.uuid4())[:8]}",
                    sender_id="cli_user",
                    recipient_id=agent.agent_id,
                    content=message,
                    message_type=MessageType.USER_INPUT,
                    session_id=context.session_id,
                    conversation_id=context.conversation_id,
                )

                response_message = await agent.process_message(
                    agent_message, context.to_execution_context()
                )
                return f"{response_message.content}\n\n📊 *Processed by AnalyticsAgent with DuckDB and Docker execution*"

            except Exception as e:
                return f"❌ Error in data analysis: {str(e)}"

        # YouTube Download Detection
        elif any(keyword in message_lower for keyword in ["youtube", "download", "youtu.be"]) and (
            "http" in message or "www." in message
        ):
            # ✅ REUSE CACHED YOUTUBE AGENT - Preserves download history
            agent, context = await self.get_or_create_agent(
                YouTubeDownloadAgent, session_id, {"operation": "youtube_download"}
            )

            try:
                import re

                youtube_patterns = [
                    r"https?://(?:www\.)?youtube\.com/watch\?v=[\w-]+",
                    r"https?://(?:www\.)?youtu\.be/[\w-]+",
                ]

                urls = []
                for pattern in youtube_patterns:
                    urls.extend(re.findall(pattern, message))

                if urls:
                    url = urls[0]
                    default_audio_only = self.config.get("agents.youtube.default_audio_only", True)
                    wants_video = any(
                        keyword in message_lower for keyword in ["video", "mp4", "watch", "visual"]
                    )
                    audio_only = default_audio_only if not wants_video else False

                    if "info" in message_lower or "information" in message_lower:
                        result = await agent._get_youtube_info(url)
                    else:
                        result = await agent._download_youtube(url, audio_only=audio_only)

                    # ✅ AGENT STAYS CACHED - No cleanup_session() call
                    if result["success"]:
                        return f"✅ YouTube operation completed!\n{result.get('message', '')}\nSession: {context.session_id}\nAgent: {agent.agent_id}\n🔄 Agent cached for future use"
                    else:
                        return f"❌ YouTube operation failed: {result['error']}"
                else:
                    return "❌ No valid YouTube URLs found in message"

            except Exception as e:
                return f"❌ YouTube operation error: {e}"

        # General Assistant (fallback)
        else:
            # ✅ REUSE CACHED ASSISTANT AGENT - Preserves full conversation history
            agent, context = await self.get_or_create_agent(
                AssistantAgent, session_id, {"operation": "general_assistance"}
            )

            try:
                from ambivo_agents.core.base import AgentMessage, MessageType

                agent_message = AgentMessage(
                    id=f"msg_{str(uuid.uuid4())[:8]}",
                    sender_id="cli_user",
                    recipient_id=agent.agent_id,
                    content=message,
                    message_type=MessageType.USER_INPUT,
                    session_id=context.session_id,
                    conversation_id=context.conversation_id,
                )

                response_message = await agent.process_message(
                    agent_message, context.to_execution_context()
                )
                return f"{response_message.content}"

            except Exception as e:
                return f"❌ Error processing your question: {e}"


# Initialize configuration and CLI
config_manager = None
cli_instance = None


def initialize_cli(
    config_path: Optional[str] = None, verbose: bool = False, use_env_vars: Optional[bool] = None
):
    """
    ✅ ENHANCED: Initialize CLI with full environment variable support

    Args:
        config_path: Path to YAML config file (optional)
        verbose: Enable verbose output
        use_env_vars: Force use of environment variables (None = auto-detect)
    """
    global config_manager, cli_instance

    # ✅ USE ENHANCED CONFIG MANAGER with ENV support
    config_manager = EnhancedConfigManager(config_path, use_env_vars)
    if verbose:
        config_manager.config["cli"]["verbose"] = True

    cli_instance = AmbivoAgentsCLI(config_manager)
    return cli_instance


# ============================================================================
# MAIN CLI GROUP
# ============================================================================


@click.group(invoke_without_command=True)
@click.version_option(version="1.1.0", prog_name="Ambivo Agents")
@click.option("--config", "-c", help="Configuration file path")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.option("--env-vars", is_flag=True, help="Force use of environment variables")
@click.pass_context
def cli(ctx, config: Optional[str], verbose: bool, env_vars: bool):
    """
    Ambivo Agents - Multi-Agent AI System CLI with Full Environment Variable Support

    🌟 Enhanced Features:
    - 🌍 Full environment variable support (AMBIVO_AGENTS_ prefix)
    - 📄 YAML configuration with ENV override
    - 🔄 Agent caching preserves session history
    - 📚 Conversation memory across commands
    - 🔌 MCP (Model Context Protocol) Integration
    - 🎯 Auto-session creation with UUID4
    - ⚙️  Graceful config fallbacks

    Configuration Priority:
    1. Environment Variables (AMBIVO_AGENTS_*)
    2. YAML Configuration File
    3. Interactive Creation Prompt
    4. Minimal Defaults

    Environment Variable Examples:
    export AMBIVO_AGENTS_REDIS_HOST=localhost
    export AMBIVO_AGENTS_OPENAI_API_KEY=your_key
    export AMBIVO_AGENTS_ENABLE_WEB_SEARCH=true
    export AMBIVO_AGENTS_ENABLE_API_AGENT=true
    export AMBIVO_AGENTS_MCP_ENABLED=true

    Author: Hemant Gosain 'Sunny'
    Company: Ambivo
    Email: sgosain@ambivo.com
    """
    global cli_instance

    # ✅ ENHANCED: Initialize CLI with full ENV support
    cli_instance = initialize_cli(config, verbose, env_vars if env_vars else None)

    if verbose:
        click.echo("🤖 Ambivo Agents CLI v1.1.0 - Enhanced with Full Environment Variable Support")
        click.echo("📧 Contact: info@ambivo.com")
        click.echo("🏢 Company: https://www.ambivo.com")
        click.echo("🌟 Agent caching, session management, ENV variables, and MCP integration")
        click.echo(f"⚙️  Configuration source: {cli_instance.config.config_source}")

    # If no command was provided, start shell mode by default
    if ctx.invoked_subcommand is None:
        default_mode = cli_instance.config.get("cli.default_mode", "shell")
        if default_mode == "shell":
            ctx.invoke(shell)
        else:
            click.echo(ctx.get_help())


# ============================================================================
# CHAT COMMANDS (Enhanced with session persistence)
# ============================================================================


@cli.command()
@click.argument("message")
@click.option("--conversation", "-conv", help="Conversation ID (overrides active session)")
@click.option(
    "--format", "-f", type=click.Choice(["text", "json"]), default="text", help="Output format"
)
def chat(message: str, conversation: Optional[str], format: str):
    """Send a message using smart agent routing with session history preservation"""

    # Determine conversation ID
    if conversation:
        conv_id = conversation
        session_source = f"explicit: {conversation}"
    else:
        active_session = cli_instance.get_current_session()
        if active_session:
            conv_id = active_session
            session_source = f"active session: {active_session}"
        else:
            conv_id = "cli"
            session_source = "default: cli"

    verbose = cli_instance.config.get("cli.verbose", False)
    if verbose:
        click.echo(f"💬 Processing: {message}")
        click.echo(f"📋 Session: {session_source}")
        click.echo(f"⚙️  Config: {cli_instance.config.config_source}")

    async def process():
        start_time = time.time()

        # ✅ This uses cached agents, preserving conversation history
        response = await cli_instance.smart_message_routing(message)
        processing_time = time.time() - start_time

        if format == "json":
            result = {
                "success": True,
                "response": response,
                "processing_time": processing_time,
                "message": message,
                "conversation_id": conv_id,
                "session_source": session_source,
                "config_source": cli_instance.config.config_source,
                "paradigm": "cached_agent_reuse_with_history",
                "moderator_available": MODERATOR_AVAILABLE,
                "loader_available": LOADER_AVAILABLE,
            }
            click.echo(json.dumps(result, indent=2))
        else:
            click.echo(f"\n🤖 Response:\n{response}")
            if verbose:
                click.echo(f"\n⏱️  Processing time: {processing_time:.2f}s")
                click.echo(f"📋 Conversation: {conv_id}")
                click.echo(f"🔄 Using cached agents with preserved history")

                click.echo(f"🎯 ModeratorAgent: {'✅' if MODERATOR_AVAILABLE else '❌'}")
                click.echo(f"⚙️  Config Source: {cli_instance.config.config_source}")

                # Show cached agent info if available
                agents_info = cli_instance.get_cached_agents_info()
                if agents_info["total_agents"] > 0:
                    click.echo(f"🤖 Cached Agents: {agents_info['total_agents']}")
                    memory_count = sum(1 for a in agents_info["agents"] if a["memory_available"])
                    click.echo(f"📚 Agents with Memory: {memory_count}")

    asyncio.run(process())


@cli.command()
def interactive():
    """Interactive chat mode with full session history preservation"""

    click.echo("🤖 Starting interactive chat mode...")

    # Check for active session
    active_session = cli_instance.get_current_session()

    if active_session:
        session_display = active_session[:8] + "..." if len(active_session) > 8 else active_session
        click.echo(f"📋 Using active session: {session_display}")
        click.echo(f"📚 Conversation history will be preserved")
    else:
        click.echo("📋 No active session - using default conversation")

    click.echo(f"⚙️  Configuration: {cli_instance.config.config_source}")
    click.echo("Type 'quit', 'exit', or 'bye' to exit")
    click.echo("-" * 60)

    async def interactive_loop():
        # Use active session or generate a unique one for this interactive session
        if active_session:
            conversation_id = active_session
        else:
            conversation_id = f"interactive_{int(time.time())}"

        while True:
            try:
                user_input = click.prompt("\n🗣️  You", type=str)

                if user_input.lower() in ["quit", "exit", "bye"]:
                    click.echo("👋 Goodbye!")
                    break

                # ✅ Process with smart routing using conversation_id (preserves history)
                response = await cli_instance.smart_message_routing(user_input)

                click.echo(f"🤖 Agent: {response}")
                session_display = (
                    conversation_id[:8] + "..." if len(conversation_id) > 8 else conversation_id
                )
                click.echo(f"📋 Session: {session_display}")

            except KeyboardInterrupt:
                click.echo("\n👋 Goodbye!")
                break
            except EOFError:
                click.echo("\n👋 Goodbye!")
                break

    asyncio.run(interactive_loop())


@cli.command()
def shell():
    """Start Ambivo Agents interactive shell with full environment variable support"""

    # Show enhanced welcome message
    click.echo("🚀 Ambivo Agents Shell v1.1.0 (Full Environment Variable Support)")
    click.echo("💡 YAML config + ENV variables + agent caching + session history + MCP integration")

    click.echo(f"⚙️  Configuration source: {cli_instance.config.config_source}")

    if LOADER_AVAILABLE:
        click.echo("✅ Using enhanced configuration loader (ENV support)")
    else:
        click.echo("⚠️  Using fallback configuration (limited ENV support)")

    # Show current session
    current_session = cli_instance.get_current_session()
    if current_session:
        session_display = (
            current_session[:8] + "..." if len(current_session) > 8 else current_session
        )
        click.echo(f"🔗 Session: {session_display}")

    # Show cached agents
    if hasattr(cli_instance, "_session_agents"):
        agents_info = cli_instance.get_cached_agents_info()
        if agents_info["total_agents"] > 0:
            click.echo(f"🤖 Cached agents: {agents_info['total_agents']} (with preserved memory)")

    # Show feature availability
    features = []

    if MODERATOR_AVAILABLE:
        features.append("🎯 ModeratorAgent")
    if LOADER_AVAILABLE:
        features.append("🌍 ENV Variables")

    if features:
        click.echo(f"🌟 Available: {' | '.join(features)}")

    click.echo("💡 Type 'help' for commands, 'exit' to quit")
    click.echo("-" * 60)

    def get_prompt():
        """Generate dynamic prompt based on session state and theme"""
        current_session = cli_instance.get_current_session()
        theme = cli_instance.config.get("cli.theme", "default")

        if current_session:
            # Show shortened session ID in prompt
            session_short = current_session[:8] if len(current_session) > 8 else current_session
            if theme == "minimal":
                return f"({session_short})> "
            else:
                return f"ambivo-agents ({session_short})> "
        else:
            if theme == "minimal":
                return "> "
            else:
                return "ambivo-agents> "

    def process_shell_command(command_line: str):
        """Process a command line in shell mode"""
        if not command_line.strip():
            return True

        # Clean up command line - remove leading colons and extra whitespace
        cleaned_command = command_line.strip()
        if cleaned_command.startswith(":"):
            cleaned_command = cleaned_command[1:].strip()

        # Parse command line
        parts = cleaned_command.split()
        if not parts:
            return True

        cmd = parts[0].lower()
        args = parts[1:] if len(parts) > 1 else []

        # Handle shell-specific commands
        if cmd in ["exit", "quit", "bye"]:
            click.echo("👋 Goodbye!")
            return False

        elif cmd == "help":
            click.echo(
                """
🌟 Ambivo Agents Enhanced Shell Commands:

📋 **Configuration (Environment Variable Support):**
   config show                - Show current configuration with source
   config get <key>           - Get configuration value
   config set <key> <value>   - Set configuration value (runtime)
   config save-sample <path>  - Save sample config with ENV documentation
   config env-template        - Show environment variable template

📋 **Session Management (with History Preservation):**
   session create [name]      - Create session (UUID4 if no name)
   session current            - Show current session + cached agents
   session use <name>         - Switch to session (preserves per-session memory)
   session end                - End current session (cleanup agents)
   session history            - Show conversation history
   session summary            - Show session summary
   session clear              - Clear conversation history
   session agents             - Show cached agents with memory status

💬 **Chat Commands (with Session History):**
   chat <message>             - Send message (uses cached agents)
   <message>                  - Direct message (shortcut)

🎬 **Specialized Agent Commands:**
   youtube download <url>     - Download video/audio (cached agent)
   youtube info <url>         - Get video information
   search <query>             - Web search (cached agent)
   scrape <url>              - Web scraping (cached agent)

🤖 **Agent Management:**
   agents                     - Show all cached agents
   debug agents               - Debug agent memory and cache status
   status                     - Show system status

🔄 **Modes:**
   interactive               - Start chat-only interactive mode
   shell                     - This shell mode (default)

🛠️ **Utilities:**
   health                    - System health check
   env-check                 - Check environment variables
   demo                      - Run feature demonstration

🚪 **Exit:**
   exit, quit, bye           - Exit shell

💡 **Enhanced Features:**
   🌍 Full environment variable support (AMBIVO_AGENTS_ prefix)
   📚 Conversation history preserved across commands
   🔄 Agent caching and reuse within sessions
   📄 YAML configuration with ENV variable override
   🎯 ModeratorAgent support for advanced routing
   ⚙️  Graceful configuration fallbacks

🌍 **Environment Variable Examples:**
   export AMBIVO_AGENTS_REDIS_HOST=localhost
   export AMBIVO_AGENTS_OPENAI_API_KEY=your_key
   export AMBIVO_AGENTS_ENABLE_WEB_SEARCH=true
   export AMBIVO_AGENTS_MCP_ENABLED=true
            """
            )
            return True

        elif cmd == "clear":
            click.clear()
            return True

        elif cmd == "chat":
            return handle_chat_command(args)
        elif cmd == "interactive":
            return handle_interactive_command()
        elif cmd == "health":
            return handle_health_command()
        elif cmd == "agents":
            return handle_agents_command()
        elif cmd == "status":
            return handle_status_command()
        elif cmd == "env-check":
            return handle_env_check_command()
        elif cmd == "demo":
            return handle_demo_command()
        else:
            # Try to interpret as chat message
            return handle_chat_command([command_line])

    def handle_chat_command(args):
        """Handle chat command with session awareness"""
        if not args:
            click.echo("❌ Usage: chat <message>")
            return True

        message = " ".join(args)

        async def process_chat():
            active_session = cli_instance.get_current_session()
            verbose = cli_instance.config.get("cli.verbose", False)

            if verbose:
                click.echo(f"💬 Processing: {message}")
                if active_session:
                    click.echo(f"📋 Session: {active_session[:8]}...")

            try:
                # ✅ Uses cached agents with preserved conversation history
                response = await cli_instance.smart_message_routing(message)
                click.echo(f"\n🤖 Response:\n{response}")

                if verbose:
                    agents_info = cli_instance.get_cached_agents_info()
                    click.echo(f"\n🔄 Cached agents: {agents_info['total_agents']}")

            except Exception as e:
                click.echo(f"❌ Error: {e}")

        asyncio.run(process_chat())
        return True

    def handle_interactive_command():
        """Handle interactive mode transition"""
        click.echo("🔄 Switching to interactive chat mode...")
        click.echo("💡 Type 'quit' to return to shell")
        click.echo("📚 Conversation history will be preserved")

        # Start interactive chat mode with session awareness
        async def interactive_chat():
            current_session = cli_instance.get_current_session()

            while True:
                try:
                    if current_session:
                        session_short = (
                            current_session[:8] if len(current_session) > 8 else current_session
                        )
                        prompt_text = f"🗣️  You ({session_short})"
                    else:
                        prompt_text = "🗣️  You"

                    user_input = click.prompt(f"\n{prompt_text}", type=str)

                    if user_input.lower() in ["quit", "exit", "bye"]:
                        click.echo("🔄 Returning to shell...")
                        break

                    # Process with cached agents (preserves history)
                    response = await cli_instance.smart_message_routing(user_input)
                    click.echo(f"🤖 Agent: {response}")

                except KeyboardInterrupt:
                    click.echo("\n🔄 Returning to shell...")
                    break
                except EOFError:
                    click.echo("\n🔄 Returning to shell...")
                    break

        asyncio.run(interactive_chat())
        return True

    def handle_health_command():
        """Enhanced health check"""
        click.echo("🏥 System Health Check:")
        click.echo("✅ CLI is working")
        click.echo(f"✅ Configuration: {cli_instance.config.config_source}")
        click.echo(f"✅ Loader: {'Enhanced' if LOADER_AVAILABLE else 'Fallback'}")

        click.echo(f"🎯 ModeratorAgent: {'Available' if MODERATOR_AVAILABLE else 'Not Available'}")

        # Session and agent status
        current_session = cli_instance.get_current_session()
        agents_info = cli_instance.get_cached_agents_info()

        click.echo(f"📋 Session: {'Active' if current_session else 'None'}")
        click.echo(f"🤖 Cached agents: {agents_info['total_agents']}")

        if agents_info["agents"]:
            memory_count = sum(1 for a in agents_info["agents"] if a["memory_available"])
            click.echo(f"📚 Agents with memory: {memory_count}")

        return True

    def handle_agents_command():
        """Show detailed agent information"""
        agents_info = cli_instance.get_cached_agents_info()
        current_session = cli_instance.get_current_session()

        session_display = (
            current_session[:8] + "..."
            if current_session and len(current_session) > 8
            else current_session or "None"
        )
        click.echo(f"🤖 Cached Agents (Session: {session_display})")
        click.echo(f"📊 Total: {agents_info['total_agents']}")
        click.echo("-" * 40)

        if agents_info["agents"]:
            for agent_info in agents_info["agents"]:
                memory_icon = "📚" if agent_info["memory_available"] else "📭"
                click.echo(f"{memory_icon} {agent_info['agent_type']}")
                click.echo(f"   ID: {agent_info['agent_id']}")
                click.echo(f"   Created: {agent_info['created_at']}")
                if "config_source" in agent_info:
                    click.echo(f"   Config: {agent_info['config_source']}")
        else:
            click.echo("📭 No cached agents")
            click.echo("💡 Agents will be created when you send messages")

        return True

    def handle_status_command():
        """Show system status in shell"""
        click.echo("📊 System Status:")
        click.echo(f"   Configuration: {cli_instance.config.config_source}")
        click.echo(
            f"   Session: {cli_instance.get_current_session()[:8] + '...' if cli_instance.get_current_session() else 'None'}"
        )

        agents_info = cli_instance.get_cached_agents_info()
        click.echo(f"   Cached Agents: {agents_info['total_agents']}")

        click.echo(f"   Loader: {'✅' if LOADER_AVAILABLE else '❌'}")

        return True

    def handle_env_check_command():
        """Check environment variable configuration"""
        click.echo("🌍 Environment Variable Configuration Check")
        click.echo("=" * 50)

        # Check for key environment variables
        key_env_vars = [
            "AMBIVO_AGENTS_REDIS_HOST",
            "AMBIVO_AGENTS_REDIS_PORT",
            "AMBIVO_AGENTS_OPENAI_API_KEY",
            "AMBIVO_AGENTS_ANTHROPIC_API_KEY",
            "AMBIVO_AGENTS_ENABLE_WEB_SEARCH",
            "AMBIVO_AGENTS_MCP_ENABLED",
        ]

        found_vars = []
        missing_vars = []

        for var in key_env_vars:
            value = os.getenv(var)
            if value:
                # Mask sensitive values
                if "key" in var.lower() or "token" in var.lower():
                    display_value = value[:8] + "..." if len(value) > 8 else "***"
                else:
                    display_value = value

                found_vars.append((var, display_value))
            else:
                missing_vars.append(var)

        if found_vars:
            click.echo("✅ Found environment variables:")
            for var, value in found_vars:
                click.echo(f"   {var} = {value}")

        if missing_vars:
            click.echo(f"\n❌ Missing environment variables:")
            for var in missing_vars:
                click.echo(f"   {var}")

        click.echo(f"\n📊 Summary:")
        click.echo(f"   Found: {len(found_vars)}")
        click.echo(f"   Missing: {len(missing_vars)}")
        click.echo(f"   Configuration source: {cli_instance.config.config_source}")

        if LOADER_AVAILABLE:
            click.echo("✅ Enhanced loader available - full ENV support")
        else:
            click.echo("⚠️  Fallback loader - limited ENV support")

        return True

    def handle_demo_command():
        """Run a demonstration of the enhanced CLI features"""
        click.echo("🎪 Ambivo Agents Enhanced CLI Demo")
        click.echo("=" * 50)

        # Show configuration
        click.echo("1. 📋 Configuration System:")
        click.echo(f"   Source: {cli_instance.config.config_source}")
        click.echo(f"   Loader: {'Enhanced' if LOADER_AVAILABLE else 'Fallback'}")

        # Show session management
        current_session = cli_instance.get_current_session()
        click.echo(f"\n2. 📋 Session Management:")
        click.echo(
            f"   Current session: {current_session[:8] + '...' if current_session else 'None'}"
        )

        # Show agent caching
        agents_info = cli_instance.get_cached_agents_info()
        click.echo(f"\n3. 🤖 Agent Caching:")
        click.echo(f"   Cached agents: {agents_info['total_agents']}")
        click.echo(f"   Memory preservation: ✅")

        # Show features
        click.echo(f"\n4. 🌟 Available Features:")
        features = [
            ("Environment Variables", LOADER_AVAILABLE),
            ("ModeratorAgent", MODERATOR_AVAILABLE),
            ("Session History", True),
            ("Agent Caching", True),
        ]

        for feature, available in features:
            status = "✅" if available else "❌"
            click.echo(f"   {status} {feature}")

        click.echo(f"\n5. 💡 Quick Demo Commands:")
        demo_commands = ["chat 'Hello, how are you?'", "agents", "status", "env-check"]

        for cmd in demo_commands:
            click.echo(f"   • {cmd}")

        click.echo(f"\n🎯 The CLI preserves conversation history across commands!")
        click.echo(f"🔄 Agents are cached and reused within sessions for efficiency!")
        click.echo(f"🌍 Environment variables override YAML configuration!")

        return True

    # Main shell loop
    try:
        while True:
            try:
                prompt = get_prompt()

                try:
                    command_line = input(prompt)
                except (KeyboardInterrupt, EOFError):
                    click.echo("\n👋 Goodbye!")
                    break
                except Exception as e:
                    click.echo(f"\n⚠️  Input error: {e}")
                    continue

                # Process command
                if not process_shell_command(command_line):
                    break

            except KeyboardInterrupt:
                click.echo("\n💡 Use 'exit' to quit")
                continue
            except EOFError:
                click.echo("\n👋 Goodbye!")
                break

    except Exception as e:
        click.echo(f"❌ Shell error: {e}")
        if cli_instance.config.get("cli.verbose", False):
            import traceback

            traceback.print_exc()


@cli.command()
@click.argument("request")
@click.option("--token", "-t", help="Authentication token for API calls")
@click.option("--timeout", type=int, default=30, help="Request timeout in seconds")
@click.option("--stream", "-s", is_flag=True, help="Stream the response")
def api(request: str, token: str, timeout: int, stream: bool):
    """
    Make API requests with intelligent documentation parsing
    
    Examples:
    - ambivo-agents api "GET https://jsonplaceholder.typicode.com/posts/1"
    - ambivo-agents api "Read docs at https://api.example.com/docs and get users" --token abc123
    - ambivo-agents api "POST https://api.example.com/users" --stream
    """
    import asyncio
    
    async def run_api_request():
        try:
            if not cli_instance:
                initialize_cli()
            
            # Get or create API agent
            session_id = cli_instance.get_current_session()
            agent, context = await cli_instance.get_or_create_agent(
                APIAgent, session_id, {"operation": "cli_api_request"}
            )
            
            # Add token to request if provided
            if token:
                request_with_token = f"{request} with token {token}"
            else:
                request_with_token = request
            
            # Add timeout if different from default
            if timeout != 30:
                request_with_token += f" with timeout {timeout} seconds"
            
            if stream:
                # Streaming response
                click.echo("🌐 API Agent - Streaming Response:")
                click.echo("=" * 50)
                
                async for chunk in agent.chat_stream(request_with_token):
                    chunk_type = chunk.sub_type.value if hasattr(chunk, 'sub_type') else 'content'
                    chunk_text = chunk.text if hasattr(chunk, 'text') else str(chunk)
                    
                    if chunk_type == 'status':
                        click.echo(f"🔄 {chunk_text}")
                    elif chunk_type == 'error':
                        click.echo(f"❌ {chunk_text}")
                    else:
                        click.echo(chunk_text)
                        
            else:
                # Non-streaming response
                click.echo("🌐 API Agent Response:")
                click.echo("=" * 30)
                
                response = await agent.chat(request_with_token)
                click.echo(response)
            
            click.echo(f"\n📋 Session: {context.session_id}")
            
        except Exception as e:
            click.echo(f"❌ API request failed: {str(e)}")
            if cli_instance.config.get("cli.verbose", False):
                import traceback
                traceback.print_exc()
    
    asyncio.run(run_api_request())


@cli.command()
def status():
    """Show comprehensive agent service status"""
    current_session = cli_instance.get_current_session()
    agents_info = cli_instance.get_cached_agents_info()

    click.echo("📊 Ambivo Agents Status")
    click.echo("=" * 50)
    click.echo(
        f"🔗 Current Session: {current_session[:8] + '...' if current_session and len(current_session) > 8 else current_session or 'None'}"
    )
    click.echo(f"🤖 Cached Agents: {agents_info['total_agents']}")
    click.echo(f"⚙️  Configuration: {cli_instance.config.config_source}")

    click.echo(f"🎯 ModeratorAgent Available: {'✅' if MODERATOR_AVAILABLE else '❌'}")
    click.echo(f"📋 Loader Available: {'✅' if LOADER_AVAILABLE else '❌'}")

    # Show key configuration values
    click.echo(f"\n⚙️  Key Configuration:")
    key_configs = [
        ("Auto Session", "cli.auto_session"),
        ("Web Search", "agent_capabilities.enable_web_search"),
        ("Knowledge Base", "agent_capabilities.enable_knowledge_base"),
        ("API Agent", "agent_capabilities.enable_api_agent"),
        ("MCP Enabled", "mcp.enabled"),
        ("YouTube Downloads", "agent_capabilities.enable_youtube_download"),
    ]

    for label, key in key_configs:
        value = cli_instance.config.get(key)
        status_icon = "✅" if value else "❌"
        click.echo(f"   {status_icon} {label}: {value}")


@cli.command()
def env_check():
    """Check environment variable configuration"""
    click.echo("🌍 Environment Variable Configuration Check")
    click.echo("=" * 50)

    # Check for key environment variables
    key_env_vars = [
        "AMBIVO_AGENTS_REDIS_HOST",
        "AMBIVO_AGENTS_REDIS_PORT",
        "AMBIVO_AGENTS_OPENAI_API_KEY",
        "AMBIVO_AGENTS_ANTHROPIC_API_KEY",
        "AMBIVO_AGENTS_ENABLE_WEB_SEARCH",
        "AMBIVO_AGENTS_MCP_ENABLED",
    ]

    found_vars = []
    missing_vars = []

    for var in key_env_vars:
        value = os.getenv(var)
        if value:
            # Mask sensitive values
            if "key" in var.lower() or "token" in var.lower():
                display_value = value[:8] + "..." if len(value) > 8 else "***"
            else:
                display_value = value

            found_vars.append((var, display_value))
        else:
            missing_vars.append(var)

    if found_vars:
        click.echo("✅ Found environment variables:")
        for var, value in found_vars:
            click.echo(f"   {var} = {value}")

    if missing_vars:
        click.echo(f"\n❌ Missing environment variables:")
        for var in missing_vars:
            click.echo(f"   {var}")

    click.echo(f"\n📊 Summary:")
    click.echo(f"   Found: {len(found_vars)}")
    click.echo(f"   Missing: {len(missing_vars)}")
    click.echo(f"   Configuration source: {cli_instance.config.config_source}")

    if LOADER_AVAILABLE:
        click.echo("✅ Enhanced loader available - full ENV support")
    else:
        click.echo("⚠️  Fallback loader - limited ENV support")


@cli.command()
def demo():
    """Run a demonstration of the enhanced CLI features"""
    click.echo("🎪 Ambivo Agents Enhanced CLI Demo")
    click.echo("=" * 50)

    # Show configuration
    click.echo("1. 📋 Configuration System:")
    click.echo(f"   Source: {cli_instance.config.config_source}")
    click.echo(f"   Loader: {'Enhanced' if LOADER_AVAILABLE else 'Fallback'}")

    # Show session management
    current_session = cli_instance.get_current_session()
    click.echo(f"\n2. 📋 Session Management:")
    click.echo(f"   Current session: {current_session[:8] + '...' if current_session else 'None'}")

    # Show agent caching
    agents_info = cli_instance.get_cached_agents_info()
    click.echo(f"\n3. 🤖 Agent Caching:")
    click.echo(f"   Cached agents: {agents_info['total_agents']}")
    click.echo(f"   Memory preservation: ✅")

    # Show features
    click.echo(f"\n4. 🌟 Available Features:")
    features = [
        ("Environment Variables", LOADER_AVAILABLE),
        ("ModeratorAgent", MODERATOR_AVAILABLE),
        ("Session History", True),
        ("Agent Caching", True),
    ]

    for feature, available in features:
        status = "✅" if available else "❌"
        click.echo(f"   {status} {feature}")

    click.echo(f"\n5. 💡 Quick Demo Commands:")
    demo_commands = ["chat 'Hello, how are you?'", "agents", "status", "env-check"]

    for cmd in demo_commands:
        click.echo(f"   • {cmd}")

    click.echo(f"\n🎯 The CLI preserves conversation history across commands!")
    click.echo(f"🔄 Agents are cached and reused within sessions for efficiency!")
    click.echo(f"🌍 Environment variables override YAML configuration!")


def main():
    """Main CLI entry point with enhanced error handling"""
    try:
        cli()
    except KeyboardInterrupt:
        click.echo("\n👋 CLI interrupted by user")
    except Exception as e:
        click.echo(f"❌ CLI error: {e}")
        if os.getenv("AMBIVO_AGENTS_CLI_VERBOSE") == "true":
            import traceback

            traceback.print_exc()
        sys.exit(1)


def cli_main():
    """Entry point function for console script"""
    main()


if __name__ == "__main__":
    main()
