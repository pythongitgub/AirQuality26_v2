#!/usr/bin/env python3
"""AQ26 static site rebuild layer.

Creates/refreshes the core public and protected unredacted pages without touching
.htaccess or .htpasswd. Accepts either configs/aq26_site_config.json or
config/aq26_site_config.json to match the existing AirQuality26_v2 repo.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any

ROOT = Path.cwd()
CONFIG_CANDIDATES = [ROOT / "configs" / "aq26_site_config.json", ROOT / "config" / "aq26_site_config.json"]
PUBLIC_DIR = ROOT / "site_public"
UNREDACTED_DIR = ROOT / "site_unredacted"

DEFAULT_CONFIG: dict[str, Any] = {
    "site_name": "AirQuality26",
    "site_title": "AirQuality26 Environmental Intelligence Observatory",
    "base_url": "https://sccairquality.com",
    "description": "Independent weekly public-interest air-quality evidence tracking, focused on Newhaven and the surrounding communities.",
    "organisation": "SCC Nexus · AQ26",
    "contact_email": "",
}

CORE_PAGES = [
    ("index.html", "AirQuality26", "Weekly public-interest air-quality intelligence for Newhaven and surrounding communities."),
    ("newhaven.html", "Newhaven evidence hub", "A focused hub for Newhaven ERF context, local monitoring, weekly evidence and source records."),
    ("source-records.html", "Source records", "Traceable records and public-source references used by AQ26."),
    ("readiness.html", "Readiness and evidence gates", "Status of evidence readiness, coverage checks and confidence labels."),
    ("methodology.html", "Methodology", "How AQ26 handles collection, redaction, scoring, review and publication."),
    ("archive.html", "Archive", "Historical weekly outputs, public evidence summaries and published bundles."),
    ("comparisons.html", "Comparisons", "Comparative context for emissions, monitoring and community impact indicators."),
    ("privacy.html", "Privacy policy", "How this website handles privacy, analytics and contact information."),
    ("terms.html", "Terms", "Terms of use, disclaimer and public-interest information notice."),
    ("cookies.html", "Cookie policy", "Cookie and analytics information for this website."),
    ("accessibility.html", "Accessibility", "Accessibility statement and improvement contact route."),
    ("contact.html", "Contact", "Contact and corrections route for AQ26."),
    ("404.html", "Page not found", "The page could not be found."),
]

UNREDACTED_EXTRA = [
    ("evidence.html", "Unredacted evidence library", "Protected reviewer evidence library and weekly evidence bundle index."),
    ("review-notes.html", "Reviewer notes", "Protected internal review notes and source-confidence observations."),
]


def load_config() -> dict[str, Any]:
    for path in CONFIG_CANDIDATES:
        if path.exists():
            try:
                loaded = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    cfg = DEFAULT_CONFIG.copy()
                    cfg.update(loaded)
                    return cfg
            except Exception as exc:  # keep build robust but explicit
                raise SystemExit(f"Could not parse {path}: {exc}") from exc
    cfg = DEFAULT_CONFIG.copy()
    return cfg


def page_url(cfg: dict[str, Any], filename: str, unredacted: bool = False) -> str:
    base = str(cfg.get("base_url", DEFAULT_CONFIG["base_url"])).rstrip("/")
    if filename == "index.html":
        return f"{base}/unredacted/" if unredacted else f"{base}/"
    return f"{base}/unredacted/{filename}" if unredacted else f"{base}/{filename}"


def nav(active: str, unredacted: bool) -> str:
    pages = [
        ("index.html", "Home"),
        ("newhaven.html", "Newhaven"),
        ("source-records.html", "Sources"),
        ("readiness.html", "Readiness"),
        ("methodology.html", "Methodology"),
        ("archive.html", "Archive"),
        ("comparisons.html", "Comparisons"),
        ("contact.html", "Contact"),
    ]
    if unredacted:
        pages.insert(3, ("evidence.html", "Evidence"))
        pages.insert(4, ("review-notes.html", "Review notes"))
    else:
        pages.append(("unredacted/", "Unredacted"))
    items = []
    for href, label in pages:
        cls = " class=\"active\"" if href == active else ""
        items.append(f'<a{cls} href="{escape(href)}">{escape(label)}</a>')
    return "\n".join(items)


def analytics(cfg: dict[str, Any]) -> str:
    ga = os.environ.get("GA_MEASUREMENT_ID") or str(cfg.get("ga_measurement_id", "")).strip()
    if not ga:
        return "<!-- Analytics not configured: set GA_MEASUREMENT_ID secret -->"
    ga = escape(ga)
    return f'''<script async src="https://www.googletagmanager.com/gtag/js?id={ga}"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){{dataLayer.push(arguments);}}
  gtag('js', new Date());
  gtag('config', '{ga}', {{ 'anonymize_ip': true }});
</script>'''


def json_ld(cfg: dict[str, Any], title: str, filename: str, unredacted: bool) -> str:
    data = {
        "@context": "https://schema.org",
        "@type": "WebPage",
        "name": title,
        "url": page_url(cfg, filename, unredacted),
        "isPartOf": {
            "@type": "WebSite",
            "name": cfg.get("site_name", "AirQuality26"),
            "url": str(cfg.get("base_url", DEFAULT_CONFIG["base_url"])).rstrip("/") + "/",
        },
        "about": "Air quality evidence, environmental monitoring and public-interest transparency for Newhaven.",
    }
    return '<script type="application/ld+json">' + json.dumps(data, ensure_ascii=False) + '</script>'


def main_content(filename: str, title: str, desc: str, unredacted: bool) -> str:
    protected = "protected unredacted" if unredacted else "public redacted"
    if filename == "newhaven.html":
        return f"""
<section class="hero"><p class="eyebrow">AQ26 evidence hub</p><h1>{escape(title)}</h1><p>{escape(desc)}</p></section>
<section class="grid cards">
  <article><h2>Facility context</h2><p>Clear public-interest context for the Newhaven energy recovery facility, local receptors, weather, transport and monitoring evidence.</p></article>
  <article><h2>Weekly evidence</h2><p>Weekly signals are arranged into source records, readiness gates and archive entries so updates can be checked consistently.</p></article>
  <article><h2>Community clarity</h2><p>The {protected} site is designed to separate verified public material from protected reviewer material and prevent accidental leakage.</p></article>
</section>"""
    if filename == "privacy.html":
        return """
<section class="hero"><h1>Privacy policy</h1><p>This site is designed to minimise personal data collection.</p></section>
<section><h2>What is collected</h2><p>Standard server logs may record browser and request information. Analytics, when enabled, is used to understand broad site usage and improve accessibility and public information.</p><h2>Contact information</h2><p>If you contact AQ26, your message details are used only to respond to the enquiry or correction.</p></section>"""
    if filename == "terms.html":
        return """
<section class="hero"><h1>Terms</h1><p>Public-interest environmental information notice.</p></section>
<section><h2>Use of information</h2><p>AQ26 is an evidence-tracking and information website. It is not legal, medical or regulatory advice. Always consult original official sources for formal decisions.</p><h2>Corrections</h2><p>Corrections and source improvements are welcomed through the contact page.</p></section>"""
    if filename == "cookies.html":
        return """
<section class="hero"><h1>Cookie policy</h1><p>Cookie and analytics information.</p></section>
<section><h2>Analytics</h2><p>Analytics may be used to understand page performance and improve public access. Analytics should be configured with privacy-conscious defaults where possible.</p><h2>Control</h2><p>You can control cookies through your browser settings.</p></section>"""
    if filename == "accessibility.html":
        return """
<section class="hero"><h1>Accessibility</h1><p>AQ26 aims to be readable, mobile-friendly and accessible.</p></section>
<section><h2>Commitment</h2><p>Pages use semantic HTML, consistent navigation, readable contrast and keyboard-friendly links. Accessibility improvements are part of the site quality gate.</p><h2>Feedback</h2><p>Please report accessibility problems through the contact page.</p></section>"""
    if filename == "contact.html":
        return """
<section class="hero"><h1>Contact and corrections</h1><p>Send corrections, source suggestions or accessibility feedback.</p></section>
<section><h2>Corrections welcome</h2><p>Please include the page URL, the sentence or data point concerned, and the source you believe should be used.</p><p>Email: <a href="mailto:info@sccnexus.com">info@sccnexus.com</a></p></section>"""
    if filename == "evidence.html":
        return """
<section class="hero"><h1>Protected evidence library</h1><p>This protected area is for unredacted reviewer evidence and source traceability.</p></section>
<section class="cards"><article><h2>Evidence bundles</h2><p>Weekly evidence bundles, source indexes and reviewer notes should be placed here by the weekly production pipeline.</p></article><article><h2>Redaction control</h2><p>Protected pages are marked noindex and kept behind HTTP Basic Auth.</p></article></section>"""
    if filename == "review-notes.html":
        return """
<section class="hero"><h1>Reviewer notes</h1><p>Protected review observations and source-confidence notes.</p></section>
<section><h2>Review process</h2><p>Use this page for reviewer-only context that must not appear on the public redacted site.</p></section>"""
    if filename == "404.html":
        return """
<section class="hero"><h1>Page not found</h1><p>The page could not be found. Use the menu to return to the AQ26 evidence areas.</p></section>"""
    return f"""
<section class="hero"><p class="eyebrow">{escape(protected.title())} site</p><h1>{escape(title)}</h1><p>{escape(desc)}</p></section>
<section class="grid cards">
  <article><h2>What this page provides</h2><p>Structured AQ26 information with consistent navigation, metadata, footer links and source-aware presentation.</p></article>
  <article><h2>Evidence discipline</h2><p>Content is arranged to support public readability, reviewer traceability and weekly production updates.</p></article>
  <article><h2>Next improvement</h2><p>Legacy evidence tables and weekly data can now be folded into this shared template safely.</p></article>
</section>"""


def render_page(cfg: dict[str, Any], filename: str, title: str, desc: str, unredacted: bool) -> str:
    site_title = escape(str(cfg.get("site_title", DEFAULT_CONFIG["site_title"])))
    canonical = page_url(cfg, filename, unredacted)
    robots = "noindex,nofollow" if unredacted else "index,follow"
    verification = os.environ.get("GOOGLE_SITE_VERIFICATION") or str(cfg.get("google_site_verification", "")).strip()
    verification_tag = f'<meta name="google-site-verification" content="{escape(verification)}">' if verification and not unredacted else ""
    body_class = "unredacted" if unredacted else "public"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return f'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)} · {site_title}</title>
  <meta name="description" content="{escape(desc)}">
  <meta name="robots" content="{robots}">
  <link rel="canonical" href="{escape(canonical)}">
  <meta property="og:title" content="{escape(title)} · {site_title}">
  <meta property="og:description" content="{escape(desc)}">
  <meta property="og:url" content="{escape(canonical)}">
  <meta property="og:type" content="website">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{escape(title)} · {site_title}">
  <meta name="twitter:description" content="{escape(desc)}">
  {verification_tag}
  <style>
    :root{{--ink:#102033;--muted:#52616f;--brand:#0f766e;--brand2:#164e63;--paper:#f7fbfc;--line:#d9e6ea}}
    *{{box-sizing:border-box}} body{{margin:0;font-family:Inter,system-ui,-apple-system,Segoe UI,Arial,sans-serif;color:var(--ink);background:var(--paper);line-height:1.6}}
    a{{color:#0f5e8c}} header{{background:linear-gradient(135deg,#093445,#0f766e);color:white;position:sticky;top:0;z-index:10;box-shadow:0 2px 12px #0002}}
    .wrap{{max-width:1180px;margin:auto;padding:0 1rem}} .top{{display:flex;align-items:center;justify-content:space-between;gap:1rem;padding:1rem 0}}
    .brand{{font-weight:800;font-size:1.15rem;color:white;text-decoration:none;letter-spacing:.02em}} .tag{{font-size:.82rem;opacity:.86}}
    #menu-toggle{{display:none}} .burger{{display:none;font-size:1.8rem;cursor:pointer}}
    nav{{display:flex;gap:.3rem;flex-wrap:wrap;align-items:center}} nav a{{color:white;text-decoration:none;padding:.55rem .7rem;border-radius:999px;font-size:.93rem}} nav a:hover,nav a.active{{background:#ffffff24}}
    main{{max-width:1180px;margin:0 auto;padding:2rem 1rem}} .hero{{background:white;border:1px solid var(--line);border-radius:24px;padding:2rem;margin-bottom:1.2rem;box-shadow:0 8px 30px #1232}}
    .hero h1{{font-size:clamp(2rem,5vw,4rem);line-height:1.05;margin:.2rem 0}} .hero p{{font-size:1.1rem;color:var(--muted);max-width:850px}} .eyebrow{{text-transform:uppercase;letter-spacing:.12em;font-weight:800;color:var(--brand)}}
    .grid{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:1rem}} .cards article, section:not(.hero){{background:white;border:1px solid var(--line);border-radius:18px;padding:1.25rem}}
    footer{{background:#071d26;color:#dbeafe;margin-top:3rem;padding:2rem 0}} footer a{{color:#e0f2fe}} .footergrid{{display:grid;grid-template-columns:2fr 1fr 1fr;gap:1rem}} .small{{font-size:.9rem;color:#b6cbd3}}
    @media(max-width:760px){{.burger{{display:block}} nav{{display:none;width:100%;padding-bottom:1rem}} #menu-toggle:checked ~ nav{{display:flex;flex-direction:column;align-items:stretch}} nav a{{border:1px solid #ffffff22}} .top{{flex-wrap:wrap}} .grid,.footergrid{{grid-template-columns:1fr}}}}
  </style>
  {analytics(cfg)}
  {json_ld(cfg, title, filename, unredacted)}
</head>
<body class="{body_class}">
<header><div class="wrap"><div class="top"><a class="brand" href="{'./' if unredacted else '/'}">AQ26</a><div class="tag">Environmental Intelligence Observatory</div><label for="menu-toggle" class="burger" aria-label="Open menu">☰</label><input id="menu-toggle" type="checkbox"> <nav aria-label="Main navigation">{nav(filename, unredacted)}</nav></div></div></header>
<main>{main_content(filename, title, desc, unredacted)}</main>
<footer><div class="wrap footergrid"><div><strong>AQ26 Environmental Intelligence Observatory</strong><p class="small">Weekly evidence tracking, public-interest transparency and protected reviewer material where appropriate. Last rebuilt {now}.</p></div><div><strong>Legal</strong><p><a href="privacy.html">Privacy</a><br><a href="terms.html">Terms</a><br><a href="cookies.html">Cookies</a><br><a href="accessibility.html">Accessibility</a></p></div><div><strong>Site</strong><p><a href="contact.html">Contact</a><br><a href="sitemap.xml">Sitemap</a><br>{'<a href="/unredacted/">Unredacted</a>' if not unredacted else '<a href="/">Public site</a>'}</p></div></div><div class="wrap small">© {datetime.now(timezone.utc).year} SCC Nexus · AQ26. All rights reserved. Corrections welcome.</div></footer>
</body></html>'''


def write_site(cfg: dict[str, Any], target: Path, unredacted: bool) -> None:
    target.mkdir(parents=True, exist_ok=True)
    pages = CORE_PAGES + (UNREDACTED_EXTRA if unredacted else [])
    for filename, title, desc in pages:
        (target / filename).write_text(render_page(cfg, filename, title, desc, unredacted), encoding="utf-8")
    base = str(cfg.get("base_url", DEFAULT_CONFIG["base_url"])).rstrip("/")
    if unredacted:
        robots = "User-agent: *\nDisallow: /\n"
        sitemap_urls = [page_url(cfg, p[0], True) for p in pages if p[0] != "404.html"]
    else:
        robots = "User-agent: *\nAllow: /\nSitemap: " + base + "/sitemap.xml\n"
        sitemap_urls = [page_url(cfg, p[0], False) for p in pages if p[0] != "404.html"]
    (target / "robots.txt").write_text(robots, encoding="utf-8")
    sitemap = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for url in sitemap_urls:
        sitemap.append(f"  <url><loc>{escape(url)}</loc></url>")
    sitemap.append("</urlset>\n")
    (target / "sitemap.xml").write_text("\n".join(sitemap), encoding="utf-8")


def main() -> None:
    cfg = load_config()
    write_site(cfg, PUBLIC_DIR, False)
    write_site(cfg, UNREDACTED_DIR, True)
    print("Built AQ26 overhauled public and unredacted sites, including legal/contact/accessibility pages.")


if __name__ == "__main__":
    main()
