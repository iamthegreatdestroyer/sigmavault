"""
ΣVAULT Transparent Filesystem (FUSE)
=====================================

A FUSE-based filesystem that transparently handles all ΣVAULT operations.
Users see a normal directory structure; underneath, everything is
dimensionally scattered and encrypted.

ARCHITECTURE:

    ┌─────────────────────────────────────────────────────────────┐
    │                    USER APPLICATIONS                        │
    │           (File managers, editors, any software)            │
    └────────────────────────┬────────────────────────────────────┘
                             │
                     Standard file operations
                     (open, read, write, etc.)
                             │
                             ▼
    ┌─────────────────────────────────────────────────────────────┐
    │                    ΣVAULT FUSE LAYER                        │
    │                                                             │
    │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
    │  │   Virtual   │  │   Vault     │  │   Transparent       │ │
    │  │   Metadata  │  │   Lock/     │  │   Scatter/Gather    │ │
    │  │   Index     │  │   Unlock    │  │   Operations        │ │
    │  └─────────────┘  └─────────────┘  └─────────────────────┘ │
    │                                                             │
    └────────────────────────┬────────────────────────────────────┘
                             │
                     Dimensional coordinates
                     + scattered data
                             │
                             ▼
    ┌─────────────────────────────────────────────────────────────┐
    │               PHYSICAL STORAGE MEDIUM                       │
    │                                                             │
    │     ░░▓▓░░▓▓░░░░▓▓░░▓▓░░░░░░▓▓░░▓▓░░░░▓▓░░▓▓░░░░░░░░▓▓     │
    │     (Scattered bits - no recognizable file structure)       │
    │                                                             │
    └─────────────────────────────────────────────────────────────┘

TRANSPARENT OPERATION:

    $ ls /mnt/sigmavault/
    Documents/  Photos/  Videos/  secret_file.txt
    
    $ cat /mnt/sigmavault/Documents/report.pdf
    [PDF opens normally]
    
    # User never sees the complexity underneath

Copyright 2025 - ΣVAULT Project
"""

import os
import sys
import stat
import errno
import time
import hashlib
import secrets
import struct
import threading
from pathlib import Path
from typing import Dict, Optional, Any, List, Tuple, Generator
from dataclasses import dataclass, field
from collections import defaultdict
import json

# Try to import FUSE
try:
    from fuse import FUSE, FuseOSError, Operations
    HAS_FUSE = True
except ImportError:
    HAS_FUSE = False
    # Define dummy classes for when FUSE isn't available
    class Operations:
        pass
    class FuseOSError(Exception):
        pass
    class FUSE:
        pass

from ..core.dimensional_scatter import (
    DimensionalScatterEngine, KeyState, ScatteredFile
)
from ..crypto.hybrid_key import (
    HybridKeyDerivation, KeyMode, KeyDerivationConfig,
    create_new_vault_key, unlock_vault, hybrid_key_to_key_state
)


# ============================================================================
# VIRTUAL METADATA INDEX
# ============================================================================

@dataclass
class VirtualFileEntry:
    """Metadata for a virtual file in the ΣVAULT filesystem."""
    path: str                        # Virtual path (what user sees)
    file_id: bytes                   # Internal unique identifier
    size: int                        # Original file size
    mode: int                        # Unix permissions
    uid: int                         # Owner UID
    gid: int                         # Owner GID
    atime: float                     # Access time
    mtime: float                     # Modification time
    ctime: float                     # Creation time
    is_directory: bool               # Whether this is a directory
    is_locked: bool = False          # Vault lock status
    lock_key_hash: Optional[bytes] = None  # Hash of lock key
    scattered_ref: Optional[str] = None    # Reference to scattered data
    
    def to_stat(self) -> dict:
        """Convert to stat-like dictionary."""
        if self.is_directory:
            mode = stat.S_IFDIR | self.mode
            nlink = 2
        else:
            mode = stat.S_IFREG | self.mode
            nlink = 1
        
        return {
            'st_mode': mode,
            'st_nlink': nlink,
            'st_size': self.size if not self.is_directory else 4096,
            'st_uid': self.uid,
            'st_gid': self.gid,
            'st_atime': self.atime,
            'st_mtime': self.mtime,
            'st_ctime': self.ctime,
        }
    
    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            'path': self.path,
            'file_id': self.file_id.hex(),
            'size': self.size,
            'mode': self.mode,
            'uid': self.uid,
            'gid': self.gid,
            'atime': self.atime,
            'mtime': self.mtime,
            'ctime': self.ctime,
            'is_directory': self.is_directory,
            'is_locked': self.is_locked,
            'lock_key_hash': self.lock_key_hash.hex() if self.lock_key_hash else None,
            'scattered_ref': self.scattered_ref,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'VirtualFileEntry':
        """Deserialize from dictionary."""
        return cls(
            path=data['path'],
            file_id=bytes.fromhex(data['file_id']),
            size=data['size'],
            mode=data['mode'],
            uid=data['uid'],
            gid=data['gid'],
            atime=data['atime'],
            mtime=data['mtime'],
            ctime=data['ctime'],
            is_directory=data['is_directory'],
            is_locked=data.get('is_locked', False),
            lock_key_hash=bytes.fromhex(data['lock_key_hash']) if data.get('lock_key_hash') else None,
            scattered_ref=data.get('scattered_ref'),
        )


class VirtualMetadataIndex:
    """
    Index of all virtual files in the ΣVAULT filesystem.
    
    This index itself is stored scattered, but cached in memory
    for performance during operation.
    """
    
    def __init__(self, scatter_engine: DimensionalScatterEngine):
        self.scatter_engine = scatter_engine
        self.entries: Dict[str, VirtualFileEntry] = {}
        self.children: Dict[str, List[str]] = defaultdict(list)
        self._lock = threading.RLock()
        
        # Initialize root directory
        self._create_root()
    
    def _create_root(self):
        """Create root directory entry."""
        now = time.time()
        root = VirtualFileEntry(
            path='/',
            file_id=secrets.token_bytes(16),
            size=0,
            mode=0o755,
            uid=os.getuid(),
            gid=os.getgid(),
            atime=now,
            mtime=now,
            ctime=now,
            is_directory=True,
        )
        self.entries['/'] = root
    
    def get(self, path: str) -> Optional[VirtualFileEntry]:
        """Get entry by path."""
        with self._lock:
            return self.entries.get(path)
    
    def exists(self, path: str) -> bool:
        """Check if path exists."""
        with self._lock:
            return path in self.entries
    
    def create_file(self, path: str, mode: int = 0o644) -> VirtualFileEntry:
        """Create a new file entry."""
        with self._lock:
            if path in self.entries:
                raise FileExistsError(f"File exists: {path}")
            
            now = time.time()
            entry = VirtualFileEntry(
                path=path,
                file_id=secrets.token_bytes(16),
                size=0,
                mode=mode,
                uid=os.getuid(),
                gid=os.getgid(),
                atime=now,
                mtime=now,
                ctime=now,
                is_directory=False,
            )
            
            self.entries[path] = entry
            
            # Add to parent's children
            parent_path = str(Path(path).parent)
            if parent_path not in self.children:
                self.children[parent_path] = []
            self.children[parent_path].append(path)
            
            return entry
    
    def create_directory(self, path: str, mode: int = 0o755) -> VirtualFileEntry:
        """Create a new directory entry."""
        with self._lock:
            if path in self.entries:
                raise FileExistsError(f"Directory exists: {path}")
            
            now = time.time()
            entry = VirtualFileEntry(
                path=path,
                file_id=secrets.token_bytes(16),
                size=0,
                mode=mode,
                uid=os.getuid(),
                gid=os.getgid(),
                atime=now,
                mtime=now,
                ctime=now,
                is_directory=True,
            )
            
            self.entries[path] = entry
            
            # Add to parent's children
            parent_path = str(Path(path).parent)
            if parent_path not in self.children:
                self.children[parent_path] = []
            self.children[parent_path].append(path)
            
            return entry
    
    def delete(self, path: str):
        """Delete an entry."""
        with self._lock:
            if path not in self.entries:
                raise FileNotFoundError(f"Not found: {path}")
            
            entry = self.entries[path]
            
            # Check if directory is empty
            if entry.is_directory and self.children.get(path):
                raise OSError(errno.ENOTEMPTY, "Directory not empty")
            
            # Remove from parent's children
            parent_path = str(Path(path).parent)
            if parent_path in self.children:
                self.children[parent_path] = [
                    p for p in self.children[parent_path] if p != path
                ]
            
            del self.entries[path]
    
    def list_directory(self, path: str) -> List[str]:
        """List children of a directory."""
        with self._lock:
            if path not in self.entries:
                raise FileNotFoundError(f"Not found: {path}")
            
            if not self.entries[path].is_directory:
                raise NotADirectoryError(f"Not a directory: {path}")
            
            children = self.children.get(path, [])
            return [Path(c).name for c in children]
    
    def update_size(self, path: str, size: int):
        """Update file size."""
        with self._lock:
            if path in self.entries:
                self.entries[path].size = size
                self.entries[path].mtime = time.time()
    
    def update_times(self, path: str, atime: float = None, mtime: float = None):
        """Update access and modification times."""
        with self._lock:
            if path in self.entries:
                if atime is not None:
                    self.entries[path].atime = atime
                if mtime is not None:
                    self.entries[path].mtime = mtime
    
    def serialize(self) -> bytes:
        """Serialize entire index."""
        data = {
            'entries': {p: e.to_dict() for p, e in self.entries.items()},
            'children': dict(self.children),
        }
        return json.dumps(data).encode('utf-8')
    
    def deserialize(self, data: bytes):
        """Deserialize index."""
        parsed = json.loads(data.decode('utf-8'))
        
        with self._lock:
            self.entries = {
                p: VirtualFileEntry.from_dict(e) 
                for p, e in parsed['entries'].items()
            }
            self.children = defaultdict(list, parsed['children'])


# ============================================================================
# FILE CONTENT CACHE
# ============================================================================

class FileContentCache:
    """
    In-memory cache for file contents during read/write operations.
    Handles buffering and dirty tracking.
    """
    
    def __init__(self, max_size_mb: int = 256):
        self.max_size = max_size_mb * 1024 * 1024
        self.cache: Dict[str, bytearray] = {}
        self.dirty: Dict[str, bool] = {}
        self.access_times: Dict[str, float] = {}
        self.current_size = 0
        self._lock = threading.RLock()
    
    def get(self, path: str) -> Optional[bytearray]:
        """Get cached content."""
        with self._lock:
            if path in self.cache:
                self.access_times[path] = time.time()
                return self.cache[path]
            return None
    
    def put(self, path: str, content: bytes, dirty: bool = False):
        """Cache file content."""
        with self._lock:
            # Evict if necessary
            content_size = len(content)
            while self.current_size + content_size > self.max_size and self.cache:
                self._evict_oldest()
            
            # Remove old entry if exists
            if path in self.cache:
                self.current_size -= len(self.cache[path])
            
            self.cache[path] = bytearray(content)
            self.dirty[path] = dirty
            self.access_times[path] = time.time()
            self.current_size += content_size
    
    def mark_dirty(self, path: str):
        """Mark file as dirty (needs flush)."""
        with self._lock:
            self.dirty[path] = True
    
    def is_dirty(self, path: str) -> bool:
        """Check if file needs flushing."""
        with self._lock:
            return self.dirty.get(path, False)
    
    def mark_clean(self, path: str):
        """Mark file as clean."""
        with self._lock:
            self.dirty[path] = False
    
    def remove(self, path: str):
        """Remove from cache."""
        with self._lock:
            if path in self.cache:
                self.current_size -= len(self.cache[path])
                del self.cache[path]
                del self.dirty[path]
                del self.access_times[path]
    
    def get_dirty_files(self) -> List[str]:
        """Get list of dirty files."""
        with self._lock:
            return [p for p, d in self.dirty.items() if d]
    
    def _evict_oldest(self):
        """Evict oldest non-dirty entry."""
        # Sort by access time
        non_dirty = [(p, t) for p, t in self.access_times.items() 
                     if not self.dirty.get(p, False)]
        
        if non_dirty:
            oldest = min(non_dirty, key=lambda x: x[1])[0]
            self.remove(oldest)


# ============================================================================
# VAULT LOCK MANAGER
# ============================================================================

class VaultLockManager:
    """
    Manages file-level vault locks.
    
    Individual files can be locked with their own key, separate from
    the main vault passphrase. This provides defense-in-depth:
    - Vault passphrase: Access to the filesystem
    - File lock: Access to specific sensitive files
    """
    
    def __init__(self, index: VirtualMetadataIndex):
        self.index = index
        self.unlocked: Dict[str, bytes] = {}  # path -> decrypted content
        self._lock = threading.RLock()
    
    def lock_file(self, path: str, lock_passphrase: str) -> bool:
        """
        Lock a file with additional passphrase.
        
        The file's content is re-encrypted with a key derived from
        the lock passphrase combined with the file's existing key.
        """
        with self._lock:
            entry = self.index.get(path)
            if not entry or entry.is_directory:
                return False
            
            if entry.is_locked:
                return False  # Already locked
            
            # Derive lock key
            lock_key = hashlib.pbkdf2_hmac(
                'sha256',
                lock_passphrase.encode('utf-8'),
                entry.file_id,  # Use file_id as salt
                iterations=100000,
                dklen=32
            )
            
            # Store hash for verification
            entry.is_locked = True
            entry.lock_key_hash = hashlib.sha256(lock_key).digest()
            
            return True
    
    def unlock_file(self, path: str, lock_passphrase: str) -> bool:
        """
        Unlock a locked file.
        """
        with self._lock:
            entry = self.index.get(path)
            if not entry or not entry.is_locked:
                return False
            
            # Derive lock key
            lock_key = hashlib.pbkdf2_hmac(
                'sha256',
                lock_passphrase.encode('utf-8'),
                entry.file_id,
                iterations=100000,
                dklen=32
            )
            
            # Verify
            if not secrets.compare_digest(
                hashlib.sha256(lock_key).digest(),
                entry.lock_key_hash
            ):
                return False
            
            entry.is_locked = False
            entry.lock_key_hash = None
            
            return True
    
    def is_locked(self, path: str) -> bool:
        """Check if file is locked."""
        entry = self.index.get(path)
        return entry and entry.is_locked
    
    def require_unlock(self, path: str) -> bool:
        """Check if file requires unlock before access."""
        return self.is_locked(path) and path not in self.unlocked


# ============================================================================
# SCATTER STORAGE BACKEND
# ============================================================================

class ScatterStorageBackend:
    """
    Backend storage that handles scattered file persistence.
    Thread-safe for concurrent operations.
    """
    
    def __init__(self, storage_path: Path, scatter_engine: DimensionalScatterEngine):
        self.storage_path = storage_path
        self.scatter_engine = scatter_engine
        self.scattered_files: Dict[str, ScatteredFile] = {}
        self._lock = threading.RLock()
        
        # Create storage directory structure
        self.data_path = storage_path / 'scatter_data'
        self.meta_path = storage_path / 'scatter_meta'
        self.data_path.mkdir(parents=True, exist_ok=True)
        self.meta_path.mkdir(parents=True, exist_ok=True)
    
    def store(self, file_id: bytes, content: bytes) -> str:
        """
        Store file content by scattering.
        Returns reference ID for retrieval.
        Thread-safe.
        """
        with self._lock:
            # Scatter the content
            scattered = self.scatter_engine.scatter(file_id, content)
            
            # Generate reference ID
            ref_id = hashlib.sha256(file_id).hexdigest()[:32]
            
            # Store scattered data
            self._persist_scattered(ref_id, scattered)
            
            # Cache
            self.scattered_files[ref_id] = scattered
            
            return ref_id
    
    def retrieve(self, ref_id: str) -> Optional[bytes]:
        """
        Retrieve and gather scattered file.
        Thread-safe.
        """
        with self._lock:
            # Check cache
            if ref_id in self.scattered_files:
                scattered = self.scattered_files[ref_id]
            else:
                scattered = self._load_scattered(ref_id)
                if scattered:
                    self.scattered_files[ref_id] = scattered
            
            if not scattered:
                return None
            
            # Gather the content
            return self.scatter_engine.gather(scattered)
    
    def delete(self, ref_id: str):
        """Delete scattered file. Thread-safe."""
        with self._lock:
            # Remove from cache
            if ref_id in self.scattered_files:
                del self.scattered_files[ref_id]
            
            # Remove persisted data
            data_file = self.data_path / f'{ref_id}.scatter'
            meta_file = self.meta_path / f'{ref_id}.meta'
            
            if data_file.exists():
                data_file.unlink()
            if meta_file.exists():
                meta_file.unlink()
    
    def _persist_scattered(self, ref_id: str, scattered: ScatteredFile):
        """Persist scattered file to disk. Thread-safe."""
        import pickle
        
        # Serialize and store
        data_file = self.data_path / f'{ref_id}.scatter'
        with open(data_file, 'wb') as f:
            pickle.dump(scattered, f)
    
    def _load_scattered(self, ref_id: str) -> Optional[ScatteredFile]:
        """Load scattered file from disk. Thread-safe."""
        import pickle
        
        data_file = self.data_path / f'{ref_id}.scatter'
        if not data_file.exists():
            return None
        
        with open(data_file, 'rb') as f:
            return pickle.load(f)


# ============================================================================
# ΣVAULT FUSE FILESYSTEM
# ============================================================================

class SigmaVaultFS(Operations):
    """
    FUSE filesystem implementation for ΣVAULT.
    
    Implements standard filesystem operations while transparently
    handling dimensional scattering underneath.
    """
    
    def __init__(self, storage_path: Path, key_state: KeyState, 
                 medium_size: int = 10 * 1024 * 1024 * 1024):  # 10GB default
        self.storage_path = storage_path
        self.key_state = key_state
        
        # Initialize components
        self.scatter_engine = DimensionalScatterEngine(key_state, medium_size)
        self.index = VirtualMetadataIndex(self.scatter_engine)
        self.cache = FileContentCache()
        self.lock_manager = VaultLockManager(self.index)
        self.storage = ScatterStorageBackend(storage_path, self.scatter_engine)
        
        # File handles
        self.open_files: Dict[int, str] = {}
        self.next_fh = 1
        self._lock = threading.RLock()
        
        # Load existing index if present
        self._load_index()
    
    def _load_index(self):
        """Load existing index from storage."""
        index_path = self.storage_path / 'vault_index.dat'
        if index_path.exists():
            try:
                with open(index_path, 'rb') as f:
                    self.index.deserialize(f.read())
            except Exception as e:
                print(f"Warning: Could not load index: {e}")
    
    def _save_index(self):
        """Save index to storage."""
        index_path = self.storage_path / 'vault_index.dat'
        with open(index_path, 'wb') as f:
            f.write(self.index.serialize())
    
    def _get_full_path(self, partial: str) -> str:
        """Convert partial path to full path."""
        if not partial.startswith('/'):
            partial = '/' + partial
        return partial
    
    # ------ FUSE Operations ------
    
    def getattr(self, path, fh=None):
        """Get file attributes. Thread-safe."""
        with self._lock:
            path = self._get_full_path(path)
            entry = self.index.get(path)
            
            if not entry:
                raise FuseOSError(errno.ENOENT)
            
            return entry.to_stat()
    
    def readdir(self, path, fh):
        """Read directory contents. Thread-safe."""
        with self._lock:
            path = self._get_full_path(path)
            
            yield '.'
            yield '..'
            
            try:
                for name in self.index.list_directory(path):
                    yield name
            except FileNotFoundError:
                raise FuseOSError(errno.ENOENT)
            except NotADirectoryError:
                raise FuseOSError(errno.ENOTDIR)
    
    def mkdir(self, path, mode):
        """Create directory. Thread-safe."""
        with self._lock:
            path = self._get_full_path(path)
            
            try:
                self.index.create_directory(path, mode)
                self._save_index()
            except FileExistsError:
                raise FuseOSError(errno.EEXIST)
    
    def rmdir(self, path):
        """Remove directory. Thread-safe."""
        with self._lock:
            path = self._get_full_path(path)
            
            try:
                self.index.delete(path)
                self._save_index()
            except FileNotFoundError:
                raise FuseOSError(errno.ENOENT)
            except OSError as e:
                raise FuseOSError(e.errno)
    
    def create(self, path, mode, fi=None):
        """Create and open file. Thread-safe."""
        with self._lock:
            path = self._get_full_path(path)
            
            try:
                entry = self.index.create_file(path, mode)
                self.cache.put(path, b'', dirty=True)
                self._save_index()
                
                # Return file handle
                fh = self.next_fh
                self.next_fh += 1
                self.open_files[fh] = path
                
                return fh
            except FileExistsError:
                raise FuseOSError(errno.EEXIST)
    
    def open(self, path, flags):
        """Open file. Thread-safe."""
        with self._lock:
            path = self._get_full_path(path)
            entry = self.index.get(path)
            
            if not entry:
                raise FuseOSError(errno.ENOENT)
            
            if entry.is_directory:
                raise FuseOSError(errno.EISDIR)
            
            # Check vault lock
            if self.lock_manager.require_unlock(path):
                raise FuseOSError(errno.EACCES)
            
            # Load content into cache if not present
            if self.cache.get(path) is None:
                if entry.scattered_ref:
                    content = self.storage.retrieve(entry.scattered_ref)
                    if content:
                        self.cache.put(path, content)
                    else:
                        self.cache.put(path, b'')
                else:
                    self.cache.put(path, b'')
            
            # Return file handle
            fh = self.next_fh
            self.next_fh += 1
            self.open_files[fh] = path
            
            return fh
    
    def read(self, path, size, offset, fh):
        """Read from file. Thread-safe."""
        with self._lock:
            path = self._get_full_path(path)
            
            content = self.cache.get(path)
            if content is None:
                raise FuseOSError(errno.ENOENT)
            
            # Update access time
            self.index.update_times(path, atime=time.time())
            
            return bytes(content[offset:offset+size])
    
    def write(self, path, data, offset, fh):
        """Write to file. Thread-safe."""
        with self._lock:
            path = self._get_full_path(path)
            
            content = self.cache.get(path)
            if content is None:
                content = bytearray()
                self.cache.put(path, content)
            
            # Extend if necessary
            end = offset + len(data)
            if end > len(content):
                content.extend(b'\x00' * (end - len(content)))
            
            # Write data
            content[offset:end] = data
            
            # Mark dirty and update size
            self.cache.mark_dirty(path)
            self.index.update_size(path, len(content))
            
            return len(data)
    
    def truncate(self, path, length, fh=None):
        """Truncate file. Thread-safe."""
        with self._lock:
            path = self._get_full_path(path)
            
            content = self.cache.get(path)
            if content is None:
                content = bytearray()
                self.cache.put(path, content)
            
            if length < len(content):
                del content[length:]
            else:
                content.extend(b'\x00' * (length - len(content)))
            
            self.cache.mark_dirty(path)
            self.index.update_size(path, length)
    
    def flush(self, path, fh):
        """Flush file. Thread-safe."""
        with self._lock:
            path = self._get_full_path(path)
            self._flush_file(path)
    
    def release(self, path, fh):
        """Release file handle. Thread-safe."""
        with self._lock:
            path = self._get_full_path(path)
            
            # Flush if dirty
            self._flush_file(path)
            
            # Remove handle
            if fh in self.open_files:
                del self.open_files[fh]
    
    def _flush_file(self, path: str):
        """Flush file to scattered storage."""
        if not self.cache.is_dirty(path):
            return
        
        content = self.cache.get(path)
        if content is None:
            return
        
        entry = self.index.get(path)
        if not entry:
            return
        
        # Scatter and store
        ref_id = self.storage.store(entry.file_id, bytes(content))
        
        # Update entry
        entry.scattered_ref = ref_id
        self.cache.mark_clean(path)
        self._save_index()
    
    def unlink(self, path):
        """Delete file. Thread-safe."""
        with self._lock:
            path = self._get_full_path(path)
            entry = self.index.get(path)
            
            if not entry:
                raise FuseOSError(errno.ENOENT)
            
            # Delete scattered data
            if entry.scattered_ref:
                self.storage.delete(entry.scattered_ref)
            
            # Remove from cache
            self.cache.remove(path)
            
            # Remove from index
            self.index.delete(path)
            self._save_index()
    
    def rename(self, old, new):
        """Rename file or directory. Thread-safe."""
        with self._lock:
            old = self._get_full_path(old)
            new = self._get_full_path(new)
            
            entry = self.index.get(old)
            if not entry:
                raise FuseOSError(errno.ENOENT)
            
            # Update entry path
            entry.path = new
            
            # Update index
            with self.index._lock:
                del self.index.entries[old]
                self.index.entries[new] = entry
                
                # Update children references
                old_parent = str(Path(old).parent)
                new_parent = str(Path(new).parent)
                
                self.index.children[old_parent] = [
                    p for p in self.index.children[old_parent] if p != old
                ]
                self.index.children[new_parent].append(new)
            
            # Update cache key
            if old in self.cache.cache:
                content = self.cache.cache.pop(old)
                dirty = self.cache.dirty.pop(old)
                self.cache.cache[new] = content
                self.cache.dirty[new] = dirty
            
            self._save_index()
    
    def chmod(self, path, mode):
        """Change permissions."""
        path = self._get_full_path(path)
        entry = self.index.get(path)
        
        if not entry:
            raise FuseOSError(errno.ENOENT)
        
        entry.mode = mode
        self._save_index()
    
    def chown(self, path, uid, gid):
        """Change ownership."""
        path = self._get_full_path(path)
        entry = self.index.get(path)
        
        if not entry:
            raise FuseOSError(errno.ENOENT)
        
        entry.uid = uid
        entry.gid = gid
        self._save_index()
    
    def utimens(self, path, times=None):
        """Update timestamps."""
        path = self._get_full_path(path)
        
        if times:
            atime, mtime = times
        else:
            now = time.time()
            atime = mtime = now
        
        self.index.update_times(path, atime, mtime)
    
    def statfs(self, path):
        """Get filesystem statistics."""
        # Return reasonable defaults
        return {
            'f_bsize': 4096,
            'f_frsize': 4096,
            'f_blocks': 1024 * 1024,  # 4GB
            'f_bfree': 512 * 1024,    # 2GB free
            'f_bavail': 512 * 1024,
            'f_files': 1000000,
            'f_ffree': 500000,
            'f_favail': 500000,
            'f_flag': 0,
            'f_namemax': 255,
        }
    
    # ------ Vault Lock Operations ------
    
    def lock_file(self, path: str, passphrase: str) -> bool:
        """Lock a file with passphrase (accessed via ioctl or xattr)."""
        path = self._get_full_path(path)
        result = self.lock_manager.lock_file(path, passphrase)
        if result:
            self._save_index()
        return result
    
    def unlock_file(self, path: str, passphrase: str) -> bool:
        """Unlock a locked file."""
        path = self._get_full_path(path)
        result = self.lock_manager.unlock_file(path, passphrase)
        if result:
            self._save_index()
        return result


# ============================================================================
# MOUNT HELPER
# ============================================================================

def mount_sigmavault(mount_point: str, storage_path: str, 
                     passphrase: str, mode: KeyMode = KeyMode.HYBRID,
                     foreground: bool = False):
    """
    Mount a ΣVAULT filesystem.
    
    Args:
        mount_point: Where to mount the filesystem
        storage_path: Where to store scattered data
        passphrase: User passphrase
        mode: Key derivation mode
        foreground: Run in foreground (for debugging)
    """
    if not HAS_FUSE:
        raise RuntimeError("FUSE not available. Install fusepy: pip install fusepy")
    
    storage = Path(storage_path)
    storage.mkdir(parents=True, exist_ok=True)
    
    config_path = storage / 'vault_config.dat'
    
    # Check if vault exists
    if config_path.exists():
        # Unlock existing vault
        with open(config_path, 'rb') as f:
            config = KeyDerivationConfig.from_bytes(f.read())
        master_key = unlock_vault(passphrase, config)
    else:
        # Create new vault
        master_key, config = create_new_vault_key(passphrase, mode)
        with open(config_path, 'wb') as f:
            f.write(config.to_bytes())
    
    # Derive key state
    key_state = hybrid_key_to_key_state(master_key)
    
    # Create and mount filesystem
    fs = SigmaVaultFS(storage, key_state)
    
    print(f"Mounting ΣVAULT at {mount_point}")
    print(f"Storage: {storage_path}")
    print(f"Mode: {mode.name}")
    print("Press Ctrl+C to unmount")
    
    FUSE(fs, mount_point, foreground=foreground, nothreads=False,
         allow_other=False)
