# Security Policy

## ⚠️ Important Disclaimer

ΣVAULT is **experimental cryptographic software**. While designed with security as a primary goal, it has **not undergone formal security audit**. 

**Do not use ΣVAULT as your sole protection for critical data without:**
- Independent security review
- Comprehensive backup strategy
- Understanding of the threat model

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.x.x   | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability

### For Critical Vulnerabilities

If you discover a vulnerability that could allow:
- **Unauthorized data access** without the key
- **Key material extraction** from running system
- **Complete bypass** of encryption
- **Cryptographic weaknesses** that reduce security

**Please DO NOT file a public GitHub issue.**

Instead:

1. **Email the maintainers directly** with:
   - Description of the vulnerability
   - Steps to reproduce (if applicable)
   - Your assessment of severity
   - Any suggested fixes

2. **We will respond within 48 hours** to acknowledge receipt

3. **We will provide a timeline** for addressing the issue

4. **You will be credited** in the security advisory (unless you prefer anonymity)

### For Non-Critical Issues

For less severe security issues (DoS, theoretical weaknesses, hardening suggestions), you may:
- Open a GitHub issue with the `security` label
- Avoid including complete exploitation details
- Use the security issue template

## Security Architecture

### Threat Model

ΣVAULT is designed to protect against:

| Threat | Protection Level |
|--------|------------------|
| Offline storage analysis | ✅ Strong - Data appears as entropy |
| Pattern analysis | ✅ Strong - Temporal variance defeats patterns |
| Known plaintext attacks | ✅ Strong - Self-referential topology |
| Key theft (passphrase only) | ✅ Strong - Requires device in hybrid mode |
| Device theft (no passphrase) | ✅ Strong - Requires passphrase in hybrid mode |
| Memory forensics | ⚠️ Limited - Decrypted data in RAM during access |
| Keyloggers | ❌ Not protected - Use hardware keys for high security |
| Coercion/Rubber-hose | ❌ Not protected - Consider hidden volumes |

### Cryptographic Components

| Component | Implementation |
|-----------|----------------|
| Key Derivation | Argon2id (or PBKDF2 fallback) |
| Entropy Source | `secrets` module (OS CSPRNG) |
| Hashing | SHA-256, SHA-512 |
| Mixing | Custom non-reversible hybrid mixer |

### Known Limitations

1. **No Perfect Forward Secrecy** - Compromised master key exposes all data
2. **Metadata Leakage** - File count and approximate sizes may be inferable
3. **No Deniability** - Cannot prove vault contains only decoy data
4. **Python Memory** - Cannot guarantee sensitive data is zeroed

## Security Best Practices

When using ΣVAULT:

1. **Use Hybrid Mode** for maximum security (device + passphrase)
2. **Strong Passphrase** - Use a passphrase manager, 20+ characters
3. **Secure Environment** - Don't mount vaults on compromised systems
4. **Regular Backups** - ΣVAULT is not a backup solution
5. **Update Regularly** - Security fixes are released as patches

## Acknowledgments

We thank the following for responsible disclosure:
- *(This section will list security researchers who report issues)*

---

*Last updated: 2025*
