#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

VISUAL_SUFFIXES = {'.png', '.jpg', '.jpeg', '.webp', '.gif', '.svg', '.webm', '.mp4'}


def human(n: int) -> str:
    units = ['B','KB','MB','GB']
    value = float(n)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f'{value:.1f} {unit}' if unit != 'B' else f'{int(value)} B'
        value /= 1024


def main() -> int:
    p = argparse.ArgumentParser(description='Catalogue AQ26 visual assets and flag oversized imagery/video/SVG.')
    p.add_argument('--root', action='append', default=['site_public','site_unredacted','site_test','website'])
    p.add_argument('--output', default='site_public/data/asset_catalogue.json')
    p.add_argument('--large-kb', type=int, default=512)
    args = p.parse_args()

    assets = []
    by_suffix = {}
    for root_s in args.root:
        root = Path(root_s)
        if not root.exists():
            continue
        for path in root.rglob('*'):
            if not path.is_file() or path.suffix.lower() not in VISUAL_SUFFIXES:
                continue
            size = path.stat().st_size
            suffix = path.suffix.lower()
            by_suffix.setdefault(suffix, {'count': 0, 'bytes': 0})
            by_suffix[suffix]['count'] += 1
            by_suffix[suffix]['bytes'] += size
            assets.append({
                'path': path.as_posix(),
                'bytes': size,
                'human': human(size),
                'suffix': suffix,
                'large': size > args.large_kb * 1024,
                'recommendation': (
                    'Optimise SVG/WebM or replace with a compressed WebP/MP4 poster if used above the fold.'
                    if size > args.large_kb * 1024 else 'OK'
                ),
            })
    assets.sort(key=lambda r: r['bytes'], reverse=True)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        'generated_utc': datetime.now(timezone.utc).isoformat(),
        'total_assets': len(assets),
        'total_bytes': sum(a['bytes'] for a in assets),
        'total_human': human(sum(a['bytes'] for a in assets)),
        'by_suffix': {k: {'count': v['count'], 'bytes': v['bytes'], 'human': human(v['bytes'])} for k, v in sorted(by_suffix.items())},
        'largest_assets': assets[:80],
    }
    out.write_text(json.dumps(payload, indent=2), encoding='utf-8')
    # Mirror into unredacted if present.
    unredacted = Path('site_unredacted/data/asset_catalogue.json')
    if unredacted.parent.exists():
        unredacted.parent.mkdir(parents=True, exist_ok=True)
        unredacted.write_text(json.dumps(payload, indent=2), encoding='utf-8')
    print(json.dumps({'output': out.as_posix(), 'total': payload['total_human'], 'largest': assets[:10]}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
