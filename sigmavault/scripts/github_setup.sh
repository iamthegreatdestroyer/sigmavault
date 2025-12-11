#!/bin/bash
# ΣVAULT GitHub Repository Setup Script
# Run this after creating a new repository on GitHub

set -e

# Configuration - UPDATE THESE
GITHUB_USERNAME="YOUR_USERNAME"
REPO_NAME="sigmavault"

echo "=========================================="
echo "ΣVAULT GitHub Repository Setup"
echo "=========================================="
echo ""

# Check if git is initialized
if [ ! -d ".git" ]; then
    echo "Initializing git repository..."
    git init
fi

# Configure git (if not already configured)
if [ -z "$(git config user.name)" ]; then
    echo "Please configure git:"
    echo "  git config user.name 'Your Name'"
    echo "  git config user.email 'your.email@example.com'"
    exit 1
fi

# Add all files
echo "Adding files to git..."
git add .

# Initial commit
echo "Creating initial commit..."
git commit -m "feat: initial ΣVAULT release v1.0.0

Trans-dimensional encrypted storage system featuring:

- 8-dimensional scattering manifold
- Entropic indistinguishability (signal/noise mixing)
- Self-referential topology (content determines storage)
- Temporal variance (automatic re-scattering)
- Holographic redundancy
- Hybrid key derivation (device + user)
- Transparent FUSE filesystem
- Per-file vault locks
- Comprehensive test suite"

# Create main branch
git branch -M main

# Add remote (update with your actual repo URL)
echo ""
echo "=========================================="
echo "MANUAL STEPS REQUIRED:"
echo "=========================================="
echo ""
echo "1. Create a new repository on GitHub:"
echo "   https://github.com/new"
echo "   Name: ${REPO_NAME}"
echo "   Description: Trans-dimensional encrypted storage - data scattered across N-dimensional manifold"
echo "   Visibility: Public (or Private)"
echo "   DO NOT initialize with README, license, or .gitignore"
echo ""
echo "2. After creating the repo, run these commands:"
echo ""
echo "   git remote add origin https://github.com/${GITHUB_USERNAME}/${REPO_NAME}.git"
echo "   git push -u origin main"
echo ""
echo "3. Create the first release:"
echo ""
echo "   git tag -a v1.0.0 -m 'Initial release - Trans-dimensional encrypted storage'"
echo "   git push origin v1.0.0"
echo ""
echo "4. Enable GitHub Actions:"
echo "   Go to Settings > Actions > General"
echo "   Enable 'Allow all actions and reusable workflows'"
echo ""
echo "5. (Optional) Enable security scanning:"
echo "   Go to Settings > Code security and analysis"
echo "   Enable Dependabot and secret scanning"
echo ""
echo "=========================================="
echo "Setup preparation complete!"
echo "=========================================="
