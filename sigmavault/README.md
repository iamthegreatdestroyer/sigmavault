# ΣVAULT - Sub-Linear Encrypted Abstraction of Underlying Linear Technology

[![CI](https://github.com/iamthegreatdestroyer/sigmavault/actions/workflows/ci.yml/badge.svg)](https://github.com/iamthegreatdestroyer/sigmavault/actions/workflows/ci.yml)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Security Policy](https://img.shields.io/badge/security-policy-green.svg)](SECURITY.md)

**A trans-dimensional filesystem where data doesn't exist in recognizable form.**

---

## The Vision

Current encryption treats data as a sequence of bytes to be transformed. ΣVAULT treats data as a **probability cloud** dispersed across an N-dimensional manifold that only coalesces into recognizable form when observed through the correct key.

```
Traditional Storage:        ΣVAULT Storage:

┌────────────────────┐     ┌────────────────────┐
│ file.txt           │     │ ░░▓▓░░▓▓░░░░▓▓░░▓▓ │
│ "Hello World"      │     │ ░▓░░▓░▓▓░░░░▓░░▓░░ │
│                    │     │ ▓░░▓░░░░▓▓░░▓▓░▓░▓ │
│ [contiguous bytes] │     │ [scattered bits]   │
└────────────────────┘     │ [no file structure]│
                           └────────────────────┘
```

**Without the key, you cannot even identify which bits belong to which file.**

---

## Core Innovations

### 1. Dimensional Scattering

Data isn't stored "somewhere" — its bits are dispersed across an 8-dimensional addressing manifold:

| Dimension       | Purpose                                    |
| --------------- | ------------------------------------------ |
| **SPATIAL**     | Physical position on medium                |
| **TEMPORAL**    | Time-variant component (changes over time) |
| **ENTROPIC**    | Noise interleaving axis                    |
| **SEMANTIC**    | Content-derived offset                     |
| **FRACTAL**     | Self-similar recursion level               |
| **PHASE**       | Wave-like interference angle               |
| **TOPOLOGICAL** | Graph connectivity relationships           |
| **HOLOGRAPHIC** | Redundancy shard identification            |

### 2. Entropic Indistinguishability

Real data bits are mixed with generated entropy in a key-dependent pattern. Without the key:

- You cannot identify which bits are signal vs. noise
- The ratio of real:entropy bits varies by location
- The mixing pattern is non-repeating

### 3. Self-Referential Topology

**The file's content determines where it's stored.**

The first N bits of a file are used to derive the storage topology for the remaining bits. This creates a cryptographic bootstrap problem:

- You need content to find content
- But you need to find content to have content
- Without the key, you cannot begin

### 4. Temporal Variance

**Same file → Different physical representation over time**

Background processes continuously re-scatter static files. An attacker observing storage over time sees constantly changing patterns with no correlation to actual file changes.

### 5. Holographic Redundancy

Inspired by holography: any sufficiently large fragment contains information to reconstruct the whole (with graceful degradation). No single point of failure.

---

## Installation

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/sigmavault.git
cd sigmavault

# Install dependencies
pip install -e .

# For FUSE filesystem support
pip install fusepy
```

### System Requirements

- Python 3.9+
- NumPy
- FUSE (for filesystem mounting)
  - Linux: `sudo apt install fuse3`
  - macOS: [macFUSE](https://osxfuse.github.io/)
  - Windows: [WinFsp](https://github.com/winfsp/winfsp)

---

## Quick Start

### Create and Mount a Vault

```bash
# Create a new vault
sigmavault create /path/to/storage --mode=hybrid

# Mount it
mkdir /mnt/secure
sigmavault mount /mnt/secure /path/to/storage

# Use it like any filesystem
cp secret_document.pdf /mnt/secure/
ls /mnt/secure/
cat /mnt/secure/secret_document.pdf  # Works transparently

# Unmount
fusermount -u /mnt/secure
```

### Lock Specific Files

```python
from sigmavault.filesystem import SigmaVaultFS

# Lock a sensitive file with additional passphrase
fs.lock_file("/secrets/passwords.txt", "extra_secret_passphrase")

# Attempting to read locked file returns access denied
# Must unlock first
fs.unlock_file("/secrets/passwords.txt", "extra_secret_passphrase")
```

### Key Modes

| Mode     | Security | Portability                           |
| -------- | -------- | ------------------------------------- |
| `hybrid` | Maximum  | Requires original device + passphrase |
| `device` | High     | No passphrase, but device-locked      |
| `user`   | Medium   | Portable, passphrase only             |

```bash
# Create with different modes
sigmavault create /storage --mode=hybrid   # Default: most secure
sigmavault create /storage --mode=device   # Device-bound only
sigmavault create /storage --mode=user     # Passphrase only (portable)
```

---

## How It Works

### Storage Flow

```
USER FILE                        ΣVAULT STORAGE
    │
    ▼
┌─────────────────┐
│ Content Analysis│──────────────────────────────────┐
│ (Self-Referential)                                 │
└────────┬────────┘                                  │
         │                                           │
         ▼                                           ▼
┌─────────────────┐                     ┌────────────────────┐
│ Topology        │                     │ Storage Topology   │
│ Generation      │────────────────────▶│ (content-derived)  │
└────────┬────────┘                     └────────────────────┘
         │                                           │
         ▼                                           │
┌─────────────────┐                                  │
│ Chunk into      │                                  │
│ Shards          │                                  │
└────────┬────────┘                                  │
         │                                           │
         ▼                                           │
┌─────────────────┐      ┌─────────────────┐        │
│ For each shard: │      │ Dimensional     │        │
│                 │─────▶│ Coordinate      │        │
│                 │      │ Generation      │        │
└────────┬────────┘      └────────┬────────┘        │
         │                        │                  │
         ▼                        ▼                  │
┌─────────────────┐      ┌─────────────────┐        │
│ Entropic        │      │ N-Dimensional   │◀───────┘
│ Mixing          │─────▶│ Scatter         │
└─────────────────┘      └────────┬────────┘
                                  │
                                  ▼
                         ┌─────────────────┐
                         │ Physical Medium │
                         │ (appears random)│
                         └─────────────────┘
```

### Retrieval Flow

```
RETRIEVAL REQUEST
    │
    ▼
┌─────────────────┐
│ Verify Key      │──── Invalid ────▶ ACCESS DENIED
└────────┬────────┘
         │ Valid
         ▼
┌─────────────────┐
│ Derive Topology │
│ from Key + ID   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Calculate       │
│ Coordinates     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Gather Scattered│
│ Bits            │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Entropic        │
│ Unmixing        │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Reconstruct     │
│ Original File   │
└─────────────────┘
```

---

## Security Properties

### What ΣVAULT Protects Against

| Attack                  | Protection                                     |
| ----------------------- | ---------------------------------------------- |
| **Direct Read**         | Data is scattered, appears as noise            |
| **Pattern Analysis**    | Entropic mixing eliminates patterns            |
| **Known Plaintext**     | Self-referential topology prevents correlation |
| **Time-based Analysis** | Temporal variance changes representation       |
| **Partial Recovery**    | Need threshold of data for any reconstruction  |
| **Device Theft**        | Hybrid mode requires both device + passphrase  |
| **Passphrase Theft**    | Hybrid mode requires original device           |

### What ΣVAULT Does NOT Protect Against

- Physical access to running, unlocked system
- Memory forensics on active system
- Keyloggers capturing passphrase
- Rubber-hose cryptanalysis (coercion)

---

## API Reference

### Python API

```python
from sigmavault import (
    DimensionalScatterEngine,
    KeyState,
    HybridKeyDerivation,
    KeyMode,
)

# Create key derivation
kdf = HybridKeyDerivation(mode=KeyMode.HYBRID)
salt = kdf.initialize()
master_key = kdf.derive_key(passphrase="your_secret")

# Create scatter engine
key_state = KeyState.derive(master_key)
engine = DimensionalScatterEngine(key_state, medium_size=10_000_000_000)

# Scatter data
file_id = os.urandom(16)
scattered = engine.scatter(file_id, file_content)

# Gather data
reconstructed = engine.gather(scattered)
```

### CLI Commands

```bash
sigmavault create <storage_path> [--mode=hybrid|device|user] [--force]
sigmavault mount <mount_point> <storage_path> [--mode=...] [--foreground]
sigmavault info <storage_path>
sigmavault demo
```

---

## Architecture

```
sigmavault/
├── core/
│   └── dimensional_scatter.py   # N-dimensional scattering engine
├── crypto/
│   └── hybrid_key.py           # Device + user key derivation
├── filesystem/
│   └── fuse_layer.py           # Transparent FUSE filesystem
├── cli.py                      # Command-line interface
└── __init__.py
```

---

## Relationship to ΣLANG

ΣVAULT is the third project in the Σ-series:

1. **ΣLANG** - Semantic compression for LLM internal representation
2. **Ryot LLM** - CPU-first LLM inference engine (uses ΣLANG)
3. **ΣVAULT** - Trans-dimensional encrypted storage (inspired by ΣLANG's sub-linear principles)

While ΣLANG compresses **meaning**, ΣVAULT scatters **existence**. Both operate on principles that transcend linear byte-sequence thinking.

---

## Performance Considerations

| Operation | Overhead                                |
| --------- | --------------------------------------- |
| Write     | ~1.5-2x due to entropic expansion       |
| Read      | ~1.5x due to gathering                  |
| Storage   | ~1.3-1.5x due to holographic redundancy |

For maximum performance, ΣVAULT caches frequently accessed files in memory after decryption.

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

Areas for contribution:

- Windows filesystem driver (WinFsp integration)
- macOS filesystem driver (macFUSE optimization)
- Hardware acceleration for scattering operations
- Additional holographic redundancy schemes
- Formal security analysis

---

## Development Roadmap

ΣVAULT follows a **12-phase development roadmap** toward production readiness:

- **Phase 1-2:** Foundation & Cryptographic Hardening (Weeks 1-8)
- **Phase 3-4:** Performance & Platform Support (Weeks 9-16)
- **Phase 5-6:** ML Integration & Quantum-Safe (Weeks 17-28)
- **Phase 7-8:** Formal Verification & Cryptanalysis (Weeks 29-40)
- **Phase 9-10:** Ecosystem & Distribution (Weeks 41-52)
- **Phase 11-12:** Production Hardening & Launch (Weeks 53-60)

**Current Status:** Phase 1 - Foundation & Validation (Active)

**Full Roadmap:** See [MASTER_CLASS_ACTION_PLAN.md](.github/MASTER_CLASS_ACTION_PLAN.md)  
**Executive Summary:** See [MASTER_CLASS_ACTION_PLAN_EXECUTIVE_SUMMARY.md](.github/MASTER_CLASS_ACTION_PLAN_EXECUTIVE_SUMMARY.md)  
**Phase 1 Guide:** See [PHASE_1_GETTING_STARTED.md](.github/PHASE_1_GETTING_STARTED.md)

### Key Milestones

- Week 4: Architecture validation complete
- Week 8: Cryptographic hardening done
- Week 16: Performance optimization finished
- Week 28: Quantum-safe integration complete
- Week 48: Production release ready

---

## License

MIT License - See [LICENSE](LICENSE)

---

## Disclaimer

ΣVAULT is experimental cryptographic software. While designed with security in mind, it has not undergone formal security audit. Use at your own risk for sensitive data. Always maintain backups.

---

_"The most secure data is data that doesn't exist in recognizable form."_
