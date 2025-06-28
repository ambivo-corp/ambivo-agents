# ambivo_agents/agents/knowledge_base.py
"""
Knowledge Base Agent with Qdrant integration.
"""

import asyncio
import json
import uuid
import time
import tempfile
import requests
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime


from ..core.base import BaseAgent, AgentRole, AgentMessage, MessageType, ExecutionContext, AgentTool
from ..config.loader import load_config, get_config_section


class QdrantServiceAdapter:
    """Adapter for Knowledge Base functionality using YAML configuration"""

    def __init__(self):
        # Load from YAML configuration
        config = load_config()
        kb_config = get_config_section('knowledge_base', config)

        self.qdrant_url = kb_config.get('qdrant_url')
        self.qdrant_api_key = kb_config.get('qdrant_api_key')

        if not self.qdrant_url:
            raise ValueError("qdrant_url is required in knowledge_base configuration")

        # Initialize Qdrant client
        try:
            import qdrant_client
            if self.qdrant_api_key:
                self.client = qdrant_client.QdrantClient(
                    url=self.qdrant_url,
                    api_key=self.qdrant_api_key
                )
            else:
                self.client = qdrant_client.QdrantClient(url=self.qdrant_url)

        except ImportError:
            raise ImportError("qdrant-client package required for Knowledge Base functionality")
        except Exception as e:
            raise ConnectionError(f"Failed to connect to Qdrant: {e}")

    def documents_from_text(self, input_text: str) -> list:
        """Convert text to documents format"""
        from langchain.text_splitter import RecursiveCharacterTextSplitter
        from llama_index.core.readers import Document as LIDoc

        # Load chunk settings from config
        config = load_config()
        kb_config = get_config_section('knowledge_base', config)

        chunk_size = kb_config.get('chunk_size', 1024)
        chunk_overlap = kb_config.get('chunk_overlap', 20)

        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )
        splitted_documents = text_splitter.create_documents(texts=[input_text])

        # Convert to llama-index format
        docs = [LIDoc.from_langchain_format(doc) for doc in splitted_documents]
        return docs

    def persist_embeddings(self, kb_name: str, doc_path: str = None,
                           documents=None, custom_meta: Dict[str, Any] = None) -> int:
        """Persist embeddings to Qdrant"""
        try:
            config = load_config()
            kb_config = get_config_section('knowledge_base', config)

            if not documents and doc_path:
                # Load document from file
                #from langchain_community.document_loaders import UnstructuredFileLoader
                from langchain_unstructured import UnstructuredLoader

                from llama_index.core.readers import Document as LIDoc

                #loader = UnstructuredFileLoader(doc_path)
                loader = UnstructuredLoader(doc_path)
                lang_docs = loader.load()
                documents = [LIDoc.from_langchain_format(doc) for doc in lang_docs]

            if not documents:
                return 2  # Error

            # Add custom metadata
            if custom_meta:
                for doc in documents:
                    if not hasattr(doc, 'metadata'):
                        doc.metadata = {}
                    doc.metadata.update(custom_meta)

            # Create collection name with prefix from config
            collection_prefix = kb_config.get('default_collection_prefix', 'kb')
            collection_name = f"{collection_prefix}_{kb_name}"

            # Create vector store and index
            from llama_index.core import VectorStoreIndex, StorageContext
            from llama_index.vector_stores.qdrant import QdrantVectorStore

            vector_store = QdrantVectorStore(
                client=self.client,
                collection_name=collection_name
            )

            storage_context = StorageContext.from_defaults(vector_store=vector_store)
            index = VectorStoreIndex.from_documents(documents, storage_context=storage_context)

            return 1  # Success

        except Exception as e:
            print(f"Error persisting embeddings: {e}")
            return 2  # Error

    def conduct_query(self, query: str, kb_name: str, additional_prompt: str = None,
                      question_type: str = "free-text", option_list=None) -> tuple:
        """Query the knowledge base"""
        try:
            config = load_config()
            kb_config = get_config_section('knowledge_base', config)

            collection_prefix = kb_config.get('default_collection_prefix', 'kb')
            collection_name = f"{collection_prefix}_{kb_name}"

            similarity_top_k = kb_config.get('similarity_top_k', 5)

            # Create vector store and query engine
            from llama_index.core import VectorStoreIndex
            from llama_index.vector_stores.qdrant import QdrantVectorStore
            from llama_index.core.indices.vector_store import VectorIndexRetriever
            from llama_index.core.query_engine import RetrieverQueryEngine
            from llama_index.core import get_response_synthesizer

            vector_store = QdrantVectorStore(
                client=self.client,
                collection_name=collection_name
            )

            index = VectorStoreIndex.from_vector_store(vector_store=vector_store)
            retriever = VectorIndexRetriever(similarity_top_k=similarity_top_k, index=index)
            response_synthesizer = get_response_synthesizer()
            query_engine = RetrieverQueryEngine(
                retriever=retriever,
                response_synthesizer=response_synthesizer
            )

            # Execute query
            response = query_engine.query(query)
            answer = str(response)
            source_list = []

            if hasattr(response, 'source_nodes') and response.source_nodes:
                for node in response.source_nodes:
                    source_info = {
                        "text": node.node.get_text()[:200] + "...",
                        "score": getattr(node, 'score', 0.0),
                        "metadata": getattr(node.node, 'metadata', {})
                    }
                    source_list.append(source_info)

            ans_dict_list = [{
                "answer": answer,
                "source": f"Found {len(source_list)} relevant sources",
                "source_list": source_list
            }]

            return answer, ans_dict_list

        except Exception as e:
            error_msg = f"Query error: {str(e)}"
            return error_msg, [{"answer": error_msg, "source": "", "source_list": []}]


class KnowledgeBaseAgent(BaseAgent):
    """Knowledge Base Agent that integrates with Qdrant infrastructure"""

    def __init__(self, agent_id: str|None=None, memory_manager=None, llm_service=None, **kwargs):
        if agent_id is None:
            agent_id = f"kb_{str(uuid.uuid4())[:8]}"

        super().__init__(
            agent_id=agent_id,
            role=AgentRole.RESEARCHER,
            memory_manager=memory_manager,
            llm_service=llm_service,
            name="Knowledge Base Agent",
            description="Agent for knowledge base operations, document processing, and intelligent retrieval",
            **kwargs
        )

        # Initialize Qdrant service
        try:
            self.qdrant_service = QdrantServiceAdapter()
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Knowledge Base service: {e}")

        # Add knowledge base tools
        self._add_knowledge_base_tools()

    def _add_knowledge_base_tools(self):
        """Add all knowledge base related tools"""

        # Document ingestion tool
        self.add_tool(AgentTool(
            name="ingest_document",
            description="Ingest a document into the knowledge base",
            function=self._ingest_document,
            parameters_schema={
                "type": "object",
                "properties": {
                    "kb_name": {"type": "string", "description": "Knowledge base name"},
                    "doc_path": {"type": "string", "description": "Path to document file"},
                    "custom_meta": {"type": "object", "description": "Custom metadata for the document"}
                },
                "required": ["kb_name", "doc_path"]
            }
        ))

        # Text ingestion tool
        self.add_tool(AgentTool(
            name="ingest_text",
            description="Ingest a Text string into the knowledge base",
            function=self._ingest_text,
            parameters_schema={
                "type": "object",
                "properties": {
                    "kb_name": {"type": "string", "description": "Knowledge base name"},
                    "input_text": {"type": "string", "description": "Text to Ingest"},
                    "custom_meta": {"type": "object", "description": "Custom metadata for the text"}
                },
                "required": ["kb_name", "input_text"]
            }
        ))

        # Knowledge base query tool
        self.add_tool(AgentTool(
            name="query_knowledge_base",
            description="Query the knowledge base for information",
            function=self._query_knowledge_base,
            parameters_schema={
                "type": "object",
                "properties": {
                    "kb_name": {"type": "string", "description": "Knowledge base name"},
                    "query": {"type": "string", "description": "Query string"},
                    "question_type": {"type": "string",
                                      "enum": ["free-text", "multi-select", "single-select", "yes-no"],
                                      "default": "free-text"},
                    "option_list": {"type": "array", "items": {"type": "string"},
                                    "description": "Options for multi/single select questions"},
                    "additional_prompt": {"type": "string", "description": "Additional prompt context"}
                },
                "required": ["kb_name", "query"]
            }
        ))

        # Web content ingestion tool
        self.add_tool(AgentTool(
            name="ingest_web_content",
            description="Ingest content from web URLs",
            function=self._ingest_web_content,
            parameters_schema={
                "type": "object",
                "properties": {
                    "kb_name": {"type": "string", "description": "Knowledge base name"},
                    "url": {"type": "string", "description": "URL to ingest"},
                    "custom_meta": {"type": "object", "description": "Custom metadata"}
                },
                "required": ["kb_name", "url"]
            }
        ))

        # API call tool
        self.add_tool(AgentTool(
            name="call_api",
            description="Make API calls to external services",
            function=self._call_api,
            parameters_schema={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "API endpoint URL"},
                    "method": {"type": "string", "enum": ["GET", "POST", "PUT", "DELETE"], "default": "GET"},
                    "headers": {"type": "object", "description": "Request headers"},
                    "payload": {"type": "object", "description": "Request payload for POST/PUT"},
                    "timeout": {"type": "number", "default": 30}
                },
                "required": ["url"]
            }
        ))

    async def _ingest_document(self, kb_name: str, doc_path: str, custom_meta: Dict[str, Any] = None) -> Dict[str, Any]:
        """Ingest a document into the knowledge base"""
        try:
            if not Path(doc_path).exists():
                return {"success": False, "error": f"File not found: {doc_path}"}

            # Add metadata
            if not custom_meta:
                custom_meta = {}

            custom_meta.update({
                "ingestion_time": time.time(),
                "agent_id": self.agent_id,
                "file_path": doc_path
            })

            # Use existing persist_embeddings method
            result = self.qdrant_service.persist_embeddings(
                kb_name=kb_name,
                doc_path=doc_path,
                custom_meta=custom_meta
            )

            if result == 1:
                return {
                    "success": True,
                    "message": f"Document {doc_path} successfully ingested into {kb_name}",
                    "kb_name": kb_name,
                    "file_path": doc_path
                }
            else:
                return {
                    "success": False,
                    "error": f"Failed to ingest document {doc_path}"
                }

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _ingest_text(self, kb_name: str, input_text: str, custom_meta: Dict[str, Any] = None) -> Dict[str, Any]:
        """Ingest text into the knowledge base"""
        try:
            # Add metadata
            if not custom_meta:
                custom_meta = {}

            custom_meta.update({
                "ingestion_time": time.time(),
                "agent_id": self.agent_id,
            })

            document_list = self.qdrant_service.documents_from_text(input_text)

            # Use existing persist_embeddings method
            result = self.qdrant_service.persist_embeddings(
                kb_name=kb_name,
                doc_path=None,
                documents=document_list,
                custom_meta=custom_meta
            )

            if result == 1:
                return {
                    "success": True,
                    "message": f"Text successfully ingested into {kb_name}",
                    "kb_name": kb_name,
                }
            else:
                return {
                    "success": False,
                    "error": f"Failed to ingest text"
                }

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def get_answer(self, kb_name: str, query: str, question_type: str = "free-text"):
        """Get answer from knowledge base"""
        try:
            # Use existing conduct_query method
            answer, ans_dict_list = self.qdrant_service.conduct_query(
                query=query,
                kb_name=kb_name,
                question_type=question_type
            )

            return {
                "success": True,
                "answer": answer,
                # "source_details": ans_dict_list,
                # "kb_name": kb_name,
                # "query": query,
                # "question_type": question_type
            }

        except Exception as e:
            return {"success": False, "error": str(e)}
    async def _query_knowledge_base(self, kb_name: str, query: str, question_type: str = "free-text",
                                    option_list: List[str] = None, additional_prompt: str = None) -> Dict[str, Any]:
        """Query the knowledge base"""
        try:
            # Use existing conduct_query method
            answer, ans_dict_list = self.qdrant_service.conduct_query(
                query=query,
                kb_name=kb_name,
                additional_prompt=additional_prompt,
                question_type=question_type,
                option_list=option_list
            )

            return {
                "success": True,
                "answer": answer,
                "source_details": ans_dict_list,
                "kb_name": kb_name,
                "query": query,
                "question_type": question_type
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _ingest_web_content(self, kb_name: str, url: str, custom_meta: Dict[str, Any] = None) -> Dict[str, Any]:
        """Ingest content from web URLs"""
        try:
            # Fetch web content
            response = requests.get(url, timeout=30)
            response.raise_for_status()

            # Create temporary file with content
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as tmp_file:
                tmp_file.write(response.text)
                tmp_path = tmp_file.name

            # Add URL to metadata
            if not custom_meta:
                custom_meta = {}

            custom_meta.update({
                "source_url": url,
                "fetch_time": time.time(),
                "content_type": response.headers.get('content-type', 'unknown')
            })

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

    async def _call_api(self, url: str, method: str = "GET", headers: Dict[str, str] = None,
                        payload: Dict[str, Any] = None, timeout: int = 30) -> Dict[str, Any]:
        """Make API calls to external services"""
        try:
            # Prepare request
            kwargs = {
                "url": url,
                "method": method.upper(),
                "timeout": timeout
            }

            if headers:
                kwargs["headers"] = headers

            if payload and method.upper() in ["POST", "PUT"]:
                kwargs["json"] = payload

            # Make request
            response = requests.request(**kwargs)

            # Parse response
            try:
                response_data = response.json()
            except:
                response_data = response.text

            return {
                "success": True,
                "status_code": response.status_code,
                "response_data": response_data,
                "headers": dict(response.headers),
                "url": url,
                "method": method.upper()
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def process_message(self, message: AgentMessage, context: ExecutionContext) -> AgentMessage:
        """Process incoming message and route to appropriate knowledge base operations"""
        self.memory.store_message(message)

        try:
            content = message.content.lower()
            user_message = message.content

            # Determine the appropriate action based on message content
            if any(keyword in content for keyword in ['ingest', 'upload', 'add document', 'add file']):
                response_content = await self._handle_ingestion_request(user_message, context)
            elif any(keyword in content for keyword in ['query', 'search', 'find', 'what', 'how', 'where', 'when']):
                response_content = await self._handle_query_request(user_message, context)
            else:
                response_content = await self._handle_general_request(user_message, context)

            response = self.create_response(
                content=response_content,
                recipient_id=message.sender_id,
                session_id=message.session_id,
                conversation_id=message.conversation_id
            )

            self.memory.store_message(response)
            return response

        except Exception as e:
            error_response = self.create_response(
                content=f"Knowledge Base Agent error: {str(e)}",
                recipient_id=message.sender_id,
                message_type=MessageType.ERROR,
                session_id=message.session_id,
                conversation_id=message.conversation_id
            )
            return error_response

    async def _handle_ingestion_request(self, user_message: str, context: ExecutionContext) -> str:
        """Handle document ingestion requests"""
        return ("I can help you ingest documents into your knowledge base. Please provide:\n\n"
                "1. Knowledge base name\n"
                "2. Document path or URL\n"
                "3. Any custom metadata (optional)\n\n"
                "I support PDF, DOCX, TXT files and web URLs. Would you like to proceed?")

    async def _handle_query_request(self, user_message: str, context: ExecutionContext) -> str:
        """Handle knowledge base query requests"""
        if self.llm_service:
            prompt = f"""
            The user wants to query a knowledge base. Based on their message, help determine:
            1. What knowledge base they want to query (if mentioned)
            2. What their actual question is

            User message: {user_message}

            Please provide a helpful response about how to query the knowledge base.
            """

            response = await self.llm_service.generate_response(prompt, context.metadata)
            return response
        else:
            return ("I can help you query knowledge bases. Please specify:\n\n"
                    "1. Knowledge base name\n"
                    "2. Your question\n"
                    "3. Question type (free-text, multiple choice, yes/no)\n\n"
                    "Example: 'Query the company_docs knowledge base: What is our return policy?'")

    async def _handle_general_request(self, user_message: str, context: ExecutionContext) -> str:
        """Handle general knowledge base requests"""
        if self.llm_service:
            prompt = f"""
            You are a Knowledge Base Agent that helps with document management and retrieval.

            Your capabilities include:
            - Ingesting documents (PDF, DOCX, TXT, web URLs)
            - Querying knowledge bases with intelligent retrieval
            - Managing document lifecycle (add, update, delete)
            - Processing various file types
            - Making API calls and database queries

            User message: {user_message}

            Provide a helpful response about how you can assist with their knowledge base needs.
            """

            response = await self.llm_service.generate_response(prompt, context.metadata)
            return response
        else:
            return ("I'm your Knowledge Base Agent! I can help you with:\n\n"
                    "📄 **Document Management**\n"
                    "- Ingest PDFs, DOCX, TXT files\n"
                    "- Process web content from URLs\n"
                    "- Delete documents and manage collections\n\n"
                    "🔍 **Intelligent Search**\n"
                    "- Query knowledge bases with natural language\n"
                    "- Support for different question types\n"
                    "- Source attribution and relevance scoring\n\n"
                    "🔧 **Integration Tools**\n"
                    "- API calls to external services\n"
                    "- Status monitoring and analytics\n\n"
                    "How can I help you today?")