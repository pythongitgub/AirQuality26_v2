#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOTS = [Path('site_public'), Path('site_test')]
GA_ID = os.environ.get('GA_MEASUREMENT_ID', '').strip()
REQUIRED_PAGES = ['index.html', 'privacy.html', 'cookies.html', 'terms.html', 'accessibility.html', 'contact.html']
REQUIRED_FOOTER_LINKS = ['/privacy.html', '/cookies.html', '/terms.html', '/accessibility.html', '/contact.html', '/sitemap.xml']


def fail(msg: str) -> None:
    print(f'ERROR: {msg}', file=sys.stderr)
    raise SystemExit(1)


def check_root(root: Path) -> None:
    if not root.exists():
        print(f'Skipping missing {root}')
        return
    for rel in REQUIRED_PAGES:
        p = root / rel
        if not p.exists() or p.stat().st_size < 200:
            fail(f'{root}/{rel} missing or too small')
    sitemap = root / 'sitemap.xml'
    robots = root / 'robots.txt'
    if not sitemap.exists():
        fail(f'{root}/sitemap.xml missing')
    if not robots.exists():
        fail(f'{root}/robots.txt missing')
    robots_text = robots.read_text(encoding='utf-8', errors='ignore')
    if 'Sitemap: https://sccairquality.com/sitemap.xml' not in robots_text:
        fail(f'{root}/robots.txt does not advertise sitemap.xml')
    try:
        ET.parse(sitemap)
    except Exception as exc:
        fail(f'{root}/sitemap.xml is not valid XML: {exc}')
    index = (root / 'index.html').read_text(encoding='utf-8', errors='ignore')
    desc = re.search(r'<meta\s+name=["\']description["\']\s+content=["\']([^"\']+)', index, flags=re.I)
    if not desc or len(desc.group(1).strip()) < 140:
        fail(f'{root}/index.html missing a useful meta description')
    if '<link rel="canonical" href="https://sccairquality.com/"' not in index:
        fail(f'{root}/index.html missing canonical home URL')
    if 'aq26-cookie-banner' not in index or 'aq26-cookie-consent' not in index:
        fail(f'{root}/index.html missing cookie banner/consent script')
    for link in REQUIRED_FOOTER_LINKS:
        if link not in index:
            fail(f'{root}/index.html footer missing {link}')
    if 'application/ld+json' not in index or 'DataCatalog' not in index:
        fail(f'{root}/index.html missing JSON-LD DataCatalog')
    if GA_ID and GA_ID not in index:
        fail(f'{root}/index.html missing GA_MEASUREMENT_ID injection')
    print(f'SEO/legal/analytics gate passed for {root}')


def main() -> int:
    for root in ROOTS:
        check_root(root)
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
