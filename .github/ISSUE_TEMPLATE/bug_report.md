---
name: Bug Report
about: Report a bug in ΣVAULT
title: '[BUG] '
labels: bug
assignees: ''
---

## Bug Description
A clear and concise description of the bug.

## Steps to Reproduce
```python
# Minimal code to reproduce the issue
from sigmavault import DimensionalScatterEngine, KeyState

# What happens vs what should happen
```

Or CLI steps:
```bash
sigmavault create /path/to/storage
sigmavault mount /mnt/test /path/to/storage
# What command failed?
```

## Expected Behavior
What you expected to happen.

## Actual Behavior
What actually happened. Include any error messages.

## Environment
- OS: [e.g., Ubuntu 22.04, macOS 14, Windows 11]
- Python version: [e.g., 3.11.5]
- ΣVAULT version: [e.g., 1.0.0]
- FUSE version: [e.g., fuse3 3.10.5]
- NumPy version: [e.g., 1.24.0]

## Security Impact
Does this bug have security implications?
- [ ] Data exposure risk
- [ ] Key material leak
- [ ] Denial of service
- [ ] None/Unknown

## Additional Context
Any other context about the problem (logs, screenshots, etc.)

**Note:** Never include actual vault passphrases or sensitive data in bug reports.

## Possible Solution
If you have ideas on how to fix this, please share.
