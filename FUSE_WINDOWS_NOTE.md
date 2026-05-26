# FUSE on Windows — Phase 6 Note

## Status

The ΣVAULT FUSE filesystem integration (Phase 3) requires a Linux FUSE driver.
On **Windows 11 (native)**, the `fusepy` / `libfuse` path is not available.

## What Works on Windows

All Phase 6 quantum-safe crypto code paths work natively on Windows:

- Kyber-1024 key generation, encapsulation, decapsulation
- Dilithium-3 signing and verification
- Hybrid KDF (Argon2id + Kyber + HKDF)
- AES-256-GCM encryption/decryption
- All 390 non-FUSE tests pass (94.9% pass rate)

## Running FUSE on Windows

Use **WSL2** (Windows Subsystem for Linux) or a Linux VM:

```bash
# In WSL2 / Linux
pip install -e .
python cli.py mount --quantum-safe /mnt/test-sigmavault
echo "test data" > /mnt/test-sigmavault/testfile.txt
cat /mnt/test-sigmavault/testfile.txt
python cli.py unmount /mnt/test-sigmavault
```

## CI Recommendation

Run FUSE integration tests in a Linux CI runner (GitHub Actions `ubuntu-latest`).
The quantum-safe crypto unit tests run on all platforms.
