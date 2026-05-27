#!/usr/bin/env python3
"""
AQ26 public-site polish and no-blank-page guard.

Purpose:
- Keep the public site as a client/user interface, not a raw scientific pool.
- Prevent professional-looking but empty pages (especially comparisons).
- Add mobile hamburger navigation and favicon/touch-icon references.
- Add backwards-compatible alias pages.
- Add stable latest download aliases where source files exist.
- Generate safe, friendly fallback content when chart payloads are absent.

This script is intentionally conservative: it does not delete data, does not expose unredacted
content, and only writes inside the chosen site root.
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import re
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

NAV = [
    ("Observatory", "index.html"),
    ("Weekly Archive", "archive.html"),
    ("Comparisons", "comparisons.html"),
    ("Source Records", "source-records.html"),
    ("Readiness", "readiness.html"),
    ("Methodology", "methodology.html"),
    ("Downloads", "downloads.html"),
]

ALIASES = {
    "historical-comparisons.html": "comparisons.html",
    "weekly-archive.html": "archive.html",
    "evidence-downloads.html": "downloads.html",
    "latest-report.html": "downloads.html",
}

CORE_PAGES = [
    "index.html",
    "archive.html",
    "comparisons.html",
    "source-records.html",
    "readiness.html",
    "methodology.html",
    "downloads.html",
]

def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

def read_json(path: Path, default: Any = None) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default

def write_text(path: Path, txt: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(txt, encoding="utf-8")

def copy_asset_if_exists(asset_source: Path, site_root: Path, name: str) -> None:
    src = asset_source / name
    if src.exists():
        dst = site_root / "assets" / name
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

def first_existing(paths: List[Path]) -> Optional[Path]:
    for p in paths:
        if p.exists():
            return p
    return None

def get_latest_summary(site_root: Path) -> Dict[str, Any]:
    candidates = [
        site_root / "data" / "latest_backfill_summary.json",
        site_root / "data" / "weekly_integrated" / "summary.json",
        site_root / "data" / "providers" / "integrated_weekly" / "summary.json",
        site_root / "data" / "public_dashboard" / "summary.json",
    ]
    for p in candidates:
        obj = read_json(p, None)
        if isinstance(obj, dict):
            return obj
    return {}

def coalesce_int(*vals: Any, default: int = 0) -> int:
    for v in vals:
        if isinstance(v, bool):
            continue
        if isinstance(v, (int, float)):
            return int(v)
        if isinstance(v, str):
            try:
                return int(float(v.replace(",", "")))
            except Exception:
                pass
    return default

def summary_metric(summary: Dict[str, Any], keys: List[str], default: int = 0) -> int:
    cur: Any = summary
    for key in keys:
        if isinstance(cur, dict) and key in cur:
            return coalesce_int(cur[key], default=default)
    # fallback flattened
    for k in keys:
        if k in summary:
            return coalesce_int(summary[k], default=default)
    return default

def find_downloads(site_root: Path) -> Dict[str, Optional[str]]:
    downloads_dir = site_root / "downloads"
    out = {"zip": None, "pdf": None, "md": None}
    if not downloads_dir.exists():
        return out
    files = sorted(downloads_dir.glob("*"), key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
    for p in files:
        low = p.name.lower()
        if out["zip"] is None and low.endswith(".zip"):
            out["zip"] = str(p.relative_to(site_root)).replace(os.sep, "/")
        if out["pdf"] is None and low.endswith(".pdf"):
            out["pdf"] = str(p.relative_to(site_root)).replace(os.sep, "/")
        if out["md"] is None and low.endswith(".md"):
            out["md"] = str(p.relative_to(site_root)).replace(os.sep, "/")
    return out

def make_latest_download_aliases(site_root: Path) -> Dict[str, str]:
    downloads_dir = site_root / "downloads"
    downloads_dir.mkdir(parents=True, exist_ok=True)
    latest = {}
    files = sorted(downloads_dir.glob("*"), key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
    rules = [
        (".zip", "latest-evidence.zip"),
        (".pdf", "latest-report.pdf"),
        (".md", "latest-report.md"),
    ]
    for suffix, alias in rules:
        src = next((p for p in files if p.name != alias and p.name.lower().endswith(suffix)), None)
        if src:
            dst = downloads_dir / alias
            try:
                shutil.copy2(src, dst)
                latest[suffix] = str(dst.relative_to(site_root)).replace(os.sep, "/")
            except Exception:
                pass
    return latest

def page_shell(title: str, body: str, site_root: Path) -> str:
    nav_links = "\n".join(f'<a href="{href}">{html.escape(label)}</a>' for label, href in NAV)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)} · AQ26</title>
<link rel="icon" type="image/svg+xml" href="assets/favicon.svg">
<link rel="apple-touch-icon" href="assets/apple-touch-icon.png">
<link rel="manifest" href="assets/site.webmanifest">
<link rel="stylesheet" href="assets/aq26_public_polish.css">
<link rel="stylesheet" href="assets/aq26_mobile_nav.css">
</head>
<body>
<header class="aq26-topbar">
  <div class="aq26-brand"><strong>SCC Nexus</strong><span>· AQ26 environmental intelligence</span></div>
  <button class="aq26-menu-toggle" type="button" aria-expanded="false" aria-controls="aq26-mobile-menu">Menu</button>
  <nav id="aq26-mobile-menu" class="aq26-nav">{nav_links}</nav>
</header>
<main class="aq26-main">
{body}
</main>
<footer class="aq26-footer">
  <strong>AQ26 WeeklyV2</strong>
  <p>Client-facing evidence dashboard. Technical QA, unredacted outputs and raw review material are held separately.</p>
  <nav>{nav_links}</nav>
</footer>
<script src="assets/aq26_mobile_nav.js"></script>
</body>
</html>"""

def card(title: str, value: str, text: str = "") -> str:
    return f"""<section class="aq26-card">
  <div class="aq26-card-label">{html.escape(title)}</div>
  <div class="aq26-card-value">{html.escape(value)}</div>
  <p>{html.escape(text)}</p>
</section>"""

def friendly_gate(label: str, status: Any, friendly_ok: str, friendly_no: str) -> str:
    ok = str(status).lower() in ("true", "1", "yes", "ok", "ready")
    return card(label, "Ready" if ok else "Preparing", friendly_ok if ok else friendly_no)

def build_comparisons_page(site_root: Path, force: bool = False) -> None:
    p = site_root / "comparisons.html"
    txt = p.read_text(encoding="utf-8", errors="ignore") if p.exists() else ""
    # if it already has substantial charts/content, only inject mobile/assets later
    blankish = (not p.exists()) or (len(re.sub(r"<[^>]+>", " ", txt).strip()) < 900) or ("Comparison charts Interactive weekly comparisons" in txt and "plotly" not in txt.lower() and "canvas" not in txt.lower())
    if not blankish and not force:
        return

    summary = get_latest_summary(site_root)
    charts = [
        ("Weekly record counts", "data/charts/weekly_record_counts.json"),
        ("Source coverage by week", "data/charts/source_coverage_by_week.json"),
        ("Readiness trend", "data/charts/readiness_trend.json"),
        ("Satellite products by week", "data/charts/satellite_products_by_week.json"),
        ("Latest source-class summary", "data/charts/source_class_summary_latest.json"),
    ]
    chart_cards = []
    for title, rel in charts:
        exists = (site_root / rel).exists()
        chart_cards.append(f"""
        <section class="aq26-chart-panel" data-chart-source="{html.escape(rel)}">
          <div>
            <h3>{html.escape(title)}</h3>
            <p>{'Chart payload found and ready for rendering.' if exists else 'Awaiting validated chart payload from the next backfill run.'}</p>
          </div>
          <a href="{html.escape(rel)}" class="aq26-small-link">{'Open data' if exists else 'Pending'}</a>
        </section>""")
    body = f"""
<section class="aq26-hero compact">
  <p class="aq26-kicker">AQ26 COMPARISONS</p>
  <h1>Interactive comparison charts</h1>
  <p>Weekly comparisons across source coverage, readiness, filings, satellite catalogue discovery and backfill progress. This page never appears blank: when a source is still warming up, it is shown clearly as pending rather than hidden.</p>
</section>
<section class="aq26-grid">
  {card('Source records', str(summary_metric(summary, ['source_records','total_source_records','records_total'], 0)), 'All public source classes in the latest run.')}
  {card('OK records', str(summary_metric(summary, ['ok_records','records_ok'], 0)), 'Successful source harvests.')}
  {card('Warnings', str(summary_metric(summary, ['warnings','records_warning'], 0)), 'Items to review before external claims.')}
  {card('Satellite products', str(summary_metric(summary, ['satellite_products','satellite_product_count'], 0)), 'Catalogue/discovery context, not yet all extracted observations.')}
</section>
<section class="aq26-section">
  <h2>Chart panels</h2>
  <p>These panels are populated from website-safe JSON generated by the weekly pipeline. Empty scientific outputs are deliberately labelled instead of leaving a blank page.</p>
  <div class="aq26-chart-grid">{''.join(chart_cards)}</div>
</section>
<section class="aq26-section">
  <h2>What this means</h2>
  <p>Comparisons are a client-friendly view of validated pipeline outputs. Technical source files, manifests, redaction checks and unredacted QA remain in the protected review site.</p>
</section>
"""
    write_text(p, page_shell("Comparisons", body, site_root))

def build_downloads_page(site_root: Path, force: bool = False) -> None:
    p = site_root / "downloads.html"
    txt = p.read_text(encoding="utf-8", errors="ignore") if p.exists() else ""
    if p.exists() and len(re.sub(r"<[^>]+>", " ", txt).strip()) > 900 and not force:
        return
    make_latest_download_aliases(site_root)
    dl = find_downloads(site_root)
    items = []
    for label, key in [("Latest redacted evidence ZIP", "zip"), ("Latest PDF report", "pdf"), ("Latest Markdown report", "md")]:
        href = dl.get(key)
        if href:
            items.append(f'<a class="aq26-download-card" href="{html.escape(href)}"><strong>{html.escape(label)}</strong><span>{html.escape(href)}</span></a>')
        else:
            items.append(f'<div class="aq26-download-card pending"><strong>{html.escape(label)}</strong><span>Awaiting next successful weekly backfill.</span></div>')
    body = f"""
<section class="aq26-hero compact">
  <p class="aq26-kicker">AQ26 DOWNLOADS</p>
  <h1>Evidence packs and reports</h1>
  <p>Public downloads expose only redacted, website-ready evidence bundles. Internal and unredacted packs remain in the protected review area.</p>
</section>
<section class="aq26-download-grid">{''.join(items)}</section>
<section class="aq26-section"><h2>Download policy</h2><p>Public evidence ZIPs should only be offered when redaction checks pass. If a weekly bundle is absent, the page shows a pending status instead of a broken link.</p></section>
"""
    write_text(p, page_shell("Downloads", body, site_root))

def build_archive_page(site_root: Path, force: bool = False) -> None:
    p = site_root / "archive.html"
    txt = p.read_text(encoding="utf-8", errors="ignore") if p.exists() else ""
    if p.exists() and len(re.sub(r"<[^>]+>", " ", txt).strip()) > 900 and not force:
        return
    weekly = read_json(site_root / "data" / "weekly_index.json", [])
    rows = []
    if isinstance(weekly, list):
        for w in weekly[:104]:
            label = w.get("week_start") or w.get("start") or w.get("window_start") or "Week"
            status = w.get("status") or w.get("harvest_status") or "indexed"
            rows.append(f"<tr><td>{html.escape(str(label))}</td><td>{html.escape(str(status))}</td></tr>")
    if not rows:
        rows.append("<tr><td>Latest weekly window</td><td>Awaiting next backfill index</td></tr>")
    body = f"""
<section class="aq26-hero compact">
  <p class="aq26-kicker">AQ26 WEEKLY ARCHIVE</p>
  <h1>Weekly evidence archive</h1>
  <p>Backfill runs are being expanded progressively. Weeks with pending evidence are shown openly so users understand what is complete and what is still building.</p>
</section>
<section class="aq26-section"><table class="aq26-table"><thead><tr><th>Week</th><th>Status</th></tr></thead><tbody>{''.join(rows[:80])}</tbody></table></section>
"""
    write_text(p, page_shell("Weekly Archive", body, site_root))

def create_alias_pages(site_root: Path) -> None:
    for alias, target in ALIASES.items():
        body = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="refresh" content="0; url={html.escape(target)}"><title>Redirecting · AQ26</title><link rel="canonical" href="{html.escape(target)}"></head><body><p>Redirecting to <a href="{html.escape(target)}">{html.escape(target)}</a>.</p><script>location.replace({json.dumps(target)});</script></body></html>"""
        write_text(site_root / alias, body)

def write_mobile_assets(asset_source: Path, site_root: Path) -> None:
    assets = site_root / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    # copy supplied branding if present
    for name in [
        "logo_web.svg", "favicon.svg", "apple-touch-icon.png", "favicon-32x32.png",
        "favicon-16x16.png", "android-chrome-192x192.png", "android-chrome-512x512.png",
        "site.webmanifest",
    ]:
        copy_asset_if_exists(asset_source, site_root, name)

    css = r"""
:root{--aq26-navy:#071b33;--aq26-blue:#0b7fb3;--aq26-cyan:#2bbfd2;--aq26-bg:#eef6fb;--aq26-card:#ffffff;--aq26-text:#0a1f38;--aq26-muted:#5f7289}
*{box-sizing:border-box}
body{margin:0;background:linear-gradient(180deg,#eef6fb 0,#fff 55%,#eef6fb 100%);color:var(--aq26-text);font-family:Inter,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
.aq26-topbar{position:sticky;top:0;z-index:40;display:flex;align-items:center;justify-content:space-between;gap:1rem;background:var(--aq26-navy);color:#fff;padding:.85rem 1.25rem;box-shadow:0 8px 24px rgba(5,20,42,.12)}
.aq26-brand{display:flex;gap:.35rem;align-items:center;white-space:nowrap}
.aq26-brand span{opacity:.88}
.aq26-nav{display:flex;align-items:center;gap:.5rem;flex-wrap:wrap}
.aq26-nav a{color:#fff;text-decoration:none;border:1px solid rgba(255,255,255,.24);border-radius:999px;padding:.45rem .75rem;font-weight:700;font-size:.92rem}
.aq26-menu-toggle{display:none;border:1px solid rgba(255,255,255,.3);background:#fff;color:var(--aq26-navy);border-radius:999px;padding:.55rem .85rem;font-weight:800}
.aq26-main{max-width:1180px;margin:0 auto;padding:2rem 1rem}
.aq26-hero{border-radius:28px;padding:3rem;background:linear-gradient(135deg,#063462,#138ebc);color:#fff;box-shadow:0 18px 50px rgba(5,35,70,.18);margin-bottom:1.5rem}
.aq26-hero.compact{padding:2.2rem}
.aq26-kicker{letter-spacing:.22em;font-weight:900;font-size:.82rem}
.aq26-hero h1{font-size:clamp(2rem,5vw,3.5rem);line-height:1.02;margin:.2rem 0 1rem}
.aq26-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:1rem;margin:1rem 0 1.5rem}
.aq26-card,.aq26-section,.aq26-chart-panel,.aq26-download-card{background:rgba(255,255,255,.94);border:1px solid rgba(10,45,80,.12);border-radius:20px;padding:1.3rem;box-shadow:0 10px 28px rgba(5,35,70,.08)}
.aq26-card-label{text-transform:uppercase;letter-spacing:.16em;color:var(--aq26-muted);font-size:.78rem;font-weight:900}
.aq26-card-value{font-size:2rem;font-weight:900;margin:.4rem 0;color:var(--aq26-navy)}
.aq26-section{margin:1.2rem 0}
.aq26-chart-grid,.aq26-download-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:1rem}
.aq26-chart-panel{display:flex;justify-content:space-between;align-items:center;gap:1rem;min-height:150px}
.aq26-small-link,.aq26-download-card{color:var(--aq26-navy);text-decoration:none;font-weight:800}
.aq26-download-card{display:flex;flex-direction:column;gap:.35rem}
.aq26-download-card.pending{opacity:.75}
.aq26-table{width:100%;border-collapse:collapse}
.aq26-table th,.aq26-table td{padding:.75rem;border-bottom:1px solid rgba(10,45,80,.12);text-align:left}
.aq26-footer{background:var(--aq26-navy);color:#fff;padding:2rem;margin-top:2rem}
.aq26-footer nav{display:flex;gap:.75rem;flex-wrap:wrap;margin-top:1rem}
.aq26-footer a{color:#fff}
@media (max-width:820px){
  .aq26-topbar{align-items:center}
  .aq26-menu-toggle{display:inline-flex}
  .aq26-nav{display:none;position:absolute;left:0;right:0;top:100%;background:var(--aq26-navy);padding:1rem;flex-direction:column;align-items:stretch;border-top:1px solid rgba(255,255,255,.16)}
  .aq26-nav[data-open="true"]{display:flex}
  .aq26-nav a{display:block;text-align:center;padding:.85rem 1rem}
  .aq26-brand span{display:none}
  .aq26-main{padding:1rem .75rem}
  .aq26-hero{padding:2rem 1.2rem;border-radius:22px}
  .aq26-grid,.aq26-chart-grid,.aq26-download-grid{grid-template-columns:1fr}
  .aq26-chart-panel{min-height:auto;align-items:flex-start}
}
"""
    write_text(assets / "aq26_public_polish.css", css)

    mobile_css = r"""
/* AQ26 mobile nav compatibility layer. This also targets generated legacy menus. */
@media (max-width: 820px){
  .nav-grid,.pill-nav,.desktop-nav,.site-nav:not(.aq26-nav){display:none!important}
}
"""
    write_text(assets / "aq26_mobile_nav.css", mobile_css)

    js = r"""
(function(){
  function ready(fn){ if(document.readyState !== 'loading') fn(); else document.addEventListener('DOMContentLoaded', fn); }
  ready(function(){
    var btn = document.querySelector('.aq26-menu-toggle');
    var nav = document.getElementById('aq26-mobile-menu') || document.querySelector('.aq26-nav');
    if(btn && nav){
      btn.addEventListener('click', function(){
        var open = nav.getAttribute('data-open') === 'true';
        nav.setAttribute('data-open', open ? 'false' : 'true');
        btn.setAttribute('aria-expanded', open ? 'false' : 'true');
      });
    }
    // If generated pages lack the AQ26 nav but contain legacy menu links, create mobile wrapper.
    if(!btn && !document.querySelector('.aq26-topbar')){
      var links = Array.from(document.querySelectorAll('a[href$=".html"]')).filter(function(a){
        return /Observatory|Archive|Comparisons|Source|Readiness|Methodology|Downloads/.test(a.textContent || '');
      }).slice(0,8);
      if(links.length){
        var bar = document.createElement('div');
        bar.className='aq26-topbar aq26-injected-topbar';
        bar.innerHTML='<div class="aq26-brand"><strong>SCC Nexus</strong><span>· AQ26</span></div><button class="aq26-menu-toggle" type="button" aria-expanded="false">Menu</button><nav class="aq26-nav" id="aq26-mobile-menu"></nav>';
        var nav2 = bar.querySelector('nav');
        links.forEach(function(a){ var clone=a.cloneNode(true); nav2.appendChild(clone); });
        document.body.insertBefore(bar, document.body.firstChild);
        bar.querySelector('button').addEventListener('click', function(){
          var open = nav2.getAttribute('data-open') === 'true';
          nav2.setAttribute('data-open', open ? 'false' : 'true');
          this.setAttribute('aria-expanded', open ? 'false' : 'true');
        });
      }
    }
  });
})();
"""
    write_text(assets / "aq26_mobile_nav.js", js)

def inject_head_and_script(site_root: Path) -> None:
    head_bits = [
        '<link rel="icon" type="image/svg+xml" href="assets/favicon.svg">',
        '<link rel="apple-touch-icon" href="assets/apple-touch-icon.png">',
        '<link rel="manifest" href="assets/site.webmanifest">',
        '<link rel="stylesheet" href="assets/aq26_public_polish.css">',
        '<link rel="stylesheet" href="assets/aq26_mobile_nav.css">',
    ]
    script = '<script src="assets/aq26_mobile_nav.js"></script>'
    for page in site_root.glob("*.html"):
        txt = page.read_text(encoding="utf-8", errors="ignore")
        changed = False
        low = txt.lower()
        if "</head>" in low:
            insert = "\n".join(bit for bit in head_bits if bit not in txt)
            if insert:
                txt = re.sub(r"</head>", insert + "\n</head>", txt, count=1, flags=re.I)
                changed = True
        if script not in txt and "</body>" in low:
            txt = re.sub(r"</body>", script + "\n</body>", txt, count=1, flags=re.I)
            changed = True
        if changed:
            page.write_text(txt, encoding="utf-8")

def validate_no_blank(site_root: Path) -> List[str]:
    problems: List[str] = []
    for name in CORE_PAGES:
        p = site_root / name
        if not p.exists():
            problems.append(f"{name}: missing")
            continue
        txt = p.read_text(encoding="utf-8", errors="ignore")
        plain = re.sub(r"<[^>]+>", " ", txt)
        plain = re.sub(r"\s+", " ", plain).strip()
        if len(plain) < 350:
            problems.append(f"{name}: too little visible content ({len(plain)} chars)")
        if "aq26_mobile_nav.js" not in txt:
            problems.append(f"{name}: mobile hamburger JS not injected")
    # downloads page should not have broken default CTA if no zip
    idx = site_root / "index.html"
    if idx.exists():
        txt = idx.read_text(encoding="utf-8", errors="ignore")
        if "Download evidence ZIP" in txt and "downloads/" not in txt:
            problems.append("index.html: evidence ZIP CTA may not link to downloads/")
    return problems

def build_status(site_root: Path, problems: List[str]) -> None:
    status = {
        "generated_at_utc": utc_now(),
        "site_root": str(site_root),
        "no_blank_validation_ok": not problems,
        "problems": problems,
        "core_pages": CORE_PAGES,
        "aliases": ALIASES,
    }
    write_text(site_root / "data" / "public_dashboard" / "polish_status.json", json.dumps(status, indent=2))

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--site-root", default="site_public")
    ap.add_argument("--asset-source", default="website/assets")
    ap.add_argument("--force-comparisons", action="store_true")
    ap.add_argument("--force-downloads", action="store_true")
    ap.add_argument("--force-archive", action="store_true")
    ap.add_argument("--fail-on-blank", action="store_true")
    args = ap.parse_args()

    site_root = Path(args.site_root)
    asset_source = Path(args.asset_source)
    if not site_root.exists():
        raise SystemExit(f"site root does not exist: {site_root}")

    write_mobile_assets(asset_source, site_root)
    make_latest_download_aliases(site_root)
    build_comparisons_page(site_root, force=args.force_comparisons)
    build_downloads_page(site_root, force=args.force_downloads)
    build_archive_page(site_root, force=args.force_archive)
    create_alias_pages(site_root)
    inject_head_and_script(site_root)

    problems = validate_no_blank(site_root)
    build_status(site_root, problems)

    print(json.dumps({"ok": not problems, "problems": problems, "site_root": str(site_root)}, indent=2))
    if problems and args.fail_on_blank:
        return 2
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
