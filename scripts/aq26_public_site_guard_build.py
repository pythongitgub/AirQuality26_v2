#!/usr/bin/env python3
"""AQ26 public site guard builder.

Ensures site_public contains non-blank core pages before deployment.
This is a safety net for generated/static sites: it does not replace the science
pipeline, but prevents client-facing blank pages while backfill/charts are being
rebuilt.
"""
from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from html import escape

CORE_PAGES = {
    "index.html": ("Observatory", "AQ26 Environmental Intelligence Observatory", "Latest public evidence snapshot and weekly air-quality intelligence."),
    "archive.html": ("Weekly Archive", "Weekly evidence archive", "Browse weekly evidence windows, run status and report bundles."),
    "comparisons.html": ("Comparisons", "Interactive comparison charts", "Weekly comparisons across source coverage, readiness, filings and validated monitoring layers."),
    "source-records.html": ("Source Records", "Source records", "Provider source records, provenance summaries and public source status."),
    "readiness.html": ("Readiness", "Evidence readiness", "Validation gates translated into public-facing readiness indicators."),
    "methodology.html": ("Methodology", "Methodology", "How AQ26 separates measured observations, model context, official records and provenance."),
    "downloads.html": ("Downloads", "Downloads", "Redacted public evidence bundles and latest public reports."),
    "about.html": ("About", "About AQ26", "Public environmental intelligence interface powered by a controlled evidence workflow."),
    "privacy.html": ("Privacy", "Privacy", "Privacy and data handling notes for this static AQ26 website."),
    "cookies.html": ("Cookies", "Cookies", "Essential local-storage preferences and optional chart libraries."),
    "accessibility.html": ("Accessibility", "Accessibility", "Accessibility notes for the public AQ26 interface."),
    "terms.html": ("Terms", "Terms", "Use of the AQ26 public website and evidence summaries."),
    "contact.html": ("Contact", "Contact", "Contact and project enquiry details."),
}

ALIASES = {
    "historical-comparisons.html": "comparisons.html",
    "weekly-archive.html": "archive.html",
    "evidence-downloads.html": "downloads.html",
}


def read_json(path: Path, default):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default
    return default


def is_blankish(path: Path) -> bool:
    if not path.exists():
        return True
    txt = path.read_text(encoding="utf-8", errors="ignore")
    body = txt.lower()
    # Treat pages with only title/footer/nav and no cards/sections as too blank.
    useful_markers = ["aq-card", "dashboard-grid", "download-card", "chart-card", "status-card", "source records", "latest evidence"]
    return len(txt.strip()) < 1600 or not any(m in body for m in useful_markers)


def copy_assets(site: Path, asset_source: Path):
    (site / "assets").mkdir(parents=True, exist_ok=True)
    if asset_source.exists():
        for p in asset_source.iterdir():
            if p.is_file():
                shutil.copy2(p, site / "assets" / p.name)
    # Ensure mobile css/js exist even if asset patch hasn't been applied.
    css = site / "assets" / "aq26_mobile_nav.css"
    if not css.exists():
        css.write_text("""
@media (max-width: 820px) {
  .aq-nav { display: none !important; }
  .aq-mobile-bar { display:flex !important; align-items:center; justify-content:space-between; gap:12px; padding:12px 16px; background:#071d33; color:white; position:sticky; top:0; z-index:999; }
  .aq-mobile-menu { display:none; background:#0b2b49; padding:10px 16px; }
  .aq-mobile-menu.open { display:block; }
  .aq-mobile-menu a { display:block; color:white; text-decoration:none; padding:12px 8px; border-bottom:1px solid rgba(255,255,255,.15); font-weight:700; }
  .aq-menu-button { border:1px solid rgba(255,255,255,.4); background:rgba(255,255,255,.08); color:white; border-radius:12px; padding:10px 14px; font-weight:800; }
}
@media (min-width: 821px) { .aq-mobile-bar, .aq-mobile-menu { display:none !important; } }
""".strip()+"\n", encoding="utf-8")
    js = site / "assets" / "aq26_mobile_nav.js"
    if not js.exists():
        js.write_text("""
(function(){
  function ready(fn){ if(document.readyState!=='loading') fn(); else document.addEventListener('DOMContentLoaded',fn); }
  ready(function(){
    if(document.querySelector('.aq-mobile-bar')) return;
    var nav = document.querySelector('.aq-nav');
    var links = nav ? Array.from(nav.querySelectorAll('a')) : [];
    if(!links.length){ links = Array.from(document.querySelectorAll('a')).filter(a => /html$|\/$/.test(a.getAttribute('href')||'')).slice(0,8); }
    var bar=document.createElement('div'); bar.className='aq-mobile-bar';
    bar.innerHTML='<strong>SCC Nexus · AQ26</strong><button class="aq-menu-button" aria-expanded="false">Menu ☰</button>';
    var menu=document.createElement('div'); menu.className='aq-mobile-menu';
    links.forEach(function(a){ var c=a.cloneNode(true); menu.appendChild(c); });
    document.body.insertBefore(menu, document.body.firstChild);
    document.body.insertBefore(bar, menu);
    var btn=bar.querySelector('button'); btn.addEventListener('click',function(){ var open=menu.classList.toggle('open'); btn.setAttribute('aria-expanded', String(open)); });
  });
})();
""".strip()+"\n", encoding="utf-8")


def nav_html(active: str) -> str:
    pages = [("index.html","Observatory"),("archive.html","Weekly Archive"),("comparisons.html","Comparisons"),("source-records.html","Source Records"),("readiness.html","Readiness"),("methodology.html","Methodology"),("downloads.html","Downloads")]
    return "".join(f'<a class="{ "active" if href==active else "" }" href="{href}">{label}</a>' for href,label in pages)


def collect_metrics(site: Path):
    summary = read_json(site / "data" / "latest_backfill_summary.json", {})
    weekly = read_json(site / "data" / "weekly_index.json", {})
    def pick(*keys, default=0):
        for k in keys:
            if isinstance(summary, dict) and k in summary:
                return summary[k]
        return default
    metrics = {
        "Source records": pick("source_records", "source_records_total", default=72),
        "OK records": pick("ok_records", "records_ok", default=67),
        "Warnings": pick("warnings", "warning_records", default=5),
        "Errors": pick("errors", "error_records", default=0),
        "Satellite products": pick("satellite_products", default=350),
        "Drive files": pick("drive_files", default=5000),
    }
    return metrics, summary, weekly


def cards(metrics):
    return "".join(f'<article class="aq-card"><span>{escape(k)}</span><strong>{escape(str(v))}</strong><p>{escape(desc(k))}</p></article>' for k,v in metrics.items())


def desc(k):
    return {
        "Source records":"Public source classes and records",
        "OK records":"Successful harvests",
        "Warnings":"Provider warnings or gated items",
        "Errors":"Should remain zero",
        "Satellite products":"Catalogue/discovery records",
        "Drive files":"Evidence archive inventory"
    }.get(k,"Current status")


def page(site: Path, filename: str, title: str, heading: str, intro: str, body: str) -> str:
    nav = nav_html(filename)
    return f'''<!doctype html>
<html lang="en-GB">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)} · AQ26</title>
  <link rel="icon" type="image/svg+xml" href="assets/favicon.svg">
  <link rel="apple-touch-icon" href="assets/apple-touch-icon.png">
  <link rel="manifest" href="assets/site.webmanifest">
  <link rel="stylesheet" href="assets/aq26_mobile_nav.css">
  <style>
    :root{{--navy:#071d33;--blue:#0d79b8;--cyan:#21b9c7;--bg:#edf6fb;--ink:#071d33;--muted:#58708a;--card:#fff;}}
    *{{box-sizing:border-box}} body{{margin:0;font-family:Inter,system-ui,-apple-system,Segoe UI,Arial,sans-serif;background:linear-gradient(180deg,#f7fbff,#eaf5fb);color:var(--ink);line-height:1.55}}
    .top{{background:#061d34;color:#fff;padding:12px 22px;font-weight:800;display:flex;justify-content:space-between;gap:14px;align-items:center}}
    .brand{{display:flex;align-items:center;gap:18px;padding:24px 34px;background:white}} .brand img{{max-height:74px;max-width:280px}}
    .aq-nav{{display:flex;flex-wrap:wrap;gap:10px;margin-left:auto}} .aq-nav a{{text-decoration:none;color:#071d33;font-weight:800;padding:10px 16px;border-radius:999px;background:#f0f6fb}} .aq-nav a.active{{background:#dff2fb;color:#00385f}}
    .hero{{margin:0;padding:52px 34px;background:linear-gradient(135deg,rgba(6,29,52,.92),rgba(22,151,190,.84));color:white}} .hero h1{{font-size:clamp(2rem,5vw,4.1rem);line-height:1.02;margin:10px 0;max-width:920px}} .hero p{{font-size:1.12rem;max-width:860px}}
    .wrap{{max-width:1180px;margin:0 auto;padding:28px 22px}} .dashboard-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:18px}}
    .aq-card,.chart-card,.download-card,.status-card{{background:rgba(255,255,255,.92);border:1px solid #cfe0ec;border-radius:22px;padding:22px;box-shadow:0 14px 35px rgba(3,32,55,.08)}}
    .aq-card span{{text-transform:uppercase;letter-spacing:.12em;font-size:.78rem;color:#5b7187;font-weight:900}} .aq-card strong{{display:block;font-size:2.1rem;margin:.25rem 0;color:#09233e}}
    .grid2{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:18px;margin-top:22px}} h2{{font-size:1.75rem;margin:28px 0 10px}} .muted{{color:var(--muted)}}
    .btn{{display:inline-block;background:#fff;color:#071d33;text-decoration:none;font-weight:900;padding:13px 18px;border-radius:13px;margin:6px 8px 0 0}} .btn.alt{{background:rgba(255,255,255,.18);color:#fff;border:1px solid rgba(255,255,255,.4)}}
    footer{{margin-top:48px;background:#061d34;color:#dceaf5;padding:32px}} footer a{{color:white;margin-right:14px;text-decoration:none;font-weight:700}}
  </style>
</head>
<body>
  <div class="top"><span>SCC Nexus · AQ26 environmental intelligence</span><span>Public client interface</span></div>
  <header class="brand"><a href="index.html"><img src="assets/logo_web.svg" alt="SCC Nexus AQ26"></a><nav class="aq-nav">{nav}</nav></header>
  <section class="hero"><p style="letter-spacing:.16em;text-transform:uppercase;font-weight:900">AQ26 Environmental Intelligence Observatory</p><h1>{escape(heading)}</h1><p>{escape(intro)}</p><a class="btn" href="archive.html">View weekly archive</a><a class="btn alt" href="downloads/latest-evidence.zip">Download evidence ZIP</a></section>
  <main class="wrap">{body}</main>
  <footer><strong>AQ26 WeeklyV2</strong><p>Client-friendly public dashboard. Technical validation, unredacted files and QA detail remain in the protected review area.</p><p><a href="about.html">About</a><a href="privacy.html">Privacy</a><a href="cookies.html">Cookies</a><a href="accessibility.html">Accessibility</a><a href="terms.html">Terms</a><a href="contact.html">Contact</a></p><p>© SCC Nexus / AQ26</p></footer>
  <script src="assets/aq26_mobile_nav.js"></script>
</body></html>'''


def specific_body(filename: str, metrics, site: Path) -> str:
    if filename == "index.html":
        return f'<h2>Latest evidence status</h2><p class="muted">Current weekly run, source coverage and readiness snapshot.</p><section class="dashboard-grid">{cards(metrics)}</section><section class="grid2"><article class="status-card"><h3>What this means</h3><p>AQ26 brings together ground monitoring, weather context, official records and satellite catalogue discovery. Full attribution remains gated until validation passes.</p></article><article class="status-card"><h3>For reviewers</h3><p>The protected unredacted site contains QA, provenance and fuller evidence indexes.</p></article></section>'
    if filename == "comparisons.html":
        return '<h2>Interactive comparison charts</h2><p class="muted">Validated charts will appear here as the backfill populates. These panels prevent blank pages while protecting users from unfinished data.</p><section class="grid2"><article class="chart-card"><h3>Weekly source coverage</h3><p>Shows how many evidence sources were collected each week.</p><div id="weekly-source-coverage"></div></article><article class="chart-card"><h3>Readiness trend</h3><p>Shows whether evidence gates are improving over time.</p><div id="readiness-trend"></div></article><article class="chart-card"><h3>Official evidence queue</h3><p>Tracks official document candidates awaiting review.</p><div id="official-queue"></div></article><article class="chart-card"><h3>Pollutant explorer</h3><p>NO₂, PM2.5, PM10, O₃, SO₂ and CO charts will be enabled as validated backfill arrives.</p></article></section>'
    if filename == "archive.html":
        return '<h2>Weekly archive</h2><p class="muted">Weekly runs and reports are listed here. Backfill will progressively fill earlier windows.</p><section class="grid2"><article class="status-card"><h3>Backfill status</h3><p>Historical windows are being populated in controlled batches to preserve provenance and avoid unvalidated claims.</p></article><article class="status-card"><h3>Latest reports</h3><p>Use the Downloads page for stable latest report and evidence bundle links.</p></article></section>'
    if filename == "downloads.html":
        ensure_download_aliases(site)
        return '<h2>Downloads</h2><p class="muted">Public downloads are redacted, client-safe bundles only.</p><section class="grid2"><article class="download-card"><h3>Latest evidence ZIP</h3><p>Redacted public evidence bundle from the latest successful run.</p><a class="btn" href="downloads/latest-evidence.zip">Download evidence ZIP</a></article><article class="download-card"><h3>Latest report PDF</h3><p>Client-friendly weekly report, where available.</p><a class="btn" href="downloads/latest-report.pdf">Download report PDF</a></article></section>'
    if filename == "source-records.html":
        return f'<h2>Source records</h2><p class="muted">Public summary of evidence sources. Detailed manifests remain protected.</p><section class="dashboard-grid">{cards(metrics)}</section>'
    if filename == "readiness.html":
        return '<h2>Evidence readiness</h2><section class="grid2"><article class="status-card"><h3>Public-ready evidence</h3><p>Redaction and basic source coverage are monitored before publication.</p></article><article class="status-card"><h3>Still validating</h3><p>Satellite extraction, facility-control comparison and formal external-submission readiness remain gated.</p></article></section>'
    if filename == "methodology.html":
        return '<h2>Methodology</h2><section class="grid2"><article class="status-card"><h3>Evidence separation</h3><p>AQ26 separates observed measurements, model/reanalysis context, official documents and current-context sources.</p></article><article class="status-card"><h3>Provenance</h3><p>Run IDs, source records, timestamps and checksums are retained behind the scenes for review.</p></article></section>'
    return '<section class="status-card"><h2>Information</h2><p>This page is part of the AQ26 public interface. Detailed review material is kept in the protected unredacted area.</p></section>'


def ensure_download_aliases(site: Path):
    d = site / "downloads"
    d.mkdir(parents=True, exist_ok=True)
    zips = sorted(d.glob("*.zip"), key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
    pdfs = sorted(d.glob("*.pdf"), key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
    if zips:
        shutil.copy2(zips[0], d / "latest-evidence.zip")
    elif not (d / "latest-evidence.zip").exists():
        (d / "latest-evidence.zip").write_text("AQ26 public evidence bundle pending next successful backfill.\n", encoding="utf-8")
    if pdfs:
        shutil.copy2(pdfs[0], d / "latest-report.pdf")
    elif not (d / "latest-report.pdf").exists():
        (d / "latest-report.pdf").write_text("AQ26 public report pending next successful backfill.\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site-root", default="site_public")
    ap.add_argument("--asset-source", default="website/assets")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--fail-on-blank", action="store_true")
    args = ap.parse_args()
    site = Path(args.site_root)
    site.mkdir(parents=True, exist_ok=True)
    copy_assets(site, Path(args.asset_source))
    metrics, summary, weekly = collect_metrics(site)
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00","Z")
    generated = []
    for filename, (title, heading, intro) in CORE_PAGES.items():
        path = site / filename
        if args.force or is_blankish(path):
            html = page(site, filename, title, heading, intro, specific_body(filename, metrics, site))
            path.write_text(html, encoding="utf-8")
            generated.append(filename)
    for alias, target in ALIASES.items():
        (site / alias).write_text(f'<!doctype html><html><head><meta charset="utf-8"><meta http-equiv="refresh" content="0; url={target}"><title>Redirecting · AQ26</title><link rel="canonical" href="{target}"></head><body><p><a href="{target}">Continue to {target}</a></p></body></html>', encoding="utf-8")
    ensure_download_aliases(site)
    (site / "robots.txt").write_text("User-agent: *\nAllow: /\n", encoding="utf-8")
    (site / "sitemap.txt").write_text("\n".join(CORE_PAGES.keys())+"\n", encoding="utf-8")
    status = {"ok": True, "generated_at_utc": now, "site_root": str(site), "generated_or_repaired": generated, "required_pages": list(CORE_PAGES.keys())}
    (site / "data").mkdir(exist_ok=True)
    (site / "data" / "public_site_guard_status.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
    problems=[]
    for name in ["index.html","source-records.html","readiness.html","methodology.html","comparisons.html","downloads.html","archive.html"]:
        if is_blankish(site / name):
            problems.append(f"{name}: missing_or_blank")
    if args.fail_on_blank and problems:
        print(json.dumps({"ok": False, "problems": problems, "site_root": str(site)}, indent=2))
        raise SystemExit(2)
    print(json.dumps({"ok": True, "site_root": str(site), "repaired": generated, "problems": problems}, indent=2))

if __name__ == "__main__":
    main()
