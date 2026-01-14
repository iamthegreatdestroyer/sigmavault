"""
ΣVAULT Security Module
======================

Security hardening utilities and cryptographic safeguards.

This module provides:
- Constant-time operations (timing attack prevention)
- Memory-bounded operations (exhaustion prevention)
- Thread safety utilities (race condition prevention)
- Safe integer operations (overflow prevention)
- Input validation
- Resource cleanup guarantees

Copyright 2026 - ΣVAULT Project
"""

from .hardening import (
    # Timing attack prevention
    constant_time_compare,
    constant_time_bytes_equal,
    constant_time_select,
    
    # Memory management
    MemoryBoundedBuffer,
    StreamingProcessor,
    
    # Thread safety
    RWLock,
    synchronized_method,
    
    # Safe operations
    safe_add,
    safe_multiply,
    clamp_to_range,
    
    # Validation
    validate_bytes_length,
    validate_file_size,
    
    # Resource management
    ManagedResource,
    
    # Verification
    verify_hardening,
)

__all__ = [
    # Timing attack prevention
    'constant_time_compare',
    'constant_time_bytes_equal',
    'constant_time_select',
    
    # Memory management
    'MemoryBoundedBuffer',
    'StreamingProcessor',
    
    # Thread safety
    'RWLock',
    'synchronized_method',
    
    # Safe operations
    'safe_add',
    'safe_multiply',
    'clamp_to_range',
    
    # Validation
    'validate_bytes_length',
    'validate_file_size',
    
    # Resource management
    'ManagedResource',
    
    # Verification
    'verify_hardening',
]
