#!/usr/bin/env python3
"""Build AQ26 publication-grade public, protected and test sites.

Single source of truth for formatting, header logo, pages, banners, SEO,
Google Analytics hooks, sitemap/robots and public/protected separation.
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
ASSET_CANDIDATES = [ROOT / "website" / "assets", ROOT / "assets"]

PUBLIC_CLAIM_NOTE = (
    "AQ26 publishes provenance-led environmental evidence screening and operational readiness notes. "
    "It is not a regulatory determination, legal advice, medical advice, laboratory certification or proof of causal attribution."
)

PAGES = [
    ("index.html", "Home", "AQ26 environmental intelligence and evidence observatory for Newhaven and surrounding communities."),
    ("newhaven.html", "Newhaven ERF", "Public redacted Newhaven ERF / BV8067IL evidence hub and review status."),
    ("weekly-update.html", "Weekly Update", "Latest public weekly AQ26 evidence summary and publication status."),
    ("source-records.html", "Source Records", "Public-safe source records, provenance notes and evidence categories."),
    ("readiness.html", "Readiness Gates", "Evidence readiness, QA gates and publication boundaries."),
    ("official-filings.html", "Official Filings", "Official-document candidates and relevance controls for Newhaven/BV8067IL."),
    ("monitoring.html", "Monitoring and Meteorology", "Ground monitoring, station role and meteorology context."),
    ("satellite.html", "Satellite and Models", "Satellite catalogue, Earthdata, CAMS and model-readiness status."),
    ("methodology.html", "Methodology", "AQ26 methods, caveats, redaction policy and review workflow."),
    ("downloads.html", "Downloads", "Public-safe downloads and audit outputs."),
    ("archive.html", "Archive", "Historical weekly archive and backfill status."),
    ("about.html", "About", "About AQ26 and the publication workflow."),
    ("privacy.html", "Privacy", "Privacy policy for AQ26."),
    ("terms.html", "Terms", "Terms of use for AQ26."),
    ("cookies.html", "Cookies", "Cookie and analytics notice."),
    ("accessibility.html", "Accessibility", "Accessibility statement."),
    ("contact.html", "Contact", "Contact, corrections and source-update enquiries."),
]

UNREDACTED_PAGES = [
    ("index.html", "Protected Review Home", "Protected AQ26 reviewer evidence area."),
    ("evidence.html", "Evidence Library", "Protected source-led evidence library and controlled-review index."),
    ("source-records.html", "Unredacted Source Records", "Protected source records and review traceability."),
    ("readiness.html", "Protected Readiness", "Protected readiness gates and internal review status."),
    ("downloads.html", "Protected Downloads", "Protected evidence downloads and review material."),
    ("methodology.html", "Protected Methodology", "Internal methodology, limitations and reviewer controls."),
    ("contact.html", "Protected Contact", "Reviewer contact and correction route."),
]

READINESS_DEFAULTS = {
    "redaction_ready": "ready",
    "provenance_ready": "ready",
    "source_records_ready": "ready",
    "official_filing_relevance_ready": "needs strict filtering",
    "ground_aq_ready": "context only",
    "monitor_role_classification_ready": "required before interpretation",
    "wind_sector_ready": "not ready",
    "satellite_catalogue_ready": "ready when latest bundle present",
    "satellite_extraction_ready": "not ready",
    "earthdata_cmr_ready": "partial / parser must count granules",
    "cams_ready": "not ready unless endpoint configured",
    "external_submission_ready": "not ready",
}


def now() -> dt.datetime:
    try:
        from zoneinfo import ZoneInfo
        return dt.datetime.now(ZoneInfo("Europe/London"))
    except Exception:
        return dt.datetime.utcnow()


def load_config() -> dict[str, Any]:
    if CONFIG_PATH.exists():
        return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
    return {}


def clean(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return None


def load_data() -> dict[str, Any]:
    names = [
        "latest_summary.json", "latest_live_summary.json", "LATEST_WEEKLYV2.json",
        "science_validation_latest.json", "drive_forensic_summary.json",
        "AQ26_WEEKLYV2_SITE_V3_VALIDATION.json", "AQ26_WEEKLYV2_SCIENCE_V33_VALIDATION.json",
    ]
    bases = [ROOT / "site_public" / "data", ROOT / "data", ROOT / "outputs", ROOT / "outputs" / "99_integrity", ROOT / "outputs" / "drive_forensic_audit"]
    out: dict[str, Any] = {}
    for name in names:
        for base in bases:
            value = read_json(base / name)
            if value is not None:
                out[name] = value
                break
    return out


def write_assets(out: Path) -> None:
    assets = out / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    for src in ASSET_CANDIDATES:
        if src.exists():
            for p in src.rglob("*"):
                if p.is_file() and not any(part in {".git", "node_modules", "__pycache__"} for part in p.parts):
                    rel = p.relative_to(src)
                    dest = assets / rel
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    if not dest.exists():
                        shutil.copy2(p, dest)

    # Force a clean horizontal wordmark for the header. This prevents the old square
    # icon being used as the main header logo.
    wordmark = assets / "aq26-logo.svg"
    wordmark.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="820" height="190" viewBox="0 0 820 190" role="img" aria-label="AirQuality26 Environmental Intelligence Observatory">'
        '<rect width="820" height="190" rx="28" fill="white"/>'
        '<g transform="translate(28 29)"><path d="M62 7 116 38 116 100 62 131 8 100 8 38Z" fill="none" stroke="#0f4c81" stroke-width="16" stroke-linejoin="round"/>'
        '<path d="M35 94 68 112 98 94M31 45 64 63 95 45" fill="none" stroke="#0e7490" stroke-width="13" stroke-linecap="round"/><path d="M62 12v114" stroke="#38bdf8" stroke-width="10" stroke-linecap="round"/></g>'
        '<text x="174" y="78" font-family="Inter,Arial,sans-serif" font-size="52" font-weight="900" fill="#0d1b2a">AirQuality26</text>'
        '<text x="177" y="119" font-family="Inter,Arial,sans-serif" font-size="23" font-weight="800" fill="#0f4c81">Environmental Intelligence Observatory</text>'
        '<text x="178" y="151" font-family="Inter,Arial,sans-serif" font-size="18" font-weight="700" fill="#64748b">AQ26 · provenance-led air-quality evidence</text></svg>',
        encoding="utf-8",
    )
    # Backwards compatibility: old templates pointed at logo_web.svg.
    shutil.copy2(wordmark, assets / "logo_web.svg")

    favicon = assets / "favicon.svg"
    favicon.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 320 320"><rect width="320" height="320" rx="64" fill="#061522"/><path d="M160 42 258 99v122l-98 57-98-57V99Z" fill="none" stroke="#38bdf8" stroke-width="28" stroke-linejoin="round"/><path d="M103 199 164 232 219 199M96 113 159 146 218 113" fill="none" stroke="#5eead4" stroke-width="22" stroke-linecap="round"/><path d="M160 50v220" stroke="#fff" stroke-width="16" stroke-linecap="round" opacity=".85"/></svg>',
        encoding="utf-8",
    )
    if not (assets / "apple-touch-icon.png").exists():
        (assets / "apple-touch-icon.png").write_bytes(b"")

    hero = assets / "air_quality_web.svg"
    hero.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1400 760"><defs><linearGradient id="g" x1="0" x2="1"><stop stop-color="#061522"/><stop offset=".55" stop-color="#0c4a6e"/><stop offset="1" stop-color="#0f766e"/></linearGradient><radialGradient id="r" cx="78%" cy="18%" r="55%"><stop stop-color="#38bdf8" stop-opacity=".5"/><stop offset="1" stop-color="#38bdf8" stop-opacity="0"/></radialGradient></defs><rect width="1400" height="760" fill="url(#g)"/><rect width="1400" height="760" fill="url(#r)"/><path d="M0 545 C210 395 420 610 650 485 S1030 360 1400 455 V760 H0Z" fill="#5eead4" opacity=".28"/><circle cx="1020" cy="190" r="118" fill="#7dd3fc" opacity=".22"/><text x="92" y="190" fill="white" font-family="Arial,sans-serif" font-size="88" font-weight="900">AirQuality26</text><text x="98" y="254" fill="#dff7ff" font-family="Arial,sans-serif" font-size="35" font-weight="700">Environmental Intelligence Observatory</text><text x="100" y="312" fill="#cbd5e1" font-family="Arial,sans-serif" font-size="26">Public-interest evidence · cautious claims · protected reviewer traceability</text></svg>',
        encoding="utf-8",
    )

    (assets / "aq26-canonical.css").write_text(css(), encoding="utf-8")
    (assets / "aq26-canonical.js").write_text(js(), encoding="utf-8")
    manifest = {
        "name": "AirQuality26 Environmental Intelligence Observatory",
        "short_name": "AQ26",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#f4f8fb",
        "theme_color": "#06364d",
        "icons": [],
    }
    (out / "site.webmanifest").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def css() -> str:
    return r'''
:root{--bg:#f4f8fb;--ink:#0d1b2a;--muted:#5d6d7e;--line:#d9e5ef;--brand:#06364d;--blue:#0ea5e9;--green:#059669;--amber:#d97706;--red:#b42318;--card:#fff;--max:1210px}*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;font-family:Inter,ui-sans-serif,system-ui,-apple-system,Segoe UI,Arial,sans-serif;color:var(--ink);background:var(--bg);line-height:1.58;overflow-x:hidden}a{color:#075985}a:focus,button:focus,input:focus{outline:3px solid #f59e0b;outline-offset:3px}.skip{position:absolute;left:-999px}.skip:focus{left:1rem;top:1rem;background:#fff;padding:.75rem;z-index:100}.wrap{max-width:var(--max);margin:auto;padding:0 1rem}.site-header{position:sticky;top:0;z-index:20;background:rgba(255,255,255,.98);border-bottom:1px solid var(--line);backdrop-filter:blur(10px)}.bar{display:flex;align-items:center;gap:1rem;padding:.48rem 1rem}.brand{display:flex;align-items:center;text-decoration:none;color:var(--ink);font-weight:950;min-width:0}.brand img{display:block;width:min(335px,58vw);height:76px;object-fit:contain;object-position:left center}.brand span{position:absolute;left:-9999px}.menu{margin-left:auto;border:1px solid var(--line);background:#fff;border-radius:999px;padding:.62rem .88rem;font-weight:950;box-shadow:0 7px 24px rgba(16,32,51,.08)}.nav{display:none;position:absolute;left:1rem;right:1rem;top:80px;background:#fff;border:1px solid var(--line);border-radius:18px;box-shadow:0 20px 45px rgba(16,32,51,.18);padding:.75rem}.nav[data-open=true]{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:.25rem}.nav a{padding:.68rem .78rem;border-radius:12px;text-decoration:none;color:var(--ink);font-weight:850}.nav a:hover,.nav a[aria-current=page]{background:#e0f2fe}.hero{background:radial-gradient(circle at 82% 15%,rgba(103,232,249,.33),transparent 28%),linear-gradient(135deg,#061522,#0a3550 56%,#053f3a);color:#fff;overflow:hidden}.hero-grid{display:grid;grid-template-columns:1.12fr .88fr;gap:2rem;align-items:center;padding:4.4rem 1rem}.eyebrow{display:inline-flex;padding:.36rem .7rem;border:1px solid rgba(255,255,255,.38);border-radius:999px;font-weight:950;color:#dff7ff}.hero h1{font-size:clamp(2.05rem,5vw,4.65rem);line-height:1.03;margin:.9rem 0}.hero p{font-size:clamp(1.04rem,2vw,1.28rem);color:#d8e9f7}.hero-card{background:rgba(255,255,255,.11);border:1px solid rgba(255,255,255,.22);border-radius:30px;padding:1rem;box-shadow:0 25px 75px rgba(0,0,0,.30)}.hero-card img{width:100%;height:auto;border-radius:23px;background:#fff}.ticker{white-space:nowrap;overflow:hidden;border-top:1px solid rgba(255,255,255,.16);border-bottom:1px solid rgba(255,255,255,.16);background:rgba(0,0,0,.16)}.ticker span{display:inline-block;padding:.68rem 0;animation:ticker 32s linear infinite;color:#dff7ff;font-weight:850}@keyframes ticker{from{transform:translateX(35%)}to{transform:translateX(-100%)}}main{padding:2rem 0}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(255px,1fr));gap:1rem}.grid.two{grid-template-columns:repeat(auto-fit,minmax(340px,1fr))}.card{background:var(--card);border:1px solid var(--line);border-radius:22px;padding:1.18rem;box-shadow:0 10px 30px rgba(16,32,51,.07)}.card h2,.card h3{margin-top:0}.warn{border-left:6px solid var(--amber);background:#fffbeb}.danger{border-left:6px solid var(--red);background:#fff1f2}.ok{border-left:6px solid var(--green);background:#ecfdf5}.button{display:inline-flex;margin:.25rem .35rem .25rem 0;padding:.72rem 1rem;border-radius:999px;text-decoration:none;background:var(--brand);color:#fff;font-weight:950}.button.alt{background:#e0f2fe;color:#0c4a6e}.table-wrap{overflow:auto;border:1px solid var(--line);border-radius:18px;background:#fff}table{width:100%;border-collapse:collapse;min-width:720px}th,td{text-align:left;padding:.78rem;border-bottom:1px solid var(--line);vertical-align:top}th{background:#eef6ff}.muted{color:var(--muted)}.site-footer{background:#07111f;color:#dbeafe;margin-top:3rem}.footgrid{display:grid;grid-template-columns:1.15fr repeat(3,.7fr);gap:1.5rem;padding:2.4rem 1rem}.site-footer a{color:#bdefff}.copyright{border-top:1px solid rgba(255,255,255,.14);padding:1rem;color:#b7c9dc;text-align:center}.searchbox{width:100%;padding:1rem;border-radius:16px;border:1px solid var(--line);font-size:1rem;margin:.5rem 0 1rem}.kpi{font-size:2rem;font-weight:950;color:#06364d}.small{font-size:.92rem}.status-ready{color:#047857;font-weight:900}.status-partial{color:#b45309;font-weight:900}.status-not{color:#b42318;font-weight:900}@media(max-width:820px){.hero-grid{grid-template-columns:1fr;padding-top:3rem}.hero-card{display:none}.footgrid{grid-template-columns:1fr}.bar{padding:.44rem .8rem}.brand img{width:min(250px,60vw);height:62px}.menu{padding:.56rem .72rem}.nav{top:66px}.grid.two{grid-template-columns:1fr}table{min-width:620px}}
'''.strip()


def js() -> str:
    return """(function(){const b=document.querySelector('[data-menu-button]'),n=document.querySelector('#nav');if(b&&n)b.addEventListener('click',()=>{const o=n.getAttribute('data-open')==='true';n.setAttribute('data-open',String(!o));b.setAttribute('aria-expanded',String(!o));});const y=document.querySelector('[data-year]');if(y)y.textContent=new Date().getFullYear();const q=document.querySelector('[data-filter]');if(q)q.addEventListener('input',()=>{const t=q.value.toLowerCase();document.querySelectorAll('[data-filter-item]').forEach(e=>{e.style.display=e.textContent.toLowerCase().includes(t)?'':'none'});});})();"""


def analytics(ga: str) -> str:
    if not ga:
        return "<!-- GA disabled: set GA_MEASUREMENT_ID secret. -->"
    g = html.escape(ga, quote=True)
    return f'<script async src="https://www.googletagmanager.com/gtag/js?id={g}"></script><script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments);}}gtag("js",new Date());gtag("config","{g}",{{anonymize_ip:true}});</script>'


def page_url(base: str, slug: str) -> str:
    return base.rstrip("/") + ("/" if slug == "index.html" else "/" + slug)


def nav_html(pages: list[tuple[str, str, str]], current: str, prefix: str = "") -> str:
    return "".join(
        f'<a href="{html.escape(prefix + ("./" if slug == "index.html" else slug))}"{(" aria-current=\"page\"" if slug == current else "")}>{html.escape(title)}</a>'
        for slug, title, _ in pages
    )


def jsonld(cfg: dict[str, Any], title: str, desc: str, slug: str, unredacted: bool) -> str:
    site = cfg.get("site", {})
    public_base = site.get("public_base_url", "https://sccairquality.com")
    base = site.get("unredacted_base_url", public_base + "/unredacted") if unredacted else public_base
    graph: list[dict[str, Any]] = [
        {"@type": "Organization", "@id": public_base.rstrip("/") + "/#org", "name": site.get("organisation", "SCC Nexus"), "url": public_base},
        {"@type": "WebSite", "@id": public_base.rstrip("/") + "/#website", "name": site.get("long_name", "AirQuality26 Environmental Intelligence Observatory"), "url": public_base},
        {"@type": "WebPage", "@id": page_url(base, slug) + "#webpage", "url": page_url(base, slug), "name": title, "description": desc, "inLanguage": "en-GB"},
        {"@type": "Dataset", "name": "AQ26 public redacted evidence index", "description": "Readiness-gated, public-safe evidence index and provenance records for environmental air-quality review."},
        {"@type": "BreadcrumbList", "itemListElement": [{"@type": "ListItem", "position": 1, "name": "AQ26", "item": public_base}, {"@type": "ListItem", "position": 2, "name": title, "item": page_url(base, slug)}]},
    ]
    if slug == "newhaven.html":
        graph.append({"@type": "Place", "name": "Newhaven Energy Recovery Facility evidence focus", "address": {"@type": "PostalAddress", "addressLocality": "Newhaven", "addressRegion": "East Sussex", "addressCountry": "GB"}, "additionalProperty": [{"@type": "PropertyValue", "name": "Permit reference", "value": "BV8067IL"}, {"@type": "PropertyValue", "name": "AQ26 publication status", "value": "screening context only; no causal attribution"}]})
    return '<script type="application/ld+json">' + json.dumps({"@context": "https://schema.org", "@graph": graph}, ensure_ascii=False) + '</script>'


def head(cfg: dict[str, Any], slug: str, title: str, desc: str, unredacted: bool, ga: str, gsc: str) -> str:
    site = cfg.get("site", {})
    public_base = site.get("public_base_url", "https://sccairquality.com")
    base = site.get("unredacted_base_url", public_base + "/unredacted") if unredacted else public_base
    robots = "noindex,nofollow,noarchive" if unredacted else "index,follow,max-image-preview:large"
    verify = f'<meta name="google-site-verification" content="{html.escape(gsc, quote=True)}">' if (gsc and not unredacted) else ""
    full_title = f"{title} · AQ26"
    url = page_url(base, slug)
    return (
        f'<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>{html.escape(full_title)}</title><meta name="description" content="{html.escape(desc, quote=True)}"><meta name="robots" content="{robots}">'
        f'<link rel="canonical" href="{html.escape(url, quote=True)}"><meta property="og:type" content="website"><meta property="og:title" content="{html.escape(full_title, quote=True)}">'
        f'<meta property="og:description" content="{html.escape(desc, quote=True)}"><meta property="og:url" content="{html.escape(url, quote=True)}"><meta property="og:site_name" content="AQ26">'
        f'<meta name="twitter:card" content="summary_large_image"><meta name="twitter:title" content="{html.escape(full_title, quote=True)}"><meta name="twitter:description" content="{html.escape(desc, quote=True)}">'
        f'<meta name="theme-color" content="#06364d"><link rel="icon" href="assets/favicon.svg" type="image/svg+xml"><link rel="manifest" href="site.webmanifest"><link rel="apple-touch-icon" href="assets/apple-touch-icon.png"><link rel="stylesheet" href="assets/aq26-canonical.css">'
        f'{verify}{jsonld(cfg, title, desc, slug, unredacted)}{analytics(ga) if not unredacted else ""}'
    )


def readiness() -> dict[str, str]:
    return READINESS_DEFAULTS.copy()


def status_class(value: str) -> str:
    v = value.lower()
    if "not" in v or "required" in v:
        return "status-not"
    if "needs" in v or "partial" in v or "context" in v:
        return "status-partial"
    return "status-ready"


def readiness_table() -> str:
    rows = "".join(f'<tr><td>{html.escape(k.replace("_", " ").title())}</td><td><span class="{status_class(v)}">{html.escape(v)}</span></td></tr>' for k, v in readiness().items())
    return '<div class="table-wrap"><table><thead><tr><th>Gate</th><th>Status / publication meaning</th></tr></thead><tbody>' + rows + '</tbody></table></div>'


def cards_for(slug: str, data: dict[str, Any], unredacted: bool) -> str:
    drive = data.get("drive_forensic_summary.json") or {}
    total = drive.get("total_items", "Drive audit pending") if isinstance(drive, dict) else "Drive audit pending"
    official = drive.get("newhaven_official_candidate_count", "pending") if isinstance(drive, dict) else "pending"
    if slug == "index.html":
        return f'<div class="grid two"><section class="card"><h2>Environmental-forensic evidence portal</h2><p>AQ26 tracks public-interest air-quality evidence around Newhaven, incinerator context, monitoring records, official filings, satellite/model context and historical source material.</p><p>Public pages are deliberately redacted and cautious. Protected pages support reviewer traceability and controlled evidence review.</p><p><a class="button" href="newhaven.html">Open Newhaven hub</a><a class="button alt" href="readiness.html">View readiness gates</a></p></section><aside class="card ok"><h3>Latest Drive audit</h3><p class="kpi">{html.escape(str(total))}</p><p class="muted">Inventoried evidence-lake items. Newhaven official candidates: {html.escape(str(official))}.</p></aside></div>'
    if slug == "readiness.html":
        return '<section class="card"><h2>Evidence readiness gates</h2><p>These gates control what AQ26 may say publicly. Strong claims remain locked until the relevant evidence, QA, comparator, meteorology and review controls pass.</p>' + readiness_table() + '</section>'
    if slug == "newhaven.html":
        return '<section class="card"><h2>Newhaven ERF / BV8067IL evidence hub</h2><p>This page organises public-safe Newhaven evidence candidates. It does not assert breach, health impact or causal attribution.</p><div class="grid"><div class="card ok"><h3>Official-document focus</h3><p>Annual/performance reports, permit records and regulatory candidates are separated from general web search results.</p></div><div class="card warn"><h3>Claim lock</h3><p>Interpretation requires source review, measurement units, station role, wind-sector and comparator checks.</p></div></div></section>'
    if slug in {"official-filings.html", "source-records.html"}:
        return f'<section class="card"><h2>Source and filing control</h2><p>AQ26 separates high-value Newhaven/BV8067IL official candidates from contextual or irrelevant material. Public citation requires manual source checking.</p><p class="kpi">{html.escape(str(official))}</p><p class="muted">Newhaven official-document candidates reported by the Drive forensic audit, subject to manual relevance review.</p></section>'
    if slug in {"monitoring.html", "satellite.html", "methodology.html"}:
        return '<section class="card"><h2>Method and interpretation discipline</h2><p>Ground monitors, weather, wind-sector, satellite catalogues and model outputs are context layers until QA and comparator gates pass. AQ26 avoids causal claims unless evidence gates support them.</p></section>'
    if slug == "downloads.html":
        return '<section class="card"><h2>Public-safe downloads</h2><p>Only redacted, public-safe summaries should appear here. Full evidence bundles and raw archives belong in the protected review area.</p><p class="muted">The audit blocks public full ZIP bundle leaks.</p></section>'
    return '<section class="card"><h2>' + html.escape(slug.replace(".html", "").replace("-", " ").title()) + '</h2><p>This AQ26 page is generated through the canonical publication template with consistent header, logo, metadata, analytics hooks, caveats and redaction controls.</p><p>' + html.escape(PUBLIC_CLAIM_NOTE) + '</p></section>'


def directory(pages: list[tuple[str, str, str]]) -> str:
    return '<section class="card"><h2>Page directory</h2><input class="searchbox" data-filter placeholder="Filter AQ26 pages"><div class="grid">' + "".join(
        f'<article class="card" data-filter-item><h3><a href="{html.escape(slug)}">{html.escape(title)}</a></h3><p>{html.escape(desc)}</p></article>'
        for slug, title, desc in pages
    ) + '</div></section>'


def hero(title: str, desc: str, unredacted: bool) -> str:
    label = "Protected reviewer evidence" if unredacted else "Redacted public evidence portal"
    ticker = "public output · protected reviewer evidence · SEO and analytics · source records · redaction gates · no causal attribution unless evidence gates pass"
    return f'<section class="hero"><div class="wrap hero-grid"><div><span class="eyebrow">{label}</span><h1>{html.escape(title)}</h1><p>{html.escape(desc)}</p><p><a class="button" href="readiness.html">Readiness gates</a><a class="button alt" href="methodology.html">Methodology</a></p></div><div class="hero-card"><img src="assets/air_quality_web.svg" alt="AQ26 air-quality evidence visual"></div></div><div class="ticker"><span>{html.escape(ticker)} &nbsp; · &nbsp; {html.escape(ticker)}</span></div></section>'


def footer(cfg: dict[str, Any], unredacted: bool) -> str:
    email = cfg.get("site", {}).get("contact_email", "enquiries@sccairquality.com")
    return f'<footer class="site-footer"><div class="wrap footgrid"><div><h2>AQ26</h2><p>Environmental Intelligence Observatory. Public outputs are redacted, cautious and readiness-gated.</p><p class="small">{html.escape(PUBLIC_CLAIM_NOTE)}</p></div><div><h3>Evidence</h3><p><a href="readiness.html">Readiness</a><br><a href="source-records.html">Sources</a><br><a href="methodology.html">Methodology</a></p></div><div><h3>Publication</h3><p><a href="downloads.html">Downloads</a><br><a href="archive.html">Archive</a><br><a href="/unredacted/" rel="nofollow">Protected review</a></p></div><div><h3>Governance</h3><p><a href="privacy.html">Privacy</a><br><a href="terms.html">Terms</a><br><a href="accessibility.html">Accessibility</a><br><a href="mailto:{html.escape(email)}">Corrections</a></p></div></div><div class="copyright">© <span data-year></span> AQ26 / SCC Nexus. Redacted public evidence screening only.</div></footer>'


def render_page(cfg: dict[str, Any], page: tuple[str, str, str], pages: list[tuple[str, str, str]], data: dict[str, Any], unredacted: bool, ga: str, gsc: str) -> str:
    slug, title, desc = page
    home = "./" if slug == "index.html" else "index.html"
    body = cards_for(slug, data, unredacted) + directory(pages)
    return f'<!doctype html><html lang="en-GB"><head>{head(cfg, slug, title, desc, unredacted, ga, gsc)}</head><body><a class="skip" href="#main">Skip to content</a><header class="site-header"><div class="wrap bar"><a class="brand" href="{home}"><img src="assets/aq26-logo.svg" alt="AirQuality26 Environmental Intelligence Observatory"><span>AQ26</span></a><button class="menu" data-menu-button aria-expanded="false" aria-controls="nav">☰ Menu</button><nav id="nav" class="nav" data-open="false">{nav_html(pages, slug)}</nav></div></header>{hero(title, desc, unredacted)}<main id="main" class="wrap">{body}</main>{footer(cfg, unredacted)}<script src="assets/aq26-canonical.js"></script></body></html>'


def write_common(out: Path, pages: list[tuple[str, str, str]], cfg: dict[str, Any], unredacted: bool, ga: str, gsc: str, data: dict[str, Any]) -> None:
    write_assets(out)
    for page in pages:
        (out / page[0]).write_text(render_page(cfg, page, pages, data, unredacted, ga, gsc), encoding="utf-8")
    if unredacted:
        (out / "robots.txt").write_text("User-agent: *\nDisallow: /\n", encoding="utf-8")
        (out / ".htaccess").write_text('AuthType Basic\nAuthName "AQ26 Protected Evidence"\nRequire valid-user\nOptions -Indexes\nHeader set X-Robots-Tag "noindex, nofollow, noarchive"\n', encoding="utf-8")
    else:
        base = cfg.get("site", {}).get("public_base_url", "https://sccairquality.com").rstrip("/")
        locs = "\n".join(f"  <url><loc>{base + ('/' if slug == 'index.html' else '/' + slug)}</loc></url>" for slug, _, _ in pages)
        (out / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + locs + '\n</urlset>\n', encoding="utf-8")
        (out / "robots.txt").write_text(f"User-agent: *\nDisallow: /unredacted/\nDisallow: /test/\nSitemap: {base}/sitemap.xml\n", encoding="utf-8")
        data_dir = out / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        (data_dir / "publication_marker.json").write_text(json.dumps({"generated_utc": now().isoformat(), "builder": "aq26_canonical_publication", "header_logo": "assets/aq26-logo.svg"}, indent=2), encoding="utf-8")
    downloads = out / "downloads"
    downloads.mkdir(exist_ok=True)
    (downloads / "README_PUBLIC_DOWNLOADS.txt").write_text("Public-safe downloads only. Full evidence ZIP bundles belong in the protected review area.\n", encoding="utf-8")


def main() -> int:
    cfg = load_config()
    data = load_data()
    ga = os.getenv("GA_MEASUREMENT_ID", "").strip()
    gsc = os.getenv("GOOGLE_SITE_VERIFICATION", "").strip()
    for path in [PUBLIC, UNREDACTED, TEST]:
        clean(path)
    write_common(PUBLIC, PAGES, cfg, False, ga, gsc, data)
    write_common(UNREDACTED, UNREDACTED_PAGES, cfg, True, "", "", data)
    shutil.copytree(PUBLIC, TEST, dirs_exist_ok=True)
    (TEST / "robots.txt").write_text("User-agent: *\nDisallow: /\n", encoding="utf-8")
    print("Built publication-grade AQ26 canonical site_public, site_unredacted and site_test.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
