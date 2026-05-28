#!/usr/bin/env python3
"""Apply AQ26 moving banners to generated public/unredacted HTML pages.

This is intentionally idempotent. It copies the banner assets into the site and injects
CSS/JS references into each HTML file if missing.
"""
from __future__ import annotations
import argparse, json, shutil
from pathlib import Path

CSS = 'aq26_moving_banners.css'
JS = 'aq26_moving_banners.js'

def inject(html: str) -> str:
    css_tag = '<link rel="stylesheet" href="assets/aq26_moving_banners.css?v=aq26-motion-20260528">'
    js_tag = '<script defer src="assets/aq26_moving_banners.js?v=aq26-motion-20260528"></script>'
    if CSS not in html:
        if '</head>' in html:
            html = html.replace('</head>', f'  {css_tag}\n</head>', 1)
        else:
            html = css_tag + '\n' + html
    if JS not in html:
        if '</body>' in html:
            html = html.replace('</body>', f'  {js_tag}\n</body>', 1)
        else:
            html = html + '\n' + js_tag + '\n'
    return html

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--site-root', default='site_public')
    ap.add_argument('--asset-source', default='website/assets')
    ap.add_argument('--summary', default=None)
    args=ap.parse_args()
    site=Path(args.site_root)
    assets=site/'assets'
    assets.mkdir(parents=True, exist_ok=True)
    src=Path(args.asset_source)
    copied=[]
    for name in [CSS, JS]:
        s=src/name
        if not s.exists():
            raise FileNotFoundError(f'Missing required asset: {s}')
        shutil.copy2(s, assets/name)
        copied.append(str(assets/name))
    changed=[]
    for p in sorted(site.glob('*.html')):
        old=p.read_text(encoding='utf-8', errors='replace')
        new=inject(old)
        if new != old:
            p.write_text(new, encoding='utf-8')
            changed.append(str(p))
    out={'ok': True, 'site_root': str(site), 'copied_assets': copied, 'html_changed': changed, 'html_changed_count': len(changed)}
    if args.summary:
        sp=Path(args.summary); sp.parent.mkdir(parents=True, exist_ok=True); sp.write_text(json.dumps(out, indent=2), encoding='utf-8')
    print(json.dumps(out, indent=2))
if __name__ == '__main__': main()
