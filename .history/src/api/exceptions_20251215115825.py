"""
Exception Types for Ryot LLM
============================

Custom exceptions for various components.
"""


class RSUError(Exception):
    """RSU-related error."""
    
    def __init__(self, message: str, context: str = ""):
        self.message = message
        self.context = context
        super().__init__(f"{context}: {message}" if context else message)


class ModelNotLoadedError(Exception):
    """Model not loaded error."""
    pass


class ContextTooLongError(Exception):
    """Context exceeds max length error."""
    pass


class CompressionError(Exception):
    """Compression failed error."""
    pass


class StorageError(Exception):
    """Storage operation failed error."""
    pass
