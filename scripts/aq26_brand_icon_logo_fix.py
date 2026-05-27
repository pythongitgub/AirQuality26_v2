#!/usr/bin/env python3
"""AQ26 site branding/mobile fixer.

Safe post-build step for both public and unredacted static sites:
- copies canonical logo/favicon/touch icons into site assets
- places favicon.svg in the site root as a browser-cache fallback
- injects cache-busted favicon/touch-icon links into every HTML page
- injects robust logo/mobile-nav CSS + hamburger JS
- avoids blank/missing branding when generated site builders overwrite HTML
"""
from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path
from datetime import datetime, timezone

ASSET_NAMES = [
    "logo_web.svg",
    "favicon.svg",
    "favicon-16x16.png",
    "favicon-32x32.png",
    "apple-touch-icon.png",
    "android-chrome-192x192.png",
    "android-chrome-512x512.png",
    "site.webmanifest",
]

CSS_NAME = "aq26_brand_ui_fix.css"
JS_NAME = "aq26_mobile_nav.js"

CSS = r'''
/* AQ26 brand, favicon and mobile navigation fix. Safe to inject after generated CSS. */
:root{
  --aq26-navy:#071628;
  --aq26-navy-2:#0f2238;
  --aq26-cyan:#4fd6c8;
  --aq26-white:#ffffff;
}

/* Make logo visible rather than a tiny stamp. */
img[src*="logo_web"], img[src*="favicon"], .brand img, .site-brand img, header img:first-child, .aq26-logo {
  max-height: 72px !important;
  width: auto !important;
  object-fit: contain !important;
}
header .brand, header .site-brand, .brand, .site-title, .aq26-brand-text {
  display:flex;
  align-items:center;
  gap:.85rem;
}
.aq26-brand-lockup{display:flex;align-items:center;gap:.85rem;text-decoration:none;color:inherit;}
.aq26-brand-lockup img{height:64px;width:auto;max-width:180px;object-fit:contain;}
.aq26-brand-lockup span{font-weight:900;letter-spacing:.01em;line-height:1.15;}

/* Hamburger navigation for phone/tablet widths. */
.aq26-mobile-topbar{
  display:none;
  position:sticky;
  top:0;
  z-index:9999;
  background:rgba(7,22,40,.97);
  color:#fff;
  border-bottom:1px solid rgba(255,255,255,.12);
  padding:.65rem .9rem;
  align-items:center;
  justify-content:space-between;
  gap:.8rem;
  backdrop-filter: blur(8px);
}
.aq26-mobile-brand{display:flex;align-items:center;gap:.65rem;min-width:0;color:#fff;text-decoration:none;}
.aq26-mobile-brand img{height:42px;width:42px;object-fit:contain;border-radius:8px;background:#fff;padding:2px;}
.aq26-mobile-brand strong{font-size:1rem;line-height:1.15;white-space:normal;}
.aq26-menu-button{
  appearance:none;border:1px solid rgba(255,255,255,.35);background:#10243b;color:#fff;
  border-radius:999px;padding:.55rem .8rem;font-weight:800;display:flex;align-items:center;gap:.45rem;
}
.aq26-menu-button span{display:block;width:18px;height:2px;background:#fff;position:relative;}
.aq26-menu-button span:before,.aq26-menu-button span:after{content:"";position:absolute;left:0;width:18px;height:2px;background:#fff;}
.aq26-menu-button span:before{top:-6px}.aq26-menu-button span:after{top:6px}
.aq26-mobile-panel{
  display:none; position:fixed; z-index:9998; left:0; right:0; top:58px;
  background:#071628; padding:.8rem; box-shadow:0 16px 28px rgba(0,0,0,.35);
  border-bottom:1px solid rgba(255,255,255,.12);
}
.aq26-mobile-panel.open{display:block;}
.aq26-mobile-panel a{
  display:block;color:#fff;text-decoration:none;font-weight:800;padding:.85rem 1rem;
  border-radius:14px;background:rgba(255,255,255,.08);margin:.35rem 0;
}
.aq26-mobile-panel a:hover{background:rgba(79,214,200,.18);}

/* Better internal review tables. */
.aq26-evidence-tools{display:flex;flex-wrap:wrap;gap:.6rem;margin:1rem 0;}
.aq26-evidence-tools input,.aq26-evidence-tools select{padding:.75rem .9rem;border-radius:12px;border:1px solid rgba(15,34,56,.25);min-width:220px;}
.aq26-table-wrap{overflow:auto;border:1px solid rgba(15,34,56,.16);border-radius:18px;background:#fff;box-shadow:0 10px 24px rgba(7,22,40,.08);}
.aq26-table-wrap table{width:100%;border-collapse:collapse;font-size:.92rem;}
.aq26-table-wrap th{position:sticky;top:0;background:#071628;color:#fff;text-align:left;padding:.8rem;z-index:1;}
.aq26-table-wrap td{padding:.72rem .8rem;border-top:1px solid #e6edf5;vertical-align:top;}
.aq26-table-wrap tr:nth-child(even){background:#f8fbff;}
.aq26-chip{display:inline-block;border-radius:999px;background:#e6f7f5;color:#073f46;font-weight:800;padding:.22rem .55rem;font-size:.78rem;}

@media (max-width: 820px){
  .aq26-mobile-topbar{display:flex;}
  body{padding-top:0!important;}
  nav:not(.aq26-mobile-panel), header nav, .nav, .menu, .nav-pills, .site-nav, .top-nav ul, .main-nav ul{
    display:none !important;
  }
  header{padding:.8rem 1rem!important;}
  header .brand img, header .site-brand img, .brand img, .site-brand img, .aq26-brand-lockup img{height:48px!important;max-height:48px!important;}
  h1{font-size:clamp(2rem,10vw,3.2rem)!important;line-height:1.05!important;}
  .hero,.aq26-hero{padding:2rem 1rem!important;border-radius:22px!important;}
  .card,.panel,.metric-card{margin-bottom:1rem!important;}
}
'''

JS = r'''
(function(){
  function ready(fn){ if(document.readyState !== 'loading') fn(); else document.addEventListener('DOMContentLoaded', fn); }
  function uniqueLinks(){
    var labels = ['Observatory','Weekly Archive','Comparisons','Source Records','Readiness','Methodology','Downloads'];
    var hrefs = ['index.html','archive.html','comparisons.html','source-records.html','readiness.html','methodology.html','downloads.html'];
    return labels.map(function(label, i){ return {label: label, href: hrefs[i]}; });
  }
  ready(function(){
    if(document.querySelector('.aq26-mobile-topbar')) return;
    var logo = 'assets/logo_web.svg';
    var top = document.createElement('div');
    top.className = 'aq26-mobile-topbar';
    top.innerHTML = '<a class="aq26-mobile-brand" href="index.html"><img src="'+logo+'" alt="AQ26"><strong>AQ26 Environmental Intelligence</strong></a><button class="aq26-menu-button" type="button" aria-expanded="false" aria-controls="aq26-mobile-panel"><span></span> Menu</button>';
    var panel = document.createElement('nav');
    panel.className = 'aq26-mobile-panel';
    panel.id = 'aq26-mobile-panel';
    panel.setAttribute('aria-label','Mobile navigation');
    uniqueLinks().forEach(function(x){ var a=document.createElement('a'); a.href=x.href; a.textContent=x.label; panel.appendChild(a); });
    document.body.insertBefore(panel, document.body.firstChild);
    document.body.insertBefore(top, document.body.firstChild);
    var btn = top.querySelector('button');
    btn.addEventListener('click', function(){
      var open = panel.classList.toggle('open');
      btn.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
  });
})();
'''

MANIFEST = '{"name":"AQ26 Environmental Intelligence","short_name":"AQ26","icons":[{"src":"assets/android-chrome-192x192.png","sizes":"192x192","type":"image/png"},{"src":"assets/android-chrome-512x512.png","sizes":"512x512","type":"image/png"}],"theme_color":"#071628","background_color":"#071628","display":"standalone"}\n'

HEAD_SNIPPET = f'''
<!-- AQ26 brand/icon/mobile patch -->
<link rel="icon" href="favicon.svg?v=aq26-20260527" type="image/svg+xml">
<link rel="icon" href="assets/favicon.svg?v=aq26-20260527" type="image/svg+xml">
<link rel="icon" type="image/png" sizes="32x32" href="assets/favicon-32x32.png?v=aq26-20260527">
<link rel="icon" type="image/png" sizes="16x16" href="assets/favicon-16x16.png?v=aq26-20260527">
<link rel="apple-touch-icon" href="assets/apple-touch-icon.png?v=aq26-20260527">
<link rel="manifest" href="assets/site.webmanifest?v=aq26-20260527">
<link rel="stylesheet" href="assets/{CSS_NAME}?v=aq26-20260527">
<script defer src="assets/{JS_NAME}?v=aq26-20260527"></script>
<!-- /AQ26 brand/icon/mobile patch -->
'''


def copy_assets(site: Path, source: Path) -> None:
    assets = site / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    for name in ASSET_NAMES:
        src = source / name
        if src.exists():
            shutil.copy2(src, assets / name)
    # root-level favicon has higher chance of overriding cached/implicit browser lookup
    for name in ["favicon.svg", "favicon-32x32.png", "favicon-16x16.png"]:
        src = assets / name
        if src.exists():
            shutil.copy2(src, site / name)
    if not (assets / "site.webmanifest").exists():
        (assets / "site.webmanifest").write_text(MANIFEST, encoding="utf-8")
    (assets / CSS_NAME).write_text(CSS, encoding="utf-8")
    (assets / JS_NAME).write_text(JS, encoding="utf-8")


def inject_head(html: str) -> str:
    # remove older AQ26 brand patch snippets to prevent duplicates
    html = re.sub(r'<!-- AQ26 brand/icon/mobile patch -->.*?<!-- /AQ26 brand/icon/mobile patch -->\s*', '', html, flags=re.S)
    # remove common old icon declarations so our cache-busted one wins
    html = re.sub(r'<link[^>]+rel=["\'](?:icon|apple-touch-icon|manifest)["\'][^>]*>\s*', '', html, flags=re.I)
    html = re.sub(r'<link[^>]+href=["\'][^"\']*(?:favicon|apple-touch-icon|site\.webmanifest)[^"\']*["\'][^>]*>\s*', '', html, flags=re.I)
    if '</head>' in html:
        return html.replace('</head>', HEAD_SNIPPET + '\n</head>', 1)
    return HEAD_SNIPPET + html


def improve_logo_text(html: str) -> str:
    # If generated pages have tiny logo images, force width/height-independent class by wrapping first logo-ish image.
    html = re.sub(r'<img([^>]+(?:logo_web|favicon|SCC|scc)[^>]*)>', r'<img class="aq26-logo"\1>', html, count=1, flags=re.I)
    return html


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--site-root', default='site_public')
    ap.add_argument('--asset-source', default='website/assets')
    ap.add_argument('--summary', default=None)
    args = ap.parse_args()

    site = Path(args.site_root)
    source = Path(args.asset_source)
    site.mkdir(parents=True, exist_ok=True)
    copy_assets(site, source)

    changed = []
    for path in sorted(site.glob('*.html')):
        html = path.read_text(encoding='utf-8', errors='ignore')
        new = improve_logo_text(inject_head(html))
        if new != html:
            path.write_text(new, encoding='utf-8')
            changed.append(str(path))

    summary = {
        'ok': True,
        'site_root': str(site),
        'asset_source': str(source),
        'changed_html_files': len(changed),
        'updated_at_utc': datetime.now(timezone.utc).isoformat(),
        'favicon_root_exists': (site/'favicon.svg').exists(),
        'logo_asset_exists': (site/'assets'/'logo_web.svg').exists(),
        'mobile_css_exists': (site/'assets'/CSS_NAME).exists(),
        'mobile_js_exists': (site/'assets'/JS_NAME).exists(),
    }
    if args.summary:
        Path(args.summary).parent.mkdir(parents=True, exist_ok=True)
        Path(args.summary).write_text(__import__('json').dumps(summary, indent=2), encoding='utf-8')
    print(__import__('json').dumps(summary, indent=2))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
