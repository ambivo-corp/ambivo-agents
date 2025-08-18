# ambivo_agents/core/persistence/sqlite_backend.py

import asyncio
import json
import logging
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Try to import aiosqlite, but make it optional
try:
    import aiosqlite

    AIOSQLITE_AVAILABLE = True
except ImportError:
    AIOSQLITE_AVAILABLE = False
    logger.warning("aiosqlite not available. SQLite workflow persistence disabled.")


class SQLiteWorkflowPersistence:
    """SQLite-based workflow state persistence"""

    def __init__(self, config: Dict[str, Any]):
        if not AIOSQLITE_AVAILABLE:
            raise ImportError(
                "aiosqlite is required for SQLite workflow persistence. "
                "Install it with: pip install aiosqlite>=0.19.0"
            )

        self.config = config
        self.db_path = config.get("database_path", "./data/workflow_state.db")
        self.enable_wal = config.get("enable_wal", True)
        self.timeout = config.get("timeout", 30.0)
        self.auto_vacuum = config.get("auto_vacuum", True)
        self.journal_mode = config.get("journal_mode", "WAL")

        # Ensure the directory exists
        db_dir = Path(self.db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)

        # Table names
        tables = config.get("tables", {})
        self.conversations_table = tables.get("conversations", "workflow_conversations")
        self.steps_table = tables.get("steps", "workflow_steps")
        self.checkpoints_table = tables.get("checkpoints", "workflow_checkpoints")
        self.sessions_table = tables.get("sessions", "workflow_sessions")

        # Retention settings
        retention = config.get("retention", {})
        self.conversation_ttl = retention.get("conversation_ttl", 2592000)  # 30 days
        self.checkpoint_ttl = retention.get("checkpoint_ttl", 604800)  # 7 days
        self.session_ttl = retention.get("session_ttl", 86400)  # 24 hours
        self.cleanup_interval = retention.get("cleanup_interval", 3600)  # 1 hour

        self._initialized = False
        self._last_cleanup = 0

    async def initialize(self):
        """Initialize the SQLite database and tables"""
        if self._initialized:
            return

        try:
            async with aiosqlite.connect(self.db_path, timeout=self.timeout) as db:
                # Configure database
                if self.enable_wal:
                    await db.execute(f"PRAGMA journal_mode={self.journal_mode}")

                if self.auto_vacuum:
                    await db.execute("PRAGMA auto_vacuum=INCREMENTAL")

                # Set other performance optimizations
                await db.execute("PRAGMA synchronous=NORMAL")
                await db.execute("PRAGMA cache_size=10000")
                await db.execute("PRAGMA temp_store=MEMORY")

                # Create tables
                await self._create_tables(db)
                await db.commit()

                logger.info(f"SQLite workflow persistence initialized: {self.db_path}")

        except Exception as e:
            logger.error(f"Failed to initialize SQLite workflow persistence: {e}")
            raise

        self._initialized = True

    async def _create_tables(self, db: aiosqlite.Connection):
        """Create necessary tables for workflow persistence"""

        # Conversations table
        await db.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {self.conversations_table} (
                conversation_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                flow_id TEXT NOT NULL,
                status TEXT NOT NULL,
                current_step TEXT,
                state_data TEXT,
                metadata TEXT,
                created_at REAL DEFAULT (julianday('now')),
                updated_at REAL DEFAULT (julianday('now'))
            )
        """
        )

        # Create indices for conversations
        await db.execute(
            f"""
            CREATE INDEX IF NOT EXISTS idx_{self.conversations_table}_session 
            ON {self.conversations_table}(session_id)
        """
        )
        await db.execute(
            f"""
            CREATE INDEX IF NOT EXISTS idx_{self.conversations_table}_flow 
            ON {self.conversations_table}(flow_id)
        """
        )
        await db.execute(
            f"""
            CREATE INDEX IF NOT EXISTS idx_{self.conversations_table}_status 
            ON {self.conversations_table}(status)
        """
        )
        await db.execute(
            f"""
            CREATE INDEX IF NOT EXISTS idx_{self.conversations_table}_updated 
            ON {self.conversations_table}(updated_at)
        """
        )

        # Steps table
        await db.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {self.steps_table} (
                step_id TEXT,
                conversation_id TEXT,
                step_type TEXT NOT NULL,
                agent_id TEXT,
                input_data TEXT,
                output_data TEXT,
                execution_start REAL,
                execution_end REAL,
                status TEXT NOT NULL,
                error_message TEXT,
                metadata TEXT,
                created_at REAL DEFAULT (julianday('now')),
                PRIMARY KEY (step_id, conversation_id),
                FOREIGN KEY (conversation_id) REFERENCES {self.conversations_table}(conversation_id)
                    ON DELETE CASCADE
            )
        """
        )

        # Create indices for steps
        await db.execute(
            f"""
            CREATE INDEX IF NOT EXISTS idx_{self.steps_table}_conversation 
            ON {self.steps_table}(conversation_id)
        """
        )
        await db.execute(
            f"""
            CREATE INDEX IF NOT EXISTS idx_{self.steps_table}_status 
            ON {self.steps_table}(status)
        """
        )
        await db.execute(
            f"""
            CREATE INDEX IF NOT EXISTS idx_{self.steps_table}_created 
            ON {self.steps_table}(created_at)
        """
        )

        # Checkpoints table
        await db.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {self.checkpoints_table} (
                checkpoint_id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                step_id TEXT NOT NULL,
                state_snapshot TEXT NOT NULL,
                metadata TEXT,
                created_at REAL DEFAULT (julianday('now')),
                FOREIGN KEY (conversation_id) REFERENCES {self.conversations_table}(conversation_id)
                    ON DELETE CASCADE
            )
        """
        )

        # Create indices for checkpoints
        await db.execute(
            f"""
            CREATE INDEX IF NOT EXISTS idx_{self.checkpoints_table}_conversation 
            ON {self.checkpoints_table}(conversation_id)
        """
        )
        await db.execute(
            f"""
            CREATE INDEX IF NOT EXISTS idx_{self.checkpoints_table}_created 
            ON {self.checkpoints_table}(created_at)
        """
        )

        # Sessions table
        await db.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {self.sessions_table} (
                session_id TEXT PRIMARY KEY,
                user_id TEXT,
                session_data TEXT,
                last_activity REAL DEFAULT (julianday('now')),
                created_at REAL DEFAULT (julianday('now'))
            )
        """
        )

        # Create indices for sessions
        await db.execute(
            f"""
            CREATE INDEX IF NOT EXISTS idx_{self.sessions_table}_user 
            ON {self.sessions_table}(user_id)
        """
        )
        await db.execute(
            f"""
            CREATE INDEX IF NOT EXISTS idx_{self.sessions_table}_activity 
            ON {self.sessions_table}(last_activity)
        """
        )

    async def save_conversation_state(self, conversation_id: str, state: Dict[str, Any]) -> bool:
        """Save conversation state to SQLite"""
        await self.initialize()

        try:
            async with aiosqlite.connect(self.db_path, timeout=self.timeout) as db:
                await db.execute(
                    f"""
                    INSERT OR REPLACE INTO {self.conversations_table}
                    (conversation_id, session_id, flow_id, status, current_step, state_data, metadata, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, julianday('now'))
                """,
                    (
                        conversation_id,
                        state.get("session_id"),
                        state.get("flow_id"),
                        state.get("status"),
                        state.get("current_step"),
                        json.dumps(state),
                        json.dumps(state.get("metadata", {})),
                    ),
                )
                await db.commit()

                # Periodic cleanup
                await self._maybe_cleanup()

                return True

        except Exception as e:
            logger.error(f"Failed to save conversation state {conversation_id}: {e}")
            return False

    async def load_conversation_state(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """Load conversation state from SQLite"""
        await self.initialize()

        try:
            async with aiosqlite.connect(self.db_path, timeout=self.timeout) as db:
                async with db.execute(
                    f"""
                    SELECT state_data, metadata FROM {self.conversations_table}
                    WHERE conversation_id = ?
                """,
                    (conversation_id,),
                ) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        state = json.loads(row[0])
                        if row[1]:
                            state["metadata"] = json.loads(row[1])
                        return state
                    return None

        except Exception as e:
            logger.error(f"Failed to load conversation state {conversation_id}: {e}")
            return None

    async def save_step_execution(self, conversation_id: str, step_data: Dict[str, Any]) -> bool:
        """Save step execution details"""
        await self.initialize()

        try:
            async with aiosqlite.connect(self.db_path, timeout=self.timeout) as db:
                await db.execute(
                    f"""
                    INSERT OR REPLACE INTO {self.steps_table}
                    (step_id, conversation_id, step_type, agent_id, input_data, 
                     output_data, execution_start, execution_end, status, error_message, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        step_data.get("step_id"),
                        conversation_id,
                        step_data.get("step_type"),
                        step_data.get("agent_id"),
                        json.dumps(step_data.get("input_data")),
                        json.dumps(step_data.get("output_data")),
                        step_data.get("execution_start"),
                        step_data.get("execution_end"),
                        step_data.get("status"),
                        step_data.get("error_message"),
                        json.dumps(step_data.get("metadata", {})),
                    ),
                )
                await db.commit()
                return True

        except Exception as e:
            logger.error(f"Failed to save step execution for {conversation_id}: {e}")
            return False

    async def create_checkpoint(
        self, conversation_id: str, step_id: str, state_snapshot: Dict[str, Any]
    ) -> Optional[str]:
        """Create a checkpoint for rollback capability"""
        await self.initialize()

        checkpoint_id = f"{conversation_id}_{step_id}_{int(time.time())}"

        try:
            async with aiosqlite.connect(self.db_path, timeout=self.timeout) as db:
                await db.execute(
                    f"""
                    INSERT INTO {self.checkpoints_table}
                    (checkpoint_id, conversation_id, step_id, state_snapshot, metadata)
                    VALUES (?, ?, ?, ?, ?)
                """,
                    (
                        checkpoint_id,
                        conversation_id,
                        step_id,
                        json.dumps(state_snapshot),
                        json.dumps({"created_timestamp": time.time()}),
                    ),
                )
                await db.commit()

                return checkpoint_id

        except Exception as e:
            logger.error(f"Failed to create checkpoint for {conversation_id}: {e}")
            return None

    async def rollback_to_checkpoint(self, checkpoint_id: str) -> Optional[Dict[str, Any]]:
        """Rollback to a specific checkpoint"""
        await self.initialize()

        try:
            async with aiosqlite.connect(self.db_path, timeout=self.timeout) as db:
                async with db.execute(
                    f"""
                    SELECT state_snapshot FROM {self.checkpoints_table}
                    WHERE checkpoint_id = ?
                """,
                    (checkpoint_id,),
                ) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        return json.loads(row[0])
                    return None

        except Exception as e:
            logger.error(f"Failed to rollback to checkpoint {checkpoint_id}: {e}")
            return None

    async def list_checkpoints(self, conversation_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """List available checkpoints for a conversation"""
        await self.initialize()

        try:
            async with aiosqlite.connect(self.db_path, timeout=self.timeout) as db:
                async with db.execute(
                    f"""
                    SELECT checkpoint_id, step_id, created_at, metadata FROM {self.checkpoints_table}
                    WHERE conversation_id = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                """,
                    (conversation_id, limit),
                ) as cursor:
                    rows = await cursor.fetchall()

                    checkpoints = []
                    for row in rows:
                        checkpoint = {
                            "checkpoint_id": row[0],
                            "step_id": row[1],
                            "created_at": row[2],
                            "metadata": json.loads(row[3]) if row[3] else {},
                        }
                        checkpoints.append(checkpoint)

                    return checkpoints

        except Exception as e:
            logger.error(f"Failed to list checkpoints for {conversation_id}: {e}")
            return []

    async def save_session_data(
        self, session_id: str, user_id: str, session_data: Dict[str, Any]
    ) -> bool:
        """Save session data"""
        await self.initialize()

        try:
            async with aiosqlite.connect(self.db_path, timeout=self.timeout) as db:
                await db.execute(
                    f"""
                    INSERT OR REPLACE INTO {self.sessions_table}
                    (session_id, user_id, session_data, last_activity)
                    VALUES (?, ?, ?, julianday('now'))
                """,
                    (session_id, user_id, json.dumps(session_data)),
                )
                await db.commit()
                return True

        except Exception as e:
            logger.error(f"Failed to save session data {session_id}: {e}")
            return False

    async def load_session_data(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Load session data"""
        await self.initialize()

        try:
            async with aiosqlite.connect(self.db_path, timeout=self.timeout) as db:
                async with db.execute(
                    f"""
                    SELECT user_id, session_data FROM {self.sessions_table}
                    WHERE session_id = ?
                """,
                    (session_id,),
                ) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        return {
                            "user_id": row[0],
                            "session_data": json.loads(row[1]) if row[1] else {},
                        }
                    return None

        except Exception as e:
            logger.error(f"Failed to load session data {session_id}: {e}")
            return None

    async def get_conversation_status(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """Get conversation status and progress"""
        await self.initialize()

        try:
            async with aiosqlite.connect(self.db_path, timeout=self.timeout) as db:
                # Get conversation info
                async with db.execute(
                    f"""
                    SELECT status, current_step, created_at, updated_at, metadata 
                    FROM {self.conversations_table}
                    WHERE conversation_id = ?
                """,
                    (conversation_id,),
                ) as cursor:
                    conv_row = await cursor.fetchone()
                    if not conv_row:
                        return None

                # Get step count
                async with db.execute(
                    f"""
                    SELECT COUNT(*) FROM {self.steps_table}
                    WHERE conversation_id = ? AND status = 'completed'
                """,
                    (conversation_id,),
                ) as cursor:
                    completed_steps = (await cursor.fetchone())[0]

                async with db.execute(
                    f"""
                    SELECT COUNT(*) FROM {self.steps_table}
                    WHERE conversation_id = ?
                """,
                    (conversation_id,),
                ) as cursor:
                    total_steps = (await cursor.fetchone())[0]

                # Calculate progress
                progress = completed_steps / total_steps if total_steps > 0 else 0.0

                status = {
                    "conversation_id": conversation_id,
                    "status": conv_row[0],
                    "current_step": conv_row[1],
                    "progress": progress,
                    "completed_steps": completed_steps,
                    "total_steps": total_steps,
                    "created_at": conv_row[2],
                    "last_updated": conv_row[3],
                    "metadata": json.loads(conv_row[4]) if conv_row[4] else {},
                }

                return status

        except Exception as e:
            logger.error(f"Failed to get conversation status {conversation_id}: {e}")
            return None

    async def _maybe_cleanup(self):
        """Perform periodic cleanup if needed"""
        current_time = time.time()
        if current_time - self._last_cleanup > self.cleanup_interval:
            await self.cleanup_expired_data()
            self._last_cleanup = current_time

    async def cleanup_expired_data(self):
        """Clean up expired conversations, steps, and checkpoints"""
        await self.initialize()

        try:
            current_time = time.time()
            conversation_cutoff = current_time - self.conversation_ttl
            checkpoint_cutoff = current_time - self.checkpoint_ttl
            session_cutoff = current_time - self.session_ttl

            # Convert to Julian days for SQLite
            conv_cutoff_julian = conversation_cutoff / 86400.0 + 2440587.5
            checkpoint_cutoff_julian = checkpoint_cutoff / 86400.0 + 2440587.5
            session_cutoff_julian = session_cutoff / 86400.0 + 2440587.5

            async with aiosqlite.connect(self.db_path, timeout=self.timeout) as db:
                # Clean up old conversations (cascades to steps)
                await db.execute(
                    f"""
                    DELETE FROM {self.conversations_table}
                    WHERE updated_at < ?
                """,
                    (conv_cutoff_julian,),
                )

                # Clean up old checkpoints
                await db.execute(
                    f"""
                    DELETE FROM {self.checkpoints_table}
                    WHERE created_at < ?
                """,
                    (checkpoint_cutoff_julian,),
                )

                # Clean up old sessions
                await db.execute(
                    f"""
                    DELETE FROM {self.sessions_table}
                    WHERE last_activity < ?
                """,
                    (session_cutoff_julian,),
                )

                await db.commit()

                # Vacuum the database to reclaim space
                if self.auto_vacuum:
                    await db.execute("PRAGMA incremental_vacuum")

                logger.debug("SQLite workflow persistence cleanup completed")

        except Exception as e:
            logger.error(f"Failed to cleanup expired workflow data: {e}")

    async def get_database_stats(self) -> Dict[str, Any]:
        """Get database statistics"""
        await self.initialize()

        try:
            async with aiosqlite.connect(self.db_path, timeout=self.timeout) as db:
                stats = {}

                # Get table counts
                for table_name in [
                    self.conversations_table,
                    self.steps_table,
                    self.checkpoints_table,
                    self.sessions_table,
                ]:
                    async with db.execute(f"SELECT COUNT(*) FROM {table_name}") as cursor:
                        count = (await cursor.fetchone())[0]
                        stats[f"{table_name}_count"] = count

                # Get database file size
                stats["database_size_bytes"] = os.path.getsize(self.db_path)
                stats["database_path"] = self.db_path

                # Get page info
                async with db.execute("PRAGMA page_count") as cursor:
                    page_count = (await cursor.fetchone())[0]
                async with db.execute("PRAGMA page_size") as cursor:
                    page_size = (await cursor.fetchone())[0]

                stats["page_count"] = page_count
                stats["page_size"] = page_size
                stats["total_pages_size"] = page_count * page_size

                return stats

        except Exception as e:
            logger.error(f"Failed to get database stats: {e}")
            return {}

    async def close(self):
        """Close the persistence backend"""
        # SQLite connections are closed automatically in context managers
        # This method is for compatibility with other backends
        logger.debug("SQLite workflow persistence closed")
