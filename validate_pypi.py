#!/usr/bin/env python3
"""PyPI metadata validation for sigmavault."""

import toml
import re

with open('pyproject.toml', 'r') as f:
    config = toml.load(f)

project = config.get('project', {})
build = config.get('build-system', {})

print('PYPI METADATA AUDIT FOR SIGMAVAULT')
print('=' * 80)
print()

# 1. REQUIRED FIELDS
print('1. REQUIRED FIELDS:')
print('-' * 80)
required = {
    'name': project.get('name'),
    'version': project.get('version'),
    'description': project.get('description'),
    'readme': project.get('readme'),
    'requires-python': project.get('requires-python'),
    'license': project.get('license'),
    'authors': project.get('authors'),
}

for field, value in required.items():
    status = '✓' if value else '✗ MISSING'
    display = str(value)[:60] + '...' if value and len(str(value)) > 60 else value
    print(f'  {status} {field:20s}: {display}')

# 2. PEP 440 VERSION CHECK
version = project.get('version', '')
pep440_pattern = r'^(\d+!)?(\d+)(\.\d+)*(a|b|rc)?(\d+)?$'
is_pep440 = bool(re.match(pep440_pattern, version))
print()
print('2. VERSION COMPLIANCE (PEP 440):')
print('-' * 80)
print(f'  {"✓" if is_pep440 else "✗"} Version: {version}')
print(f'     Status: {"Valid PEP 440" if is_pep440 else "Invalid format"}')

# 3. OPTIONAL RECOMMENDED FIELDS
print()
print('3. OPTIONAL BUT RECOMMENDED FIELDS:')
print('-' * 80)
optional_rec = {
    'maintainers': project.get('maintainers'),
    'keywords': project.get('keywords'),
    'classifiers': project.get('classifiers'),
    'urls': project.get('urls'),
}

for field, value in optional_rec.items():
    if isinstance(value, list):
        print(f'  ✓ {field:20s}: {len(value)} items')
    elif isinstance(value, dict):
        print(f'  ✓ {field:20s}: {len(value)} entries')
    elif value:
        print(f'  ✓ {field:20s}: configured')
    else:
        print(f'  ⚠ {field:20s}: NOT SET (optional)')

# 4. DEPENDENCIES
print()
print('4. DEPENDENCIES:')
print('-' * 80)
deps = project.get('dependencies', [])
opt_deps = project.get('optional-dependencies', {})
print(f'  ✓ Core dependencies: {len(deps)} package(s)')
for dep in deps:
    print(f'      • {dep}')

if opt_deps:
    print(f'  ✓ Optional dependency groups: {len(opt_deps)}')
    for group, packages in opt_deps.items():
        print(f'      • {group}: {len(packages)} package(s)')
        for pkg in packages:
            print(f'          - {pkg}')

# 5. ENTRY POINTS & SCRIPTS
print()
print('5. ENTRY POINTS & CONSOLE SCRIPTS:')
print('-' * 80)
scripts = project.get('scripts', {})
if scripts:
    for name, target in scripts.items():
        print(f'  ✓ Command: {name}')
        print(f'      → {target}')
else:
    print(f'  ⚠ No console scripts defined')

# 6. CLASSIFIERS
print()
print('6. CLASSIFIERS SUMMARY:')
print('-' * 80)
classifiers = project.get('classifiers', [])
if classifiers:
    dev_status = [c for c in classifiers if c.startswith('Development Status')]
    py_versions = [c for c in classifiers if c.startswith('Programming Language')]
    topics = [c for c in classifiers if c.startswith('Topic')]
    os_list = [c for c in classifiers if c.startswith('Operating System')]
    
    print(f'  ✓ Total classifiers: {len(classifiers)}')
    print(f'    • Development Status: {dev_status[0] if dev_status else "NOT SET"}')
    print(f'    • Python versions: {len(py_versions)} specified')
    print(f'    • Topics: {len(topics)}')
    print(f'    • Operating Systems: {len(os_list)}')
else:
    print(f'  ⚠ No classifiers defined')

# 7. BUILD SYSTEM
print()
print('7. BUILD SYSTEM:')
print('-' * 80)
print(f'  ✓ Backend: {build.get("build-backend")}')
requires = build.get('requires', [])
for req in requires:
    print(f'      • {req}')

# 8. WINDOWS SUPPORT CHECK
print()
print('8. PLATFORM SUPPORT CHECK:')
print('-' * 80)
os_support = [c for c in classifiers if c.startswith('Operating System')]
has_windows = any('Windows' in c for c in os_support)
has_linux = any('Linux' in c for c in os_support)
has_macos = any('Mac' in c for c in os_support)

print(f'  Windows: {"✓" if has_windows else "⚠ NOT DECLARED"}')
print(f'  Linux:   {"✓" if has_linux else "⚠ NOT DECLARED"}')
print(f'  macOS:   {"✓" if has_macos else "⚠ NOT DECLARED"}')

# 9. SUMMARY & RECOMMENDATIONS
print()
print('9. RECOMMENDATIONS FOR PyPI PUBLISHING:')
print('-' * 80)

recommendations = []
if not project.get('urls'):
    recommendations.append('  ⚠ Add [project.urls] with: Homepage, Repository, Documentation, Issues')
if not has_windows:
    recommendations.append('  ⚠ Add "Operating System :: Microsoft :: Windows" classifier if applicable')
if not project.get('maintainers'):
    recommendations.append('  ℹ Consider adding maintainers field for larger projects')

if recommendations:
    for rec in recommendations:
        print(rec)
else:
    print('  ✓ Configuration looks good for PyPI publishing!')

print()
print('=' * 80)
print('READY FOR PYPI: ', end='')
print('✓ YES' if not any('✗' in r for r in recommendations) else '✓ MOSTLY (see recommendations)')
print('=' * 80)
