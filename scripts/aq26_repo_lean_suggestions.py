#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path

KEEP_WORKFLOWS = {'weekly-production.yml', 'aq26-hostinger-ssh-preflight.yml'}
KEEP_TOP_LEVEL = {'.github','scripts','configs','site_public','site_unredacted','site_test','docs','requirements.txt','README.md','.gitignore'}
HEAVY_PATTERNS = ('.zip','.7z','.tar','.gz','.parquet','.mht')
GENERATED_DIRS = {'outputs','downloads','exports','reports','evidence','artifacts','logs','__pycache__'}

def main() -> int:
    root = Path.cwd()
    workflows = sorted(p.name for p in (root/'.github/workflows').glob('*.yml')) if (root/'.github/workflows').exists() else []
    large = []
    for p in root.rglob('*'):
        if not p.is_file():
            continue
        try:
            size = p.stat().st_size
        except OSError:
            continue
        if size > 10*1024*1024 or p.suffix.lower() in HEAVY_PATTERNS:
            large.append({'path': str(p), 'mb': round(size/1024/1024, 2)})
    top = sorted(p.name for p in root.iterdir() if p.name not in KEEP_TOP_LEVEL)
    print(json.dumps({
        'keep_workflows': sorted(KEEP_WORKFLOWS),
        'disable_workflows': [w for w in workflows if w not in KEEP_WORKFLOWS],
        'candidate_top_level_review_or_remove': top,
        'generated_dirs_safe_to_remove_from_git_if_regenerated': sorted(GENERATED_DIRS),
        'large_files_review': sorted(large, key=lambda x: -x['mb'])[:200]
    }, indent=2))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
