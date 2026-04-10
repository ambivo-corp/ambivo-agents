# ambivo_agents/services/factory.py
"""
Agent Factory for creating different types of agents

Author: Hemant Gosain 'Sunny'
Company: Ambivo
Email: sgosain@ambivo.com
License: MIT
"""

import logging
from typing import Any, Dict, Optional

from ..agents.assistant import AssistantAgent
from ..config.loader import (
    get_available_agent_types,
    get_config_section,
    get_enabled_capabilities,
    load_config,
    validate_agent_capabilities,
)
from ..core.base import AgentMessage, AgentRole, BaseAgent, MessageType
from ..core.llm import LLMServiceInterface
from ..core.memory import MemoryManagerInterface


class ProxyAgent(BaseAgent):
    """Agent that routes incoming messages to specialized agents based on content analysis.

    Maintains a registry of agents and matches message content against keyword
    patterns to select the appropriate handler (web search, knowledge base,
    web scraper, etc.). Falls back to the AssistantAgent when no pattern matches.
    """

    def __init__(self, agent_id: str, memory_manager, llm_service=None, **kwargs):
        super().__init__(
            agent_id=agent_id,
            role=AgentRole.PROXY,
            memory_manager=memory_manager,
            llm_service=llm_service,
            name="Proxy Agent",
            description="Agent that routes messages to appropriate specialized agents",
            **kwargs,
        )
        self.agent_registry: Dict[str, BaseAgent] = {}

    def register_agent(self, agent: BaseAgent) -> bool:
        """Register an agent in the routing registry.

        Args:
            agent: Agent instance to register. Must have an agent_id attribute.

        Returns:
            True if registration succeeded, False otherwise.
        """
        if agent and hasattr(agent, "agent_id"):
            self.agent_registry[agent.agent_id] = agent
            logging.info(
                f"Registered agent {agent.agent_id} ({agent.__class__.__name__}) with proxy"
            )
            return True
        else:
            logging.error(f"Failed to register agent: invalid agent object")
            return False

    def get_registered_agents(self) -> Dict[str, BaseAgent]:
        """Get all registered agents"""
        return self.agent_registry.copy()

    def unregister_agent(self, agent_id: str) -> bool:
        """Remove an agent from the routing registry by its ID."""
        if agent_id in self.agent_registry:
            del self.agent_registry[agent_id]
            logging.info(f"Unregistered agent {agent_id} from proxy")
            return True
        return False

    async def process_message(self, message, context=None):
        """Route a message to the appropriate specialized agent based on keyword content analysis.

        Args:
            message: AgentMessage to route.
            context: Optional execution context.

        Returns:
            AgentMessage response from the selected agent, with routing metadata attached.
        """
        self.memory.store_message(message)

        try:
            content = message.content.lower()


            target_agent = None

            # Web search routing (HIGH PRIORITY for web search requests)
            if any(
                keyword in content
                for keyword in [
                    "search web",
                    "web search",
                    "find online",
                    "search_web",
                    "brave search",
                    "aves search",
                    "search the web",
                    "search for",
                ]
            ):
                # Look for WebSearchAgent by class name or agent key
                for agent_key, agent in self.agent_registry.items():
                    if (
                        "WebSearchAgent" in agent.__class__.__name__
                        or "web_search" in agent_key
                        or "websearch" in agent_key
                    ):
                        target_agent = agent
                        break

            # Knowledge Base routing (for KB operations)
            elif any(
                keyword in content
                for keyword in [
                    "ingest_document",
                    "ingest_text",
                    "ingest",
                    "knowledge base",
                    "kb",
                    "query_knowledge_base",
                    "query",
                    "search documents",
                    "vector database",
                    "qdrant",
                    "semantic search",
                    "document",
                    "pdf",
                    "docx",
                ]
            ):
                # Look for KnowledgeBaseAgent
                for agent_key, agent in self.agent_registry.items():
                    if (
                        "KnowledgeBaseAgent" in agent.__class__.__name__
                        or "knowledge_base" in agent_key
                        or "knowledge" in agent_key
                    ):
                        target_agent = agent
                        break

            # Web scraping routing (only for explicit scraping requests)
            elif any(
                keyword in content
                for keyword in [
                    "scrape",
                    "web scraping",
                    "crawl",
                    "extract from url",
                    "scrape_url",
                    "apartments.com",
                    "scrape website",
                ]
            ):
                # Look for WebScraperAgent
                for agent_key, agent in self.agent_registry.items():
                    if (
                        "WebScraperAgent" in agent.__class__.__name__
                        or "web_scraper" in agent_key
                        or "webscraper" in agent_key
                    ):
                        target_agent = agent
                        break

            # Default to Assistant Agent if no specific routing found
            if not target_agent:
                for agent in self.agent_registry.values():
                    if agent.role == AgentRole.ASSISTANT:
                        target_agent = agent
                        break

            if target_agent:
                logging.info(
                    f"Routing message to {target_agent.__class__.__name__} ({target_agent.agent_id})"
                )
                logging.info(f"Routing reason: Content analysis for '{content[:50]}...'")

                response = await target_agent.process_message(message, context)

                response.metadata.update(
                    {
                        "routed_by": self.agent_id,
                        "routed_to": target_agent.agent_id,
                        "routed_to_class": target_agent.__class__.__name__,
                        "routing_reason": f"Content matched {target_agent.__class__.__name__} patterns",
                    }
                )

                return response
            else:
                available_agents = [
                    f"{agent.__class__.__name__} ({agent_id})"
                    for agent_id, agent in self.agent_registry.items()
                ]
                error_response = self.create_response(
                    content=f"I couldn't find an appropriate agent to handle your request. Available agents: {available_agents}",
                    recipient_id=message.sender_id,
                    message_type=MessageType.ERROR,
                    session_id=message.session_id,
                    conversation_id=message.conversation_id,
                )
                return error_response

        except Exception as e:
            logging.error(f"Proxy routing error: {e}")
            error_response = self.create_response(
                content=f"Routing error: {str(e)}",
                recipient_id=message.sender_id,
                message_type=MessageType.ERROR,
                session_id=message.session_id,
                conversation_id=message.conversation_id,
            )
            return error_response


class AgentFactory:
    """Factory for creating agent instances by role or specialized type name."""

    @staticmethod
    def create_agent(
        role: AgentRole,
        agent_id: str,
        memory_manager: MemoryManagerInterface,
        llm_service: LLMServiceInterface = None,
        config: Dict[str, Any] = None,
        **kwargs,
    ) -> BaseAgent:
        """Create an agent instance for the given AgentRole.

        For RESEARCHER role, selects the best available specialized agent
        (KnowledgeBase > WebSearch > WebScraper) based on config capabilities.

        Args:
            role: The AgentRole to create (ASSISTANT, RESEARCHER, PROXY).
            agent_id: Unique identifier for the agent.
            memory_manager: Memory manager for conversation persistence.
            llm_service: Optional LLM service for language generation.
            config: Optional config dict for capability checking.

        Returns:
            A BaseAgent subclass instance.

        Raises:
            ValueError: If the role is unsupported or agent creation fails.
        """

        if role == AgentRole.ASSISTANT:
            return AssistantAgent(
                agent_id=agent_id, memory_manager=memory_manager, llm_service=llm_service, **kwargs
            )
        elif role == AgentRole.RESEARCHER:
            # Import specialized agents dynamically based on configuration
            capabilities = validate_agent_capabilities(config)


            if capabilities.get("knowledge_base", False):
                try:
                    from ..agents.knowledge_base import KnowledgeBaseAgent

                    logging.info("Creating KnowledgeBaseAgent for RESEARCHER role")
                    return KnowledgeBaseAgent(
                        agent_id=agent_id,
                        memory_manager=memory_manager,
                        llm_service=llm_service,
                        **kwargs,
                    )
                except Exception as e:
                    logging.error(f"Failed to create KnowledgeBaseAgent: {e}", exc_info=True)
                    raise ValueError(f"Failed to create KnowledgeBaseAgent: {e}") from e

            elif capabilities.get("web_search", False):
                try:
                    from ..agents.web_search import WebSearchAgent

                    logging.info("Creating WebSearchAgent for RESEARCHER role")
                    return WebSearchAgent(
                        agent_id=agent_id,
                        memory_manager=memory_manager,
                        llm_service=llm_service,
                        **kwargs,
                    )
                except Exception as e:
                    logging.error(f"Failed to create WebSearchAgent: {e}", exc_info=True)
                    raise ValueError(f"Failed to create WebSearchAgent: {e}") from e

            elif capabilities.get("web_scraping", False):
                try:
                    from ..agents.web_scraper import WebScraperAgent

                    logging.info("Creating WebScraperAgent for RESEARCHER role")
                    return WebScraperAgent(
                        agent_id=agent_id,
                        memory_manager=memory_manager,
                        llm_service=llm_service,
                        **kwargs,
                    )
                except Exception as e:
                    logging.error(f"Failed to create WebScraperAgent: {e}", exc_info=True)
                    raise ValueError(f"Failed to create WebScraperAgent: {e}") from e

            # Fallback to assistant if no specialized researcher is available
            logging.warning(
                "No specialized researcher agents available, falling back to AssistantAgent"
            )
            return AssistantAgent(
                agent_id=agent_id, memory_manager=memory_manager, llm_service=llm_service, **kwargs
            )

        elif role == AgentRole.PROXY:
            return ProxyAgent(
                agent_id=agent_id, memory_manager=memory_manager, llm_service=llm_service, **kwargs
            )
        else:
            raise ValueError(f"Unsupported agent role: {role}")

    @staticmethod
    def create_specialized_agent(
        agent_type: str,
        agent_id: str,
        memory_manager: MemoryManagerInterface,
        llm_service: LLMServiceInterface = None,
        config: Dict[str, Any] = None,
        **kwargs,
    ) -> BaseAgent:
        """Create a specialized agent by type name string.

        Args:
            agent_type: One of 'knowledge_base', 'web_scraper', 'web_search', 'moderator'.
            agent_id: Unique identifier for the agent.
            memory_manager: Memory manager for conversation persistence.
            llm_service: Optional LLM service.
            config: Config dict used to validate capabilities are enabled.

        Returns:
            A specialized BaseAgent subclass instance.

        Raises:
            ValueError: If agent_type is unknown or not enabled in config.
        """

        capabilities = validate_agent_capabilities(config)

        if agent_type == "knowledge_base":
            if not capabilities.get("knowledge_base", False):
                raise ValueError("Knowledge base not enabled in agent_config.yaml")
            from ..agents.knowledge_base import KnowledgeBaseAgent

            return KnowledgeBaseAgent(agent_id, memory_manager, llm_service, **kwargs)

        elif agent_type == "web_scraper":
            if not capabilities.get("web_scraping", False):
                raise ValueError("Web scraping not enabled in agent_config.yaml")
            from ..agents.web_scraper import WebScraperAgent

            return WebScraperAgent(agent_id, memory_manager, llm_service, **kwargs)

        elif agent_type == "web_search":
            if not capabilities.get("web_search", False):
                raise ValueError("Web search not enabled in agent_config.yaml")
            from ..agents.web_search import WebSearchAgent

            return WebSearchAgent(agent_id, memory_manager, llm_service, **kwargs)

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
