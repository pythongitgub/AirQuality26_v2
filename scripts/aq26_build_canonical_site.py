#!/usr/bin/env python3
"""Build one clean AQ26 public site and one protected unredacted site.

This replaces the accumulated patch-on-patch static folders with a single
canonical build so Hostinger is not left serving old template fragments.
"""
from __future__ import annotations

import datetime as dt
import html
import json
import os
import shutil
import zipfile
from pathlib import Path
from typing import Any
try:
    import yaml
except Exception as exc:  # pragma: no cover
    raise SystemExit("PyYAML is required. Add pyyaml to requirements.txt") from exc

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs" / "aq26_canonical_site.yml"
PUBLIC = ROOT / "site_public"
UNREDACTED = ROOT / "site_unredacted"
TEST = ROOT / "site_test"
ASSET_CANDIDATES = [ROOT / "website" / "assets", ROOT / "site_public" / "assets", ROOT / "assets"]

PUBLIC_CLAIM_NOTE = (
    "AQ26 publishes provenance-led screening evidence and operational readiness notes. "
    "It is not a regulatory determination, legal advice, medical advice or proof of causal attribution."
)

READINESS_DEFAULTS = {
    "redaction_ready": "ready",
    "provenance_ready": "ready",
    "source_records_ready": "ready",
    "ground_aq_ready": "context only",
    "wind_sector_ready": "not ready",
    "satellite_catalogue_ready": "ready when latest bundle present",
    "satellite_extraction_ready": "not ready",
    "cams_ready": "not ready unless CAMS_BASE_URL is configured",
    "external_submission_ready": "not ready",
}


def load_config() -> dict[str, Any]:
    with CONFIG_PATH.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def london_now() -> dt.datetime:
    try:
        from zoneinfo import ZoneInfo
        return dt.datetime.now(ZoneInfo("Europe/London"))
    except Exception:
        return dt.datetime.utcnow()


def clean_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def copy_assets(out: Path) -> None:
    assets = out / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    for src in ASSET_CANDIDATES:
        if src.exists():
            for p in src.rglob("*"):
                if p.is_file():
                    rel = p.relative_to(src)
                    dest = assets / rel
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    if not dest.exists():
                        shutil.copy2(p, dest)
    # Minimal fallbacks for missing repos.
    logo = assets / "logo_web.svg"
    if not logo.exists():
        logo.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 320"><rect width="320" height="320" rx="64" fill="#07111f"/><circle cx="160" cy="160" r="92" fill="#42c3ff"/><text x="160" y="178" text-anchor="middle" font-family="Arial" font-size="76" font-weight="800" fill="#07111f">AQ</text></svg>', encoding="utf-8")
    if not (assets / "favicon.svg").exists():
        shutil.copy2(logo, assets / "favicon.svg")
    if not (assets / "air_quality_web.svg").exists():
        (assets / "air_quality_web.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 600"><rect width="1200" height="600" fill="#07111f"/><path d="M0 420 C240 340 320 520 560 410 S910 270 1200 360 V600 H0Z" fill="#42c3ff" opacity=".55"/><circle cx="850" cy="170" r="110" fill="#6ee7b7" opacity=".7"/><text x="90" y="180" fill="white" font-family="Arial" font-size="68" font-weight="800">AQ26</text><text x="96" y="238" fill="#dff7ff" font-family="Arial" font-size="28">Environmental Intelligence Observatory</text></svg>', encoding="utf-8")


def css() -> str:
    return """
:root{--bg:#f5f8fc;--ink:#102033;--muted:#5f7088;--line:#d8e4f0;--brand:#0c4a6e;--blue:#42c3ff;--green:#10b981;--amber:#f59e0b;--red:#b42318;--card:#fff;--max:1180px}*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;font-family:Inter,ui-sans-serif,system-ui,-apple-system,Segoe UI,Arial,sans-serif;color:var(--ink);background:var(--bg);line-height:1.58}a{color:#075985}a:focus,button:focus{outline:3px solid var(--amber);outline-offset:3px}.skip{position:absolute;left:-999px;top:0;background:#fff;padding:.75rem;z-index:100}.skip:focus{left:1rem;top:1rem}.wrap{max-width:var(--max);margin:auto;padding:0 1rem}.site-header{position:sticky;top:0;z-index:20;background:rgba(255,255,255,.97);border-bottom:1px solid var(--line);backdrop-filter:blur(10px)}.bar{display:flex;align-items:center;gap:1rem;padding:.7rem 1rem}.brand{display:flex;align-items:center;gap:.7rem;text-decoration:none;color:var(--ink);font-weight:950}.brand img{width:58px;height:58px;object-fit:contain}.brand span{line-height:1.05}.brand small{display:block;color:var(--muted);font-weight:800}.menu{margin-left:auto;border:1px solid var(--line);background:#fff;border-radius:999px;padding:.6rem .85rem;font-weight:900}.nav{display:none;position:absolute;left:1rem;right:1rem;top:76px;background:#fff;border:1px solid var(--line);border-radius:18px;box-shadow:0 20px 45px rgba(16,32,51,.18);padding:.75rem}.nav[data-open=true]{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:.25rem}.nav a{padding:.7rem .8rem;border-radius:12px;text-decoration:none;color:var(--ink);font-weight:850}.nav a:hover,.nav a[aria-current=page]{background:#e6f6ff}.hero{background:radial-gradient(circle at 85% 18%,rgba(110,231,183,.32),transparent 28%),linear-gradient(135deg,#07111f,#0e314a 58%,#062a2f);color:#fff;overflow:hidden}.hero-grid{display:grid;grid-template-columns:1.1fr .9fr;gap:2rem;align-items:center;padding:4.2rem 1rem}.eyebrow{display:inline-flex;padding:.35rem .7rem;border:1px solid rgba(255,255,255,.35);border-radius:999px;font-weight:900;color:#dff7ff}.hero h1{font-size:clamp(2rem,5vw,4.7rem);line-height:1.03;margin:.9rem 0}.hero p{font-size:clamp(1.04rem,2vw,1.28rem);color:#d8e9f7}.hero-card{background:rgba(255,255,255,.11);border:1px solid rgba(255,255,255,.22);border-radius:28px;padding:1rem;box-shadow:0 25px 75px rgba(0,0,0,.28)}.hero-card img{width:100%;height:auto;border-radius:22px;background:#fff}.ticker{white-space:nowrap;overflow:hidden;border-top:1px solid rgba(255,255,255,.16);border-bottom:1px solid rgba(255,255,255,.16);background:rgba(0,0,0,.16)}.ticker span{display:inline-block;padding:.65rem 0;animation:ticker 28s linear infinite;color:#dff7ff;font-weight:800}@keyframes ticker{from{transform:translateX(100%)}to{transform:translateX(-100%)}}main{padding:2rem 0}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(245px,1fr));gap:1rem}.card{background:var(--card);border:1px solid var(--line);border-radius:22px;padding:1.15rem;box-shadow:0 10px 30px rgba(16,32,51,.07)}.card h2,.card h3{margin-top:0}.notice{border-left:6px solid var(--blue);background:#ecfeff}.warn{border-left:6px solid var(--amber);background:#fffbeb}.danger{border-left:6px solid var(--red);background:#fff1f2}.ok{border-left:6px solid var(--green);background:#ecfdf5}.button{display:inline-flex;align-items:center;justify-content:center;margin:.25rem .35rem .25rem 0;padding:.72rem 1rem;border-radius:999px;text-decoration:none;background:var(--brand);color:#fff;font-weight:900}.button.alt{background:#e0f2fe;color:#0c4a6e}.table-wrap{overflow:auto;border:1px solid var(--line);border-radius:18px;background:#fff}table{width:100%;border-collapse:collapse;min-width:680px}th,td{text-align:left;padding:.78rem;border-bottom:1px solid var(--line);vertical-align:top}th{background:#eef6ff}.muted{color:var(--muted)}.site-footer{background:#07111f;color:#dbeafe;margin-top:3rem}.footgrid{display:grid;grid-template-columns:1.15fr repeat(3,.7fr);gap:1.5rem;padding:2.4rem 1rem}.site-footer a{color:#bdefff}.copyright{border-top:1px solid rgba(255,255,255,.14);padding:1rem;color:#b7c9dc;text-align:center}.searchbox{width:100%;padding:1rem;border-radius:16px;border:1px solid var(--line);font-size:1rem;margin:.5rem 0 1rem}.pill{display:inline-flex;border:1px solid var(--line);border-radius:999px;padding:.35rem .6rem;background:#fff;font-weight:800;color:var(--muted)}@media(max-width:820px){.hero-grid{grid-template-columns:1fr;padding-top:3rem}.hero-card{display:none}.footgrid{grid-template-columns:1fr}.brand img{width:48px;height:48px}.brand small{font-size:.75rem}.nav{top:68px}.ticker span{animation-duration:18s}}
""".strip()


def js() -> str:
    return """
(function(){
  const btn=document.querySelector('[data-menu-button]');
  const nav=document.querySelector('#nav');
  if(btn&&nav){btn.addEventListener('click',()=>{const open=nav.getAttribute('data-open')==='true';nav.setAttribute('data-open',String(!open));btn.setAttribute('aria-expanded',String(!open));});}
  const y=document.querySelector('[data-year]'); if(y)y.textContent=new Date().getFullYear();
  const q=document.querySelector('[data-filter]'); if(q){q.addEventListener('input',()=>{const term=q.value.toLowerCase();document.querySelectorAll('[data-filter-item]').forEach(el=>{el.style.display=el.textContent.toLowerCase().includes(term)?'':'none';});});}
})();
""".strip()


def analytics(ga: str) -> str:
    if not ga:
        return "<!-- GA disabled: set GA_MEASUREMENT_ID secret. -->"
    safe = html.escape(ga, quote=True)
    return f'''<script async src="https://www.googletagmanager.com/gtag/js?id={safe}"></script><script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments);}}gtag('js',new Date());gtag('config','{safe}',{{anonymize_ip:true}});</script>'''


def page_url(base: str, slug: str) -> str:
    return base.rstrip("/") + ("/" if slug == "index.html" else "/" + slug)


def nav_html(pages: list[dict[str, Any]], current: str, base_prefix: str = "") -> str:
    links = []
    for p in pages:
        slug = p["slug"]
        cur = ' aria-current="page"' if slug == current else ""
        href = base_prefix + ("./" if slug == "index.html" else slug)
        links.append(f'<a href="{html.escape(href)}"{cur}>{html.escape(p.get("nav", p.get("title", slug)))}</a>')
    return "".join(links)


def head(cfg: dict[str, Any], page: dict[str, Any], *, unredacted: bool, ga: str, gsc: str) -> str:
    site = cfg["site"]
    base = site["unredacted_base_url"] if unredacted else site["public_base_url"]
    url = page_url(base, page["slug"])
    title = page["title"]
    desc = page["description"]
    robots = "noindex,nofollow,noarchive" if unredacted else "index,follow"
    verify = f'<meta name="google-site-verification" content="{html.escape(gsc, quote=True)}">' if gsc and not unredacted else ""
    jsonld = {
        "@context": "https://schema.org",
        "@type": "WebPage",
        "name": title,
        "url": url,
        "description": desc,
        "inLanguage": "en-GB",
        "publisher": {"@type": "Organization", "name": site["organisation"], "url": site["public_base_url"]},
    }
    if page["slug"] == "index.html" and not unredacted:
        jsonld = {"@context":"https://schema.org","@type":"WebSite","name":site["long_name"],"url":site["public_base_url"],"publisher":{"@type":"Organization","name":site["organisation"]},"inLanguage":"en-GB"}
    return f'''<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)} · AQ26</title><meta name="description" content="{html.escape(desc, quote=True)}"><meta name="robots" content="{robots}"><link rel="canonical" href="{html.escape(url, quote=True)}"><meta property="og:title" content="{html.escape(title, quote=True)} · AQ26"><meta property="og:description" content="{html.escape(desc, quote=True)}"><meta property="og:type" content="website"><meta property="og:url" content="{html.escape(url, quote=True)}"><meta property="og:site_name" content="AQ26"><meta name="twitter:card" content="summary_large_image"><meta name="twitter:title" content="{html.escape(title, quote=True)} · AQ26"><meta name="twitter:description" content="{html.escape(desc, quote=True)}">{verify}<link rel="icon" href="assets/favicon.svg" type="image/svg+xml"><link rel="manifest" href="site.webmanifest"><link rel="apple-touch-icon" href="assets/apple-touch-icon.png"><link rel="stylesheet" href="assets/aq26-canonical.css"><script type="application/ld+json">{json.dumps(jsonld, ensure_ascii=False)}</script>{analytics(ga if not unredacted else "")}'''


def footer(cfg: dict[str, Any], *, unredacted: bool) -> str:
    email = cfg["site"].get("contact_email", "enquiries@sccairquality.com")
    protected = '<a href="/unredacted/" rel="nofollow">Protected evidence</a>' if not unredacted else '<a href="/">Public redacted site</a>'
    return f'''<footer class="site-footer"><div class="wrap footgrid"><div><strong>Environmental Intelligence Observatory · AQ26</strong><p>Weekly evidence tracking, provenance-led public transparency and protected reviewer material where appropriate.</p><p class="muted">{html.escape(PUBLIC_CLAIM_NOTE)}</p></div><div><strong>Site</strong><br><a href="/">Home</a><br><a href="/newhaven.html">Newhaven</a><br><a href="/weekly-update.html">Weekly update</a><br>{protected}</div><div><strong>Legal</strong><br><a href="/privacy.html">Privacy</a><br><a href="/terms.html">Terms</a><br><a href="/cookies.html">Cookies</a><br><a href="/accessibility.html">Accessibility</a></div><div><strong>Contact</strong><br><a href="/contact.html">Corrections</a><br><a href="mailto:{html.escape(email)}">{html.escape(email)}</a><br><a href="/sitemap.xml">Sitemap</a></div></div><div class="copyright">© <span data-year></span> SCC Nexus · AQ26. All rights reserved. Corrections welcome.</div></footer>'''


def hero(page: dict[str, Any], *, unredacted: bool) -> str:
    label = "Protected reviewer area" if unredacted else "Public redacted site"
    return f'''<section class="hero"><div class="wrap hero-grid"><div><span class="eyebrow">{label}</span><h1>{html.escape(page["title"])}</h1><p>{html.escape(page["description"])}</p><p><span class="pill">Provenance-first</span> <span class="pill">Redaction gates</span> <span class="pill">Cautious wording</span></p></div><div class="hero-card"><img src="assets/air_quality_web.svg" alt="AQ26 environmental intelligence visual"></div></div><div class="ticker"><span>Weekly AQ26 update • Newhaven ERF context • source records • redacted public output • protected reviewer evidence • no causal attribution without gates • corrections welcome • </span></div></section>'''


def load_json_candidates() -> dict[str, Any]:
    candidates: dict[str, Any] = {}
    for name in ["latest_summary.json", "latest_live_summary.json", "science_validation_latest.json", "latest_backfill_summary.json"]:
        for base in [ROOT / "site_public" / "data", ROOT / "data", ROOT / "outputs"]:
            p = base / name
            if p.exists():
                try:
                    candidates[name] = json.loads(p.read_text(encoding="utf-8"))
                except Exception:
                    candidates[name] = {"_error": "Could not parse"}
                break
    return candidates


def readiness_table(data: dict[str, Any]) -> str:
    rows = []
    latest = data.get("latest_summary.json", {}) if isinstance(data.get("latest_summary.json"), dict) else {}
    gates = latest.get("readiness_gates") or latest.get("gates") or {}
    merged = dict(READINESS_DEFAULTS)
    if isinstance(gates, dict):
        for k, v in gates.items():
            merged[str(k)] = str(v).lower() if isinstance(v, bool) else str(v)
    for k, v in merged.items():
        rows.append(f"<tr><td>{html.escape(k.replace('_',' '))}</td><td>{html.escape(v)}</td></tr>")
    return '<div class="table-wrap"><table><thead><tr><th>Gate</th><th>Status</th></tr></thead><tbody>' + ''.join(rows) + '</tbody></table></div>'


def public_body(page: dict[str, Any], cfg: dict[str, Any], data: dict[str, Any]) -> str:
    slug = page["slug"]
    if slug == "index.html":
        return f'''<section class="grid"><article class="card ok"><h2>Current purpose</h2><p>AQ26 organises public, provider, satellite-catalogue and regulatory context evidence around Newhaven ERF and wider incinerator review.</p></article><article class="card warn"><h2>Publication boundary</h2><p>{html.escape(PUBLIC_CLAIM_NOTE)}</p></article><article class="card"><h2>Protected review</h2><p>Detailed operational diagnostics and unredacted reviewer material are held behind HTTP Basic Auth.</p><p><a class="button alt" href="/unredacted/" rel="nofollow">Protected evidence area</a></p></article></section><section class="card"><h2>Evidence readiness</h2>{readiness_table(data)}</section>'''
    if slug == "readiness.html":
        return f'<section class="card"><h2>Readiness gates</h2><p>These gates prevent AQ26 public wording from overstating evidence before extraction, QA, wind-sector and review steps are complete.</p>{readiness_table(data)}</section>'
    if slug == "newhaven.html":
        return '''<section class="grid"><article class="card"><h2>Newhaven ERF</h2><p>Newhaven Energy Recovery Facility and permit reference BV8067IL are treated as a controlled reference focus for evidence gathering, not as a pre-judged cause of measured impacts.</p></article><article class="card warn"><h2>Interpretation rule</h2><p>Nearby or regional air-quality stations must be labelled as target proxy, control, background or not-target. No station should be presented as a direct stack-adjacent measurement unless its location and role are verified.</p></article><article class="card"><h2>Next analytical gate</h2><p>Wind direction, wind speed, upwind/downwind classification and pollutant QA are required before impact language is permitted.</p></article></section>'''
    if slug == "weekly-update.html":
        return '''<section class="grid"><article class="card ok"><h2>Weekly status</h2><p>The weekly publication should expose redacted summary status, source counts and readiness gates only.</p></article><article class="card warn"><h2>Known limitation</h2><p>Satellite catalogue discovery is not the same as pollutant extraction. CAMS and Earthdata readiness must remain separate from external-submission readiness.</p></article></section>'''
    if slug == "downloads.html":
        links = []
        dl = PUBLIC / "downloads"
        for p in sorted(dl.glob("*")) if dl.exists() else []:
            if p.name.lower().endswith((".pdf", ".md", ".txt", ".json")) or "public" in p.name.lower():
                links.append(f'<li><a href="downloads/{html.escape(p.name)}">{html.escape(p.name)}</a></li>')
        if not links:
            links.append('<li>No public-safe downloads found in this build.</li>')
        return '<section class="card"><h2>Public downloads</h2><p>Full unredacted ZIP evidence bundles are not published here.</p><ul>' + ''.join(links) + '</ul></section>'
    if slug == "methodology.html":
        return '''<section class="grid"><article class="card"><h2>Method</h2><p>AQ26 separates source discovery, provenance, redaction, readiness gates, contextual measurement, satellite catalogue discovery, satellite extraction and external submission readiness.</p></article><article class="card warn"><h2>No-attribution rule</h2><p>No public page may say that Newhaven ERF caused a measured impact unless wind-sector, source, QA, control-site and review gates pass.</p></article><article class="card"><h2>Official filings</h2><p>Official search results must be filtered by result title, URL, snippet and document text, not inflated merely because a search query contained Newhaven terms.</p></article></section>'''
    if slug in {"privacy.html", "terms.html", "cookies.html", "accessibility.html", "contact.html"}:
        text = {
            "privacy.html":"AQ26 processes only the minimum information needed to run this website, protect the unredacted area, respond to corrections and understand aggregate site performance.",
            "terms.html":PUBLIC_CLAIM_NOTE + " Users should check original sources and should not treat screening outputs as final regulatory findings.",
            "cookies.html":"AQ26 may use essential access-control cookies and privacy-conscious analytics when GA_MEASUREMENT_ID is configured.",
            "accessibility.html":"AQ26 aims to use semantic HTML, visible focus states, responsive layouts, readable contrast and clear correction routes.",
            "contact.html":f'For corrections, source updates or accessibility issues, email <a href="mailto:{html.escape(cfg["site"].get("contact_email","enquiries@sccairquality.com"))}">{html.escape(cfg["site"].get("contact_email","enquiries@sccairquality.com"))}</a>. Include the page URL and supporting public source material.'
        }[slug]
        return f'<section class="card"><h2>{html.escape(page["title"])}</h2><p>{text}</p></section>'
    return f'<section class="grid"><article class="card"><h2>{html.escape(page["title"])}</h2><p>{html.escape(page["description"])}</p></article><article class="card warn"><h2>Public wording guard</h2><p>{html.escape(PUBLIC_CLAIM_NOTE)}</p></article></section>'


def unredacted_body(page: dict[str, Any]) -> str:
    slug = page["slug"]
    if slug in {"downloads.html", "evidence.html"}:
        links = []
        dl = UNREDACTED / "downloads"
        for p in sorted(dl.glob("*")) if dl.exists() else []:
            links.append(f'<li><a href="downloads/{html.escape(p.name)}">{html.escape(p.name)}</a></li>')
        if not links:
            links.append('<li>No protected downloads found in this build.</li>')
        return '<section class="card"><h2>Protected downloads</h2><p>This area is blocked from indexing and requires HTTP Basic Auth.</p><ul>' + ''.join(links) + '</ul></section>'
    return f'<section class="grid"><article class="card danger"><h2>Protected review material</h2><p>{html.escape(page["description"])}</p><p>Do not redistribute without permission. No public causal attribution should be copied from this area unless the relevant gates pass.</p></article><article class="card"><h2>Reviewer checklist</h2><ul><li>Check source provenance.</li><li>Check redaction status.</li><li>Check official filing relevance.</li><li>Check target/control/wind-sector classification.</li></ul></article></section>'


def render_page(cfg: dict[str, Any], page: dict[str, Any], pages: list[dict[str, Any]], *, unredacted: bool, data: dict[str, Any], ga: str, gsc: str) -> str:
    body = unredacted_body(page) if unredacted else public_body(page, cfg, data)
    return f'''<!doctype html><html lang="en-GB"><head>{head(cfg,page,unredacted=unredacted,ga=ga,gsc=gsc)}</head><body><a class="skip" href="#main">Skip to content</a><header class="site-header"><div class="wrap bar"><a class="brand" href="{'/unredacted/' if unredacted else '/'}"><img src="assets/logo_web.svg" alt="AQ26 logo"><span>AQ26<small>{'Protected evidence review' if unredacted else 'Environmental Intelligence Observatory'}</small></span></a><button class="menu" data-menu-button aria-expanded="false" aria-controls="nav">☰ Menu</button><nav id="nav" class="nav" data-open="false">{nav_html(pages,page['slug'])}</nav></div></header>{hero(page,unredacted=unredacted)}<main id="main" class="wrap">{body}<section class="card"><h2>Page directory</h2><input class="searchbox" data-filter placeholder="Filter AQ26 pages"><div class="grid">{''.join(f'<article class="card" data-filter-item><h3><a href="{html.escape(p["slug"])}">{html.escape(p.get("nav",p["title"]))}</a></h3><p>{html.escape(p["description"])}</p></article>' for p in pages)}</div></section></main>{footer(cfg,unredacted=unredacted)}<script src="assets/aq26-canonical.js"></script></body></html>'''


def write_manifest(out: Path, cfg: dict[str, Any], *, unredacted: bool) -> None:
    site = cfg["site"]
    manifest = {
        "name": "AQ26",
        "short_name": "AQ26",
        "start_url": "/unredacted/" if unredacted else "/",
        "display": "standalone",
        "background_color": "#f5f8fc",
        "theme_color": "#0c4a6e",
        "icons": [
            {"src":"assets/android-chrome-192x192.png","sizes":"192x192","type":"image/png"},
            {"src":"assets/android-chrome-512x512.png","sizes":"512x512","type":"image/png"},
        ],
    }
    (out / "site.webmanifest").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def write_static(cfg: dict[str, Any], out: Path, pages: list[dict[str, Any]], *, unredacted: bool, data: dict[str, Any], ga: str, gsc: str) -> None:
    copy_assets(out)
    (out / "assets" / "aq26-canonical.css").write_text(css(), encoding="utf-8")
    (out / "assets" / "aq26-canonical.js").write_text(js(), encoding="utf-8")
    write_manifest(out, cfg, unredacted=unredacted)
    for page in pages:
        (out / page["slug"]).write_text(render_page(cfg,page,pages,unredacted=unredacted,data=data,ga=ga,gsc=gsc), encoding="utf-8")
    nf = {"slug":"404.html","title":"Page not found","nav":"404","description":"The requested AQ26 page could not be found."}
    (out / "404.html").write_text(render_page(cfg,nf,pages,unredacted=unredacted,data=data,ga=ga,gsc=gsc), encoding="utf-8")
    if unredacted:
        (out / "robots.txt").write_text("User-agent: *\nDisallow: /\n", encoding="utf-8")
        (out / ".htaccess").write_text('''AuthType Basic\nAuthName "AQ26 Protected Evidence"\nAuthBasicProvider file\nAuthUserFile /home/u288464186/.aq26_auth/.htpasswd\nRequire valid-user\nOptions -Indexes\n<FilesMatch "^\\.ht">\n  Require all denied\n</FilesMatch>\nHeader set X-Robots-Tag "noindex, nofollow, noarchive"\n''', encoding="utf-8")
    else:
        base = cfg["site"]["public_base_url"].rstrip("/")
        today = london_now().date().isoformat()
        sm = ['<?xml version="1.0" encoding="UTF-8"?>','<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
        for p in pages:
            sm.append(f'<url><loc>{html.escape(page_url(base,p["slug"]))}</loc><lastmod>{today}</lastmod><changefreq>weekly</changefreq><priority>{html.escape(str(p.get("priority","0.6")))}</priority></url>')
        sm.append('</urlset>')
        (out / "sitemap.xml").write_text("\n".join(sm), encoding="utf-8")
        (out / "sitemap.txt").write_text("\n".join(page_url(base,p["slug"]) for p in pages), encoding="utf-8")
        (out / "robots.txt").write_text("User-agent: *\nAllow: /\nDisallow: /unredacted/\nDisallow: /test/\nDisallow: /git-test/\nSitemap: https://sccairquality.com/sitemap.xml\n", encoding="utf-8")


def copy_downloads() -> None:
    for d in [PUBLIC / "downloads", UNREDACTED / "downloads"]:
        d.mkdir(parents=True, exist_ok=True)
    source_dirs = [ROOT / "outputs" / "reports", ROOT / "outputs" / "evidence", ROOT / "site_public" / "downloads", ROOT / "site_unredacted" / "downloads"]
    copied = set()
    for srcdir in source_dirs:
        if not srcdir.exists():
            continue
        for p in srcdir.glob("*"):
            if not p.is_file() or p.name in copied:
                continue
            lower = p.name.lower()
            # Full evidence zips only in protected area.
            if lower.endswith(".zip") and "evidence" in lower and "public" not in lower:
                shutil.copy2(p, UNREDACTED / "downloads" / p.name)
            elif lower.endswith((".pdf", ".md", ".txt", ".json")):
                shutil.copy2(p, PUBLIC / "downloads" / p.name)
                shutil.copy2(p, UNREDACTED / "downloads" / p.name)
            copied.add(p.name)


def main() -> int:
    cfg = load_config()
    data = load_json_candidates()
    ga = os.getenv("GA_MEASUREMENT_ID", "").strip()
    gsc = os.getenv("GOOGLE_SITE_VERIFICATION", "").strip()
    for path in [PUBLIC, UNREDACTED, TEST]:
        clean_dir(path)
    # Copy downloads before rendering download pages.
    copy_downloads()
    write_static(cfg, PUBLIC, cfg["public_pages"], unredacted=False, data=data, ga=ga, gsc=gsc)
    write_static(cfg, UNREDACTED, cfg["unredacted_pages"], unredacted=True, data=data, ga=ga, gsc=gsc)
    shutil.copytree(PUBLIC, TEST, dirs_exist_ok=True)
    (PUBLIC / "AQ26_CANONICAL_BUILD.json").write_text(json.dumps({"built_at": london_now().isoformat(), "public_pages": len(cfg["public_pages"]), "unredacted_pages": len(cfg["unredacted_pages"]), "ga_configured": bool(ga), "gsc_configured": bool(gsc)}, indent=2), encoding="utf-8")
    print("Built clean AQ26 canonical site_public, site_unredacted and site_test.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
