# ambivo_agents/agents/knowledge_base.py
"""
LLM-Aware Knowledge Base Agent with conversation history and intelligent intent detection
Updated for consistency with other agents
"""

import asyncio
import json
import tempfile
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncIterator, Coroutine, Dict, List, Optional, Union

import logging
import requests

from ..config.loader import get_config_section, load_config
from ..core.file_resolution import resolve_agent_file_path
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
from ..core.history import ContextType, KnowledgeBaseAgentHistoryMixin

_logger = logging.getLogger(__name__)


class TempKBAdapter:
    """Adapter that routes KB operations through vectordb-api temp KB endpoints.

    Instead of writing directly to Qdrant (permanent collections), this adapter
    uses the vectordb-api HTTP endpoints which provide:
    - Automatic TTL-based expiration
    - Redis lifecycle tracking
    - Session-scoped collection naming
    - Centralized cleanup via /pgv/temp_kb_cleanup
    """

    def __init__(self, vectordb_api_url: str, api_token: str = None,
                 session_id: str = None, ttl_hours: float = 24):
        self.base_url = vectordb_api_url.rstrip("/")
        self.api_token = api_token
        self.session_id = session_id
        self.ttl_hours = ttl_hours
        self._kb_name = None # Resolved on first call

    @property
    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"
        return headers

    # Ingestion 

    def persist_embeddings(
        self, kb_name: str, doc_path: str = None, documents=None,
        custom_meta: Dict[str, Any] = None
    ) -> int:
        """Persist embeddings via vectordb-api temp_kb_index_text endpoint.

        Converts documents/file content to text and posts to the temp KB
        HTTP endpoint which handles chunking, embedding, and TTL tracking.

        Returns:
            1 on success, 2 on error (matches QdrantServiceAdapter contract)
        """
        try:
            text = self._resolve_text(doc_path, documents)
            if not text:
                _logger.error("No text content to index into temp KB")
                return 2

            payload = {
                "session_id": self.session_id,
                "text": text,
                "ttl_hours": self.ttl_hours,
            }
            if self._kb_name:
                payload["kb_name"] = self._kb_name

            resp = requests.post(
                f"{self.base_url}/pgv/temp_kb_index_text",
                headers=self._headers,
                json=payload,
                timeout=60,
            )

            if not resp.ok:
                error_body = resp.text[:500]
                _logger.error(f"Temp KB indexing HTTP {resp.status_code}: {error_body}")
                return 2

            result = resp.json()

            if result.get("success"):
                self._kb_name = result.get("kb_name")
                _logger.info(
                    f"Indexed text into temp KB '{self._kb_name}' "
                    f"(chunks: {result.get('chunks_added')}, "
                    f"expires: {result.get('expires_at')})"
                )
                return 1
            else:
                _logger.error(f"Temp KB indexing failed: {result.get('message')}")
                return 2

        except Exception as e:
            _logger.error(f"Error persisting to temp KB: {e}")
            return 2

    def documents_from_text(self, input_text: str) -> list:
        """Convert text to document-like dicts for persist_embeddings compatibility."""
        # For TempKBAdapter, we pass raw text directly to the API.
        # Return a simple wrapper so persist_embeddings can extract it.
        return [{"text": input_text}]

    # Querying 

    def conduct_query(
        self, query: str, kb_name: str, additional_prompt: str = None,
        question_type: str = "free-text", option_list=None,
    ) -> tuple:
        """Query the temp KB via vectordb-api temp_kb_query endpoint."""
        try:
            payload = {
                "session_id": self.session_id,
                "query": query,
                "use_llm": False,
                "top_k": 5,
            }
            if additional_prompt:
                payload["additional_prompt"] = additional_prompt

            resp = requests.post(
                f"{self.base_url}/pgv/temp_kb_query",
                headers=self._headers,
                json=payload,
                timeout=60,
            )

            if not resp.ok:
                error_msg = f"Temp KB query HTTP {resp.status_code}: {resp.text[:500]}"
                _logger.error(error_msg)
                return error_msg, [{"answer": error_msg, "source": "", "source_list": []}]

            result = resp.json()

            if result.get("success"):
                answer = result.get("answer", "")
                source_list = result.get("source_details", result.get("results", []))
                ans_dict_list = [{"answer": answer, "source": "", "source_list": source_list}]
                return answer, ans_dict_list
            else:
                error_msg = result.get("message", "Query failed")
                return error_msg, [{"answer": error_msg, "source": "", "source_list": []}]

        except Exception as e:
            error_msg = f"Temp KB query error: {e}"
            _logger.error(error_msg)
            return error_msg, [{"answer": error_msg, "source": "", "source_list": []}]

    # Cleanup 

    def delete_temp_kb(self) -> bool:
        """Delete this temp KB via vectordb-api."""
        try:
            resp = requests.delete(
                f"{self.base_url}/pgv/temp_kb_delete",
                headers=self._headers,
                json={"session_id": self.session_id},
                timeout=30,
            )

            if not resp.ok:
                _logger.warning(f"Temp KB delete HTTP {resp.status_code}: {resp.text[:500]}")
                return False

            result = resp.json()
            if result.get("success"):
                _logger.info(f"Deleted temp KB for session {self.session_id}")
                return True
            else:
                _logger.warning(f"Temp KB delete failed: {result.get('message')}")
                return False
        except Exception as e:
            _logger.error(f"Error deleting temp KB for session {self.session_id}: {e}")
            return False

    # Helpers 

    def _resolve_text(self, doc_path: str = None, documents=None) -> str:
        """Extract text content from a file path or document list."""
        if documents:
            parts = []
            for doc in documents:
                if isinstance(doc, dict):
                    parts.append(doc.get("text", str(doc)))
                elif hasattr(doc, "get_text"):
                    parts.append(doc.get_text())
                elif hasattr(doc, "text"):
                    parts.append(doc.text)
                elif hasattr(doc, "page_content"):
                    parts.append(doc.page_content)
                else:
                    parts.append(str(doc))
            return "\n\n".join(parts)

        if doc_path:
            try:
                path = Path(doc_path)
                if path.exists() and path.is_file():
                    return path.read_text(errors="replace")
            except Exception as e:
                _logger.error(f"Could not read file {doc_path}: {e}")

        return ""


class QdrantServiceAdapter:
    """Adapter for Knowledge Base functionality using YAML configuration"""

    def __init__(self):
        # Load from YAML configuration
        config = load_config()
        kb_config = get_config_section("knowledge_base", config)

        self.qdrant_url = kb_config.get("qdrant_url")
        self.qdrant_api_key = kb_config.get("qdrant_api_key")

        if not self.qdrant_url:
            raise ValueError("qdrant_url is required in knowledge_base configuration")

        # Initialize Qdrant client
        try:
            import qdrant_client

            if self.qdrant_api_key:
                self.client = qdrant_client.QdrantClient(
                    url=self.qdrant_url, api_key=self.qdrant_api_key
                )
            else:
                self.client = qdrant_client.QdrantClient(url=self.qdrant_url)

        except ImportError:
            raise ImportError("qdrant-client package required for Knowledge Base functionality")
        except Exception as e:
            raise ConnectionError(f"Failed to connect to Qdrant: {e}")

        # Configure LlamaIndex Settings (embed_model + llm) from ambivo config
        self._configure_llama_index(config)
        self._configure_llm(config)

    def _configure_llama_index(self, config: Dict[str, Any]) -> None:
        """Set up LlamaIndex Settings (embed_model + llm) using available provider keys.

        Embeddings: OpenAI → Bedrock → VoyageAI
        LLM: OpenAI → Anthropic (via langchain) → Bedrock
        """
        import os
        try:
            from llama_index.core import Settings
        except ImportError:
            return  # LlamaIndex not installed — nothing to configure

        llm_config = get_config_section("llm", config)

        # --- 1. OpenAI (preferred — fastest, cheapest) ---
        openai_key = llm_config.get("openai_api_key") or os.environ.get("OPENAI_API_KEY")
        if openai_key:
            try:
                from llama_index.embeddings.openai import OpenAIEmbedding
                Settings.embed_model = OpenAIEmbedding(api_key=openai_key)
                _logger.info("LlamaIndex embed_model set to OpenAIEmbedding")
                return
            except ImportError:
                pass
            # Fallback: langchain wrapper for OpenAI
            try:
                from langchain_openai import OpenAIEmbeddings
                from llama_index.embeddings.langchain import LangchainEmbedding
                Settings.embed_model = LangchainEmbedding(OpenAIEmbeddings(openai_api_key=openai_key))
                _logger.info("LlamaIndex embed_model set to LangchainEmbedding(OpenAI)")
                return
            except ImportError:
                pass

        # --- 2. AWS Bedrock (Titan embeddings) ---
        aws_access_key = llm_config.get("aws_access_key_id") or os.environ.get("AWS_ACCESS_KEY_ID")
        aws_secret_key = llm_config.get("aws_secret_access_key") or os.environ.get("AWS_SECRET_ACCESS_KEY")
        aws_region = llm_config.get("aws_region") or os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
        if aws_access_key and aws_secret_key:
            try:
                from langchain_aws import BedrockEmbeddings
                from llama_index.embeddings.langchain import LangchainEmbedding
                import boto3
                bedrock_client = boto3.client(
                    "bedrock-runtime",
                    region_name=aws_region,
                    aws_access_key_id=aws_access_key,
                    aws_secret_access_key=aws_secret_key,
                )
                bedrock_embed = BedrockEmbeddings(
                    client=bedrock_client,
                    model_id="amazon.titan-embed-text-v2:0",
                )
                Settings.embed_model = LangchainEmbedding(bedrock_embed)
                _logger.info("LlamaIndex embed_model set to Bedrock Titan embeddings")
                return
            except (ImportError, Exception) as e:
                _logger.debug(f"Bedrock embeddings not available: {e}")

        # --- 3. VoyageAI (Anthropic's embedding partner) ---
        voyage_key = os.environ.get("VOYAGE_API_KEY")
        if voyage_key:
            try:
                from langchain_voyageai import VoyageAIEmbeddings
                from llama_index.embeddings.langchain import LangchainEmbedding
                Settings.embed_model = LangchainEmbedding(
                    VoyageAIEmbeddings(voyage_api_key=voyage_key, model="voyage-3")
                )
                _logger.info("LlamaIndex embed_model set to VoyageAI embeddings")
                return
            except (ImportError, Exception) as e:
                _logger.debug(f"VoyageAI embeddings not available: {e}")

        _logger.warning(
            "No embedding provider configured. Set one of: "
            "AMBIVO_AGENTS_LLM_OPENAI_API_KEY, AWS credentials, or VOYAGE_API_KEY"
        )

    def _configure_llm(self, config: Dict[str, Any]) -> None:
        """Set LlamaIndex Settings.llm so response_synthesizer doesn't default to OpenAI."""
        import os
        try:
            from llama_index.core import Settings
        except ImportError:
            return

        llm_config = get_config_section("llm", config)
        openai_key = llm_config.get("openai_api_key") or os.environ.get("OPENAI_API_KEY")

        # --- 1. OpenAI ---
        if openai_key:
            try:
                from llama_index.llms.openai import OpenAI as LlamaOpenAI
                Settings.llm = LlamaOpenAI(api_key=openai_key, model="gpt-4o-mini")
                _logger.info("LlamaIndex LLM set to OpenAI gpt-4o-mini")
                return
            except ImportError:
                pass

        # --- 2. Anthropic via langchain ---
        anthropic_key = llm_config.get("anthropic_api_key") or os.environ.get("ANTHROPIC_API_KEY")
        if anthropic_key:
            try:
                from langchain_anthropic import ChatAnthropic
                from llama_index.llms.langchain import LangChainLLM
                lc_llm = ChatAnthropic(anthropic_api_key=anthropic_key, model_name="claude-sonnet-4-5-20250514")
                Settings.llm = LangChainLLM(llm=lc_llm)
                _logger.info("LlamaIndex LLM set to Anthropic Claude via LangChain")
                return
            except ImportError:
                pass

        # --- 3. Bedrock ---
        aws_access_key = llm_config.get("aws_access_key_id") or os.environ.get("AWS_ACCESS_KEY_ID")
        aws_secret_key = llm_config.get("aws_secret_access_key") or os.environ.get("AWS_SECRET_ACCESS_KEY")
        aws_region = llm_config.get("aws_region") or os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
        if aws_access_key and aws_secret_key:
            try:
                from langchain_aws import ChatBedrock
                from llama_index.llms.langchain import LangChainLLM
                import boto3
                bedrock_client = boto3.client(
                    "bedrock-runtime", region_name=aws_region,
                    aws_access_key_id=aws_access_key, aws_secret_access_key=aws_secret_key,
                )
                lc_llm = ChatBedrock(client=bedrock_client, model_id="anthropic.claude-sonnet-4-5-20250514-v1:0")
                Settings.llm = LangChainLLM(llm=lc_llm)
                _logger.info("LlamaIndex LLM set to Bedrock Claude")
                return
            except (ImportError, Exception) as e:
                _logger.debug(f"Bedrock LLM not available: {e}")

        _logger.warning("No LLM provider configured for LlamaIndex response synthesis")

    def documents_from_text(self, input_text: str) -> list:
        """Convert text to documents format"""
        from langchain.text_splitter import RecursiveCharacterTextSplitter
        from llama_index.core.readers import Document as LIDoc

        # Load chunk settings from config
        config = load_config()
        kb_config = get_config_section("knowledge_base", config)

        chunk_size = kb_config.get("chunk_size", 1024)
        chunk_overlap = kb_config.get("chunk_overlap", 20)

        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size, chunk_overlap=chunk_overlap
        )
        splitted_documents = text_splitter.create_documents(texts=[input_text])

        # Convert to llama-index format
        docs = [LIDoc.from_langchain_format(doc) for doc in splitted_documents]
        return docs

    def persist_embeddings(
        self, kb_name: str, doc_path: str = None, documents=None, custom_meta: Dict[str, Any] = None
    ) -> int:
        """Persist embeddings to Qdrant"""
        try:
            config = load_config()
            kb_config = get_config_section("knowledge_base", config)

            if not documents and doc_path:
                # Use enhanced file processor service
                from ..services.file_processor import FileProcessorService

                file_processor = FileProcessorService()

                # Check if file is supported by enhanced processor
                if file_processor.is_supported_file(doc_path):
                    self.logger.info(f"Using enhanced file processor for {doc_path}")
                    documents = file_processor.process_file(doc_path, custom_meta)
                else:
                    # Fallback to UnstructuredLoader for unsupported files
                    self.logger.info(f"Using UnstructuredLoader fallback for {doc_path}")
                    try:
                        from langchain_unstructured import UnstructuredLoader
                        from llama_index.core.readers import Document as LIDoc

                        loader = UnstructuredLoader(doc_path)
                        lang_docs = loader.load()
                        documents = [LIDoc.from_langchain_format(doc) for doc in lang_docs]
                    except Exception as fallback_ex:
                        self.logger.warning(f"UnstructuredLoader also failed: {fallback_ex}")
                        return 2

            if not documents:
                return 2 # Error

            # Add custom metadata
            if custom_meta:
                for doc in documents:
                    if not hasattr(doc, "metadata"):
                        doc.metadata = {}
                    doc.metadata.update(custom_meta)

            # Create collection name with prefix from config
            collection_prefix = kb_config.get("default_collection_prefix", "")
            collection_name = kb_name
            if collection_prefix:
                collection_name = f"{collection_prefix}_{kb_name}"

            # Create vector store and index
            from llama_index.core import StorageContext, VectorStoreIndex
            from llama_index.vector_stores.qdrant import QdrantVectorStore

            vector_store = QdrantVectorStore(client=self.client, collection_name=collection_name)

            storage_context = StorageContext.from_defaults(vector_store=vector_store)
            index = VectorStoreIndex.from_documents(documents, storage_context=storage_context)

            return 1 # Success

        except Exception as e:
            self.logger.error(f"Error persisting embeddings: {e}")
            return 2 # Error

    def conduct_query(
        self,
        query: str,
        kb_name: str,
        additional_prompt: str = None,
        question_type: str = "free-text",
        option_list=None,
    ) -> tuple:
        """Query the knowledge base"""
        try:
            config = load_config()
            kb_config = get_config_section("knowledge_base", config)

            collection_prefix = kb_config.get("default_collection_prefix", "")
            collection_name = kb_name
            if collection_prefix:
                collection_name = f"{collection_prefix}_{kb_name}"

            similarity_top_k = kb_config.get("similarity_top_k", 5)

            # Create vector store and query engine
            from llama_index.core import VectorStoreIndex, get_response_synthesizer
            from llama_index.core.indices.vector_store import VectorIndexRetriever
            from llama_index.core.query_engine import RetrieverQueryEngine
            from llama_index.vector_stores.qdrant import QdrantVectorStore

            vector_store = QdrantVectorStore(client=self.client, collection_name=collection_name)

            index = VectorStoreIndex.from_vector_store(vector_store=vector_store)
            retriever = VectorIndexRetriever(similarity_top_k=similarity_top_k, index=index)
            response_synthesizer = get_response_synthesizer()
            query_engine = RetrieverQueryEngine(
                retriever=retriever, response_synthesizer=response_synthesizer
            )

            # Execute query
            response = query_engine.query(query)
            answer = str(response)
            source_list = []

            if hasattr(response, "source_nodes") and response.source_nodes:
                for node in response.source_nodes:
                    source_info = {
                        "text": node.node.get_text()[:200] + "...",
                        "score": getattr(node, "score", 0.0),
                        "metadata": getattr(node.node, "metadata", {}),
                    }
                    source_list.append(source_info)

            ans_dict_list = [
                {
                    "answer": answer,
                    "source": f"Found {len(source_list)} relevant sources",
                    "source_list": source_list,
                }
            ]

            return answer, ans_dict_list

        except Exception as e:
            error_msg = f"Query error: {str(e)}"
            return error_msg, [{"answer": error_msg, "source": "", "source_list": []}]


class KnowledgeBaseAgent(BaseAgent, KnowledgeBaseAgentHistoryMixin):
    """LLM-Aware Knowledge Base Agent with conversation context and intelligent routing"""

    def __init__(
        self,
        agent_id: str = None,
        memory_manager=None,
        llm_service=None,
        system_message: str = None,
        **kwargs,
    ):
        if agent_id is None:
            agent_id = f"kb_{str(uuid.uuid4())[:8]}"

        default_system = """You are a specialized knowledge base agent with the following capabilities:
            - Ingest, store, and semantically search documents using vector databases
            - Support multiple document formats (PDF, DOCX, TXT, HTML, etc.)
            - Remember knowledge base operations and document references from conversations
            - Understand context like "search in that document" or "add this to the knowledge base"
            - Provide relevant, sourced answers from the knowledge base with citations
            - Manage multiple knowledge bases and collections efficiently"""

        super().__init__(
            agent_id=agent_id,
            role=AgentRole.RESEARCHER,
            memory_manager=memory_manager,
            llm_service=llm_service,
            name="Knowledge Base Agent",
            description="LLM-aware knowledge base agent with conversation history",
            system_message=system_message or default_system,
            **kwargs,
        )

        # Initialize history mixin
        self.setup_history_mixin()

        # Initialize Qdrant service
        try:
            self.qdrant_service = QdrantServiceAdapter()
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Knowledge Base service: {e}")

        # Add knowledge base tools
        self._add_knowledge_base_tools()

    async def _llm_analyze_kb_intent(
        self, user_message: str, conversation_context: str = ""
    ) -> Dict[str, Any]:
        """Use LLM to analyze knowledge base related intent and topics"""
        if not self.llm_service:
            return self._keyword_based_kb_analysis(user_message)

        prompt = f"""
        Analyze this user message in the context of a knowledge base conversation and extract:
        1. Primary intent (ingest_document, ingest_text, query_kb, create_kb, manage_kb, help_request)
        2. Knowledge base name (if mentioned or inferrable)
        3. Document/file references (file paths, document names)
        4. Query content (if querying)
        5. Context references (referring to previous KB operations)
        6. Operation specifics (metadata, query type, etc.)
        7. Key topics and keywords for routing to the right knowledge base(s)

        IMPORTANT: The kb_name must be the EXACT, COMPLETE identifier as it appears in the message.
        Do NOT truncate, shorten, or remove any part of it (including numeric suffixes, hashes, or IDs).
        Copy the full knowledge base name character-for-character from the message.

        Conversation Context:
        {conversation_context}

        Current User Message: {user_message}

        Respond in JSON format:
        {{
            "primary_intent": "ingest_document|ingest_text|query_kb|create_kb|manage_kb|help_request",
            "kb_name": "knowledge_base_name or null",
            "document_references": ["file1.pdf", "doc2.txt"],
            "query_content": "the actual question to ask" or null,
            "uses_context_reference": true/false,
            "context_type": "previous_kb|previous_document|previous_query",
            "operation_details": {{
                "query_type": "free-text|multi-select|single-select|yes-no",
                "custom_metadata": {{}},
                "source_type": "file|url|text"
            }},
            "topics": ["topic1", "topic2", "keywordA"],
            "confidence": 0.0-1.0
        }}
        """

        try:
            response = await self.llm_service.generate_response(prompt)
            import re

            json_match = re.search(r"\{.*\}", response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                result = self._validate_kb_name_from_message(result, user_message)
                return result
            else:
                return self._extract_kb_intent_from_llm_response(response, user_message)
        except Exception as e:
            return self._keyword_based_kb_analysis(user_message)

    def _validate_kb_name_from_message(self, intent_result: Dict[str, Any], user_message: str) -> Dict[str, Any]:
        """Validate and recover potentially truncated kb_name from the original message.

        LLMs sometimes truncate long collection names (e.g. dropping trailing hash suffixes).
        This finds the full name in the original message and corrects the result.
        """
        import re

        kb_name = intent_result.get("kb_name")
        if not kb_name or kb_name not in user_message:
            return intent_result

        # Find all potential collection-style identifiers in the message
        # Matches patterns like: content_5a77b0fb_kavehg-franchise_5a77b0fb8b57864d7e16d4ba
        # or more generally any long underscore/hyphen-separated identifier
        candidates = re.findall(r'[a-zA-Z][a-zA-Z0-9_-]{8,}', user_message)

        for candidate in candidates:
            # If the LLM-extracted name is a prefix of a longer candidate, use the full one
            if candidate.startswith(kb_name) and len(candidate) > len(kb_name):
                self.logger.info(
                    f"KB name corrected: '{kb_name}' -> '{candidate}'"
                )
                intent_result["kb_name"] = candidate
                break

        return intent_result

    def _keyword_based_kb_analysis(self, user_message: str) -> Dict[str, Any]:
        """Fallback keyword-based KB intent analysis with simple topic extraction"""
        content_lower = user_message.lower()

        # Determine intent
        if any(
            word in content_lower for word in ["ingest", "upload", "add document", "import", "load"]
        ):
            intent = "ingest_document"
        elif any(word in content_lower for word in ["add text", "ingest text", "text to"]):
            intent = "ingest_text"
        elif any(
            word in content_lower
            for word in ["query", "search", "find", "ask", "what", "how", "where"]
        ):
            intent = "query_kb"
        elif any(word in content_lower for word in ["create", "new kb", "make kb", "setup"]):
            intent = "create_kb"
        elif any(word in content_lower for word in ["help", "what can", "how to"]):
            intent = "help_request"
        else:
            intent = "help_request"

        # Extract KB names and documents
        kb_names = self.extract_context_from_text(user_message, ContextType.KNOWLEDGE_BASE)
        documents = self.extract_context_from_text(user_message, ContextType.DOCUMENT_NAME)
        file_paths = self.extract_context_from_text(user_message, ContextType.FILE_PATH)
        all_documents = documents + file_paths

        # Extract query content
        query_content = (
            self._extract_query_from_kb_message(user_message) if intent == "query_kb" else None
        )

        # Simple topic extraction: keywords longer than 3 chars, minus stopwords
        stop = {
            "the",
            "and",
            "for",
            "with",
            "this",
            "that",
            "into",
            "what",
            "how",
            "where",
            "why",
            "when",
            "from",
            "about",
            "please",
            "can",
            "you",
            "me",
            "to",
            "in",
            "on",
            "of",
            "a",
            "an",
            "is",
            "are",
        }
        topics = [w.strip(".,:;!?()[]{}\"'") for w in user_message.lower().split()]
        topics = [w for w in topics if len(w) > 3 and w not in stop]
        topics = list(dict.fromkeys(topics))[:10]

        return {
            "primary_intent": intent,
            "kb_name": kb_names[0] if kb_names else None,
            "document_references": all_documents,
            "query_content": query_content,
            "uses_context_reference": any(word in content_lower for word in ["this", "that", "it"]),
            "context_type": "previous_kb",
            "operation_details": {
                "query_type": "free-text",
                "custom_metadata": {},
                "source_type": "file",
            },
            "topics": topics,
            "confidence": 0.7,
        }

    # ambivo_agents/agents/knowledge_base.py - FIXED METHODS for context preservation

    async def process_message(
        self, message: Union[str, AgentMessage], context: ExecutionContext = None
    ) -> AgentMessage:
        """Process message with LLM-based KB intent detection - FIXED: Context preserved across provider switches"""
        # Handle both string and AgentMessage inputs
        if isinstance(message, AgentMessage):
            user_message = message.content
            original_message = message
        else:
            user_message = str(message)
            original_message = AgentMessage(
                id=str(uuid.uuid4()),
                sender_id=context.user_id if context else self.context.user_id,
                recipient_id=self.agent_id,
                content=user_message,
                message_type=MessageType.USER_INPUT,
                timestamp=datetime.now(),
            )

        self.memory.store_message(original_message)

        try:

            # Update conversation state
            self.update_conversation_state(user_message)

            # Get conversation context AND conversation history
            conversation_context = self._get_kb_conversation_context_summary()
            conversation_history = []

            try:
                conversation_history = await self.get_conversation_history(
                    limit=5, include_metadata=True
                )
            except Exception as e:
                self.logger.warning(f"Could not get conversation history: {e}")

            # FIX: Build LLM context with conversation history
            llm_context = {
                "conversation_history": conversation_history, # KEY FIX
                "conversation_id": original_message.conversation_id,
                "user_id": original_message.sender_id,
                "agent_type": "knowledge_base",
            }

            # FIX: Use LLM to analyze intent WITH CONTEXT
            intent_analysis = await self._llm_analyze_kb_intent_with_context(
                user_message, conversation_context, llm_context
            )

            # Merge external kb_names/topics into operation_details for routing
            try:
                op = intent_analysis.get("operation_details") or {}
                # bring topics from intent
                if intent_analysis.get("topics") is not None:
                    op["topics"] = intent_analysis.get("topics")
                op["primary_intent_inferred"] = intent_analysis.get("primary_intent")
                # pick kb_names from message metadata or context metadata
                external_kbs = []
                if isinstance(original_message, AgentMessage) and original_message.metadata:
                    external_kbs = original_message.metadata.get("kb_names") or []
                if not external_kbs and context and getattr(context, "metadata", None):
                    external_kbs = context.metadata.get("kb_names") or []
                if external_kbs:
                    op["kb_names"] = external_kbs
                intent_analysis["operation_details"] = op
            except Exception as _:
                pass

            # Route request based on LLM analysis with context
            response_content = await self._route_kb_with_llm_analysis_with_context(
                intent_analysis, user_message, context, llm_context
            )

            if isinstance(response_content, tuple):
                response_content, resp_metadata = response_content
            else:
                resp_metadata = {}

            response = self.create_response(
                content=response_content,
                metadata=resp_metadata,
                recipient_id=original_message.sender_id,
                session_id=original_message.session_id,
                conversation_id=original_message.conversation_id,
            )

            self.memory.store_message(response)
            return response

        except Exception as e:
            error_response = self.create_response(
                content=f"Knowledge Base Agent error: {str(e)}",
                recipient_id=original_message.sender_id,
                message_type=MessageType.ERROR,
                session_id=original_message.session_id,
                conversation_id=original_message.conversation_id,
            )
            return error_response

    async def _llm_analyze_kb_intent_with_context(
        self, user_message: str, conversation_context: str = "", llm_context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Use LLM to analyze knowledge base related intent - FIXED: With conversation context and topics"""
        if not self.llm_service:
            return self._keyword_based_kb_analysis(user_message)

        prompt = f"""
        Analyze this user message in the context of a knowledge base conversation and extract:
        1. Primary intent (ingest_document, ingest_text, query_kb, create_kb, manage_kb, help_request)
        2. Knowledge base name (if mentioned or inferrable)
        3. Document/file references (file paths, document names)
        4. Query content (if querying)
        5. Context references (referring to previous KB operations)
        6. Operation specifics (metadata, query type, etc.)
        7. Key topics and keywords for routing to the right knowledge base(s)

        IMPORTANT: The kb_name must be the EXACT, COMPLETE identifier as it appears in the message.
        Do NOT truncate, shorten, or remove any part of it (including numeric suffixes, hashes, or IDs).
        Copy the full knowledge base name character-for-character from the message.

        Conversation Context:
        {conversation_context}

        Current User Message: {user_message}

        Respond in JSON format:
        {{
            "primary_intent": "ingest_document|ingest_text|query_kb|create_kb|manage_kb|help_request",
            "kb_name": "knowledge_base_name or null",
            "document_references": ["file1.pdf", "doc2.txt"],
            "query_content": "the actual question to ask" or null,
            "uses_context_reference": true/false,
            "context_type": "previous_kb|previous_document|previous_query",
            "operation_details": {{
                "query_type": "free-text|multi-select|single-select|yes-no",
                "custom_metadata": {{}},
                "source_type": "file|url|text"
            }},
            "topics": ["topic1", "topic2", "keywordA"],
            "confidence": 0.0-1.0
        }}
        """

        try:
            # FIX: Pass conversation history through context
            response = await self.llm_service.generate_response(
                prompt=prompt,
                context=llm_context, # KEY: Context preserves memory across provider switches
            )

            import re

            json_match = re.search(r"\{.*\}", response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                result = self._validate_kb_name_from_message(result, user_message)
                return result
            else:
                return self._extract_kb_intent_from_llm_response(response, user_message)
        except Exception as e:
            self.logger.warning(f"LLM KB intent analysis failed: {e}")
            return self._keyword_based_kb_analysis(user_message)

    async def _route_kb_with_llm_analysis_with_context(
        self,
        intent_analysis: Dict[str, Any],
        user_message: str,
        context: ExecutionContext,
        llm_context: Dict[str, Any],
    ) -> str | tuple[Any, dict]:
        """Route KB request based on LLM intent analysis - FIXED: With context preservation"""

        primary_intent = intent_analysis.get("primary_intent", "help_request")
        kb_name = intent_analysis.get("kb_name")
        documents = intent_analysis.get("document_references", [])
        query_content = intent_analysis.get("query_content")
        uses_context = intent_analysis.get("uses_context_reference", False)
        operation_details = intent_analysis.get("operation_details", {})

        # Resolve context references if needed
        if uses_context:
            kb_name = kb_name or self.get_current_knowledge_base()
            if not documents:
                recent_doc = self.get_recent_document()
                if recent_doc:
                    documents = [recent_doc]

        # Route based on intent
        if primary_intent == "help_request":
            return await self._handle_kb_help_request_with_context(user_message, llm_context)
        elif primary_intent == "ingest_document":
            return await self._handle_document_ingestion(
                kb_name, documents, operation_details, user_message
            )
        elif primary_intent == "ingest_text":
            return await self._handle_text_ingestion(kb_name, user_message, operation_details)
        elif primary_intent == "query_kb":
            return await self._handle_kb_query(kb_name, query_content, operation_details)
        elif primary_intent == "create_kb":
            return await self._handle_kb_creation(kb_name, user_message)
        elif primary_intent == "manage_kb":
            return await self._handle_kb_management(kb_name, user_message)
        else:
            return await self._handle_kb_help_request_with_context(user_message, llm_context)

    async def _handle_kb_help_request_with_context(
        self, user_message: str, llm_context: Dict[str, Any]
    ) -> str:
        """Handle KB help requests with conversation context - FIXED: Context preserved"""

        # Use LLM for more intelligent help if available
        if self.llm_service and llm_context.get("conversation_history"):
            help_prompt = f"""As a knowledge base assistant, provide helpful guidance for: {user_message}

    Consider the user's previous KB operations and provide contextual assistance."""

            try:
                # FIX: Use LLM with conversation context
                intelligent_help = await self.llm_service.generate_response(
                    prompt=help_prompt, context=llm_context # KEY: Context preserves memory
                )
                return intelligent_help
            except Exception as e:
                self.logger.warning(f"LLM help generation failed: {e}")

        # Fallback to standard help message
        state = self.get_conversation_state()

        response = (
            "I'm your Knowledge Base Agent! I can help you with:\n\n"
            " **Document Management**\n"
            "- Ingest PDFs, DOCX, TXT, MD files\n"
            "- Process web content from URLs\n"
            "- Add text content directly\n\n"
            " **Intelligent Search**\n"
            "- Natural language queries\n"
            "- Semantic similarity search\n"
            "- Source attribution\n\n"
            " **Smart Context Features**\n"
            "- Remembers knowledge bases from conversation\n"
            "- Understands 'that KB' and 'this document'\n"
            "- Maintains working context\n\n"
        )

        # Add current context information
        if state.knowledge_bases:
            response += f" **Your Knowledge Bases:**\n"
            for kb in state.knowledge_bases[-3:]: # Show last 3
                response += f" • {kb}\n"

        if state.working_files:
            response += f"\n **Recent Documents:** {len(state.working_files)} files\n"

        response += "\n **Examples:**\n"
        response += "• 'Ingest research.pdf into ai_papers'\n"
        response += "• 'Query ai_papers: What are the main findings?'\n"
        response += "• 'Add this text to the knowledge base: [content]'\n"
        response += "\nI understand context from our conversation! "

        return response

    async def process_message_stream(
        self, message: Union[str, AgentMessage], context: ExecutionContext = None
    ) -> AsyncIterator[StreamChunk]:
        """Stream processing for Knowledge Base operations - FIXED: Context preserved across provider switches"""
        # Handle both string and AgentMessage inputs
        if isinstance(message, AgentMessage):
            user_message = message.content
            original_message = message
        else:
            user_message = str(message)
            original_message = AgentMessage(
                id=str(uuid.uuid4()),
                sender_id=context.user_id if context else self.context.user_id,
                recipient_id=self.agent_id,
                content=user_message,
                message_type=MessageType.USER_INPUT,
                timestamp=datetime.now(),
            )

        self.memory.store_message(original_message)

        try:
            self.update_conversation_state(user_message)

            yield StreamChunk(
                text="**Knowledge Base Assistant**\n\n",
                sub_type=StreamSubType.STATUS,
                metadata={"agent": "knowledge_base", "phase": "initialization"},
            )

            # FIX: Get conversation context for streaming
            conversation_context = self._get_kb_conversation_context_summary()

            llm_context_from_routing = original_message.metadata.get("llm_context", {})
            conversation_history_from_routing = llm_context_from_routing.get(
                "conversation_history", []
            )

            if conversation_history_from_routing:
                conversation_history = conversation_history_from_routing
            else:
                conversation_history = await self.get_conversation_history(
                    limit=5, include_metadata=True
                )

            yield StreamChunk(
                text="Analyzing knowledge base request...\n",
                sub_type=StreamSubType.STATUS,
                metadata={"phase": "analysis"},
            )

            # FIX: Build LLM context for streaming
            llm_context = {
                "conversation_history": conversation_history, # KEY FIX
                "conversation_id": original_message.conversation_id,
                "streaming": True,
                "agent_type": "knowledge_base", # media_editor, web_scraper, etc.
                "routed_from_moderator": bool(llm_context_from_routing),
            }

            intent_analysis = await self._llm_analyze_kb_intent(user_message, conversation_context)

            primary_intent = intent_analysis.get("primary_intent", "help_request")
            kb_name = intent_analysis.get("kb_name")
            documents = intent_analysis.get("document_references", [])

            # Route based on intent with streaming
            if primary_intent == "ingest_document":
                yield StreamChunk(
                    text="**Document Ingestion**\n\n",
                    sub_type=StreamSubType.STATUS,
                    metadata={"intent": "ingest_document"},
                )
                if not kb_name:
                    yield StreamChunk(
                        text="Determining knowledge base...\n",
                        sub_type=StreamSubType.STATUS,
                        metadata={"phase": "determining_kb"},
                    )
                if not documents:
                    yield StreamChunk(
                        text="Identifying documents...\n",
                        sub_type=StreamSubType.STATUS,
                        metadata={"phase": "identifying_docs"},
                    )

                async for chunk in self._stream_document_ingestion_with_context(
                    kb_name, documents, user_message, llm_context
                ):
                    yield chunk

            elif primary_intent == "ingest_text":
                yield StreamChunk(
                    text="**Text Ingestion**\n\n",
                    sub_type=StreamSubType.STATUS,
                    metadata={"intent": "ingest_text"},
                )
                async for chunk in self._stream_text_ingestion_with_context(
                    kb_name, user_message, llm_context
                ):
                    yield chunk

            elif primary_intent == "query_kb":
                yield StreamChunk(
                    text="**Knowledge Base Query**\n\n",
                    sub_type=StreamSubType.STATUS,
                    metadata={"intent": "query_kb"},
                )
                async for chunk in self._stream_kb_query_with_context(
                    kb_name, intent_analysis.get("query_content"), user_message, llm_context
                ):
                    yield chunk

            else:
                # Stream help or other responses with context
                if self.llm_service:
                    help_prompt = f"As a knowledge base assistant, help with: {user_message}"
                    enhanced_system_message = self.get_system_message_for_llm(llm_context)
                    # Stream with conversation context
                    async for chunk in self.llm_service.generate_response_stream(
                        help_prompt, context=llm_context, system_message=enhanced_system_message
                    ):
                        yield chunk
                else:
                    response_content = await self._route_kb_with_llm_analysis(
                        intent_analysis, user_message, context
                    )
                    yield StreamChunk(
                        text=response_content,
                        sub_type=StreamSubType.CONTENT,
                        metadata={"intent": "general_response"},
                    )

        except Exception as e:
            yield StreamChunk(
                text=f"**Knowledge Base Error:** {str(e)}",
                sub_type=StreamSubType.ERROR,
                metadata={"error": str(e)},
            )

    async def _stream_document_ingestion_with_context(
        self, kb_name: str, documents: list, user_message: str, llm_context: Dict[str, Any]
    ) -> AsyncIterator[str]:
        """Stream document ingestion with context preservation"""
        try:
            if not kb_name or not documents:
                # Resolve missing parameters with streaming feedback
                if not kb_name:
                    yield "No knowledge base specified. "
                    if self.llm_service:
                        # FIX: Use context-aware LLM for help
                        async for chunk in self.llm_service.generate_response_stream(
                            f"User wants to ingest documents but didn't specify KB. Help them: {user_message}",
                            context=llm_context, # KEY: Context preserves memory
                        ):
                            yield chunk
                    return

            document_path = documents[0]
            yield f"**Processing:** {document_path}\n"
            yield f"**Target KB:** {kb_name}\n\n"

            yield "Starting ingestion process...\n"

            # Simulate progress updates during ingestion
            start_time = time.time()

            # Call the actual ingestion method
            result = await self._ingest_document(kb_name, document_path)

            processing_time = time.time() - start_time

            if result["success"]:
                yield f"**Ingestion Completed Successfully!**\n\n"
                yield f"**Summary:**\n"
                yield f"Document: {document_path}\n"
                yield f"Knowledge Base: {kb_name}\n"
                yield f"Processing Time: {processing_time:.2f}s\n"
                yield f"Status: Ready for queries! \n"
            else:
                yield f"**Ingestion Failed:** {result['error']}\n"

        except Exception as e:
            yield f"**Error during document ingestion:** {str(e)}"

    async def _stream_text_ingestion_with_context(
        self, kb_name: str, user_message: str, llm_context: Dict[str, Any]
    ) -> AsyncIterator[str]:
        """Stream text ingestion with context preservation"""
        try:
            if not kb_name:
                yield " Please specify which knowledge base to use.\n"
                return

            # Extract text content
            text_content = self._extract_text_for_ingestion(user_message)

            if not text_content:
                yield f" Ready to add text to **{kb_name}**. What text would you like me to ingest?\n"
                return

            yield f"**Processing text for {kb_name}**\n"
            yield f"**Text length:** {len(text_content)} characters\n\n"

            yield "Processing and indexing text...\n"

            result = await self._ingest_text(kb_name, text_content)

            if result["success"]:
                preview = text_content[:100] + "..." if len(text_content) > 100 else text_content
                yield f"**Text Ingestion Completed**\n\n"
                yield f"**Preview:** {preview}\n"
                yield f"**Knowledge Base:** {kb_name}\n"
                yield f"**Length:** {len(text_content)} characters\n"
                yield f"**Status:** Text successfully indexed!\n"
            else:
                yield f" **Text ingestion failed:** {result['error']}\n"

        except Exception as e:
            yield f" **Error during text ingestion:** {str(e)}"

    async def _stream_kb_query_with_context(
        self, kb_name: str, query_content: str, user_message: str, llm_context: Dict[str, Any]
    ) -> AsyncIterator[str]:
        """Stream knowledge base queries with context preservation"""
        try:
            if not kb_name:
                yield " **Knowledge Base Query**\n\n"
                available_kbs = self.conversation_state.knowledge_bases
                if available_kbs:
                    yield "**Available Knowledge Bases:**\n"
                    for kb in available_kbs:
                        yield f"{kb}\n"
                    yield f"\nWhich knowledge base would you like to search?\n"
                else:
                    yield "No knowledge bases found. Please create one first.\n"
                return

            if not query_content:
                yield f" **Searching {kb_name}**\n\nWhat would you like me to find?\n"
                return

            yield f"**Searching Knowledge Base:** {kb_name}\n"
            yield f"**Query:** {query_content}\n\n"

            yield "Performing semantic search...\n"

            # Perform the actual query
            result = await self._query_knowledge_base(kb_name, query_content)

            if result["success"]:
                answer = result["answer"]
                source_count = len(result.get("source_details", []))

                yield f"**Search Results:**\n\n"

                # Stream the answer progressively if it's long
                if len(answer) > 200:
                    words = answer.split()
                    chunk_size = 20
                    for i in range(0, len(words), chunk_size):
                        chunk = " ".join(words[i : i + chunk_size])
                        yield f"{chunk} "
                        await asyncio.sleep(0.05) # Small delay for streaming effect
                else:
                    yield answer

                # yield f"\n\n **Sources:** {source_count} relevant documents found\n"
                # yield f" **Query completed successfully!**\n"
                yield f"\n"
            else:
                yield f" **Query failed:** {result['error']}\n"

        except Exception as e:
            yield f" **Error during query:** {str(e)}"

    def _get_kb_conversation_context_summary(self) -> str:
        """Get KB conversation context summary"""
        try:
            recent_history = self.get_conversation_history_with_context(
                limit=3, context_types=[ContextType.KNOWLEDGE_BASE, ContextType.DOCUMENT_NAME]
            )

            context_summary = []
            for msg in recent_history:
                if msg.get("message_type") == "user_input":
                    extracted_context = msg.get("extracted_context", {})
                    kb_names = extracted_context.get("knowledge_base", [])
                    docs = extracted_context.get("document_name", [])

                    if kb_names:
                        context_summary.append(f"Previous KB: {kb_names[0]}")
                    if docs:
                        context_summary.append(f"Previous document: {docs[0]}")

            # Add current state
            current_kb = self.get_current_knowledge_base()
            if current_kb:
                context_summary.append(f"Current KB: {current_kb}")

            return "\n".join(context_summary) if context_summary else "No previous KB context"
        except Exception as e:
            self.logger.warning(f"Failed to get KB context: {e}")
            return "No previous KB context"

    async def _route_kb_with_llm_analysis(
        self, intent_analysis: Dict[str, Any], user_message: str, context: ExecutionContext
    ) -> str | tuple[Any, dict]:
        """Route KB request based on LLM intent analysis"""

        primary_intent = intent_analysis.get("primary_intent", "help_request")
        kb_name = intent_analysis.get("kb_name")
        documents = intent_analysis.get("document_references", [])
        query_content = intent_analysis.get("query_content")
        uses_context = intent_analysis.get("uses_context_reference", False)
        operation_details = intent_analysis.get("operation_details", {})

        # Resolve context references if needed
        if uses_context:
            kb_name = kb_name or self.get_current_knowledge_base()
            if not documents:
                recent_doc = self.get_recent_document()
                if recent_doc:
                    documents = [recent_doc]

        # Route based on intent
        if primary_intent == "help_request":
            return await self._handle_kb_help_request(user_message)
        elif primary_intent == "ingest_document":
            return await self._handle_document_ingestion(
                kb_name, documents, operation_details, user_message
            )
        elif primary_intent == "ingest_text":
            return await self._handle_text_ingestion(kb_name, user_message, operation_details)
        elif primary_intent == "query_kb":
            return await self._handle_kb_query(kb_name, query_content, operation_details)
        elif primary_intent == "create_kb":
            return await self._handle_kb_creation(kb_name, user_message)
        elif primary_intent == "manage_kb":
            return await self._handle_kb_management(kb_name, user_message)
        else:
            return await self._handle_kb_help_request(user_message)

    async def _handle_document_ingestion(
        self,
        kb_name: str,
        documents: List[str],
        operation_details: Dict[str, Any],
        user_message: str,
    ) -> str:
        """Handle document ingestion with LLM analysis"""

        # Resolve missing parameters
        if not kb_name:
            available_kbs = self.conversation_state.knowledge_bases
            if available_kbs:
                return (
                    f"I can ingest documents! Which knowledge base?\n\n"
                    f"**Available KBs:**\n"
                    + "\n".join([f"• {kb}" for kb in available_kbs])
                    + f"\n\nOr specify a new KB name."
                )
            else:
                return (
                    "I can ingest documents into knowledge bases. Please specify:\n\n"
                    "1. **Knowledge base name** (I'll create it if it doesn't exist)\n"
                    "2. **Document path** or just tell me which document\n\n"
                    "Example: 'Ingest research.pdf into ai_papers'"
                )

        if not documents:
            return (
                f"I'll ingest into the **{kb_name}** knowledge base. Which document would you like to add?\n\n"
                f"Please provide the document path or tell me the filename."
            )

        # Perform ingestion
        document_path = documents[0]

        try:
            # Check if it's a URL or file path
            if document_path.startswith("http"):
                result = await self._ingest_web_content(kb_name, document_path)
                operation_type = "Web content"
            else:
                result = await self._ingest_document(kb_name, document_path)
                operation_type = "Document"

            if result["success"]:
                return (
                    f" **{operation_type} Ingestion Completed**\n\n"
                    f" **Source:** {document_path}\n"
                    f" **Knowledge Base:** {kb_name}\n"
                    f"**Status:** Successfully processed and indexed\n\n"
                    f"You can now query this knowledge base! "
                )
            else:
                return f" **Ingestion failed:** {result['error']}"

        except Exception as e:
            return f" **Error during ingestion:** {str(e)}"

    async def _handle_text_ingestion(
        self, kb_name: str, user_message: str, operation_details: Dict[str, Any]
    ) -> str:
        """Handle text ingestion with LLM analysis"""

        if not kb_name:
            return "I can ingest text into knowledge bases. Please specify which knowledge base to use."

        # Extract text content from message (after removing command parts)
        text_content = self._extract_text_for_ingestion(user_message)

        if not text_content:
            return f"I'll add text to the **{kb_name}** knowledge base. What text would you like me to ingest?"

        try:
            result = await self._ingest_text(kb_name, text_content)

            if result["success"]:
                preview = text_content[:100] + "..." if len(text_content) > 100 else text_content
                return (
                    f" **Text Ingestion Completed**\n\n"
                    f" **Text Preview:** {preview}\n"
                    f" **Knowledge Base:** {kb_name}\n"
                    f" **Length:** {len(text_content)} characters\n\n"
                    f"Text successfully indexed! "
                )
            else:
                return f" **Text ingestion failed:** {result['error']}"

        except Exception as e:
            return f" **Error during text ingestion:** {str(e)}"

    async def _handle_kb_query(
        self, kb_name: str, query_content: str, operation_details: Dict[str, Any]
    ) -> str | tuple[Any, dict]:
        """Handle KB queries with single or multiple knowledge bases.
        - If operation_details.kb_names provided with one KB, query it directly.
        - If multiple KBs provided, score/select candidates and consolidate results.
        - Keep answer crisp; attribution, topics, and intent go in metadata only.
        """

        op = operation_details or {}
        provided_kbs = (
            self._normalize_kb_names_input(op.get("kb_names")) if op.get("kb_names") else []
        )
        topics = op.get("topics") or []
        inferred_intent = op.get("primary_intent_inferred")

        # If multiple KBs provided, select and query across them
        if provided_kbs and len(provided_kbs) > 1:
            if not query_content:
                return "What question would you like to ask across the provided knowledge bases?"
            # Score and select top candidates (top 2 by score; fallback to first 2)
            scored = [
                (kb, self._score_kb_for_query(kb, query_content or "", topics))
                for kb in provided_kbs
            ]
            scored.sort(key=lambda x: x[1], reverse=True)
            top = [kb for kb, sc in scored if sc > 0][:2]
            if not top:
                top = provided_kbs[:2]
            answer, metadata = await self._multi_kb_query_and_consolidate(
                top, query_content, question_type=op.get("query_type", "free-text")
            )
            # add intent/topics to metadata
            metadata.update(
                {
                    "intent_topics": {
                        "primary_intent": inferred_intent,
                        "topics": topics,
                    }
                }
            )
            return answer, metadata

        # If exactly one KB provided, use it directly
        if provided_kbs and len(provided_kbs) == 1:
            target_kb = provided_kbs[0].get("kb_name")
            if not query_content:
                return f"I'll search the **{target_kb}** knowledge base. What would you like me to find?"
            try:
                query_type = op.get("query_type", "free-text")
                result = await self._query_knowledge_base(
                    target_kb, query_content, question_type=query_type
                )
                if result.get("success"):
                    metadata = {
                        "used_kbs": [
                            {
                                "kb_name": target_kb,
                                "description": provided_kbs[0].get("description"),
                            }
                        ],
                        "primary_kb": target_kb,
                        "sources_dict": result.get("source_details", {}),
                        "intent_topics": {
                            "primary_intent": inferred_intent,
                            "topics": topics,
                        },
                    }
                    return result.get("answer"), metadata
                else:
                    return f" **Query failed:** {result['error']}"
            except Exception as e:
                return f" **Error during query:** {str(e)}"

        # No provided_kbs: use existing single-KB behavior with enriched metadata
        # Resolve missing parameters
        if not kb_name:
            available_kbs = self.conversation_state.knowledge_bases
            if available_kbs:
                return (
                    f"I can query knowledge bases! Which one?\n\n"
                    f"**Available KBs from our conversation:**\n"
                    + "\n".join([f"• {kb}" for kb in available_kbs])
                    + f"\n\nExample: 'Query {available_kbs[0]}: {query_content or 'your question'}'"
                )
            else:
                return (
                    "I can query knowledge bases, but I need to know which one to search.\n\n"
                    "Please specify: `Query [kb_name]: [your question]`"
                )

        if not query_content:
            return f"I'll search the **{kb_name}** knowledge base. What would you like me to find?"

        try:
            query_type = op.get("query_type", "free-text")
            result = await self._query_knowledge_base(
                kb_name, query_content, question_type=query_type
            )
            if result.get("success"):
                metadata = {
                    "used_kbs": [{"kb_name": kb_name}],
                    "primary_kb": kb_name,
                    "sources_dict": result.get("source_details", {}),
                    "intent_topics": {
                        "primary_intent": inferred_intent,
                        "topics": topics,
                    },
                }
                return result.get("answer"), metadata
            else:
                return f" **Query failed:** {result['error']}"

        except Exception as e:
            return f" **Error during query:** {str(e)}"

    async def _handle_kb_creation(self, kb_name: str, user_message: str) -> str:
        """Handle KB creation requests"""

        if not kb_name:
            return (
                "I can create knowledge bases! What would you like to name the new knowledge base?\n\n"
                "Example: 'Create a knowledge base called research_papers'"
            )

        # KB creation is implicit when first document is ingested
        return (
            f"Great! I'll create the **{kb_name}** knowledge base when you add the first document.\n\n"
            f"To get started:\n"
            f"• `Ingest document.pdf into {kb_name}`\n"
            f"• `Add text to {kb_name}: [your text content]`\n"
            f"• `Ingest https://example.com into {kb_name}`"
        )

    async def _handle_kb_management(self, kb_name: str, user_message: str) -> str:
        """Handle KB management requests"""

        available_kbs = self.conversation_state.knowledge_bases

        if not available_kbs:
            return "No knowledge bases found in our conversation. Create one by ingesting your first document!"

        response = f" **Knowledge Base Management**\n\n"
        response += f"**Available Knowledge Bases:**\n"
        for kb in available_kbs:
            response += f"• {kb}\n"

        response += f"\n**Management Options:**\n"
        response += f"• Query: `Query {available_kbs[0]}: your question`\n"
        response += f"• Add docs: `Ingest file.pdf into {available_kbs[0]}`\n"
        response += f"• Add text: `Add text to {available_kbs[0]}: content`\n"

        return response

    async def _handle_kb_help_request(self, user_message: str) -> str:
        """Handle KB help requests with conversation context"""

        state = self.get_conversation_state()

        response = (
            "I'm your Knowledge Base Agent! I can help you with:\n\n"
            " **Document Management**\n"
            "- Ingest PDFs, DOCX, TXT, MD files\n"
            "- Process web content from URLs\n"
            "- Add text content directly\n\n"
            " **Intelligent Search**\n"
            "- Natural language queries\n"
            "- Semantic similarity search\n"
            "- Source attribution\n\n"
            " **Smart Context Features**\n"
            "- Remembers knowledge bases from conversation\n"
            "- Understands 'that KB' and 'this document'\n"
            "- Maintains working context\n\n"
        )

        # Add current context information
        if state.knowledge_bases:
            response += f" **Your Knowledge Bases:**\n"
            for kb in state.knowledge_bases[-3:]: # Show last 3
                response += f" • {kb}\n"

        if state.working_files:
            response += f"\n **Recent Documents:** {len(state.working_files)} files\n"

        response += "\n **Examples:**\n"
        response += "• 'Ingest research.pdf into ai_papers'\n"
        response += "• 'Query ai_papers: What are the main findings?'\n"
        response += "• 'Add this text to the knowledge base: [content]'\n"
        response += "\nI understand context from our conversation! "

        return response

    def _extract_query_from_kb_message(self, message: str) -> str:
        """Extract query content from KB message"""
        # Look for colon pattern first
        import re

        colon_match = re.search(r":\s*(.+)", message)
        if colon_match:
            return colon_match.group(1).strip()

        # Remove KB operation keywords
        query_keywords = ["query", "search", "find", "ask", "what", "how", "where", "when", "why"]
        words = message.split()
        filtered_words = []

        for word in words:
            if word.lower() not in query_keywords and not word.lower().endswith("_kb"):
                filtered_words.append(word)

        return " ".join(filtered_words).strip()

    def _extract_text_for_ingestion(self, message: str) -> str:
        """Extract text content for ingestion from message"""
        # Look for colon pattern
        import re

        colon_match = re.search(r":\s*(.+)", message)
        if colon_match:
            return colon_match.group(1).strip()

        # Remove ingestion keywords
        ingest_keywords = ["ingest", "add", "upload", "text", "into", "to"]
        words = message.split()
        filtered_words = []
        skip_next = False

        for word in words:
            if skip_next:
                skip_next = False
                continue

            if word.lower() in ingest_keywords:
                continue
            elif word.lower().endswith("_kb") or word.lower().endswith("_base"):
                continue
            else:
                filtered_words.append(word)

        return " ".join(filtered_words).strip()

    def _extract_kb_intent_from_llm_response(
        self, llm_response: str, user_message: str
    ) -> Dict[str, Any]:
        """Extract KB intent from non-JSON LLM response"""
        content_lower = llm_response.lower()

        if "ingest" in content_lower or "upload" in content_lower:
            intent = "ingest_document"
        elif "query" in content_lower or "search" in content_lower:
            intent = "query_kb"
        elif "create" in content_lower:
            intent = "create_kb"
        else:
            intent = "help_request"

        # Simple topics from user_message as fallback
        stop = {
            "the",
            "and",
            "for",
            "with",
            "this",
            "that",
            "into",
            "what",
            "how",
            "where",
            "why",
            "when",
            "from",
            "about",
            "please",
            "can",
            "you",
            "me",
            "to",
            "in",
            "on",
            "of",
            "a",
            "an",
            "is",
            "are",
        }
        topics = [w.strip(".,:;!?()[]{}\"'") for w in user_message.lower().split()]
        topics = [w for w in topics if len(w) > 3 and w not in stop]
        topics = list(dict.fromkeys(topics))[:10]

        return {
            "primary_intent": intent,
            "kb_name": None,
            "document_references": [],
            "query_content": None,
            "uses_context_reference": False,
            "context_type": "none",
            "operation_details": {"query_type": "free-text"},
            "topics": topics,
            "confidence": 0.6,
        }

    # --- Helper methods for multi-KB routing and consolidation ---
    def _normalize_kb_names_input(self, kb_names_input: Any) -> List[Dict[str, Optional[str]]]:
        """Normalize kb_names input to a list of dicts with kb_name and optional description.
        Accepts list of strings, list of dicts, or JSON string."""
        normalized: List[Dict[str, Optional[str]]] = []
        try:
            data = kb_names_input
            if isinstance(kb_names_input, str):
                try:
                    data = json.loads(kb_names_input)
                except Exception:
                    # single name string
                    data = [kb_names_input]
            if isinstance(data, dict):
                data = [data]
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, str):
                        normalized.append({"kb_name": item, "description": None})
                    elif isinstance(item, dict):
                        name = item.get("kb_name") or item.get("name") or item.get("id")
                        desc = item.get("description")
                        if name:
                            normalized.append({"kb_name": name, "description": desc})
            # de-duplicate by kb_name preserving order
            seen = set()
            deduped = []
            for entry in normalized:
                n = entry.get("kb_name")
                if n and n not in seen:
                    seen.add(n)
                    deduped.append(entry)
            return deduped
        except Exception:
            return []

    def _score_kb_for_query(
        self, kb_entry: Dict[str, Any], user_message: str, topics: List[str]
    ) -> float:
        """Score a KB using keyword overlap between topics/user_message and kb name/description."""
        name = (kb_entry.get("kb_name") or "").lower()
        desc = (kb_entry.get("description") or "").lower()
        haystack = f"{name} {desc}"
        # Build candidate keywords
        stop = {
            "the",
            "and",
            "for",
            "with",
            "this",
            "that",
            "into",
            "what",
            "how",
            "where",
            "why",
            "when",
            "from",
            "about",
            "please",
            "can",
            "you",
            "me",
            "to",
            "in",
            "on",
            "of",
            "a",
            "an",
            "is",
            "are",
        }
        msg_tokens = [w.strip(".,:;!?()[]{}\"'") for w in user_message.lower().split()]
        msg_tokens = [w for w in msg_tokens if len(w) > 3 and w not in stop]
        keywords = set(topics or []) | set(msg_tokens)
        score = 0.0
        for kw in keywords:
            if not kw:
                continue
            if kw in haystack:
                score += 1.0
        # bonus if description mentions domain-like hints
        if "legal" in haystack and any(
            kw in {"law", "legal", "contract", "policy", "regulation"} for kw in keywords
        ):
            score += 1.5
        if "finance" in haystack and any(
            kw in {"finance", "budget", "revenue", "cost", "profit"} for kw in keywords
        ):
            score += 1.0
        return score

    async def _multi_kb_query_and_consolidate(
        self, selected_kbs: List[Dict[str, Any]], query: str, question_type: str = "free-text"
    ) -> tuple[str, Dict[str, Any]]:
        """Query multiple KBs and consolidate result. Returns (answer, metadata)."""
        per_kb_results: Dict[str, Any] = {}
        sources_dict: Dict[str, Any] = {}
        best_answer = None
        best_kb = None
        best_source_count = -1
        for kb in selected_kbs:
            name = kb["kb_name"]
            result = await self._query_knowledge_base(name, query, question_type=question_type)
            per_kb_results[name] = result
            if result.get("success"):
                srcs = result.get("source_details", [])
                sources_dict[name] = srcs
                src_count = len(srcs)
                if src_count > best_source_count:
                    best_source_count = src_count
                    best_answer = result.get("answer")
                    best_kb = name
        # Fallback: if no success, return error string
        if best_answer is None:
            return (
                "No relevant information found in the provided knowledge bases.",
                {
                    "used_kbs": [
                        {"kb_name": kb["kb_name"], "description": kb.get("description")}
                        for kb in selected_kbs
                    ],
                    "sources_dict": sources_dict,
                },
            )
        metadata = {
            "used_kbs": [
                {"kb_name": kb["kb_name"], "description": kb.get("description")}
                for kb in selected_kbs
            ],
            "primary_kb": best_kb,
            "sources_dict": sources_dict,
        }
        return best_answer, metadata

    # Tool implementations
    def _add_knowledge_base_tools(self):
        """Add all knowledge base related tools"""

        # Document ingestion tool
        self.add_tool(
            AgentTool(
                name="ingest_document",
                description="Ingest a document into the knowledge base",
                function=self._ingest_document,
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "kb_name": {"type": "string", "description": "Knowledge base name"},
                        "doc_path": {"type": "string", "description": "Path to document file"},
                        "custom_meta": {
                            "type": "object",
                            "description": "Custom metadata for the document",
                        },
                    },
                    "required": ["kb_name", "doc_path"],
                },
            )
        )

        # Text ingestion tool
        self.add_tool(
            AgentTool(
                name="ingest_text",
                description="Ingest a Text string into the knowledge base",
                function=self._ingest_text,
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "kb_name": {"type": "string", "description": "Knowledge base name"},
                        "input_text": {"type": "string", "description": "Text to Ingest"},
                        "custom_meta": {
                            "type": "object",
                            "description": "Custom metadata for the text",
                        },
                    },
                    "required": ["kb_name", "input_text"],
                },
            )
        )

        # Knowledge base query tool
        self.add_tool(
            AgentTool(
                name="query_knowledge_base",
                description="Query the knowledge base for information",
                function=self._query_knowledge_base,
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "kb_name": {"type": "string", "description": "Knowledge base name"},
                        "query": {"type": "string", "description": "Query string"},
                        "question_type": {
                            "type": "string",
                            "enum": ["free-text", "multi-select", "single-select", "yes-no"],
                            "default": "free-text",
                        },
                        "option_list": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Options for multi/single select questions",
                        },
                        "additional_prompt": {
                            "type": "string",
                            "description": "Additional prompt context",
                        },
                    },
                    "required": ["kb_name", "query"],
                },
            )
        )

        # Web content ingestion tool
        self.add_tool(
            AgentTool(
                name="ingest_web_content",
                description="Ingest content from web URLs",
                function=self._ingest_web_content,
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "kb_name": {"type": "string", "description": "Knowledge base name"},
                        "url": {"type": "string", "description": "URL to ingest"},
                        "custom_meta": {"type": "object", "description": "Custom metadata"},
                    },
                    "required": ["kb_name", "url"],
                },
            )
        )

        # API call tool
        self.add_tool(
            AgentTool(
                name="call_api",
                description="Make API calls to external services",
                function=self._call_api,
                parameters_schema={
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "API endpoint URL"},
                        "method": {
                            "type": "string",
                            "enum": ["GET", "POST", "PUT", "DELETE"],
                            "default": "GET",
                        },
                        "headers": {"type": "object", "description": "Request headers"},
                        "payload": {
                            "type": "object",
                            "description": "Request payload for POST/PUT",
                        },
                        "timeout": {"type": "number", "default": 30},
                    },
                    "required": ["url"],
                },
            )
        )

    def _resolve_file_path(self, filename: str) -> Optional[Path]:
        """Resolve file path using universal file resolution"""
        return resolve_agent_file_path(filename, agent_type="code")

    async def _ingest_document(
        self, kb_name: str, doc_path: str, custom_meta: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Ingest a document into the knowledge base"""
        try:
            # Try to resolve the file path using docker_shared structure
            resolved_path = self._resolve_file_path(doc_path)
            if not resolved_path or not resolved_path.exists():
                return {"success": False, "error": f"File not found: {doc_path}"}

            # Use the resolved path
            doc_path = str(resolved_path)

            # Add metadata
            if not custom_meta:
                custom_meta = {}

            custom_meta.update(
                {"ingestion_time": time.time(), "agent_id": self.agent_id, "file_path": doc_path}
            )

            # Use existing persist_embeddings method
            result = self.qdrant_service.persist_embeddings(
                kb_name=kb_name, doc_path=doc_path, custom_meta=custom_meta
            )

            if result == 1:
                return {
                    "success": True,
                    "message": f"Document {doc_path} successfully ingested into {kb_name}",
                    "kb_name": kb_name,
                    "file_path": doc_path,
                }
            else:
                return {"success": False, "error": f"Failed to ingest document {doc_path}"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _ingest_text(
        self, kb_name: str, input_text: str, custom_meta: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Ingest text into the knowledge base"""
        try:
            # Add metadata
            if not custom_meta:
                custom_meta = {}

            custom_meta.update(
                {
                    "ingestion_time": time.time(),
                    "agent_id": self.agent_id,
                }
            )

            document_list = self.qdrant_service.documents_from_text(input_text)

            # Use existing persist_embeddings method
            result = self.qdrant_service.persist_embeddings(
                kb_name=kb_name, doc_path=None, documents=document_list, custom_meta=custom_meta
            )

            if result == 1:
                return {
                    "success": True,
                    "message": f"Text successfully ingested into {kb_name}",
                    "kb_name": kb_name,
                }
            else:
                return {"success": False, "error": f"Failed to ingest text"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def get_answer(self, kb_name: str, query: str, question_type: str = "free-text"):
        """Get answer from knowledge base"""
        try:
            # Use existing conduct_query method
            answer, ans_dict_list = self.qdrant_service.conduct_query(
                query=query, kb_name=kb_name, question_type=question_type
            )

            return {
                "success": True,
                "answer": answer,
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _query_knowledge_base(
        self,
        kb_name: str,
        query: str,
        question_type: str = "free-text",
        option_list: List[str] = None,
        additional_prompt: str = None,
    ) -> Dict[str, Any]:
        """Query the knowledge base"""
        try:
            # Use existing conduct_query method
            answer, ans_dict_list = self.qdrant_service.conduct_query(
                query=query,
                kb_name=kb_name,
                additional_prompt=additional_prompt,
                question_type=question_type,
                option_list=option_list,
            )

            return {
                "success": True,
                "answer": answer,
                "source_details": ans_dict_list,
                "kb_name": kb_name,
                "query": query,
                "question_type": question_type,
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _ingest_web_content(
        self, kb_name: str, url: str, custom_meta: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Ingest content from web URLs"""
        try:
            # Fetch web content
            response = requests.get(url, timeout=30)
            response.raise_for_status()

            # Create temporary file with content
            with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as tmp_file:
                tmp_file.write(response.text)
                tmp_path = tmp_file.name

            # Add URL to metadata
            if not custom_meta:
                custom_meta = {}

            custom_meta.update(
                {
                    "source_url": url,
                    "fetch_time": time.time(),
                    "content_type": response.headers.get("content-type", "unknown"),
                }
            )

            # Ingest the content
            result = await self._ingest_document(kb_name, tmp_path, custom_meta)

            # Clean up temporary file
            Path(tmp_path).unlink()

            if result["success"]:
                result["url"] = url
                result["message"] = f"Web content from {url} successfully ingested into {kb_name}"

            return result

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _call_api(
        self,
        url: str,
        method: str = "GET",
        headers: Dict[str, str] = None,
        payload: Dict[str, Any] = None,
        timeout: int = 30,
    ) -> Dict[str, Any]:
        """Make API calls to external services"""
        try:
            # Prepare request
            kwargs = {"url": url, "method": method.upper(), "timeout": timeout}

            if headers:
                kwargs["headers"] = headers

            if payload and method.upper() in ["POST", "PUT"]:
                kwargs["json"] = payload

            # Make request
            response = requests.request(**kwargs)

            # Parse response
            try:
                response_data = response.json()
            except Exception as e:
                self.logger.warning(f"Failed to parse JSON response: {e}")
                response_data = response.text

            return {
                "success": True,
                "status_code": response.status_code,
                "response_data": response_data,
                "headers": dict(response.headers),
                "url": url,
                "method": method.upper(),
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _stream_document_ingestion(
        self, kb_name: str, documents: list, user_message: str
    ) -> AsyncIterator[str]:
        """Stream document ingestion with progress updates"""
        try:
            if not kb_name or not documents:
                # Resolve missing parameters with streaming feedback
                if not kb_name:
                    yield " No knowledge base specified. "
                    if self.llm_service:
                        async for chunk in self.llm_service.generate_response_stream(
                            f"User wants to ingest documents but didn't specify KB. Help them: {user_message}"
                        ):
                            yield chunk
                    return

            document_path = documents[0]
            yield f" **Processing:** {document_path}\n"
            yield f" **Target KB:** {kb_name}\n\n"

            yield "Starting ingestion process...\n"

            # Simulate progress updates during ingestion
            start_time = time.time()

            # Call the actual ingestion method
            result = await self._ingest_document(kb_name, document_path)

            processing_time = time.time() - start_time

            if result["success"]:
                yield f" **Ingestion Completed Successfully!**\n\n"
                yield f" **Summary:**\n"
                yield f"• Document: {document_path}\n"
                yield f"• Knowledge Base: {kb_name}\n"
                yield f"• Processing Time: {processing_time:.2f}s\n"
                yield f"• Status: Ready for queries! \n"
            else:
                yield f" **Ingestion Failed:** {result['error']}\n"

        except Exception as e:
            yield f" **Error during document ingestion:** {str(e)}"

    async def _stream_text_ingestion(self, kb_name: str, user_message: str) -> AsyncIterator[str]:
        """Stream text ingestion with progress"""
        try:
            if not kb_name:
                yield " Please specify which knowledge base to use.\n"
                return

            # Extract text content
            text_content = self._extract_text_for_ingestion(user_message)

            if not text_content:
                yield f" Ready to add text to **{kb_name}**. What text would you like me to ingest?\n"
                return

            yield f" **Processing text for {kb_name}**\n"
            yield f" **Text length:** {len(text_content)} characters\n\n"

            yield "Processing and indexing text...\n"

            result = await self._ingest_text(kb_name, text_content)

            if result["success"]:
                preview = text_content[:100] + "..." if len(text_content) > 100 else text_content
                yield f" **Text Ingestion Completed**\n\n"
                yield f" **Preview:** {preview}\n"
                yield f" **Knowledge Base:** {kb_name}\n"
                yield f" **Length:** {len(text_content)} characters\n"
                yield f" **Status:** Text successfully indexed!\n"
            else:
                yield f" **Text ingestion failed:** {result['error']}\n"

        except Exception as e:
            yield f" **Error during text ingestion:** {str(e)}"

    async def _stream_kb_query(
        self, kb_name: str, query_content: str, user_message: str
    ) -> AsyncIterator[str]:
        """Stream knowledge base queries with progress and results"""
        try:
            if not kb_name:
                yield " **Knowledge Base Query**\n\n"
                available_kbs = self.conversation_state.knowledge_bases
                if available_kbs:
                    yield "**Available Knowledge Bases:**\n"
                    for kb in available_kbs:
                        yield f"• {kb}\n"
                    yield f"\nWhich knowledge base would you like to search?\n"
                else:
                    yield "No knowledge bases found. Please create one first.\n"
                return

            if not query_content:
                yield f" **Searching {kb_name}**\n\nWhat would you like me to find?\n"
                return

            yield f" **Searching Knowledge Base:** {kb_name}\n"
            yield f" **Query:** {query_content}\n\n"

            yield "Performing semantic search...\n"

            # Perform the actual query
            result = await self._query_knowledge_base(kb_name, query_content)

            if result["success"]:
                answer = result["answer"]
                source_count = len(result.get("source_details", []))

                yield f" **Search Results:**\n\n"

                # Stream the answer progressively if it's long
                if len(answer) > 200:
                    words = answer.split()
                    chunk_size = 20
                    for i in range(0, len(words), chunk_size):
                        chunk = " ".join(words[i : i + chunk_size])
                        yield f"{chunk} "
                        await asyncio.sleep(0.05) # Small delay for streaming effect
                else:
                    yield answer

                # yield f"\n\n **Sources:** {source_count} relevant documents found\n"
                # yield f" **Query completed successfully!**\n"
                yield f"\n"
            else:
                yield f" **Query failed:** {result['error']}\n"

        except Exception as e:
            yield f" **Error during query:** {str(e)}"
