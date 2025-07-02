# ambivo_agents/mcp/server.py
"""
Model Context Protocol (MCP) Server implementation for Ambivo Agents
Exposes agent capabilities as MCP tools and resources
"""

import asyncio
import json
import logging
from typing import Dict, List, Any, Optional, Sequence
from dataclasses import dataclass

try:
    import mcp
    from mcp.server import NotificationOptions, Server
    from mcp.server.models import InitializationOptions
    from mcp import ClientSession, StdioServerParameters
    from mcp.server.stdio import stdio_server
    from mcp.types import (
        CallToolRequest, CallToolResult, GetPromptRequest, GetPromptResult,
        ListPromptsRequest, ListPromptsResult, ListResourcesRequest,
        ListResourcesResult, ListToolsRequest, ListToolsResult,
        ReadResourceRequest, ReadResourceResult, Tool, TextContent,
        ImageContent, EmbeddedResource, Prompt, PromptArgument, Resource
    )

    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False

from ..services.agent_service import AgentService, create_agent_service
from ..config.loader import load_config, get_enabled_capabilities


@dataclass
class MCPAgentContext:
    """Context for MCP agent operations"""
    user_id: str = "mcp_user"
    session_id: str = "mcp_session"
    tenant_id: str = "default"


class MCPAgentServer:
    """MCP Server that exposes Ambivo Agents as MCP tools and resources"""

    def __init__(self):
        if not MCP_AVAILABLE:
            raise ImportError("MCP package not available. Install with: pip install mcp")

        self.config = load_config()
        self.capabilities = get_enabled_capabilities(self.config)
        self.agent_service = create_agent_service()
        self.context = MCPAgentContext()
        self.server = Server("ambivo-agents")
        self.logger = logging.getLogger("MCPAgentServer")

        # Register MCP handlers
        self._register_handlers()

    def _register_handlers(self):
        """Register MCP protocol handlers"""

        @self.server.list_tools()
        async def handle_list_tools() -> List[Tool]:
            """List available agent tools"""
            tools = []

            # Code execution tool
            if self.capabilities.get('code_execution', False):
                tools.append(Tool(
                    name="execute_code",
                    description="Execute Python or Bash code in a secure Docker container",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "code": {
                                "type": "string",
                                "description": "Code to execute"
                            },
                            "language": {
                                "type": "string",
                                "enum": ["python", "bash"],
                                "default": "python",
                                "description": "Programming language"
                            }
                        },
                        "required": ["code"]
                    }
                ))

            # Web search tool
            if self.capabilities.get('web_search', False):
                tools.append(Tool(
                    name="search_web",
                    description="Search the web for information",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Search query"
                            },
                            "max_results": {
                                "type": "integer",
                                "default": 5,
                                "description": "Maximum number of results"
                            }
                        },
                        "required": ["query"]
                    }
                ))

            # Knowledge base tools
            if self.capabilities.get('knowledge_base', False):
                tools.extend([
                    Tool(
                        name="query_knowledge_base",
                        description="Query a knowledge base for information",
                        inputSchema={
                            "type": "object",
                            "properties": {
                                "query": {
                                    "type": "string",
                                    "description": "Question to ask the knowledge base"
                                },
                                "kb_name": {
                                    "type": "string",
                                    "description": "Knowledge base name"
                                }
                            },
                            "required": ["query", "kb_name"]
                        }
                    ),
                    Tool(
                        name="ingest_document",
                        description="Add a document to the knowledge base",
                        inputSchema={
                            "type": "object",
                            "properties": {
                                "file_path": {
                                    "type": "string",
                                    "description": "Path to document file"
                                },
                                "kb_name": {
                                    "type": "string",
                                    "description": "Knowledge base name"
                                }
                            },
                            "required": ["file_path", "kb_name"]
                        }
                    )
                ])

            # YouTube download tool
            if self.capabilities.get('youtube_download', False):
                tools.append(Tool(
                    name="download_youtube",
                    description="Download video or audio from YouTube",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "url": {
                                "type": "string",
                                "description": "YouTube URL"
                            },
                            "audio_only": {
                                "type": "boolean",
                                "default": True,
                                "description": "Download only audio if true"
                            }
                        },
                        "required": ["url"]
                    }
                ))

            # Media processing tools
            if self.capabilities.get('media_editor', False):
                tools.extend([
                    Tool(
                        name="extract_audio",
                        description="Extract audio from video file",
                        inputSchema={
                            "type": "object",
                            "properties": {
                                "video_path": {
                                    "type": "string",
                                    "description": "Path to video file"
                                },
                                "output_format": {
                                    "type": "string",
                                    "enum": ["mp3", "wav", "aac"],
                                    "default": "mp3"
                                }
                            },
                            "required": ["video_path"]
                        }
                    ),
                    Tool(
                        name="convert_video",
                        description="Convert video format",
                        inputSchema={
                            "type": "object",
                            "properties": {
                                "video_path": {
                                    "type": "string",
                                    "description": "Path to video file"
                                },
                                "output_format": {
                                    "type": "string",
                                    "enum": ["mp4", "avi", "mov"],
                                    "default": "mp4"
                                }
                            },
                            "required": ["video_path"]
                        }
                    )
                ])

            # Web scraping tool
            if self.capabilities.get('web_scraping', False):
                tools.append(Tool(
                    name="scrape_website",
                    description="Scrape content from a website",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "url": {
                                "type": "string",
                                "description": "URL to scrape"
                            },
                            "extract_links": {
                                "type": "boolean",
                                "default": True,
                                "description": "Extract links from page"
                            }
                        },
                        "required": ["url"]
                    }
                ))

            return tools

        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> List[
            TextContent | ImageContent | EmbeddedResource]:
            """Handle tool execution"""
            try:
                # Route to appropriate agent based on tool name
                if name == "execute_code":
                    message = f"Execute {arguments.get('language', 'python')} code: {arguments['code']}"
                elif name == "search_web":
                    message = f"Search web: {arguments['query']}"
                elif name == "query_knowledge_base":
                    message = f"Query {arguments['kb_name']}: {arguments['query']}"
                elif name == "ingest_document":
                    message = f"Ingest {arguments['file_path']} into {arguments['kb_name']}"
                elif name == "download_youtube":
                    audio_type = "audio" if arguments.get('audio_only', True) else "video"
                    message = f"Download {audio_type} from {arguments['url']}"
                elif name == "extract_audio":
                    message = f"Extract audio from {arguments['video_path']} as {arguments.get('output_format', 'mp3')}"
                elif name == "convert_video":
                    message = f"Convert {arguments['video_path']} to {arguments.get('output_format', 'mp4')}"
                elif name == "scrape_website":
                    message = f"Scrape website {arguments['url']}"
                else:
                    return [TextContent(type="text", text=f"Unknown tool: {name}")]

                # Process through agent service
                result = await self.agent_service.process_message(
                    message=message,
                    session_id=self.context.session_id,
                    user_id=self.context.user_id,
                    tenant_id=self.context.tenant_id,
                    metadata={"mcp_tool": name, "mcp_arguments": arguments}
                )

                if result['success']:
                    return [TextContent(type="text", text=result['response'])]
                else:
                    return [TextContent(type="text", text=f"Tool execution failed: {result['error']}")]

            except Exception as e:
                self.logger.error(f"Tool execution error: {e}")
                return [TextContent(type="text", text=f"Internal error: {str(e)}")]

        @self.server.list_resources()
        async def handle_list_resources() -> List[Resource]:
            """List available resources"""
            resources = []

            # Agent capabilities resource
            resources.append(Resource(
                uri="ambivo://capabilities",
                name="Agent Capabilities",
                description="Current agent capabilities and configuration",
                mimeType="application/json"
            ))

            # Service statistics resource
            resources.append(Resource(
                uri="ambivo://service/stats",
                name="Service Statistics",
                description="Current service statistics and health",
                mimeType="application/json"
            ))

            # Session information
            resources.append(Resource(
                uri=f"ambivo://session/{self.context.session_id}",
                name="Current Session",
                description="Information about the current MCP session",
                mimeType="application/json"
            ))

            return resources

        @self.server.read_resource()
        async def handle_read_resource(uri: str) -> str:
            """Read resource content"""
            try:
                if uri == "ambivo://capabilities":
                    return json.dumps({
                        "enabled_capabilities": self.capabilities,
                        "available_agents": list(self.agent_service.sessions.keys()) if hasattr(self.agent_service,
                                                                                                'sessions') else [],
                        "mcp_version": "1.0",
                        "server_info": {
                            "name": "ambivo-agents",
                            "version": "1.0.0",
                            "description": "Ambivo Agents MCP Server"
                        }
                    }, indent=2)

                elif uri == "ambivo://service/stats":
                    stats = self.agent_service.get_service_stats()
                    return json.dumps(stats, indent=2)

                elif uri.startswith("ambivo://session/"):
                    session_id = uri.split("/")[-1]
                    session_info = self.agent_service.get_session_info(session_id)
                    if session_info:
                        return json.dumps(session_info, indent=2)
                    else:
                        return json.dumps({"error": "Session not found"}, indent=2)

                else:
                    return json.dumps({"error": f"Unknown resource: {uri}"}, indent=2)

            except Exception as e:
                return json.dumps({"error": str(e)}, indent=2)

        @self.server.list_prompts()
        async def handle_list_prompts() -> List[Prompt]:
            """List available prompts"""
            prompts = []

            # Agent-specific prompts
            if self.capabilities.get('code_execution', False):
                prompts.append(Prompt(
                    name="code_execution_prompt",
                    description="Generate and execute code to solve problems",
                    arguments=[
                        PromptArgument(
                            name="task",
                            description="Task description",
                            required=True
                        ),
                        PromptArgument(
                            name="language",
                            description="Programming language",
                            required=False
                        )
                    ]
                ))

            if self.capabilities.get('knowledge_base', False):
                prompts.append(Prompt(
                    name="knowledge_query_prompt",
                    description="Query knowledge base with context",
                    arguments=[
                        PromptArgument(
                            name="question",
                            description="Question to ask",
                            required=True
                        ),
                        PromptArgument(
                            name="kb_name",
                            description="Knowledge base name",
                            required=True
                        )
                    ]
                ))

            return prompts

        @self.server.get_prompt()
        async def handle_get_prompt(name: str, arguments: Dict[str, str]) -> GetPromptResult:
            """Get prompt content"""
            if name == "code_execution_prompt":
                task = arguments.get("task", "")
                language = arguments.get("language", "python")

                prompt_text = f"""You are a code execution assistant. Your task is to write and execute {language} code to accomplish the following:

Task: {task}

Please:
1. Write clean, well-commented code
2. Include error handling where appropriate
3. Execute the code and verify the results
4. Explain the solution

Language: {language}
"""
                return GetPromptResult(
                    description=f"Code execution prompt for: {task}",
                    messages=[TextContent(type="text", text=prompt_text)]
                )

            elif name == "knowledge_query_prompt":
                question = arguments.get("question", "")
                kb_name = arguments.get("kb_name", "")

                prompt_text = f"""You are querying the knowledge base '{kb_name}' with the following question:

Question: {question}

Please provide a comprehensive answer based on the knowledge base content, including:
1. Direct answer to the question
2. Supporting evidence from the knowledge base
3. Source attribution where possible
4. Additional relevant context

Knowledge Base: {kb_name}
"""
                return GetPromptResult(
                    description=f"Knowledge base query for: {question}",
                    messages=[TextContent(type="text", text=prompt_text)]
                )

            else:
                raise ValueError(f"Unknown prompt: {name}")

    async def run_stdio(self):
        """Run the MCP server with stdio transport"""
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="ambivo-agents",
                    server_version="1.0.0",
                    capabilities=self.server.get_capabilities(
                        notification_options=NotificationOptions(),
                        experimental_capabilities={}
                    )
                )
            )


# CLI entry point
async def main():
    """Main entry point for MCP server"""
    logging.basicConfig(level=logging.INFO)
    server = MCPAgentServer()
    await server.run_stdio()


if __name__ == "__main__":
    asyncio.run(main())