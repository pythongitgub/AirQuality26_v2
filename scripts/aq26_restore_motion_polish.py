#!/usr/bin/env python3
"""
AQ26 restore motion + public polish.

Purpose:
- restore a professional animated/moving banner feel without creating blank pages;
- keep the white branded header;
- make public pages readable and non-technical;
- summarise readiness issues instead of dumping raw JSON/Python lists;
- leave real data payloads in site_public/data untouched for later backfill.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

CORE_PAGES = {
    "index.html": ("AQ26 Environmental Intelligence Observatory", "Weekly air-quality and emissions intelligence", "Public dashboard for evidence, provenance and source readiness."),
    "archive.html": ("Weekly evidence archive", "Backfill windows and weekly evidence status", "Track which evidence windows are complete, partial or awaiting harvest."),
    "comparisons.html": ("Comparison charts", "Interactive weekly comparisons", "Compare source coverage, readiness, filings and context signals."),
    "source-records.html": ("Source Records", "Where the evidence comes from", "Readable provenance summaries for public review."),
    "readiness.html": ("Readiness", "Evidence gates and validation status", "Plain-English readiness status, warnings and next actions."),
    "methodology.html": ("Methodology", "How AQ26 validates evidence", "A transparent explanation of collection, validation and limitations."),
    "downloads.html": ("Downloads", "Public evidence bundles and reports", "Download public/redacted bundles when available."),
    "about.html": ("About AQ26", "Environmental evidence intelligence", "Project overview and scope."),
    "privacy.html": ("Privacy", "Privacy and data handling", "How this static site handles visitor privacy."),
    "cookies.html": ("Cookies", "Cookie notice", "Essential preferences and chart assets only."),
    "accessibility.html": ("Accessibility", "Accessible environmental intelligence", "Design commitments for usable public pages."),
    "terms.html": ("Terms", "Use of this evidence website", "Important limitations and no-endorsement notice."),
    "contact.html": ("Contact", "Contact SCC Nexus / AQ26", "How to request review or provide feedback."),
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

CSS = r'''
:root{
  --aq26-navy:#061528;
  --aq26-ink:#0b1d3a;
  --aq26-muted:#47627f;
  --aq26-line:#d9e5f2;
  --aq26-bg:#f5f9fd;
  --aq26-card:#ffffff;
  --aq26-teal:#42d4cb;
  --aq26-cyan:#1f9ed5;
  --aq26-warn:#fff4cf;
  --aq26-warn-border:#f2b600;
  --aq26-green:#e7fbf4;
  --aq26-red:#ffe8e8;
  --radius:24px;
  --shadow:0 18px 50px rgba(9, 29, 55, .12);
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;background:linear-gradient(180deg,#eef6fb 0%,#ffffff 35%,#f7fbff 100%);color:var(--aq26-ink);font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",Arial,sans-serif;line-height:1.55}
a{color:#075c91;text-decoration-thickness:1px;text-underline-offset:3px}
.aq26-topbar{background:var(--aq26-navy);color:#fff;font-size:.86rem;font-weight:800;letter-spacing:.01em;padding:.42rem 1.2rem;display:flex;justify-content:space-between;gap:1rem;align-items:center}
.aq26-main-header{background:#fff;border-bottom:1px solid var(--aq26-line);box-shadow:0 3px 14px rgba(16,42,67,.06);position:sticky;top:0;z-index:20}
.aq26-header-inner{max-width:1260px;margin:0 auto;padding:1.1rem 1.35rem;display:grid;grid-template-columns:320px 1fr auto;gap:1rem;align-items:center}
.aq26-logo{display:flex;align-items:center;text-decoration:none;min-width:0}.aq26-logo img{width:min(292px,34vw);height:auto;display:block}.aq26-mode{justify-self:center;border:1px solid #d4e4f2;background:#f2f7fb;color:#27415f;border-radius:999px;padding:.48rem .85rem;font-weight:900;font-size:.85rem}.aq26-nav{display:flex;flex-wrap:wrap;gap:.55rem;justify-content:flex-end}.aq26-nav a{display:inline-flex;align-items:center;border:1px solid #cfdeeb;background:#f4f8fc;color:#071b34;text-decoration:none;border-radius:999px;padding:.56rem .85rem;font-weight:900;box-shadow:inset 0 -1px rgba(0,0,0,.04)}.aq26-nav a[aria-current='page'],.aq26-nav a:hover{background:var(--aq26-navy);color:#fff;border-color:var(--aq26-navy)}.aq26-menu-button{display:none;align-items:center;gap:.45rem;border:1px solid #cfdeeb;background:#fff;color:#071b34;border-radius:999px;padding:.55rem .85rem;font-weight:900;font-size:1rem}.aq26-menu-button span{font-size:1.3rem;line-height:1}
main{max-width:1260px;margin:0 auto;padding:2.1rem 1.25rem 4rem}.aq26-hero{position:relative;overflow:hidden;border-radius:32px;color:#fff;background:linear-gradient(135deg,rgba(8,32,60,.94),rgba(17,105,143,.9));box-shadow:var(--shadow);padding:3rem 3rem;margin:1rem 0 2rem;min-height:310px}.aq26-hero:before{content:"";position:absolute;inset:-20%;background:radial-gradient(circle at 15% 20%,rgba(66,212,203,.32),transparent 24%),radial-gradient(circle at 85% 35%,rgba(83,177,216,.34),transparent 26%),linear-gradient(110deg,transparent 0%,rgba(255,255,255,.13) 38%,transparent 58%);animation:aq26-sheen 11s linear infinite;opacity:.9}.aq26-hero:after{content:"PM₂.₅  NO₂  O₃  SO₂  PM₁₀";position:absolute;right:-3%;bottom:2%;font-size:clamp(2.8rem,8vw,8rem);font-weight:1000;letter-spacing:.04em;color:rgba(255,255,255,.06);white-space:nowrap}.aq26-hero-content{position:relative;z-index:1;max-width:840px}.aq26-kicker{color:#83fff2;text-transform:uppercase;font-weight:1000;letter-spacing:.18em;font-size:.88rem;margin:0 0 .65rem}.aq26-hero h1{color:#fff;margin:.15rem 0 .65rem;font-size:clamp(2.1rem,5vw,4.8rem);line-height:.98;letter-spacing:-.055em;text-shadow:0 2px 18px rgba(0,0,0,.28)}.aq26-hero p{color:#f2fbff;font-size:clamp(1.05rem,1.7vw,1.35rem);max-width:760px}.aq26-actions{display:flex;flex-wrap:wrap;gap:.8rem;margin-top:1.5rem}.aq26-btn{display:inline-flex;align-items:center;justify-content:center;border-radius:14px;padding:.82rem 1.05rem;text-decoration:none;font-weight:1000;border:1px solid rgba(255,255,255,.32)}.aq26-btn.primary{background:var(--aq26-teal);color:#061528;border-color:var(--aq26-teal)}.aq26-btn.secondary{background:rgba(255,255,255,.12);color:#fff}
.aq26-marquee{margin:1rem 0 2rem;overflow:hidden;border:1px solid #cce3f2;background:#fff;border-radius:999px;box-shadow:0 12px 32px rgba(10,40,70,.08)}.aq26-marquee-track{display:flex;gap:2rem;width:max-content;animation:aq26-marquee 28s linear infinite;padding:.78rem 1rem}.aq26-marquee span{font-weight:900;color:#12365b;white-space:nowrap}.aq26-marquee b{color:#0b857f}.aq26-note{border-left:5px solid var(--aq26-warn-border);background:var(--aq26-warn);border-radius:14px;padding:1rem 1.15rem;margin:1.5rem 0;color:#0b1d3a}.aq26-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:1.2rem;margin:1.3rem 0}.aq26-card{background:var(--aq26-card);border:1px solid var(--aq26-line);border-radius:22px;box-shadow:0 15px 35px rgba(10,40,70,.08);padding:1.25rem}.aq26-card h3{margin:.2rem 0 .5rem;color:var(--aq26-ink);font-size:1.45rem}.aq26-label{font-size:.78rem;letter-spacing:.16em;text-transform:uppercase;color:#008e8a;font-weight:1000}.aq26-card p{color:#334e68}.aq26-table-wrap{overflow:auto;background:#fff;border:1px solid var(--aq26-line);border-radius:22px;box-shadow:0 15px 35px rgba(10,40,70,.08);margin:1.2rem 0}.aq26-table{border-collapse:collapse;width:100%;min-width:720px}.aq26-table th{background:#061528;color:#fff;text-align:left;padding:1rem;font-size:.9rem}.aq26-table td{padding:.95rem 1rem;border-bottom:1px solid #e7eef7;color:#102a43;vertical-align:top}.aq26-status{display:inline-flex;border-radius:999px;padding:.28rem .65rem;font-weight:900;background:#e7fbf4;color:#075f56}.aq26-status.warn{background:#fff4cf;color:#6a4c00}.aq26-status.bad{background:#ffe8e8;color:#8a1f1f}.aq26-footer{background:#061528;color:#d7e7f6;margin-top:3rem;padding:2.2rem 1.3rem}.aq26-footer-inner{max-width:1260px;margin:0 auto;display:flex;justify-content:space-between;gap:1rem;flex-wrap:wrap}.aq26-footer a{color:#fff;margin-right:.85rem}
@keyframes aq26-sheen{0%{transform:translateX(-8%) rotate(0deg)}50%{transform:translateX(8%) rotate(1deg)}100%{transform:translateX(-8%) rotate(0deg)}}@keyframes aq26-marquee{from{transform:translateX(0)}to{transform:translateX(-50%)}}
@media(max-width:900px){.aq26-header-inner{grid-template-columns:1fr auto;padding:.85rem 1rem}.aq26-logo img{width:230px}.aq26-mode{display:none}.aq26-menu-button{display:inline-flex}.aq26-nav{grid-column:1/-1;display:none;flex-direction:column;align-items:stretch;gap:.5rem}.aq26-nav.is-open{display:flex}.aq26-nav a{justify-content:center}.aq26-hero{padding:2rem 1.3rem;border-radius:24px;min-height:auto}.aq26-grid{grid-template-columns:1fr}.aq26-topbar{font-size:.75rem}.aq26-topbar span:last-child{display:none}}
@media(prefers-reduced-motion:reduce){.aq26-hero:before,.aq26-marquee-track{animation:none}}
'''

JS = r'''
(function(){
  function initMenu(){
    var btn=document.querySelector('[data-aq26-menu]');
    var nav=document.querySelector('.aq26-nav');
    if(!btn||!nav) return;
    btn.addEventListener('click',function(){
      var open=nav.classList.toggle('is-open');
      btn.setAttribute('aria-expanded', open?'true':'false');
    });
  }
  function initReadinessSummary(){
    var el=document.querySelector('[data-readiness-json]');
    if(!el) return;
  }
  document.addEventListener('DOMContentLoaded',function(){initMenu();initReadinessSummary();});
})();
'''

def read_json(path: Path) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return None
    return None

def copy_asset(src_dir: Path, site: Path, name: str, fallback: str = "") -> None:
    dst = site / "assets" / name
    dst.parent.mkdir(parents=True, exist_ok=True)
    src = src_dir / name
    if src.exists() and src.is_file():
        shutil.copy2(src, dst)
    elif fallback and not dst.exists():
        dst.write_text(fallback, encoding='utf-8')

def ensure_assets(site: Path, asset_source: Path) -> None:
    (site / "assets").mkdir(parents=True, exist_ok=True)
    copy_asset(asset_source, site, "air_quality_web.svg")
    copy_asset(asset_source, site, "favicon.svg")
    # if user asset missing, preserve existing or create simple SVG fallback
    if not (site / "assets" / "air_quality_web.svg").exists():
        (site / "assets" / "air_quality_web.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg" width="520" height="140" viewBox="0 0 520 140"><rect fill="#fff" width="520" height="140"/><text x="20" y="58" font-family="Arial" font-size="38" font-weight="700" fill="#102a43">SCC Nexus</text><text x="20" y="102" font-family="Arial" font-size="30" fill="#35b9cf">Air Quality Report</text></svg>', encoding='utf-8')
    if not (site / "assets" / "favicon.svg").exists():
        (site / "assets" / "favicon.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64"><rect rx="12" width="64" height="64" fill="#fff"/><path d="M14 32 32 12l18 20-18 20z" fill="none" stroke="#1fb7c9" stroke-width="8"/></svg>', encoding='utf-8')
    (site / "assets" / "aq26_motion_polish.css").write_text(CSS, encoding='utf-8')
    (site / "assets" / "aq26_motion_polish.js").write_text(JS, encoding='utf-8')


def nav_html(current: str) -> str:
    links=[]
    for label, href in NAV:
        cur = " aria-current='page'" if href == current else ""
        links.append(f"<a href='{href}'{cur}>{html.escape(label)}</a>")
    return "".join(links)


def page_shell(site: Path, filename: str, title: str, subtitle: str, intro: str, body: str, mode: str="Public observatory") -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{html.escape(title)} - AQ26</title>
  <meta name="description" content="{html.escape(intro)}">
  <link rel="icon" type="image/svg+xml" href="assets/favicon.svg?v=aq26-motion-20260527">
  <link rel="stylesheet" href="assets/aq26_motion_polish.css?v=aq26-motion-20260527">
</head>
<body>
  <div class="aq26-topbar"><span>SCC Nexus · AQ26 Weekly evidence, provenance and air-quality intelligence</span><span>{html.escape(mode)}</span></div>
  <header class="aq26-main-header">
    <div class="aq26-header-inner">
      <a class="aq26-logo" href="index.html" aria-label="AQ26 home"><img src="assets/air_quality_web.svg?v=aq26-motion-20260527" alt="SCC Nexus Air Quality Report"></a>
      <span class="aq26-mode">{html.escape(mode)}</span>
      <button class="aq26-menu-button" type="button" data-aq26-menu aria-expanded="false"><span>☰</span> Menu</button>
      <nav class="aq26-nav" aria-label="Primary navigation">{nav_html(filename)}</nav>
    </div>
  </header>
  <main>
    <section class="aq26-hero">
      <div class="aq26-hero-content">
        <p class="aq26-kicker">SCC Nexus · AQ26</p>
        <h1>{html.escape(title)}</h1>
        <p>{html.escape(subtitle)}</p>
        <div class="aq26-actions"><a class="aq26-btn primary" href="downloads.html">Latest downloads</a><a class="aq26-btn secondary" href="comparisons.html">Explore comparisons</a></div>
      </div>
    </section>
    <section class="aq26-marquee" aria-label="AQ26 evidence highlights"><div class="aq26-marquee-track">
      <span><b>Evidence</b> · weekly source records</span><span><b>Coverage</b> · ground monitoring + weather + official filings</span><span><b>Integrity</b> · redaction and provenance checks</span><span><b>Readiness</b> · science gates before external submission</span>
      <span><b>Evidence</b> · weekly source records</span><span><b>Coverage</b> · ground monitoring + weather + official filings</span><span><b>Integrity</b> · redaction and provenance checks</span><span><b>Readiness</b> · science gates before external submission</span>
    </div></section>
    {body}
  </main>
  <footer class="aq26-footer"><div class="aq26-footer-inner"><div><strong>AQ26 WeeklyV2</strong><br>Public interface for environmental evidence summaries; no endorsement, regulatory determination or causal attribution is claimed.</div><nav><a href="about.html">About</a><a href="privacy.html">Privacy</a><a href="cookies.html">Cookies</a><a href="accessibility.html">Accessibility</a><a href="terms.html">Terms</a><a href="contact.html">Contact</a></nav></div></footer>
  <script src="assets/aq26_motion_polish.js?v=aq26-motion-20260527"></script>
</body>
</html>
"""

def latest_data_summary(site: Path) -> Dict[str, Any]:
    candidates = [
        site / "data" / "latest_summary.json",
        site / "data" / "latest_live_summary.json",
        site / "data" / "latest_backfill_summary.json",
        site / "data" / "weekly_index.json",
    ]
    out={}
    for c in candidates:
        data=read_json(c)
        if isinstance(data, dict):
            out.update(data)
    return out


def make_home(site: Path) -> str:
    data = latest_data_summary(site)
    cards = [
        ("Evidence", "Weekly", "Backfill outputs and public summaries are refreshed by the AQ26 workflow."),
        ("Coverage", "Multi-source", "Ground monitoring, weather, official records and satellite/reanalysis context."),
        ("Integrity", "Provenance", "Public pages use redacted summaries. Internal QA remains in the protected review area."),
    ]
    body = '<div class="aq26-note"><strong>AQ26 Environmental Intelligence Observatory:</strong> this public site shows plain-English summaries while deeper QA and provenance remain in the protected review area.</div>'
    body += '<h2>Weekly air-quality and emissions intelligence</h2><div class="aq26-grid">'
    for label, head, text in cards:
        body += f'<article class="aq26-card"><div class="aq26-label">{label}</div><h3>{head}</h3><p>{text}</p></article>'
    body += '</div>'
    return body


def make_archive(site: Path) -> str:
    wi = read_json(site / "data" / "weekly_index.json")
    rows=[]
    if isinstance(wi, dict):
        weeks = wi.get("weeks") or wi.get("history") or wi.get("weekly") or []
        if isinstance(weeks, list):
            for w in weeks[:30]:
                if isinstance(w, dict):
                    label = w.get("week") or w.get("window") or w.get("start_date") or w.get("id") or "Weekly window"
                    status = w.get("status") or ("Harvested" if w.get("harvested") else "Pending")
                    rows.append((str(label), str(status), "Weekly evidence window tracked by AQ26."))
    if not rows:
        rows=[("Latest weekly window", "Awaiting next backfill index", "The archive will expand after the next successful weekly run." )]
    return table_body("Weekly backfill windows", ["Week", "Status", "Note"], rows)


def table_body(heading: str, headers: List[str], rows: Iterable[Tuple[Any,...]]) -> str:
    out=f"<h2>{html.escape(heading)}</h2><div class='aq26-table-wrap'><table class='aq26-table'><thead><tr>"
    for h in headers: out += f"<th>{html.escape(str(h))}</th>"
    out += "</tr></thead><tbody>"
    for row in rows:
        out += "<tr>" + "".join(f"<td>{html.escape(str(cell))}</td>" for cell in row) + "</tr>"
    out += "</tbody></table></div>"
    return out


def make_comparisons(site: Path) -> str:
    chart_dir = site / "data" / "charts"
    files = sorted(chart_dir.glob("*.json")) if chart_dir.exists() else []
    rows=[]
    for f in files[:12]:
        rows.append((f.stem.replace("_"," ").title(), f"data/charts/{f.name}", "Available chart payload"))
    if not rows:
        rows=[("Weekly record counts", "Awaiting chart payload", "Run the WeeklyV2 backfill to populate interactive comparison charts."), ("Source coverage", "Awaiting chart payload", "Coverage summaries will appear after the next build." )]
    return '<div class="aq26-note"><strong>Comparison charts:</strong> animated and interactive chart panels are restored as chart payloads become available.</div>' + table_body("Available comparison payloads", ["Chart", "Payload", "Status"], rows)


def make_source_records(site: Path) -> str:
    paths = [site/"data"/"source_records_latest.json", site/"data"/"source_records.json"]
    recs=[]
    for p in paths:
        data=read_json(p)
        if isinstance(data, list): recs=data; break
        if isinstance(data, dict) and isinstance(data.get("records"), list): recs=data["records"]; break
    rows=[]
    for r in recs[:25] if isinstance(recs,list) else []:
        if isinstance(r,dict):
            rows.append((r.get("provider") or r.get("source") or "Source", r.get("status") or r.get("ok") or "Tracked", r.get("note") or r.get("path") or "AQ26 source record"))
    if not rows:
        rows=[("WeeklyV2", "Tracked", "Source records are generated by each evidence run."), ("LAQN / OpenAQ / Weather / Official records", "Tracked", "Providers are summarised publicly and reviewed internally." )]
    return table_body("Public source provenance", ["Source", "Status", "Note"], rows)


def make_readiness(site: Path) -> str:
    data = read_json(site / "data" / "science_validation_latest.json") or read_json(site / "data" / "readiness_latest.json") or {}
    rows=[]
    if isinstance(data, dict):
        ok = data.get("ok") or data.get("ok_ready") or data.get("ready")
        strict = data.get("strict_ready") or data.get("external_grade")
        warnings = data.get("warning_count") or data.get("warnings") or data.get("issue_count") or 0
        errors = data.get("error_count") or data.get("errors") or 0
        rows.append(("Validation status", "Ready" if ok is True else "In review", "Latest science and evidence gates are tracked by AQ26."))
        rows.append(("External submission", "Not ready" if not strict else "Candidate", "Public site must not imply endorsement or causal attribution."))
        rows.append(("Warnings", warnings, "Warnings are summarised here; full issue logs remain in the internal review area."))
        rows.append(("Errors", errors, "Errors must be resolved before formal external submission."))
    else:
        rows=[]
    if not rows:
        rows=[("Validation status", "In review", "Run the WeeklyV2 science backfill to refresh readiness gates."), ("External submission", "Not ready", "No endorsement, representation or causal attribution is claimed." )]
    body='<div class="aq26-note"><strong>Readiness summary:</strong> detailed raw validation logs are kept out of public pages and reviewed in the protected unredacted area.</div>'
    body+=table_body("Evidence gates", ["Gate", "Status", "Plain-English note"], rows)
    return body


def make_methodology(site: Path) -> str:
    body='<div class="aq26-grid">'
    items=[("Collect", "AQ26 collects provider records from ground monitoring, weather, official filings, satellite catalogue discovery and contextual sources."), ("Validate", "Each run produces source records, integrity ledgers and readiness gates."), ("Publish", "Only redacted, plain-English public summaries should be promoted to the public website."),]
    for h,t in items: body+=f'<article class="aq26-card"><div class="aq26-label">Method</div><h3>{h}</h3><p>{t}</p></article>'
    body+='</div>'
    return body


def make_downloads(site: Path) -> str:
    downloads = site / "downloads"
    rows=[]
    if downloads.exists():
        for f in sorted(downloads.iterdir()):
            if f.is_file(): rows.append((f.name, f"downloads/{f.name}", f"{f.stat().st_size:,} bytes"))
    if not rows:
        downloads.mkdir(parents=True, exist_ok=True)
        (downloads/"latest-evidence.zip").write_bytes(b"AQ26 public evidence placeholder. Run backfill to replace this file.\n")
        (downloads/"latest-report.pdf").write_bytes(b"AQ26 public report placeholder. Run backfill to replace this file.\n")
        rows=[("latest-evidence.zip", "downloads/latest-evidence.zip", "Placeholder until next redacted evidence bundle"), ("latest-report.pdf", "downloads/latest-report.pdf", "Placeholder until next public report")]
    return table_body("Latest public downloads", ["File", "Link", "Status"], rows)


def make_simple(title: str, subtitle: str, intro: str) -> str:
    return f'<article class="aq26-card"><h2>{html.escape(title)}</h2><p>{html.escape(intro or subtitle)}</p><p>This page is maintained as part of the AQ26 public evidence interface.</p></article>'


def body_for(site: Path, filename: str, title: str, subtitle: str, intro: str) -> str:
    if filename == "index.html": return make_home(site)
    if filename == "archive.html": return make_archive(site)
    if filename == "comparisons.html": return make_comparisons(site)
    if filename == "source-records.html": return make_source_records(site)
    if filename == "readiness.html": return make_readiness(site)
    if filename == "methodology.html": return make_methodology(site)
    if filename == "downloads.html": return make_downloads(site)
    return make_simple(title, subtitle, intro)


def write_pages(site: Path, asset_source: Path, force: bool) -> None:
    site.mkdir(parents=True, exist_ok=True)
    ensure_assets(site, asset_source)
    for filename,(title,subtitle,intro) in CORE_PAGES.items():
        body = body_for(site, filename, title, subtitle, intro)
        content = page_shell(site, filename, title, subtitle, intro, body)
        path=site/filename
        if force or not path.exists() or len(path.read_text(encoding='utf-8', errors='ignore').strip()) < 1000:
            path.write_text(content, encoding='utf-8')
    for alias,target in ALIASES.items():
        content=f"<!doctype html><meta charset='utf-8'><meta http-equiv='refresh' content='0; url={target}'><link rel='canonical' href='{target}'><title>Redirecting - AQ26</title><p>Redirecting to <a href='{target}'>{target}</a>.</p>"
        (site/alias).write_text(content, encoding='utf-8')
    (site/"robots.txt").write_text("User-agent: *\nAllow: /\n", encoding='utf-8')
    (site/"sitemap.txt").write_text("\n".join(CORE_PAGES.keys())+"\n", encoding='utf-8')


def validate(site: Path) -> Dict[str,Any]:
    problems=[]
    for filename in CORE_PAGES:
        p=site/filename
        if not p.exists(): problems.append(f"{filename}: missing")
        else:
            text=p.read_text(encoding='utf-8', errors='ignore')
            if len(re.sub(r"<[^>]+>", "", text).strip()) < 80: problems.append(f"{filename}: too little readable content")
            if "aq26_motion_polish.css" not in text: problems.append(f"{filename}: missing motion polish css")
            if "air_quality_web.svg" not in text: problems.append(f"{filename}: missing header logo")
    return {"ok": not problems, "problems": problems, "site_root": str(site), "checked_at_utc": datetime.now(timezone.utc).isoformat()}


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--site-root', default='site_public')
    ap.add_argument('--asset-source', default='website/assets')
    ap.add_argument('--force', action='store_true')
    ap.add_argument('--validate-only', action='store_true')
    ap.add_argument('--summary', default='')
    args=ap.parse_args()
    site=Path(args.site_root)
    assets=Path(args.asset_source)
    if not args.validate_only:
        write_pages(site, assets, args.force)
    result=validate(site)
    print(json.dumps(result, indent=2))
    if args.summary:
        sp=Path(args.summary); sp.parent.mkdir(parents=True, exist_ok=True); sp.write_text(json.dumps(result, indent=2), encoding='utf-8')
    if not result['ok']:
        raise SystemExit(2)

if __name__ == '__main__':
    main()
