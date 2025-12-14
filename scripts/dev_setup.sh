#!/bin/bash
# ΣVAULT Development Environment Setup
# Run this to set up your local development environment

set -e

echo "=========================================="
echo "ΣVAULT Development Setup"
echo "=========================================="
echo ""

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2 | cut -d'.' -f1,2)
REQUIRED_VERSION="3.9"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    echo "Error: Python 3.9 or higher is required (found $PYTHON_VERSION)"
    exit 1
fi
echo "✓ Python version: $PYTHON_VERSION"

# Check for FUSE
echo ""
echo "Checking FUSE installation..."
if [ "$(uname)" == "Darwin" ]; then
    # macOS
    if [ -d "/Library/Frameworks/macFUSE.framework" ]; then
        echo "✓ macFUSE detected"
    else
        echo "⚠ macFUSE not found. Install from: https://osxfuse.github.io/"
        echo "  (Required for filesystem mounting, not for core functionality)"
    fi
elif [ "$(uname)" == "Linux" ]; then
    # Linux
    if command -v fusermount3 &> /dev/null || command -v fusermount &> /dev/null; then
        echo "✓ FUSE detected"
    else
        echo "⚠ FUSE not found. Install with: sudo apt install fuse3"
        echo "  (Required for filesystem mounting, not for core functionality)"
    fi
fi

# Create virtual environment if it doesn't exist
echo ""
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi
echo "✓ Virtual environment ready"

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip --quiet

# Install dependencies
echo "Installing dependencies..."
pip install numpy --quiet
pip install pytest pytest-cov --quiet

# Try to install optional dependencies
echo "Installing optional dependencies..."
pip install fusepy --quiet 2>/dev/null || echo "  fusepy not installed (FUSE not available)"
pip install argon2-cffi --quiet 2>/dev/null || echo "  argon2-cffi not installed (will use PBKDF2 fallback)"
pip install psutil --quiet 2>/dev/null || echo "  psutil not installed (limited device fingerprinting)"

# Install package in development mode
echo "Installing ΣVAULT in development mode..."
pip install -e . --quiet

echo "✓ Dependencies installed"

# Run tests
echo ""
echo "Running tests..."
python -m pytest tests/ -v --tb=short

# Run demo
echo ""
echo "Running dimensional scattering demo..."
python tests/test_sigmavault.py --demo

echo ""
echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo ""
echo "To activate the environment in the future:"
echo "  source venv/bin/activate"
echo ""
echo "To run tests:"
echo "  python -m pytest tests/ -v"
echo ""
echo "To run the demo:"
echo "  python -m sigmavault.cli demo"
echo "  # or"
echo "  python tests/test_sigmavault.py --demo"
echo ""
echo "To create a vault:"
echo "  sigmavault create /path/to/storage"
echo ""
