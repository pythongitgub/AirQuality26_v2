#!/usr/bin/env python3
"""
AQ26 public site guard builder.
Creates/repairs a complete public static-site shell so the client-facing website
never deploys blank pages, then validates the required pages.

Backward-compatible CLI flags are intentionally supported because several AQ26
workflows call this script with older arguments such as --fail-on-blank.
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from datetime import datetime, timezone

CORE_PAGES = {
    "index.html": ("AQ26 Environmental Intelligence Observatory", "Weekly air-quality and emissions intelligence", "Explore the latest evidence status, monitoring coverage, reports and provenance summaries."),
    "archive.html": ("Weekly Archive", "Browse weekly evidence runs", "Historical weekly runs will appear here as the backfill completes. Current summaries remain available while historical pages are being populated."),
    "comparisons.html": ("Interactive Comparison Charts", "Source coverage, readiness and filings", "Validated charts are being generated from the weekly backfill. Until then, this page shows the comparison areas that will be populated."),
    "source-records.html": ("Source Records", "Where the evidence comes from", "Provider records, source classes, retrieval status and provenance summaries are collected here."),
    "readiness.html": ("Readiness", "Evidence gates and validation status", "This page summarises which evidence layers are ready for public interpretation and which remain under validation."),
    "methodology.html": ("Methodology", "How AQ26 builds evidence", "AQ26 separates raw evidence, validation, public summaries and internal review outputs."),
    "downloads.html": ("Downloads", "Reports and public evidence packs", "Redacted public downloads are shown here after each successful weekly evidence build."),
    "about.html": ("About AQ26", "Environmental intelligence for public understanding", "AQ26 brings together monitoring, weather, official documents, satellite context and provenance."),
    "privacy.html": ("Privacy", "Privacy notice", "This static website is designed to avoid unnecessary personal data collection."),
    "cookies.html": ("Cookies", "Cookie information", "AQ26 uses essential local preferences for banners and display features."),
    "accessibility.html": ("Accessibility", "Accessible public information", "AQ26 aims to present environmental intelligence in a clear, accessible way."),
    "terms.html": ("Terms", "Use of this website", "AQ26 information is provided for evidence review and public understanding, not as regulatory or medical advice."),
    "contact.html": ("Contact", "Get in touch", "Use the project contact route for evidence questions, corrections or partnership enquiries."),
}
ALIASES = {
    "historical-comparisons.html": "comparisons.html",
    "weekly-archive.html": "archive.html",
    "evidence-downloads.html": "downloads.html",
}
NAV = [
    ("Observatory", "index.html"),
    ("Weekly Archive", "archive.html"),
    ("Comparisons", "comparisons.html"),
    ("Source Records", "source-records.html"),
    ("Readiness", "readiness.html"),
    ("Methodology", "methodology.html"),
    ("Downloads", "downloads.html"),
]
FOOT = [("About", "about.html"), ("Privacy", "privacy.html"), ("Cookies", "cookies.html"), ("Accessibility", "accessibility.html"), ("Terms", "terms.html"), ("Contact", "contact.html")]

CSS = """
:root{--aq26-bg:#07111f;--aq26-card:#0f1f35;--aq26-text:#eef7ff;--aq26-muted:#a8bfd4;--aq26-accent:#2dd4bf;--aq26-blue:#60a5fa;--aq26-warn:#fbbf24}*{box-sizing:border-box}body{margin:0;font-family:Inter,ui-sans-serif,system-ui,-apple-system,Segoe UI,Arial,sans-serif;background:linear-gradient(135deg,#07111f 0%,#10233e 52%,#0b342f 100%);color:var(--aq26-text);line-height:1.55}.site-header{position:sticky;top:0;z-index:20;background:rgba(7,17,31,.88);backdrop-filter:blur(12px);border-bottom:1px solid rgba(255,255,255,.1)}.header-inner{max-width:1180px;margin:auto;padding:14px 18px;display:flex;align-items:center;gap:16px}.brand{display:flex;align-items:center;gap:10px;font-weight:800;letter-spacing:.03em}.brand img{width:42px;height:42px}.desktop-nav{margin-left:auto;display:flex;gap:8px;flex-wrap:wrap}.desktop-nav a,.mobile-panel a{color:var(--aq26-text);text-decoration:none;padding:9px 12px;border-radius:999px;background:rgba(255,255,255,.08);font-size:.92rem}.desktop-nav a:hover,.mobile-panel a:hover{background:rgba(45,212,191,.22)}.hamburger{display:none;margin-left:auto;background:rgba(255,255,255,.12);border:1px solid rgba(255,255,255,.22);color:var(--aq26-text);padding:9px 12px;border-radius:12px}.mobile-panel{display:none;padding:10px 18px 16px;border-top:1px solid rgba(255,255,255,.1)}.mobile-panel.open{display:grid;gap:8px}.hero,.content{max-width:1180px;margin:auto;padding:42px 18px}.hero-card{padding:34px;border:1px solid rgba(255,255,255,.14);border-radius:28px;background:linear-gradient(135deg,rgba(15,31,53,.92),rgba(7,58,53,.75));box-shadow:0 22px 60px rgba(0,0,0,.25)}h1{font-size:clamp(2rem,5vw,4.6rem);line-height:1.02;margin:0 0 16px}.lead{font-size:1.18rem;color:var(--aq26-muted);max-width:840px}.grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:18px}.card{background:rgba(15,31,53,.82);border:1px solid rgba(255,255,255,.13);border-radius:22px;padding:22px}.kicker{color:var(--aq26-accent);font-weight:700;text-transform:uppercase;letter-spacing:.12em;font-size:.78rem}.big{font-size:2.25rem;font-weight:850}.muted{color:var(--aq26-muted)}.button-row{display:flex;gap:12px;flex-wrap:wrap;margin-top:20px}.button{display:inline-block;color:#06111f;background:var(--aq26-accent);text-decoration:none;border-radius:14px;padding:12px 16px;font-weight:800}.button.secondary{background:rgba(255,255,255,.12);color:var(--aq26-text);border:1px solid rgba(255,255,255,.18)}footer{max-width:1180px;margin:30px auto;padding:24px 18px;color:var(--aq26-muted);border-top:1px solid rgba(255,255,255,.12)}footer a{color:var(--aq26-muted);margin-right:12px}.fallback-note{border-left:4px solid var(--aq26-warn);padding:14px 16px;background:rgba(251,191,36,.12);border-radius:14px;margin:18px 0}.chart-shell{min-height:220px;display:grid;place-items:center;border:1px dashed rgba(255,255,255,.25);border-radius:18px;color:var(--aq26-muted);padding:24px;text-align:center}@media(max-width:820px){.desktop-nav{display:none}.hamburger{display:block}.header-inner{padding:12px}.grid{grid-template-columns:1fr}.hero,.content{padding:24px 14px}.hero-card{padding:24px}.brand span{font-size:.95rem}}
""".strip()
JS = """
(function(){function ready(fn){if(document.readyState!=='loading')fn();else document.addEventListener('DOMContentLoaded',fn)}ready(function(){var b=document.querySelector('[data-aq26-menu]');var p=document.querySelector('[data-aq26-mobile-panel]');if(!b||!p)return;b.addEventListener('click',function(){var open=p.classList.toggle('open');b.setAttribute('aria-expanded',open?'true':'false')});});})();
""".strip()

def now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')

def has_content(path: Path) -> bool:
    return path.exists() and path.stat().st_size > 300 and "AQ26" in path.read_text(encoding="utf-8", errors="ignore")

def nav_html():
    return "".join(f'<a href="{href}">{label}</a>' for label, href in NAV)

def foot_html():
    return "".join(f'<a href="{href}">{label}</a>' for label, href in FOOT)

def page_html(title, subtitle, body, active=""):
    cards = """
    <section class="grid" aria-label="AQ26 public dashboard summary">
      <article class="card"><div class="kicker">Evidence</div><div class="big">Weekly</div><p class="muted">Backfill outputs and public summaries are refreshed by the AQ26 workflow.</p></article>
      <article class="card"><div class="kicker">Coverage</div><div class="big">Multi-source</div><p class="muted">Ground monitoring, weather, official records and satellite/reanalysis context.</p></article>
      <article class="card"><div class="kicker">Integrity</div><div class="big">Provenance</div><p class="muted">Public pages use redacted summaries. Internal QA remains in the protected review area.</p></article>
    </section>
    """
    return f"""<!doctype html>
<html lang="en-GB"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title} · AQ26</title><meta name="description" content="AQ26 public environmental intelligence dashboard"><link rel="icon" type="image/svg+xml" href="assets/favicon.svg"><link rel="apple-touch-icon" href="assets/apple-touch-icon.png"><link rel="manifest" href="assets/site.webmanifest"><link rel="stylesheet" href="assets/aq26_mobile_nav.css"></head>
<body><header class="site-header"><div class="header-inner"><a class="brand" href="index.html" style="color:inherit;text-decoration:none"><img src="assets/favicon.svg" alt="AQ26"><span>AQ26 Environmental Intelligence</span></a><nav class="desktop-nav" aria-label="Main navigation">{nav_html()}</nav><button class="hamburger" data-aq26-menu aria-expanded="false">☰ Menu</button></div><nav class="mobile-panel" data-aq26-mobile-panel aria-label="Mobile navigation">{nav_html()}</nav></header>
<main><section class="hero"><div class="hero-card"><div class="kicker">SCC Nexus · AQ26</div><h1>{title}</h1><p class="lead">{subtitle}</p><div class="button-row"><a class="button" href="downloads.html">Latest downloads</a><a class="button secondary" href="comparisons.html">Explore comparisons</a></div></div></section><section class="content">{body}{cards}</section></main>
<footer><div>{foot_html()}</div><p>© SCC Nexus / AQ26. Public interface for environmental evidence summaries; no endorsement, regulatory determination or causal attribution is claimed.</p><p class="muted">Generated {now()}</p></footer><script src="assets/aq26_mobile_nav.js"></script></body></html>"""

def body_for(name, title, subtitle):
    if name == "comparisons.html":
        return """<div class="fallback-note"><strong>Charts warming up:</strong> validated comparison panels are generated by the WeeklyV2 backfill. This page will never remain blank; fallback cards are shown until chart JSON is present.</div><div class="grid"><div class="card"><h2>Weekly source coverage</h2><div class="chart-shell">Awaiting source coverage chart payload</div></div><div class="card"><h2>Readiness trend</h2><div class="chart-shell">Awaiting readiness trend chart payload</div></div><div class="card"><h2>Official filings</h2><div class="chart-shell">Awaiting filings chart payload</div></div></div>"""
    if name == "downloads.html":
        return """<div class="fallback-note"><strong>Public downloads:</strong> latest public/redacted bundles appear here after a successful weekly build.</div><div class="grid"><div class="card"><h2>Evidence ZIP</h2><p class="muted">Use this when available for the public redacted evidence bundle.</p><a class="button" href="downloads/latest-evidence.zip">Download latest evidence ZIP</a></div><div class="card"><h2>Report PDF</h2><p class="muted">Weekly report PDF alias.</p><a class="button secondary" href="downloads/latest-report.pdf">Download latest report</a></div><div class="card"><h2>Internal review</h2><p class="muted">Unredacted materials are restricted to the protected review site.</p></div></div>"""
    if name == "archive.html":
        return """<div class="fallback-note"><strong>Backfill in progress:</strong> historical weeks are being populated progressively. This archive will expand as validated weeks are added.</div><div class="grid"><div class="card"><h2>Latest week</h2><p class="muted">Current weekly evidence summary.</p></div><div class="card"><h2>Historical windows</h2><p class="muted">Backfill windows and status cards will appear here.</p></div><div class="card"><h2>Validation</h2><p class="muted">Only validated public summaries are shown.</p></div></div>"""
    return f"""<div class="fallback-note"><strong>{title}:</strong> this page has been prepared so users never see a blank screen while the AQ26 evidence backfill populates richer content.</div><p class="lead">{subtitle}</p>"""

def write_assets(site_root: Path, asset_source: Path):
    assets = site_root / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    for name in ["logo_web.svg", "favicon.svg", "apple-touch-icon.png", "favicon-32x32.png", "favicon-16x16.png", "android-chrome-192x192.png", "android-chrome-512x512.png", "site.webmanifest"]:
        src = asset_source / name
        if src.exists():
            shutil.copy2(src, assets / name)
    if not (assets / "favicon.svg").exists():
        (assets / "favicon.svg").write_text("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 128 128'><rect width='128' height='128' rx='28' fill='#07111f'/><circle cx='64' cy='64' r='38' fill='#2dd4bf'/><text x='64' y='72' text-anchor='middle' font-family='Arial' font-size='28' font-weight='700' fill='#07111f'>AQ</text></svg>", encoding="utf-8")
    (assets / "aq26_mobile_nav.css").write_text(CSS, encoding="utf-8")
    (assets / "aq26_mobile_nav.js").write_text(JS, encoding="utf-8")
    if not (assets / "site.webmanifest").exists():
        (assets / "site.webmanifest").write_text(json.dumps({"name":"AQ26","short_name":"AQ26","start_url":"/","display":"standalone","background_color":"#07111f","theme_color":"#07111f"}, indent=2), encoding="utf-8")

def create_alias(path: Path, target: str):
    html = f"""<!doctype html><html lang="en-GB"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="refresh" content="0; url={target}"><title>Redirecting · AQ26</title><link rel="canonical" href="{target}"></head><body><p>Redirecting to <a href="{target}">{target}</a>.</p></body></html>"""
    path.write_text(html, encoding="utf-8")

def ensure_download_aliases(site_root: Path):
    d = site_root / "downloads"
    d.mkdir(parents=True, exist_ok=True)
    if not (d / "latest-evidence.zip").exists():
        (d / "latest-evidence.zip").write_bytes(b"AQ26 public evidence bundle placeholder. Await next successful WeeklyV2 backfill for full bundle.\n")
    if not (d / "latest-report.pdf").exists():
        (d / "latest-report.pdf").write_bytes(b"%PDF-1.4\n% AQ26 placeholder PDF. Await next successful WeeklyV2 backfill.\n%%EOF\n")

def build(site_root: Path, asset_source: Path, force: bool):
    site_root.mkdir(parents=True, exist_ok=True)
    write_assets(site_root, asset_source)
    for name, (title, subtitle, desc) in CORE_PAGES.items():
        p = site_root / name
        if force or not has_content(p):
            p.write_text(page_html(title, subtitle, body_for(name, title, subtitle)), encoding="utf-8")
    for alias, target in ALIASES.items():
        create_alias(site_root / alias, target)
    ensure_download_aliases(site_root)
    (site_root / "robots.txt").write_text("User-agent: *\nAllow: /\n", encoding="utf-8")
    (site_root / "sitemap.txt").write_text("\n".join(CORE_PAGES.keys()) + "\n", encoding="utf-8")

def validate(site_root: Path):
    problems=[]
    for name in CORE_PAGES:
        p=site_root/name
        if not has_content(p):
            problems.append(f"{name}: missing or blank")
    for name in ALIASES:
        if not (site_root/name).exists():
            problems.append(f"{name}: alias missing")
    for name in ["assets/aq26_mobile_nav.css", "assets/aq26_mobile_nav.js", "assets/favicon.svg", "downloads/latest-evidence.zip", "downloads/latest-report.pdf"]:
        if not (site_root/name).exists():
            problems.append(f"{name}: missing")
    return {"ok": not problems, "problems": problems, "site_root": str(site_root)}

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--site-root", default="site_public")
    ap.add_argument("--asset-source", default="website/assets")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--force-public-pages", action="store_true")
    ap.add_argument("--force-comparisons", action="store_true")
    ap.add_argument("--force-downloads", action="store_true")
    ap.add_argument("--force-archive", action="store_true")
    ap.add_argument("--validate-only", action="store_true")
    ap.add_argument("--fail-on-blank", action="store_true", help="Backward-compatible alias: fail if validation finds blank/missing pages.")
    ap.add_argument("--summary", default="")
    args=ap.parse_args()
    site_root=Path(args.site_root)
    asset_source=Path(args.asset_source)
    force = args.force or args.force_public_pages or args.force_comparisons or args.force_downloads or args.force_archive
    if not args.validate_only:
        build(site_root, asset_source, force=True if force else False)
    result=validate(site_root)
    txt=json.dumps(result, indent=2)
    print(txt)
    if args.summary:
        Path(args.summary).parent.mkdir(parents=True, exist_ok=True)
        Path(args.summary).write_text(txt, encoding="utf-8")
    if (args.fail_on_blank or args.validate_only) and not result["ok"]:
        raise SystemExit(2)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
