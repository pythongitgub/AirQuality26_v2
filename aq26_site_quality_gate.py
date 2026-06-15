#!/usr/bin/env python3
from pathlib import Path
import re, sys
ROOT=Path(__file__).resolve().parents[1]
errors=[]
required_public=['index.html','weekly-update.html','incinerators.html','newhaven.html','historical.html','sources.html','methodology.html','downloads.html','about.html','privacy.html','terms.html','cookies.html','accessibility.html','contact.html','404.html','sitemap.xml','robots.txt']
required_unredacted=['index.html','newhaven.html','weekly-update.html','evidence.html','candidates.html','diagnostics.html','methodology.html','archive.html','downloads.html','privacy.html','terms.html','404.html','robots.txt']
for base, files in [(ROOT/'site_public', required_public),(ROOT/'site_unredacted', required_unredacted)]:
    for f in files:
        if not (base/f).exists(): errors.append(f'Missing {base.name}/{f}')
    for htmlf in base.glob('*.html'):
        txt=htmlf.read_text(encoding='utf-8', errors='ignore')
        checks=['<title>','meta name="description"','rel="canonical"','property="og:title"','twitter:card','site-footer','nav-toggle','application/ld+json']
        for c in checks:
            if c not in txt: errors.append(f'{htmlf}: missing {c}')
        if len(txt.strip())<1200: errors.append(f'{htmlf}: suspiciously small')
# Public must link to unredacted
if '/unredacted/' not in (ROOT/'site_public/index.html').read_text(encoding='utf-8', errors='ignore'):
    errors.append('Public index missing /unredacted/ link')
# Unredacted must be noindex/disallow
for htmlf in (ROOT/'site_unredacted').glob('*.html'):
    if 'noindex,nofollow' not in htmlf.read_text(encoding='utf-8', errors='ignore'):
        errors.append(f'{htmlf}: missing noindex')
if errors:
    print('AQ26 site quality gate failed:')
    for e in errors: print(' -', e)
    sys.exit(1)
print('AQ26 site quality gate passed.')
