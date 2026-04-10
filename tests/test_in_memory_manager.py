"""Tests for InMemoryMemoryManager"""

import pytest
from ambivo_agents.core.memory import InMemoryMemoryManager, create_memory_manager


class MockMessage:
    """Simple mock message for testing"""

    def __init__(self, content, sender="user", conversation_id=None, session_id=None):
        self.content = content
        self.sender_id = sender
        self.conversation_id = conversation_id
        self.session_id = session_id

    def to_dict(self):
        return {
            "content": self.content,
            "sender_id": self.sender_id,
            "conversation_id": self.conversation_id,
            "session_id": self.session_id,
        }


class TestInMemoryMemoryManager:
    def test_init(self):
        mm = InMemoryMemoryManager("test_agent")
        assert mm.agent_id == "test_agent"
        assert mm.available is True

    def test_store_and_retrieve_messages(self):
        mm = InMemoryMemoryManager("test_agent")
        msg1 = MockMessage("Hello", conversation_id="conv1")
        msg2 = MockMessage("World", conversation_id="conv1")

        mm.store_message(msg1)
        mm.store_message(msg2)

        messages = mm.get_recent_messages(limit=10, conversation_id="conv1")
        assert len(messages) == 2
        assert messages[0]["content"] == "Hello"
        assert messages[1]["content"] == "World"

    def test_message_limit(self):
        mm = InMemoryMemoryManager("test_agent")
        for i in range(20):
            mm.store_message(MockMessage(f"msg_{i}", conversation_id="conv1"))

        messages = mm.get_recent_messages(limit=5, conversation_id="conv1")
        assert len(messages) == 5
        assert messages[0]["content"] == "msg_15"

    def test_store_and_retrieve_context(self):
        mm = InMemoryMemoryManager("test_agent")
        mm.store_context("key1", {"data": "value"}, conversation_id="conv1")

        result = mm.get_context("key1", conversation_id="conv1")
        assert result == {"data": "value"}

        result = mm.get_context("nonexistent", conversation_id="conv1")
        assert result is None

    def test_clear_memory_specific(self):
        mm = InMemoryMemoryManager("test_agent")
        mm.store_message(MockMessage("msg1", conversation_id="conv1"))
        mm.store_message(MockMessage("msg2", conversation_id="conv2"))

        mm.clear_memory(conversation_id="conv1")

        assert len(mm.get_recent_messages(conversation_id="conv1")) == 0
        assert len(mm.get_recent_messages(conversation_id="conv2")) == 1

    def test_clear_memory_all(self):
        mm = InMemoryMemoryManager("test_agent")
        mm.store_message(MockMessage("msg1", conversation_id="conv1"))
        mm.store_message(MockMessage("msg2", conversation_id="conv2"))
        mm.store_context("key1", "val1", conversation_id="conv1")

        mm.clear_memory()

        assert len(mm.get_recent_messages(conversation_id="conv1")) == 0
        assert len(mm.get_recent_messages(conversation_id="conv2")) == 0
        assert mm.get_context("key1", conversation_id="conv1") is None

    def test_session_id_fallback(self):
        mm = InMemoryMemoryManager("test_agent")
        mm.store_message(MockMessage("msg1", session_id="sess1"))

        messages = mm.get_recent_messages(session_id="sess1")
        assert len(messages) == 1

    def test_agent_id_fallback(self):
        mm = InMemoryMemoryManager("test_agent")
        mm.store_message(MockMessage("msg1"))

        messages = mm.get_recent_messages()
        assert len(messages) == 1

    def test_stats(self):
        mm = InMemoryMemoryManager("test_agent")
        mm.store_message(MockMessage("msg1"))
        mm.get_recent_messages()

        stats = mm.get_stats()
        assert stats.total_operations == 2


class TestCreateMemoryManager:
    def test_falls_back_to_in_memory(self):
        """When Redis is unavailable, should fall back to InMemory"""
        mm = create_memory_manager("test_agent", redis_config={"host": "nonexistent", "port": 9999})
        assert isinstance(mm, InMemoryMemoryManager)
