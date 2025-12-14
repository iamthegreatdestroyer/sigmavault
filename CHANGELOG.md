# Changelog

All notable changes to ΣVAULT will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned
- Windows filesystem driver (WinFsp)
- Hardware security key integration
- Vault migration tools
- Performance benchmarking suite

## [1.0.0] - 2025-01-XX

### Added
- **Dimensional Scattering Engine**
  - 8-dimensional addressing manifold (Spatial, Temporal, Entropic, Semantic, Fractal, Phase, Topological, Holographic)
  - Self-referential topology generation (content determines storage)
  - Temporal variance (automatic re-scattering over time)
  - Holographic redundancy for data resilience

- **Entropic Mixer**
  - Key-dependent signal/noise interleaving
  - Coordinate-specific mixing patterns
  - Configurable entropy ratio (0.3-0.7)

- **Hybrid Key Derivation**
  - Device fingerprinting (CPU, disk, MAC, TPM)
  - User passphrase (Argon2id / PBKDF2 fallback)
  - Three modes: HYBRID, DEVICE_ONLY, USER_ONLY
  - Non-reversible key mixing

- **FUSE Filesystem Layer**
  - Transparent mount/unmount
  - Standard filesystem operations (read, write, mkdir, etc.)
  - In-memory caching with dirty tracking
  - Automatic scatter on write, gather on read

- **Vault Lock Manager**
  - Per-file additional encryption
  - Separate lock passphrase from vault passphrase
  - Selective file locking

- **CLI Interface**
  - `sigmavault create` - Create new vault
  - `sigmavault mount` - Mount vault filesystem
  - `sigmavault info` - Display vault information
  - `sigmavault demo` - Run demonstration

### Security
- Constant-time key comparisons
- No key material in logs or errors
- Device binding prevents key portability attacks
- Temporal variance defeats pattern analysis

### Known Issues
- Memory forensics can recover decrypted data from RAM
- No hidden volume / deniability support
- Windows support not yet implemented

---

## Version History

| Version | Date | Highlights |
|---------|------|------------|
| 1.0.0 | 2025-01 | Initial release with full dimensional scattering |

---

## Upgrade Guide

### From Pre-release to 1.0.0
This is the initial release. No migration needed.

---

## Links
- [GitHub Repository](https://github.com/YOUR_USERNAME/sigmavault)
- [Issue Tracker](https://github.com/YOUR_USERNAME/sigmavault/issues)
- [Security Policy](SECURITY.md)
