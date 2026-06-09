#!/usr/bin/env python3
from __future__ import annotations

import html
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

BASE_URL = os.environ.get("AQ26_PUBLIC_BASE_URL", "https://sccairquality.com").rstrip("/")
GA_ID = os.environ.get("GA_MEASUREMENT_ID", "").strip()
SITE_DIRS = [Path("site_public"), Path("site_test")]

DEFAULT_DESCRIPTIONS = {
    "index.html": "AirQuality26 publishes weekly, provenance-controlled UK incinerator air-quality evidence, source records, historical comparisons and redacted public reports.",
    "weekly-update.html": "Latest AirQuality26 controlled weekly evidence update with source-record counts, readiness gates, redaction status and cautious public release notes.",
    "incinerators.html": "AirQuality26 incinerator review index for UK facility monitoring, evidence readiness, public summaries and controlled source-record analysis.",
    "historical.html": "Historical AirQuality26 comparison and backfill status for UK air-quality evidence around incinerators and matched control sites.",
    "source-records.html": "Public-safe AirQuality26 source-record index with provenance metadata, timestamps, redaction status and SHA256 evidence references where applicable.",
    "methodology.html": "AirQuality26 methodology explaining cautious public reporting, source provenance, validation gates, redaction checks and evidence limitations.",
    "downloads.html": "AirQuality26 public downloads for weekly reports, evidence notices, source-record summaries and provenance-controlled public files.",
    "about.html": "About AirQuality26, a cautious environmental evidence observatory publishing weekly public air-quality source records and controlled review outputs.",
    "privacy.html": "AirQuality26 privacy notice explaining what information is collected, how analytics are used, and how public evidence records are protected.",
    "cookies.html": "AirQuality26 cookie policy describing essential cookies, optional Google Analytics measurement, consent controls and privacy-respecting site operation.",
    "terms.html": "AirQuality26 terms of use covering public evidence summaries, limitations, no endorsement, no legal or medical advice and responsible reuse.",
    "accessibility.html": "AirQuality26 accessibility statement for the public website, including readable structure, keyboard access, contrast goals and contact routes.",
    "contact.html": "Contact AirQuality26 for evidence review, corrections, data-source queries, accessibility feedback and controlled unredacted access requests.",
    "data-catalog.html": "AirQuality26 public data catalogue listing weekly JSON feeds, source summaries, readiness metadata and provenance-controlled public outputs.",
    "weekly-archive.html": "AirQuality26 weekly archive for previous public reports, source-record summaries, evidence notices and historical update references.",
}

LEGAL_PAGES = {
    "privacy.html": ("Privacy notice", "AirQuality26 publishes public, redacted evidence summaries. The website may use basic server logs and optional Google Analytics if consent is given. Public pages avoid exposing private file IDs, secret values, or unredacted evidence paths."),
    "cookies.html": ("Cookie policy", "The site uses essential storage for cookie-consent preferences. Google Analytics is only enabled when a GA4 measurement ID is configured and the visitor accepts analytics cookies."),
    "terms.html": ("Terms of use", "AirQuality26 public content is a cautious evidence-review resource. It is not legal advice, medical advice, causal proof, regulatory endorsement, or a substitute for independent expert assessment."),
    "accessibility.html": ("Accessibility statement", "AirQuality26 aims to keep public evidence pages readable, keyboard-accessible and structured with clear headings, links and contrast. Accessibility feedback can be sent through the contact page."),
    "contact.html": ("Contact", "For corrections, evidence-source questions, accessibility feedback, or controlled-review access requests, use the published SCC Nexus contact route or the repository issue process used for AirQuality26."),
}

FOOTER = """
<footer class="aq26-site-footer" role="contentinfo">
  <div class="aq26-footer-inner">
    <div>
      <strong>AirQuality26</strong><br>
      <span>Public pages are redacted and cautious. No endorsement by WHO, UNEP, EEA, C40 Cities or named academic experts is implied.</span>
    </div>
    <nav aria-label="Footer links">
      <a href="/privacy.html">Privacy</a>
      <a href="/cookies.html">Cookies</a>
      <a href="/terms.html">Terms</a>
      <a href="/accessibility.html">Accessibility</a>
      <a href="/contact.html">Contact</a>
      <a href="/sitemap.xml">Sitemap</a>
    </nav>
  </div>
</footer>
""".strip()

CSS = """
<style id="aq26-seo-legal-css">
.aq26-site-footer{margin-top:3rem;background:#081728;color:#eaf2fb;padding:1.5rem 1rem;font-size:.95rem}.aq26-footer-inner{max-width:1120px;margin:0 auto;display:flex;gap:1rem;justify-content:space-between;align-items:flex-start;flex-wrap:wrap}.aq26-site-footer a{color:#eaf2fb;text-decoration:underline;margin-right:1rem}.aq26-cookie-banner{position:fixed;left:1rem;right:1rem;bottom:1rem;z-index:9999;background:#081728;color:#fff;border:1px solid rgba(255,255,255,.25);box-shadow:0 12px 40px rgba(0,0,0,.35);border-radius:14px;padding:1rem;max-width:980px;margin:auto}.aq26-cookie-banner p{margin:.2rem 0 .8rem}.aq26-cookie-actions{display:flex;gap:.6rem;flex-wrap:wrap}.aq26-cookie-actions button{border:0;border-radius:999px;padding:.65rem 1rem;font-weight:700;cursor:pointer}.aq26-cookie-accept{background:#dfefff;color:#07182a}.aq26-cookie-reject{background:#263a50;color:#fff}.aq26-cookie-banner[hidden]{display:none!important}
</style>
""".strip()

COOKIE_AND_ANALYTICS = f"""
<script id="aq26-cookie-consent">
(function(){{
  var GA_ID = {json.dumps(GA_ID)};
  window.dataLayer = window.dataLayer || [];
  function gtag(){{dataLayer.push(arguments);}}
  window.gtag = window.gtag || gtag;
  if (GA_ID) {{
    gtag('consent','default',{{'analytics_storage':'denied'}});
  }}
  function loadGA(){{
    if(!GA_ID || document.getElementById('aq26-ga4-script')) return;
    var s=document.createElement('script');
    s.id='aq26-ga4-script'; s.async=true; s.src='https://www.googletagmanager.com/gtag/js?id='+encodeURIComponent(GA_ID);
    document.head.appendChild(s);
    gtag('js', new Date());
    gtag('config', GA_ID, {{'anonymize_ip': true}});
    gtag('consent','update',{{'analytics_storage':'granted'}});
  }}
  function closeBanner(choice){{
    localStorage.setItem('aq26_cookie_choice', choice);
    var b=document.getElementById('aq26-cookie-banner'); if(b) b.hidden=true;
    if(choice==='accepted') loadGA();
  }}
  document.addEventListener('DOMContentLoaded', function(){{
    var choice=localStorage.getItem('aq26_cookie_choice');
    if(choice==='accepted') loadGA();
    if(choice) return;
    var b=document.createElement('div');
    b.id='aq26-cookie-banner'; b.className='aq26-cookie-banner'; b.setAttribute('role','dialog'); b.setAttribute('aria-label','Cookie notice');
    b.innerHTML='<strong>Cookies and analytics</strong><p>We use essential storage for this notice. Optional Google Analytics helps us understand public interest in AQ26 pages.</p><div class="aq26-cookie-actions"><button class="aq26-cookie-accept" type="button">Accept analytics</button><button class="aq26-cookie-reject" type="button">Reject optional analytics</button><a href="/cookies.html" style="color:#fff;align-self:center">Cookie policy</a></div>';
    document.body.appendChild(b);
    b.querySelector('.aq26-cookie-accept').addEventListener('click', function(){{closeBanner('accepted');}});
    b.querySelector('.aq26-cookie-reject').addEventListener('click', function(){{closeBanner('rejected');}});
  }});
}})();
</script>
""".strip()

JSON_LD = {
    "@context": "https://schema.org",
    "@graph": [
        {"@type": "Organization", "name": "AirQuality26", "url": BASE_URL},
        {"@type": "WebSite", "name": "AirQuality26", "url": BASE_URL, "description": DEFAULT_DESCRIPTIONS["index.html"]},
        {"@type": "DataCatalog", "name": "AirQuality26 public evidence catalogue", "url": f"{BASE_URL}/data-catalog.html", "description": "Public-safe weekly air-quality evidence summaries, source records and provenance metadata."},
    ],
}


def title_from_filename(path: Path) -> str:
    stem = path.stem.replace('-', ' ').replace('_', ' ').strip().title()
    if path.name == 'index.html':
        return 'Environmental Intelligence Observatory · AQ26'
    return f"{stem} · AQ26"


def canonical_for(path: Path, root: Path) -> str:
    rel = path.relative_to(root).as_posix()
    if rel == 'index.html':
        return BASE_URL + '/'
    return BASE_URL + '/' + quote(rel)


def strip_existing_managed_blocks(text: str) -> str:
    # Remove previous managed head/footer/banner blocks to avoid duplicates.
    patterns = [
        r'<style id="aq26-seo-legal-css">.*?</style>',
        r'<script id="aq26-cookie-consent">.*?</script>',
        r'<script type="application/ld\+json" id="aq26-jsonld">.*?</script>',
        r'<footer class="aq26-site-footer".*?</footer>',
        r'<meta name="description" content="[^"]*"\s*/?>',
        r'<link rel="canonical" href="[^"]*"\s*/?>',
        r'<meta property="og:[^"]+" content="[^"]*"\s*/?>',
        r'<meta name="twitter:[^"]+" content="[^"]*"\s*/?>',
    ]
    out = text
    for p in patterns:
        out = re.sub(p, '', out, flags=re.I | re.S)
    return out


def ensure_html_shell(title: str, body: str) -> str:
    return f"<!doctype html>\n<html lang=\"en-GB\">\n<head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"><title>{html.escape(title)}</title></head><body><main><h1>{html.escape(title.replace(' · AQ26',''))}</h1><p>{html.escape(body)}</p></main></body></html>\n"


def ensure_legal_pages(root: Path) -> None:
    for name, (title, body) in LEGAL_PAGES.items():
        p = root / name
        if not p.exists() or p.stat().st_size < 200:
            p.write_text(ensure_html_shell(f"{title} · AQ26", body), encoding='utf-8')


def inject_page(path: Path, root: Path) -> None:
    text = path.read_text(encoding='utf-8', errors='ignore')
    if '<html' not in text.lower():
        return
    text = strip_existing_managed_blocks(text)
    title = title_from_filename(path)
    m = re.search(r'<title>(.*?)</title>', text, flags=re.I | re.S)
    if m and m.group(1).strip():
        title = re.sub(r'\s+', ' ', m.group(1)).strip()
    desc = DEFAULT_DESCRIPTIONS.get(path.name, f"AirQuality26 public evidence page for weekly, provenance-controlled UK air-quality review, redacted source records and cautious incinerator evidence updates.")
    url = canonical_for(path, root)
    head_bits = [
        f'<meta name="description" content="{html.escape(desc, quote=True)}">',
        f'<link rel="canonical" href="{html.escape(url, quote=True)}">',
        f'<meta property="og:title" content="{html.escape(title, quote=True)}">',
        f'<meta property="og:description" content="{html.escape(desc, quote=True)}">',
        f'<meta property="og:url" content="{html.escape(url, quote=True)}">',
        '<meta property="og:type" content="website">',
        '<meta name="twitter:card" content="summary_large_image">',
        f'<meta name="twitter:title" content="{html.escape(title, quote=True)}">',
        f'<meta name="twitter:description" content="{html.escape(desc, quote=True)}">',
        CSS,
    ]
    if path.name == 'index.html':
        head_bits.append('<script type="application/ld+json" id="aq26-jsonld">' + json.dumps(JSON_LD, ensure_ascii=False) + '</script>')
    insertion = '\n'.join(head_bits) + '\n'
    if '</head>' in text.lower():
        text = re.sub(r'</head>', insertion + '</head>', text, flags=re.I, count=1)
    else:
        text = insertion + text
    body_insertion = '\n' + FOOTER + '\n' + COOKIE_AND_ANALYTICS + '\n'
    if '</body>' in text.lower():
        text = re.sub(r'</body>', body_insertion + '</body>', text, flags=re.I, count=1)
    else:
        text += body_insertion
    path.write_text(text, encoding='utf-8')


def write_sitemap(root: Path) -> None:
    urls = []
    for p in sorted(root.rglob('*.html')):
        rel = p.relative_to(root).as_posix()
        if rel.startswith('unredacted/') or rel.startswith('test/'):
            continue
        urls.append((canonical_for(p, root), datetime.fromtimestamp(p.stat().st_mtime, timezone.utc).date().isoformat()))
    xml = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for loc, lastmod in urls:
        priority = '1.0' if loc == BASE_URL + '/' else '0.7'
        xml.append(f'  <url><loc>{html.escape(loc)}</loc><lastmod>{lastmod}</lastmod><changefreq>weekly</changefreq><priority>{priority}</priority></url>')
    xml.append('</urlset>')
    (root / 'sitemap.xml').write_text('\n'.join(xml) + '\n', encoding='utf-8')
    # Keep sitemap.txt for backwards compatibility, but sitemap.xml is the SEO-critical file.
    (root / 'sitemap.txt').write_text('\n'.join(loc for loc, _ in urls) + '\n', encoding='utf-8')


def write_robots(root: Path) -> None:
    (root / 'robots.txt').write_text(f"User-agent: *\nAllow: /\nDisallow: /unredacted/\nDisallow: /test/\nSitemap: {BASE_URL}/sitemap.xml\n", encoding='utf-8')


def process_root(root: Path) -> None:
    if not root.exists():
        print(f"Skipping missing {root}")
        return
    ensure_legal_pages(root)
    for p in sorted(root.rglob('*.html')):
        if 'unredacted' in p.parts:
            continue
        inject_page(p, root)
    write_sitemap(root)
    write_robots(root)
    print(f"SEO/legal/analytics applied to {root}: {len(list(root.rglob('*.html')))} HTML files")


def main() -> int:
    for root in SITE_DIRS:
        process_root(root)
    if GA_ID:
        print(f"GA4 injection enabled for measurement ID prefix: {GA_ID[:4]}…")
    else:
        print("GA4 injection not enabled: GA_MEASUREMENT_ID is not set.")
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
