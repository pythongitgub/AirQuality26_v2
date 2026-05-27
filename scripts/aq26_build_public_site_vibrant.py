#!/usr/bin/env python3
"""AQ26 vibrant public website builder.

Purpose
-------
Build a client-friendly public website from existing AQ26 JSON/CSV outputs without
leaking raw internal validation logs. This deliberately avoids blank pages: if a
payload is absent it renders a clear, professional "building" state.

It preserves site_public/data and site_public/downloads, creates consistent HTML
pages, copies branding assets, and writes CSS/JS used for moving banners and
interactive chart previews.
"""
from __future__ import annotations

import argparse
import csv
import html
import json
import re
import shutil
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

CORE_PAGES = {
    "index.html": ("AQ26 Environmental Intelligence Observatory", "Weekly air-quality and emissions intelligence"),
    "archive.html": ("Weekly Evidence Archive", "Backfill status across weekly windows"),
    "comparisons.html": ("Comparison Dashboard", "Interactive comparisons across source coverage, readiness and filings"),
    "source-records.html": ("Source Records", "Where the evidence comes from"),
    "readiness.html": ("Readiness", "Evidence gates and validation status"),
    "methodology.html": ("Methodology", "How AQ26 separates evidence, context and interpretation"),
    "downloads.html": ("Downloads", "Public evidence bundles and reports"),
    "about.html": ("About AQ26", "A public interface for environmental evidence summaries"),
    "privacy.html": ("Privacy", "How this static site handles user data"),
    "cookies.html": ("Cookies", "Essential preferences and chart assets"),
    "accessibility.html": ("Accessibility", "Readable, responsive environmental intelligence"),
    "terms.html": ("Terms", "Use of this public evidence interface"),
    "contact.html": ("Contact", "How to request clarification or review"),
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

CHART_FILES = [
    ("Weekly record counts", "data/charts/weekly_record_counts.json"),
    ("Source coverage by week", "data/charts/source_coverage_by_week.json"),
    ("Readiness trend", "data/charts/readiness_trend.json"),
    ("Satellite products by week", "data/charts/satellite_products_by_week.json"),
    ("Pollutant timeseries", "data/charts/pollutant_timeseries.json"),
    ("Official filings", "data/charts/official_filings.json"),
    ("Facility-control comparison", "data/charts/facility_control_comparison.json"),
    ("Source class summary", "data/charts/source_class_summary_latest.json"),
]


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def read_json(path: Path, default: Any = None) -> Any:
    try:
        if path.exists() and path.stat().st_size > 0:
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default
    return default


def read_csv_rows(path: Path, limit: int = 5000) -> list[dict[str, str]]:
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8", newline="") as f:
            return [row for _, row in zip(range(limit), csv.DictReader(f))]
    except Exception:
        return []


def esc(x: Any) -> str:
    return html.escape("" if x is None else str(x), quote=True)


def titleize(name: str) -> str:
    return re.sub(r"[_\-]+", " ", name).strip().title()


def as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        for key in ("records", "rows", "items", "data", "sources", "weeks", "files"):
            if isinstance(value.get(key), list):
                return value[key]
    return []


def pick_first(*vals: Any, default: Any = None) -> Any:
    for v in vals:
        if v not in (None, "", [], {}):
            return v
    return default


def count_source_records(site: Path) -> tuple[int, int, int, list[dict[str, Any]]]:
    candidates = [
        site / "data/source_records_latest.json",
        site / "data/providers/laqn/evidence_lake/source_records.json",
        site / "data/providers/laqn/source_records.json",
        site / "data/providers/earthdata/source_records.json",
    ]
    rows: list[dict[str, Any]] = []
    for p in candidates:
        data = read_json(p)
        for item in as_list(data):
            if isinstance(item, dict):
                item = dict(item)
                item.setdefault("_source_file", str(p.relative_to(site)))
                rows.append(item)
    csv_path = site / "data/source_records_latest.csv"
    for row in read_csv_rows(csv_path, 2000):
        row.setdefault("_source_file", str(csv_path.relative_to(site)))
        rows.append(row)

    seen = set()
    dedup = []
    for r in rows:
        key = json.dumps(r, sort_keys=True, default=str)[:500]
        if key not in seen:
            seen.add(key)
            dedup.append(r)
    ok = 0
    warnings = 0
    for r in dedup:
        status = str(pick_first(r.get("status"), r.get("ok"), r.get("state"), default="")).lower()
        if status in ("ok", "true", "ready", "success", "200"):
            ok += 1
        elif status in ("warning", "warn", "partial"):
            warnings += 1
    return len(dedup), ok, warnings, dedup


def weekly_rows(site: Path) -> list[dict[str, Any]]:
    data = read_json(site / "data/weekly_index.json", {})
    rows = as_list(data)
    if rows:
        return [r for r in rows if isinstance(r, dict)]
    rows = []
    for p in sorted((site / "data/history").glob("week_*.json")):
        d = read_json(p, {})
        if isinstance(d, dict):
            d.setdefault("week", p.stem.replace("week_", ""))
            rows.append(d)
    return rows


def validation_summary(site: Path) -> dict[str, Any]:
    data = read_json(site / "data/science_validation_latest.json", {})
    if not isinstance(data, dict):
        data = {}
    issues = data.get("issues") if isinstance(data.get("issues"), list) else []
    warning_count = int(pick_first(data.get("warning_count"), len([i for i in issues if str(i.get("severity", "")).lower() == "warning"]), default=0) or 0)
    error_count = int(pick_first(data.get("error_count"), len([i for i in issues if str(i.get("severity", "")).lower() == "error"]), default=0) or 0)
    ok = bool(data.get("ok")) if "ok" in data else error_count == 0
    strict = bool(data.get("strict_ready")) if "strict_ready" in data else (error_count == 0 and warning_count == 0)
    external = bool(data.get("external_grade")) if "external_grade" in data else strict
    return {
        "ok": ok,
        "strict_ready": strict,
        "external_grade": external,
        "warning_count": warning_count,
        "error_count": error_count,
        "issue_count": int(pick_first(data.get("issue_count"), len(issues), default=warning_count + error_count) or 0),
        "created_at_utc": pick_first(data.get("created_at_utc"), data.get("created_at"), default="Building"),
    }


def chart_payloads(site: Path) -> list[dict[str, Any]]:
    rows = []
    for title, rel in CHART_FILES:
        p = site / rel
        exists = p.exists() and p.stat().st_size > 2
        size = p.stat().st_size if exists else 0
        rows.append({"title": title, "rel": rel, "exists": exists, "size": size})
    return rows


def derive_stats(site: Path) -> dict[str, Any]:
    latest = read_json(site / "data/latest_summary.json", {}) or {}
    backfill = read_json(site / "data/latest_backfill_summary.json", {}) or {}
    live = read_json(site / "data/latest_live_summary.json", {}) or {}
    validation = validation_summary(site)
    source_count, ok_records, source_warnings, source_rows = count_source_records(site)
    weeks = weekly_rows(site)
    charts = chart_payloads(site)

    satellite = 0
    for p in [site / "data/charts/satellite_products_by_week.json", site / "data/providers/earthdata/granule_candidates.json"]:
        d = read_json(p)
        if isinstance(d, list):
            satellite += len(d)
        elif isinstance(d, dict):
            satellite += int(pick_first(d.get("count"), len(as_list(d)), default=0) or 0)
    drive_files = pick_first(latest.get("drive_files"), backfill.get("drive_files"), live.get("drive_files"), default=None)
    if drive_files is None:
        inv = read_json(site / "data/providers/gdrive/gdrive_recursive_inventory.json") or read_json(site / "data/gdrive_recursive_inventory.json")
        drive_files = len(as_list(inv)) if inv else "Building"
    redaction_leaks = pick_first(latest.get("redaction_leaks"), backfill.get("redaction_leaks"), live.get("redaction_leaks"), default=0)

    ready_charts = sum(1 for c in charts if c["exists"])
    harvested_weeks = len([w for w in weeks if str(pick_first(w.get("status"), w.get("harvest_status"), default="")).lower() not in ("", "not_yet_harvested", "pending")])

    return {
        "source_records": source_count or "Building",
        "ok_records": ok_records or (source_count - source_warnings if isinstance(source_count, int) and source_count else "Building"),
        "warnings": validation["warning_count"] + source_warnings,
        "errors": validation["error_count"],
        "satellite_products": satellite or "Building",
        "drive_files": drive_files,
        "redaction_leaks": redaction_leaks,
        "weeks_total": len(weeks) or "Building",
        "weeks_harvested": harvested_weeks or "Building",
        "chart_payloads": ready_charts,
        "validation": validation,
        "source_rows": source_rows,
        "weeks": weeks,
        "charts": charts,
        "latest": latest,
        "backfill": backfill,
    }


def copy_assets(site: Path, asset_source: Path) -> None:
    (site / "assets").mkdir(parents=True, exist_ok=True)
    for name in ["air_quality_web.svg", "favicon.svg", "logo_web.svg", "apple-touch-icon.png", "favicon-32x32.png", "favicon-16x16.png", "android-chrome-192x192.png", "android-chrome-512x512.png", "site.webmanifest"]:
        src = asset_source / name
        if src.exists():
            shutil.copy2(src, site / "assets" / name)
    # Root favicon helps browsers that ignore HTML link updates.
    if (site / "assets/favicon.svg").exists():
        shutil.copy2(site / "assets/favicon.svg", site / "favicon.svg")


def write_assets(site: Path) -> None:
    css = r'''
:root{--navy:#061426;--navy2:#0d2440;--blue:#155e8f;--cyan:#39d2d0;--teal:#0d7f89;--ink:#07162f;--muted:#58708b;--paper:#ffffff;--soft:#eef7fb;--line:#d8e6f0;--warn:#fff6d7;--shadow:0 18px 50px rgba(5,24,48,.14)}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;font-family:Inter,ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif;background:linear-gradient(180deg,#f6fbff 0,#eef7fb 48%,#f8fbfd 100%);color:var(--ink);line-height:1.5}.aq26-top-strip{background:var(--navy);color:#fff;font-size:.82rem;font-weight:800;display:flex;justify-content:space-between;gap:1rem;padding:.42rem 1.4rem}.aq26-header{background:#fff;border-bottom:1px solid var(--line);box-shadow:0 2px 14px rgba(5,24,48,.08);position:sticky;top:0;z-index:50}.aq26-header-inner{max-width:1400px;margin:auto;display:flex;align-items:center;justify-content:space-between;gap:1.4rem;padding:1.05rem 1.6rem}.aq26-logo{display:block;width:min(320px,34vw);max-height:82px;object-fit:contain}.aq26-nav{display:flex;flex-wrap:wrap;justify-content:flex-end;gap:.58rem}.aq26-nav a,.aq26-menu-button{display:inline-flex;align-items:center;gap:.35rem;border:1px solid #c7d9e8;border-radius:999px;background:#f3f8fc;color:#061426;text-decoration:none;font-weight:900;padding:.64rem .95rem;box-shadow:0 1px 0 rgba(255,255,255,.7) inset}.aq26-nav a:hover,.aq26-menu-button:hover{background:#e7f6fb;border-color:#7dcfda}.aq26-menu-button{display:none;font-size:1rem;cursor:pointer}.aq26-mobile-panel{display:none;padding:.5rem 1rem 1rem;background:#fff;border-top:1px solid var(--line)}.aq26-mobile-panel a{display:block;padding:.8rem 1rem;margin:.4rem 0;border-radius:1rem;background:#f1f7fb;color:#061426;text-decoration:none;font-weight:900}.aq26-main{max-width:1200px;margin:0 auto;padding:2.2rem 1.25rem 4rem}.hero{position:relative;overflow:hidden;border-radius:2rem;padding:3rem 2.2rem;color:#fff;background:linear-gradient(120deg,#123a67,#137aa0,#37c7d1);box-shadow:var(--shadow);isolation:isolate}.hero:before{content:"";position:absolute;inset:-30%;background:radial-gradient(circle at 20% 30%,rgba(255,255,255,.28),transparent 20%),radial-gradient(circle at 80% 25%,rgba(57,210,208,.35),transparent 24%),linear-gradient(90deg,transparent,rgba(255,255,255,.13),transparent);animation:aq26Float 12s ease-in-out infinite alternate;z-index:-1}.hero:after{content:"";position:absolute;inset:0;background:linear-gradient(90deg,rgba(6,20,38,.35),rgba(6,20,38,.05));z-index:-1}.eyebrow{letter-spacing:.22em;text-transform:uppercase;font-size:.82rem;color:#99fff5;font-weight:950}.hero h1{font-size:clamp(2.2rem,6vw,5.3rem);line-height:.98;margin:.7rem 0 1rem;color:#fff;text-shadow:0 4px 18px rgba(0,0,0,.2)}.hero p{font-size:clamp(1.05rem,2vw,1.35rem);max-width:820px;color:#effcff}.button-row{display:flex;flex-wrap:wrap;gap:.8rem;margin-top:1.5rem}.btn{display:inline-flex;border-radius:.95rem;padding:.82rem 1.15rem;font-weight:950;text-decoration:none;border:1px solid rgba(255,255,255,.5);background:var(--cyan);color:#031221}.btn.secondary{background:rgba(255,255,255,.16);color:#fff}.marquee{overflow:hidden;border-left:5px solid #ffc400;background:linear-gradient(90deg,#fff6d8,#effcff);border-radius:1rem;margin:1.6rem 0;padding:.7rem 0}.marquee-track{display:flex;gap:3rem;white-space:nowrap;animation:aq26Marquee 28s linear infinite}.marquee span{font-weight:850;color:#0b2748}.section-head{margin:2.2rem 0 1rem}.section-head h2{font-size:clamp(1.5rem,3vw,2.3rem);margin:.2rem 0}.section-head p{color:var(--muted);margin:.2rem 0}.grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:1rem}.grid.two{grid-template-columns:repeat(2,minmax(0,1fr))}.card{background:rgba(255,255,255,.95);border:1px solid var(--line);border-radius:1.4rem;padding:1.25rem;box-shadow:0 10px 30px rgba(5,24,48,.08);position:relative;overflow:hidden}.card:after{content:"";position:absolute;right:-20px;bottom:-35px;width:210px;height:100px;background:url('air_quality_web.svg') no-repeat center/contain;opacity:.045}.card .label{letter-spacing:.18em;text-transform:uppercase;color:#008f91;font-size:.78rem;font-weight:950}.card .metric{font-size:clamp(1.8rem,4vw,3.2rem);font-weight:950;line-height:1.05;margin:.45rem 0;color:var(--ink)}.card h3{font-size:1.35rem;margin:.2rem 0;color:var(--ink)}.card p{color:#456079}.status-good{color:#087a57}.status-warn{color:#a76b00}.status-bad{color:#b82c2c}.table-wrap{background:#fff;border:1px solid var(--line);border-radius:1.4rem;overflow:auto;box-shadow:0 10px 30px rgba(5,24,48,.08)}table{width:100%;border-collapse:collapse;min-width:700px}th,td{text-align:left;padding:.85rem 1rem;border-bottom:1px solid #e9f0f5;vertical-align:top}th{background:#07162f;color:#fff;font-size:.85rem;letter-spacing:.05em}td{color:#0b1d35}.chart-preview{height:300px;border:1px dashed #bdd4e5;border-radius:1.2rem;display:grid;place-items:center;background:linear-gradient(135deg,#fff,#f0fbff);color:#50677f;font-weight:850}.footer{background:#061426;color:#dbeaf4;margin-top:3rem;padding:2rem 1.4rem}.footer-inner{max-width:1200px;margin:auto}.footer a{color:#fff;margin-right:1rem}.pill{display:inline-flex;padding:.35rem .7rem;border-radius:999px;background:#e7fbfa;color:#006b72;font-weight:900;font-size:.82rem}.note{background:#fff7dd;border-left:5px solid #ffc400;border-radius:1rem;padding:1rem 1.2rem;margin:1.2rem 0;color:#1b2b44}.safe-summary{font-size:1.02rem}.hide{display:none!important}@keyframes aq26Float{from{transform:translateX(-2%) translateY(0) rotate(0deg)}to{transform:translateX(3%) translateY(2%) rotate(2deg)}}@keyframes aq26Marquee{0%{transform:translateX(0)}100%{transform:translateX(-50%)}}@media(max-width:880px){.aq26-top-strip{font-size:.72rem;padding:.35rem .8rem}.aq26-header-inner{padding:.8rem 1rem}.aq26-logo{width:min(230px,62vw)}.aq26-nav{display:none}.aq26-menu-button{display:inline-flex}.aq26-mobile-panel.open{display:block}.aq26-main{padding:1.2rem .85rem 3rem}.hero{padding:2rem 1.25rem;border-radius:1.35rem}.grid,.grid.two{grid-template-columns:1fr}.marquee-track{animation-duration:18s}.card{padding:1rem}}
'''
    js = r'''
(function(){
  const btn=document.querySelector('[data-aq26-menu]');
  const panel=document.querySelector('[data-aq26-mobile-panel]');
  if(btn&&panel){btn.addEventListener('click',()=>{const open=panel.classList.toggle('open');btn.setAttribute('aria-expanded',open?'true':'false');});}
  document.querySelectorAll('[data-chart-json]').forEach(async el=>{
    const url=el.getAttribute('data-chart-json');
    try{
      const r=await fetch(url,{cache:'no-store'}); if(!r.ok) throw new Error('not ok');
      const data=await r.json();
      const count=Array.isArray(data)?data.length:(Array.isArray(data.rows)?data.rows.length:(Array.isArray(data.data)?data.data.length:Object.keys(data||{}).length));
      el.innerHTML='<strong>Payload ready</strong><br><span>'+count+' records/keys available.</span><br><a class="btn" href="'+url+'">Open JSON</a>';
    }catch(e){ el.innerHTML='<strong>Preparing chart</strong><br><span>Payload will appear after the next successful backfill.</span>'; }
  });
})();
'''
    (site / "assets/aq26_vibrant.css").write_text(css, encoding="utf-8")
    (site / "assets/aq26_vibrant.js").write_text(js, encoding="utf-8")


def head(title: str) -> str:
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(title)} · AQ26</title><meta name="description" content="AQ26 public environmental evidence observatory"><link rel="icon" type="image/svg+xml" href="assets/favicon.svg?v=aq26-vibrant"><link rel="apple-touch-icon" href="assets/apple-touch-icon.png"><link rel="stylesheet" href="assets/aq26_vibrant.css?v=aq26-vibrant-20260527"></head><body>'''


def header(active: str) -> str:
    nav = "".join(f'<a href="{href}" class="{"active" if href == active else ""}">{label}</a>' for href, label in NAV)
    mobile = "".join(f'<a href="{href}">{label}</a>' for href, label in NAV)
    return f'''<div class="aq26-top-strip"><span>SCC Nexus · AQ26 weekly evidence, provenance and air-quality intelligence</span><span>Public observatory</span></div><header class="aq26-header"><div class="aq26-header-inner"><a href="index.html" aria-label="AQ26 home"><img class="aq26-logo" src="assets/air_quality_web.svg?v=aq26-vibrant" alt="SCC Nexus Air Quality Report"></a><nav class="aq26-nav" aria-label="Primary navigation">{nav}</nav><button class="aq26-menu-button" data-aq26-menu aria-expanded="false">☰ Menu</button></div><div class="aq26-mobile-panel" data-aq26-mobile-panel>{mobile}</div></header>'''


def footer() -> str:
    return '''<footer class="footer"><div class="footer-inner"><h3>AQ26 WeeklyV2</h3><p>Public interface for environmental evidence summaries; no endorsement, regulatory determination or causal attribution is claimed.</p><p><a href="about.html">About</a><a href="privacy.html">Privacy</a><a href="cookies.html">Cookies</a><a href="accessibility.html">Accessibility</a><a href="terms.html">Terms</a><a href="contact.html">Contact</a></p></div></footer><script src="assets/aq26_vibrant.js?v=aq26-vibrant-20260527"></script></body></html>'''


def hero(title: str, subtitle: str, eyebrow: str = "SCC Nexus · AQ26") -> str:
    return f'''<section class="hero"><div class="eyebrow">{esc(eyebrow)}</div><h1>{esc(title)}</h1><p>{esc(subtitle)}</p><div class="button-row"><a class="btn" href="downloads.html">Latest downloads</a><a class="btn secondary" href="comparisons.html">Explore comparisons</a></div></section>'''


def marquee(stats: dict[str, Any]) -> str:
    items = [
        f"Source records: {stats['source_records']}",
        f"Weekly windows: {stats['weeks_total']}",
        f"Chart payloads: {stats['chart_payloads']}",
        f"Warnings under review: {stats['warnings']}",
        f"Redaction leaks: {stats['redaction_leaks']}",
        "Unredacted QA kept separate from public pages",
    ]
    text = "".join(f"<span>{esc(x)}</span>" for x in items * 2)
    return f'<div class="marquee" aria-label="Evidence status ticker"><div class="marquee-track">{text}</div></div>'


def page_wrap(site: Path, filename: str, title: str, subtitle: str, body: str, eyebrow: str = "SCC Nexus · AQ26") -> None:
    html_text = head(title) + header(filename) + f'<main class="aq26-main">' + hero(title, subtitle, eyebrow) + body + '</main>' + footer()
    (site / filename).write_text(html_text, encoding="utf-8")


def render_index(site: Path, stats: dict[str, Any]) -> None:
    kpis = [
        ("Source records", stats["source_records"], "Evidence records available across public and provider payloads."),
        ("OK records", stats["ok_records"], "Records marked ready/success where status is available."),
        ("Warnings", stats["warnings"], "Reviewed in the protected evidence area before public promotion."),
        ("Satellite products", stats["satellite_products"], "Earthdata/CDSE catalogue context where available."),
        ("Drive files", stats["drive_files"], "Google Drive evidence inventory status."),
        ("Redaction leaks", stats["redaction_leaks"], "Public-safety gate for downloads and summaries."),
    ]
    cards = "".join(f'<article class="card"><div class="label">{esc(label)}</div><div class="metric">{esc(value)}</div><p>{esc(note)}</p></article>' for label, value, note in kpis)
    body = marquee(stats) + f'''
<section class="section-head"><h2>Latest evidence status</h2><p>A client-friendly summary of the evidence pipeline. Detailed QA remains protected.</p></section><section class="grid">{cards}</section>
<section class="section-head"><h2>What this means</h2><p>AQ26 is being built as a weekly evidence and provenance platform, not a causal-attribution claim engine.</p></section>
<section class="grid"><article class="card"><div class="label">Evidence</div><h3>Weekly</h3><p>Backfill outputs and public summaries are refreshed by the AQ26 workflow.</p></article><article class="card"><div class="label">Coverage</div><h3>Multi-source</h3><p>Ground monitoring, weather, official records, satellite catalogue and reanalysis context are cross-referenced.</p></article><article class="card"><div class="label">Integrity</div><h3>Provenance</h3><p>Public pages use redacted summaries. Internal QA remains in the protected review area.</p></article></section>
'''
    page_wrap(site, "index.html", "AQ26 Environmental Intelligence Observatory", "Weekly air-quality and emissions intelligence", body)


def render_comparisons(site: Path, stats: dict[str, Any]) -> None:
    cards = "".join(f'''<article class="card"><div class="label">Chart payload</div><h3>{esc(c['title'])}</h3><p>{'Public chart-ready JSON is available.' if c['exists'] else 'Awaiting next successful backfill payload.'}</p><a class="btn" href="{esc(c['rel'])}">Open payload</a></article>''' for c in stats["charts"])
    previews = "".join(f'<article class="card"><h3>{esc(c["title"])}</h3><div class="chart-preview" data-chart-json="{esc(c["rel"])}">Loading preview…</div></article>' for c in stats["charts"][:4])
    body = marquee(stats) + f'''<section class="section-head"><h2>Chart-ready comparisons</h2><p>Payloads are exposed as public JSON and previewed below when available.</p></section><section class="grid two">{cards}</section><section class="section-head"><h2>Preview area</h2></section><section class="grid two">{previews}</section>'''
    page_wrap(site, "comparisons.html", "Comparison Dashboard", "Interactive comparisons across source coverage, readiness and filings", body, "AQ26 Comparisons")


def render_archive(site: Path, stats: dict[str, Any]) -> None:
    rows = stats["weeks"][:80]
    if not rows:
        tr = '<tr><td>Latest weekly window</td><td>Building</td><td>The next backfill will populate this table.</td></tr>'
    else:
        tr = "".join(f'<tr><td>{esc(pick_first(r.get("week"), r.get("window"), r.get("week_start"), default="Weekly window"))}</td><td>{esc(pick_first(r.get("status"), r.get("harvest_status"), default="Tracked"))}</td><td>{esc(pick_first(r.get("source_records"), r.get("records"), r.get("record_count"), default="See JSON payload"))}</td></tr>' for r in rows)
    body = marquee(stats) + f'''<section class="section-head"><h2>Weekly archive</h2><p>Historical coverage is expanded progressively. Pending weeks are shown clearly rather than hidden.</p></section><div class="table-wrap"><table><thead><tr><th>Week</th><th>Status</th><th>Evidence</th></tr></thead><tbody>{tr}</tbody></table></div>'''
    page_wrap(site, "archive.html", "Weekly Evidence Archive", "Backfill status across weekly windows", body, "AQ26 Weekly Archive")


def render_sources(site: Path, stats: dict[str, Any]) -> None:
    rows = stats["source_rows"][:80]
    if not rows:
        tr = '<tr><td>Public source records</td><td>Building</td><td>Source-record payload will be linked after the next collection run.</td></tr>'
    else:
        def cell(r: dict[str, Any], keys: Iterable[str], default: str = "—") -> str:
            return esc(pick_first(*(r.get(k) for k in keys), default=default))
        tr = "".join(f'<tr><td>{cell(r,["provider","source","name","_source_file"])}</td><td>{cell(r,["status","ok","state"])}</td><td>{cell(r,["url","endpoint","path","_source_file"])}</td></tr>' for r in rows)
    body = marquee(stats) + f'''<section class="section-head"><h2>Source records</h2><p>Public-safe view of evidence provenance. Full manifests and raw warnings remain protected.</p></section><div class="table-wrap"><table><thead><tr><th>Provider/source</th><th>Status</th><th>Reference</th></tr></thead><tbody>{tr}</tbody></table></div>'''
    page_wrap(site, "source-records.html", "Source Records", "Where the evidence comes from", body, "AQ26 Source Records")


def render_readiness(site: Path, stats: dict[str, Any]) -> None:
    v = stats["validation"]
    rows = [
        ("Public evidence pages", "Ready" if v["error_count"] == 0 else "Needs review", "Pages are generated with no-blank safeguards."),
        ("Warnings", v["warning_count"], "Warnings are summarised publicly and detailed internally."),
        ("Errors", v["error_count"], "Errors should be resolved before external submission."),
        ("External submission", "Not ready" if not v["external_grade"] else "Candidate", "No endorsement, representation or causal attribution is claimed."),
        ("Redaction", stats["redaction_leaks"], "Public downloads should remain redacted."),
    ]
    tr = "".join(f'<tr><td>{esc(a)}</td><td>{esc(b)}</td><td>{esc(c)}</td></tr>' for a, b, c in rows)
    body = marquee(stats) + f'''<section class="section-head"><h2>Readiness gates</h2><p>This is a public-safe summary. Raw validation objects, GitHub paths and issue traces are held in the protected review site.</p></section><div class="table-wrap"><table><thead><tr><th>Gate</th><th>Status</th><th>Public note</th></tr></thead><tbody>{tr}</tbody></table></div><div class="note"><strong>Review position:</strong> evidence is being assembled for controlled review. This site does not claim regulatory determination, endorsement or causal attribution.</div>'''
    page_wrap(site, "readiness.html", "Readiness", "Evidence gates and validation status", body, "AQ26 Readiness")


def render_downloads(site: Path, stats: dict[str, Any]) -> None:
    dl = site / "downloads"
    dl.mkdir(exist_ok=True)
    # Non-empty placeholder files only when missing, so buttons never 404.
    for fname, text in {"latest-evidence.zip": "AQ26 evidence bundle placeholder. The next successful backfill will replace this file.\n", "latest-report.pdf": "AQ26 public report placeholder. The next successful report build will replace this file.\n"}.items():
        p = dl / fname
        if not p.exists() or p.stat().st_size == 0:
            p.write_bytes(text.encode("utf-8"))
    body = marquee(stats) + '''<section class="section-head"><h2>Public downloads</h2><p>Only redacted, public-safe evidence bundles should be linked here.</p></section><section class="grid"><article class="card"><div class="label">Evidence bundle</div><h3>Latest evidence ZIP</h3><p>Stable link for the current public evidence bundle.</p><a class="btn" href="downloads/latest-evidence.zip">Download ZIP</a></article><article class="card"><div class="label">Report</div><h3>Latest public report</h3><p>Stable link for the current public report when available.</p><a class="btn" href="downloads/latest-report.pdf">Download report</a></article><article class="card"><div class="label">Validation</div><h3>Public safety</h3><p>Unredacted evidence remains password protected.</p><a class="btn secondary" href="readiness.html">View readiness</a></article></section>'''
    page_wrap(site, "downloads.html", "Downloads", "Public evidence bundles and reports", body, "AQ26 Downloads")


def render_methodology(site: Path, stats: dict[str, Any]) -> None:
    body = marquee(stats) + '''<section class="section-head"><h2>Methodology</h2><p>AQ26 separates evidence collection, provenance, QA, public presentation and expert interpretation.</p></section><section class="grid"><article class="card"><div class="label">1</div><h3>Collect</h3><p>Gather source records from monitoring, meteorology, official filings, satellite catalogues and news/context providers.</p></article><article class="card"><div class="label">2</div><h3>Validate</h3><p>Track source status, warnings, errors, schema readiness and redaction gates before public promotion.</p></article><article class="card"><div class="label">3</div><h3>Present</h3><p>Show accessible public summaries while keeping detailed QA and raw manifests in the protected review area.</p></article></section>'''
    page_wrap(site, "methodology.html", "Methodology", "How AQ26 separates evidence, context and interpretation", body, "AQ26 Methodology")


def render_static(site: Path, filename: str, stats: dict[str, Any]) -> None:
    title, subtitle = CORE_PAGES[filename]
    content = {
        "about.html": "AQ26 is an evidence and provenance interface for environmental intelligence summaries. It is designed to make weekly air-quality and emissions context easier to review without overstating causality.",
        "privacy.html": "This static public site does not intentionally collect personal data. Server logs may be handled by the hosting provider. Protected review content is kept separate.",
        "cookies.html": "AQ26 uses essential local-storage preferences and may load chart assets for interactive views. No advertising cookies are intentionally set.",
        "accessibility.html": "The site aims for readable contrast, responsive navigation and plain-English summaries. Further improvements will follow as content matures.",
        "terms.html": "AQ26 public pages provide evidence summaries only. No endorsement, regulatory determination, representation or causal attribution is claimed.",
        "contact.html": "For questions, use the contact route provided by SCC Nexus or request clarification through the project owner.",
    }.get(filename, subtitle)
    body = marquee(stats) + f'<section class="section-head"><h2>{esc(title)}</h2><p>{esc(subtitle)}</p></section><article class="card"><p>{esc(content)}</p></article>'
    page_wrap(site, filename, title, subtitle, body)


def write_alias(site: Path, filename: str, target: str, title: str) -> None:
    (site / filename).write_text(head(title) + header(target) + f'<main class="aq26-main"><section class="card"><h1>{esc(title)}</h1><p>This page has moved to <a href="{esc(target)}">{esc(target)}</a>.</p></section></main>' + footer(), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--site-root", default="site_public")
    ap.add_argument("--asset-source", default="website/assets")
    ap.add_argument("--summary", default=None)
    args = ap.parse_args()
    site = Path(args.site_root)
    assets = Path(args.asset_source)
    site.mkdir(parents=True, exist_ok=True)
    (site / "data").mkdir(exist_ok=True)
    copy_assets(site, assets)
    write_assets(site)
    stats = derive_stats(site)

    render_index(site, stats)
    render_archive(site, stats)
    render_comparisons(site, stats)
    render_sources(site, stats)
    render_readiness(site, stats)
    render_methodology(site, stats)
    render_downloads(site, stats)
    for fn in ["about.html", "privacy.html", "cookies.html", "accessibility.html", "terms.html", "contact.html"]:
        render_static(site, fn, stats)
    write_alias(site, "historical-comparisons.html", "comparisons.html", "Historical comparisons")
    write_alias(site, "weekly-archive.html", "archive.html", "Weekly archive")
    write_alias(site, "evidence-downloads.html", "downloads.html", "Evidence downloads")
    (site / "robots.txt").write_text("User-agent: *\nAllow: /\n", encoding="utf-8")
    (site / "sitemap.txt").write_text("\n".join(CORE_PAGES.keys()) + "\n", encoding="utf-8")

    summary = {
        "ok": True,
        "built_at": now_utc(),
        "site_root": str(site),
        "core_pages": sorted(CORE_PAGES.keys()),
        "stats": {k: v for k, v in stats.items() if k not in ("source_rows", "weeks", "charts", "latest", "backfill", "validation")},
        "chart_payloads_ready": stats["chart_payloads"],
    }
    out = Path(args.summary) if args.summary else site / "data/public_vibrant_site_summary.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2, sort_keys=True, default=str), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
