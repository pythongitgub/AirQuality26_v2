#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--max-mb', type=float, default=25)
    ap.add_argument('--write-notices', default='true')
    args = ap.parse_args()
    max_bytes = int(args.max_mb * 1024 * 1024)
    roots = [Path('site_public'), Path('site_unredacted'), Path('site_test')]
    removed = []
    for root in roots:
        if not root.exists():
            continue
        for p in root.rglob('*'):
            if not p.is_file():
                continue
            if p.name == '.htpasswd':
                removed.append({'path': str(p), 'bytes': p.stat().st_size, 'reason': 'htpasswd_never_publish_from_repo'})
                p.unlink()
                continue
            if p.stat().st_size > max_bytes:
                removed.append({'path': str(p), 'bytes': p.stat().st_size, 'reason': f'larger_than_{args.max_mb}_mb'})
                p.unlink()
    if str(args.write_notices).lower() in {'1','true','yes','y'}:
        for root in roots:
            if not root.exists():
                continue
            notice_dir = root / 'downloads'
            notice_dir.mkdir(parents=True, exist_ok=True)
            (notice_dir / 'LARGE_EVIDENCE_BUNDLE_NOTICE.txt').write_text(
                'Large AQ26 evidence bundles are retained as GitHub Actions artifacts and/or Google Drive archive files. The public website keeps lean reports, manifests, hashes and data feeds for speed and SEO.\n',
                encoding='utf-8'
            )
    print(json.dumps({'ok': True, 'removed': removed}, indent=2))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
