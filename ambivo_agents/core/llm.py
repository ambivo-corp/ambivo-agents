# ambivo_agents/core/llm.py
"""
LLM service with multiple provider support and automatic rotation.
"""

import asyncio
import logging
import os
import re
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Any, AsyncIterator, Dict, List, Optional

from ..config.loader import get_config_section, load_config
from .base import ProviderConfig, ProviderTracker

# LLM Provider imports
try:
    import boto3
    import openai
    from langchain.chains.llm_math.base import LLMMathChain
    from langchain_anthropic import ChatAnthropic
    from langchain_aws import BedrockEmbeddings, BedrockLLM
    from langchain_openai import ChatOpenAI, OpenAIEmbeddings
    from langchain_voyageai import VoyageAIEmbeddings
    from llama_index.core.node_parser import SentenceSplitter
    from llama_index.embeddings.langchain import LangchainEmbedding

    LANGCHAIN_AVAILABLE = True
except ImportError as e:
    LANGCHAIN_AVAILABLE = False
    logging.warning(f"LangChain dependencies not available: {e}")


class LLMServiceInterface(ABC):
    """Abstract interface for LLM services"""

    @abstractmethod
    async def generate_response(self, prompt: str, context: Dict[str, Any] = None) -> str:
        """Generate a response using the LLM"""
        pass

    @abstractmethod
    async def query_knowledge_base(
        self, query: str, kb_name: str, context: Dict[str, Any] = None
    ) -> tuple[str, List[Dict]]:
        """Query a knowledge base"""
        pass

    @abstractmethod
    async def generate_response_stream(
        self, prompt: str, context: Dict[str, Any] = None
    ) -> AsyncIterator[str]:
        """Generate a streaming response using the LLM"""
        pass


def _clean_chunk_content(chunk: str) -> str:
    """Clean chunk content to remove unwanted text while preserving formatting"""
    if not chunk or not isinstance(chunk, str):
        return ""

    # Remove common unwanted patterns
    unwanted_patterns = [
        r"<bound method.*?>",
        r"AIMessageChunk\(.*?\)",
        r"content=\'\'",
        r"additional_kwargs=\{\}",
        r"response_metadata=.*?",
        r"id=\'run--.*?\'",
    ]

    cleaned = chunk
    for pattern in unwanted_patterns:
        cleaned = re.sub(pattern, "", cleaned)

    # Only strip if the entire chunk is whitespace, preserve internal formatting
    return cleaned if cleaned.strip() else ""


class MultiProviderLLMService(LLMServiceInterface):
    """LLM service with multiple provider support and automatic rotation"""

    def __init__(self, config_data: Dict[str, Any] = None, preferred_provider: str = "openai"):
        # Load configuration from YAML if not provided
        if config_data is None:
            config = load_config()
            config_data = get_config_section("llm", config)

        self.config_data = config_data
        self.preferred_provider = preferred_provider
        self.provider_tracker = ProviderTracker()
        self.current_llm = None
        self.current_embeddings = None
        self.temperature = config_data.get("temperature", 0.5)

        if not LANGCHAIN_AVAILABLE:
            raise ImportError("LangChain dependencies are required but not available")

        # Initialize providers
        self._initialize_providers()

        # Set current provider
        self.current_provider = self.provider_tracker.get_best_available_provider()
        if preferred_provider and self.provider_tracker.is_provider_available(preferred_provider):
            self.current_provider = preferred_provider

        self.provider_tracker.current_provider = self.current_provider

        # Initialize the current provider
        if self.current_provider:
            self._initialize_current_provider()
        else:
            raise RuntimeError("No available LLM providers configured")

    def _initialize_providers(self):
        """Initialize all available providers"""

        # Anthropic configuration
        if self.config_data.get("anthropic_api_key"):
            self.provider_tracker.providers["anthropic"] = ProviderConfig(
                name="anthropic",
                model_name="claude-3-5-sonnet-20241022",
                priority=1,
                max_requests_per_minute=50,
                max_requests_per_hour=1000,
                cooldown_minutes=5,
            )

        # OpenAI configuration
        if self.config_data.get("openai_api_key"):
            self.provider_tracker.providers["openai"] = ProviderConfig(
                name="openai",
                model_name="gpt-4o",
                priority=2,
                max_requests_per_minute=60,
                max_requests_per_hour=3600,
                cooldown_minutes=3,
            )

        # Bedrock configuration
        if self.config_data.get("aws_access_key_id"):
            self.provider_tracker.providers["bedrock"] = ProviderConfig(
                name="bedrock",
                model_name="cohere.command-text-v14",
                priority=3,
                max_requests_per_minute=40,
                max_requests_per_hour=2400,
                cooldown_minutes=10,
            )

        if not self.provider_tracker.providers:
            raise RuntimeError("No LLM providers configured in YAML config")

    def _initialize_current_provider(self):
        """Initialize the current provider's LLM and embeddings"""
        try:
            if self.current_provider == "anthropic":
                self._setup_anthropic()
            elif self.current_provider == "openai":
                self._setup_openai()
            elif self.current_provider == "bedrock":
                self._setup_bedrock()

            # Setup common components using the correct imports
            if self.current_llm:
                self.llm_math = LLMMathChain.from_llm(self.current_llm, verbose=False)

                if self.current_embeddings:
                    self.embed_model = LangchainEmbedding(self.current_embeddings)

                    # Setup LlamaIndex components
                    text_splitter = SentenceSplitter(chunk_size=1024, chunk_overlap=20)

                    # Configure LlamaIndex Settings
                    try:
                        from llama_index.core import Settings

                        Settings.llm = self.current_llm
                        Settings.embed_model = self.embed_model
                        Settings.chunk_size = 512
                        Settings.text_splitter = text_splitter
                    except ImportError:
                        logging.warning("LlamaIndex Settings not available")

        except Exception as e:
            logging.error(f"Failed to initialize {self.current_provider}: {e}")
            self.provider_tracker.record_error(self.current_provider, str(e))
            self._try_fallback_provider()

    def _setup_anthropic(self):
        """Setup Anthropic provider"""
        os.environ["ANTHROPIC_API_KEY"] = self.config_data["anthropic_api_key"]
        if self.config_data.get("voyage_api_key"):
            os.environ["VOYAGE_API_KEY"] = self.config_data["voyage_api_key"]

        self.current_llm = ChatAnthropic(
            model_name="claude-3-5-sonnet-20241022",
            temperature=self.temperature,
            timeout=None,
            stop=None,
        )

        if self.config_data.get("voyage_api_key"):
            self.current_embeddings = VoyageAIEmbeddings(model="voyage-large-2", batch_size=128)

    def _setup_openai(self):
        """Setup OpenAI provider"""
        os.environ["OPENAI_API_KEY"] = self.config_data["openai_api_key"]
        openai.api_key = self.config_data["openai_api_key"]

        self.current_llm = ChatOpenAI(model="gpt-4o", temperature=self.temperature)
        self.current_embeddings = OpenAIEmbeddings()

    def _setup_bedrock(self):
        """Setup Bedrock provider"""
        boto3_client = boto3.client(
            "bedrock-runtime",
            region_name=self.config_data.get("aws_region", "us-east-1"),
            aws_access_key_id=self.config_data["aws_access_key_id"],
            aws_secret_access_key=self.config_data["aws_secret_access_key"],
        )

        self.current_llm = BedrockLLM(model="cohere.command-text-v14", client=boto3_client)
        self.current_embeddings = BedrockEmbeddings(
            model_id="amazon.titan-embed-text-v1", client=boto3_client
        )

    # ambivo_agents/core/llm.py - FIXED LLM rotation logic

    # Fix for ambivo_agents/core/llm.py
    # Replace the _try_fallback_provider method with this corrected version:

    # Fix for ambivo_agents/core/llm.py
    # Replace the _try_fallback_provider method with this corrected version:

    def _try_fallback_provider(self):
        """Try to switch to a fallback provider - FIXED VERSION"""
        # Find available providers (excluding current one)
        fallback_providers = []
        for name, config in self.provider_tracker.providers.items():
            if name != self.current_provider and self.provider_tracker.is_provider_available(name):
                fallback_providers.append((name, config))

        if not fallback_providers:
            # Check if any providers are in cooldown and can be restored
            for name, config in self.provider_tracker.providers.items():
                if (
                    name != self.current_provider
                    and not config.is_available
                    and config.last_error_time
                ):

                    time_since_error = datetime.now() - config.last_error_time
                    if time_since_error > timedelta(minutes=config.cooldown_minutes):
                        config.is_available = True
                        config.error_count = 0
                        fallback_providers.append((name, config))
                        logging.info(f"Restored provider {name} from cooldown")

        if fallback_providers:
            # Sort by priority and error count - ✅ FIXED: Use .priority instead of ['priority']
            fallback_providers.sort(key=lambda x: (x[1].priority, x[1].error_count))
            old_provider = self.current_provider
            self.current_provider = fallback_providers[0][0]
            self.provider_tracker.current_provider = self.current_provider

            print(f"LLM provider rotated: {old_provider} → {self.current_provider}")

            # Re-initialize the new provider
            self._initialize_current_provider()
            return True
        else:
            logging.error("No fallback providers available")
            return False

    async def _execute_with_retry_stream(self, stream_func) -> AsyncIterator[str]:
        """FIXED: Execute streaming function with proper provider rotation"""
        max_retries = len(self.provider_tracker.providers)
        retry_count = 0

        while retry_count < max_retries:
            try:
                # Record request for current provider
                self.provider_tracker.record_request(self.current_provider)

                async for chunk in stream_func():
                    yield chunk
                return  # Success, exit retry loop

            except Exception as e:
                error_str = str(e).lower()
                logging.error(f"Streaming error with {self.current_provider}: {e}")

                # Record error
                self.provider_tracker.record_error(self.current_provider, str(e))

                # Check if we should retry with different provider
                should_retry = (
                    any(
                        keyword in error_str
                        for keyword in ["429", "rate limit", "quota", "insufficient_quota"]
                    )
                    or any(keyword in error_str for keyword in ["timeout", "connection", "network"])
                    or retry_count < max_retries - 1
                )

                if should_retry:
                    logging.warning(
                        f"Attempting fallback from {self.current_provider} (attempt {retry_count + 1}/{max_retries})"
                    )

                    if self._try_fallback_provider():
                        retry_count += 1
                        continue
                    else:
                        # No fallback available, raise the error
                        raise e
                else:
                    # Max retries reached
                    raise e

        raise RuntimeError(f"All {max_retries} providers exhausted for streaming")

    def _execute_with_retry(self, func, *args, **kwargs):
        """FIXED: Execute function with proper provider rotation"""
        max_retries = len(self.provider_tracker.providers)
        retry_count = 0

        while retry_count < max_retries:
            try:
                # Record request for current provider
                self.provider_tracker.record_request(self.current_provider)
                return func(*args, **kwargs)

            except Exception as e:
                error_str = str(e).lower()
                logging.error(f"Error with {self.current_provider}: {e}")

                # Record error
                self.provider_tracker.record_error(self.current_provider, str(e))

                # Check if we should retry
                should_retry = (
                    any(
                        keyword in error_str
                        for keyword in ["429", "rate limit", "quota", "insufficient_quota"]
                    )
                    or any(keyword in error_str for keyword in ["timeout", "connection", "network"])
                    or retry_count < max_retries - 1
                )

                if should_retry:
                    logging.warning(
                        f"Attempting fallback from {self.current_provider} (attempt {retry_count + 1}/{max_retries})"
                    )

                    if self._try_fallback_provider():
                        retry_count += 1
                        continue
                    else:
                        # No fallback available
                        raise e
                else:
                    # Max retries reached or non-retryable error
                    raise e

        raise RuntimeError(f"All {max_retries} providers exhausted")

    async def generate_response(
        self, prompt: str, context: Dict[str, Any] = None, system_message: str = None
    ) -> str:
        """Generate a response using the current LLM provider Preserves context across provider switches"""
        if not self.current_llm:
            raise RuntimeError("No LLM provider available")

        # 🔥 Build context-aware prompt BEFORE provider calls
        final_prompt = self._build_system_aware_prompt(prompt, context, system_message)

        def _generate():
            try:
                if hasattr(self.current_llm, "invoke"):
                    # 🔥 FIX: Use context-enhanced prompt
                    response = self.current_llm.invoke(final_prompt)
                    if hasattr(response, "content"):
                        return response.content
                    elif hasattr(response, "text"):
                        return response.text
                    else:
                        return str(response)
                elif hasattr(self.current_llm, "predict"):
                    # 🔥 FIX: Use context-enhanced prompt
                    return self.current_llm.predict(final_prompt)
                elif hasattr(self.current_llm, "__call__"):
                    # 🔥 FIX: Use context-enhanced prompt
                    response = self.current_llm(final_prompt)
                    if hasattr(response, "content"):
                        return response.content
                    elif hasattr(response, "text"):
                        return response.text
                    else:
                        return str(response)
                else:
                    # 🔥 FIX: Use context-enhanced prompt
                    return str(self.current_llm(final_prompt))
            except Exception as e:
                logging.error(f"LLM generation error: {e}")
                raise e

        try:
            return self._execute_with_retry(_generate)
        except Exception as e:
            raise RuntimeError(f"Failed to generate response after retries: {str(e)}")

    def _build_system_aware_prompt(
        self, user_prompt: str, context: Dict[str, Any] = None, system_message: str = None
    ) -> str:
        """🆕 Build prompt with system message integration"""

        prompt_parts = []

        # 1. Add system message if provided
        if system_message:
            prompt_parts.append(f"SYSTEM INSTRUCTIONS:\n{system_message}\n")

        # 2. Add conversation context (existing functionality enhanced)
        if context and context.get("conversation_history"):
            conversation_history = context["conversation_history"]
            prompt_parts.append("CONVERSATION HISTORY:")

            for msg in conversation_history[-5:]:  # Last 5 messages
                msg_type = msg.get("message_type", "unknown")
                content = msg.get("content", "")

                if msg_type == "user_input":
                    prompt_parts.append(f"User: {content}")
                elif msg_type == "agent_response":
                    prompt_parts.append(f"Assistant: {content}")

            prompt_parts.append("")  # Empty line separator

        # 3. Add current user prompt
        prompt_parts.append(f"CURRENT REQUEST:\n{user_prompt}")

        # 4. Add final instruction that respects system message
        if system_message:
            prompt_parts.append(
                "\nRespond according to your system instructions above, considering the conversation history."
            )

        return "\n".join(prompt_parts)

    def _build_context_aware_prompt(self, prompt: str, context: Dict[str, Any] = None) -> str:
        """🔥 NEW: Build context-aware prompt that preserves conversation history across provider switches"""
        if not context:
            return prompt

        # Extract conversation history from context
        conversation_history = context.get("conversation_history", [])
        conversation_id = context.get("conversation_id")
        user_id = context.get("user_id")

        if not conversation_history:
            return prompt

        # Build conversation context
        context_lines = []
        context_lines.append("# Previous Conversation Context:")

        for msg in conversation_history[-5:]:  # Last 5 messages for context
            msg_type = msg.get("message_type", "unknown")
            content = msg.get("content", "")
            timestamp = msg.get("timestamp", "")

            if msg_type == "user_input":
                context_lines.append(f"User: {content}")
            elif msg_type == "agent_response":
                context_lines.append(f"Assistant: {content}")

        context_lines.append("")
        context_lines.append("# Current Request:")
        context_lines.append(f"User: {prompt}")
        context_lines.append("")
        context_lines.append("Please respond considering the previous conversation context above.")

        enhanced_prompt = "\n".join(context_lines)

        # 🔥 CRITICAL: Log provider switches with context preservation
        if hasattr(self, "_last_provider") and self._last_provider != self.current_provider:
            logging.info(f"🔄 Provider switched: {self._last_provider} → {self.current_provider}")
            logging.info(f"🧠 Context preserved: {len(conversation_history)} messages in history")

        self._last_provider = self.current_provider

        return enhanced_prompt

    async def generate_response_stream(
        self, prompt: str, context: Dict[str, Any] = None, system_message: str = None
    ) -> AsyncIterator[str]:
        """Generate a streaming response - FIXED: Preserves context across provider switches"""
        if not self.current_llm:
            raise RuntimeError("No LLM provider available")

        final_prompt = self._build_system_aware_prompt(prompt, context, system_message)

        async def _generate_stream():
            try:
                if self.current_provider == "anthropic":
                    async for chunk in self._stream_anthropic(final_prompt):
                        yield chunk
                elif self.current_provider == "openai":
                    async for chunk in self._stream_openai(final_prompt):
                        yield chunk
                elif self.current_provider == "bedrock":
                    async for chunk in self._stream_bedrock(final_prompt):
                        yield chunk
                else:
                    # Fallback to non-streaming
                    response = await self.generate_response(prompt, context)  # Use original method
                    yield response
            except Exception as e:
                logging.error(f"LLM streaming error: {e}")
                raise e

        try:
            async for chunk in self._execute_with_retry_stream(_generate_stream):
                self.provider_tracker.record_request(self.current_provider)
                yield chunk
        except Exception as e:
            raise RuntimeError(f"Failed to generate streaming response: {str(e)}")

    async def query_knowledge_base(
        self, query: str, kb_name: str, context: Dict[str, Any] = None
    ) -> tuple[str, List[Dict]]:
        """Query a knowledge base (placeholder implementation)"""
        # This would integrate with your actual knowledge base system
        response = await self.generate_response(
            f"Based on the knowledge base '{kb_name}', answer: {query}"
        )

        sources = [{"source": f"{kb_name}_knowledge_base", "relevance_score": 0.9}]
        return response, sources

    def get_current_provider(self) -> str:
        """Get the current provider name"""
        return self.current_provider

    def get_available_providers(self) -> List[str]:
        """Get list of available provider names"""
        return [
            name
            for name, config in self.provider_tracker.providers.items()
            if self.provider_tracker.is_provider_available(name)
        ]

    def get_provider_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all providers"""
        stats = {}
        for name, config in self.provider_tracker.providers.items():
            stats[name] = {
                "priority": config.priority,
                "request_count": config.request_count,
                "error_count": config.error_count,
                "is_available": config.is_available,
                "last_request_time": (
                    config.last_request_time.isoformat() if config.last_request_time else None
                ),
                "last_error_time": (
                    config.last_error_time.isoformat() if config.last_error_time else None
                ),
            }
        return stats

    async def _stream_anthropic(self, prompt: str) -> AsyncIterator[str]:
        """Stream from Anthropic Claude"""
        try:
            # Use Anthropic's streaming API
            async for chunk in self.current_llm.astream(prompt):
                if hasattr(chunk, "content") and chunk.content:
                    yield chunk.content
                elif hasattr(chunk, "text") and chunk.text:
                    yield chunk.text
                else:
                    # For AIMessageChunk objects, extract content properly
                    content = str(chunk)
                    if content and content != "None" and not content.startswith("<bound method"):
                        yield content
        except Exception as e:
            # Fallback for older Anthropic client versions
            try:
                async for chunk in self.current_llm.astream(prompt):
                    if hasattr(chunk, "content") and chunk.content:
                        yield chunk.content
            except:
                # Non-streaming fallback
                response = await self.current_llm.ainvoke(prompt)
                yield response.content if hasattr(response, "content") else str(response)

    async def _stream_openai(self, prompt: str) -> AsyncIterator[str]:
        """Stream from OpenAI GPT"""
        try:
            # Use OpenAI's streaming API
            async for chunk in self.current_llm.astream(prompt):
                # Handle different chunk types properly
                if hasattr(chunk, "content"):
                    if isinstance(chunk.content, str) and chunk.content:
                        yield chunk.content
                    elif hasattr(chunk.content, "text") and chunk.content.text:
                        yield chunk.content.text
                elif hasattr(chunk, "text") and chunk.text:
                    yield chunk.text
                else:
                    # Extract content from AIMessageChunk properly
                    content_str = str(chunk)
                    if (
                        content_str
                        and content_str != "None"
                        and not content_str.startswith("<bound method")
                        and not content_str.startswith("AIMessageChunk")
                    ):
                        yield content_str
        except Exception as e:
            # Fallback for older OpenAI client versions
            try:
                response = await self.current_llm.ainvoke(prompt)
                yield response.content if hasattr(response, "content") else str(response)
            except Exception as e2:
                yield f"OpenAI streaming error: {str(e2)}"

    async def _stream_bedrock(self, prompt: str) -> AsyncIterator[str]:
        """Stream from AWS Bedrock"""
        try:
            # Bedrock streaming might not be available in all versions
            if hasattr(self.current_llm, "astream"):
                async for chunk in self.current_llm.astream(prompt):
                    if hasattr(chunk, "content") and chunk.content:
                        yield chunk.content
                    elif hasattr(chunk, "text") and chunk.text:
                        yield chunk.text
                    else:
                        content = str(chunk)
                        if (
                            content
                            and content != "None"
                            and not content.startswith("<bound method")
                        ):
                            yield content
            else:
                # Non-streaming fallback for Bedrock
                response = await self.current_llm.ainvoke(prompt)
                yield response.content if hasattr(response, "content") else str(response)
        except Exception as e:
            # Bedrock fallback
            try:
                response = await self.generate_response(prompt)
                yield response
            except:
                yield f"Bedrock streaming error: {str(e)}"


def create_multi_provider_llm_service(
    config_data: Dict[str, Any] = None, preferred_provider: str = "openai"
) -> MultiProviderLLMService:
    """
    Create a multi-provider LLM service with configuration from YAML.

    Args:
        config_data: Optional LLM configuration. If None, loads from YAML.
        preferred_provider: Preferred provider name

    Returns:
        MultiProviderLLMService instance
    """
    return MultiProviderLLMService(config_data, preferred_provider)
