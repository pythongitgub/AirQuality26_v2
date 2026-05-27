#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, re, shutil
from pathlib import Path

CORE_PAGES = [
    'index.html','archive.html','comparisons.html','source-records.html','readiness.html','methodology.html','downloads.html',
    'about.html','privacy.html','cookies.html','accessibility.html','terms.html','contact.html','historical-comparisons.html','weekly-archive.html','evidence-downloads.html','evidence.html'
]
CSS_NAME='aq26_white_header_legibility.css'
JS_NAME='aq26_white_header_legibility.js'
FULL_LOGO='air_quality_web.svg'
FAVICON='favicon.svg'

def read(p:Path)->str:
    return p.read_text(encoding='utf-8', errors='replace')

def write(p:Path,s:str):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(s, encoding='utf-8')

def copy_asset(asset_source:Path, site_root:Path, name:str):
    dst = site_root/'assets'/name
    src = asset_source/name
    if src.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src,dst)
    return dst.exists()

def ensure_assets(asset_source:Path, site_root:Path):
    (site_root/'assets').mkdir(parents=True, exist_ok=True)
    for name in [FULL_LOGO,FAVICON,'logo_web.svg','apple-touch-icon.png','favicon-32x32.png','favicon-16x16.png','android-chrome-192x192.png','android-chrome-512x512.png','site.webmanifest',CSS_NAME,JS_NAME]:
        copy_asset(asset_source, site_root, name)

def inject_head(html:str)->str:
    links = f'''\n<link rel="icon" type="image/svg+xml" href="assets/{FAVICON}?v=aq26-legibility-20260527">\n<link rel="apple-touch-icon" href="assets/apple-touch-icon.png?v=aq26-legibility-20260527">\n<link rel="stylesheet" href="assets/{CSS_NAME}?v=aq26-legibility-20260527">'''
    if CSS_NAME not in html:
        html = re.sub(r'</head\s*>', links+'\n</head>', html, flags=re.I, count=1)
    script = f'\n<script src="assets/{JS_NAME}?v=aq26-legibility-20260527" defer></script>'
    if JS_NAME not in html:
        html = re.sub(r'</body\s*>', script+'\n</body>', html, flags=re.I, count=1)
    return html

def replace_header_logo(html:str)->str:
    # Replace header image sources that point at compact logos with full header SVG.
    def repl(m):
        tag=m.group(0)
        if 'air_quality_web.svg' in tag:
            return tag
        tag=re.sub(r'src=["\']([^"\']*(?:favicon|logo_web|logo)[^"\']*)["\']', 'src="assets/air_quality_web.svg?v=aq26-legibility-20260527"', tag, flags=re.I)
        if 'aq26-header-logo' not in tag:
            tag=tag.replace('<img ', '<img class="aq26-header-logo" ', 1)
        return tag
    # Only broadly replace img tags; JS also repairs at runtime.
    html = re.sub(r'<img\b[^>]*(?:favicon|logo_web|logo)[^>]*>', repl, html, flags=re.I)
    return html

def ensure_min_page(site_root:Path, page:str):
    p=site_root/page
    if p.exists() and p.stat().st_size>500:
        return
    title = page.replace('.html','').replace('-',' ').title() if page!='index.html' else 'AQ26 Environmental Intelligence Observatory'
    body = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title} · AQ26</title></head><body><header class="site-header"><a class="site-brand" href="index.html"><img class="aq26-header-logo" src="assets/air_quality_web.svg" alt="SCC Nexus Air Quality Report"></a><nav class="site-nav"><a href="index.html">Observatory</a><a href="archive.html">Weekly Archive</a><a href="comparisons.html">Comparisons</a><a href="source-records.html">Source Records</a><a href="readiness.html">Readiness</a><a href="methodology.html">Methodology</a><a href="downloads.html">Downloads</a></nav></header><main><section class="page-hero"><p class="eyebrow">SCC Nexus · AQ26</p><h1>{title}</h1><p>Weekly air-quality and emissions intelligence.</p><p><a class="button primary" href="downloads.html">Latest downloads</a> <a class="button secondary" href="comparisons.html">Explore comparisons</a></p></section><section class="notice"><strong>{title}:</strong> this page has been prepared so users never see a blank screen while the AQ26 evidence backfill populates richer content.</section><section class="card"><h2>Evidence status</h2><p>Backfill outputs and public summaries are refreshed by the AQ26 workflow.</p></section></main><footer>© SCC Nexus / AQ26</footer></body></html>'''
    write(p,body)

def process(site_root:Path, asset_source:Path, force_core:bool):
    site_root.mkdir(parents=True, exist_ok=True)
    ensure_assets(asset_source, site_root)
    if force_core:
        for page in CORE_PAGES:
            ensure_min_page(site_root,page)
    changed=[]
    for p in site_root.glob('*.html'):
        html=read(p)
        new=replace_header_logo(inject_head(html))
        if new!=html:
            write(p,new); changed.append(str(p))
    return changed

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--site-root', default='site_public')
    ap.add_argument('--asset-source', default='website/assets')
    ap.add_argument('--force-core-pages', action='store_true')
    ap.add_argument('--summary', default=None)
    args=ap.parse_args()
    changed=process(Path(args.site_root), Path(args.asset_source), args.force_core_pages)
    summary={'ok':True,'site_root':args.site_root,'changed':changed,'asset_css':CSS_NAME,'asset_js':JS_NAME}
    if args.summary:
        write(Path(args.summary), json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
if __name__=='__main__': main()
