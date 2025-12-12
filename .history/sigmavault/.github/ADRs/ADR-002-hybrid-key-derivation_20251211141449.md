# ADR-002: Hybrid Key Derivation Strategy

**Status:** PROPOSED  
**Date:** December 11, 2025  
**Author:** @CIPHER, @APEX  
**Reviewers:** @ARCHITECT, @AXIOM, @FORTRESS

---

## Context

ΣVAULT's security model depends on deriving a cryptographically strong master key from two sources:

1. **Device Fingerprint** - Hardware characteristics unique to the physical device
2. **User Passphrase** - User-provided entropy and memorability

The architectural question is: **How should device and user entropy be combined to create a secure, usable, and recoverable key?**

This decision affects:

- Security model (key compromise scenarios)
- Portability (can user move vault to different device?)
- User experience (password entry complexity)
- Key recovery (what happens if device fails?)
- Threat model (physical theft, remote compromise, key escrow)

---

## Decision

**We adopt a Hybrid Key Derivation Model with three operational modes:**

### Hybrid Key Formula

```
MASTER_KEY_512 = Argon2id(
    passphrase = SHA256(user_passphrase),
    salt = HMAC-SHA256(device_fingerprint, "ΣVAULT_KEY_SALT"),
    time_cost = 3,
    memory_cost = 65536 KB,
    parallelism = 4,
    hash_length = 64 bytes
)
```

### Device Fingerprint Components

```python
device_fingerprint = SHA256(
    cpu_model +           # via cpuinfo
    disk_serial +         # via os.stat
    mac_address +         # via socket.getmac()
    tpm_public_key +      # via TPM 2.0 (Linux/Windows)
    motherboard_uuid      # via dmidecode (Linux) or WMI (Windows)
)
```

### Three Key Modes

#### Mode 1: HYBRID (Recommended) ✅

**Formula:** User passphrase + Device fingerprint

```python
master_key = Argon2id(
    passphrase = SHA256(user_passphrase),
    salt = HMAC-SHA256(device_fingerprint, "ΣVAULT")
)
```

**Security Properties:**

- Requires BOTH device AND passphrase to decrypt
- Device theft requires passphrase knowledge
- Passphrase compromise requires physical device
- **Threat Model:** Protects against both remote and physical attacks

**Use Case:**

- Default mode for single-device users
- Maximum security for local vaults
- Not portable between devices

#### Mode 2: DEVICE_ONLY 🔒

**Formula:** Device fingerprint only (no passphrase required)

```python
master_key = Argon2id(
    passphrase = SHA256(device_fingerprint),
    salt = "ΣVAULT_DEVICE_ONLY"
)
```

**Security Properties:**

- No user passphrase needed
- Unlock device = automatic vault access
- Device hardware is the only key
- **Threat Model:** Protects against remote/online attacks only

**Use Case:**

- Trusted desktop environments
- Enterprise managed devices
- High-security workstations with biometric unlock
- Trade-off: Physical theft defeats security

#### Mode 3: USER_ONLY 🔓

**Formula:** User passphrase only (portable across devices)

```python
master_key = Argon2id(
    passphrase = SHA256(user_passphrase),
    salt = "ΣVAULT_USER_ONLY"
)
```

**Security Properties:**

- User passphrase is sole security factor
- Works on any device (fully portable)
- Device compromise doesn't compromise vault
- **Threat Model:** Vulnerable to device compromise

**Use Case:**

- Mobile/portable vaults
- Sync across multiple devices
- Remote access scenarios
- Trade-off: Passphrase is single point of failure

---

## Rationale

### 1. Why Hybrid Rather Than Single Factor?

**Single Factor Approaches:**

❌ **Device-Only:**

- Physical theft = vault compromised
- Requires TPM/secure enclave (not universal)
- No portability

❌ **Passphrase-Only:**

- Weak passphrases feasible (90% of users choose weak passwords)
- Dictionary attack vulnerability
- No hardware protection

✅ **Hybrid:**

- Requires BOTH factors (security through multiplication)
- Device provides 2^256 entropy (hardware UUID)
- Passphrase provides 2^64 typical entropy (weak user choice)
- Combined: 2^320 effective security space

**Security Advantage:**
$$\text{Hybrid Security} = \log_2(\text{Device Entropy} \times \text{Passphrase Entropy})$$
$$= 256 + 64 = 320 \text{ bits effective}$$

vs. Passphrase-only: $\sim 40-50$ bits (typical user)

### 2. Why Argon2id and Not PBKDF2/bcrypt?

| Algorithm    | Memory    | Time              | Parallelism   | GPU Resistance   |
| ------------ | --------- | ----------------- | ------------- | ---------------- |
| **PBKDF2**   | 0 KB      | 10,000 iterations | No            | ❌ Vulnerable    |
| **bcrypt**   | ~4 KB     | Configurable      | No            | ⚠️ Vulnerable    |
| **scrypt**   | 16 MB     | Configurable      | Limited       | ✅ Good          |
| **Argon2id** | **64 MB** | **3 iterations**  | **4 threads** | **✅ Excellent** |

**Argon2id Advantages:**

- **Memory-hard:** Requires 64MB RAM (expensive to parallelize)
- **GPU-resistant:** Parallel memory access thwarts GPU/ASIC attacks
- **OWASP approved:** Recommended for password hashing (2023)
- **Time-memory trade-off:** Tunable (3 iterations, 65536 KB baseline)

### 3. Device Fingerprint Components

**Why these five components?**

1. **CPU Model** - Relatively permanent, model-specific
2. **Disk Serial** - Unique per storage device
3. **MAC Address** - Network interface identifier
4. **TPM Public Key** - Tamper-proof module (if available)
5. **Motherboard UUID** - Hardware identifier

**Fingerprint Properties:**

- Combined entropy: ~256 bits
- Stable across OS reinstalls (hardware unchanged)
- Unique per physical device (astronomically unlikely collision)
- OS-agnostic: Available on Linux, Windows, macOS

**Non-Components (intentionally excluded):**

- ❌ Hostname (user-changeable)
- ❌ IP address (network-dependent)
- ❌ OS version (upgradeable)
- ❌ Timezone (user-configurable)

### 4. Argon2id Parameters (Why These Values?)

```python
time_cost = 3           # 3 passes over memory
memory_cost = 65536     # 64 MB (half typical RAM on IoT)
parallelism = 4         # 4-way parallelism (quad-core baseline)
hash_length = 64        # 512 bits (matches master key)
```

**Rationale:**

| Parameter   | Value    | Reason                                                       |
| ----------- | -------- | ------------------------------------------------------------ |
| time_cost   | 3        | Typical device: ~50ms per derivation (acceptable for unlock) |
| memory_cost | 65536 KB | 64MB memory requirement prevents parallelization             |
| parallelism | 4        | Quad-core common; 4 threads = 25% CPU utilization            |
| hash_length | 64       | 512-bit key matches dimensional mixing requirement           |

**Performance Target:** Key derivation should take **50-100ms** on typical device

- Desktop: 50ms (overkill for login speed)
- Mobile: 100ms (noticeable but acceptable)
- Prevents brute force: 10 guesses/second max practical

### 5. SHA256 Passphrase Pre-Processing

**Why hash the passphrase before Argon2id?**

```
passphrase → SHA256 → Argon2id(hash, salt) → master_key
```

**Advantages:**

- Normalizes passphrase to fixed 256-bit input
- Enables rainbow table generation (defense: high memory cost)
- Separates concerns: hashing vs. key derivation
- Enables passphrase entropy analysis

**Alternative (Rejected): Direct Argon2id**

```
passphrase → Argon2id(plaintext, salt) → master_key
```

- Vulnerable to length-extension attacks
- No normalization for character encoding
- Less portable across platforms

---

## Consequences

### Positive Consequences ✅

1. **Multi-Factor Security**

   - Passphrase + Device = 320 bits effective security
   - Physical theft doesn't compromise vault
   - Remote attacks need device access too

2. **Resistant to Known Attacks**

   - GPU-resistant (Argon2id memory-hard)
   - Offline dictionary attack impractical (64MB memory per attempt)
   - Side-channel resistant (constant-time operations possible)
   - Timing attack resistant (configurable iteration cost)

3. **Operational Flexibility**

   - Three modes support different threat models
   - USER_ONLY enables portability
   - DEVICE_ONLY enables seamless integration
   - HYBRID provides maximum security

4. **Device Fingerprint Stability**

   - Survives OS reinstalls (hardware-based)
   - Survives firmware updates (not OS-dependent)
   - Doesn't break on software updates
   - Portable identity across device lifetime

5. **Graceful Degradation**
   - Device fingerprint partially unavailable? Use DEVICE_ONLY (reduced entropy)
   - No TPM? Use alternatives (CPU serial, disk serial)
   - Weak passphrase? HYBRID mode provides device backup
   - Single device lost? USER_ONLY mode enables recovery on new device

### Negative Consequences / Trade-offs ⚠️

1. **Reduced Portability in HYBRID Mode**

   - Vault bound to specific device
   - Cannot access on different machine without mode change
   - Device failure requires key recovery procedure
   - **Mitigation:** USER_ONLY mode for portable vaults, documented recovery procedures

2. **Device Fingerprint Instability Risks**

   - Motherboard replacement breaks HYBRID mode
   - Disk replacement breaks HYBRID mode
   - Virtualization environments may have dynamic UUIDs
   - **Mitigation:** Graceful degradation, recovery key backup, whitelist-based fallback

3. **Passphrase Complexity Trade-off**

   - Weak passphrases still possible (user education required)
   - DEVICE_ONLY encourages no passphrase (convenience vs. security)
   - Recovery procedures must be documented
   - **Mitigation:** Minimum passphrase strength enforcement, security guidelines

4. **TPM Dependency (Optional)**

   - Not all systems have TPM
   - TPM firmware bugs could impact security
   - Windows TPM 2.0 has vulnerabilities (mitigated in patches)
   - **Mitigation:** TPM used only as additional component, not sole dependency

5. **Implementation Complexity**
   - Multiple modes require careful testing
   - Key rotation between modes is complex
   - Device fingerprint extraction OS-specific
   - **Mitigation:** Comprehensive test suite (Phase 1), security audit (Phase 2)

---

## Alternatives Considered

### Alternative 1: Single Passphrase (User-Only)

**Approach:** Only user passphrase, no device component

**Advantages:**

- ✅ Fully portable across devices
- ✅ Simple implementation
- ✅ Standard approach (similar to password managers)

**Disadvantages:**

- ❌ Passphrase only security factor (~40-50 bits typical)
- ❌ Vulnerable to dictionary attacks (despite Argon2id)
- ❌ No protection against device compromise
- ❌ Weak passphrases common (users choose predictable patterns)

**Example Attack:** Offline dictionary attack with 10^6 common passphrases

- Time: 10^6 × 50ms = 13.8 hours (single GPU)
- Memory: 64MB (prohibitive for GPU)
- Verdict: Impractical but theoretically possible

**Decision:** Rejected as default - insufficiently secure

### Alternative 2: Single Device Fingerprint

**Approach:** Only device identification, no passphrase

**Advantages:**

- ✅ Perfect security for authenticated device
- ✅ Seamless user experience (no passphrase needed)
- ✅ Fast key derivation

**Disadvantages:**

- ❌ Physical theft = complete compromise
- ❌ Device fingerprint can be captured (TPM not impenetrable)
- ❌ No portability between devices
- ❌ No recovery if device lost/stolen

**Decision:** Offered as MODE option (DEVICE_ONLY) but not default

### Alternative 3: Three-Factor (Passphrase + Device + Biometric)

**Approach:** User passphrase + Device fingerprint + Biometric (fingerprint/face)

**Advantages:**

- ✅ Three independent factors
- ✅ Biometric prevents unauthorized use of device
- ✅ Modern device support (all phones have biometric)

**Disadvantages:**

- ❌ Biometric not cryptographic (spoofable)
- ❌ Degrades security model (bio ≠ crypto)
- ❌ Platform-dependent (different across OS)
- ❌ Biometric failures (false rejection) interrupt access

**Decision:** Rejected for core protocol; can be added as device-unlock layer

### Alternative 4: Key Encryption Key (KEK) Escrow

**Approach:** Backup key encryption key stored with trusted third party

**Advantages:**

- ✅ Recovery if device lost (third party can help)
- ✅ Device fingerprint change doesn't break access
- ✅ Risk mitigation for key loss

**Disadvantages:**

- ❌ Introduces new attack surface (escrow server)
- ❌ Trust requirement (escrow must be honest)
- ❌ Adds complexity (network dependency)
- ❌ Privacy concern (escrow sees key material)

**Decision:** Offered as optional feature (Phase 4) not core protocol

### Alternative 5: Quantum-Safe Key Derivation

**Approach:** Use post-quantum key derivation (lattice-based)

**Advantages:**

- ✅ Quantum computer resistance
- ✅ Future-proof

**Disadvantages:**

- ❌ Lattice-based KDF not standardized
- ❌ Performance impact unknown
- ❌ Adds complexity without proven benefit

**Decision:** Deferred to Phase 6 (post-quantum transition)

---

## Security Assumptions

### Assumption 1: Device Fingerprint Uniqueness

**Statement:** Device fingerprint has sufficient entropy (≥256 bits) to resist collision attacks

**Validity:** ✅ Strong (combined components highly unique)  
**Risk:** ⚠️ Low (but check TPM availability)  
**Validation:** Phase 1 (empirical testing across devices)

### Assumption 2: Argon2id Remains Cryptographically Sound

**Statement:** Argon2id will not be broken by quantum computers or future attacks

**Validity:** ⚠️ Medium (depends on ongoing cryptanalysis)  
**Risk:** ⚠️ High (any KDF can be theoretically broken)  
**Validation:** Phase 6 (hybrid classical + post-quantum)

### Assumption 3: Device Fingerprint Stability

**Statement:** Device fingerprint doesn't change across OS updates, firmware updates, etc.

**Validity:** ✅ Strong (hardware-based, stable)  
**Risk:** ⚠️ Medium (hardware can be replaced)  
**Validation:** Phase 1 (test across device updates), documentation

### Assumption 4: Passphrase Entropy

**Statement:** User will choose passphrase with ≥64 bits entropy

**Validity:** ⚠️ Weak (most users choose weak passwords)  
**Risk:** ⚠️ High (contradicts user behavior)  
**Validation:** Phase 1 (strength requirements, education)

---

## Implementation Status

### Core Implementation ✅

| Component                    | File                 | Lines | Status         |
| ---------------------------- | -------------------- | ----- | -------------- |
| HybridKeyDerivation class    | crypto/hybrid_key.py | 150   | ✅ Implemented |
| UserKeyDerivation class      | crypto/hybrid_key.py | 120   | ✅ Implemented |
| DeviceFingerprint extraction | crypto/hybrid_key.py | 80    | ✅ Implemented |
| Argon2id integration         | crypto/hybrid_key.py | 60    | ✅ Implemented |
| KeyMode enum                 | crypto/hybrid_key.py | 3     | ✅ Implemented |

### Testing ✅

| Test                     | File               | Lines | Status     |
| ------------------------ | ------------------ | ----- | ---------- |
| Hybrid key derivation    | test_sigmavault.py | 35    | ✅ Passing |
| User key derivation      | test_sigmavault.py | 25    | ✅ Passing |
| Device fingerprint       | test_sigmavault.py | 20    | ✅ Passing |
| Key mode switching       | test_sigmavault.py | 18    | ✅ Passing |
| Deterministic derivation | test_sigmavault.py | 15    | ✅ Passing |

---

## Success Criteria for ADR-002

- [ ] Threat model analysis approved by @CIPHER
- [ ] Cryptographic soundness validated by @AXIOM
- [ ] Device fingerprint testing completed by @APEX
- [ ] Passphrase strength requirements defined
- [ ] Recovery procedures documented
- [ ] Approved by @ARCHITECT

---

## Key Rotation Strategy

**Planned for Phase 2:**

1. **Passphrase Rotation**

   - User changes passphrase → re-derive with new passphrase
   - All dimensional coordinates must be recalculated
   - Background re-scattering operation

2. **Device Rotation**

   - User moves vault to new device
   - Switch to USER_ONLY mode temporarily
   - Restore HYBRID mode on new device

3. **Emergency Key Change**
   - If compromise suspected
   - Decrypt all files, re-scatter with new key
   - Estimated time: 1TB < 1 hour

---

## Related ADRs

- [ADR-001: Dimensional Addressing Strategy](./ADR-001-dimensional-addressing.md)
- [ADR-003: FUSE Filesystem Layer](./ADR-003-fuse-filesystem.md)

---

## References

1. Biryukov, A., Dinu, D., Khovratovich, D. (2016). "Argon2: New Generation of Memory-Hard Password Hashing"
2. NIST SP 800-63B: Digital Identity Guidelines
3. OWASP Password Storage Cheat Sheet (2023)
4. Shannon, C. E. (1949). "Communication Theory of Secrecy Systems"
5. Boneh, D., Shoup, V. (2020). "A Graduate Course in Applied Cryptography" (Chapter 8)

---

**Version:** 1.0.0  
**Last Updated:** December 11, 2025  
**Status:** PROPOSED (awaiting team review)
