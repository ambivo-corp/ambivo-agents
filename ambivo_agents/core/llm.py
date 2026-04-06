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

# LLM Provider imports - direct SDK usage (no langchain)
try:
    import openai

    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    import anthropic as anthropic_sdk

    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

try:
    import boto3

    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False

# Optional: LlamaIndex for knowledge base (installed via [knowledge] extra)
LLAMA_INDEX_AVAILABLE = False
SentenceSplitter = None
LangchainEmbedding = None
LlamaIndexSettings = None
try:
    from llama_index.core.node_parser import SentenceSplitter  # noqa: F811
    from llama_index.embeddings.langchain import LangchainEmbedding  # noqa: F811
    from llama_index.core import Settings as LlamaIndexSettings  # noqa: F811

    LLAMA_INDEX_AVAILABLE = True
except ImportError:
    pass

# Backward compat flag - True if at least one LLM provider is available
LANGCHAIN_AVAILABLE = OPENAI_AVAILABLE or ANTHROPIC_AVAILABLE or BOTO3_AVAILABLE


class LLMResponse:
    """Simple response object matching the interface previously provided by langchain"""

    def __init__(self, content: str):
        self.content = content
        self.text = content

    def __str__(self):
        return self.content


def _retry_with_backoff(func, max_retries=3, base_delay=1.0):
    """Retry a function with exponential backoff for rate limit (429) errors"""
    import time as _time

    for attempt in range(max_retries + 1):
        try:
            return func()
        except Exception as e:
            status = getattr(e, "status_code", None) or getattr(e, "status", None)
            status = getattr(e, "status_code", None) or getattr(e, "status", None)
            err_str = str(e).lower()
            is_rate_limit = status == 429 or "rate_limit" in err_str or "rate limit" in err_str
            if is_rate_limit and attempt < max_retries:
                delay = base_delay * (2 ** attempt)
                logging.warning(f"Rate limited (attempt {attempt + 1}/{max_retries + 1}), retrying in {delay}s")
                _time.sleep(delay)
            else:
                raise


async def _async_retry_with_backoff(coro_func, max_retries=3, base_delay=1.0):
    """Async retry with exponential backoff for rate limit (429) errors"""
    for attempt in range(max_retries + 1):
        try:
            return await coro_func()
        except Exception as e:
            status = getattr(e, "status_code", None) or getattr(e, "status", None)
            err_str = str(e).lower()
            is_rate_limit = status == 429 or "rate_limit" in err_str or "rate limit" in err_str
            if is_rate_limit and attempt < max_retries:
                delay = base_delay * (2 ** attempt)
                logging.warning(f"Rate limited (attempt {attempt + 1}/{max_retries + 1}), retrying in {delay}s")
                await asyncio.sleep(delay)
            else:
                raise


class DirectOpenAILLM:
    """Direct OpenAI SDK wrapper with invoke/ainvoke/astream interface"""

    def __init__(self, model: str, temperature: float, api_key: str):
        self.model = model
        self.temperature = temperature
        self.client = openai.OpenAI(api_key=api_key)
        self.async_client = openai.AsyncOpenAI(api_key=api_key)

    def invoke(self, prompt: str) -> LLMResponse:
        def _call():
            return self.client.chat.completions.create(
                model=self.model,
                temperature=self.temperature,
                messages=[{"role": "user", "content": prompt}],
            )

        response = _retry_with_backoff(_call)
        content = ""
        if response.choices and response.choices[0].message:
            content = response.choices[0].message.content or ""
        return LLMResponse(content)

    async def ainvoke(self, prompt: str) -> LLMResponse:
        async def _call():
            return await self.async_client.chat.completions.create(
                model=self.model,
                temperature=self.temperature,
                messages=[{"role": "user", "content": prompt}],
            )

        response = await _async_retry_with_backoff(_call)
        content = ""
        if response.choices and response.choices[0].message:
            content = response.choices[0].message.content or ""
        return LLMResponse(content)

    async def astream(self, prompt: str):
        try:
            stream = await self.async_client.chat.completions.create(
                model=self.model,
                temperature=self.temperature,
                messages=[{"role": "user", "content": prompt}],
                stream=True,
            )
            async for chunk in stream:
                delta = chunk.choices[0].delta if chunk.choices else None
                if delta and delta.content:
                    yield LLMResponse(delta.content)
        except Exception as e:
            logging.warning(f"OpenAI streaming failed, falling back to non-streaming: {e}")
            response = await self.ainvoke(prompt)
            yield response


class DirectAnthropicLLM:
    """Direct Anthropic SDK wrapper with invoke/ainvoke/astream interface"""

    def __init__(self, model: str, temperature: float, api_key: str, timeout: int = 120):
        self.model = model
        self.temperature = temperature
        self.client = anthropic_sdk.Anthropic(api_key=api_key)
        self.async_client = anthropic_sdk.AsyncAnthropic(api_key=api_key)
        self.timeout = timeout

    def invoke(self, prompt: str) -> LLMResponse:
        def _call():
            return self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                temperature=self.temperature,
                messages=[{"role": "user", "content": prompt}],
            )

        response = _retry_with_backoff(_call)
        content = ""
        if response.content:
            first = response.content[0]
            content = first.text if hasattr(first, "text") else str(first)
        return LLMResponse(content)

    async def ainvoke(self, prompt: str) -> LLMResponse:
        async def _call():
            return await self.async_client.messages.create(
                model=self.model,
                max_tokens=4096,
                temperature=self.temperature,
                messages=[{"role": "user", "content": prompt}],
            )

        response = await _async_retry_with_backoff(_call)
        content = ""
        if response.content:
            first = response.content[0]
            content = first.text if hasattr(first, "text") else str(first)
        return LLMResponse(content)

    async def astream(self, prompt: str):
        try:
            async with self.async_client.messages.stream(
                model=self.model,
                max_tokens=4096,
                temperature=self.temperature,
                messages=[{"role": "user", "content": prompt}],
            ) as stream:
                async for text in stream.text_stream:
                    if text:
                        yield LLMResponse(text)
        except Exception as e:
            logging.warning(f"Anthropic streaming failed, falling back to non-streaming: {e}")
            response = await self.ainvoke(prompt)
            yield response


class DirectBedrockLLM:
    """Direct AWS Bedrock wrapper with invoke/ainvoke/astream interface"""

    def __init__(self, model: str, client):
        self.model = model
        self.bedrock_client = client

    def invoke(self, prompt: str) -> LLMResponse:
        import json as _json

        def _call():
            # Anthropic Messages API format for Bedrock
            if "anthropic" in self.model:
                body = _json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 4096,
                    "messages": [{"role": "user", "content": prompt}],
                })
            else:
                # Generic format for other Bedrock models
                body = _json.dumps({"prompt": prompt, "max_tokens": 4096, "temperature": 0.5})

            return self.bedrock_client.invoke_model(modelId=self.model, body=body)

        response = _retry_with_backoff(_call)
        result = _json.loads(response["body"].read())

        # Parse response based on model format
        text = ""
        if "content" in result and isinstance(result["content"], list):
            # Anthropic Messages API response
            for block in result["content"]:
                if isinstance(block, dict) and block.get("type") == "text":
                    text += block.get("text", "")
        elif "generations" in result:
            # Cohere response format
            generations = result["generations"]
            text = generations[0].get("text", "") if generations else ""
        else:
            # Fallback for other formats
            text = result.get("completion", "") or result.get("output", "") or str(result)

        return LLMResponse(text)

    async def ainvoke(self, prompt: str) -> LLMResponse:
        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, self.invoke, prompt)
        except Exception as e:
            logging.error(f"Bedrock ainvoke failed: {e}", exc_info=True)
            raise

    async def astream(self, prompt: str):
        response = await self.ainvoke(prompt)
        yield response


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
            raise ImportError(
                "No LLM provider SDKs available. Install openai or anthropic."
            )

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
                model_name="claude-sonnet-4-5-20250514",
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
                model_name="anthropic.claude-sonnet-4-5-20250514-v1:0",
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

            # Setup LlamaIndex components if available (installed via [knowledge] extra)
            if self.current_llm and LLAMA_INDEX_AVAILABLE and self.current_embeddings:
                try:
                    self.embed_model = LangchainEmbedding(self.current_embeddings)
                    text_splitter = SentenceSplitter(chunk_size=1024, chunk_overlap=20)

                    LlamaIndexSettings.llm = self.current_llm
                    LlamaIndexSettings.embed_model = self.embed_model
                    LlamaIndexSettings.chunk_size = 512
                    LlamaIndexSettings.text_splitter = text_splitter
                except Exception as e:
                    logging.debug(f"LlamaIndex setup skipped: {e}")

        except Exception as e:
            logging.error(f"Failed to initialize {self.current_provider}: {e}", exc_info=True)
            self.provider_tracker.record_error(self.current_provider, str(e))
            self._try_fallback_provider()

    def _setup_anthropic(self):
        """Setup Anthropic provider using direct SDK"""
        if not ANTHROPIC_AVAILABLE:
            raise ImportError("anthropic package required. Install with: pip install anthropic")
        api_key = self.config_data.get("anthropic_api_key")
        if not api_key:
            raise ValueError("anthropic_api_key not configured")

        self.current_llm = DirectAnthropicLLM(
            model="claude-sonnet-4-5-20250514",
            temperature=self.temperature,
            api_key=api_key,
            timeout=120,
        )

        # VoyageAI embeddings are optional (installed via [voyageai] extra)
        voyage_key = self.config_data.get("voyage_api_key")
        if voyage_key:
            try:
                from langchain_voyageai import VoyageAIEmbeddings

                os.environ["VOYAGE_API_KEY"] = voyage_key
                self.current_embeddings = VoyageAIEmbeddings(
                    model="voyage-large-2", batch_size=128
                )
            except ImportError:
                logging.warning("VoyageAI not available - install ambivo-agents[voyageai]")

    def _setup_openai(self):
        """Setup OpenAI provider using direct SDK"""
        if not OPENAI_AVAILABLE:
            raise ImportError("openai package required. Install with: pip install openai")
        api_key = self.config_data.get("openai_api_key")
        if not api_key:
            raise ValueError("openai_api_key not configured")

        self.current_llm = DirectOpenAILLM(
            model="gpt-4o", temperature=self.temperature, api_key=api_key
        )
        # OpenAI embeddings via direct SDK
        self.current_embeddings = None  # Embeddings handled by LlamaIndex if [knowledge] installed

    def _setup_bedrock(self):
        """Setup Bedrock provider using direct boto3 SDK"""
        if not BOTO3_AVAILABLE:
            raise ImportError("boto3 package required. Install with: pip install boto3")
        aws_access_key = self.config_data.get("aws_access_key_id")
        if not aws_access_key:
            raise ValueError("aws_access_key_id not configured")
        aws_secret_key = self.config_data.get("aws_secret_access_key")
        if not aws_secret_key:
            raise ValueError("aws_secret_access_key not configured")
        boto3_client = boto3.client(
            "bedrock-runtime",
            region_name=self.config_data.get("aws_region", "us-east-1"),
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_key,
        )

        self.current_llm = DirectBedrockLLM(
            model="anthropic.claude-sonnet-4-5-20250514-v1:0", client=boto3_client
        )
        self.current_embeddings = None  # Embeddings handled by LlamaIndex if [knowledge] installed

    def _try_fallback_provider(self):
        """Try to switch to a fallback provider"""
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
            # Sort by priority and error count - FIXED: Use .priority instead of ['priority']
            fallback_providers.sort(key=lambda x: (x[1].priority, x[1].error_count))
            old_provider = self.current_provider
            self.current_provider = fallback_providers[0][0]
            self.provider_tracker.current_provider = self.current_provider

            logging.info(f"LLM provider rotated: {old_provider} → {self.current_provider}")

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
                logging.warning(f"Streaming error with {self.current_provider}: {e}", exc_info=True)

                # Record error
                self.provider_tracker.record_error(self.current_provider, str(e))

                # Only retry on transient/rate-limit errors
                is_retryable = any(
                    keyword in error_str
                    for keyword in [
                        "429", "rate limit", "quota", "insufficient_quota",
                        "timeout", "connection", "network", "502", "503", "504",
                    ]
                )

                if is_retryable and retry_count < max_retries - 1:
                    # Exponential backoff before retry
                    backoff = min(2 ** retry_count, 30)
                    logging.info(
                        f"Retrying after {backoff}s backoff from {self.current_provider} "
                        f"(attempt {retry_count + 1}/{max_retries})"
                    )
                    await asyncio.sleep(backoff)

                    if self._try_fallback_provider():
                        retry_count += 1
                        continue
                    else:
                        raise e
                else:
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
                logging.error(f"Error with {self.current_provider}: {e}", exc_info=True)

                # Record error
                self.provider_tracker.record_error(self.current_provider, str(e))

                # Only retry on transient/rate-limit errors
                is_retryable = any(
                    keyword in error_str
                    for keyword in [
                        "429", "rate limit", "quota", "insufficient_quota",
                        "timeout", "connection", "network", "502", "503", "504",
                    ]
                )

                if is_retryable and retry_count < max_retries - 1:
                    backoff = min(2 ** retry_count, 30)
                    logging.info(
                        f"Retrying after {backoff}s backoff from {self.current_provider} "
                        f"(attempt {retry_count + 1}/{max_retries})"
                    )
                    import time
                    time.sleep(backoff)

                    if self._try_fallback_provider():
                        retry_count += 1
                        continue
                    else:
                        raise e
                else:
                    raise e

        raise RuntimeError(f"All {max_retries} providers exhausted")

    async def generate_response(
        self, prompt: str, context: Dict[str, Any] = None, system_message: str = None
    ) -> str:
        """Generate a response using the current LLM provider Preserves context across provider switches"""
        if not self.current_llm:
            raise RuntimeError("No LLM provider available")

        # Build context-aware prompt BEFORE provider calls
        final_prompt = self._build_system_aware_prompt(prompt, context, system_message)

        def _generate():
            try:
                if hasattr(self.current_llm, "invoke"):
                    # FIX: Use context-enhanced prompt
                    response = self.current_llm.invoke(final_prompt)
                    if hasattr(response, "content"):
                        return response.content
                    elif hasattr(response, "text"):
                        return response.text
                    else:
                        return str(response)
                elif hasattr(self.current_llm, "predict"):
                    # FIX: Use context-enhanced prompt
                    return self.current_llm.predict(final_prompt)
                elif hasattr(self.current_llm, "__call__"):
                    # FIX: Use context-enhanced prompt
                    response = self.current_llm(final_prompt)
                    if hasattr(response, "content"):
                        return response.content
                    elif hasattr(response, "text"):
                        return response.text
                    else:
                        return str(response)
                else:
                    # FIX: Use context-enhanced prompt
                    return str(self.current_llm(final_prompt))
            except Exception as e:
                logging.error(f"LLM generation error: {e}", exc_info=True)
                raise e

        try:
            return self._execute_with_retry(_generate)
        except Exception as e:
            raise RuntimeError(f"Failed to generate response after retries: {str(e)}")

    def _build_system_aware_prompt(
        self, user_prompt: str, context: Dict[str, Any] = None, system_message: str = None
    ) -> str:
        """Build prompt with system message integration"""

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
        """Build context-aware prompt that preserves conversation history across provider switches"""
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

        # CRITICAL: Log provider switches with context preservation
        if hasattr(self, "_last_provider") and self._last_provider != self.current_provider:
            logging.info(f"Provider switched: {self._last_provider} → {self.current_provider}")
            logging.info(f"Context preserved: {len(conversation_history)} messages in history")

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
            async for chunk in self.current_llm.astream(prompt):
                content = chunk.content if hasattr(chunk, "content") else str(chunk)
                if content and content != "None":
                    yield content
        except Exception as e:
            logging.warning(f"Anthropic streaming failed, falling back to non-streaming: {e}")
            try:
                response = await self.current_llm.ainvoke(prompt)
                yield response.content if hasattr(response, "content") else str(response)
            except Exception as fallback_err:
                logging.error(f"Anthropic non-streaming fallback also failed: {fallback_err}", exc_info=True)
                raise RuntimeError(f"Anthropic streaming exhausted: {fallback_err}") from fallback_err

    async def _stream_openai(self, prompt: str) -> AsyncIterator[str]:
        """Stream from OpenAI GPT"""
        try:
            async for chunk in self.current_llm.astream(prompt):
                content = chunk.content if hasattr(chunk, "content") else str(chunk)
                if content and content != "None":
                    yield content
        except Exception as e:
            logging.warning(f"OpenAI streaming failed, falling back to non-streaming: {e}")
            try:
                response = await self.current_llm.ainvoke(prompt)
                yield response.content if hasattr(response, "content") else str(response)
            except Exception as fallback_err:
                logging.error(f"OpenAI non-streaming fallback also failed: {fallback_err}", exc_info=True)
                raise RuntimeError(f"OpenAI streaming exhausted: {fallback_err}") from fallback_err

    async def _stream_bedrock(self, prompt: str) -> AsyncIterator[str]:
        """Stream from AWS Bedrock"""
        try:
            async for chunk in self.current_llm.astream(prompt):
                content = chunk.content if hasattr(chunk, "content") else str(chunk)
                if content and content != "None":
                    yield content
        except Exception as e:
            logging.warning(f"Bedrock streaming failed, falling back to non-streaming: {e}")
            try:
                response = await self.current_llm.ainvoke(prompt)
                yield response.content if hasattr(response, "content") else str(response)
            except Exception as fallback_err:
                logging.error(f"Bedrock non-streaming fallback also failed: {fallback_err}", exc_info=True)
                raise RuntimeError(f"Bedrock streaming exhausted: {fallback_err}") from fallback_err


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
