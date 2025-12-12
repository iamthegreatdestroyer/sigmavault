"""
ΣVAULT Container Detection and Utilities

Enhanced container detection and runtime utilities for Docker, Podman,
Kubernetes, LXC, and other container environments.

Features:
    - Multi-runtime container detection
    - Container resource limits detection
    - FUSE compatibility checking in containers
    - Namespace and cgroup awareness
"""

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from enum import Enum, auto


class ContainerRuntime(Enum):
    """Container runtime types."""
    NONE = auto()        # Not in a container
    DOCKER = auto()      # Docker
    PODMAN = auto()      # Podman (rootless container)
    KUBERNETES = auto()  # Kubernetes pod
    LXC = auto()         # LXC/LXD container
    CONTAINERD = auto()  # containerd (standalone)
    CRIO = auto()        # CRI-O
    WSL = auto()         # Windows Subsystem for Linux
    VAGRANT = auto()     # Vagrant VM
    UNKNOWN = auto()     # Unknown container type


@dataclass
class ContainerInfo:
    """Information about the container environment."""
    
    runtime: ContainerRuntime
    runtime_version: Optional[str] = None
    container_id: Optional[str] = None
    
    # Resource limits
    memory_limit_bytes: Optional[int] = None
    cpu_limit_cores: Optional[float] = None
    cpu_quota_us: Optional[int] = None
    cpu_period_us: Optional[int] = None
    
    # FUSE/filesystem info
    fuse_available: bool = False
    privileged: bool = False
    
    # Namespace info
    namespaces: List[str] = field(default_factory=list)
    
    # Environment hints
    env_hints: Dict[str, str] = field(default_factory=dict)
    
    @property
    def is_containerized(self) -> bool:
        """Return True if running in any container."""
        return self.runtime != ContainerRuntime.NONE
    
    @property
    def has_resource_limits(self) -> bool:
        """Return True if container has resource limits."""
        return self.memory_limit_bytes is not None or self.cpu_limit_cores is not None
    
    @property
    def runtime_name(self) -> str:
        """Return human-readable runtime name."""
        return self.runtime.name.lower()


class ContainerDetector:
    """
    Enhanced container runtime detection.
    
    Uses multiple heuristics to detect container environments:
    - Environment variables
    - Filesystem markers (/.dockerenv, etc.)
    - cgroup information
    - Process tree analysis
    - Namespace detection
    """
    
    # Environment variable hints for container runtimes
    ENV_HINTS = {
        'KUBERNETES_SERVICE_HOST': ContainerRuntime.KUBERNETES,
        'KUBERNETES_PORT': ContainerRuntime.KUBERNETES,
        'container': None,  # Special handling - value determines runtime
        'PODMAN_SYSTEMD_UNIT': ContainerRuntime.PODMAN,
        'WSL_DISTRO_NAME': ContainerRuntime.WSL,
        'DOCKER_HOST': ContainerRuntime.DOCKER,
        'SIGMAVAULT_CONTAINER': None,  # Our own marker
    }
    
    def __init__(self):
        """Initialize container detector."""
        self._cached_info: Optional[ContainerInfo] = None
    
    def detect(self, force_refresh: bool = False) -> ContainerInfo:
        """
        Detect container environment.
        
        Args:
            force_refresh: If True, bypass cache.
        
        Returns:
            ContainerInfo with detection results.
        """
        if self._cached_info is not None and not force_refresh:
            return self._cached_info
        
        runtime = ContainerRuntime.NONE
        runtime_version = None
        container_id = None
        env_hints: Dict[str, str] = {}
        
        # 1. Check environment variables
        runtime, env_hints = self._check_environment()
        
        # 2. Check filesystem markers
        if runtime == ContainerRuntime.NONE:
            runtime = self._check_filesystem_markers()
        
        # 3. Check cgroup information (Linux only)
        if runtime == ContainerRuntime.NONE:
            runtime, container_id = self._check_cgroups()
        
        # 4. Get container ID if not found yet
        if container_id is None:
            container_id = self._get_container_id(runtime)
        
        # 5. Detect resource limits
        memory_limit, cpu_limit, cpu_quota, cpu_period = self._detect_resource_limits()
        
        # 6. Check FUSE availability
        fuse_available = self._check_fuse_in_container()
        
        # 7. Check if privileged
        privileged = self._check_privileged()
        
        # 8. Detect namespaces
        namespaces = self._detect_namespaces()
        
        self._cached_info = ContainerInfo(
            runtime=runtime,
            runtime_version=runtime_version,
            container_id=container_id,
            memory_limit_bytes=memory_limit,
            cpu_limit_cores=cpu_limit,
            cpu_quota_us=cpu_quota,
            cpu_period_us=cpu_period,
            fuse_available=fuse_available,
            privileged=privileged,
            namespaces=namespaces,
            env_hints=env_hints
        )
        
        return self._cached_info
    
    def _check_environment(self) -> Tuple[ContainerRuntime, Dict[str, str]]:
        """Check environment variables for container hints."""
        hints: Dict[str, str] = {}
        runtime = ContainerRuntime.NONE
        
        for env_var, expected_runtime in self.ENV_HINTS.items():
            value = os.environ.get(env_var)
            if value:
                hints[env_var] = value
                
                if env_var == 'container':
                    # Special handling for 'container' env var
                    if value == 'podman':
                        runtime = ContainerRuntime.PODMAN
                    elif value == 'docker':
                        runtime = ContainerRuntime.DOCKER
                    elif value == 'lxc':
                        runtime = ContainerRuntime.LXC
                    elif value:
                        runtime = ContainerRuntime.UNKNOWN
                elif env_var == 'SIGMAVAULT_CONTAINER':
                    # Our own container marker
                    if value == 'docker':
                        runtime = ContainerRuntime.DOCKER
                    elif value == 'podman':
                        runtime = ContainerRuntime.PODMAN
                    elif value == 'kubernetes':
                        runtime = ContainerRuntime.KUBERNETES
                elif expected_runtime:
                    runtime = expected_runtime
        
        return runtime, hints
    
    def _check_filesystem_markers(self) -> ContainerRuntime:
        """Check filesystem for container markers."""
        # Docker marker
        if Path('/.dockerenv').exists():
            return ContainerRuntime.DOCKER
        
        # Podman marker
        if Path('/run/.containerenv').exists():
            return ContainerRuntime.PODMAN
        
        # LXC marker
        if Path('/dev/lxc').exists():
            return ContainerRuntime.LXC
        
        return ContainerRuntime.NONE
    
    def _check_cgroups(self) -> Tuple[ContainerRuntime, Optional[str]]:
        """Check cgroup for container information."""
        cgroup_paths = [
            '/proc/1/cgroup',
            '/proc/self/cgroup',
        ]
        
        for cgroup_path in cgroup_paths:
            try:
                with open(cgroup_path, 'r') as f:
                    content = f.read()
                    
                    # Docker
                    if '/docker/' in content:
                        container_id = self._extract_docker_id(content)
                        return ContainerRuntime.DOCKER, container_id
                    
                    # Kubernetes
                    if '/kubepods/' in content or 'kubepods' in content:
                        return ContainerRuntime.KUBERNETES, None
                    
                    # Podman
                    if '/libpod-' in content:
                        return ContainerRuntime.PODMAN, None
                    
                    # LXC
                    if '/lxc/' in content:
                        return ContainerRuntime.LXC, None
                    
                    # containerd
                    if '/containerd/' in content:
                        return ContainerRuntime.CONTAINERD, None
                    
                    # CRI-O
                    if '/crio-' in content:
                        return ContainerRuntime.CRIO, None
                        
            except (FileNotFoundError, PermissionError):
                continue
        
        # Check cgroup v2
        try:
            with open('/proc/self/mountinfo', 'r') as f:
                content = f.read()
                if 'docker' in content:
                    return ContainerRuntime.DOCKER, None
        except (FileNotFoundError, PermissionError):
            pass
        
        return ContainerRuntime.NONE, None
    
    def _extract_docker_id(self, cgroup_content: str) -> Optional[str]:
        """Extract Docker container ID from cgroup content."""
        # Pattern: /docker/<container_id>
        match = re.search(r'/docker/([a-f0-9]{64})', cgroup_content)
        if match:
            return match.group(1)
        
        # Short ID pattern
        match = re.search(r'/docker/([a-f0-9]{12})', cgroup_content)
        if match:
            return match.group(1)
        
        return None
    
    def _get_container_id(self, runtime: ContainerRuntime) -> Optional[str]:
        """Get container ID based on runtime."""
        if runtime == ContainerRuntime.NONE:
            return None
        
        # Try hostname (often the container ID in Docker)
        try:
            import socket
            hostname = socket.gethostname()
            # Docker short IDs are 12 hex chars
            if re.match(r'^[a-f0-9]{12}$', hostname):
                return hostname
        except Exception:
            pass
        
        return None
    
    def _detect_resource_limits(self) -> Tuple[
        Optional[int], Optional[float], Optional[int], Optional[int]
    ]:
        """Detect container resource limits from cgroups."""
        memory_limit = None
        cpu_limit = None
        cpu_quota = None
        cpu_period = None
        
        # cgroup v2 paths
        cgroup_v2_paths = {
            'memory_max': '/sys/fs/cgroup/memory.max',
            'cpu_max': '/sys/fs/cgroup/cpu.max',
        }
        
        # cgroup v1 paths
        cgroup_v1_paths = {
            'memory_limit': '/sys/fs/cgroup/memory/memory.limit_in_bytes',
            'cpu_quota': '/sys/fs/cgroup/cpu/cpu.cfs_quota_us',
            'cpu_period': '/sys/fs/cgroup/cpu/cpu.cfs_period_us',
        }
        
        # Try cgroup v2 first
        try:
            with open(cgroup_v2_paths['memory_max'], 'r') as f:
                value = f.read().strip()
                if value != 'max':
                    memory_limit = int(value)
        except (FileNotFoundError, PermissionError, ValueError):
            # Try cgroup v1
            try:
                with open(cgroup_v1_paths['memory_limit'], 'r') as f:
                    memory_limit = int(f.read().strip())
            except (FileNotFoundError, PermissionError, ValueError):
                pass
        
        # CPU limits
        try:
            with open(cgroup_v2_paths['cpu_max'], 'r') as f:
                parts = f.read().strip().split()
                if parts[0] != 'max':
                    cpu_quota = int(parts[0])
                    cpu_period = int(parts[1]) if len(parts) > 1 else 100000
                    cpu_limit = cpu_quota / cpu_period
        except (FileNotFoundError, PermissionError, ValueError):
            # Try cgroup v1
            try:
                with open(cgroup_v1_paths['cpu_quota'], 'r') as f:
                    cpu_quota = int(f.read().strip())
                with open(cgroup_v1_paths['cpu_period'], 'r') as f:
                    cpu_period = int(f.read().strip())
                if cpu_quota > 0 and cpu_period > 0:
                    cpu_limit = cpu_quota / cpu_period
            except (FileNotFoundError, PermissionError, ValueError):
                pass
        
        return memory_limit, cpu_limit, cpu_quota, cpu_period
    
    def _check_fuse_in_container(self) -> bool:
        """Check if FUSE is available in the container."""
        # Check for /dev/fuse device
        if not Path('/dev/fuse').exists():
            return False
        
        # Check if we can actually use it
        try:
            # Try to open /dev/fuse
            fd = os.open('/dev/fuse', os.O_RDWR)
            os.close(fd)
            return True
        except (OSError, PermissionError):
            return False
    
    def _check_privileged(self) -> bool:
        """Check if container is running in privileged mode."""
        # Privileged containers typically have access to all devices
        if not Path('/dev').exists():
            return False
        
        # Check for common privileged-mode indicators
        indicators = [
            # Access to all host devices
            Path('/dev/sda'),
            Path('/dev/mem'),
            # Docker socket
            Path('/var/run/docker.sock'),
            # Host PID namespace
            Path('/proc/1/root') if os.path.islink('/proc/1/root') else None,
        ]
        
        for indicator in indicators:
            if indicator and indicator.exists():
                return True
        
        # Check capabilities (if we have CAP_SYS_ADMIN, likely privileged)
        try:
            with open('/proc/self/status', 'r') as f:
                content = f.read()
                # CapEff line contains effective capabilities
                match = re.search(r'CapEff:\s+([0-9a-f]+)', content)
                if match:
                    cap_eff = int(match.group(1), 16)
                    # CAP_SYS_ADMIN is bit 21
                    if cap_eff & (1 << 21):
                        return True
        except (FileNotFoundError, PermissionError):
            pass
        
        return False
    
    def _detect_namespaces(self) -> List[str]:
        """Detect which namespaces are in use."""
        namespaces = []
        ns_path = Path('/proc/self/ns')
        
        if not ns_path.exists():
            return namespaces
        
        namespace_types = [
            'mnt',    # Mount namespace
            'pid',    # PID namespace
            'net',    # Network namespace
            'ipc',    # IPC namespace
            'uts',    # UTS namespace
            'user',   # User namespace
            'cgroup', # Cgroup namespace
            'time',   # Time namespace (Linux 5.6+)
        ]
        
        for ns_type in namespace_types:
            ns_file = ns_path / ns_type
            if ns_file.exists():
                namespaces.append(ns_type)
        
        return namespaces


# Global singleton
_detector = ContainerDetector()


def detect_container() -> ContainerInfo:
    """
    Detect container environment.
    
    This is the main entry point for container detection.
    Results are cached for performance.
    
    Returns:
        ContainerInfo with detection results.
    
    Example:
        >>> info = detect_container()
        >>> if info.is_containerized:
        ...     print(f"Running in {info.runtime_name}")
        ...     if info.memory_limit_bytes:
        ...         print(f"Memory limit: {info.memory_limit_bytes / (1024**3):.1f} GB")
    """
    return _detector.detect()


def is_containerized() -> bool:
    """
    Quick check if running in a container.
    
    Returns:
        True if running in any container environment.
    """
    return detect_container().is_containerized


def get_container_runtime() -> ContainerRuntime:
    """
    Get the container runtime type.
    
    Returns:
        ContainerRuntime enum value.
    """
    return detect_container().runtime


def is_fuse_available_in_container() -> bool:
    """
    Check if FUSE is available in the container.
    
    This is important for ΣVAULT since it may need FUSE
    for virtual filesystem mounting.
    
    Returns:
        True if FUSE can be used in the container.
    """
    return detect_container().fuse_available


__all__ = [
    'ContainerRuntime',
    'ContainerInfo',
    'ContainerDetector',
    'detect_container',
    'is_containerized',
    'get_container_runtime',
    'is_fuse_available_in_container',
]
