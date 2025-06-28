# ambivo_agents/core/memory.py
"""
Memory management system for ambivo_agents.
FIXED: Redis key consistency issue for session history retrieval
"""

import json
import gzip
import time
import logging
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Any, Optional, Union
from collections import OrderedDict
import hashlib
import base64

from ..config.loader import load_config, get_config_section

# External dependencies with fallbacks
try:
    import redis
    from cachetools import TTLCache
    import lz4.frame

    REDIS_AVAILABLE = True
    COMPRESSION_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    COMPRESSION_AVAILABLE = False


@dataclass
class MemoryStats:
    """Memory usage and performance statistics"""
    total_operations: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    compression_savings_bytes: int = 0
    avg_response_time_ms: float = 0.0
    redis_memory_usage_bytes: int = 0
    local_cache_size: int = 0
    error_count: int = 0

    @property
    def cache_hit_rate(self) -> float:
        """Calculate cache hit rate percentage"""
        total = self.cache_hits + self.cache_misses
        return (self.cache_hits / total * 100) if total > 0 else 0.0


class MemoryManagerInterface(ABC):
    """Abstract interface for memory management"""

    @abstractmethod
    def store_message(self, message):
        """Store a message in memory"""
        pass

    @abstractmethod
    def get_recent_messages(self, limit: int = 10, conversation_id: Optional[str] = None):
        """Retrieve recent messages from memory"""
        pass

    @abstractmethod
    def store_context(self, key: str, value: Any, conversation_id: Optional[str] = None):
        """Store contextual information"""
        pass

    @abstractmethod
    def get_context(self, key: str, conversation_id: Optional[str] = None):
        """Retrieve contextual information"""
        pass

    @abstractmethod
    def clear_memory(self, conversation_id: Optional[str] = None):
        """Clear memory"""
        pass


class CompressionManager:
    """Handles data compression with safe UTF-8 handling"""

    def __init__(self, enabled: bool = True, algorithm: str = 'lz4', compression_level: int = 1):
        self.enabled = enabled
        self.algorithm = algorithm
        self.compression_level = compression_level
        self.min_size_bytes = 100
        self.stats = {'compressed_count': 0, 'decompressed_count': 0, 'bytes_saved': 0}

    def compress(self, data: str) -> str:
        """Compress string data with safe UTF-8 handling"""
        if not self.enabled or len(data) < self.min_size_bytes or not COMPRESSION_AVAILABLE:
            return data

        try:
            if isinstance(data, str):
                data_bytes = data.encode('utf-8', errors='replace')
            else:
                data_bytes = str(data).encode('utf-8', errors='replace')

            if self.algorithm == 'gzip':
                compressed = gzip.compress(data_bytes, compresslevel=self.compression_level)
            elif self.algorithm == 'lz4':
                compressed = lz4.frame.compress(data_bytes, compression_level=self.compression_level)
            else:
                return data

            original_size = len(data_bytes)
            compressed_size = len(compressed)

            if compressed_size < original_size:
                self.stats['bytes_saved'] += (original_size - compressed_size)
                self.stats['compressed_count'] += 1

                compressed_b64 = base64.b64encode(compressed).decode('ascii')
                return f'COMPRESSED:{self.algorithm}:{compressed_b64}'

            return data

        except Exception as e:
            logging.error(f"Compression failed: {e}")
            return data

    def decompress(self, data: str) -> str:
        """Decompress data with safe UTF-8 handling"""
        if not isinstance(data, str) or not data.startswith('COMPRESSED:'):
            return str(data)

        try:
            parts = data.split(':', 2)
            if len(parts) == 3:
                algorithm = parts[1]
                compressed_b64 = parts[2]

                compressed_data = base64.b64decode(compressed_b64.encode('ascii'))

                if algorithm == 'gzip':
                    decompressed = gzip.decompress(compressed_data).decode('utf-8', errors='replace')
                elif algorithm == 'lz4':
                    decompressed = lz4.frame.decompress(compressed_data).decode('utf-8', errors='replace')
                else:
                    decompressed = compressed_data.decode('utf-8', errors='replace')

                self.stats['decompressed_count'] += 1
                return decompressed

            return data

        except Exception as e:
            logging.error(f"Decompression failed: {e}")
            return str(data)


class IntelligentCache:
    """Intelligent caching with safe encoding"""

    def __init__(self, enabled: bool = True, max_size: int = 1000, ttl_seconds: int = 300):
        self.enabled = enabled
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.cache: TTLCache = TTLCache(maxsize=max_size, ttl=ttl_seconds)
        self.stats = {'hits': 0, 'misses': 0, 'evictions': 0}
        self._lock = threading.RLock()

    def _safe_key(self, key: str) -> str:
        """Ensure key is safe for caching"""
        if isinstance(key, bytes):
            return key.decode('utf-8', errors='replace')
        return str(key)

    def get(self, key: str) -> Optional[Any]:
        """Get item from cache with safe key handling"""
        if not self.enabled:
            return None

        with self._lock:
            try:
                safe_key = self._safe_key(key)
                value = self.cache[safe_key]
                self.stats['hits'] += 1
                return value
            except KeyError:
                self.stats['misses'] += 1
                return None
            except Exception as e:
                logging.error(f"Cache get error: {e}")
                self.stats['misses'] += 1
                return None

    def set(self, key: str, value: Any) -> None:
        """Set item in cache with safe key handling"""
        if not self.enabled:
            return

        with self._lock:
            try:
                safe_key = self._safe_key(key)
                if len(self.cache) >= self.max_size:
                    self.stats['evictions'] += 1
                self.cache[safe_key] = value
            except Exception as e:
                logging.error(f"Cache set error: {e}")

    def delete(self, key: str) -> bool:
        """Delete item from cache"""
        if not self.enabled:
            return False

        with self._lock:
            try:
                safe_key = self._safe_key(key)
                del self.cache[safe_key]
                return True
            except KeyError:
                return False
            except Exception as e:
                logging.error(f"Cache delete error: {e}")
                return False

    def clear(self) -> None:
        """Clear all cache entries"""
        with self._lock:
            self.cache.clear()


class RedisMemoryManager(MemoryManagerInterface):
    """Redis memory manager with session-based keys and UTF-8 handling - FIXED KEY CONSISTENCY"""

    def __init__(self, agent_id: str, redis_config: Dict[str, Any] = None):
        self.agent_id = agent_id

        # Load configuration from YAML
        config = load_config()
        memory_config = config.get('memory_management', {})

        # Get Redis config from YAML if not provided
        if redis_config is None:
            redis_config = get_config_section('redis', config)

        self.redis_config = redis_config.copy()

        # Ensure safe Redis configuration
        self.redis_config.update({
            'decode_responses': True,
            'encoding': 'utf-8',
            'encoding_errors': 'replace',
            'socket_timeout': 10,
            'socket_connect_timeout': 10,
            'retry_on_timeout': True
        })

        # Initialize components from config
        compression_config = memory_config.get('compression', {})
        self.compression_manager = CompressionManager(
            enabled=compression_config.get('enabled', True),
            algorithm=compression_config.get('algorithm', 'lz4'),
            compression_level=compression_config.get('compression_level', 1)
        )

        cache_config = memory_config.get('cache', {})
        self.cache = IntelligentCache(
            enabled=cache_config.get('enabled', True),
            max_size=cache_config.get('max_size', 1000),
            ttl_seconds=cache_config.get('ttl_seconds', 300)
        )

        # Statistics
        self.stats = MemoryStats()

        # Initialize Redis connection
        if not REDIS_AVAILABLE:
            raise ImportError("Redis package is required but not installed")

        try:
            self.redis_client = redis.Redis(**self.redis_config)
            self.redis_client.ping()
            self.available = True
        except Exception as e:
            raise ConnectionError(f"Failed to connect to Redis: {e}")

    def _get_primary_identifier(self, session_id: str = None, conversation_id: str = None) -> str:
        """
        FIXED: Get consistent primary identifier for key generation
        Priority: conversation_id > session_id > agent_id
        """
        if conversation_id:
            return conversation_id
        elif session_id:
            return session_id
        else:
            return self.agent_id

    def _get_message_key(self, session_id: str = None, conversation_id: str = None) -> str:
        """
        FIXED: Generate consistent message key
        Uses the same primary identifier logic for both storage and retrieval
        """
        primary_id = self._get_primary_identifier(session_id, conversation_id)

        # Always use session: prefix for session/conversation IDs
        if primary_id != self.agent_id:
            return f"session:{primary_id}:messages"
        else:
            # Fallback to agent-based key only when no session info
            return f"agent:{primary_id}:messages"

    def _get_context_key(self, session_id: str = None, conversation_id: str = None) -> str:
        """
        FIXED: Generate consistent context key
        Uses the same primary identifier logic
        """
        primary_id = self._get_primary_identifier(session_id, conversation_id)

        if primary_id != self.agent_id:
            return f"session:{primary_id}:context"
        else:
            return f"agent:{primary_id}:context"

    def _safe_serialize(self, obj: Any) -> str:
        """Safely serialize object to JSON with UTF-8 handling"""
        try:
            json_str = json.dumps(obj, ensure_ascii=True, default=str)
            return self.compression_manager.compress(json_str)
        except Exception as e:
            logging.error(f"Serialization error: {e}")
            return json.dumps({"error": "serialization_failed", "original_type": str(type(obj))})

    def _safe_deserialize(self, data: str) -> Any:
        """Safely deserialize JSON data"""
        try:
            if isinstance(data, bytes):
                data = data.decode('utf-8', errors='replace')

            decompressed_data = self.compression_manager.decompress(str(data))
            return json.loads(decompressed_data)
        except Exception as e:
            logging.error(f"Deserialization error: {e}")
            return {"error": "deserialization_failed", "data": str(data)[:100]}

    def store_message(self, message):
        """FIXED: Store message with consistent key generation"""
        try:
            # Extract session/conversation info from message
            session_id = getattr(message, 'session_id', None)
            conversation_id = getattr(message, 'conversation_id', None)

            # FIXED: Use consistent key generation
            key = self._get_message_key(session_id, conversation_id)

            message_data = self._safe_serialize(message.to_dict() if hasattr(message, 'to_dict') else message)

            self.redis_client.lpush(key, message_data)
            self.redis_client.expire(key, 30 * 24 * 3600)  # 30 days TTL

            # Cache the latest message
            self.cache.set(f"recent_msg:{key}", message_data)
            self.stats.total_operations += 1

            # Enhanced debug logging
            logging.debug(f"STORED message - Key: {key}")
            logging.debug(f"  session_id: {session_id}, conversation_id: {conversation_id}")
            logging.debug(f"  primary_id: {self._get_primary_identifier(session_id, conversation_id)}")

        except Exception as e:
            logging.error(f"Error storing message: {e}")
            self.stats.error_count += 1

    def get_recent_messages(self, limit: int = 10, conversation_id: Optional[str] = None):
        """FIXED: Get recent messages with proper message ordering and error handling"""
        try:
            # Generate key using fixed logic
            key = self._get_message_key(conversation_id, conversation_id)

            # Enhanced debug logging
            logging.debug(f"RETRIEVING MESSAGES from key: {key}")
            logging.debug(f"  conversation_id: {conversation_id}, limit: {limit}")

            # Check if key exists
            key_exists = self.redis_client.exists(key)
            if not key_exists:
                logging.debug(f"  Key {key} does not exist")
                return []

            total_messages = self.redis_client.llen(key)
            logging.debug(f"  Total messages in Redis: {total_messages}")

            # Skip cache and go directly to Redis
            message_data_list = self.redis_client.lrange(key, 0, limit - 1)
            logging.debug(f"  Retrieved {len(message_data_list)} raw items from Redis")

            messages = []

            # Process all messages (don't reverse yet)
            for i, message_data in enumerate(message_data_list):
                try:
                    logging.debug(f"  Processing message {i + 1}: {str(message_data)[:50]}...")

                    # Deserialize message
                    data = self._safe_deserialize(message_data)

                    if isinstance(data, dict) and 'content' in data:
                        logging.debug(
                            f"    ✅ Valid message: {data.get('message_type')} - {data.get('content')[:30]}...")
                        messages.append(data)
                    else:
                        logging.warning(f"    ⚠️ Invalid message format: {type(data)}")

                except Exception as e:
                    logging.error(f"  ❌ Error parsing message {i + 1}: {e}")
                    continue

            # CRITICAL FIX: Reverse to get chronological order (oldest first)
            # LPUSH stores newest first, so we need to reverse for proper conversation flow
            messages.reverse()

            logging.debug(f"  ✅ Returning {len(messages)} messages in chronological order")

            self.stats.total_operations += 1
            return messages

        except Exception as e:
            logging.error(f"Error retrieving messages: {e}")
            self.stats.error_count += 1
            return []

    def store_context(self, key: str, value: Any, conversation_id: Optional[str] = None):
        """FIXED: Store context with consistent keys"""
        try:
            redis_key = self._get_context_key(conversation_id, conversation_id)

            value_json = self._safe_serialize(value)

            self.redis_client.hset(redis_key, key, value_json)
            self.redis_client.expire(redis_key, 30 * 24 * 3600)  # 30 days TTL

            self.cache.set(f"ctx:{redis_key}:{key}", value)
            self.stats.total_operations += 1

        except Exception as e:
            logging.error(f"Error storing context: {e}")
            self.stats.error_count += 1

    def get_context(self, key: str, conversation_id: Optional[str] = None):
        """FIXED: Get context with consistent keys"""
        try:
            redis_key = self._get_context_key(conversation_id, conversation_id)

            cache_key = f"ctx:{redis_key}:{key}"
            cached_value = self.cache.get(cache_key)
            if cached_value is not None:
                self.stats.cache_hits += 1
                return cached_value

            self.stats.cache_misses += 1

            value_str = self.redis_client.hget(redis_key, key)
            if value_str:
                value = self._safe_deserialize(value_str)
                self.cache.set(cache_key, value)
                self.stats.total_operations += 1
                return value

            return None

        except Exception as e:
            logging.error(f"Error retrieving context: {e}")
            self.stats.error_count += 1
            return None

    def clear_memory(self, conversation_id: Optional[str] = None):
        """FIXED: Clear memory with consistent keys"""
        try:
            if conversation_id:
                # Clear specific session
                message_key = self._get_message_key(conversation_id, conversation_id)
                context_key = self._get_context_key(conversation_id, conversation_id)
                deleted_count = self.redis_client.delete(message_key, context_key)

                logging.debug(f"Cleared memory for conversation {conversation_id}: {deleted_count} keys deleted")
            else:
                # Clear all agent keys
                agent_pattern = f"agent:{self.agent_id}:*"
                session_pattern = f"session:*"

                agent_keys = self.redis_client.keys(agent_pattern)
                session_keys = self.redis_client.keys(session_pattern)

                all_keys = agent_keys + session_keys
                if all_keys:
                    deleted_count = self.redis_client.delete(*all_keys)
                else:
                    deleted_count = 0

                logging.debug(f"Cleared all memory: {deleted_count} keys deleted")

            self.cache.clear()
            self.stats.total_operations += 1

        except Exception as e:
            logging.error(f"Error clearing memory: {e}")
            self.stats.error_count += 1

    def get_stats(self) -> MemoryStats:
        """Get memory usage statistics"""
        try:
            info = self.redis_client.info('memory')
            self.stats.redis_memory_usage_bytes = info.get('used_memory', 0)
            self.stats.local_cache_size = len(self.cache.cache)
            self.stats.cache_hits += self.cache.stats['hits']
            self.stats.cache_misses += self.cache.stats['misses']
            self.stats.compression_savings_bytes = self.compression_manager.stats['bytes_saved']
        except Exception as e:
            logging.error(f"Error getting stats: {e}")

        return self.stats

    def debug_session_keys(self, session_id: str = None, conversation_id: str = None) -> Dict[str, Any]:
        """
        NEW: Debug method to inspect Redis keys for a session
        Useful for troubleshooting key consistency issues
        """
        try:
            keys_to_check = []

            # Check all possible key combinations
            if conversation_id:
                keys_to_check.extend([
                    f"session:{conversation_id}:messages",
                    f"session:{conversation_id}:context"
                ])

            if session_id and session_id != conversation_id:
                keys_to_check.extend([
                    f"session:{session_id}:messages",
                    f"session:{session_id}:context"
                ])

            # Agent fallback keys
            keys_to_check.extend([
                f"agent:{self.agent_id}:messages",
                f"agent:{self.agent_id}:context"
            ])

            result = {
                'session_id': session_id,
                'conversation_id': conversation_id,
                'agent_id': self.agent_id,
                'primary_identifier': self._get_primary_identifier(session_id, conversation_id),
                'message_key': self._get_message_key(session_id, conversation_id),
                'context_key': self._get_context_key(session_id, conversation_id),
                'keys_checked': len(keys_to_check),
                'key_status': {}
            }

            for key in keys_to_check:
                exists = self.redis_client.exists(key)
                if exists:
                    key_type = self.redis_client.type(key)
                    if key_type == 'list':
                        length = self.redis_client.llen(key)
                        result['key_status'][key] = {
                            'exists': True,
                            'type': key_type,
                            'length': length
                        }
                    elif key_type == 'hash':
                        length = self.redis_client.hlen(key)
                        result['key_status'][key] = {
                            'exists': True,
                            'type': key_type,
                            'length': length
                        }
                    else:
                        result['key_status'][key] = {
                            'exists': True,
                            'type': key_type
                        }
                else:
                    result['key_status'][key] = {'exists': False}

            return result

        except Exception as e:
            return {'error': str(e)}

    def debug_keys(self, pattern: str = "*") -> Dict[str, Any]:
        """Enhanced debug method to inspect Redis keys"""
        try:
            keys = self.redis_client.keys(pattern)
            result = {
                'total_keys': len(keys),
                'keys': []
            }

            for key in keys[:20]:  # Limit to first 20 keys
                key_str = key.decode() if isinstance(key, bytes) else str(key)
                key_type = self.redis_client.type(key_str)

                if key_type == 'list':
                    length = self.redis_client.llen(key_str)
                    result['keys'].append({
                        'key': key_str,
                        'type': key_type,
                        'length': length
                    })
                elif key_type == 'hash':
                    length = self.redis_client.hlen(key_str)
                    result['keys'].append({
                        'key': key_str,
                        'type': key_type,
                        'length': length
                    })
                else:
                    result['keys'].append({
                        'key': key_str,
                        'type': key_type
                    })

            return result

        except Exception as e:
            logging.error(f"Error debugging keys: {e}")
            return {'error': str(e)}


def create_redis_memory_manager(agent_id: str, redis_config: Dict[str, Any] = None):
    """
    Create Redis memory manager with configuration from YAML.

    Args:
        agent_id: Unique identifier for the agent
        redis_config: Optional Redis configuration. If None, loads from YAML.

    Returns:
        RedisMemoryManager instance
    """
    return RedisMemoryManager(agent_id, redis_config)