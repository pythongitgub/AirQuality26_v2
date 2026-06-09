#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


def human(n: int) -> str:
    units = ['B','KB','MB','GB']
    value = float(n)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f'{value:.1f} {unit}' if unit != 'B' else f'{int(value)} B'
        value /= 1024


def main() -> int:
    p = argparse.ArgumentParser(description='Remove heavy archive/bundle files from website publish folders and write metadata stubs.')
    p.add_argument('--root', action='append', default=['site_public','site_unredacted','site_test'])
    p.add_argument('--max-mb', type=float, default=25.0)
    p.add_argument('--archive-dir', default='outputs/website_pruned_heavy_files')
    p.add_argument('--delete', action='store_true', help='Delete files instead of moving them to archive-dir.')
    args = p.parse_args()

    max_bytes = int(args.max_mb * 1024 * 1024)
    archive = Path(args.archive_dir)
    archive.mkdir(parents=True, exist_ok=True)
    pruned = []
    heavy_suffixes = {'.zip', '.7z', '.tar', '.gz', '.tgz'}

    for root_s in args.root:
        root = Path(root_s)
        if not root.exists():
            continue
        for path in list(root.rglob('*')):
            if not path.is_file():
                continue
            size = path.stat().st_size
            if path.suffix.lower() in heavy_suffixes and size > max_bytes:
                rel = path.relative_to(root)
                entry = {
                    'site_root': root_s,
                    'path': path.as_posix(),
                    'relative_path': rel.as_posix(),
                    'bytes': size,
                    'human': human(size),
                    'action': 'deleted' if args.delete else 'moved_to_outputs_archive',
                    'timestamp_utc': datetime.now(timezone.utc).isoformat(),
                    'replacement_note': 'Large evidence bundles should be published through Google Drive/shared drive or a separate short-retention Actions artifact, not inside the public website tree.',
                }
                pruned.append(entry)
                stub = path.with_suffix(path.suffix + '.metadata.json')
                stub.write_text(json.dumps(entry, indent=2), encoding='utf-8')
                if args.delete:
                    path.unlink()
                else:
                    dest = archive / root_s / rel
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    if dest.exists():
                        dest.unlink()
                    shutil.move(path.as_posix(), dest.as_posix())
    manifest = archive / 'pruned_publish_files_manifest.json'
    manifest.write_text(json.dumps({'pruned': pruned, 'count': len(pruned)}, indent=2), encoding='utf-8')
    print(json.dumps({'pruned_count': len(pruned), 'manifest': manifest.as_posix(), 'items': pruned[:20]}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
