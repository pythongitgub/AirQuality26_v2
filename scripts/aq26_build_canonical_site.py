#!/usr/bin/env python3
"""Build AQ26 publication site with restored branded header, video banner and assets.

This keeps the clean publication/readiness-gated structure, but restores the
AQ26/SCC Nexus visual system from the proven public site: horizontal header logo,
video hero/banner, cards, ticker, footer, sitemap/robots and protected pages.
"""
from __future__ import annotations

import datetime as dt
import html
import json
import os
import shutil
from pathlib import Path
from typing import Any

try:
    import yaml
except Exception as exc:
    raise SystemExit("PyYAML is required. Add pyyaml to the workflow.") from exc

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs" / "aq26_canonical_site.yml"
PUBLIC = ROOT / "site_public"
UNREDACTED = ROOT / "site_unredacted"
TEST = ROOT / "site_test"
ASSET_SOURCE_DIRS = [ROOT / "assets", ROOT / "website" / "assets"]

PUBLIC_CLAIM_NOTE = (
    "AQ26 publishes provenance-led environmental evidence screening and operational readiness notes. "
    "It is not a regulatory determination, legal advice, medical advice, laboratory certification or proof of causal attribution."
)

PAGES = [
    ("index.html", "Home", "Weekly public-interest air-quality intelligence for Newhaven and surrounding communities."),
    ("newhaven.html", "Newhaven", "Public redacted Newhaven ERF / BV8067IL evidence hub and review status."),
    ("source-records.html", "Sources", "Public-safe source records, provenance notes and evidence categories."),
    ("weekly-update.html", "Weekly update", "Latest public weekly AQ26 evidence summary and publication status."),
    ("readiness.html", "Readiness", "Evidence readiness, QA gates and publication boundaries."),
    ("methodology.html", "Methodology", "AQ26 methods, caveats, redaction policy and review workflow."),
    ("downloads.html", "Downloads", "Public-safe downloads and audit outputs."),
    ("archive.html", "Archive", "Historical weekly archive and backfill status."),
    ("about.html", "About", "About AQ26 and the publication workflow."),
    ("privacy.html", "Privacy", "Privacy policy for AQ26."),
    ("terms.html", "Terms", "Terms of use for AQ26."),
    ("cookies.html", "Cookies", "Cookie notice for AQ26."),
    ("accessibility.html", "Accessibility", "Accessibility statement."),
    ("contact.html", "Contact", "Contact, corrections and source-update enquiries."),
]

UNREDACTED_PAGES = [
    ("index.html", "Protected review", "Protected AQ26 reviewer evidence area."),
    ("evidence.html", "Evidence library", "Protected source-led evidence library and controlled-review index."),
    ("source-records.html", "Unredacted sources", "Protected source records and review traceability."),
    ("readiness.html", "Protected readiness", "Protected readiness gates and internal review status."),
    ("downloads.html", "Protected downloads", "Protected evidence downloads and review material."),
    ("methodology.html", "Protected methodology", "Internal methodology, limitations and reviewer controls."),
    ("contact.html", "Protected contact", "Reviewer contact and correction route."),
]

READINESS = {
    "Redaction gate": "ready",
    "Provenance/source records": "ready",
    "Official filing relevance": "needs strict filtering",
    "Ground monitoring": "context only until monitor role/wind-sector checks pass",
    "Satellite catalogue": "catalogue ready; extraction/interpretation gated",
    "CAMS/model context": "not ready unless endpoint configured",
    "External submission": "not ready",
}


def load_config() -> dict[str, Any]:
    if CONFIG_PATH.exists():
        return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
    return {"site": {"public_base_url": "https://sccairquality.com", "unredacted_base_url": "https://sccairquality.com/unredacted", "organisation": "SCC Nexus", "contact_email": "enquiries@sccairquality.com"}}


def clean(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def now_iso() -> str:
    try:
        from zoneinfo import ZoneInfo
        return dt.datetime.now(ZoneInfo("Europe/London")).strftime("%Y-%m-%d %H:%M %Z")
    except Exception:
        return dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")


def copy_assets(out: Path) -> None:
    assets = out / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    copied = 0
    for src in ASSET_SOURCE_DIRS:
        if not src.exists():
            continue
        for p in src.rglob("*"):
            if not p.is_file():
                continue
            if any(part in {".git", "node_modules", "__pycache__"} for part in p.parts):
                continue
            rel = p.relative_to(src)
            dest = assets / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, dest)
            copied += 1
    if copied == 0:
        write_fallback_assets(assets)
    # Always make sure these compatibility names exist.
    if not (assets / "logo_web.svg").exists() and (assets / "aq26-logo.svg").exists():
        shutil.copy2(assets / "aq26-logo.svg", assets / "logo_web.svg")
    if not (assets / "aq26-logo.svg").exists() and (assets / "logo_web.svg").exists():
        shutil.copy2(assets / "logo_web.svg", assets / "aq26-logo.svg")
    if not (assets / "aq26-brand.css").exists():
        (assets / "aq26-brand.css").write_text(default_css(), encoding="utf-8")
    if not (assets / "aq26-brand.js").exists():
        (assets / "aq26-brand.js").write_text(default_js(), encoding="utf-8")
    (out / "site.webmanifest").write_text(json.dumps({"name": "AirQuality26 Environmental Intelligence Observatory", "short_name": "AQ26", "start_url": "/", "display": "standalone", "background_color": "#f5f8fc", "theme_color": "#0f4c81", "icons": []}, indent=2), encoding="utf-8")


def write_fallback_assets(assets: Path) -> None:
    (assets / "logo_web.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg" width="820" height="190" viewBox="0 0 820 190"><rect width="820" height="190" rx="28" fill="white"/><text x="40" y="82" font-family="Arial,sans-serif" font-size="54" font-weight="900" fill="#102033">AirQuality26</text><text x="42" y="124" font-family="Arial,sans-serif" font-size="24" font-weight="800" fill="#0f4c81">Environmental Intelligence Observatory</text><text x="42" y="154" font-family="Arial,sans-serif" font-size="18" font-weight="700" fill="#5f6b7a">SCC Nexus · AQ26</text></svg>', encoding="utf-8")
    shutil.copy2(assets / "logo_web.svg", assets / "aq26-logo.svg")
    (assets / "air_quality_web.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1400 760"><defs><linearGradient id="g" x1="0" x2="1"><stop stop-color="#071728"/><stop offset=".55" stop-color="#0f4c81"/><stop offset="1" stop-color="#2cb7df"/></linearGradient></defs><rect width="1400" height="760" fill="url(#g)"/><text x="90" y="210" fill="white" font-family="Arial,sans-serif" font-size="92" font-weight="900">AirQuality26</text><text x="96" y="278" fill="#dff7ff" font-family="Arial,sans-serif" font-size="36" font-weight="700">Environmental Intelligence Observatory</text></svg>', encoding="utf-8")


def default_css() -> str:
    return r'''
:root{--ink:#102033;--muted:#5f6b7a;--line:#d8e0ea;--blue:#0f4c81;--deep:#102033;--cyan:#0e7490;--bg:#f5f8fc;--card:#fff;--shadow:0 18px 45px rgba(16,32,51,.13)}*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;font-family:Inter,system-ui,-apple-system,Segoe UI,Arial,sans-serif;color:var(--ink);background:var(--bg);line-height:1.62}a{color:#0f4c81}img{max-width:100%;height:auto}.wrap{max-width:1180px;margin:0 auto;padding:0 22px}.site-header{background:rgba(255,255,255,.97);border-bottom:1px solid var(--line);position:sticky;top:0;z-index:50;backdrop-filter:blur(12px)}.bar{display:flex;align-items:center;justify-content:space-between;gap:24px;min-height:88px}.brand{display:flex;align-items:center;text-decoration:none;color:var(--ink);gap:12px}.brand img{height:68px;width:auto;display:block}.brand-title{display:none}.nav{display:flex;gap:10px;flex-wrap:wrap;align-items:center}.nav a{text-decoration:none;color:var(--ink);font-weight:800;font-size:.95rem;padding:10px 12px;border-radius:12px}.nav a:hover,.nav a[aria-current="page"]{background:#eef4fb}.menu{display:none;background:#fff;border:1px solid var(--line);border-radius:14px;padding:10px 13px;font-weight:900;box-shadow:0 4px 14px rgba(16,32,51,.06)}.hero{position:relative;min-height:430px;color:#fff;background:#0b2744;overflow:hidden}.hero-video{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;background:#0b2744 url('/assets/air_quality_web.svg') center/cover no-repeat;transform:scale(1.01)}.hero:after{content:"";position:absolute;inset:0;background:linear-gradient(90deg,rgba(8,25,45,.86),rgba(8,40,74,.58) 50%,rgba(132,28,68,.43));z-index:1}.hero-inner{position:relative;z-index:2;padding:88px 0 84px;max-width:900px}.badge{display:inline-flex;background:rgba(255,255,255,.17);border:1px solid rgba(255,255,255,.35);border-radius:999px;padding:7px 14px;font-weight:900;font-size:.82rem;text-transform:uppercase;letter-spacing:.045em}h1{font-size:clamp(2.5rem,6vw,5.2rem);line-height:1.02;margin:.55em 0 .25em;letter-spacing:-.055em}h2{font-size:clamp(1.55rem,3vw,2.35rem);line-height:1.12;letter-spacing:-.025em}.hero p{font-size:clamp(1.05rem,1.7vw,1.36rem);max-width:820px}.ticker{position:absolute;bottom:0;left:0;right:0;z-index:3;background:rgba(9,25,43,.96);color:#fff;white-space:nowrap;overflow:hidden;font-weight:900}.ticker span{display:inline-block;padding:12px 0;animation:aq26ticker 28s linear infinite}@keyframes aq26ticker{from{transform:translateX(100vw)}to{transform:translateX(-100%)}}main{padding:36px 0 54px}.grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:20px}.two{display:grid;grid-template-columns:minmax(0,2fr) minmax(280px,1fr);gap:22px}.card{background:var(--card);border:1px solid var(--line);border-radius:24px;padding:24px;box-shadow:var(--shadow)}.muted{color:var(--muted)}.kpi{font-size:2.1rem;font-weight:950;color:#0f4c81;line-height:1}.pill{display:inline-block;border-radius:999px;padding:4px 10px;font-size:.8rem;font-weight:900;background:#eef4fb}.pill.public{background:#ecfdf5;color:#166534}.pill.protected{background:#fff7ed;color:#7c2d12}.btnrow{display:flex;gap:12px;flex-wrap:wrap}.button{display:inline-flex;align-items:center;justify-content:center;background:#0f4c81;color:#fff;text-decoration:none;border-radius:14px;padding:12px 15px;font-weight:900}.button.secondary{background:#102033}.table-wrap{overflow:auto}table{width:100%;border-collapse:separate;border-spacing:0;background:#fff;border:1px solid var(--line);border-radius:18px;overflow:hidden}th,td{text-align:left;vertical-align:top;border-bottom:1px solid var(--line);padding:12px}th{background:#eaf2fb}footer{background:#102033;color:#fff;margin-top:26px;padding:34px 0 24px}.footgrid{display:grid;grid-template-columns:2fr 1fr 1fr;gap:24px}footer a{color:#dbeafe}.footer-logo img{height:60px}.copyright{border-top:1px solid rgba(255,255,255,.18);margin-top:26px;padding-top:20px;color:#e5eef8}@media(max-width:900px){.brand img{height:52px}.menu{display:block}.nav{display:none;width:100%;flex-direction:column;align-items:stretch;padding-bottom:16px}.nav.open{display:flex}.bar{flex-wrap:wrap;align-items:center}.nav a{padding:12px 14px}.hero{min-height:390px}.hero-inner{padding:66px 0 70px}.two,.grid,.footgrid{grid-template-columns:1fr}}@media(max-width:520px){.wrap{padding:0 16px}.brand img{height:44px}.hero{min-height:340px}.card{border-radius:20px;padding:18px}.bar{min-height:68px}}
'''.strip()


def default_js() -> str:
    return """(function(){const b=document.querySelector('[data-menu-button]'),n=document.querySelector('#nav');if(b&&n)b.addEventListener('click',()=>{const open=n.classList.toggle('open');b.setAttribute('aria-expanded',String(open));});})();"""


def analytics(ga: str) -> str:
    if not ga:
        return "<!-- GA disabled: set GA_MEASUREMENT_ID secret. -->"
    g = esc(ga)
    return f'<script async src="https://www.googletagmanager.com/gtag/js?id={g}"></script><script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments)}};gtag(\'js\',new Date());gtag(\'config\',\'{g}\');</script>'


def page_url(base: str, slug: str) -> str:
    return base.rstrip("/") + ("/" if slug == "index.html" else "/" + slug)


def nav_html(pages: list[tuple[str, str, str]], current: str, unredacted: bool) -> str:
    links = []
    for slug, label, _ in pages[:8]:
        href = "./" if slug == "index.html" else slug
        current_attr = ' aria-current="page"' if slug == current else ""
        links.append(f'<a href="{esc(href)}"{current_attr}>{esc(label)}</a>')
    if not unredacted:
        links.append('<a href="/unredacted/" rel="nofollow">Unredacted</a>')
    return "".join(links)


def jsonld(cfg: dict[str, Any], title: str, desc: str, slug: str, unredacted: bool) -> str:
    site = cfg.get("site", {})
    public_base = site.get("public_base_url", "https://sccairquality.com")
    base = site.get("unredacted_base_url", public_base.rstrip("/") + "/unredacted") if unredacted else public_base
    data = {"@context": "https://schema.org", "@type": "WebPage", "name": f"{title} · AQ26", "url": page_url(base, slug), "description": desc, "publisher": {"@type": "Organization", "name": site.get("organisation", "SCC Nexus")}, "inLanguage": "en-GB"}
    return '<script type="application/ld+json">' + json.dumps(data, ensure_ascii=False) + '</script>'


def head(cfg: dict[str, Any], slug: str, title: str, desc: str, unredacted: bool, ga: str, gsc: str) -> str:
    site = cfg.get("site", {})
    public_base = site.get("public_base_url", "https://sccairquality.com")
    base = site.get("unredacted_base_url", public_base.rstrip("/") + "/unredacted") if unredacted else public_base
    full_title = f"{title} · AQ26"
    url = page_url(base, slug)
    robots = "noindex,nofollow,noarchive" if unredacted else "index,follow"
    verify = f'<meta name="google-site-verification" content="{esc(gsc)}">' if (gsc and not unredacted) else ""
    return f'''<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{esc(full_title)}</title><meta name="description" content="{esc(desc)}"><meta name="robots" content="{robots}"><link rel="canonical" href="{esc(url)}"><meta property="og:title" content="{esc(full_title)}"><meta property="og:description" content="{esc(desc)}"><meta property="og:type" content="website"><meta property="og:url" content="{esc(url)}"><meta property="og:image" content="{esc(public_base.rstrip('/'))}/assets/air_quality_web.svg"><meta name="twitter:card" content="summary_large_image"><meta name="twitter:title" content="{esc(full_title)}"><meta name="twitter:description" content="{esc(desc)}"><meta name="twitter:image" content="{esc(public_base.rstrip('/'))}/assets/air_quality_web.svg">{jsonld(cfg,title,desc,slug,unredacted)}{verify}{analytics(ga) if not unredacted else ""}<link rel="stylesheet" href="/assets/aq26-brand.css">'''


def readiness_table() -> str:
    rows = "".join(f"<tr><td>{esc(k)}</td><td>{esc(v)}</td></tr>" for k, v in READINESS.items())
    return '<div class="table-wrap"><table><thead><tr><th>Gate</th><th>Status</th></tr></thead><tbody>' + rows + '</tbody></table></div>'


def body_for(slug: str, unredacted: bool) -> str:
    protected = '<span class="pill protected">Protected reviewer evidence</span>' if unredacted else '<span class="pill public">Public redaction gate active</span>'
    if slug == "index.html":
        return f'''<div class="two"><section class="card"><h2>Public-interest air-quality intelligence</h2><p>AQ26 tracks weekly public-interest evidence around Newhaven, incinerator context, monitoring records and historical source material. Public pages are deliberately redacted and cautious.</p><p>Use the public pages for readable summaries. Use the protected evidence area for reviewer traceability and unredacted evidence libraries.</p><div class="btnrow"><a class="button" href="/newhaven.html">Open Newhaven hub</a><a class="button secondary" href="/unredacted/" rel="nofollow">Protected evidence area</a></div></section><aside class="card"><h3>Evidence status</h3><p class="muted">Public summaries avoid exposing private reviewer material, direct protected links or credentials.</p><p>{protected}</p><p><span class="pill public">SEO and analytics active</span></p></aside></div><section class="grid" style="margin-top:22px"><div class="card"><div class="kpi">AQ26</div><strong>Evidence observatory</strong><p class="muted">Source records, readiness gates and weekly evidence tracking.</p></div><div class="card"><div class="kpi">0</div><strong>public leak target</strong><p class="muted">Protected files remain behind authentication.</p></div><div class="card"><div class="kpi">✓</div><strong>canonical deployment</strong><p class="muted">Single build path for public and protected pages.</p></div></section>'''
    if slug == "readiness.html":
        return '<section class="card"><h2>Readiness gates</h2><p>Public wording remains cautious until source, QA, comparator, meteorology and review gates support stronger interpretation.</p>' + readiness_table() + '</section>'
    if slug == "newhaven.html":
        return '<section class="card"><h2>Newhaven ERF / BV8067IL evidence hub</h2><p>This page organises public-safe Newhaven evidence candidates. It does not assert breach, health impact or causal attribution.</p><p><span class="pill public">Official-document focus</span> <span class="pill public">Claim lock active</span></p></section>'
    if slug == "downloads.html":
        return '<section class="card"><h2>Public-safe downloads</h2><p>Only redacted, public-safe summaries should appear here. Full evidence bundles and raw archives belong in the protected review area.</p></section>'
    return '<section class="card"><h2>' + esc(slug.replace('.html','').replace('-',' ').title()) + '</h2><p>' + esc(PUBLIC_CLAIM_NOTE) + '</p></section>'


def hero(title: str, desc: str, unredacted: bool) -> str:
    badge = "Protected site" if unredacted else "Public site"
    video = '<video class="hero-video" data-aq26-hero-video autoplay muted loop playsinline poster="/assets/air_quality_web.svg"><source src="/assets/desktop_banner_1.webm" type="video/webm"></video>'
    ticker = "Weekly AQ26 update • Newhaven ERF context • source records • redacted public output • protected reviewer evidence • SEO and analytics active • corrections welcome • "
    return f'<section class="hero">{video}<div class="wrap hero-inner"><span class="badge">{esc(badge)}</span><h1>{esc("AirQuality26" if title == "Home" else title)}</h1><p>{esc(desc)}</p></div><div class="ticker"><span>{esc(ticker)}</span></div></section>'


def footer(cfg: dict[str, Any]) -> str:
    email = cfg.get("site", {}).get("contact_email", "enquiries@sccairquality.com")
    return f'''<footer><div class="wrap footgrid"><div><span class="footer-logo"><img src="/assets/logo_web.svg" alt="SCC Nexus Air Quality Report"></span><br><strong>Environmental Intelligence Observatory · AQ26</strong><p>Weekly evidence tracking, public-interest transparency and protected reviewer material where appropriate.</p><p class="muted">Last rebuilt {esc(now_iso())}.</p></div><div><strong>Legal</strong><br><a href="/privacy.html">Privacy</a><br><a href="/terms.html">Terms</a><br><a href="/cookies.html">Cookies</a><br><a href="/accessibility.html">Accessibility</a></div><div><strong>Site</strong><br><a href="/contact.html">Contact</a><br><a href="mailto:{esc(email)}">{esc(email)}</a><br><a href="/sitemap.xml">Sitemap</a><br><a href="/unredacted/" rel="nofollow">Protected evidence</a></div></div><div class="wrap"><p class="copyright">© 2026 SCC Nexus · AQ26. All rights reserved. Corrections welcome.</p></div></footer>'''


def render_page(cfg: dict[str, Any], page: tuple[str, str, str], pages: list[tuple[str, str, str]], unredacted: bool, ga: str, gsc: str) -> str:
    slug, title, desc = page
    nav = nav_html(pages, slug, unredacted)
    return f'''<!doctype html><html lang="en-GB"><head>{head(cfg, slug, title, desc, unredacted, ga, gsc)}</head><body><header class="site-header"><div class="wrap bar"><a class="brand" href="/"><img src="/assets/logo_web.svg" alt="SCC Nexus Air Quality Report"><span class="brand-title">AQ26<small>Environmental Intelligence Observatory</small></span></a><button class="menu" data-menu-button aria-expanded="false" aria-controls="nav">☰ Menu</button><nav class="nav" id="nav">{nav}</nav></div></header>{hero(title, desc, unredacted)}<main class="wrap">{body_for(slug, unredacted)}</main>{footer(cfg)}<script src="/assets/aq26-brand.js"></script></body></html>'''


def write_site(out: Path, pages: list[tuple[str, str, str]], cfg: dict[str, Any], unredacted: bool, ga: str, gsc: str) -> None:
    copy_assets(out)
    for page in pages:
        (out / page[0]).write_text(render_page(cfg, page, pages, unredacted, ga, gsc), encoding="utf-8")
    downloads = out / "downloads"
    downloads.mkdir(exist_ok=True)
    (downloads / "README_PUBLIC_DOWNLOADS.txt").write_text("Public-safe downloads only. Full evidence ZIP bundles belong in the protected review area.\n", encoding="utf-8")
    if unredacted:
        (out / "robots.txt").write_text("User-agent: *\nDisallow: /\n", encoding="utf-8")
        (out / ".htaccess").write_text('AuthType Basic\nAuthName "AQ26 Protected Evidence"\nRequire valid-user\nOptions -Indexes\nHeader set X-Robots-Tag "noindex, nofollow, noarchive"\n', encoding="utf-8")
    else:
        base = cfg.get("site", {}).get("public_base_url", "https://sccairquality.com").rstrip("/")
        locs = [f"  <url><loc>{base + ('/' if slug == 'index.html' else '/' + slug)}</loc></url>" for slug, _, _ in pages]
        (out / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "\n".join(locs) + '\n</urlset>\n', encoding="utf-8")
        (out / "robots.txt").write_text(f"User-agent: *\nDisallow: /unredacted/\nDisallow: /test/\nSitemap: {base}/sitemap.xml\n", encoding="utf-8")
        data_dir = out / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        (data_dir / "publication_marker.json").write_text(json.dumps({"generated": now_iso(), "builder": "aq26_restored_branded_publication", "visual_system": "aq26-brand.css + video banner + logo_web.svg"}, indent=2), encoding="utf-8")


def main() -> int:
    cfg = load_config()
    ga = os.getenv("GA_MEASUREMENT_ID", "").strip()
    gsc = os.getenv("GOOGLE_SITE_VERIFICATION", "").strip()
    for folder in (PUBLIC, UNREDACTED, TEST):
        clean(folder)
    write_site(PUBLIC, PAGES, cfg, False, ga, gsc)
    write_site(UNREDACTED, UNREDACTED_PAGES, cfg, True, "", "")
    shutil.copytree(PUBLIC, TEST, dirs_exist_ok=True)
    (TEST / "robots.txt").write_text("User-agent: *\nDisallow: /\n", encoding="utf-8")
    print("Built restored branded AQ26 site_public, site_unredacted and site_test.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
