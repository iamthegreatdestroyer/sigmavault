"""
ΣVAULT Snapshot Manager
Creates immutable snapshots of encrypted storage state

Phase 15A: Point-in-time recovery system for 8-dimensional encrypted storage
"""

import asyncio
from typing import Dict, List, Optional
from datetime import datetime
from pathlib import Path
import logging
import json
import hashlib
import shutil

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SnapshotManager:
    """
    Manages immutable snapshots of ΣVAULT storage
    
    Snapshots preserve:
    - Encrypted data blocks
    - Manifold coordinate mappings
    - Encryption metadata
    - Storage manifests
    
    Features:
    - Point-in-time recovery
    - Immutable snapshots with checksums
    - Component-based snapshotting
    - Automated snapshot listing and restoration
    """
    
    def __init__(
        self,
        storage_root: Path = Path("/data/sigmavault"),
        snapshot_root: Path = Path("/data/sigmavault/snapshots")
    ):
        """
        Initialize SnapshotManager
        
        Args:
            storage_root: Root directory for ΣVAULT storage
            snapshot_root: Root directory for snapshots
        """
        self.storage_root = storage_root
        self.snapshot_root = snapshot_root
        
        # Create snapshot directory
        self.snapshot_root.mkdir(parents=True, exist_ok=True)
        logger.info(f"SnapshotManager initialized: {self.snapshot_root}")
        
    async def create_snapshot(
        self,
        name: Optional[str] = None,
        description: str = ""
    ) -> Dict:
        """
        Create immutable snapshot of current storage state
        
        Preserves:
        - Encrypted data blocks
        - Manifold coordinate mappings
        - Encryption metadata
        - Storage manifests
        
        Args:
            name: Optional snapshot name (auto-generated if None)
            description: Human-readable description
            
        Returns:
            Snapshot manifest with metadata and checksums
            
        Raises:
            Exception: If snapshot creation fails
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        snapshot_name = name or f"snapshot_{timestamp}"
        snapshot_id = f"{snapshot_name}_{timestamp}"
        
        logger.info(f"Creating snapshot: {snapshot_id}")
        
        snapshot_dir = self.snapshot_root / snapshot_id
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        
        manifest = {
            "snapshot_id": snapshot_id,
            "name": snapshot_name,
            "description": description,
            "timestamp": timestamp,
            "created_at": datetime.now().isoformat(),
            "components": {},
            "storage_root": str(self.storage_root)
        }
        
        try:
            # Snapshot encrypted data blocks
            data_dir = self.storage_root / "data"
            if data_dir.exists():
                logger.info("Snapshotting data blocks...")
                data_snapshot = snapshot_dir / "data"
                shutil.copytree(data_dir, data_snapshot)
                checksum = await self._calculate_dir_checksum(data_snapshot)
                manifest["components"]["data"] = {
                    "path": str(data_snapshot.relative_to(self.snapshot_root)),
                    "checksum": checksum,
                    "size_bytes": self._get_dir_size(data_snapshot)
                }
                logger.info(f"  ✓ Data blocks snapshotted (checksum: {checksum[:16]}...)")
                
            # Snapshot manifold mappings
            manifold_dir = self.storage_root / "manifolds"
            if manifold_dir.exists():
                logger.info("Snapshotting manifold mappings...")
                manifold_snapshot = snapshot_dir / "manifolds"
                shutil.copytree(manifold_dir, manifold_snapshot)
                checksum = await self._calculate_dir_checksum(manifold_snapshot)
                manifest["components"]["manifolds"] = {
                    "path": str(manifold_snapshot.relative_to(self.snapshot_root)),
                    "checksum": checksum,
                    "size_bytes": self._get_dir_size(manifold_snapshot)
                }
                logger.info(f"  ✓ Manifold mappings snapshotted (checksum: {checksum[:16]}...)")
                
            # Snapshot encryption metadata
            metadata_dir = self.storage_root / "metadata"
            if metadata_dir.exists():
                logger.info("Snapshotting metadata...")
                metadata_snapshot = snapshot_dir / "metadata"
                shutil.copytree(metadata_dir, metadata_snapshot)
                checksum = await self._calculate_dir_checksum(metadata_snapshot)
                manifest["components"]["metadata"] = {
                    "path": str(metadata_snapshot.relative_to(self.snapshot_root)),
                    "checksum": checksum,
                    "size_bytes": self._get_dir_size(metadata_snapshot)
                }
                logger.info(f"  ✓ Metadata snapshotted (checksum: {checksum[:16]}...)")
                
            # Save manifest
            manifest_path = snapshot_dir / "manifest.json"
            with open(manifest_path, 'w') as f:
                json.dump(manifest, f, indent=2)
            
            logger.info(f"✅ Snapshot created: {snapshot_id}")
            logger.info(f"   Location: {snapshot_dir}")
            logger.info(f"   Components: {', '.join(manifest['components'].keys())}")
            
            return manifest
            
        except Exception as e:
            logger.error(f"Failed to create snapshot: {e}")
            # Cleanup on failure
            if snapshot_dir.exists():
                shutil.rmtree(snapshot_dir)
            raise
        
    async def list_snapshots(self) -> List[Dict]:
        """
        List all available snapshots
        
        Returns:
            List of snapshot metadata sorted by creation time (newest first)
        """
        snapshots = []
        
        if not self.snapshot_root.exists():
            logger.warning(f"Snapshot root does not exist: {self.snapshot_root}")
            return snapshots
        
        for snapshot_dir in self.snapshot_root.iterdir():
            if not snapshot_dir.is_dir():
                continue
                
            manifest_path = snapshot_dir / "manifest.json"
            if not manifest_path.exists():
                continue
                
            try:
                with open(manifest_path) as f:
                    manifest = json.load(f)
                    
                    # Calculate total size
                    total_size = sum(
                        comp.get("size_bytes", 0) 
                        for comp in manifest.get("components", {}).values()
                    )
                    
                    snapshots.append({
                        "snapshot_id": manifest["snapshot_id"],
                        "name": manifest["name"],
                        "description": manifest.get("description", ""),
                        "created_at": manifest["created_at"],
                        "timestamp": manifest.get("timestamp", ""),
                        "components": list(manifest["components"].keys()),
                        "total_size_bytes": total_size
                    })
            except Exception as e:
                logger.warning(f"Could not read snapshot {snapshot_dir.name}: {e}")
                
        # Sort by creation time (newest first)
        snapshots.sort(key=lambda x: x["created_at"], reverse=True)
        logger.info(f"Found {len(snapshots)} snapshots")
        
        return snapshots
        
    async def restore_snapshot(self, snapshot_id: str) -> Dict:
        """
        Restore storage from snapshot
        
        Restores all components from the specified snapshot to current storage root.
        
        Args:
            snapshot_id: ID of snapshot to restore
            
        Returns:
            Restoration results with success status for each component
            
        Raises:
            ValueError: If snapshot not found
            Exception: If restoration fails
        """
        logger.info(f"Restoring from snapshot: {snapshot_id}")
        
        snapshot_dir = self.snapshot_root / snapshot_id
        
        if not snapshot_dir.exists():
            raise ValueError(f"Snapshot not found: {snapshot_id}")
            
        manifest_path = snapshot_dir / "manifest.json"
        if not manifest_path.exists():
            raise ValueError(f"Snapshot manifest not found: {manifest_path}")
            
        with open(manifest_path) as f:
            manifest = json.load(f)
            
        results = {
            "snapshot_id": snapshot_id,
            "restored_at": datetime.now().isoformat(),
            "components": {}
        }
        
        try:
            # Restore data blocks
            if "data" in manifest["components"]:
                logger.info("Restoring data blocks...")
                data_snapshot = snapshot_dir / "data"
                data_target = self.storage_root / "data"
                
                if data_target.exists():
                    shutil.rmtree(data_target)
                    
                shutil.copytree(data_snapshot, data_target)
                
                # Verify checksum
                restored_checksum = await self._calculate_dir_checksum(data_target)
                expected_checksum = manifest["components"]["data"]["checksum"]
                
                success = restored_checksum == expected_checksum
                results["components"]["data"] = {
                    "success": success,
                    "checksum_match": success,
                    "restored_size_bytes": self._get_dir_size(data_target)
                }
                
                if success:
                    logger.info(f"  ✓ Data blocks restored (verified)")
                else:
                    logger.error(f"  ✗ Data blocks checksum mismatch!")
                
            # Restore manifold mappings
            if "manifolds" in manifest["components"]:
                logger.info("Restoring manifold mappings...")
                manifold_snapshot = snapshot_dir / "manifolds"
                manifold_target = self.storage_root / "manifolds"
                
                if manifold_target.exists():
                    shutil.rmtree(manifold_target)
                    
                shutil.copytree(manifold_snapshot, manifold_target)
                
                # Verify checksum
                restored_checksum = await self._calculate_dir_checksum(manifold_target)
                expected_checksum = manifest["components"]["manifolds"]["checksum"]
                
                success = restored_checksum == expected_checksum
                results["components"]["manifolds"] = {
                    "success": success,
                    "checksum_match": success,
                    "restored_size_bytes": self._get_dir_size(manifold_target)
                }
                
                if success:
                    logger.info(f"  ✓ Manifold mappings restored (verified)")
                else:
                    logger.error(f"  ✗ Manifold mappings checksum mismatch!")
                
            # Restore metadata
            if "metadata" in manifest["components"]:
                logger.info("Restoring metadata...")
                metadata_snapshot = snapshot_dir / "metadata"
                metadata_target = self.storage_root / "metadata"
                
                if metadata_target.exists():
                    shutil.rmtree(metadata_target)
                    
                shutil.copytree(metadata_snapshot, metadata_target)
                
                # Verify checksum
                restored_checksum = await self._calculate_dir_checksum(metadata_target)
                expected_checksum = manifest["components"]["metadata"]["checksum"]
                
                success = restored_checksum == expected_checksum
                results["components"]["metadata"] = {
                    "success": success,
                    "checksum_match": success,
                    "restored_size_bytes": self._get_dir_size(metadata_target)
                }
                
                if success:
                    logger.info(f"  ✓ Metadata restored (verified)")
                else:
                    logger.error(f"  ✗ Metadata checksum mismatch!")
            
            logger.info(f"✅ Snapshot restored: {snapshot_id}")
            
            return results
            
        except Exception as e:
            logger.error(f"Failed to restore snapshot: {e}")
            raise
        
    async def delete_snapshot(self, snapshot_id: str):
        """
        Delete a snapshot
        
        Permanently removes snapshot and all its components.
        
        Args:
            snapshot_id: ID of snapshot to delete
            
        Raises:
            ValueError: If snapshot not found
        """
        snapshot_dir = self.snapshot_root / snapshot_id
        
        if not snapshot_dir.exists():
            raise ValueError(f"Snapshot not found: {snapshot_id}")
            
        try:
            size_bytes = self._get_dir_size(snapshot_dir)
            shutil.rmtree(snapshot_dir)
            logger.info(f"✅ Snapshot deleted: {snapshot_id}")
            logger.info(f"   Freed: {self._format_size(size_bytes)}")
        except Exception as e:
            logger.error(f"Failed to delete snapshot: {e}")
            raise
        
    async def _calculate_dir_checksum(self, directory: Path) -> str:
        """
        Calculate SHA-256 checksum of directory contents
        
        Args:
            directory: Directory path
            
        Returns:
            Hex-encoded SHA-256 checksum
        """
        sha256 = hashlib.sha256()
        
        for file_path in sorted(directory.rglob("*")):
            if file_path.is_file():
                with open(file_path, 'rb') as f:
                    while chunk := f.read(8192):
                        sha256.update(chunk)
                        
        return sha256.hexdigest()
    
    def _get_dir_size(self, directory: Path) -> int:
        """
        Calculate total size of directory
        
        Args:
            directory: Directory path
            
        Returns:
            Total size in bytes
        """
        total_size = 0
        for file_path in directory.rglob("*"):
            if file_path.is_file():
                total_size += file_path.stat().st_size
        return total_size
    
    def _format_size(self, size_bytes: int) -> str:
        """Format bytes to human-readable size"""
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size_bytes < 1024:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.2f} PB"


# CLI interface
async def main():
    """Command-line interface for snapshot management"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="ΣVAULT Snapshot Manager",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create snapshot
  python snapshot_manager.py create --name "pre-migration" --description "Before schema migration"
  
  # List snapshots
  python snapshot_manager.py list
  
  # Restore snapshot
  python snapshot_manager.py restore --snapshot-id snapshot_pre-migration_20251216_120000
  
  # Delete snapshot
  python snapshot_manager.py delete --snapshot-id snapshot_old_20251201_100000
        """
    )
    parser.add_argument(
        "command",
        choices=["create", "list", "restore", "delete"],
        help="Operation to perform"
    )
    parser.add_argument("--name", help="Snapshot name")
    parser.add_argument("--description", default="", help="Snapshot description")
    parser.add_argument("--snapshot-id", help="Snapshot ID for restore/delete")
    parser.add_argument("--storage-root", default="/data/sigmavault", help="Storage root directory")
    parser.add_argument("--snapshot-root", help="Snapshot root directory (auto from storage-root if not specified)")
    
    args = parser.parse_args()
    
    storage_root = Path(args.storage_root)
    snapshot_root = Path(args.snapshot_root) if args.snapshot_root else storage_root / "snapshots"
    
    manager = SnapshotManager(storage_root=storage_root, snapshot_root=snapshot_root)
    
    try:
        if args.command == "create":
            manifest = await manager.create_snapshot(
                name=args.name,
                description=args.description
            )
            print(f"\n✅ Snapshot created: {manifest['snapshot_id']}\n")
            
        elif args.command == "list":
            snapshots = await manager.list_snapshots()
            
            if not snapshots:
                print("\nNo snapshots found\n")
                return
                
            print("\nAvailable snapshots:\n")
            for snap in snapshots:
                size_str = manager._format_size(snap["total_size_bytes"])
                print(f"  📦 {snap['snapshot_id']}")
                print(f"     Name: {snap['name']}")
                print(f"     Created: {snap['created_at']}")
                print(f"     Size: {size_str}")
                print(f"     Components: {', '.join(snap['components'])}")
                if snap['description']:
                    print(f"     Description: {snap['description']}")
                print()
                
        elif args.command == "restore":
            if not args.snapshot_id:
                print("Error: --snapshot-id required for restore")
                return
                
            results = await manager.restore_snapshot(args.snapshot_id)
            print(f"\n✅ Restored from snapshot: {args.snapshot_id}\n")
            
            for component, result in results["components"].items():
                status = "✅" if result["success"] else "❌"
                match_status = "✓" if result.get("checksum_match") else "✗"
                size_str = manager._format_size(result.get("restored_size_bytes", 0))
                print(f"  {status} {component:12} [{match_status} checksum] {size_str}")
            print()
                
        elif args.command == "delete":
            if not args.snapshot_id:
                print("Error: --snapshot-id required for delete")
                return
                
            await manager.delete_snapshot(args.snapshot_id)
            print(f"\n✅ Snapshot deleted: {args.snapshot_id}\n")
            
    except Exception as e:
        print(f"\n❌ Error: {e}\n")
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
