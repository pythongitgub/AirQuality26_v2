#!/usr/bin/env python3
"""
AQ26 public site guard builder.
Creates/repairs all core public pages so the website never deploys blank pages.
This is intentionally self-contained and dependency-free.
"""
from __future__ import annotations

import argparse
import html
import json
import shutil
from pathlib import Path
from datetime import datetime, timezone

CORE_PAGES = {
    "index.html": ("AQ26 Environmental Intelligence Observatory", "A clear weekly environmental intelligence dashboard for air quality, emissions evidence, provenance and public-facing interpretation."),
    "archive.html": ("Weekly Archive", "Browse weekly AQ26 evidence windows, latest run status and historical backfill progress."),
    "comparisons.html": ("Interactive Comparisons", "Compare source coverage, evidence readiness, pollutant streams, official evidence and weekly progress."),
    "source-records.html": ("Source Records", "Review public-safe source records, provider status and provenance summaries."),
    "readiness.html": ("Readiness", "Understand which evidence streams are live, validating, pending or intentionally gated."),
    "methodology.html": ("Methodology", "How AQ26 separates observations, official records, model context, satellite discovery and validation caveats."),
    "downloads.html": ("Downloads", "Download public redacted evidence packs, reports and website-ready summaries when available."),
    "about.html": ("About AQ26", "AQ26 is a weekly evidence platform for environmental intelligence and air-quality context."),
    "privacy.html": ("Privacy", "Privacy and data handling information for this static public dashboard."),
    "cookies.html": ("Cookies", "Cookie and local-storage information for AQ26."),
    "accessibility.html": ("Accessibility", "Accessibility statement for the public AQ26 dashboard."),
    "terms.html": ("Terms", "Terms and disclaimers for public use of AQ26 outputs."),
    "contact.html": ("Contact", "Contact and project enquiry information."),
}

NAV = [
    ("index.html", "Observatory"),
    ("archive.html", "Weekly Archive"),
    ("comparisons.html", "Comparisons"),
    ("source-records.html", "Source Records"),
    ("readiness.html", "Readiness"),
    ("methodology.html", "Methodology"),
    ("downloads.html", "Downloads"),
]

ALIASES = {
    "historical-comparisons.html": "comparisons.html",
    "weekly-archive.html": "archive.html",
    "evidence-downloads.html": "downloads.html",
}


def read_json(path: Path):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return None


def nonblank(path: Path) -> bool:
    if not path.exists() or path.stat().st_size < 500:
        return False
    txt = path.read_text(encoding="utf-8", errors="ignore").strip()
    body = txt.lower()
    if "<body" not in body or "</html" not in body:
        return False
    # Must contain more than just nav/footer headings.
    return len(txt) > 900 and ("aq26-card" in txt or "aq26-panel" in txt or "aq26-hero" in txt)


def ensure_assets(site: Path, asset_source: Path | None):
    assets = site / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    if asset_source and asset_source.exists():
        for name in ["logo_web.svg", "favicon.svg", "site.webmanifest", "apple-touch-icon.png", "favicon-32x32.png", "favicon-16x16.png", "android-chrome-192x192.png", "android-chrome-512x512.png"]:
            src = asset_source / name
            if src.exists():
                shutil.copy2(src, assets / name)
    if not (assets / "favicon.svg").exists():
        (assets / "favicon.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="14" fill="#0f766e"/><text x="32" y="40" text-anchor="middle" font-size="22" fill="white" font-family="Arial">AQ</text></svg>', encoding="utf-8")
    if not (assets / "logo_web.svg").exists():
        shutil.copy2(assets / "favicon.svg", assets / "logo_web.svg")
    (assets / "aq26_mobile_nav.css").write_text("""
:root{--aq26-bg:#061b2a;--aq26-card:#ffffff;--aq26-ink:#0f172a;--aq26-accent:#0f766e;--aq26-soft:#ecfeff;--aq26-line:#dbeafe;--aq26-warn:#f59e0b;--aq26-ok:#16a34a;}
*{box-sizing:border-box} body{margin:0;font-family:Inter,system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif;background:#f8fafc;color:var(--aq26-ink);line-height:1.5}.aq26-top{position:sticky;top:0;z-index:50;background:rgba(6,27,42,.96);color:white;border-bottom:1px solid rgba(255,255,255,.14)}.aq26-wrap{max-width:1180px;margin:0 auto;padding:0 18px}.aq26-nav{display:flex;align-items:center;justify-content:space-between;gap:18px;min-height:72px}.aq26-brand{display:flex;align-items:center;gap:12px;text-decoration:none;color:white}.aq26-brand img{width:42px;height:42px}.aq26-brand strong{display:block;font-size:1.05rem}.aq26-brand span{display:block;font-size:.78rem;opacity:.76}.aq26-links{display:flex;gap:8px;flex-wrap:wrap}.aq26-links a{color:white;text-decoration:none;padding:9px 12px;border:1px solid rgba(255,255,255,.16);border-radius:999px;font-size:.9rem}.aq26-links a:hover{background:rgba(255,255,255,.12)}.aq26-menu-button{display:none;background:white;color:#061b2a;border:0;border-radius:999px;padding:10px 14px;font-weight:800}.aq26-hero{background:linear-gradient(135deg,#083344,#0f766e 58%,#22c55e);color:white;padding:58px 0}.aq26-hero h1{font-size:clamp(2rem,5vw,4.2rem);line-height:1.02;margin:.2rem 0 1rem}.aq26-hero p{font-size:1.1rem;max-width:850px}.aq26-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:18px;margin:24px 0}.aq26-card,.aq26-panel{background:white;border:1px solid var(--aq26-line);border-radius:22px;padding:20px;box-shadow:0 12px 35px rgba(15,23,42,.06)}.aq26-card h3,.aq26-panel h2{margin-top:0}.aq26-badge{display:inline-flex;align-items:center;gap:8px;border-radius:999px;padding:7px 11px;background:#dcfce7;color:#166534;font-weight:750;font-size:.85rem}.aq26-badge.warn{background:#fef3c7;color:#92400e}.aq26-metric{font-size:2.15rem;font-weight:900;color:#0f766e}.aq26-main{padding:26px 0 54px}.aq26-footer{background:#061b2a;color:white;padding:30px 0;margin-top:40px}.aq26-footer a{color:white}.aq26-list{display:grid;gap:10px}.aq26-list a,.aq26-download{display:block;padding:13px 15px;border:1px solid #dbeafe;border-radius:16px;background:#f8fafc;text-decoration:none;color:#0f172a}.aq26-chart-placeholder{min-height:220px;border:2px dashed #bae6fd;border-radius:20px;background:linear-gradient(180deg,#f0f9ff,#fff);display:flex;align-items:center;justify-content:center;text-align:center;padding:22px;color:#075985;font-weight:700}.aq26-two{display:grid;grid-template-columns:1fr 1fr;gap:18px}.aq26-table{width:100%;border-collapse:collapse;background:white;border-radius:18px;overflow:hidden}.aq26-table th,.aq26-table td{border-bottom:1px solid #e2e8f0;padding:10px;text-align:left}.aq26-table th{background:#f1f5f9}.aq26-note{background:#fff7ed;border:1px solid #fed7aa;border-radius:18px;padding:14px;color:#7c2d12}.aq26-mobile-panel{display:none}
@media(max-width:820px){.aq26-nav{min-height:64px}.aq26-menu-button{display:inline-flex}.aq26-links{display:none;position:absolute;left:14px;right:14px;top:66px;background:#082f49;border:1px solid rgba(255,255,255,.18);border-radius:22px;padding:12px;box-shadow:0 25px 60px rgba(0,0,0,.25)}.aq26-links.open{display:grid}.aq26-links a{border-radius:14px}.aq26-grid,.aq26-two{grid-template-columns:1fr}.aq26-brand span{display:none}.aq26-hero{padding:34px 0}.aq26-wrap{padding:0 14px}}
""".strip()+"\n", encoding="utf-8")
    (assets / "aq26_mobile_nav.js").write_text("""
(function(){
  function ready(fn){ if(document.readyState!=='loading') fn(); else document.addEventListener('DOMContentLoaded',fn); }
  ready(function(){
    var btn=document.querySelector('[data-aq26-menu-button]');
    var links=document.querySelector('[data-aq26-links]');
    if(!btn || !links) return;
    btn.addEventListener('click',function(){ var open=links.classList.toggle('open'); btn.setAttribute('aria-expanded', open?'true':'false'); });
  });
})();
""".strip()+"\n", encoding="utf-8")


def nav_html(current: str) -> str:
    links = "\n".join(f'<a href="{html.escape(h)}" {"aria-current=\"page\"" if h == current else ""}>{html.escape(t)}</a>' for h,t in NAV)
    return f"""
<header class="aq26-top">
  <div class="aq26-wrap aq26-nav">
    <a class="aq26-brand" href="index.html"><img src="assets/logo_web.svg" alt="AQ26 logo"><span><strong>AQ26</strong><span>Environmental Intelligence Observatory</span></span></a>
    <button class="aq26-menu-button" data-aq26-menu-button aria-expanded="false" aria-controls="aq26-menu">☰ Menu</button>
    <nav id="aq26-menu" class="aq26-links" data-aq26-links>{links}</nav>
  </div>
</header>
"""


def page(site: Path, filename: str, title: str, subtitle: str, content: str):
    doc = f"""<!doctype html>
<html lang="en-GB">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)} · AQ26</title>
  <meta name="description" content="{html.escape(subtitle)}">
  <link rel="icon" type="image/svg+xml" href="assets/favicon.svg">
  <link rel="apple-touch-icon" href="assets/apple-touch-icon.png">
  <link rel="manifest" href="assets/site.webmanifest">
  <link rel="stylesheet" href="assets/aq26_mobile_nav.css">
</head>
<body>
{nav_html(filename)}
<section class="aq26-hero"><div class="aq26-wrap"><span class="aq26-badge">Weekly evidence platform</span><h1>{html.escape(title)}</h1><p>{html.escape(subtitle)}</p></div></section>
<main class="aq26-main"><div class="aq26-wrap">{content}</div></main>
<footer class="aq26-footer"><div class="aq26-wrap"><strong>AQ26 WeeklyV2</strong><p>Public-facing environmental intelligence dashboard. Redacted public evidence only. No endorsement, regulatory determination or causal attribution is claimed.</p><p><a href="about.html">About</a> · <a href="privacy.html">Privacy</a> · <a href="cookies.html">Cookies</a> · <a href="accessibility.html">Accessibility</a> · <a href="terms.html">Terms</a> · <a href="contact.html">Contact</a></p></div></footer>
<script src="assets/aq26_mobile_nav.js"></script>
</body>
</html>
"""
    (site / filename).write_text(doc, encoding="utf-8")


def summarise(site: Path):
    summary = read_json(site / "data" / "latest_backfill_summary.json") or read_json(site / "data" / "weekly_index.json") or {}
    return summary if isinstance(summary, dict) else {}


def core_content(site: Path, filename: str, title: str, subtitle: str) -> str:
    s = summarise(site)
    run_id = html.escape(str(s.get("run_ts") or s.get("run_id") or "latest published run"))
    records = s.get("source_records") or s.get("records_total") or s.get("record_count") or "—"
    warnings = s.get("warnings") or s.get("warning_count") or "—"
    errors = s.get("errors") or s.get("error_count") or "0"
    if filename == "index.html":
        return f"""
<div class="aq26-grid">
 <section class="aq26-card"><h3>Latest evidence run</h3><div class="aq26-metric">{run_id}</div><p>Latest available public dashboard payload.</p></section>
 <section class="aq26-card"><h3>Source records</h3><div class="aq26-metric">{records}</div><p>Ground monitoring, official records, weather and satellite catalogue sources.</p></section>
 <section class="aq26-card"><h3>Validation status</h3><div class="aq26-metric">{errors}</div><p>Errors should remain zero. Warnings: {html.escape(str(warnings))}.</p></section>
</div>
<section class="aq26-panel"><h2>What this site shows</h2><p>AQ26 turns weekly evidence collection into a public-friendly intelligence dashboard. Raw data and unredacted review files are kept separate from the public website.</p></section>
"""
    if filename == "comparisons.html":
        return """
<section class="aq26-panel"><h2>Comparison dashboard</h2><p>Validated comparison charts are being populated by the WeeklyV2 backfill and integrated evidence workflows. Until then, these panels show what will be available and prevent blank public pages.</p><div class="aq26-grid"><div class="aq26-chart-placeholder">Weekly source coverage chart<br>Awaiting latest chart payload</div><div class="aq26-chart-placeholder">Readiness trend chart<br>Awaiting latest chart payload</div><div class="aq26-chart-placeholder">Official filings and evidence queue<br>Awaiting latest chart payload</div></div></section>
<section class="aq26-panel"><h2>Planned comparisons</h2><table class="aq26-table"><tr><th>Comparison</th><th>Status</th></tr><tr><td>LAQN / OpenAQ pollutant observations</td><td>Backfill in progress</td></tr><tr><td>Weather context and wind-sector review</td><td>Preparing</td></tr><tr><td>Satellite/reanalysis context</td><td>Discovery validated; extraction pending</td></tr></table></section>
"""
    if filename == "archive.html":
        return """
<section class="aq26-panel"><h2>Weekly archive</h2><p>Historical weekly windows will appear here as the controlled backfill completes. The page remains live with transparent status rather than displaying blanks.</p><div class="aq26-list"><a href="downloads.html">View latest public downloads</a><a href="readiness.html">Review evidence readiness</a><a href="source-records.html">Review source records status</a></div></section>
"""
    if filename == "downloads.html":
        dl = site / "downloads"
        files = sorted(dl.glob("*")) if dl.exists() else []
        links = []
        for f in files[:20]:
            if f.is_file():
                links.append(f'<a class="aq26-download" href="downloads/{html.escape(f.name)}">{html.escape(f.name)} · {f.stat().st_size:,} bytes</a>')
        if not links:
            links.append('<div class="aq26-note">No public redacted evidence bundle is available in this build yet. Run the WeeklyV2 backfill/report workflow, then redeploy.</div>')
        return '<section class="aq26-panel"><h2>Public downloads</h2><p>Only redacted public bundles should be exposed here.</p><div class="aq26-list">' + "\n".join(links) + '</div></section>'
    if filename == "source-records.html":
        return """
<section class="aq26-panel"><h2>Source records status</h2><p>Source records record where evidence came from, when it was retrieved, and whether it passed basic collection checks.</p><table class="aq26-table"><tr><th>Stream</th><th>Public status</th></tr><tr><td>Ground monitoring</td><td>Active / backfilling</td></tr><tr><td>Official records</td><td>Candidate queue under review</td></tr><tr><td>NASA Earthdata</td><td>Catalogue discovery validated</td></tr><tr><td>Unredacted evidence files</td><td>Restricted review site only</td></tr></table></section>
"""
    if filename == "readiness.html":
        return """
<section class="aq26-panel"><h2>Readiness overview</h2><p>AQ26 publishes evidence progressively. Some streams are live, while others are intentionally held until validation is complete.</p><div class="aq26-grid"><div class="aq26-card"><span class="aq26-badge">Live</span><h3>Public dashboard</h3><p>Core public pages are available.</p></div><div class="aq26-card"><span class="aq26-badge warn">Validating</span><h3>Pollutant trends</h3><p>Backfill and source validation are in progress.</p></div><div class="aq26-card"><span class="aq26-badge warn">Pending</span><h3>Attribution</h3><p>No causal claims are made.</p></div></div></section>
"""
    if filename == "methodology.html":
        return """
<section class="aq26-panel"><h2>Methodology summary</h2><p>AQ26 separates observed measurements, official records, model/reanalysis context, satellite catalogue discovery and current-context material. Public pages show redacted, website-ready summaries only.</p><ul><li>Ground observations are treated separately from modelled context.</li><li>Official documents require relevance review before public interpretation.</li><li>Satellite discovery is not presented as measured local concentration until extraction and validation pass.</li><li>Unredacted QA and provenance details are held in the restricted review site.</li></ul></section>
"""
    return f"""
<section class="aq26-panel"><h2>{html.escape(title)}</h2><p>{html.escape(subtitle)}</p><p>This page is intentionally populated by the no-blank guard so users never see an empty public page while the deeper evidence pipeline continues to backfill.</p></section>
"""


def make_alias(site: Path, alias: str, target: str):
    (site / alias).write_text(f'<!doctype html><html lang="en-GB"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="refresh" content="0; url={html.escape(target)}"><link rel="canonical" href="{html.escape(target)}"><title>Redirecting · AQ26</title></head><body><p>Redirecting to <a href="{html.escape(target)}">{html.escape(target)}</a>.</p></body></html>', encoding="utf-8")


def stable_download_aliases(site: Path):
    dl = site / "downloads"
    dl.mkdir(parents=True, exist_ok=True)
    zips = sorted([p for p in dl.glob("*.zip") if p.name != "latest-evidence.zip"], key=lambda p: p.stat().st_mtime, reverse=True)
    pdfs = sorted([p for p in dl.glob("*.pdf") if p.name != "latest-report.pdf"], key=lambda p: p.stat().st_mtime, reverse=True)
    if zips:
        shutil.copy2(zips[0], dl / "latest-evidence.zip")
    if pdfs:
        shutil.copy2(pdfs[0], dl / "latest-report.pdf")


def validate(site: Path):
    problems=[]
    for fn in CORE_PAGES:
        if not nonblank(site / fn):
            problems.append(f"{fn}: missing or blank")
    return problems


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--site-root", default="site_public")
    ap.add_argument("--asset-source", default="website/assets")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--validate-only", action="store_true")
    ap.add_argument("--summary", default="")
    args=ap.parse_args()
    site=Path(args.site_root)
    asset=Path(args.asset_source) if args.asset_source else None
    site.mkdir(parents=True, exist_ok=True)
    if not args.validate_only:
        ensure_assets(site, asset)
        for fn,(title,subtitle) in CORE_PAGES.items():
            if args.force or not nonblank(site / fn):
                page(site, fn, title, subtitle, core_content(site, fn, title, subtitle))
        for alias,target in ALIASES.items():
            make_alias(site, alias, target)
        stable_download_aliases(site)
        (site / "robots.txt").write_text("User-agent: *\nAllow: /\n", encoding="utf-8")
        (site / "sitemap.txt").write_text("\n".join(CORE_PAGES.keys())+"\n", encoding="utf-8")
    problems=validate(site)
    result={"ok": not problems, "problems": problems, "site_root": str(site), "generated_at_utc": datetime.now(timezone.utc).isoformat()}
    if args.summary:
        Path(args.summary).parent.mkdir(parents=True, exist_ok=True)
        Path(args.summary).write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if not problems else 2

if __name__ == "__main__":
    raise SystemExit(main())
