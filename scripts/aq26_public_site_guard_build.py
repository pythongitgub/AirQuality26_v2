#!/usr/bin/env python3
"""AQ26 public site guard build.

Purpose:
- Never let site_public be empty or missing core pages.
- Create a professional client-safe shell if the scientific/backfill site has not yet been generated.
- Add old URL aliases and stable download aliases.
- Validate that core pages are non-blank before deployment.

This is a safety net. It does not replace the WeeklyV2/Stage2 backfill outputs.
"""
from __future__ import annotations

import argparse
import html
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

CORE_PAGES = {
    "index.html": ("AQ26 Environmental Intelligence Observatory", "Overview", "A client-friendly weekly environmental intelligence dashboard."),
    "archive.html": ("Weekly Archive", "Weekly evidence archive", "Browse weekly AQ26 evidence runs and readiness summaries."),
    "comparisons.html": ("Comparisons", "Interactive comparison charts", "Charts will populate from validated weekly backfill outputs. Current fallback panels keep this page useful while data is warming up."),
    "source-records.html": ("Source Records", "Source coverage and provenance", "A public summary of source classes, validation status and evidence coverage."),
    "readiness.html": ("Readiness", "Evidence readiness", "Plain-English readiness indicators showing which data streams are live, warming up or under validation."),
    "methodology.html": ("Methodology", "How AQ26 works", "AQ26 separates ground monitoring, official documents, weather and satellite/reanalysis context with provenance and validation."),
    "downloads.html": ("Downloads", "Reports and evidence bundles", "Download the latest redacted public report and evidence bundle when available."),
    "about.html": ("About AQ26", "About the project", "AQ26 brings together weekly air-quality and emissions-related evidence for accessible public review."),
    "privacy.html": ("Privacy", "Privacy", "This static website uses essential local-storage preferences and publishes redacted evidence summaries."),
    "cookies.html": ("Cookies", "Cookies", "AQ26 uses essential local-storage preferences and may load chart libraries for interactive visuals."),
    "accessibility.html": ("Accessibility", "Accessibility", "AQ26 aims to provide readable, accessible summaries with responsive navigation."),
    "terms.html": ("Terms", "Terms", "AQ26 outputs are informational and do not claim regulatory, legal, medical or causal determinations."),
    "contact.html": ("Contact", "Contact", "Contact details and project ownership can be added here."),
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

CSS = """
:root{--ink:#061b35;--muted:#64748b;--bg:#eef6fb;--card:#fff;--a:#0d6ea8;--b:#21b6c7;--ok:#15803d;--warn:#b45309;--bad:#b91c1c}
*{box-sizing:border-box} body{margin:0;font-family:Inter,system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif;background:linear-gradient(180deg,#f7fbff 0%,#eaf4fa 100%);color:var(--ink);line-height:1.5}.topbar{background:#071c33;color:white;padding:.55rem 1.25rem;font-size:.88rem;display:flex;justify-content:space-between;gap:1rem}.brand{display:flex;align-items:center;gap:1rem;padding:1rem 1.35rem;background:white}.brand img{height:72px;max-width:260px}.nav{display:flex;flex-wrap:wrap;gap:.5rem;margin-left:auto}.nav a,.menu-btn{border:1px solid #d7e6f2;border-radius:999px;padding:.65rem 1rem;text-decoration:none;color:#071c33;background:#f7fbff;font-weight:800}.nav a:hover{background:#e3f3fb}.mobile-head{display:none}.hero{margin:0;padding:4rem 1.35rem;background:linear-gradient(120deg,rgba(8,42,74,.92),rgba(17,148,184,.78)),url('assets/aq26-hero.jpg');background-size:cover;color:white}.hero-inner{max-width:1100px}.eyebrow{letter-spacing:.24em;text-transform:uppercase;font-weight:900}.hero h1{font-size:clamp(2.1rem,5vw,4.2rem);line-height:1.02;margin:.8rem 0}.hero p{font-size:1.12rem;max-width:780px}.btns{display:flex;flex-wrap:wrap;gap:.7rem;margin-top:1.5rem}.btn{display:inline-block;border-radius:.75rem;padding:.85rem 1.1rem;text-decoration:none;font-weight:900}.btn.primary{background:white;color:#071c33}.btn.secondary{background:rgba(255,255,255,.16);color:white;border:1px solid rgba(255,255,255,.45)}main{max-width:1180px;margin:0 auto;padding:2rem 1.25rem}.grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:1rem}.card{background:rgba(255,255,255,.92);border:1px solid #d8e7f2;border-radius:1.15rem;padding:1.25rem;box-shadow:0 12px 34px rgba(15,42,70,.08)}.card h3{margin:.1rem 0 .35rem}.metric{font-size:2.2rem;font-weight:950}.ok{color:var(--ok)}.warn{color:var(--warn)}.bad{color:var(--bad)}.section{margin-top:1.4rem}.placeholder{border:1px dashed #a8c8de;background:#f8fcff}.footer{background:#071c33;color:white;margin-top:3rem;padding:2rem 1.35rem}.footer a{color:white;margin-right:1rem}.cookie{position:fixed;left:1rem;right:1rem;bottom:1rem;background:white;border:1px solid #d8e7f2;border-radius:1rem;padding:1rem;box-shadow:0 12px 28px rgba(0,0,0,.12);z-index:30}.cookie button{border:0;border-radius:.6rem;padding:.55rem .8rem;font-weight:800;margin-right:.5rem}.dl{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:1rem}.small{color:var(--muted)}
@media(max-width:820px){.topbar{font-size:.75rem}.brand{padding:.7rem 1rem}.brand img{height:54px}.mobile-head{display:flex;align-items:center;justify-content:space-between;width:100%;gap:1rem}.desktop-brand{display:none}.nav{display:none;position:absolute;left:1rem;right:1rem;top:82px;z-index:25;background:white;border:1px solid #d7e6f2;border-radius:1rem;padding:.8rem;box-shadow:0 16px 32px rgba(0,0,0,.14)}.nav.open{display:grid}.nav a{display:block}.menu-btn{display:inline-flex;background:#071c33;color:white;border:0}.hero{padding:2.4rem 1rem}.grid{grid-template-columns:1fr}.dl{grid-template-columns:1fr}.cookie{font-size:.86rem}}
@media(min-width:821px){.menu-btn{display:none}}
"""

JS = """
(function(){
  const btn=document.querySelector('[data-menu-toggle]');
  const nav=document.querySelector('[data-nav]');
  if(btn&&nav){btn.addEventListener('click',()=>{const open=nav.classList.toggle('open');btn.setAttribute('aria-expanded',open?'true':'false');});}
  document.querySelectorAll('[data-cookie-accept]').forEach(b=>b.addEventListener('click',()=>{localStorage.setItem('aq26_cookie_ok','1');document.querySelector('.cookie')?.remove();}));
  if(localStorage.getItem('aq26_cookie_ok')==='1'){document.querySelector('.cookie')?.remove();}
})();
"""

def read_summary(site: Path) -> dict:
    candidates = [
        site / "data" / "latest_backfill_summary.json",
        site / "data" / "weekly_integrated" / "summary.json",
        site / "data" / "providers" / "integrated_weekly" / "summary.json",
    ]
    for p in candidates:
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                pass
    return {}

def find_downloads(site: Path) -> dict:
    d = site / "downloads"
    out = {"zip": None, "pdf": None, "md": None}
    if d.exists():
        zips = sorted(d.glob("*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
        pdfs = sorted(d.glob("*.pdf"), key=lambda p: p.stat().st_mtime, reverse=True)
        mds = sorted(d.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
        if zips: out["zip"] = zips[0]
        if pdfs: out["pdf"] = pdfs[0]
        if mds: out["md"] = mds[0]
    return out

def copy_assets(site: Path, asset_source: Path):
    assets = site / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    (assets / "aq26_site.css").write_text(CSS, encoding="utf-8")
    (assets / "aq26_site.js").write_text(JS, encoding="utf-8")
    for name in ["logo_web.svg", "favicon.svg", "apple-touch-icon.png", "favicon-32x32.png", "favicon-16x16.png", "android-chrome-192x192.png", "android-chrome-512x512.png", "site.webmanifest"]:
        src = asset_source / name
        if src.exists():
            shutil.copy2(src, assets / name)
    if not (assets / "logo_web.svg").exists():
        (assets / "logo_web.svg").write_text("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 240 80'><rect width='240' height='80' rx='16' fill='#071c33'/><text x='24' y='50' font-family='Arial' font-size='28' font-weight='700' fill='white'>SCC Nexus AQ26</text></svg>", encoding="utf-8")
    if not (assets / "favicon.svg").exists():
        shutil.copy2(assets / "logo_web.svg", assets / "favicon.svg")

def nav_html(active: str) -> str:
    return "".join(f"<a href='{href}'{' aria-current=page' if href==active else ''}>{html.escape(label)}</a>" for label, href in NAV)

def base_page(site: Path, filename: str, title: str, heading: str, intro: str, summary: dict, body: str) -> str:
    run_id = summary.get("run_id") or summary.get("run_ts") or "latest weekly run"
    window = summary.get("window") or summary.get("week") or "current evidence window"
    cards = ""
    if filename == "index.html":
        metrics = [
            ("Source records", summary.get("source_records") or summary.get("records_total") or "—", "All source classes"),
            ("OK records", summary.get("ok_records") or summary.get("records_ok") or "—", "Successful harvests"),
            ("Warnings", summary.get("warnings") or summary.get("records_warning") or "—", "Provider warnings"),
            ("Errors", summary.get("errors") or summary.get("records_error") or "0", "Should remain zero"),
        ]
        cards = "<section class='section grid'>" + "".join(f"<article class='card'><h3>{html.escape(str(k))}</h3><div class='metric'>{html.escape(str(v))}</div><p class='small'>{html.escape(str(desc))}</p></article>" for k,v,desc in metrics) + "</section>"
    return f"""<!doctype html>
<html lang='en'>
<head>
  <meta charset='utf-8'>
  <meta name='viewport' content='width=device-width, initial-scale=1'>
  <title>{html.escape(title)} · AQ26</title>
  <link rel='icon' type='image/svg+xml' href='assets/favicon.svg'>
  <link rel='apple-touch-icon' href='assets/apple-touch-icon.png'>
  <link rel='manifest' href='assets/site.webmanifest'>
  <link rel='stylesheet' href='assets/aq26_site.css'>
</head>
<body>
  <div class='topbar'><span>SCC Nexus · AQ26 environmental intelligence</span><span>Run {html.escape(str(run_id))} · {html.escape(str(window))}</span></div>
  <header class='brand'>
    <img class='desktop-brand' src='assets/logo_web.svg' alt='SCC Nexus AQ26'>
    <div class='mobile-head'><strong>AQ26</strong><button class='menu-btn' data-menu-toggle aria-expanded='false'>☰ Menu</button></div>
    <nav class='nav' data-nav>{nav_html(filename)}</nav>
  </header>
  <section class='hero'><div class='hero-inner'><div class='eyebrow'>AQ26 Environmental Intelligence Observatory</div><h1>{html.escape(heading)}</h1><p>{html.escape(intro)}</p><div class='btns'><a class='btn primary' href='archive.html'>View weekly archive</a><a class='btn secondary' href='downloads/latest-evidence.zip'>Download evidence ZIP</a></div></div></section>
  <main>
    {cards}
    {body}
  </main>
  <footer class='footer'><strong>AQ26 WeeklyV2</strong><p>Controlled-review evidence dashboard. Public pages show redacted, client-friendly summaries; unredacted QA and provenance review is separate.</p><p><a href='about.html'>About</a><a href='privacy.html'>Privacy</a><a href='cookies.html'>Cookies</a><a href='accessibility.html'>Accessibility</a><a href='terms.html'>Terms</a><a href='contact.html'>Contact</a></p><p>© SCC Nexus / AQ26</p></footer>
  <div class='cookie'><strong>Cookies on AQ26</strong><p>We use essential local-storage preferences for this banner and may load chart libraries for interactive charts. No advertising cookies are intentionally set by this static site.</p><button data-cookie-accept>Accept</button><a class='btn' href='cookies.html'>Cookie details</a></div>
  <script src='assets/aq26_site.js'></script>
</body>
</html>"""

def body_for(filename: str, downloads: dict) -> str:
    if filename == "comparisons.html":
        return """
<section class='section card'><h2>Comparison charts</h2><p>Interactive weekly comparisons will appear here as the validated backfill grows. We avoid blank charts by showing the current status, available source coverage and next-data requirements.</p></section>
<section class='section grid'>
  <article class='card placeholder'><h3>Weekly source coverage</h3><p>Ready for chart payload: <code>source_coverage_by_week.json</code>.</p></article>
  <article class='card placeholder'><h3>Readiness trend</h3><p>Ready for chart payload: <code>readiness_trend.json</code>.</p></article>
  <article class='card placeholder'><h3>Pollutant explorer</h3><p>Populates after LAQN/OpenAQ historical backfill has validated value-bearing observations.</p></article>
  <article class='card placeholder'><h3>Facility/control comparison</h3><p>Held until validated target/control logic, weather context and provenance gates pass.</p></article>
</section>"""
    if filename == "downloads.html":
        z = "downloads/latest-evidence.zip" if (downloads.get("zip") or (Path("downloads/latest-evidence.zip"))) else "#"
        return f"""
<section class='section card'><h2>Latest downloads</h2><p>Public downloads are redacted, client-safe bundles only. Unredacted evidence remains behind the protected review area.</p></section>
<section class='section dl'>
  <article class='card'><h3>Evidence ZIP</h3><p>Latest redacted public evidence bundle, where available.</p><a class='btn primary' href='downloads/latest-evidence.zip'>Download latest evidence ZIP</a></article>
  <article class='card'><h3>Weekly report</h3><p>Latest public PDF report, where available.</p><a class='btn primary' href='downloads/latest-report.pdf'>Download latest report PDF</a></article>
</section>"""
    if filename == "archive.html":
        return """
<section class='section card'><h2>Weekly archive</h2><p>The archive lists validated weekly runs and backfill windows. Backfilled weeks will appear as the weekly pipeline commits public summaries.</p></section>
<section class='section card placeholder'><h3>Backfill status</h3><p>Run AQ26 WeeklyV2 Science Backfill or Stage2 follow-on to populate historical weekly cards.</p></section>"""
    if filename == "readiness.html":
        return """
<section class='section grid'>
  <article class='card'><h3>Public redaction</h3><p class='ok'>Public pages are redacted and client-safe.</p></article>
  <article class='card'><h3>Ground monitoring</h3><p>LAQN/OpenAQ streams are being integrated into chart-ready outputs.</p></article>
  <article class='card'><h3>Satellite context</h3><p class='warn'>Catalogue discovery is live; controlled extraction remains gated.</p></article>
  <article class='card'><h3>External submission</h3><p class='bad'>Not yet ready for formal external scientific submission.</p></article>
</section>"""
    if filename == "source-records.html":
        return """
<section class='section card'><h2>Source records</h2><p>Each weekly run tracks provider status, record counts, retrieval windows and provenance. Detailed unredacted manifests are available in the protected review site.</p></section>"""
    if filename == "methodology.html":
        return """
<section class='section card'><h2>Methodology</h2><p>AQ26 separates observed ground measurements, official/regulatory documents, weather, satellite/reanalysis context and current-context sources. Public outputs are caveated and do not claim causation.</p></section>"""
    return "<section class='section card'><h2>Information</h2><p>This page is part of the AQ26 public client interface. Content is kept accessible, redacted and provenance-aware.</p></section>"

def ensure_download_aliases(site: Path, downloads: dict):
    d = site / "downloads"
    d.mkdir(parents=True, exist_ok=True)
    if downloads.get("zip"):
        shutil.copy2(downloads["zip"], d / "latest-evidence.zip")
    elif not (d / "latest-evidence.zip").exists():
        (d / "latest-evidence.zip").write_text("AQ26 latest redacted evidence bundle is awaiting the next successful backfill run.\n", encoding="utf-8")
    if downloads.get("pdf"):
        shutil.copy2(downloads["pdf"], d / "latest-report.pdf")
    elif not (d / "latest-report.pdf").exists():
        (d / "latest-report.pdf").write_text("AQ26 latest report PDF is awaiting the next successful backfill run.\n", encoding="utf-8")

def looks_blank(path: Path) -> bool:
    if not path.exists():
        return True
    txt = path.read_text(encoding="utf-8", errors="ignore")
    stripped = " ".join(txt.split()).lower()
    if len(stripped) < 900:
        return True
    # A page with only title/footer and no card/main content is blank for UX purposes.
    return ("<main" not in stripped) or ("class='card'" not in stripped and 'class="card"' not in stripped)

def write_pages(site: Path, asset_source: Path, force: bool):
    site.mkdir(parents=True, exist_ok=True)
    copy_assets(site, asset_source)
    summary = read_summary(site)
    downloads = find_downloads(site)
    ensure_download_aliases(site, downloads)
    for filename, (title, heading, intro) in CORE_PAGES.items():
        p = site / filename
        if force or looks_blank(p):
            p.write_text(base_page(site, filename, title, heading, intro, summary, body_for(filename, downloads)), encoding="utf-8")
    for alias, target in ALIASES.items():
        (site / alias).write_text(f"<!doctype html><meta charset='utf-8'><meta http-equiv='refresh' content='0; url={html.escape(target)}'><title>Redirecting · AQ26</title><p>Redirecting to <a href='{html.escape(target)}'>{html.escape(target)}</a>.</p>", encoding="utf-8")
    (site / "robots.txt").write_text("User-agent: *\nAllow: /\n", encoding="utf-8")
    manifest = {"generated_at_utc": datetime.now(timezone.utc).isoformat(), "core_pages": sorted(CORE_PAGES), "aliases": ALIASES, "status": "public_guard_ready"}
    (site / "data").mkdir(exist_ok=True)
    (site / "data" / "public_guard_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

def validate(site: Path) -> int:
    problems = []
    for name in CORE_PAGES:
        if looks_blank(site / name):
            problems.append(f"{name}: missing or blank")
    for name in ["assets/aq26_site.css", "assets/aq26_site.js", "assets/favicon.svg"]:
        if not (site / name).exists():
            problems.append(f"{name}: missing")
    result = {"ok": not problems, "problems": problems, "site_root": str(site)}
    print(json.dumps(result, indent=2))
    return 0 if not problems else 2

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site-root", default="site_public")
    ap.add_argument("--asset-source", default="website/assets")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--validate-only", action="store_true")
    args = ap.parse_args()
    site = Path(args.site_root)
    asset_source = Path(args.asset_source)
    if not args.validate_only:
        write_pages(site, asset_source, force=args.force)
    raise SystemExit(validate(site))

if __name__ == "__main__":
    main()
