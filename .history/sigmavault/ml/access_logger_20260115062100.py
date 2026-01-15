"""
Access Pattern Logger for ML Training
=====================================

Logs file access events for machine learning model training.
Privacy-preserving: only metadata logged, no file contents.

Copyright (c) 2025 ΣVAULT. All Rights Reserved.
Agents: @TENSOR @NEURAL
"""

import hashlib
import sqlite3
import threading
from collections import deque
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Literal
import json


@dataclass
class AccessEvent:
    """
    Single file access event for ML training.
    
    Privacy-preserving: file paths are hashed, contents never logged.
    """
    
    timestamp: datetime
    vault_id: str
    file_path_hash: str  # SHA-256 hash of file path
    operation: Literal["read", "write", "stat", "delete"]
    bytes_accessed: int
    duration_ms: float
    user_id_hash: str  # Hashed user identifier
    device_fingerprint: str
    ip_hash: Optional[str]  # Hashed IP address
    success: bool
    error_code: Optional[str] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for storage."""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'AccessEvent':
        """Reconstruct from dictionary."""
        data['timestamp'] = datetime.fromisoformat(data['timestamp'])
        return cls(**data)


class AccessLogger:
    """
    Privacy-preserving access pattern logger for ML training.
    
    Features:
    - SQLite backend for persistent storage
    - Ring buffer for memory efficiency
    - Automatic cleanup of old data
    - Thread-safe operations
    - Privacy: hashed identifiers only
    
    Example:
        >>> logger = AccessLogger(vault_path="/secure/vault")
        >>> event = AccessEvent(
        ...     timestamp=datetime.now(),
        ...     vault_id="vault-123",
        ...     file_path_hash=hashlib.sha256(b"/secret/file").hexdigest(),
        ...     operation="read",
        ...     bytes_accessed=4096,
        ...     duration_ms=12.5,
        ...     user_id_hash="hash-user-123",
        ...     device_fingerprint="desktop-001",
        ...     ip_hash=None,
        ...     success=True
        ... )
        >>> logger.log_event(event)
    """
    
    def __init__(
        self,
        vault_path: Path,
        db_name: str = "access_logs.db",
        buffer_size: int = 10000,
        retention_days: int = 90
    ):
        """
        Initialize access logger.
        
        Args:
            vault_path: Path to vault directory
            db_name: SQLite database filename
            buffer_size: Size of in-memory ring buffer
            retention_days: Days to retain logs before cleanup
        """
        self.vault_path = Path(vault_path)
        self.db_path = self.vault_path / ".ml" / db_name
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        self.buffer_size = buffer_size
        self.retention_days = retention_days
        self._closed = False
        
        # In-memory ring buffer for fast access
        self.buffer: deque = deque(maxlen=buffer_size)
        self.buffer_lock = threading.Lock()
        
        # Initialize database
        self._init_db()
    
    def _init_db(self):
        """Initialize SQLite database schema."""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS access_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    vault_id TEXT NOT NULL,
                    file_path_hash TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    bytes_accessed INTEGER,
                    duration_ms REAL,
                    user_id_hash TEXT NOT NULL,
                    device_fingerprint TEXT,
                    ip_hash TEXT,
                    success INTEGER,
                    error_code TEXT
                )
            """)
            
            # Indexes for efficient queries
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp 
                ON access_events(timestamp)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_vault_id 
                ON access_events(vault_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_user 
                ON access_events(user_id_hash)
            """)
            
            conn.commit()
    
    def log_event(self, event: AccessEvent):
        """
        Log a single access event.
        
        Args:
            event: AccessEvent to log
        """
        # Add to ring buffer
        with self.buffer_lock:
            self.buffer.append(event)
        
        # Persist to database (async in production)
        self._persist_event(event)
    
    def _persist_event(self, event: AccessEvent):
        """Persist event to SQLite database."""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute("""
                INSERT INTO access_events (
                    timestamp, vault_id, file_path_hash, operation,
                    bytes_accessed, duration_ms, user_id_hash,
                    device_fingerprint, ip_hash, success, error_code
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                event.timestamp.isoformat(),
                event.vault_id,
                event.file_path_hash,
                event.operation,
                event.bytes_accessed,
                event.duration_ms,
                event.user_id_hash,
                event.device_fingerprint,
                event.ip_hash,
                int(event.success),
                event.error_code
            ))
            conn.commit()
    
    def get_recent_events(
        self,
        window: timedelta = timedelta(hours=1),
        vault_id: Optional[str] = None
    ) -> List[AccessEvent]:
        """
        Retrieve recent events from specified time window.
        
        Args:
            window: Time window to query
            vault_id: Optional filter by vault ID
            
        Returns:
            List of AccessEvent objects
        """
        cutoff = datetime.now() - window
        
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            
            if vault_id:
                cursor = conn.execute("""
                    SELECT * FROM access_events
                    WHERE timestamp >= ? AND vault_id = ?
                    ORDER BY timestamp DESC
                """, (cutoff.isoformat(), vault_id))
            else:
                cursor = conn.execute("""
                    SELECT * FROM access_events
                    WHERE timestamp >= ?
                    ORDER BY timestamp DESC
                """, (cutoff.isoformat(),))
            
            rows = cursor.fetchall()
        
        # Convert to AccessEvent objects
        events = []
        for row in rows:
            event_dict = dict(row)
            event_dict['timestamp'] = datetime.fromisoformat(event_dict['timestamp'])
            event_dict['success'] = bool(event_dict['success'])
            # Remove 'id' field from database (not in AccessEvent dataclass)
            event_dict.pop('id', None)
            events.append(AccessEvent(**event_dict))
        
        return events
    
    def get_buffer_events(self) -> List[AccessEvent]:
        """Get events from in-memory ring buffer."""
        with self.buffer_lock:
            return list(self.buffer)
    
    def cleanup_old_logs(self):
        """Remove logs older than retention period."""
        cutoff = datetime.now() - timedelta(days=self.retention_days)
        
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.execute("""
                DELETE FROM access_events
                WHERE timestamp < ?
            """, (cutoff.isoformat(),))
            deleted = cursor.rowcount
            conn.commit()
        
        return deleted
    
    def get_statistics(self, window: timedelta = timedelta(days=7)) -> Dict:
        """
        Get access statistics for specified time window.
        
        Args:
            window: Time window to analyze
            
        Returns:
            Dictionary of statistics
        """
        cutoff = datetime.now() - window
        
        with sqlite3.connect(str(self.db_path)) as conn:
            # Total events
            cursor = conn.execute("""
                SELECT COUNT(*) FROM access_events
                WHERE timestamp >= ?
            """, (cutoff.isoformat(),))
            total_events = cursor.fetchone()[0]
            
            # Events by operation
            cursor = conn.execute("""
                SELECT operation, COUNT(*) as count
                FROM access_events
                WHERE timestamp >= ?
                GROUP BY operation
            """, (cutoff.isoformat(),))
            by_operation = {row[0]: row[1] for row in cursor.fetchall()}
            
            # Success rate
            cursor = conn.execute("""
                SELECT success, COUNT(*) as count
                FROM access_events
                WHERE timestamp >= ?
                GROUP BY success
            """, (cutoff.isoformat(),))
            success_counts = {bool(row[0]): row[1] for row in cursor.fetchall()}
            success_rate = success_counts.get(True, 0) / total_events if total_events > 0 else 0
            
            # Unique users
            cursor = conn.execute("""
                SELECT COUNT(DISTINCT user_id_hash)
                FROM access_events
                WHERE timestamp >= ?
            """, (cutoff.isoformat(),))
            unique_users = cursor.fetchone()[0]
            
            # Unique files
            cursor = conn.execute("""
                SELECT COUNT(DISTINCT file_path_hash)
                FROM access_events
                WHERE timestamp >= ?
            """, (cutoff.isoformat(),))
            unique_files = cursor.fetchone()[0]
        
        return {
            'total_events': total_events,
            'by_operation': by_operation,
            'success_rate': success_rate,
            'unique_users': unique_users,
            'unique_files': unique_files,
            'window_days': window.days
        }
    
    @staticmethod
    def hash_identifier(identifier: str, salt: str = "") -> str:
        """
        Privacy-preserving hash of identifier.
        
        Args:
            identifier: User ID, file path, or IP address
            salt: Optional salt (use vault-specific salt)
            
        Returns:
            SHA-256 hash hex string
        """
        data = f"{identifier}:{salt}".encode('utf-8')
        return hashlib.sha256(data).hexdigest()
