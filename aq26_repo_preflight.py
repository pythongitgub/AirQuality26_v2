#!/usr/bin/env python3
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
required = [
    'config/aq26_site_config.json',
    'scripts/aq26_build_overhauled_site.py',
    'scripts/aq26_site_quality_gate.py',
    'scripts/aq26_deploy_hostinger_dual.py',
    'requirements.txt',
]
missing = [p for p in required if not (ROOT / p).exists()]
if missing:
    print('AQ26 repository preflight failed. Missing files:')
    for p in missing:
        print(f' - {p}')
    print('\nUpload the full AQ26 overhaul pack at the repository root, not inside another folder.')
    sys.exit(1)
print('AQ26 repository preflight passed.')
for p in required:
    print(f'OK: {p}')
