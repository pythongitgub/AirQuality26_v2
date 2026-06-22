#!/usr/bin/env python3
"""Fail-fast AQ26 site audit for SEO, assets, redaction, protected folders and accidental repo leaks."""
from __future__ import annotations

import argparse
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]

class Parser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags=[]
        self.title=False
        self.h1=False
    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))
        if tag == 'h1': self.h1=True
    def handle_startendtag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))
    def handle_data(self, data):
        pass
    def handle_decl(self, decl):
        pass

def attr(tags, tag, key, value=None):
    for t,a in tags:
        if t != tag: continue
        if key not in a: continue
        if value is None or a.get(key)==value or (isinstance(a.get(key), str) and value in a.get(key,'')):
            return a
    return None

def local_exists(base: Path, html_file: Path, ref: str) -> bool:
    if not ref or ref.startswith(('#','mailto:','tel:','data:','javascript:')): return True
    u=urlparse(ref)
    if u.scheme in {'http','https'}: return True
    path=u.path
    if not path: return True
    # Absolute links are site-root links. Public pages may point to /unredacted/,
    # and protected pages may point back to public legal/contact/sitemap pages.
    if path.startswith('/'):
        if path == '/unredacted/' and (ROOT/'site_unredacted'/'index.html').exists():
            return True
        if path.startswith('/unredacted/'):
            rest = path[len('/unredacted/'):].strip('/') or 'index.html'
            return (ROOT/'site_unredacted'/rest).exists()
        return (ROOT/'site_public'/path.lstrip('/')).exists()
    target=html_file.parent/path
    return target.exists()

def audit_dir(base: Path, public: bool, errors: list[str], warnings: list[str]):
    if not base.exists():
        errors.append(f'Missing folder: {base}')
        return
    bad_dirs=['git-test','.git','node_modules','__pycache__']
    for bad in bad_dirs:
        if (base/bad).exists():
            errors.append(f'Unsafe/stale directory present: {base/bad}')
    for p in base.rglob('*'):
        if p.is_file() and p.name in {'.env','.htpasswd','id_rsa','id_ed25519'}:
            errors.append(f'Sensitive file must not be deployed: {p}')
        if p.is_file() and p.suffix.lower() in {'.py','.ipynb','.yml','.yaml'} and 'git-test' in p.as_posix():
            errors.append(f'Repo/source file leaked to web root: {p}')
    for html in base.rglob('*.html'):
        if 'git-test' in html.parts: continue
        txt=html.read_text(encoding='utf-8', errors='ignore')
        if len(txt.strip()) < 1200:
            errors.append(f'{html.relative_to(base)} suspiciously small/blank')
        p=Parser(); p.feed(txt)
        if '<title>' not in txt.lower(): errors.append(f'{html.relative_to(base)} missing title')
        if 'name="description"' not in txt.lower() and "name='description'" not in txt.lower(): errors.append(f'{html.relative_to(base)} missing meta description')
        if 'rel="canonical"' not in txt.lower() and "rel='canonical'" not in txt.lower(): errors.append(f'{html.relative_to(base)} missing canonical')
        if 'property="og:title"' not in txt.lower(): errors.append(f'{html.relative_to(base)} missing Open Graph title')
        if 'twitter:card' not in txt.lower(): errors.append(f'{html.relative_to(base)} missing Twitter card')
        if 'application/ld+json' not in txt.lower(): errors.append(f'{html.relative_to(base)} missing JSON-LD')
        if '<h1' not in txt.lower(): errors.append(f'{html.relative_to(base)} missing h1')
        if public and 'googletagmanager.com/gtag/js?id=' not in txt and 'GA disabled' not in txt:
            warnings.append(f'{html.relative_to(base)} analytics not configured')
        if (not public) and 'noindex' not in txt.lower(): errors.append(f'{html.relative_to(base)} protected page missing noindex')
        refs=[]
        for tag,attrs in p.tags:
            for key in ['href','src','poster']:
                if key in attrs: refs.append(attrs[key])
        for ref in refs:
            if not local_exists(base, html, ref): errors.append(f'{html.relative_to(base)} broken local asset/link: {ref}')
    if public:
        for req in ['index.html','newhaven.html','weekly-update.html','source-records.html','readiness.html','methodology.html','downloads.html','privacy.html','terms.html','cookies.html','accessibility.html','contact.html','sitemap.xml','robots.txt','site.webmanifest']:
            if not (base/req).exists(): errors.append(f'Missing public required file: {req}')
        robots=(base/'robots.txt').read_text(encoding='utf-8', errors='ignore') if (base/'robots.txt').exists() else ''
        if 'Disallow: /unredacted/' not in robots: errors.append('robots.txt must disallow /unredacted/')
        if 'Sitemap:' not in robots: errors.append('robots.txt missing Sitemap line')
        sitemap=(base/'sitemap.xml').read_text(encoding='utf-8', errors='ignore') if (base/'sitemap.xml').exists() else ''
        urls=re.findall(r'<loc>(.*?)</loc>', sitemap)
        if len(urls) < 12: errors.append(f'sitemap.xml too small: {len(urls)} URLs')
        if any('/unredacted/' in u for u in urls): errors.append('Public sitemap must not include /unredacted/')
        for p in (base/'downloads').glob('*.zip') if (base/'downloads').exists() else []:
            if 'public' not in p.name.lower():
                errors.append(f'Full ZIP bundle must not be public: downloads/{p.name}')
    else:
        if not (base/'.htaccess').exists(): errors.append('Protected unredacted site missing .htaccess')
        robots=(base/'robots.txt').read_text(encoding='utf-8', errors='ignore') if (base/'robots.txt').exists() else ''
        if 'Disallow: /' not in robots: errors.append('Unredacted robots.txt must disallow all')

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--public', default='site_public')
    ap.add_argument('--unredacted', default='site_unredacted')
    ap.add_argument('--json-out', default='outputs/AQ26_SITE_AUDIT.json')
    args=ap.parse_args()
    errors=[]; warnings=[]
    audit_dir(ROOT/args.public, True, errors, warnings)
    audit_dir(ROOT/args.unredacted, False, errors, warnings)
    out=ROOT/args.json_out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({'ok': not errors, 'error_count': len(errors), 'warning_count': len(warnings), 'errors': errors, 'warnings': warnings}, indent=2), encoding='utf-8')
    if errors:
        print('AQ26 site audit failed:')
        for e in errors: print(' -', e)
        print(f'Full audit written to {out}')
        return 1
    print(f'AQ26 site audit passed with {len(warnings)} warnings. Report: {out}')
    for w in warnings[:20]: print(' - warning:', w)
    return 0
if __name__=='__main__':
    sys.exit(main())
