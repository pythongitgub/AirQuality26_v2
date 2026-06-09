#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import mimetypes
from collections import defaultdict
from pathlib import Path


def sha256(path: Path, block: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(block), b''):
            h.update(chunk)
    return h.hexdigest()


def human(n: int) -> str:
    units = ['B','KB','MB','GB','TB']
    value = float(n)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f'{value:.1f} {unit}' if unit != 'B' else f'{int(value)} B'
        value /= 1024


def classify(path: Path) -> str:
    suffix = path.suffix.lower()
    parts = {p.lower() for p in path.parts}
    if suffix in {'.zip', '.7z', '.tar', '.gz', '.tgz'}:
        return 'archives'
    if suffix in {'.png', '.jpg', '.jpeg', '.webp', '.gif', '.svg', '.webm', '.mp4'}:
        return 'visual_assets'
    if suffix in {'.json', '.geojson'}:
        return 'json_metadata'
    if suffix in {'.csv', '.tsv'}:
        return 'tables'
    if suffix in {'.pdf', '.docx', '.md', '.html', '.txt'}:
        return 'reports_pages'
    if 'outputs' in parts:
        return 'generated_outputs'
    return 'other'


def main() -> int:
    p = argparse.ArgumentParser(description='Create an AQ26 artifact/file-size audit report.')
    p.add_argument('--root', action='append', default=[], help='Root folder to scan. Repeatable.')
    p.add_argument('--output-dir', default='outputs/aq26_size_audit')
    p.add_argument('--top', type=int, default=80)
    p.add_argument('--hash-files-over-mb', type=float, default=1.0)
    args = p.parse_args()

    roots = [Path(r) for r in args.root] or [Path('outputs'), Path('site_public'), Path('site_unredacted'), Path('site_test')]
    files = []
    by_root = defaultdict(int)
    by_class = defaultdict(int)
    by_suffix = defaultdict(int)
    by_hash = defaultdict(list)

    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob('*'):
            if not path.is_file():
                continue
            try:
                size = path.stat().st_size
            except OSError:
                continue
            rel = path.as_posix()
            cat = classify(path)
            suffix = path.suffix.lower() or '[none]'
            by_root[root.as_posix()] += size
            by_class[cat] += size
            by_suffix[suffix] += size
            file_hash = ''
            if size >= args.hash_files_over_mb * 1024 * 1024:
                file_hash = sha256(path)
                by_hash[file_hash].append(rel)
            files.append({
                'path': rel,
                'bytes': size,
                'mb': round(size / 1048576, 3),
                'class': cat,
                'suffix': suffix,
                'mime': mimetypes.guess_type(path.name)[0] or '',
                'sha256': file_hash,
            })

    files.sort(key=lambda r: r['bytes'], reverse=True)
    dupes = []
    for h, paths in by_hash.items():
        if h and len(paths) > 1:
            sizes = [next(f['bytes'] for f in files if f['path'] == p) for p in paths]
            dupes.append({'sha256': h, 'copies': len(paths), 'bytes_each': sizes[0], 'duplicate_bytes': sizes[0]*(len(paths)-1), 'paths': paths})
    dupes.sort(key=lambda r: r['duplicate_bytes'], reverse=True)

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    summary = {
        'total_files': len(files),
        'total_bytes': sum(f['bytes'] for f in files),
        'total_human': human(sum(f['bytes'] for f in files)),
        'by_root': {k: {'bytes': v, 'human': human(v)} for k, v in sorted(by_root.items(), key=lambda x: x[1], reverse=True)},
        'by_class': {k: {'bytes': v, 'human': human(v)} for k, v in sorted(by_class.items(), key=lambda x: x[1], reverse=True)},
        'by_suffix': {k: {'bytes': v, 'human': human(v)} for k, v in sorted(by_suffix.items(), key=lambda x: x[1], reverse=True)[:30]},
        'top_files': files[:args.top],
        'duplicate_groups': dupes[:30],
        'duplicate_bytes_potential_saving': sum(d['duplicate_bytes'] for d in dupes),
        'duplicate_human_potential_saving': human(sum(d['duplicate_bytes'] for d in dupes)),
    }
    (out / 'artifact_size_summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    with (out / 'artifact_largest_files.csv').open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['bytes','mb','class','suffix','mime','sha256','path'])
        writer.writeheader()
        writer.writerows(files[:args.top])
    with (out / 'artifact_duplicate_groups.json').open('w', encoding='utf-8') as f:
        json.dump(dupes, f, indent=2)
    print(json.dumps({
        'output_dir': out.as_posix(),
        'total': summary['total_human'],
        'files': len(files),
        'largest': files[:10],
        'duplicate_potential_saving': summary['duplicate_human_potential_saving'],
    }, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
