# ΣVAULT Phase 6 — Migration Guide (v5 → v6)

## Overview

Phase 6 introduces quantum-safe cryptography. Existing vaults created with v5
(classical-only) remain readable. This guide explains the migration path.

---

## Vault Version Detection

Every vault header begins with a magic byte sequence:

| Version | Magic bytes (hex)       | Description               |
|---------|-------------------------|---------------------------|
| v5      | `534947 4D4156 41554C 545F56 350000` | Classical only (Argon2id) |
| v6      | `534947 4D4156 41554C 545F56 360000` | Hybrid (Argon2id + Kyber) |

The `detect_vault_version()` function in `sigmavault.crypto.hybrid_kdf` reads
the first bytes of a vault header and returns `5`, `6`, or `0` (unknown).

```python
from sigmavault.crypto.hybrid_kdf import detect_vault_version

with open("vault.bin", "rb") as f:
    header = f.read(32)

version = detect_vault_version(header)
if version == 5:
    print("v5 vault — classical KDF")
elif version == 6:
    print("v6 vault — quantum-safe KDF")
```

---

## Reading v5 Vaults

Use `derive_key_v5()` for vaults without a Kyber ciphertext in the header:

```python
from sigmavault.crypto.hybrid_kdf import derive_key_v5

# Reads the stored Argon2id salt from vault header
classical_key = derive_key_v5(password, stored_salt)
```

No v5 data is deleted or made unreadable. The v5 KDF path remains supported.

---

## Migrating a v5 Vault to v6

1. **Open the vault** using `derive_key_v5()` to obtain the classical key.
2. **Generate a new Kyber-1024 keypair** (store the secret key securely).
3. **Call `derive_key()`** with the same password and a new Kyber public key.
4. **Re-encrypt the vault data** under the new v6 key.
5. **Update the vault header** with `VAULT_MAGIC_V6`, new salt, and Kyber ciphertext.

```python
from sigmavault.crypto.kyber_key_encapsulation import (
    KyberKeyEncapsulation, KyberSecurityLevel,
)
from sigmavault.crypto.hybrid_kdf import derive_key, derive_key_v5

# Step 1 — unlock existing v5 vault
old_key = derive_key_v5(password, v5_salt)

# Step 2 — generate Kyber-1024 keypair (persist kyber_sk securely!)
kem = KyberKeyEncapsulation(KyberSecurityLevel.LEVEL5)
kyber_pk, kyber_sk = kem.generate_keypair()

# Step 3 — derive new v6 key
result = derive_key(password, kyber_pk)
new_key = result.derived_key

# Step 4/5 — re-encrypt and write new header
# (application-specific; store result.salt and result.kyber_ciphertext in header)
```

---

## Kyber Secret Key Storage

The Kyber-1024 secret key (3168 bytes) must be stored alongside the vault.
**Never store it in plaintext.** Recommended options:

- Encrypt it with the user's passphrase via a classical KDF before storage.
- Use a hardware security module (HSM) or OS keystore.
- Split it using a secret sharing scheme (Shamir's) for high-security vaults.

---

## Backward Compatibility Guarantees

- v5 vaults are never deleted or corrupted by Phase 6 code.
- `derive_key_v5()` remains available indefinitely.
- `SignatureMode.CLASSIC` (ECDSA) remains a supported option.
- New vaults default to `SignatureMode.QUANTUM` (Dilithium-3).
