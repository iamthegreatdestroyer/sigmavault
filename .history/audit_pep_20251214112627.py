#!/usr/bin/env python3
"""PEP Compliance Audit Script for TASK 6"""

import os
from pathlib import Path

print('='*80)
print('PEP COMPLIANCE VERIFICATION')
print('='*80)
print()

# Check __pycache__ locations
print('TEST 6: __pycache__ Distribution Verification')
print('-' * 80)

pycache_found = []

for root, dirs, files in os.walk('.'):
    if '__pycache__' in root:
        rel_path = os.path.relpath(root, '.')
        if not rel_path.startswith('build') and not rel_path.startswith('dist'):
            pycache_found.append(rel_path)
        if '__pycache__' in dirs:
            dirs.remove('__pycache__')

if pycache_found:
    print(f'⚠ {len(pycache_found)} __pycache__ directories found (normal during development):')
    for path in pycache_found[:5]:
        print(f'  - {path}')
    if len(pycache_found) > 5:
        print(f'  ... and {len(pycache_found)-5} more')
else:
    print('✓ No __pycache__ directories in source')

# Verify tests location
print()
print('TEST 7: Project Structure Verification')
print('-' * 80)

required_dirs = {
    'sigmavault': 'Package root',
    'tests': 'Test directory (at root level)',
    'docs': 'Documentation',
    'scripts': 'Development scripts',
}

for dir_name, description in required_dirs.items():
    path = Path(dir_name)
    if path.exists() and path.is_dir():
        print(f'✓ {dir_name}/ exists - {description}')
    else:
        print(f'✗ {dir_name}/ missing - {description}')

# Verify __init__.py presence
print()
print('TEST 8: __init__.py Verification')
print('-' * 80)

packages = [
    'sigmavault',
    'sigmavault/core',
    'sigmavault/crypto',
    'sigmavault/filesystem',
    'sigmavault/ml',
    'sigmavault/drivers',
    'sigmavault/drivers/storage',
    'sigmavault/drivers/platform',
]

for pkg in packages:
    init_file = Path(pkg) / '__init__.py'
    if init_file.exists():
        with open(init_file) as f:
            content = f.read()
            has_docstring = content.strip().startswith('"""') or content.strip().startswith("'''")
            has_all = '__all__' in content
            print(f'✓ {pkg}/__init__.py exists (docstring: {has_docstring}, __all__: {has_all})')
    else:
        print(f'✗ {pkg}/__init__.py missing')

# PEP 517 verification
print()
print('TEST 9: PEP 517 Build System Interface')
print('-' * 80)

pyproject = Path('pyproject.toml')
if pyproject.exists():
    content = pyproject.read_text()
    has_build_system = '[build-system]' in content
    has_requires = 'requires =' in content
    has_backend = 'build-backend =' in content
    
    print(f'✓ pyproject.toml exists')
    print(f'  ✓ [build-system] section: {has_build_system}')
    print(f'  ✓ requires field: {has_requires}')
    print(f'  ✓ build-backend field: {has_backend}')
    
    if has_build_system and has_requires and has_backend:
        print(f'✓ PEP 517 compliant')
    else:
        print(f'✗ PEP 517 incomplete')
else:
    print('✗ pyproject.toml missing')

# PEP 518 verification
print()
print('TEST 10: PEP 518 Metadata Specification')
print('-' * 80)

if pyproject.exists():
    content = pyproject.read_text()
    required_fields = {
        'name': 'Project name',
        'version': 'Version number',
        'description': 'Description',
    }
    
    for field, desc in required_fields.items():
        if f'{field} =' in content:
            print(f'✓ {field}: {desc}')
        else:
            print(f'✗ {field}: {desc} missing')
    
    optional_fields = {
        'readme': 'README file reference',
        'requires-python': 'Python version requirement',
        'license': 'License',
        'authors': 'Author information',
        'keywords': 'Keywords',
        'classifiers': 'Classifiers',
        'dependencies': 'Dependencies',
    }
    
    print()
    print('Optional fields:')
    for field, desc in optional_fields.items():
        if f'{field} =' in content or f'{field} {{' in content:
            print(f'  ✓ {field}: {desc}')
        else:
            print(f'  ✗ {field}: {desc}')

print()
print('='*80)
