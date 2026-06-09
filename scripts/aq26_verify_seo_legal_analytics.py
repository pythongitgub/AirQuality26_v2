#!/usr/bin/env python3
from __future__ import annotations
import argparse, os, re
from pathlib import Path

def read(p: Path) -> str:
    return p.read_text(encoding='utf-8', errors='ignore')

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--site-root', default='site_public')
    ap.add_argument('--require-ga', action='store_true')
    args = ap.parse_args()
    root = Path(args.site_root)
    errors=[]
    for fn in ['index.html','sitemap.xml','robots.txt','privacy.html','cookies.html','terms.html','accessibility.html','contact.html']:
        if not (root/fn).exists(): errors.append(f'Missing {fn}')
    if (root/'robots.txt').exists() and 'sitemap.xml' not in read(root/'robots.txt'):
        errors.append('robots.txt does not reference sitemap.xml')
    index = read(root/'index.html') if (root/'index.html').exists() else ''
    checks = ['googletagmanager.com/gtag/js', 'G-', 'AQ26 SEO ANALYTICS', 'AQ26 LEGAL FOOTER COOKIE', 'cookie-banner']
    for c in checks:
        if c not in index:
            errors.append(f'index.html missing {c}')
    if args.require_ga and not os.environ.get('GA_MEASUREMENT_ID','').strip():
        errors.append('GA_MEASUREMENT_ID required but missing')
    if '<link rel="canonical"' not in index:
        errors.append('index.html missing canonical link')
    if 'application/ld+json' not in index:
        errors.append('index.html missing JSON-LD')
    if errors:
        print('AQ26 SEO verification failed:')
        for e in errors: print(' - '+e)
        return 1
    print('AQ26 SEO/legal/analytics verification passed.')
    return 0
if __name__ == '__main__':
    raise SystemExit(main())
