#!/usr/bin/env python3
from __future__ import annotations
import argparse, html, json, os, re
from datetime import datetime, timezone
from pathlib import Path

DOMAIN_DEFAULT = "https://sccairquality.com"
LEGAL_PAGES = {
    "privacy.html": ("Privacy", "How AirQuality26 handles privacy, analytics, public evidence records and redacted outputs."),
    "cookies.html": ("Cookies", "Cookie notice for AirQuality26, including Google Analytics measurement and consent choices."),
    "terms.html": ("Terms", "Terms of use for the AirQuality26 public evidence website."),
    "accessibility.html": ("Accessibility", "Accessibility statement for AirQuality26."),
    "contact.html": ("Contact", "Contact information and evidence-submission guidance for AirQuality26."),
}

FOOTER_LINKS = [
    ("privacy.html", "Privacy"), ("cookies.html", "Cookies"), ("terms.html", "Terms"),
    ("accessibility.html", "Accessibility"), ("contact.html", "Contact"), ("sitemap.xml", "Sitemap"),
]

DEFAULT_DESC = (
    "AirQuality26 publishes weekly provenance-controlled UK incinerator air-quality evidence, "
    "source records, historical comparisons and redacted public reports."
)

def read(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="ignore")

def write(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")

def page_title(text: str, fallback: str) -> str:
    m = re.search(r"<title[^>]*>(.*?)</title>", text, re.I|re.S)
    if m:
        return re.sub(r"\s+", " ", m.group(1)).strip() or fallback
    h = re.search(r"<h1[^>]*>(.*?)</h1>", text, re.I|re.S)
    if h:
        return re.sub(r"<[^>]+>", "", h.group(1)).strip() or fallback
    return fallback

def ensure_head(html_text: str) -> str:
    if re.search(r"<head[\s>]", html_text, re.I):
        return html_text
    return re.sub(r"<html([^>]*)>", r"<html\1>\n<head><meta charset=\"utf-8\"></head>", html_text, count=1, flags=re.I)

def upsert_head_block(text: str, marker: str, block: str) -> str:
    pattern = re.compile(rf"\n?<!-- {re.escape(marker)} START -->.*?<!-- {re.escape(marker)} END -->\n?", re.I|re.S)
    text = pattern.sub("", text)
    return re.sub(r"</head>", f"\n<!-- {marker} START -->\n{block}\n<!-- {marker} END -->\n</head>", text, count=1, flags=re.I)

def upsert_body_block(text: str, marker: str, block: str) -> str:
    pattern = re.compile(rf"\n?<!-- {re.escape(marker)} START -->.*?<!-- {re.escape(marker)} END -->\n?", re.I|re.S)
    text = pattern.sub("", text)
    if re.search(r"</body>", text, re.I):
        return re.sub(r"</body>", f"\n<!-- {marker} START -->\n{block}\n<!-- {marker} END -->\n</body>", text, count=1, flags=re.I)
    return text + f"\n<!-- {marker} START -->\n{block}\n<!-- {marker} END -->\n"

def meta_block(title: str, desc: str, canonical: str, domain: str, ga_id: str) -> str:
    data = {
        "@context": "https://schema.org",
        "@graph": [
            {"@type": "Organization", "@id": domain + "/#organization", "name": "AirQuality26", "url": domain},
            {"@type": "WebSite", "@id": domain + "/#website", "url": domain, "name": "AirQuality26", "publisher": {"@id": domain + "/#organization"}},
            {"@type": "DataCatalog", "@id": domain + "/#catalog", "name": "AirQuality26 public evidence catalogue", "url": domain + "/data-catalog.html"},
        ],
    }
    lines = [
        f'<meta name="description" content="{html.escape(desc, quote=True)}">',
        '<meta name="robots" content="index,follow,max-image-preview:large">',
        f'<link rel="canonical" href="{html.escape(canonical, quote=True)}">',
        f'<meta property="og:title" content="{html.escape(title, quote=True)}">',
        f'<meta property="og:description" content="{html.escape(desc, quote=True)}">',
        f'<meta property="og:url" content="{html.escape(canonical, quote=True)}">',
        '<meta property="og:type" content="website">',
        '<meta name="twitter:card" content="summary_large_image">',
        f'<meta name="twitter:title" content="{html.escape(title, quote=True)}">',
        f'<meta name="twitter:description" content="{html.escape(desc, quote=True)}">',
        '<script type="application/ld+json">' + json.dumps(data, ensure_ascii=False) + '</script>',
    ]
    if ga_id:
        lines += [
            '<script>window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments);}</script>',
            '<script>gtag("consent","default",{"analytics_storage":"denied","ad_storage":"denied","ad_user_data":"denied","ad_personalization":"denied"});</script>',
            f'<script async src="https://www.googletagmanager.com/gtag/js?id={html.escape(ga_id, quote=True)}"></script>',
            f'<script>gtag("js",new Date());gtag("config","{html.escape(ga_id, quote=True)}",{{"anonymize_ip":true}});</script>',
        ]
    return "\n".join(lines)

def footer_block() -> str:
    links = " · ".join(f'<a href="/{href}">{label}</a>' for href, label in FOOTER_LINKS)
    return f'''<style>
.aq26-legal-footer{{background:#071525;color:#e6edf7;padding:24px 18px;margin-top:40px;font-size:14px;line-height:1.5}}
.aq26-legal-footer a{{color:#dbeafe;text-decoration:underline;text-underline-offset:3px}}
.aq26-cookie-banner{{position:fixed;left:16px;right:16px;bottom:16px;background:#071525;color:#fff;padding:16px;border-radius:14px;box-shadow:0 12px 40px rgba(0,0,0,.25);z-index:9999;display:none;max-width:980px;margin:auto}}
.aq26-cookie-banner button{{margin-left:8px;padding:8px 12px;border-radius:8px;border:1px solid #cbd5e1;cursor:pointer}}
.aq26-cookie-banner .accept{{background:#2563eb;color:#fff;border-color:#2563eb}}
</style>
<footer class="aq26-legal-footer" role="contentinfo"><strong>AirQuality26</strong><br>Public pages are redacted and cautious. No endorsement by WHO, UNEP, EEA, C40 Cities or named academic experts is implied.<br>{links}</footer>
<div id="aq26-cookie-banner" class="aq26-cookie-banner" role="dialog" aria-live="polite" aria-label="Cookie notice">
  AirQuality26 uses essential site functions and, with consent, Google Analytics to understand public use of the evidence pages.
  <button type="button" class="accept" onclick="aq26CookieChoice('accepted')">Accept analytics</button>
  <button type="button" onclick="aq26CookieChoice('rejected')">Reject analytics</button>
  <a href="/cookies.html" style="color:#fff;margin-left:10px">Cookie policy</a>
</div>
<script>
function aq26CookieChoice(choice){{localStorage.setItem('aq26_cookie_choice',choice);var b=document.getElementById('aq26-cookie-banner');if(b)b.style.display='none';if(choice==='accepted'&&window.gtag){{gtag('consent','update',{{'analytics_storage':'granted'}});}}}}
(function(){{var c=localStorage.getItem('aq26_cookie_choice');var b=document.getElementById('aq26-cookie-banner');if(!c&&b)b.style.display='block';if(c==='accepted'&&window.gtag){{gtag('consent','update',{{'analytics_storage':'granted'}});}}}})();
</script>'''

def create_legal_page(root: Path, filename: str, title: str, desc: str, domain: str, ga_id: str) -> None:
    body = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)} · AQ26</title></head><body>
<main style="max-width:900px;margin:40px auto;padding:0 18px;font-family:system-ui,-apple-system,Segoe UI,Arial,sans-serif;line-height:1.6"><p><a href="/">← Back to AirQuality26</a></p><h1>{html.escape(title)}</h1><p>{html.escape(desc)}</p>
<p>AirQuality26 publishes controlled, provenance-aware public evidence summaries. Public pages are redacted and cautious; protected unredacted materials are for authorised review only.</p>
<p>Generated and updated automatically by the AQ26 weekly workflow. Last updated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}.</p></main></body></html>'''
    canonical = domain.rstrip('/') + '/' + filename
    body = ensure_head(body)
    body = upsert_head_block(body, 'AQ26 SEO ANALYTICS', meta_block(title + ' · AQ26', desc, canonical, domain.rstrip('/'), ga_id))
    body = upsert_body_block(body, 'AQ26 LEGAL FOOTER COOKIE', footer_block())
    write(root / filename, body)

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--site-root', default='site_public')
    ap.add_argument('--domain', default=os.environ.get('AQ26_PUBLIC_URL', DOMAIN_DEFAULT))
    ap.add_argument('--ga-id', default=os.environ.get('GA_MEASUREMENT_ID','').strip())
    args = ap.parse_args()
    root = Path(args.site_root)
    domain = args.domain.rstrip('/')
    if not root.exists():
        raise SystemExit(f'Missing site root: {root}')
    html_files = [p for p in root.rglob('*.html') if 'unredacted' not in p.parts]
    if not html_files:
        raise SystemExit(f'No HTML files found under {root}')
    for p in html_files:
        txt = ensure_head(read(p))
        rel = p.relative_to(root).as_posix()
        canonical = domain + ('/' if rel == 'index.html' else '/' + rel)
        title = page_title(txt, 'AirQuality26')
        desc = DEFAULT_DESC
        block = meta_block(title, desc, canonical, domain, args.ga_id)
        txt = upsert_head_block(txt, 'AQ26 SEO ANALYTICS', block)
        txt = upsert_body_block(txt, 'AQ26 LEGAL FOOTER COOKIE', footer_block())
        write(p, txt)
    # legal pages after patching existing pages
    for fn, (title, desc) in LEGAL_PAGES.items():
        create_legal_page(root, fn, title, desc, domain, args.ga_id)
    urls = []
    for p in sorted(root.rglob('*.html')):
        if 'unredacted' in p.parts: continue
        rel = p.relative_to(root).as_posix()
        loc = domain + ('/' if rel == 'index.html' else '/' + rel)
        urls.append(loc)
    sitemap = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + ''.join(f'  <url><loc>{html.escape(u)}</loc></url>\n' for u in urls) + '</urlset>\n'
    write(root / 'sitemap.xml', sitemap)
    write(root / 'sitemap.txt', '\n'.join(urls) + '\n')
    write(root / 'robots.txt', f'User-agent: *\nAllow: /\nDisallow: /unredacted/\nSitemap: {domain}/sitemap.xml\n')
    print(f'AQ26 SEO/legal/analytics applied to {root}; pages={len(html_files)}; ga_id_present={bool(args.ga_id)}')
    return 0
if __name__ == '__main__':
    raise SystemExit(main())
