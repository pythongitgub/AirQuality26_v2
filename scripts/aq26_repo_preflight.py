from pathlib import Path
import sys

root = Path.cwd()
required_any = [
    [Path('config/aq26_site_config.json'), Path('configs/aq26_site_config.json')],
]
required = [
    Path('scripts/aq26_build_overhauled_site.py'),
    Path('scripts/aq26_site_quality_gate.py'),
    Path('scripts/aq26_deploy_hostinger_dual.py'),
    Path('requirements.txt'),
]
missing = []
for group in required_any:
    if not any((root / p).exists() for p in group):
        missing.append(' or '.join(str(p) for p in group))
for p in required:
    if not (root / p).exists():
        missing.append(str(p))

if missing:
    print('AQ26 preflight failed. Missing required paths:')
    for item in missing:
        print(f' - {item}')
    print('\nCurrent repository root listing:')
    for p in sorted(root.iterdir()):
        print(f' - {p.name}/' if p.is_dir() else f' - {p.name}')
    sys.exit(1)

# Normalise config folder spelling for the existing scripts.
config = root / 'config' / 'aq26_site_config.json'
configs = root / 'configs' / 'aq26_site_config.json'
if not config.exists() and configs.exists():
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(configs.read_text(encoding='utf-8'), encoding='utf-8')
    print('Normalised config path: copied configs/aq26_site_config.json to config/aq26_site_config.json')
else:
    print('Config path OK.')
print('AQ26 preflight passed.')
