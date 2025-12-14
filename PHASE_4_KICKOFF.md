# Phase 4: Platform Support Expansion

## Executive Summary

Phase 4 extends ΣVAULT's reach across multiple platforms and deployment environments. Building on the solid foundation of Phase 3 (39 tests passing, baseline performance established), we now focus on platform abstraction, containerization, and cloud storage backends.

**Agents:** @NEXUS (synthesis), @FLUX (DevOps), @CORE (low-level systems)  
**Timeline:** Weeks 13-16  
**Priority:** HIGH

---

## Objectives

### Primary Goals

1. **Storage Abstraction Layer** — Unified interface for multiple storage backends
2. **Windows Support** — Full WinFsp integration for native Windows filesystem
3. **Container Support** — Docker/Podman images for portable deployment
4. **Cloud Storage Backends** — S3-compatible and Azure Blob support
5. **Cross-Platform CI/CD** — Platform-specific testing workflows

### Target Platform Matrix

| Platform         | Status     | Target                  |
| ---------------- | ---------- | ----------------------- |
| Linux (ext4)     | ✅ Primary | Production-ready        |
| Windows (WinFsp) | ⚠️ Partial | Full FUSE compatibility |
| macOS (macFUSE)  | 🔄 Working | FSEvents optimization   |
| Docker           | 📋 Planned | Multi-arch images       |
| AWS S3           | 📋 Planned | Full backend support    |
| Azure Blob       | 📋 Planned | Full backend support    |

---

## Architecture

### Storage Backend Abstraction

```
┌─────────────────────────────────────────────────────────┐
│                 ΣVAULT Core Engine                      │
│     (DimensionalScatterEngine, EntropicMixer)          │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│              StorageBackend Interface                   │
│  read(offset, size) → bytes                            │
│  write(offset, data) → None                            │
│  size() → int                                          │
│  sync() → None                                         │
│  supports_sparse() → bool                              │
└────────────────────────┬────────────────────────────────┘
                         │
         ┌───────────────┼───────────────┐
         │               │               │
         ▼               ▼               ▼
┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│ FileBackend │  │  S3Backend  │  │ AzureBackend│
│ (Local FS)  │  │ (AWS/MinIO) │  │ (Blob Stor) │
└─────────────┘  └─────────────┘  └─────────────┘
```

### Platform Abstraction

```
┌─────────────────────────────────────────────────────────┐
│                  Platform Interface                     │
│  get_device_fingerprint() → bytes                      │
│  get_filesystem_driver() → FSDriver                    │
│  get_secure_storage() → SecureStorage                  │
└────────────────────────┬────────────────────────────────┘
                         │
         ┌───────────────┼───────────────┐
         │               │               │
         ▼               ▼               ▼
┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│LinuxPlatform│  │WinPlatform  │  │MacPlatform  │
│ (FUSE3)     │  │ (WinFsp)    │  │ (macFUSE)   │
└─────────────┘  └─────────────┘  └─────────────┘
```

---

## Implementation Plan

### Week 1: Storage Abstraction Layer

**Deliverables:**

- [ ] `drivers/storage/__init__.py` — Package initialization
- [ ] `drivers/storage/base.py` — Abstract `StorageBackend` interface
- [ ] `drivers/storage/file_backend.py` — Local filesystem implementation
- [ ] `drivers/storage/memory_backend.py` — In-memory backend (testing)
- [ ] Unit tests for storage backends

**Interface Definition:**

```python
from abc import ABC, abstractmethod
from typing import Optional

class StorageBackend(ABC):
    """Abstract interface for storage backends."""

    @abstractmethod
    def read(self, offset: int, size: int) -> bytes:
        """Read bytes from storage at given offset."""
        pass

    @abstractmethod
    def write(self, offset: int, data: bytes) -> None:
        """Write bytes to storage at given offset."""
        pass

    @abstractmethod
    def size(self) -> int:
        """Return total size of storage medium."""
        pass

    @abstractmethod
    def sync(self) -> None:
        """Ensure all writes are persisted."""
        pass

    @property
    @abstractmethod
    def supports_sparse(self) -> bool:
        """Whether backend supports sparse files/objects."""
        pass

    def truncate(self, size: int) -> None:
        """Resize the storage medium."""
        raise NotImplementedError("Backend does not support truncate")
```

### Week 2: Platform Abstraction & Windows Support

**Deliverables:**

- [ ] `drivers/platform/__init__.py` — Package initialization
- [ ] `drivers/platform/base.py` — Abstract `Platform` interface
- [ ] `drivers/platform/linux.py` — Linux-specific implementation
- [ ] `drivers/platform/windows.py` — Windows WinFsp integration
- [ ] `drivers/platform/macos.py` — macOS-specific implementation
- [ ] Platform detection and auto-selection

**Windows WinFsp Integration:**

```python
class WindowsPlatform(Platform):
    """Windows platform implementation using WinFsp."""

    def get_filesystem_driver(self) -> FSDriver:
        try:
            import winfspy
            return WinFspDriver()
        except ImportError:
            raise PlatformError(
                "WinFsp not installed. Get it from: "
                "https://github.com/winfsp/winfsp/releases"
            )

    def get_device_fingerprint(self) -> bytes:
        """Windows-specific device fingerprinting."""
        import subprocess
        # Get Windows-specific identifiers
        wmic_cpu = subprocess.check_output(
            "wmic cpu get ProcessorId", shell=True
        ).decode()
        wmic_disk = subprocess.check_output(
            "wmic diskdrive get SerialNumber", shell=True
        ).decode()
        # Combine into fingerprint
        return self._derive_fingerprint(wmic_cpu, wmic_disk)
```

### Week 3: Container Support

**Deliverables:**

- [ ] `Dockerfile` — Multi-stage build for minimal image
- [ ] `docker-compose.yml` — Development environment
- [ ] `.dockerignore` — Exclude unnecessary files
- [ ] GitHub Actions workflow for container builds
- [ ] Container registry publishing (ghcr.io)

**Dockerfile Strategy:**

```dockerfile
# Build stage
FROM python:3.11-slim AS builder
WORKDIR /app
COPY pyproject.toml .
RUN pip install build && python -m build

# Runtime stage
FROM python:3.11-slim AS runtime
RUN apt-get update && apt-get install -y fuse3 libfuse3-dev
COPY --from=builder /app/dist/*.whl /tmp/
RUN pip install /tmp/*.whl && rm /tmp/*.whl
ENTRYPOINT ["sigmavault"]
```

### Week 4: Cloud Storage Backends

**Deliverables:**

- [ ] `drivers/storage/s3_backend.py` — AWS S3 / MinIO support
- [ ] `drivers/storage/azure_backend.py` — Azure Blob Storage support
- [ ] Cloud backend configuration schema
- [ ] Integration tests with LocalStack/Azurite
- [ ] Documentation for cloud deployment

**S3 Backend Design:**

```python
class S3StorageBackend(StorageBackend):
    """AWS S3 compatible storage backend."""

    def __init__(
        self,
        bucket: str,
        prefix: str = "sigmavault/",
        endpoint_url: Optional[str] = None,  # For MinIO
        chunk_size: int = 5 * 1024 * 1024,   # 5MB chunks
    ):
        self.bucket = bucket
        self.prefix = prefix
        self.chunk_size = chunk_size
        self.client = boto3.client('s3', endpoint_url=endpoint_url)

    def read(self, offset: int, size: int) -> bytes:
        """Read using S3 range requests."""
        chunk_start = offset // self.chunk_size
        chunk_end = (offset + size - 1) // self.chunk_size

        data = b''
        for chunk_idx in range(chunk_start, chunk_end + 1):
            chunk_data = self._get_chunk(chunk_idx)
            data += chunk_data

        # Extract exact range
        start_offset = offset % self.chunk_size
        return data[start_offset:start_offset + size]

    @property
    def supports_sparse(self) -> bool:
        return True  # S3 objects can be any size
```

---

## Testing Strategy

### Platform-Specific Tests

```python
import pytest
import platform

@pytest.mark.skipif(
    platform.system() != "Windows",
    reason="Windows-only test"
)
def test_winfsp_mount():
    """Test Windows filesystem mounting via WinFsp."""
    pass

@pytest.mark.skipif(
    platform.system() != "Linux",
    reason="Linux-only test"
)
def test_fuse3_mount():
    """Test Linux filesystem mounting via FUSE3."""
    pass
```

### Container Tests

```yaml
# .github/workflows/container-test.yml
jobs:
  container-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Build container
        run: docker build -t sigmavault:test .
      - name: Run container tests
        run: |
          docker run --privileged sigmavault:test \
            python -m pytest tests/ -v
```

### Cloud Backend Tests (LocalStack)

```python
@pytest.fixture
def localstack_s3():
    """Provide LocalStack S3 for testing."""
    import docker
    client = docker.from_env()
    container = client.containers.run(
        "localstack/localstack",
        detach=True,
        ports={"4566/tcp": 4566},
        environment={"SERVICES": "s3"}
    )
    yield "http://localhost:4566"
    container.stop()
    container.remove()

def test_s3_backend_write_read(localstack_s3):
    """Test S3 backend basic operations."""
    backend = S3StorageBackend(
        bucket="test-bucket",
        endpoint_url=localstack_s3
    )
    backend.write(0, b"Hello ΣVAULT")
    assert backend.read(0, 12) == b"Hello ΣVAULT"
```

---

## Success Criteria

### Functional Requirements

- [ ] Storage abstraction supports file, memory, S3, Azure backends
- [ ] Windows WinFsp mounts work identically to Linux FUSE
- [ ] Docker container runs on linux/amd64 and linux/arm64
- [ ] Cloud backends pass all integration tests
- [ ] Cross-platform CI passes on all target platforms

### Performance Requirements

- [ ] File backend: No regression from Phase 3 baseline
- [ ] S3 backend: < 100ms latency for 1MB reads (same region)
- [ ] Container startup: < 5 seconds
- [ ] Memory backend: > 1 GB/sec throughput

### Quality Requirements

- [ ] Test coverage ≥ 85% for new code
- [ ] All platforms tested in CI
- [ ] Documentation for each backend/platform
- [ ] No security regressions

---

## Dependencies

### New Python Packages

```toml
[project.optional-dependencies]
cloud = [
    "boto3>=1.26.0",        # AWS S3
    "azure-storage-blob",   # Azure Blob
]
windows = [
    "winfspy>=0.8.0",       # WinFsp Python bindings
]
container = [
    "docker>=6.0.0",        # Docker SDK (testing)
]
```

### External Dependencies

| Dependency | Platform | Purpose                           |
| ---------- | -------- | --------------------------------- |
| WinFsp     | Windows  | FUSE-compatible filesystem driver |
| macFUSE    | macOS    | FUSE implementation               |
| FUSE3      | Linux    | Filesystem in userspace           |
| LocalStack | Testing  | AWS service emulation             |
| Azurite    | Testing  | Azure Blob emulation              |

---

## Risk Assessment

### Technical Risks

| Risk                             | Probability | Impact | Mitigation                      |
| -------------------------------- | ----------- | ------ | ------------------------------- |
| WinFsp API differences           | Medium      | High   | Comprehensive wrapper layer     |
| Cloud latency issues             | Low         | Medium | Local caching, async operations |
| Container privilege requirements | Medium      | Medium | Document FUSE_ALLOW_OTHER       |
| Platform-specific bugs           | Medium      | Medium | Extensive CI coverage           |

### Schedule Risks

| Risk                          | Probability | Impact | Mitigation                        |
| ----------------------------- | ----------- | ------ | --------------------------------- |
| WinFsp integration complexity | High        | Medium | Start early, allocate buffer      |
| Cloud backend edge cases      | Medium      | Low    | Focus on core functionality first |

---

## Phase 4 Status

```
Phase 4 Status: IN PROGRESS
Start Date: 2025-12-11
Target Completion: Week 16

Progress:
├── Storage Abstraction Layer: 📋 Not Started
├── Platform Abstraction: 📋 Not Started
├── Windows WinFsp Support: 📋 Not Started
├── Container Support: 📋 Not Started
├── Cloud Storage Backends: 📋 Not Started
└── Cross-Platform CI/CD: 📋 Not Started
```

---

**Phase 4 Lead:** @NEXUS (Cross-Domain Synthesis)  
**Supporting Agents:** @FLUX (DevOps), @CORE (Low-Level Systems)

_"Systems are only as powerful as their connections."_ — @SYNAPSE
