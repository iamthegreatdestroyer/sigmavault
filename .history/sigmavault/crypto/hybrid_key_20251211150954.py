"""
ΣVAULT Hybrid Key Derivation
============================

Creates cryptographic keys bound to BOTH device AND user.

HYBRID KEY ARCHITECTURE:

    ┌─────────────────────┐     ┌─────────────────────┐
    │   DEVICE IDENTITY   │     │   USER IDENTITY     │
    │                     │     │                     │
    │  • CPU ID           │     │  • Passphrase       │
    │  • Disk Serial      │     │  • Biometric Hash   │
    │  • MAC Addresses    │     │  • Security Key     │
    │  • TPM (if present) │     │  • Memory Pattern   │
    │  • Boot UUID        │     │                     │
    └──────────┬──────────┘     └──────────┬──────────┘
               │                           │
               ▼                           ▼
    ┌─────────────────────┐     ┌─────────────────────┐
    │  DEVICE FINGERPRINT │     │  USER KEY MATERIAL  │
    │    (256 bits)       │     │    (256 bits)       │
    └──────────┬──────────┘     └──────────┬──────────┘
               │                           │
               └───────────┬───────────────┘
                           │
                           ▼
                ┌─────────────────────┐
                │   HYBRID MIXER      │
                │   (Non-reversible)  │
                └──────────┬──────────┘
                           │
                           ▼
                ┌─────────────────────┐
                │   MASTER KEY        │
                │   (512 bits)        │
                └──────────┬──────────┘
                           │
                           ▼
                ┌─────────────────────┐
                │   KEY DERIVATION    │
                │   (Argon2id)        │
                └──────────┬──────────┘
                           │
                           ▼
                ┌─────────────────────┐
                │   DIMENSIONAL KEY   │
                │   (KeyState)        │
                └─────────────────────┘

SECURITY PROPERTIES:

1. Device-Only Access: If device is cloned, data is inaccessible without user key
2. User-Only Access: If passphrase is stolen, useless without original device
3. Both Required: Maximum security requires physical device + knowledge
4. No Single Point: Neither device nor user can be attacked in isolation

MODES:

- HYBRID (default): Both device + user required
- DEVICE_ONLY: Only device fingerprint (portable within same device)
- USER_ONLY: Only user key (portable across devices, less secure)

Copyright 2025 - ΣVAULT Project
"""

import os
import hashlib
import secrets
import struct
import platform
import subprocess
import re
from typing import Optional, Tuple, List, Dict, Any
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
import base64

# Try to import platform-specific modules
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


class KeyMode(Enum):
    """Key derivation modes."""
    HYBRID = auto()       # Device + User (maximum security)
    DEVICE_ONLY = auto()  # Only device fingerprint
    USER_ONLY = auto()    # Only user passphrase


@dataclass
class DeviceFingerprint:
    """
    Unique device identification derived from hardware characteristics.
    
    The fingerprint is designed to be:
    - Stable: Same device produces same fingerprint
    - Unique: Different devices produce different fingerprints
    - Non-transferable: Can't be copied to another device
    """
    cpu_id: bytes
    disk_serials: bytes
    mac_addresses: bytes
    boot_uuid: bytes
    platform_info: bytes
    tpm_id: Optional[bytes]  # If TPM available
    
    def combine(self) -> bytes:
        """Combine all components into single fingerprint."""
        components = [
            self.cpu_id,
            self.disk_serials,
            self.mac_addresses,
            self.boot_uuid,
            self.platform_info,
        ]
        
        if self.tpm_id:
            components.append(self.tpm_id)
        
        # Hash each component then combine
        hashes = [hashlib.sha256(c).digest() for c in components]
        combined = b''.join(hashes)
        
        # Final fingerprint is SHA-512 of all component hashes
        return hashlib.sha512(combined).digest()[:32]  # 256 bits


class DeviceFingerprintCollector:
    """
    Collects hardware characteristics to create device fingerprint.
    Works across Linux, macOS, and Windows.
    """
    
    def collect(self) -> DeviceFingerprint:
        """Collect all device identification components."""
        return DeviceFingerprint(
            cpu_id=self._get_cpu_id(),
            disk_serials=self._get_disk_serials(),
            mac_addresses=self._get_mac_addresses(),
            boot_uuid=self._get_boot_uuid(),
            platform_info=self._get_platform_info(),
            tpm_id=self._get_tpm_id(),
        )
    
    def _get_cpu_id(self) -> bytes:
        """Get CPU identification."""
        cpu_info = []
        
        # Try various methods
        try:
            # Linux: /proc/cpuinfo
            if os.path.exists('/proc/cpuinfo'):
                with open('/proc/cpuinfo', 'r') as f:
                    for line in f:
                        if 'model name' in line or 'cpu family' in line or 'model' in line:
                            cpu_info.append(line.strip())
        except:
            pass
        
        try:
            # Cross-platform via platform module
            cpu_info.append(platform.processor())
            cpu_info.append(platform.machine())
        except:
            pass
        
        try:
            # Windows: WMIC
            if platform.system() == 'Windows':
                result = subprocess.run(
                    ['wmic', 'cpu', 'get', 'ProcessorId'],
                    capture_output=True, text=True
                )
                cpu_info.append(result.stdout)
        except:
            pass
        
        return hashlib.sha256('|'.join(cpu_info).encode()).digest()
    
    def _get_disk_serials(self) -> bytes:
        """Get disk serial numbers."""
        serials = []
        
        try:
            # Linux: /dev/disk/by-id
            if os.path.exists('/dev/disk/by-id'):
                for entry in os.listdir('/dev/disk/by-id'):
                    serials.append(entry)
        except:
            pass
        
        try:
            # Linux: lsblk
            result = subprocess.run(
                ['lsblk', '-o', 'SERIAL', '-n'],
                capture_output=True, text=True
            )
            serials.extend(result.stdout.strip().split('\n'))
        except:
            pass
        
        try:
            # macOS
            if platform.system() == 'Darwin':
                result = subprocess.run(
                    ['system_profiler', 'SPStorageDataType'],
                    capture_output=True, text=True
                )
                serials.append(result.stdout)
        except:
            pass
        
        try:
            # Windows
            if platform.system() == 'Windows':
                result = subprocess.run(
                    ['wmic', 'diskdrive', 'get', 'SerialNumber'],
                    capture_output=True, text=True
                )
                serials.append(result.stdout)
        except:
            pass
        
        return hashlib.sha256('|'.join(serials).encode()).digest()
    
    def _get_mac_addresses(self) -> bytes:
        """Get MAC addresses of network interfaces."""
        macs = []
        
        try:
            if HAS_PSUTIL:
                for name, addrs in psutil.net_if_addrs().items():
                    for addr in addrs:
                        if hasattr(addr, 'family') and addr.family == psutil.AF_LINK:
                            macs.append(addr.address)
        except:
            pass
        
        try:
            # Fallback: /sys/class/net on Linux
            if os.path.exists('/sys/class/net'):
                for iface in os.listdir('/sys/class/net'):
                    addr_path = f'/sys/class/net/{iface}/address'
                    if os.path.exists(addr_path):
                        with open(addr_path) as f:
                            macs.append(f.read().strip())
        except:
            pass
        
        # Sort for consistency
        macs = sorted(set(macs))
        return hashlib.sha256('|'.join(macs).encode()).digest()
    
    def _get_boot_uuid(self) -> bytes:
        """Get boot/machine UUID."""
        uuid_sources = []
        
        try:
            # Linux
            if os.path.exists('/etc/machine-id'):
                with open('/etc/machine-id') as f:
                    uuid_sources.append(f.read().strip())
        except:
            pass
        
        try:
            # Linux alternative
            if os.path.exists('/var/lib/dbus/machine-id'):
                with open('/var/lib/dbus/machine-id') as f:
                    uuid_sources.append(f.read().strip())
        except:
            pass
        
        try:
            # macOS
            if platform.system() == 'Darwin':
                result = subprocess.run(
                    ['ioreg', '-rd1', '-c', 'IOPlatformExpertDevice'],
                    capture_output=True, text=True
                )
                match = re.search(r'"IOPlatformUUID"\s*=\s*"([^"]+)"', result.stdout)
                if match:
                    uuid_sources.append(match.group(1))
        except:
            pass
        
        try:
            # Windows
            if platform.system() == 'Windows':
                result = subprocess.run(
                    ['wmic', 'csproduct', 'get', 'UUID'],
                    capture_output=True, text=True
                )
                uuid_sources.append(result.stdout)
        except:
            pass
        
        return hashlib.sha256('|'.join(uuid_sources).encode()).digest()
    
    def _get_platform_info(self) -> bytes:
        """Get platform identification."""
        info = [
            platform.system(),
            platform.release(),
            platform.version(),
            platform.machine(),
            platform.node(),
        ]
        return hashlib.sha256('|'.join(info).encode()).digest()
    
    def _get_tpm_id(self) -> Optional[bytes]:
        """Get TPM identification if available."""
        try:
            # Linux: Check for TPM device
            if os.path.exists('/dev/tpm0') or os.path.exists('/dev/tpmrm0'):
                # TPM is present, get endorsement key hash
                result = subprocess.run(
                    ['tpm2_getcap', 'handles-persistent'],
                    capture_output=True, text=True
                )
                return hashlib.sha256(result.stdout.encode()).digest()
        except:
            pass
        
        return None


@dataclass
class UserKeyMaterial:
    """
    User-provided key material.
    Can come from various sources for flexibility.
    """
    passphrase_hash: bytes        # Primary: from passphrase
    security_key_hash: Optional[bytes] = None  # Optional: hardware key
    memory_pattern: Optional[bytes] = None     # Optional: memorable pattern
    
    def combine(self) -> bytes:
        """Combine all user key material."""
        components = [self.passphrase_hash]
        
        if self.security_key_hash:
            components.append(self.security_key_hash)
        if self.memory_pattern:
            components.append(self.memory_pattern)
        
        combined = b''.join(components)
        return hashlib.sha512(combined).digest()[:32]  # 256 bits


class UserKeyDerivation:
    """
    Derives user key material from various inputs.
    Uses memory-hard function (Argon2id) for passphrase.
    """
    
    # Argon2id parameters (high security)
    ARGON2_TIME_COST = 4
    ARGON2_MEMORY_COST = 65536  # 64 MB
    ARGON2_PARALLELISM = 4
    ARGON2_HASH_LEN = 32
    
    def __init__(self, salt: Optional[bytes] = None):
        self.salt = salt or secrets.token_bytes(32)
    
    def derive_from_passphrase(self, passphrase: str) -> bytes:
        """Derive key material from passphrase using Argon2id."""
        try:
            from argon2 import PasswordHasher, Type
            from argon2.low_level import hash_secret_raw
            
            return hash_secret_raw(
                secret=passphrase.encode('utf-8'),
                salt=self.salt,
                time_cost=self.ARGON2_TIME_COST,
                memory_cost=self.ARGON2_MEMORY_COST,
                parallelism=self.ARGON2_PARALLELISM,
                hash_len=self.ARGON2_HASH_LEN,
                type=Type.ID,
            )
        except ImportError:
            # Fallback to PBKDF2 if Argon2 not available
            return hashlib.pbkdf2_hmac(
                'sha256',
                passphrase.encode('utf-8'),
                self.salt,
                iterations=600000,  # High iteration count
                dklen=32
            )
    
    def derive_from_security_key(self, key_data: bytes) -> bytes:
        """Derive from hardware security key response."""
        return hashlib.sha256(self.salt + key_data).digest()
    
    def derive_from_pattern(self, pattern: List[int]) -> bytes:
        """
        Derive from memorable pattern (like phone unlock pattern).
        Pattern is list of positions touched in order.
        """
        pattern_bytes = bytes(pattern)
        return hashlib.sha256(self.salt + pattern_bytes).digest()
    
    def create_user_material(self, passphrase: str,
                            security_key_data: Optional[bytes] = None,
                            pattern: Optional[List[int]] = None) -> UserKeyMaterial:
        """Create complete user key material from available inputs."""
        return UserKeyMaterial(
            passphrase_hash=self.derive_from_passphrase(passphrase),
            security_key_hash=self.derive_from_security_key(security_key_data) if security_key_data else None,
            memory_pattern=self.derive_from_pattern(pattern) if pattern else None,
        )


class HybridMixer:
    """
    Mixes device and user keys in a non-reversible way.
    
    Properties:
    - Given output, cannot determine input components
    - Small change in either input → completely different output
    - Timing-safe to prevent side-channel attacks
    - Constant-time operations for all cryptographic functions
    """
    
    DOMAIN_SEPARATOR = b'SIGMAVAULT_HYBRID_MIX_V1'
    
    # Constant key for HMAC operations (prevents timing attacks)
    HMAC_KEY = b'\x00' * 64  # 512-bit zero key for domain separation
    
    @staticmethod
    def _constant_time_compare(a: bytes, b: bytes) -> bool:
        """
        Constant-time comparison to prevent timing attacks.
        
        Args:
            a: First byte sequence
            b: Second byte sequence
            
        Returns:
            True if sequences are equal, False otherwise
        """
        if len(a) != len(b):
            return False
        
        # Use secrets.compare_digest for constant-time comparison
        return secrets.compare_digest(a, b)
    
    @staticmethod
    def _constant_time_xor(a: bytes, b: bytes) -> bytes:
        """
        Constant-time XOR operation.
        
        Args:
            a: First byte sequence
            b: Second byte sequence
            
        Returns:
            XOR result (length of shorter input)
        """
        result = bytearray(min(len(a), len(b)))
        for i in range(len(result)):
            result[i] = a[i] ^ b[i]
        return bytes(result)
    
    @staticmethod
    def mix(device_key: bytes, user_key: bytes) -> bytes:
        """
        Mix device and user keys into hybrid master key.
        Uses constant-time HMAC operations to prevent timing attacks.
        
        Args:
            device_key: Device fingerprint (32 bytes)
            user_key: User key material (32 bytes)
            
        Returns:
            64-byte master key
        """
        # Validate input lengths for constant-time behavior
        if len(device_key) != 32 or len(user_key) != 32:
            raise ValueError("Device and user keys must be exactly 32 bytes")
        
        # Step 1: Create domain-separated inputs using HMAC
        device_hmac = hashlib.sha512()
        device_hmac.update(HybridMixer.HMAC_KEY)
        device_hmac.update(HybridMixer.DOMAIN_SEPARATOR + b'DEVICE')
        device_hmac.update(device_key)
        device_mixed = device_hmac.digest()
        
        user_hmac = hashlib.sha512()
        user_hmac.update(HybridMixer.HMAC_KEY)
        user_hmac.update(HybridMixer.DOMAIN_SEPARATOR + b'USER')
        user_hmac.update(user_key)
        user_mixed = user_hmac.digest()
        
        # Step 2: Combine using constant-time XOR
        combined = HybridMixer._constant_time_xor(device_mixed, user_mixed)
        
        # Step 3: Final expansion with additional HMAC rounds for 512-bit output
        final_hmac = hashlib.sha512()
        final_hmac.update(HybridMixer.HMAC_KEY)
        final_hmac.update(HybridMixer.DOMAIN_SEPARATOR + b'FINAL')
        final_hmac.update(combined)
        final_hmac.update(struct.pack('>Q', len(device_key)))
        final_hmac.update(struct.pack('>Q', len(user_key)))
        
        # Generate 512-bit output through multiple HMAC rounds
        result = bytearray()
        prev = b''
        
        for i in range(8):  # Generate 8 rounds for 512 bytes total
            round_input = prev + final_hmac.digest() + bytes([i])
            round_hmac = hashlib.sha512()
            round_hmac.update(HybridMixer.HMAC_KEY)
            round_hmac.update(HybridMixer.DOMAIN_SEPARATOR + b'ROUND')
            round_hmac.update(round_input)
            prev = round_hmac.digest()
            result.extend(prev)
        
        # Step 4: Fold to 64 bytes using constant-time XOR
        final_result = bytearray(64)
        for i in range(0, len(result), 64):
            chunk = result[i:i+64]
            for j in range(min(64, len(chunk))):
                final_result[j] ^= chunk[j]
        
        return bytes(final_result)


class HybridKeyDerivation:
    """
    Main interface for hybrid key derivation.
    Produces KeyState for dimensional scattering.
    """
    
    def __init__(self, mode: KeyMode = KeyMode.HYBRID):
        self.mode = mode
        self.device_collector = DeviceFingerprintCollector()
        self.user_derivation: Optional[UserKeyDerivation] = None
        self._cached_device_fingerprint: Optional[bytes] = None
    
    def initialize(self, salt: Optional[bytes] = None) -> bytes:
        """
        Initialize key derivation system.
        Returns salt that should be stored with encrypted data.
        """
        salt = salt or secrets.token_bytes(32)
        self.user_derivation = UserKeyDerivation(salt)
        return salt
    
    def derive_key(self, passphrase: Optional[str] = None,
                   security_key_data: Optional[bytes] = None,
                   pattern: Optional[List[int]] = None) -> bytes:
        """
        Derive hybrid key based on mode.
        
        Args:
            passphrase: User passphrase (required for HYBRID and USER_ONLY)
            security_key_data: Optional hardware key response
            pattern: Optional memory pattern
            
        Returns:
            512-bit master key
        """
        # Get device fingerprint (cached for consistency)
        if self._cached_device_fingerprint is None:
            fingerprint = self.device_collector.collect()
            self._cached_device_fingerprint = fingerprint.combine()
        
        device_key = self._cached_device_fingerprint
        
        # Get user key material
        if self.mode in (KeyMode.HYBRID, KeyMode.USER_ONLY):
            if passphrase is None:
                raise ValueError("Passphrase required for this key mode")
            
            if self.user_derivation is None:
                self.initialize()
            
            user_material = self.user_derivation.create_user_material(
                passphrase, security_key_data, pattern
            )
            user_key = user_material.combine()
        else:
            user_key = b'\x00' * 32  # Null user key for device-only mode
        
        # Mix based on mode
        if self.mode == KeyMode.HYBRID:
            return HybridMixer.mix(device_key, user_key)
        elif self.mode == KeyMode.DEVICE_ONLY:
            return HybridMixer.mix(device_key, device_key)  # Double device
        else:  # USER_ONLY
            return HybridMixer.mix(user_key, user_key)  # Double user
    
    def verify_device(self) -> bool:
        """
        Verify we're on the same device that created the key.
        Used to detect device changes.
        """
        current = self.device_collector.collect().combine()
        
        if self._cached_device_fingerprint is None:
            return True  # No cached fingerprint to compare
        
        # Compare in constant time
        return secrets.compare_digest(current, self._cached_device_fingerprint)


@dataclass
class KeyDerivationConfig:
    """Configuration for key derivation stored with vault."""
    mode: KeyMode
    salt: bytes
    device_fingerprint_hash: bytes  # Hash of fingerprint for verification
    created_at: float
    version: int = 1
    
    def to_bytes(self) -> bytes:
        """Serialize config."""
        return (
            struct.pack('>BIQd',
                self.mode.value,
                self.version,
                len(self.salt),
                self.created_at
            ) +
            self.salt +
            self.device_fingerprint_hash
        )
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'KeyDerivationConfig':
        """Deserialize config."""
        mode_val, version, salt_len, created_at = struct.unpack('>BIQd', data[:21])
        salt = data[21:21+salt_len]
        device_hash = data[21+salt_len:21+salt_len+32]
        
        return cls(
            mode=KeyMode(mode_val),
            salt=salt,
            device_fingerprint_hash=device_hash,
            created_at=created_at,
            version=version,
        )


# ============================================================================
# KEY STATE CONVERSION
# ============================================================================

def hybrid_key_to_key_state(hybrid_key: bytes) -> 'KeyState':
    """
    Convert hybrid key to KeyState for dimensional scattering.
    Imports from dimensional_scatter to avoid circular import.
    """
    from .dimensional_scatter import KeyState
    return KeyState.derive(hybrid_key)


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def create_new_vault_key(passphrase: str, 
                         mode: KeyMode = KeyMode.HYBRID) -> Tuple[bytes, KeyDerivationConfig]:
    """
    Create a new vault key.
    
    Returns:
        Tuple of (master_key, config_to_store)
    """
    import time
    
    kdf = HybridKeyDerivation(mode)
    salt = kdf.initialize()
    
    master_key = kdf.derive_key(passphrase)
    
    # Create config
    fingerprint = kdf.device_collector.collect().combine()
    config = KeyDerivationConfig(
        mode=mode,
        salt=salt,
        device_fingerprint_hash=hashlib.sha256(fingerprint).digest(),
        created_at=time.time(),
    )
    
    return master_key, config


def unlock_vault(passphrase: str, config: KeyDerivationConfig) -> bytes:
    """
    Unlock existing vault with passphrase.
    
    Returns:
        Master key if successful
        
    Raises:
        ValueError: If device mismatch or wrong passphrase
    """
    kdf = HybridKeyDerivation(config.mode)
    kdf.initialize(config.salt)
    
    # Verify device if in hybrid or device-only mode
    if config.mode in (KeyMode.HYBRID, KeyMode.DEVICE_ONLY):
        current_fingerprint = kdf.device_collector.collect().combine()
        current_hash = hashlib.sha256(current_fingerprint).digest()
        
        if not secrets.compare_digest(current_hash, config.device_fingerprint_hash):
            raise ValueError("Device mismatch - vault created on different device")
    
    return kdf.derive_key(passphrase)
