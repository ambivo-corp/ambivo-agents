# ambivo_agents/core/history.py
"""
BaseAgentHistoryMixin - Shared conversation context functionality for agents
Provides standardized methods for agents to access and use conversation history
"""

import re
import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Callable, Union, Pattern
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum


class ContextType(Enum):
    """Types of context that can be extracted from conversation history"""
    URL = "url"
    FILE_PATH = "file_path"
    KNOWLEDGE_BASE = "knowledge_base"
    SEARCH_TERM = "search_term"
    DOCUMENT_NAME = "document_name"
    MEDIA_FILE = "media_file"
    CODE_REFERENCE = "code_reference"
    CUSTOM = "custom"


@dataclass
class ContextItem:
    """Represents a piece of context extracted from conversation history"""
    value: str
    context_type: ContextType
    source_message: str
    timestamp: datetime
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConversationState:
    """Tracks the current state of a conversation"""
    current_resource: Optional[str] = None
    current_operation: Optional[str] = None
    last_intent: Optional[str] = None
    working_files: List[str] = field(default_factory=list)
    knowledge_bases: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseAgentHistoryMixin:
    """
    Mixin providing conversation history and context functionality for agents.

    This mixin adds the ability for agents to:
    1. Extract context from conversation history
    2. Maintain conversation state
    3. Detect intent and resolve missing context
    4. Provide standardized history-aware processing

    Usage:
        class MyAgent(BaseAgent, BaseAgentHistoryMixin):
            def __init__(self, **kwargs):
                super().__init__(**kwargs)
                self.setup_history_mixin()
    """

    def setup_history_mixin(self):
        """Initialize the history mixin - call this in agent __init__"""
        self.conversation_state = ConversationState()
        self.context_extractors: Dict[ContextType, Callable] = {}
        self.intent_keywords: Dict[str, List[str]] = {}
        self.logger = logging.getLogger(f"{self.__class__.__name__}-History")

        # Register default extractors
        self._register_default_extractors()

        # Register default intent keywords
        self._register_default_intents()

    def _register_default_extractors(self):
        """Register default context extractors"""

        # URL extractor (works for various URL types)
        self.register_context_extractor(
            ContextType.URL,
            lambda text: re.findall(r'https?://[^\s<>"{}|\\^`\[\]]+', text, re.IGNORECASE)
        )

        # File path extractor (common file extensions)
        self.register_context_extractor(
            ContextType.FILE_PATH,
            lambda text: re.findall(r'[^\s]+\.[a-zA-Z0-9]{2,4}(?:\s|$)', text)
        )

        # Knowledge base name extractor (alphanumeric with underscores/hyphens)
        self.register_context_extractor(
            ContextType.KNOWLEDGE_BASE,
            lambda text: re.findall(r'\b[a-zA-Z][a-zA-Z0-9_-]*(?:_kb|_base|_knowledge)\b', text, re.IGNORECASE)
        )

    def _register_default_intents(self):
        """Register default intent keywords for common operations"""
        self.intent_keywords = {
            'download': ['download', 'get', 'fetch', 'retrieve', 'save'],
            'upload': ['upload', 'ingest', 'add', 'import', 'insert'],
            'query': ['search', 'find', 'query', 'look', 'check'],
            'process': ['convert', 'transform', 'process', 'extract', 'generate'],
            'analyze': ['analyze', 'examine', 'inspect', 'review', 'evaluate'],
            'modify': ['edit', 'change', 'update', 'modify', 'alter'],
            'delete': ['delete', 'remove', 'clear', 'drop', 'destroy']
        }

    # ========================
    # CONTEXT EXTRACTOR METHODS
    # ========================

    def register_context_extractor(self, context_type: ContextType, extractor_func: Callable[[str], List[str]]):
        """
        Register a custom context extractor function

        Args:
            context_type: Type of context this extractor handles
            extractor_func: Function that takes text and returns list of extracted items
        """
        self.context_extractors[context_type] = extractor_func

    def extract_context_from_text(self, text: str, context_type: ContextType) -> List[str]:
        """
        Extract specific type of context from text

        Args:
            text: Text to extract context from
            context_type: Type of context to extract

        Returns:
            List of extracted context items
        """
        extractor = self.context_extractors.get(context_type)
        if not extractor:
            self.logger.warning(f"No extractor registered for context type: {context_type}")
            return []

        try:
            return extractor(text)
        except Exception as e:
            self.logger.error(f"Error extracting {context_type} from text: {e}")
            return []

    def extract_all_context_from_text(self, text: str) -> Dict[ContextType, List[str]]:
        """
        Extract all types of context from text

        Args:
            text: Text to extract context from

        Returns:
            Dictionary mapping context types to extracted items
        """
        context = {}
        for context_type in self.context_extractors:
            items = self.extract_context_from_text(text, context_type)
            if items:
                context[context_type] = items
        return context

    # ========================
    # CONVERSATION HISTORY METHODS
    # ========================

    def get_conversation_history_with_context(self,
                                              limit: int = 10,
                                              context_types: Optional[List[ContextType]] = None) -> List[
        Dict[str, Any]]:
        """
        Get conversation history with extracted context

        Args:
            limit: Maximum number of messages to retrieve
            context_types: Specific context types to extract (None for all)

        Returns:
            List of messages with extracted context
        """
        try:
            if not hasattr(self, 'memory') or not self.memory:
                self.logger.warning("No memory manager available")
                return []

            # Get raw history
            history = self.memory.get_recent_messages(
                limit=limit,
                conversation_id=getattr(self.context, 'conversation_id', None)
            )

            # Enrich with context
            enriched_history = []
            for msg in history:
                if isinstance(msg, dict):
                    content = msg.get('content', '')

                    # Extract context from message
                    if context_types:
                        extracted_context = {}
                        for ctx_type in context_types:
                            items = self.extract_context_from_text(content, ctx_type)
                            if items:
                                extracted_context[ctx_type.value] = items
                    else:
                        extracted_context = self.extract_all_context_from_text(content)
                        # Convert enum keys to strings for JSON serialization
                        extracted_context = {k.value: v for k, v in extracted_context.items()}

                    # Add context to message
                    enriched_msg = {
                        **msg,
                        'extracted_context': extracted_context,
                        'has_context': len(extracted_context) > 0
                    }
                    enriched_history.append(enriched_msg)

            return enriched_history

        except Exception as e:
            self.logger.error(f"Error getting conversation history with context: {e}")
            return []

    def get_recent_context_items(self,
                                 context_type: ContextType,
                                 limit: int = 5,
                                 max_messages: int = 10) -> List[ContextItem]:
        """
        Get recent context items of specific type from conversation history

        Args:
            context_type: Type of context to retrieve
            limit: Maximum number of context items to return
            max_messages: Maximum number of messages to search through

        Returns:
            List of ContextItem objects, most recent first
        """
        try:
            history = self.get_conversation_history_with_context(
                limit=max_messages,
                context_types=[context_type]
            )

            context_items = []
            for msg in reversed(history):  # Most recent first
                if msg.get('has_context'):
                    items = msg.get('extracted_context', {}).get(context_type.value, [])
                    for item in items:
                        context_item = ContextItem(
                            value=item,
                            context_type=context_type,
                            source_message=msg.get('content', '')[:100],
                            timestamp=datetime.fromisoformat(msg.get('timestamp', datetime.now().isoformat())),
                            metadata={'message_id': msg.get('id')}
                        )
                        context_items.append(context_item)

                        if len(context_items) >= limit:
                            break

                if len(context_items) >= limit:
                    break

            return context_items

        except Exception as e:
            self.logger.error(f"Error getting recent context items: {e}")
            return []

    def get_most_recent_context(self, context_type: ContextType) -> Optional[str]:
        """
        Get the most recent context item of specific type

        Args:
            context_type: Type of context to retrieve

        Returns:
            Most recent context item or None
        """
        items = self.get_recent_context_items(context_type, limit=1)
        return items[0].value if items else None

    # ========================
    # INTENT DETECTION METHODS
    # ========================

    def detect_intent(self, message: str) -> Optional[str]:
        """
        Detect user intent from message

        Args:
            message: Message to analyze

        Returns:
            Detected intent or None
        """
        content_lower = message.lower()

        for intent, keywords in self.intent_keywords.items():
            if any(keyword in content_lower for keyword in keywords):
                return intent

        return None

    def has_intent_without_context(self, message: str, required_context_types: List[ContextType]) -> bool:
        """
        Check if message has intent but lacks required context

        Args:
            message: Message to analyze
            required_context_types: Context types required for this intent

        Returns:
            True if intent detected but context missing
        """
        # Check if intent is present
        intent = self.detect_intent(message)
        if not intent:
            return False

        # Check if any required context is missing
        for context_type in required_context_types:
            items = self.extract_context_from_text(message, context_type)
            if not items:
                return True  # Intent present but this context type missing

        return False  # All required context is present

    def should_check_history(self, message: str, context_types: List[ContextType]) -> bool:
        """
        Determine if agent should check conversation history for context

        Args:
            message: Current message
            context_types: Context types that might be needed

        Returns:
            True if history should be checked
        """
        # Check for pronouns indicating reference to previous context
        pronouns = ['that', 'this', 'it', 'them', 'those', 'these']
        content_lower = message.lower()
        has_pronouns = any(pronoun in content_lower for pronoun in pronouns)

        # Check for intent without context
        has_intent_without_context = self.has_intent_without_context(message, context_types)

        # Check for short messages (likely missing context)
        is_short_message = len(message.split()) < 6

        return has_pronouns or has_intent_without_context or is_short_message

    # ========================
    # CONVERSATION STATE METHODS
    # ========================

    def update_conversation_state(self, message: str, operation: str = None):
        """
        Update conversation state based on current message

        Args:
            message: Current message
            operation: Operation being performed (optional)
        """
        # Update last intent
        self.conversation_state.last_intent = self.detect_intent(message)

        # Update current operation
        if operation:
            self.conversation_state.current_operation = operation

        # Extract and update resources
        all_context = self.extract_all_context_from_text(message)

        # Update current resource (prioritize URLs, then files)
        if ContextType.URL in all_context:
            self.conversation_state.current_resource = all_context[ContextType.URL][0]
        elif ContextType.FILE_PATH in all_context:
            self.conversation_state.current_resource = all_context[ContextType.FILE_PATH][0]

        # Update working files
        if ContextType.FILE_PATH in all_context:
            for file_path in all_context[ContextType.FILE_PATH]:
                if file_path not in self.conversation_state.working_files:
                    self.conversation_state.working_files.append(file_path)

        # Update knowledge bases
        if ContextType.KNOWLEDGE_BASE in all_context:
            for kb in all_context[ContextType.KNOWLEDGE_BASE]:
                if kb not in self.conversation_state.knowledge_bases:
                    self.conversation_state.knowledge_bases.append(kb)

    def get_conversation_state(self) -> ConversationState:
        """Get current conversation state"""
        return self.conversation_state

    def clear_conversation_state(self):
        """Clear conversation state"""
        self.conversation_state = ConversationState()

    # ========================
    # HIGH-LEVEL HELPER METHODS
    # ========================

    def resolve_context_for_message(self,
                                    message: str,
                                    required_context_types: List[ContextType]) -> Dict[ContextType, Optional[str]]:
        """
        Resolve context for a message by checking current message and history

        Args:
            message: Current message
            required_context_types: Types of context needed

        Returns:
            Dictionary mapping context types to resolved values
        """
        resolved_context = {}

        # First, try to extract from current message
        current_context = self.extract_all_context_from_text(message)

        for context_type in required_context_types:
            if context_type in current_context and current_context[context_type]:
                # Found in current message
                resolved_context[context_type] = current_context[context_type][0]
            else:
                # Not found, check history
                recent_item = self.get_most_recent_context(context_type)
                resolved_context[context_type] = recent_item

        return resolved_context

    def process_message_with_context_resolution(self,
                                                message: str,
                                                required_context_types: List[ContextType],
                                                processor_func: Callable) -> Any:
        """
        Process a message with automatic context resolution

        Args:
            message: Message to process
            required_context_types: Context types needed for processing
            processor_func: Function to call with resolved context

        Returns:
            Result from processor_func
        """
        # Resolve context
        resolved_context = self.resolve_context_for_message(message, required_context_types)

        # Update conversation state
        self.update_conversation_state(message)

        # Call processor with resolved context
        return processor_func(message, resolved_context)

    # ========================
    # DEBUGGING AND INTROSPECTION
    # ========================

    def debug_conversation_context(self) -> Dict[str, Any]:
        """
        Get debugging information about conversation context

        Returns:
            Dictionary with debugging information
        """
        try:
            recent_history = self.get_conversation_history_with_context(limit=5)

            return {
                'conversation_state': {
                    'current_resource': self.conversation_state.current_resource,
                    'current_operation': self.conversation_state.current_operation,
                    'last_intent': self.conversation_state.last_intent,
                    'working_files': self.conversation_state.working_files,
                    'knowledge_bases': self.conversation_state.knowledge_bases
                },
                'registered_extractors': list(self.context_extractors.keys()),
                'intent_keywords': self.intent_keywords,
                'recent_context_summary': {
                    'messages_with_context': len([msg for msg in recent_history if msg.get('has_context')]),
                    'total_messages': len(recent_history),
                    'context_types_found': list(set([
                        ctx_type for msg in recent_history
                        for ctx_type in msg.get('extracted_context', {}).keys()
                    ]))
                }
            }
        except Exception as e:
            return {'error': str(e)}


# ========================
# SPECIALIZED MIXINS FOR SPECIFIC AGENT TYPES
# ========================

class MediaAgentHistoryMixin(BaseAgentHistoryMixin):
    """Specialized history mixin for media processing agents"""

    def setup_history_mixin(self):
        super().setup_history_mixin()

        # Register media-specific extractors
        self.register_context_extractor(
            ContextType.MEDIA_FILE,
            lambda text: re.findall(r'[^\s]+\.(?:mp4|avi|mov|mkv|mp3|wav|flac|aac|m4a|webm|ogg)', text, re.IGNORECASE)
        )

        # Add media-specific intents
        self.intent_keywords.update({
            'extract_audio': ['extract audio', 'get audio', 'audio from'],
            'convert_video': ['convert video', 'convert to', 'change format'],
            'resize': ['resize', 'scale', 'change size'],
            'trim': ['trim', 'cut', 'clip'],
            'thumbnail': ['thumbnail', 'screenshot', 'frame']
        })

    def get_recent_media_file(self) -> Optional[str]:
        """Get most recent media file from conversation"""
        return self.get_most_recent_context(ContextType.MEDIA_FILE)


class KnowledgeBaseAgentHistoryMixin(BaseAgentHistoryMixin):
    """Specialized history mixin for knowledge base agents"""

    def setup_history_mixin(self):
        super().setup_history_mixin()

        # Register KB-specific extractors
        self.register_context_extractor(
            ContextType.DOCUMENT_NAME,
            lambda text: re.findall(r'[^\s]+\.(?:pdf|docx|txt|md|html|csv|json)', text, re.IGNORECASE)
        )

        # Add KB-specific intents
        self.intent_keywords.update({
            'ingest': ['ingest', 'upload', 'add document', 'import'],
            'query_kb': ['query', 'search', 'find in', 'ask'],
            'create_kb': ['create knowledge base', 'new kb', 'make kb']
        })

    def get_current_knowledge_base(self) -> Optional[str]:
        """Get current knowledge base from state or history"""
        if self.conversation_state.knowledge_bases:
            return self.conversation_state.knowledge_bases[-1]
        return self.get_most_recent_context(ContextType.KNOWLEDGE_BASE)

    def get_recent_document(self) -> Optional[str]:
        """Get most recent document from conversation"""
        return self.get_most_recent_context(ContextType.DOCUMENT_NAME)


class WebAgentHistoryMixin(BaseAgentHistoryMixin):
    """Specialized history mixin for web-related agents (search, scraping)"""

    def setup_history_mixin(self):
        super().setup_history_mixin()

        # Register web-specific extractors
        self.register_context_extractor(
            ContextType.SEARCH_TERM,
            lambda text: self._extract_search_terms(text)
        )

        # Add web-specific intents
        self.intent_keywords.update({
            'search': ['search', 'find', 'look up', 'search for'],
            'scrape': ['scrape', 'extract from', 'crawl'],
            'news_search': ['news', 'latest', 'recent'],
            'academic_search': ['research', 'academic', 'papers']
        })

    def _extract_search_terms(self, text: str) -> List[str]:
        """Extract search terms from text"""
        # Look for quoted phrases and key terms
        quoted_terms = re.findall(r'"([^"]+)"', text)
        if quoted_terms:
            return quoted_terms

        # Extract terms after search keywords
        search_patterns = [
            r'search for (.+?)(?:\.|$)',
            r'find (.+?)(?:\.|$)',
            r'look up (.+?)(?:\.|$)'
        ]

        for pattern in search_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                return [match.strip() for match in matches]

        return []

    def get_recent_search_term(self) -> Optional[str]:
        """Get most recent search term from conversation"""
        return self.get_most_recent_context(ContextType.SEARCH_TERM)

    def get_recent_url(self) -> Optional[str]:
        """Get most recent URL from conversation"""
        return self.get_most_recent_context(ContextType.URL)