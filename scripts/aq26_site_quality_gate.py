#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, re, sys
from pathlib import Path
import yaml


def read_yaml(path: Path) -> dict:
    with path.open('r', encoding='utf-8') as f:
        return yaml.safe_load(f) or {}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--config', default='configs/aq26_nextlevel_site.yml')
    args = ap.parse_args()
    cfg = read_yaml(Path(args.config))
    site = cfg.get('site', {})
    q = cfg.get('quality', {})
    public = Path(site.get('public_root', 'site_public'))
    unredacted = Path(site.get('unredacted_root', 'site_unredacted'))
    failures = []

    for rel in q.get('required_public_files', []):
        p = public / rel
        if not p.exists() or p.stat().st_size == 0:
            failures.append(f'missing_or_empty_public_file:{rel}')

    sitemap = public / 'sitemap.xml'
    if sitemap.exists() and '<urlset' not in sitemap.read_text(encoding='utf-8', errors='ignore'):
        failures.append('invalid_sitemap_xml')
    robots = public / 'robots.txt'
    if robots.exists() and 'Sitemap:' not in robots.read_text(encoding='utf-8', errors='ignore'):
        failures.append('robots_missing_sitemap')

    forbidden = q.get('forbidden_public_patterns', [])
    for p in public.rglob('*'):
        if not p.is_file() or p.stat().st_size > 2_000_000:
            continue
        text = p.read_text(encoding='utf-8', errors='ignore')
        for pat in forbidden:
            if pat and pat in text:
                failures.append(f'forbidden_public_pattern:{pat}:{p}')

    # Public site must not contain .htpasswd. Unredacted .htpasswd should be remote-generated, not committed.
    for p in list(public.rglob('.htpasswd')) + list(unredacted.rglob('.htpasswd')):
        failures.append(f'htpasswd_in_publish_tree:{p}')

    result = {'ok': not failures, 'failures': failures}
    print(json.dumps(result, indent=2))
    if failures:
        return 1
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
