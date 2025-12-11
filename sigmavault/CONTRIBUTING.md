# Contributing to ΣVAULT

Thank you for your interest in contributing to ΣVAULT! This document provides guidelines and instructions for contributing to this trans-dimensional encrypted storage system.

## Table of Contents
- [Code of Conduct](#code-of-conduct)
- [Security Considerations](#security-considerations)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Making Changes](#making-changes)
- [Testing](#testing)
- [Submitting Changes](#submitting-changes)
- [Style Guidelines](#style-guidelines)

## Code of Conduct

Be respectful, inclusive, and constructive. We're building security software that people trust with their data — quality and integrity matter.

## Security Considerations

**ΣVAULT is cryptographic software.** All contributions must prioritize security:

### DO:
- Use constant-time comparisons for secrets (`secrets.compare_digest`)
- Zero sensitive memory when possible
- Use cryptographically secure random sources (`secrets` module)
- Consider timing side-channels in crypto code
- Document security assumptions

### DON'T:
- Hardcode keys, salts, or secrets
- Log or print key material
- Use `random` module for security-sensitive operations
- Reduce entropy without explicit justification
- Introduce new dependencies without security review

### Reporting Vulnerabilities
See [SECURITY.md](SECURITY.md) for responsible disclosure guidelines.

## Getting Started

1. **Fork the repository** on GitHub
2. **Clone your fork** locally:
   ```bash
   git clone https://github.com/YOUR_USERNAME/sigmavault.git
   cd sigmavault
   ```
3. **Add upstream remote**:
   ```bash
   git remote add upstream https://github.com/ORIGINAL_OWNER/sigmavault.git
   ```

## Development Setup

### Prerequisites
- Python 3.9 or higher
- NumPy
- FUSE (for filesystem testing)
  - Linux: `sudo apt install fuse3 libfuse3-dev`
  - macOS: [macFUSE](https://osxfuse.github.io/)

### Installation
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode with all dependencies
pip install -e ".[full,dev]"
```

### Verify Setup
```bash
# Run tests
python -m pytest tests/ -v

# Run demo
python -m sigmavault.cli demo
```

## Making Changes

### Branch Naming
- `feature/description` - New features
- `fix/description` - Bug fixes
- `security/description` - Security improvements
- `docs/description` - Documentation changes
- `refactor/description` - Code refactoring
- `perf/description` - Performance improvements

### Workflow
1. Create a branch from `main`:
   ```bash
   git checkout -b feature/my-new-feature
   ```

2. Make your changes, following the [Style Guidelines](#style-guidelines)

3. Write or update tests as needed

4. Run the test suite:
   ```bash
   python -m pytest tests/ -v
   ```

5. Run the demo to verify functionality:
   ```bash
   python -m sigmavault.cli demo
   ```

6. Commit your changes:
   ```bash
   git commit -m "feat: add new scattering dimension for improved security"
   ```

## Testing

### Running Tests
```bash
# All tests
python -m pytest tests/ -v

# With coverage
python -m pytest tests/ -v --cov=sigmavault

# Specific test file
python -m pytest tests/test_sigmavault.py -v

# Security-focused tests only
python -m pytest tests/ -v -k "security"
```

### Writing Tests
- Place tests in `tests/` directory
- Use descriptive test names: `test_scatter_gather_roundtrip_preserves_data`
- Include both positive and negative test cases
- Test edge cases (empty files, large files, special characters)
- Test security properties (key changes → different output)

### Test Structure
```python
class TestDimensionalScatter(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures."""
        self.key_state = create_test_key_state()
        self.engine = DimensionalScatterEngine(self.key_state, 1_000_000)
    
    def test_scatter_gather_roundtrip(self):
        """Test that scatter→gather preserves original data."""
        original = b"Test data for scattering"
        file_id = secrets.token_bytes(16)
        
        scattered = self.engine.scatter(file_id, original)
        reconstructed = self.engine.gather(scattered)
        
        self.assertEqual(reconstructed[:len(original)], original)
    
    def test_different_keys_produce_different_scatter(self):
        """Test that different keys scatter to different locations."""
        # Security property test
        pass
```

## Submitting Changes

### Commit Messages
Follow [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` - New feature
- `fix:` - Bug fix
- `security:` - Security improvement
- `docs:` - Documentation changes
- `style:` - Code style changes
- `refactor:` - Code refactoring
- `perf:` - Performance improvements
- `test:` - Adding or updating tests
- `chore:` - Maintenance tasks

Examples:
```
feat: add 9th dimension for quantum-resistant scattering
fix: resolve entropy ratio calculation in unmix operation
security: use constant-time comparison for key verification
perf: optimize LSH lookup in dimensional coordinate generation
```

### Pull Request Process
1. Update documentation if needed
2. Ensure all tests pass
3. Update CHANGELOG.md with your changes
4. Submit PR against `main` branch
5. Fill out the PR template completely
6. Wait for review

### Review Process
- Security-sensitive PRs require additional review
- PRs require at least one approval
- Address all review comments
- Keep PRs focused and reasonably sized

## Style Guidelines

### Python Style
- Follow PEP 8
- Use type hints for all public functions
- Maximum line length: 100 characters
- Use docstrings (Google style) for public functions/classes

### Documentation
```python
def scatter(self, file_id: bytes, content: bytes) -> ScatteredFile:
    """
    Scatter file content across dimensional manifold.
    
    Disperses the input bytes across an N-dimensional addressing
    space, mixing with entropy and applying temporal variance.
    
    Args:
        file_id: Unique 16-byte identifier for the file
        content: Raw file bytes to scatter
        
    Returns:
        ScatteredFile containing coordinates and scattered data
        
    Raises:
        ValueError: If file_id is not 16 bytes
        
    Security:
        - Content influences storage topology (self-referential)
        - Entropy mixing ratio determined by key state
        
    Example:
        >>> scattered = engine.scatter(file_id, b"secret data")
        >>> print(f"Shards: {len(scattered.shard_coordinates)}")
        Shards: 8
    """
```

### Security-Sensitive Code
```python
# SECURITY: Use constant-time comparison for key verification
if not secrets.compare_digest(provided_hash, stored_hash):
    raise AuthenticationError("Invalid key")

# SECURITY: Zero sensitive data after use
key_material = derive_key(passphrase)
try:
    result = use_key(key_material)
finally:
    # Best effort zeroing (Python doesn't guarantee this)
    key_material = b'\x00' * len(key_material)
```

## Areas for Contribution

### High Priority
- [ ] Windows filesystem driver (WinFsp integration)
- [ ] Formal security analysis/audit preparation
- [ ] Performance benchmarking suite
- [ ] Additional holographic redundancy schemes
- [ ] Hardware acceleration for scattering

### Medium Priority
- [ ] macOS filesystem optimization
- [ ] Additional key derivation modes
- [ ] Vault migration tools
- [ ] Compression before scattering (optional)
- [ ] Remote storage backends

### Documentation
- [ ] Security architecture deep-dive
- [ ] Performance tuning guide
- [ ] Threat model documentation
- [ ] API reference (Sphinx)

## Questions?

Open an issue with the `question` label or start a discussion.

---

Thank you for helping make ΣVAULT more secure and capable! 🔐
