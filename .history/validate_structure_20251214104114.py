#!/usr/bin/env python3
"""
Validation Script for Project Restructure
Verifies that all critical files are in correct locations
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent.absolute()

# Configuration
REQUIRED_FILES = {
    "Root Level": [
        "pyproject.toml",
        "README.md",
        "LICENSE",
        "SECURITY.md",
        "CONTRIBUTING.md",
        "CHANGELOG.md",
        "Dockerfile",
        "docker-compose.yml",
        ".gitignore",
        ".dockerignore",
        "cli.py",
    ],
    "Directories": [
        ".github",
        "sigmavault",
        "tests",
        "scripts",
        "benchmarks",
        "docs",
    ],
    ".github Contents": [
        ".github/workflows",
        ".github/ADRs",
        ".github/agents",
        ".github/ISSUE_TEMPLATE",
    ],
    "Python Package": [
        "sigmavault/__init__.py",
        "sigmavault/core",
        "sigmavault/crypto",
        "sigmavault/drivers",
        "sigmavault/filesystem",
        "sigmavault/ml",
    ],
}

SHOULD_NOT_EXIST = [
    "sigmavault/pyproject.toml",
    "sigmavault/.github",
    "sigmavault/tests",
    "sigmavault/cli.py",
    "sigmavault/README.md",
]

def check_file(path, name):
    """Check if file exists"""
    full_path = ROOT / path
    exists = full_path.exists()
    status = "✅" if exists else "❌"
    print(f"{status} {name:<50} ({path})")
    return exists

def check_dir(path, name):
    """Check if directory exists"""
    full_path = ROOT / path
    exists = full_path.is_dir()
    status = "✅" if exists else "❌"
    print(f"{status} {name:<50} ({path})")
    return exists

def validate_structure():
    """Run validation"""
    print("=" * 80)
    print("PROJECT RESTRUCTURE VALIDATION")
    print("=" * 80)
    
    all_good = True
    
    # Check root level files
    print("\n📄 ROOT LEVEL FILES:")
    print("-" * 80)
    for file in REQUIRED_FILES["Root Level"]:
        if not check_file(file, file):
            all_good = False
    
    # Check directories
    print("\n📁 REQUIRED DIRECTORIES:")
    print("-" * 80)
    for dir_name in REQUIRED_FILES["Directories"]:
        if not check_dir(dir_name, dir_name):
            all_good = False
    
    # Check .github contents
    print("\n🐙 GITHUB DIRECTORY CONTENTS:")
    print("-" * 80)
    for path in REQUIRED_FILES[".github Contents"]:
        if not check_dir(path, path.split("/")[1]):
            all_good = False
    
    # Check Python package
    print("\n🐍 PYTHON PACKAGE:")
    print("-" * 80)
    for file in REQUIRED_FILES["Python Package"]:
        if not check_file(file, file):
            all_good = False
    
    # Check for files that SHOULD NOT exist
    print("\n⚠️  CLEANUP CHECK (Should NOT exist):")
    print("-" * 80)
    cleanup_ok = True
    for path in SHOULD_NOT_EXIST:
        full_path = ROOT / path
        exists = full_path.exists()
        if exists:
            print(f"⚠️  {path:<50} (SHOULD BE DELETED)")
            cleanup_ok = False
        else:
            print(f"✅ {path:<50} (correctly removed)")
    
    # Summary
    print("\n" + "=" * 80)
    if all_good and cleanup_ok:
        print("✅ PROJECT STRUCTURE VALIDATION: PASSED")
        print("=" * 80)
        return 0
    else:
        print("❌ PROJECT STRUCTURE VALIDATION: FAILED")
        print("=" * 80)
        if not cleanup_ok:
            print("\n⚠️  ACTION REQUIRED:")
            print("   Delete the nested sigmavault/ directory:")
            print("   rm -r sigmavault/sigmavault")
        return 1

def test_imports():
    """Test that imports work correctly"""
    print("\n" + "=" * 80)
    print("TESTING IMPORTS")
    print("=" * 80)
    
    try:
        import sigmavault
        print(f"✅ import sigmavault: OK (v{sigmavault.__version__})")
    except ImportError as e:
        print(f"❌ import sigmavault: FAILED - {e}")
        return False
    
    try:
        from sigmavault.core import DimensionalScatterEngine
        print(f"✅ from sigmavault.core import ...: OK")
    except ImportError as e:
        print(f"❌ from sigmavault.core import ...: FAILED - {e}")
        return False
    
    try:
        from sigmavault.crypto import HybridKeyDerivation
        print(f"✅ from sigmavault.crypto import ...: OK")
    except ImportError as e:
        print(f"❌ from sigmavault.crypto import ...: FAILED - {e}")
        return False
    
    return True

if __name__ == "__main__":
    result = validate_structure()
    
    print("\n🧪 Running import tests...")
    if test_imports():
        print("\n✅ ALL IMPORTS SUCCESSFUL")
    else:
        print("\n⚠️  SOME IMPORTS FAILED")
        result = 1
    
    sys.exit(result)
