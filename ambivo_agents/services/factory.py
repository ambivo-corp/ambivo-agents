# ambivo_agents/services/factory.py
"""
Agent Factory for creating different types of agents - UPDATED WITH YOUTUBE SUPPORT

Author: Hemant Gosain 'Sunny'
Company: Ambivo
Email: sgosain@ambivo.com
License: MIT
"""

import logging
from typing import Dict, Any, Optional

from ..core.base import AgentRole, BaseAgent, AgentMessage, MessageType
from ..core.memory import MemoryManagerInterface
from ..core.llm import LLMServiceInterface
from ..config.loader import (
    load_config,
    get_config_section,
    validate_agent_capabilities,
    get_available_agent_types,
    get_enabled_capabilities
)

from ..agents.assistant import AssistantAgent
from ..agents.code_executor import CodeExecutorAgent


class ProxyAgent(BaseAgent):
    """Agent that routes messages to appropriate specialized agents - UPDATED WITH YOUTUBE SUPPORT"""

    def __init__(self, agent_id: str, memory_manager, llm_service=None, **kwargs):
        super().__init__(
            agent_id=agent_id,
            role=AgentRole.PROXY,
            memory_manager=memory_manager,
            llm_service=llm_service,
            name="Proxy Agent",
            description="Agent that routes messages to appropriate specialized agents",
            **kwargs
        )
        self.agent_registry: Dict[str, BaseAgent] = {}

    def register_agent(self, agent: BaseAgent) -> bool:
        """Register an agent for routing"""
        if agent and hasattr(agent, 'agent_id'):
            self.agent_registry[agent.agent_id] = agent
            logging.info(f"Registered agent {agent.agent_id} ({agent.__class__.__name__}) with proxy")
            return True
        else:
            logging.error(f"Failed to register agent: invalid agent object")
            return False

    def get_registered_agents(self) -> Dict[str, BaseAgent]:
        """Get all registered agents"""
        return self.agent_registry.copy()

    def unregister_agent(self, agent_id: str) -> bool:
        """Unregister an agent"""
        if agent_id in self.agent_registry:
            del self.agent_registry[agent_id]
            logging.info(f"Unregistered agent {agent_id} from proxy")
            return True
        return False

    async def process_message(self, message, context=None):
        """Route messages to appropriate agents based on content analysis - UPDATED WITH YOUTUBE"""
        self.memory.store_message(message)

        try:
            content = message.content.lower()

            # Improved routing logic with YouTube support
            target_agent = None

            # YouTube download routing (HIGHEST PRIORITY for YouTube URLs)
            if any(keyword in content for keyword in [
                'youtube.com', 'youtu.be', 'download youtube', 'youtube download',
                'download video', 'download audio', 'youtube mp3', 'youtube mp4',
                'download from youtube'
            ]) or 'youtube' in content:
                # Look for YouTubeDownloadAgent by class name or agent key
                for agent_key, agent in self.agent_registry.items():
                    if ('YouTubeDownloadAgent' in agent.__class__.__name__ or
                            'youtube_download' in agent_key or
                            'youtube' in agent_key):
                        target_agent = agent
                        break

            # Web search routing (HIGH PRIORITY for web search requests)
            elif any(keyword in content for keyword in [
                'search web', 'web search', 'find online', 'search_web',
                'brave search', 'aves search', 'search the web', 'search for'
            ]):
                # Look for WebSearchAgent by class name or agent key
                for agent_key, agent in self.agent_registry.items():
                    if ('WebSearchAgent' in agent.__class__.__name__ or
                            'web_search' in agent_key or
                            'websearch' in agent_key):
                        target_agent = agent
                        break

            # Knowledge Base routing (for KB operations)
            elif any(keyword in content for keyword in [
                'ingest_document', 'ingest_text', 'ingest', 'knowledge base', 'kb',
                'query_knowledge_base', 'query', 'search documents', 'vector database',
                'qdrant', 'semantic search', 'document', 'pdf', 'docx'
            ]):
                # Look for KnowledgeBaseAgent
                for agent_key, agent in self.agent_registry.items():
                    if ('KnowledgeBaseAgent' in agent.__class__.__name__ or
                            'knowledge_base' in agent_key or
                            'knowledge' in agent_key):
                        target_agent = agent
                        break

            # Media processing routing (for FFmpeg operations)
            elif any(keyword in content for keyword in [
                'extract_audio', 'convert_video', 'media', 'ffmpeg', 'audio', 'video',
                'mp4', 'mp3', 'wav', 'extract audio', 'resize video', 'trim video',
                'video format', 'audio format'
            ]):
                # Look for MediaEditorAgent
                for agent_key, agent in self.agent_registry.items():
                    if ('MediaEditorAgent' in agent.__class__.__name__ or
                            'media_editor' in agent_key or
                            'mediaeditor' in agent_key):
                        target_agent = agent
                        break

            # Code execution routing
            elif any(keyword in content for keyword in [
                'execute', 'run code', 'python', 'bash', '```python', '```bash',
                'script', 'code execution'
            ]):
                # Look for CodeExecutorAgent
                for agent in self.agent_registry.values():
                    if agent.role == AgentRole.CODE_EXECUTOR:
                        target_agent = agent
                        break

            # Web scraping routing (only for explicit scraping requests)
            elif any(keyword in content for keyword in [
                'scrape', 'web scraping', 'crawl', 'extract from url', 'scrape_url',
                'apartments.com', 'scrape website'
            ]):
                # Look for WebScraperAgent
                for agent_key, agent in self.agent_registry.items():
                    if ('WebScraperAgent' in agent.__class__.__name__ or
                            'web_scraper' in agent_key or
                            'webscraper' in agent_key):
                        target_agent = agent
                        break

            # Default to Assistant Agent if no specific routing found
            if not target_agent:
                for agent in self.agent_registry.values():
                    if agent.role == AgentRole.ASSISTANT:
                        target_agent = agent
                        break

            if target_agent:
                logging.info(f"Routing message to {target_agent.__class__.__name__} ({target_agent.agent_id})")
                logging.info(f"Routing reason: Content analysis for '{content[:50]}...'")

                response = await target_agent.process_message(message, context)

                response.metadata.update({
                    'routed_by': self.agent_id,
                    'routed_to': target_agent.agent_id,
                    'routed_to_class': target_agent.__class__.__name__,
                    'routing_reason': f"Content matched {target_agent.__class__.__name__} patterns"
                })

                return response
            else:
                available_agents = [f"{agent.__class__.__name__} ({agent_id})" for agent_id, agent in
                                    self.agent_registry.items()]
                error_response = self.create_response(
                    content=f"I couldn't find an appropriate agent to handle your request. Available agents: {available_agents}",
                    recipient_id=message.sender_id,
                    message_type=MessageType.ERROR,
                    session_id=message.session_id,
                    conversation_id=message.conversation_id
                )
                return error_response

        except Exception as e:
            logging.error(f"Proxy routing error: {e}")
            error_response = self.create_response(
                content=f"Routing error: {str(e)}",
                recipient_id=message.sender_id,
                message_type=MessageType.ERROR,
                session_id=message.session_id,
                conversation_id=message.conversation_id
            )
            return error_response


class AgentFactory:
    """Factory for creating different types of agents - UPDATED WITH YOUTUBE SUPPORT"""

    @staticmethod
    def create_agent(role: AgentRole,
                     agent_id: str,
                     memory_manager: MemoryManagerInterface,
                     llm_service: LLMServiceInterface = None,
                     config: Dict[str, Any] = None,
                     **kwargs) -> BaseAgent:
        """Create an agent of the specified role"""

        if role == AgentRole.ASSISTANT:
            return AssistantAgent(
                agent_id=agent_id,
                memory_manager=memory_manager,
                llm_service=llm_service,
                **kwargs
            )
        elif role == AgentRole.CODE_EXECUTOR:
            return CodeExecutorAgent(
                agent_id=agent_id,
                memory_manager=memory_manager,
                llm_service=llm_service,
                **kwargs
            )
        elif role == AgentRole.RESEARCHER:
            # Import specialized agents dynamically based on configuration
            capabilities = validate_agent_capabilities(config)

            # PRIORITY ORDER: Knowledge Base > Web Search > YouTube > Web Scraper > Media Editor
            if capabilities.get('knowledge_base', False):
                try:
                    from ..agents.knowledge_base import KnowledgeBaseAgent
                    logging.info("Creating KnowledgeBaseAgent for RESEARCHER role")
                    return KnowledgeBaseAgent(
                        agent_id=agent_id,
                        memory_manager=memory_manager,
                        llm_service=llm_service,
                        **kwargs
                    )
                except Exception as e:
                    logging.error(f"Failed to create KnowledgeBaseAgent: {e}")

            elif capabilities.get('web_search', False):
                try:
                    from ..agents.web_search import WebSearchAgent
                    logging.info("Creating WebSearchAgent for RESEARCHER role")
                    return WebSearchAgent(
                        agent_id=agent_id,
                        memory_manager=memory_manager,
                        llm_service=llm_service,
                        **kwargs
                    )
                except Exception as e:
                    logging.error(f"Failed to create WebSearchAgent: {e}")

            elif capabilities.get('youtube_download', False):
                try:
                    from ..agents.youtube_download import YouTubeDownloadAgent
                    logging.info("Creating YouTubeDownloadAgent for RESEARCHER role")
                    return YouTubeDownloadAgent(
                        agent_id=agent_id,
                        memory_manager=memory_manager,
                        llm_service=llm_service,
                        **kwargs
                    )
                except Exception as e:
                    logging.error(f"Failed to create YouTubeDownloadAgent: {e}")

            elif capabilities.get('web_scraping', False):
                try:
                    from ..agents.web_scraper import WebScraperAgent
                    logging.info("Creating WebScraperAgent for RESEARCHER role")
                    return WebScraperAgent(
                        agent_id=agent_id,
                        memory_manager=memory_manager,
                        llm_service=llm_service,
                        **kwargs
                    )
                except Exception as e:
                    logging.error(f"Failed to create WebScraperAgent: {e}")

            elif capabilities.get('media_editor', False):
                try:
                    from ..agents.media_editor import MediaEditorAgent
                    logging.info("Creating MediaEditorAgent for RESEARCHER role")
                    return MediaEditorAgent(
                        agent_id=agent_id,
                        memory_manager=memory_manager,
                        llm_service=llm_service,
                        **kwargs
                    )
                except Exception as e:
                    logging.error(f"Failed to create MediaEditorAgent: {e}")

            # Fallback to assistant if no specialized researcher is available
            logging.warning("No specialized researcher agents available, falling back to AssistantAgent")
            return AssistantAgent(
                agent_id=agent_id,
                memory_manager=memory_manager,
                llm_service=llm_service,
                **kwargs
            )

        elif role == AgentRole.PROXY:
            return ProxyAgent(
                agent_id=agent_id,
                memory_manager=memory_manager,
                llm_service=llm_service,
                **kwargs
            )
        else:
            raise ValueError(f"Unsupported agent role: {role}")

    @staticmethod
    def create_specialized_agent(agent_type: str,
                                 agent_id: str,
                                 memory_manager: MemoryManagerInterface,
                                 llm_service: LLMServiceInterface = None,
                                 config: Dict[str, Any] = None,
                                 **kwargs) -> BaseAgent:
        """Create specialized agents by type name - UPDATED WITH YOUTUBE SUPPORT"""

        capabilities = validate_agent_capabilities(config)

        if agent_type == "knowledge_base":
            if not capabilities.get('knowledge_base', False):
                raise ValueError("Knowledge base not enabled in agent_config.yaml")
            from ..agents.knowledge_base import KnowledgeBaseAgent
            return KnowledgeBaseAgent(agent_id, memory_manager, llm_service, **kwargs)

        elif agent_type == "web_scraper":
            if not capabilities.get('web_scraping', False):
                raise ValueError("Web scraping not enabled in agent_config.yaml")
            from ..agents.web_scraper import WebScraperAgent
            return WebScraperAgent(agent_id, memory_manager, llm_service, **kwargs)

        elif agent_type == "web_search":
            if not capabilities.get('web_search', False):
                raise ValueError("Web search not enabled in agent_config.yaml")
            from ..agents.web_search import WebSearchAgent
            return WebSearchAgent(agent_id, memory_manager, llm_service, **kwargs)

        elif agent_type == "media_editor":
            if not capabilities.get('media_editor', False):
                raise ValueError("Media editor not enabled in agent_config.yaml")
            from ..agents.media_editor import MediaEditorAgent
            return MediaEditorAgent(agent_id, memory_manager, llm_service, **kwargs)

        elif agent_type == "youtube_download":
            if not capabilities.get('youtube_download', False):
                raise ValueError("YouTube download not enabled in agent_config.yaml")
            from ..agents.youtube_download import YouTubeDownloadAgent
            return YouTubeDownloadAgent(agent_id, memory_manager, llm_service, **kwargs)
        elif agent_type == "moderator":

            from ..agents.moderator import ModeratorAgent
            return ModeratorAgent(agent_id, memory_manager, llm_service, **kwargs)

        else:
            raise ValueError(f"Unknown or unavailable agent type: {agent_type}")

    @staticmethod
    def get_available_agent_types(config: Dict[str, Any] = None) -> Dict[str, bool]:
        """
        Get available agent types based on configuration.

        This now uses the centralized capability checking from loader.py
        """
        return get_available_agent_types(config)