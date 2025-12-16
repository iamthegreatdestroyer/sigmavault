#!/usr/bin/env python
"""Phase 0 Interface Contracts Verification Script"""

import os
from pathlib import Path
import re

def verify_phase0():
    project_path = Path('sigmavault')
    required_files = [
        'api/__init__.py',
        'api/interfaces.py',
        'api/types.py',
        'api/exceptions.py',
        'stubs/__init__.py',
        'stubs/mock_vault.py',
    ]

    print('=' * 80)
    print('PHASE 0 INTERFACE CONTRACTS - VERIFICATION SCAN')
    print('=' * 80)
    print()

    print('STEP 1: SCANNING FOR REQUIRED FILES')
    print('-' * 80)
    files_status = {}
    for file in required_files:
        full_path = project_path / file
        exists = full_path.exists()
        files_status[file] = exists
        status = '✓' if exists else '✗'
        print(f'{status} {file:<40}')

    all_files_exist = all(files_status.values())
    print()

    print('STEP 2: VERIFYING PROTOCOL DEFINITIONS')
    print('-' * 80)
    protocols = []
    if files_status.get('api/interfaces.py'):
        with open(project_path / 'api/interfaces.py', 'r') as f:
            interfaces_content = f.read()
        protocols = re.findall(r'class\s+(\w+)\(Protocol\):', interfaces_content)
        print(f'Protocols found: {len(protocols)}')
        for protocol in protocols:
            print(f'  - {protocol}')
    else:
        print('✗ api/interfaces.py not found')

    print()
    print('STEP 3: VERIFYING TYPE DEFINITIONS')
    print('-' * 80)
    enums = []
    dataclasses = []
    if files_status.get('api/types.py'):
        with open(project_path / 'api/types.py', 'r') as f:
            types_content = f.read()
        enums = re.findall(r'class\s+(\w+)\(Enum\):', types_content)
        dataclasses = re.findall(r'@dataclass.*?\nclass\s+(\w+)', types_content, re.DOTALL)
        print(f'Enum classes: {len(enums)}')
        for enum in enums:
            print(f'  - {enum}')
        print()
        print(f'Dataclass definitions: {len(dataclasses)}')
        for dc in dataclasses:
            print(f'  - {dc}')
    else:
        print('✗ api/types.py not found')

    print()
    print('STEP 4: VERIFYING EXPORTS')
    print('-' * 80)
    all_exports = []
    if files_status.get('api/__init__.py'):
        with open(project_path / 'api/__init__.py', 'r') as f:
            init_content = f.read()
        all_match = re.search(r'__all__\s*=\s*\[(.*?)\]', init_content, re.DOTALL)
        if all_match:
            all_exports = re.findall(r'"(\w+)"', all_match.group(1))
            print(f'Exports in __all__: {len(all_exports)}')
            for i, export in enumerate(all_exports, 1):
                print(f'  {i:2d}. {export}')
        else:
            print('✗ __all__ not found in api/__init__.py')
    else:
        print('✗ api/__init__.py not found')

    print()
    print('STEP 5: TESTING MOCK IMPORTS')
    print('-' * 80)
    import_test_pass = False
    try:
        from sigmavault.api import SecureStorage, VaultManager, KeyBindingMode
        from sigmavault.stubs import MockSecureStorage, MockVaultManager
        print('✓ Import from sigmavault.api: SUCCESS')
        print('✓ Import from sigmavault.stubs: SUCCESS')
        
        vault = MockSecureStorage('/test/vault')
        manager = MockVaultManager()
        print('✓ MockSecureStorage instantiation: SUCCESS')
        print('✓ MockVaultManager instantiation: SUCCESS')
        
        result = vault.store('test/key', b'test_data')
        if result.success:
            print('✓ Store operation: SUCCESS')
            import_test_pass = True
        else:
            print('✗ Store operation: FAILED')
    except Exception as e:
        print(f'✗ Import/operation test FAILED: {str(e)[:50]}')

    print()
    print('=' * 80)
    print('VERIFICATION SUMMARY')
    print('=' * 80)
    print()

    issues = []
    if not all_files_exist:
        missing = [f for f, exists in files_status.items() if not exists]
        issues.append(f'Missing files: {", ".join(missing)}')

    if len(protocols) != 4:
        issues.append(f'Expected 4 protocols, found {len(protocols)}')

    if len(enums) != 5:
        issues.append(f'Expected 5 enum classes, found {len(enums)}')

    if len(dataclasses) == 0:
        issues.append('No dataclass definitions found')

    if len(all_exports) == 0:
        issues.append('No exports in __all__')

    if not import_test_pass:
        issues.append('Mock import test failed')

    overall_status = 'COMPLETE' if not issues and all_files_exist and import_test_pass else 'PARTIAL' if all_files_exist else 'MISSING'

    print(f'PROJECT: SIGMAVAULT')
    print(f'STATUS: {overall_status}')
    print()
    print('FILES:')
    for file, exists in files_status.items():
        status = '✓' if exists else '✗'
        print(f'  {status} {file}')

    print()
    print(f'PROTOCOLS DEFINED: {len(protocols)}')
    for protocol in protocols:
        print(f'  - {protocol}')

    print()
    print(f'TYPES DEFINED: {len(enums)} enums + {len(dataclasses)} dataclasses = {len(enums) + len(dataclasses)} total')

    print()
    print(f'EXPORTS IN __all__: {len(all_exports)}')

    print()
    print(f'MOCK IMPORT TEST: {"PASS" if import_test_pass else "FAIL"}')

    if issues:
        print()
        print('ISSUES/MISSING:')
        for issue in issues:
            print(f'  - {issue}')
    else:
        print()
        print('✓ ALL CHECKS PASSED - PHASE 0 COMPLETE')

    print()
    print('=' * 80)

if __name__ == '__main__':
    verify_phase0()
