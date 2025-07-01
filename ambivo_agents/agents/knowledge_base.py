# ambivo_agents/agents/knowledge_base.py
"""
LLM-Aware Knowledge Base Agent with conversation history and intelligent intent detection
Updated for consistency with other agents
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
from ..core.history import KnowledgeBaseAgentHistoryMixin, ContextType


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
                from langchain_unstructured import UnstructuredLoader
                from llama_index.core.readers import Document as LIDoc

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
            collection_prefix = kb_config.get('default_collection_prefix', '')
            collection_name = kb_name
            if collection_prefix:
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

            collection_prefix = kb_config.get('default_collection_prefix', '')
            collection_name = kb_name
            if collection_prefix:
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


class KnowledgeBaseAgent(BaseAgent, KnowledgeBaseAgentHistoryMixin):
    """LLM-Aware Knowledge Base Agent with conversation context and intelligent routing"""

    def __init__(self, agent_id: str = None, memory_manager=None, llm_service=None, **kwargs):
        if agent_id is None:
            agent_id = f"kb_{str(uuid.uuid4())[:8]}"

        super().__init__(
            agent_id=agent_id,
            role=AgentRole.RESEARCHER,
            memory_manager=memory_manager,
            llm_service=llm_service,
            name="Knowledge Base Agent",
            description="LLM-aware knowledge base agent with conversation history",
            **kwargs
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

    async def _llm_analyze_kb_intent(self, user_message: str, conversation_context: str = "") -> Dict[str, Any]:
        """Use LLM to analyze knowledge base related intent"""
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
            "confidence": 0.0-1.0
        }}
        """

        try:
            response = await self.llm_service.generate_response(prompt)
            import re
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            else:
                return self._extract_kb_intent_from_llm_response(response, user_message)
        except Exception as e:
            return self._keyword_based_kb_analysis(user_message)

    def _keyword_based_kb_analysis(self, user_message: str) -> Dict[str, Any]:
        """Fallback keyword-based KB intent analysis"""
        content_lower = user_message.lower()

        # Determine intent
        if any(word in content_lower for word in ['ingest', 'upload', 'add document', 'import', 'load']):
            intent = 'ingest_document'
        elif any(word in content_lower for word in ['add text', 'ingest text', 'text to']):
            intent = 'ingest_text'
        elif any(word in content_lower for word in ['query', 'search', 'find', 'ask', 'what', 'how', 'where']):
            intent = 'query_kb'
        elif any(word in content_lower for word in ['create', 'new kb', 'make kb', 'setup']):
            intent = 'create_kb'
        elif any(word in content_lower for word in ['help', 'what can', 'how to']):
            intent = 'help_request'
        else:
            intent = 'help_request'

        # Extract KB names and documents
        kb_names = self.extract_context_from_text(user_message, ContextType.KNOWLEDGE_BASE)
        documents = self.extract_context_from_text(user_message, ContextType.DOCUMENT_NAME)
        file_paths = self.extract_context_from_text(user_message, ContextType.FILE_PATH)
        all_documents = documents + file_paths

        # Extract query content
        query_content = self._extract_query_from_kb_message(user_message) if intent == 'query_kb' else None

        return {
            "primary_intent": intent,
            "kb_name": kb_names[0] if kb_names else None,
            "document_references": all_documents,
            "query_content": query_content,
            "uses_context_reference": any(word in content_lower for word in ['this', 'that', 'it']),
            "context_type": "previous_kb",
            "operation_details": {
                "query_type": "free-text",
                "custom_metadata": {},
                "source_type": "file"
            },
            "confidence": 0.7
        }

    async def process_message(self, message: AgentMessage, context: ExecutionContext = None) -> AgentMessage:
        """Process message with LLM-based KB intent detection and history context"""
        self.memory.store_message(message)

        try:
            user_message = message.content

            # Update conversation state
            self.update_conversation_state(user_message)

            # Get conversation context for LLM analysis
            conversation_context = self._get_kb_conversation_context_summary()

            # Use LLM to analyze intent
            intent_analysis = await self._llm_analyze_kb_intent(user_message, conversation_context)

            # Route request based on LLM analysis
            response_content = await self._route_kb_with_llm_analysis(intent_analysis, user_message, context)

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

    def _get_kb_conversation_context_summary(self) -> str:
        """Get KB conversation context summary"""
        try:
            recent_history = self.get_conversation_history_with_context(
                limit=3,
                context_types=[ContextType.KNOWLEDGE_BASE, ContextType.DOCUMENT_NAME]
            )

            context_summary = []
            for msg in recent_history:
                if msg.get('message_type') == 'user_input':
                    extracted_context = msg.get('extracted_context', {})
                    kb_names = extracted_context.get('knowledge_base', [])
                    docs = extracted_context.get('document_name', [])

                    if kb_names:
                        context_summary.append(f"Previous KB: {kb_names[0]}")
                    if docs:
                        context_summary.append(f"Previous document: {docs[0]}")

            # Add current state
            current_kb = self.get_current_knowledge_base()
            if current_kb:
                context_summary.append(f"Current KB: {current_kb}")

            return "\n".join(context_summary) if context_summary else "No previous KB context"
        except:
            return "No previous KB context"

    async def _route_kb_with_llm_analysis(self, intent_analysis: Dict[str, Any], user_message: str,
                                          context: ExecutionContext) -> str:
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
            return await self._handle_document_ingestion(kb_name, documents, operation_details, user_message)
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

    async def _handle_document_ingestion(self, kb_name: str, documents: List[str], operation_details: Dict[str, Any],
                                         user_message: str) -> str:
        """Handle document ingestion with LLM analysis"""

        # Resolve missing parameters
        if not kb_name:
            available_kbs = self.conversation_state.knowledge_bases
            if available_kbs:
                return f"I can ingest documents! Which knowledge base?\n\n" \
                       f"**Available KBs:**\n" + "\n".join([f"• {kb}" for kb in available_kbs]) + \
                    f"\n\nOr specify a new KB name."
            else:
                return "I can ingest documents into knowledge bases. Please specify:\n\n" \
                       "1. **Knowledge base name** (I'll create it if it doesn't exist)\n" \
                       "2. **Document path** or just tell me which document\n\n" \
                       "Example: 'Ingest research.pdf into ai_papers'"

        if not documents:
            return f"I'll ingest into the **{kb_name}** knowledge base. Which document would you like to add?\n\n" \
                   f"Please provide the document path or tell me the filename."

        # Perform ingestion
        document_path = documents[0]

        try:
            # Check if it's a URL or file path
            if document_path.startswith('http'):
                result = await self._ingest_web_content(kb_name, document_path)
                operation_type = "Web content"
            else:
                result = await self._ingest_document(kb_name, document_path)
                operation_type = "Document"

            if result['success']:
                return f"✅ **{operation_type} Ingestion Completed**\n\n" \
                       f"📄 **Source:** {document_path}\n" \
                       f"🗃️ **Knowledge Base:** {kb_name}\n" \
                       f"⏱️ **Status:** Successfully processed and indexed\n\n" \
                       f"You can now query this knowledge base! 🎉"
            else:
                return f"❌ **Ingestion failed:** {result['error']}"

        except Exception as e:
            return f"❌ **Error during ingestion:** {str(e)}"

    async def _handle_text_ingestion(self, kb_name: str, user_message: str, operation_details: Dict[str, Any]) -> str:
        """Handle text ingestion with LLM analysis"""

        if not kb_name:
            return "I can ingest text into knowledge bases. Please specify which knowledge base to use."

        # Extract text content from message (after removing command parts)
        text_content = self._extract_text_for_ingestion(user_message)

        if not text_content:
            return f"I'll add text to the **{kb_name}** knowledge base. What text would you like me to ingest?"

        try:
            result = await self._ingest_text(kb_name, text_content)

            if result['success']:
                preview = text_content[:100] + "..." if len(text_content) > 100 else text_content
                return f"✅ **Text Ingestion Completed**\n\n" \
                       f"📝 **Text Preview:** {preview}\n" \
                       f"🗃️ **Knowledge Base:** {kb_name}\n" \
                       f"📊 **Length:** {len(text_content)} characters\n\n" \
                       f"Text successfully indexed! 🎉"
            else:
                return f"❌ **Text ingestion failed:** {result['error']}"

        except Exception as e:
            return f"❌ **Error during text ingestion:** {str(e)}"

    async def _handle_kb_query(self, kb_name: str, query_content: str, operation_details: Dict[str, Any]) -> str:
        """Handle KB queries with LLM analysis"""

        # Resolve missing parameters
        if not kb_name:
            available_kbs = self.conversation_state.knowledge_bases
            if available_kbs:
                return f"I can query knowledge bases! Which one?\n\n" \
                       f"**Available KBs from our conversation:**\n" + \
                    "\n".join([f"• {kb}" for kb in available_kbs]) + \
                    f"\n\nExample: 'Query {available_kbs[0]}: {query_content or 'your question'}'"
            else:
                return "I can query knowledge bases, but I need to know which one to search.\n\n" \
                       "Please specify: `Query [kb_name]: [your question]`"

        if not query_content:
            return f"I'll search the **{kb_name}** knowledge base. What would you like me to find?"

        try:
            query_type = operation_details.get("query_type", "free-text")
            result = await self._query_knowledge_base(kb_name, query_content, question_type=query_type)

            if result['success']:
                answer = result['answer']
                source_count = len(result.get('source_details', []))

                return f"🔍 **Query Results from {kb_name}**\n\n" \
                       f"**Question:** {query_content}\n\n" \
                       f"**Answer:**\n{answer}\n\n" \
                       f"📊 **Sources:** {source_count} relevant documents found"
            else:
                return f"❌ **Query failed:** {result['error']}"

        except Exception as e:
            return f"❌ **Error during query:** {str(e)}"

    async def _handle_kb_creation(self, kb_name: str, user_message: str) -> str:
        """Handle KB creation requests"""

        if not kb_name:
            return "I can create knowledge bases! What would you like to name the new knowledge base?\n\n" \
                   "Example: 'Create a knowledge base called research_papers'"

        # KB creation is implicit when first document is ingested
        return f"Great! I'll create the **{kb_name}** knowledge base when you add the first document.\n\n" \
               f"To get started:\n" \
               f"• `Ingest document.pdf into {kb_name}`\n" \
               f"• `Add text to {kb_name}: [your text content]`\n" \
               f"• `Ingest https://example.com into {kb_name}`"

    async def _handle_kb_management(self, kb_name: str, user_message: str) -> str:
        """Handle KB management requests"""

        available_kbs = self.conversation_state.knowledge_bases

        if not available_kbs:
            return "No knowledge bases found in our conversation. Create one by ingesting your first document!"

        response = f"📚 **Knowledge Base Management**\n\n"
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

        response = ("I'm your Knowledge Base Agent! I can help you with:\n\n"
                    "📄 **Document Management**\n"
                    "- Ingest PDFs, DOCX, TXT, MD files\n"
                    "- Process web content from URLs\n"
                    "- Add text content directly\n\n"
                    "🔍 **Intelligent Search**\n"
                    "- Natural language queries\n"
                    "- Semantic similarity search\n"
                    "- Source attribution\n\n"
                    "🧠 **Smart Context Features**\n"
                    "- Remembers knowledge bases from conversation\n"
                    "- Understands 'that KB' and 'this document'\n"
                    "- Maintains working context\n\n")

        # Add current context information
        if state.knowledge_bases:
            response += f"🗃️ **Your Knowledge Bases:**\n"
            for kb in state.knowledge_bases[-3:]:  # Show last 3
                response += f"   • {kb}\n"

        if state.working_files:
            response += f"\n📁 **Recent Documents:** {len(state.working_files)} files\n"

        response += "\n💡 **Examples:**\n"
        response += "• 'Ingest research.pdf into ai_papers'\n"
        response += "• 'Query ai_papers: What are the main findings?'\n"
        response += "• 'Add this text to the knowledge base: [content]'\n"
        response += "\nI understand context from our conversation! 🚀"

        return response

    def _extract_query_from_kb_message(self, message: str) -> str:
        """Extract query content from KB message"""
        # Look for colon pattern first
        import re
        colon_match = re.search(r':\s*(.+)', message)
        if colon_match:
            return colon_match.group(1).strip()

        # Remove KB operation keywords
        query_keywords = ['query', 'search', 'find', 'ask', 'what', 'how', 'where', 'when', 'why']
        words = message.split()
        filtered_words = []

        for word in words:
            if word.lower() not in query_keywords and not word.lower().endswith('_kb'):
                filtered_words.append(word)

        return ' '.join(filtered_words).strip()

    def _extract_text_for_ingestion(self, message: str) -> str:
        """Extract text content for ingestion from message"""
        # Look for colon pattern
        import re
        colon_match = re.search(r':\s*(.+)', message)
        if colon_match:
            return colon_match.group(1).strip()

        # Remove ingestion keywords
        ingest_keywords = ['ingest', 'add', 'upload', 'text', 'into', 'to']
        words = message.split()
        filtered_words = []
        skip_next = False

        for word in words:
            if skip_next:
                skip_next = False
                continue

            if word.lower() in ingest_keywords:
                continue
            elif word.lower().endswith('_kb') or word.lower().endswith('_base'):
                continue
            else:
                filtered_words.append(word)

        return ' '.join(filtered_words).strip()

    def _extract_kb_intent_from_llm_response(self, llm_response: str, user_message: str) -> Dict[str, Any]:
        """Extract KB intent from non-JSON LLM response"""
        content_lower = llm_response.lower()

        if 'ingest' in content_lower or 'upload' in content_lower:
            intent = 'ingest_document'
        elif 'query' in content_lower or 'search' in content_lower:
            intent = 'query_kb'
        elif 'create' in content_lower:
            intent = 'create_kb'
        else:
            intent = 'help_request'

        return {
            "primary_intent": intent,
            "kb_name": None,
            "document_references": [],
            "query_content": None,
            "uses_context_reference": False,
            "context_type": "none",
            "operation_details": {"query_type": "free-text"},
            "confidence": 0.6
        }

    # Tool implementations
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