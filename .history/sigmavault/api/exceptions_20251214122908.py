"""ΣVAULT Custom Exceptions"""

from typing import Optional


class VaultError(Exception):
    """Base exception for all ΣVAULT errors."""
    
    def __init__(self, message: str, error_code: str = "VAULT_ERROR", is_retryable: bool = False):
        super().__init__(message)
        self.error_code = error_code
        self.is_retryable = is_retryable


class VaultNotFoundError(VaultError):
    def __init__(self, path: str):
        super().__init__(f"Vault not found: {path}", "VAULT_NOT_FOUND")
        self.path = path


class VaultLockedError(VaultError):
    def __init__(self, message: str = "Vault or entry is locked"):
        super().__init__(message, "VAULT_LOCKED")


class InvalidPassphraseError(VaultError):
    def __init__(self):
        super().__init__("Invalid passphrase", "INVALID_PASSPHRASE")


class DeviceBindingError(VaultError):
    def __init__(self, message: str = "Key not valid on this device"):
        super().__init__(message, "DEVICE_BINDING_ERROR")


class KeyNotFoundError(VaultError):
    def __init__(self, key: str):
        super().__init__(f"Key not found: {key}", "KEY_NOT_FOUND")
        self.key = key


class IntegrityError(VaultError):
    def __init__(self, key: Optional[str] = None):
        message = f"Integrity check failed for: {key}" if key else "Data integrity check failed"
        super().__init__(message, "INTEGRITY_ERROR")
        self.key = key


class ScatterError(VaultError):
    def __init__(self, message: str):
        super().__init__(message, "SCATTER_ERROR", is_retryable=True)


class GatherError(VaultError):
    def __init__(self, message: str, missing_shards: int = 0):
        super().__init__(message, "GATHER_ERROR", is_retryable=True)
        self.missing_shards = missing_shards


class MountError(VaultError):
    def __init__(self, mount_point: str, reason: str):
        super().__init__(f"Failed to mount at {mount_point}: {reason}", "MOUNT_ERROR")
        self.mount_point = mount_point
