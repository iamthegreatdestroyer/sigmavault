#!/usr/bin/env python3
"""
ΣVAULT Command Line Interface
=============================

Usage:
    sigmavault mount <mount_point> <storage_path> [--mode=hybrid] [--foreground]
    sigmavault create <storage_path> [--mode=hybrid]
    sigmavault lock <mount_point> <file_path>
    sigmavault unlock <mount_point> <file_path>
    sigmavault info <storage_path>
    sigmavault demo

Commands:
    mount     Mount a ΣVAULT filesystem
    create    Create a new ΣVAULT without mounting
    lock      Lock a specific file with additional passphrase
    unlock    Unlock a locked file
    info      Show vault information
    demo      Run demonstration of dimensional scattering

Copyright 2025 - ΣVAULT Project
"""

import argparse
import sys
import os
import getpass
from pathlib import Path


def cmd_mount(args):
    """Mount ΣVAULT filesystem."""
    try:
        from .filesystem import mount_sigmavault
        from .crypto import KeyMode
    except ImportError:
        print("Error: Required modules not found.")
        print("Make sure sigmavault is properly installed.")
        sys.exit(1)
    
    # Get passphrase
    passphrase = getpass.getpass("Enter vault passphrase: ")
    if not args.existing:
        confirm = getpass.getpass("Confirm passphrase: ")
        if passphrase != confirm:
            print("Passphrases do not match.")
            sys.exit(1)
    
    # Determine mode
    mode_map = {
        'hybrid': KeyMode.HYBRID,
        'device': KeyMode.DEVICE_ONLY,
        'user': KeyMode.USER_ONLY,
    }
    mode = mode_map.get(args.mode, KeyMode.HYBRID)
    
    print(f"\nMounting ΣVAULT...")
    print(f"  Mount point: {args.mount_point}")
    print(f"  Storage: {args.storage_path}")
    print(f"  Mode: {args.mode}")
    print()
    
    try:
        mount_sigmavault(
            args.mount_point,
            args.storage_path,
            passphrase,
            mode,
            foreground=args.foreground
        )
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


def cmd_create(args):
    """Create new ΣVAULT."""
    from .crypto import create_new_vault_key, KeyMode, KeyDerivationConfig
    
    storage = Path(args.storage_path)
    storage.mkdir(parents=True, exist_ok=True)
    
    config_path = storage / 'vault_config.dat'
    
    if config_path.exists() and not args.force:
        print(f"Vault already exists at {args.storage_path}")
        print("Use --force to overwrite.")
        sys.exit(1)
    
    # Get passphrase
    passphrase = getpass.getpass("Enter new vault passphrase: ")
    confirm = getpass.getpass("Confirm passphrase: ")
    if passphrase != confirm:
        print("Passphrases do not match.")
        sys.exit(1)
    
    # Determine mode
    mode_map = {
        'hybrid': KeyMode.HYBRID,
        'device': KeyMode.DEVICE_ONLY,
        'user': KeyMode.USER_ONLY,
    }
    mode = mode_map.get(args.mode, KeyMode.HYBRID)
    
    print("\nCreating ΣVAULT...")
    print(f"  Storage: {args.storage_path}")
    print(f"  Mode: {args.mode}")
    
    master_key, config = create_new_vault_key(passphrase, mode)
    
    with open(config_path, 'wb') as f:
        f.write(config.to_bytes())
    
    print("\n✓ ΣVAULT created successfully!")
    print(f"  Config saved to: {config_path}")
    print("\nTo mount, run:")
    print(f"  sigmavault mount /path/to/mount {args.storage_path}")


def cmd_lock(args):
    """Lock a specific file."""
    print("File locking requires the vault to be mounted.")
    print("Use the lock command through the mounted filesystem:")
    print(f"  setfattr -n user.sigmavault.lock -v '<passphrase>' {args.file_path}")
    print("\nOr use the Python API:")
    print("  fs.lock_file(path, passphrase)")


def cmd_unlock(args):
    """Unlock a specific file."""
    print("File unlocking requires the vault to be mounted.")
    print("Use the unlock command through the mounted filesystem:")
    print(f"  setfattr -n user.sigmavault.unlock -v '<passphrase>' {args.file_path}")
    print("\nOr use the Python API:")
    print("  fs.unlock_file(path, passphrase)")


def cmd_info(args):
    """Show vault information."""
    from .crypto import KeyDerivationConfig, KeyMode
    import time
    
    storage = Path(args.storage_path)
    config_path = storage / 'vault_config.dat'
    
    if not config_path.exists():
        print(f"No vault found at {args.storage_path}")
        sys.exit(1)
    
    with open(config_path, 'rb') as f:
        config = KeyDerivationConfig.from_bytes(f.read())
    
    print("\n╔════════════════════════════════════════════════════════════╗")
    print("║                    ΣVAULT INFORMATION                      ║")
    print("╠════════════════════════════════════════════════════════════╣")
    print(f"║  Storage Path: {str(storage):<43} ║")
    print(f"║  Key Mode: {config.mode.name:<47} ║")
    print(f"║  Created: {time.ctime(config.created_at):<48} ║")
    print(f"║  Version: {config.version:<48} ║")
    print("╠════════════════════════════════════════════════════════════╣")
    
    # Count scattered files
    scatter_data = storage / 'scatter_data'
    if scatter_data.exists():
        file_count = len(list(scatter_data.glob('*.scatter')))
        print(f"║  Scattered Files: {file_count:<40} ║")
    
    # Calculate storage size
    total_size = sum(f.stat().st_size for f in storage.rglob('*') if f.is_file())
    size_mb = total_size / (1024 * 1024)
    print(f"║  Storage Used: {size_mb:.2f} MB{' ' * 35}║")
    
    print("╚════════════════════════════════════════════════════════════╝")


def cmd_demo(args):
    """Run demonstration of dimensional scattering."""
    import secrets
    import hashlib
    
    print("\n" + "=" * 70)
    print("ΣVAULT DIMENSIONAL SCATTERING DEMONSTRATION")
    print("=" * 70)
    
    # Import core modules
    try:
        from .core import DimensionalScatterEngine, KeyState
        from .crypto import HybridKeyDerivation, KeyMode
    except ImportError as e:
        print(f"Import error: {e}")
        print("Running standalone demo...")
        _run_standalone_demo()
        return
    
    # Create demo key
    print("\n1. Creating hybrid key from device + passphrase...")
    kdf = HybridKeyDerivation(KeyMode.HYBRID)
    kdf.initialize()
    master_key = kdf.derive_key("demo_passphrase_123")
    
    print(f"   Master key (first 32 hex chars): {master_key[:16].hex()}")
    
    # Create key state
    print("\n2. Deriving dimensional key state...")
    key_state = KeyState.derive(master_key)
    print(f"   Temporal prime: {key_state.temporal_prime}")
    print(f"   Entropy ratio: {key_state.entropy_ratio:.3f}")
    print(f"   Scatter depth: {key_state.scatter_depth}")
    
    # Create scatter engine
    print("\n3. Initializing dimensional scatter engine...")
    engine = DimensionalScatterEngine(key_state, medium_size=100_000_000)
    
    # Demo data
    demo_text = b"This is a secret message that will be dimensionally scattered!"
    file_id = secrets.token_bytes(16)
    
    print(f"\n4. Original data ({len(demo_text)} bytes):")
    print(f"   '{demo_text.decode()}'")
    
    # Scatter
    print("\n5. Scattering across dimensional manifold...")
    scattered = engine.scatter(file_id, demo_text)
    
    print(f"   Original size: {scattered.original_size} bytes")
    print(f"   Shards created: {len(scattered.shard_coordinates)}")
    
    total_scattered_bytes = sum(
        len(data) for shard in scattered.shard_coordinates 
        for coord, data in shard
    )
    print(f"   Total scattered bytes: {total_scattered_bytes}")
    print(f"   Expansion ratio: {total_scattered_bytes / len(demo_text):.2f}x")
    
    # Show some coordinates
    print("\n6. Sample dimensional coordinates:")
    for i, (coord, data) in enumerate(scattered.shard_coordinates[0][:3]):
        print(f"   Chunk {i}:")
        print(f"     Spatial: {coord.spatial}")
        print(f"     Temporal: {coord.temporal}")
        print(f"     Phase: {coord.phase:.4f}")
        print(f"     Data (hex): {data[:16].hex()}...")
    
    # Gather
    print("\n7. Gathering from dimensional manifold...")
    reconstructed = engine.gather(scattered)
    
    print(f"   Reconstructed ({len(reconstructed)} bytes):")
    print(f"   '{reconstructed.decode()}'")
    
    # Verify
    if reconstructed == demo_text:
        print("\n✓ SUCCESS: Data perfectly reconstructed!")
    else:
        print("\n✗ ERROR: Data mismatch!")
    
    # Demonstrate entropic mixing
    print("\n8. Entropic indistinguishability demonstration:")
    print("   Without the key, scattered data appears as random noise.")
    print("   Sample scattered bytes (hex):")
    sample = scattered.shard_coordinates[0][0][1][:32]
    print(f"   {sample.hex()}")
    
    # Calculate entropy
    byte_counts = [0] * 256
    for b in sample:
        byte_counts[b] += 1
    entropy = -sum(
        (c/len(sample)) * (c/len(sample) and __import__('math').log2(c/len(sample)))
        for c in byte_counts if c > 0
    )
    print(f"   Entropy: {entropy:.2f} bits/byte (max: 8.0)")
    print("   [High entropy = indistinguishable from random]")
    
    print("\n" + "=" * 70)
    print("Demonstration complete!")
    print("=" * 70)


def _run_standalone_demo():
    """Run simplified demo without full imports."""
    import secrets
    
    print("\n[Standalone Mode - Core concepts only]\n")
    
    print("1. Dimensional Scattering Concept:")
    print("   Traditional: File bytes stored at contiguous addresses")
    print("   ΣVAULT: Bits scattered across N-dimensional manifold")
    print()
    
    print("2. The 8 Dimensions:")
    dimensions = [
        ("SPATIAL", "Physical position on medium"),
        ("TEMPORAL", "Time-variant component"),
        ("ENTROPIC", "Noise interleaving axis"),
        ("SEMANTIC", "Content-derived offset"),
        ("FRACTAL", "Self-similar recursion level"),
        ("PHASE", "Wave interference angle"),
        ("TOPOLOGICAL", "Graph connectivity"),
        ("HOLOGRAPHIC", "Redundancy shard ID"),
    ]
    for name, desc in dimensions:
        print(f"   • {name}: {desc}")
    print()
    
    print("3. Why it's secure:")
    print("   • Without the key, you can't identify which bits are real vs noise")
    print("   • The file's content determines where it's stored (bootstrap problem)")
    print("   • Same file has different physical representation over time")
    print("   • Partial access reveals nothing about the whole")
    print()
    
    print("4. Demo data transformation:")
    original = b"Secret message!"
    print(f"   Original: {original}")
    
    # Simulate scattering (simplified)
    scattered = bytearray()
    for i, byte in enumerate(original):
        # Add real byte
        scattered.append(byte ^ (i * 17 + 42))
        # Add entropy bytes
        for _ in range(3):
            scattered.append(secrets.randbelow(256))
    
    print(f"   Scattered ({len(scattered)} bytes): {scattered[:32].hex()}...")
    print(f"   Expansion: {len(scattered) / len(original):.1f}x")
    print()
    
    print("5. Without the key:")
    print("   The scattered bytes are indistinguishable from random noise.")
    print("   An attacker cannot even identify file boundaries.")


def main():
    parser = argparse.ArgumentParser(
        description="ΣVAULT - Trans-Dimensional Encrypted Storage",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Create a new vault:
    sigmavault create /path/to/storage --mode=hybrid
    
  Mount an existing vault:
    sigmavault mount /mnt/secure /path/to/storage
    
  Run demonstration:
    sigmavault demo
    
Key Modes:
  hybrid   - Requires both device AND passphrase (most secure)
  device   - Only device fingerprint (no passphrase)
  user     - Only passphrase (portable across devices)
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    
    # Mount command
    mount_parser = subparsers.add_parser('mount', help='Mount ΣVAULT filesystem')
    mount_parser.add_argument('mount_point', help='Mount point directory')
    mount_parser.add_argument('storage_path', help='Storage directory')
    mount_parser.add_argument('--mode', default='hybrid',
                             choices=['hybrid', 'device', 'user'],
                             help='Key derivation mode')
    mount_parser.add_argument('--foreground', '-f', action='store_true',
                             help='Run in foreground')
    mount_parser.add_argument('--existing', '-e', action='store_true',
                             help='Mount existing vault (skip passphrase confirm)')
    
    # Create command
    create_parser = subparsers.add_parser('create', help='Create new ΣVAULT')
    create_parser.add_argument('storage_path', help='Storage directory')
    create_parser.add_argument('--mode', default='hybrid',
                              choices=['hybrid', 'device', 'user'],
                              help='Key derivation mode')
    create_parser.add_argument('--force', '-f', action='store_true',
                              help='Overwrite existing vault')
    
    # Lock command
    lock_parser = subparsers.add_parser('lock', help='Lock a file')
    lock_parser.add_argument('mount_point', help='Mount point')
    lock_parser.add_argument('file_path', help='File to lock')
    
    # Unlock command
    unlock_parser = subparsers.add_parser('unlock', help='Unlock a file')
    unlock_parser.add_argument('mount_point', help='Mount point')
    unlock_parser.add_argument('file_path', help='File to unlock')
    
    # Info command
    info_parser = subparsers.add_parser('info', help='Show vault information')
    info_parser.add_argument('storage_path', help='Storage directory')
    
    # Demo command
    demo_parser = subparsers.add_parser('demo', help='Run demonstration')
    
    args = parser.parse_args()
    
    if args.command == 'mount':
        cmd_mount(args)
    elif args.command == 'create':
        cmd_create(args)
    elif args.command == 'lock':
        cmd_lock(args)
    elif args.command == 'unlock':
        cmd_unlock(args)
    elif args.command == 'info':
        cmd_info(args)
    elif args.command == 'demo':
        cmd_demo(args)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
