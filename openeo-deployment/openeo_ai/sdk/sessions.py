# ABOUTME: Session management with SQLite persistence for conversation context.
# Handles session creation, retrieval, update, and cleanup operations.

"""
Session management for OpenEO AI Assistant.

Manages chat sessions with persistence to SQLite.
"""

import uuid
import json
import sqlite3
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path


class SessionManager:
    """
    Manage AI chat sessions with SQLite persistence.

    Provides session creation, retrieval, update, and deletion
    with context storage for conversation continuity.
    """

    def __init__(self, db_path: str = "data/openeo_ai.db"):
        """
        Initialize SessionManager.

        Args:
            db_path: Path to SQLite database file.
                     Use ":memory:" for in-memory database (testing).
        """
        self.db_path = db_path
        self._conn = None  # Persistent connection for :memory:

        # Ensure parent directory exists
        if db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        else:
            # For in-memory, keep a persistent connection
            self._conn = sqlite3.connect(":memory:")

        self._init_db()

    def _get_connection(self):
        """Get database connection."""
        if self._conn is not None:
            return self._conn
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        """Initialize database schema."""
        conn = self._get_connection()
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ai_sessions (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    last_active TEXT NOT NULL,
                    context TEXT,
                    sdk_session_id TEXT
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_sessions_user
                ON ai_sessions(user_id)
            """)
            # Migrate: add sdk_session_id column if table already exists without it
            try:
                conn.execute("ALTER TABLE ai_sessions ADD COLUMN sdk_session_id TEXT")
                conn.commit()
            except sqlite3.OperationalError:
                pass  # Column already exists
            # Index on sdk_session_id must come AFTER migration adds the column
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_sessions_sdk_id
                ON ai_sessions(sdk_session_id)
            """)
            conn.commit()
        finally:
            if self._conn is None:
                conn.close()

    def ensure_session(self, session_id: str, user_id: str = "default") -> str:
        """Ensure a session exists with the given ID. Creates if missing.

        Args:
            session_id: Specific session ID to use (from frontend)
            user_id: User identifier

        Returns:
            The session_id
        """
        existing = self.get_session(session_id)
        if existing:
            return session_id
        now = datetime.utcnow().isoformat()
        conn = self._get_connection()
        try:
            conn.execute(
                """
                INSERT OR IGNORE INTO ai_sessions (id, user_id, created_at, last_active, context)
                VALUES (?, ?, ?, ?, ?)
                """,
                (session_id, user_id, now, now, json.dumps({}))
            )
            conn.commit()
        finally:
            if self._conn is None:
                conn.close()
        return session_id

    def create_session(self, user_id: str) -> str:
        """
        Create a new session.

        Args:
            user_id: User identifier

        Returns:
            New session ID (UUID string)
        """
        session_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()

        conn = self._get_connection()
        try:
            conn.execute(
                """
                INSERT INTO ai_sessions (id, user_id, created_at, last_active, context)
                VALUES (?, ?, ?, ?, ?)
                """,
                (session_id, user_id, now, now, json.dumps({}))
            )
            conn.commit()
        finally:
            if self._conn is None:
                conn.close()

        return session_id

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve session by ID.

        Args:
            session_id: Session identifier

        Returns:
            Session dict or None if not found
        """
        conn = self._get_connection()
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM ai_sessions WHERE id = ?",
                (session_id,)
            )
            row = cursor.fetchone()

            if row:
                result = {
                    "id": row["id"],
                    "user_id": row["user_id"],
                    "created_at": row["created_at"],
                    "last_active": row["last_active"],
                    "context": json.loads(row["context"] or "{}"),
                }
                # sdk_session_id may not exist in old schemas
                try:
                    result["sdk_session_id"] = row["sdk_session_id"]
                except (IndexError, KeyError):
                    result["sdk_session_id"] = None
                return result
            return None
        finally:
            if self._conn is None:
                conn.close()

    def update_session(self, session_id: str, user_id: str) -> bool:
        """
        Update session last_active timestamp.

        Args:
            session_id: Session identifier
            user_id: User identifier (for verification)

        Returns:
            True if updated, False if not found
        """
        now = datetime.utcnow().isoformat()

        conn = self._get_connection()
        try:
            cursor = conn.execute(
                """
                UPDATE ai_sessions
                SET last_active = ?
                WHERE id = ? AND user_id = ?
                """,
                (now, session_id, user_id)
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            if self._conn is None:
                conn.close()

    def update_context(self, session_id: str, context: Dict[str, Any]) -> bool:
        """
        Update session context.

        Args:
            session_id: Session identifier
            context: Context data to store

        Returns:
            True if updated, False if not found
        """
        now = datetime.utcnow().isoformat()

        conn = self._get_connection()
        try:
            cursor = conn.execute(
                """
                UPDATE ai_sessions
                SET context = ?, last_active = ?
                WHERE id = ?
                """,
                (json.dumps(context), now, session_id)
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            if self._conn is None:
                conn.close()

    def list_sessions(
        self,
        user_id: str,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        List sessions for a user.

        Args:
            user_id: User identifier
            limit: Maximum number of sessions to return

        Returns:
            List of session dicts
        """
        conn = self._get_connection()
        try:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT * FROM ai_sessions
                WHERE user_id = ?
                ORDER BY last_active DESC
                LIMIT ?
                """,
                (user_id, limit)
            )

            return [
                {
                    "id": row["id"],
                    "user_id": row["user_id"],
                    "created_at": row["created_at"],
                    "last_active": row["last_active"],
                    "context": json.loads(row["context"] or "{}")
                }
                for row in cursor.fetchall()
            ]
        finally:
            if self._conn is None:
                conn.close()

    def set_sdk_session_id(self, session_id: str, sdk_session_id: str) -> bool:
        """Store the Claude SDK session ID for resume support.

        Args:
            session_id: Our session identifier
            sdk_session_id: The SDK's session ID from ResultMessage

        Returns:
            True if updated, False if session not found
        """
        now = datetime.utcnow().isoformat()
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                """
                UPDATE ai_sessions
                SET sdk_session_id = ?, last_active = ?
                WHERE id = ?
                """,
                (sdk_session_id, now, session_id)
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            if self._conn is None:
                conn.close()

    def get_sdk_session_id(self, session_id: str) -> Optional[str]:
        """Get the SDK session ID for a given session.

        Args:
            session_id: Our session identifier

        Returns:
            SDK session ID string, or None if not found/not set
        """
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                "SELECT sdk_session_id FROM ai_sessions WHERE id = ?",
                (session_id,)
            )
            row = cursor.fetchone()
            return row[0] if row and row[0] else None
        finally:
            if self._conn is None:
                conn.close()

    def delete_session(self, session_id: str) -> bool:
        """
        Delete a session.

        Args:
            session_id: Session identifier

        Returns:
            True if deleted, False if not found
        """
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                "DELETE FROM ai_sessions WHERE id = ?",
                (session_id,)
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            if self._conn is None:
                conn.close()

    def delete_older_than(self, threshold: datetime) -> int:
        """
        Delete sessions older than threshold.

        Args:
            threshold: Delete sessions with last_active before this time

        Returns:
            Number of deleted sessions
        """
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                "DELETE FROM ai_sessions WHERE last_active < ?",
                (threshold.isoformat(),)
            )
            conn.commit()
            return cursor.rowcount
        finally:
            if self._conn is None:
                conn.close()
