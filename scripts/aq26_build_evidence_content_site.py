#!/usr/bin/env python3
from __future__ import annotations
import csv, json, shutil
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any, Iterable

ROOT = Path.cwd()
PUBLIC = ROOT / "site_public"
UNRED = ROOT / "site_unredacted"
SEED = ROOT / "content_seed" / "site_unredacted"

def ensure_dirs() -> None:
    for p in [PUBLIC, UNRED, UNRED / "data", UNRED / "downloads", PUBLIC / "assets", UNRED / "assets"]:
        p.mkdir(parents=True, exist_ok=True)

def copy_seed_if_missing() -> None:
    if (SEED / "data").exists():
        shutil.copytree(SEED / "data", UNRED / "data", dirs_exist_ok=True)
    if (SEED / "downloads").exists():
        shutil.copytree(SEED / "downloads", UNRED / "downloads", dirs_exist_ok=True)

def read_json(rel: str, default: Any) -> Any:
    for base in [UNRED, SEED]:
        p = base / rel
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                return default
    return default

def read_csv(rel: str, limit: int | None = None) -> list[dict[str, str]]:
    for base in [UNRED, SEED]:
        p = base / rel
        if p.exists():
            with p.open(newline="", encoding="utf-8", errors="replace") as f:
                rows = list(csv.DictReader(f))
                return rows if limit is None else rows[:limit]
    return []

def safe(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, (dict, list)):
        v = json.dumps(v, ensure_ascii=False)
    return escape(str(v))

def val(d: dict[str, Any], *keys: str, default: Any = "") -> Any:
    cur: Any = d
    for k in keys:
        if isinstance(cur, dict) and k in cur:
            cur = cur[k]
        else:
            return default
    return cur

def table(rows: list[dict[str, Any]], columns: list[tuple[str, str]], empty: str = "No records available yet.") -> str:
    if not rows:
        return f'<p class="muted">{escape(empty)}</p>'
    head = "".join(f"<th>{escape(label)}</th>" for _, label in columns)
    body = []
    for r in rows:
        cells = "".join(f"<td>{safe(r.get(key, ''))}</td>" for key, _ in columns)
        body.append(f"<tr>{cells}</tr>")
    return f'<div class="table-wrap"><table><thead><tr>{head}</tr></thead><tbody>{"".join(body)}</tbody></table></div>'

def card_grid(items: Iterable[tuple[str, Any, str]]) -> str:
    out = []
    for label, value, note in items:
        out.append(f'<article class="metric"><strong>{safe(value)}</strong><span>{escape(label)}</span><small>{escape(note)}</small></article>')
    return '<section class="metrics">' + ''.join(out) + '</section>'

def status_badge(x: Any) -> str:
    if x is True:
        return '<span class="badge good">ready</span>'
    if x is False:
        return '<span class="badge warn">not ready</span>'
    return f'<span class="badge">{safe(x)}</span>'

STYLE = """
:root{--bg:#07131f;--panel:#0f2133;--panel2:#132b43;--text:#eef7ff;--muted:#b8c8d8;--line:#29435c;--accent:#64d2ff;--gold:#f4c45f;--good:#77dd99;--warn:#ffb86b;--bad:#ff7b7b;--white:#fff;--ink:#122235}*{box-sizing:border-box}body{margin:0;font-family:Inter,system-ui,-apple-system,Segoe UI,Arial,sans-serif;background:linear-gradient(180deg,#07131f,#10263b 45%,#f5f8fb 45%);color:var(--ink)}a{color:#095e93}header.hero{background:radial-gradient(circle at 20% 0%,#1f7fb2,#07131f 55%);color:var(--text);padding:0 0 2rem}.nav{max-width:1180px;margin:auto;display:flex;align-items:center;justify-content:space-between;padding:1rem}.brand{display:flex;gap:.7rem;align-items:center;color:var(--text);text-decoration:none}.brand-mark{background:#fff;color:#0d4971;border-radius:14px;padding:.6rem;font-weight:900}.burger{display:none;background:#fff;color:#10263b;border:0;border-radius:12px;padding:.65rem .8rem;font-weight:800}.menu{display:flex;gap:.45rem;flex-wrap:wrap}.menu a{color:#eaf7ff;text-decoration:none;padding:.55rem .7rem;border:1px solid rgba(255,255,255,.18);border-radius:999px;font-size:.92rem}.hero-inner{max-width:1180px;margin:auto;padding:2rem 1rem 1rem}.eyebrow{text-transform:uppercase;letter-spacing:.12em;color:var(--gold);font-weight:800;font-size:.82rem}.hero h1{font-size:clamp(2rem,5vw,4rem);line-height:1;margin:.3rem 0}.hero p{font-size:1.15rem;color:#d8e7f2;max-width:850px}.container{max-width:1180px;margin:-1.8rem auto 0;padding:0 1rem 3rem}.panel{background:var(--white);border:1px solid #dce6ef;border-radius:24px;padding:1.35rem;margin:1rem 0;box-shadow:0 14px 30px rgba(5,22,38,.08)}.panel.dark{background:var(--panel);color:var(--text);border-color:var(--line)}.panel.dark p,.panel.dark li{color:var(--muted)}.metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:.85rem;margin:1rem 0}.metric{background:#fff;border:1px solid #dae6ef;border-radius:18px;padding:1rem}.metric strong{font-size:2rem;display:block;color:#0d5e8c}.metric span{font-weight:800;display:block}.metric small{color:#607487}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:1rem}.callout{border-left:6px solid var(--accent);background:#eef9ff;padding:1rem;border-radius:16px}.warnbox{border-left:6px solid var(--warn);background:#fff7ed;padding:1rem;border-radius:16px}.table-wrap{overflow:auto;border:1px solid #dbe8f0;border-radius:18px}table{border-collapse:collapse;width:100%;font-size:.9rem;background:white}th,td{padding:.75rem;border-bottom:1px solid #e7eef5;text-align:left;vertical-align:top}th{background:#edf6fb;color:#14314a;position:sticky;top:0}code,pre{background:#eef4f9;padding:.5rem;border-radius:8px;white-space:pre-wrap}.badge{display:inline-block;border-radius:999px;background:#e8eff6;padding:.2rem .55rem;font-weight:800;font-size:.8rem}.badge.good{background:#dff8e8;color:#126530}.badge.warn{background:#fff1dc;color:#8a4a00}.badge.bad{background:#ffe1e1;color:#9b1c1c}.muted{color:#607487}.footer{background:#07131f;color:#dbeaf6;padding:2rem 1rem}.footer-inner{max-width:1180px;margin:auto;display:grid;grid-template-columns:2fr 1fr 1fr;gap:1rem}.footer a{color:#dbeaf6}.download-list a{display:block;padding:.8rem;margin:.4rem 0;background:#eef8ff;border-radius:12px;text-decoration:none;font-weight:800}.timeline{border-left:4px solid #b6dbea;padding-left:1rem}.timeline article{margin:.9rem 0;padding:.8rem;background:#f7fbff;border-radius:14px}@media(max-width:780px){.burger{display:block}.menu{display:none;flex-direction:column;width:100%;padding:0 1rem 1rem}.menu.open{display:flex}.nav{align-items:flex-start;flex-wrap:wrap}.menu a{width:100%;border-radius:12px}.footer-inner{grid-template-columns:1fr}.container{margin-top:-1rem}.hero h1{font-size:2.4rem}}
"""
SCRIPT = "function aq26ToggleMenu(){var m=document.getElementById('aq26-menu'); if(m){m.classList.toggle('open');}}"
NAV = [("index.html", "Overview"),("newhaven.html", "Newhaven"),("weekly-update.html", "Weekly"),("evidence.html", "Evidence"),("source-records.html", "Sources"),("candidates.html", "Candidates"),("diagnostics.html", "Diagnostics"),("downloads.html", "Downloads")]
LEGAL = [("privacy.html","Privacy"),("terms.html","Terms"),("cookies.html","Cookies"),("accessibility.html","Accessibility"),("contact.html","Contact")]

def layout(title: str, kicker: str, summary: str, body: str, *, public: bool = False, canonical_path: str = "") -> str:
    base = "https://sccairquality.com" + (canonical_path or "/")
    robots = "index,follow" if public else "noindex,nofollow"
    nav_links = NAV if not public else [("index.html","Home"),("newhaven.html","Newhaven"),("source-records.html","Sources"),("methodology.html","Methodology"),("contact.html","Contact"),("unredacted/","Protected evidence")]
    menu = "".join(f'<a href="{href}">{label}</a>' for href,label in nav_links)
    legal = "".join(f'<a href="{href}">{label}</a><br>' for href,label in LEGAL)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    ld = json.dumps({"@context":"https://schema.org","@type":"WebSite","name":"AirQuality26 Environmental Intelligence Observatory","url":"https://sccairquality.com/","description":summary}, ensure_ascii=False)
    return f'''<!doctype html><html lang="en-GB"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(title)} · AirQuality26 Environmental Intelligence Observatory</title><meta name="description" content="{escape(summary)}"><meta name="robots" content="{robots}"><link rel="canonical" href="{base}"><meta property="og:title" content="{escape(title)} · AQ26"><meta property="og:description" content="{escape(summary)}"><meta property="og:type" content="website"><meta property="og:url" content="{base}"><meta name="twitter:card" content="summary_large_image"><script type="application/ld+json">{ld}</script><style>{STYLE}</style><script>{SCRIPT}</script></head><body><header class="hero"><nav class="nav" aria-label="Main navigation"><a class="brand" href="index.html"><span class="brand-mark">AQ26</span><span><strong>AirQuality26</strong><br><small>Environmental Intelligence Observatory</small></span></a><button class="burger" onclick="aq26ToggleMenu()" aria-controls="aq26-menu">☰ Menu</button><div class="menu" id="aq26-menu">{menu}</div></nav><section class="hero-inner"><div class="eyebrow">{escape(kicker)}</div><h1>{escape(title)}</h1><p>{escape(summary)}</p></section></header><main class="container">{body}</main><footer class="footer"><div class="footer-inner"><section><strong>AQ26 Environmental Intelligence Observatory</strong><p>Evidence-led weekly air-quality intelligence for Newhaven and wider facility monitoring. Protected pages are for reviewer traceability and are not for public indexing.</p><p>Last rebuilt {now}.</p></section><section><strong>Legal</strong><p>{legal}</p></section><section><strong>Site</strong><p><a href="sitemap.xml">Sitemap</a><br><a href="/">Public site</a><br><a href="/unredacted/">Protected evidence</a></p></section></div><p style="max-width:1180px;margin:1rem auto 0">© 2026 SCC Nexus · AQ26. All rights reserved. Corrections welcome.</p></footer></body></html>'''

def write(path: Path, html: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")

def build_unredacted() -> None:
    latest = read_json("data/weekly/latest_alert_unredacted.json", {})
    weekly = read_json("data/weekly/LATEST_WEEKLYV2.json", {})
    deep = read_json("data/newhaven/newhaven_deep_dive_summary_unredacted.json", {})
    gates = read_json("data/weekly/evidence_readiness_gates.json", {})
    priorities = read_json("data/weekly/evidence_priority_scores.json", {}).get("high_priority", [])
    backfill = read_json("data/weekly/missing_date_backfill_plan.json", {}).get("planned_weeks", [])
    official = read_json("data/weekly/official_filing_index.json", {})
    satellite = read_json("data/weekly/satellite_catalogue_metadata.json", {})
    sources = read_json("data/weekly/source_records_unredacted.json", [])
    focused = read_json("data/backfill/incinerators/focused_backfill_summary_unredacted.json", {})
    readiness_rows = read_csv("data/backfill/incinerators/facility_backfill_readiness_unredacted.csv", 60)
    candidates = read_csv("data/review/UK_Incinerator_Overlay_Candidate_Review.csv", 80)
    diagnostics = read_csv("data/backfill/incinerators/openaq_live_probe_diagnostics.csv", 80)
    inventory = read_csv("data/newhaven/local_evidence_inventory.csv", 80)
    extraction = read_csv("data/newhaven/file_extraction_summary.csv", 60)
    measurements = read_csv("data/newhaven/structured_emissions_measurement_records.csv", 80)
    metrics = card_grid([("facilities in register", val(latest,"total_facilities", default=val(deep,"total_facilities",default="46")), "incinerator/EfW register spine"),("validated overlays", val(latest,"validated_overlays", default=val(deep,"validated_overlays",default="8")), "monitoring overlays retained"),("candidate overlays", val(latest,"candidate_overlays", default=val(deep,"candidate_overlays",default="35")), "human review queue"),("unresolved facilities", val(latest,"unresolved_facilities", default=val(deep,"unresolved_facilities",default="3")), "manual fallback discovery"),("overlay coverage", str(val(latest,"overlay_path_coverage_pct", default="93.5"))+"%", "triage coverage signal"),("structured records", val(deep,"structured_records",default="1537"), "extracted evidence rows")])
    gate_items = [(k.replace("_"," "), status_badge(v)) for k,v in gates.items() if k.endswith("_ready") or k in ["automation_ready","provenance_ready"]]
    gate_html = '<div class="grid">' + ''.join(f'<article class="metric"><span>{escape(k)}</span>{v}</article>' for k,v in gate_items) + '</div>'
    index_body = f'<section class="panel dark"><h2>Protected reviewer console</h2><p>This is the evidence-rich unredacted layer. It brings back the weekly pulse, source provenance, review queues, Newhaven-specific evidence and diagnostic tables behind HTTP Basic Auth.</p></section>{metrics}<section class="panel"><h2>Latest AQ26 weekly evidence pulse</h2><p><strong>{safe(val(latest,"headline",default="Weekly incinerator evidence update"))}</strong> · alert level: <span class="badge warn">{safe(val(latest,"alert_level",default="amber"))}</span></p><p>{safe(val(latest,"unredacted_notice", default=val(latest,"public_notice", default="Internal review area. Do not publish raw diagnostics externally.")))}</p><div class="grid"><a class="panel" href="newhaven.html"><h3>Newhaven evidence hub</h3><p>Facility context, structured evidence inventory and emissions measurement extraction.</p></a><a class="panel" href="weekly-update.html"><h3>Weekly update</h3><p>Readiness gates, missing-date backfill plan and source-specific status.</p></a><a class="panel" href="evidence.html"><h3>Evidence library</h3><p>Evidence bundle, source index, priority scores and download links.</p></a><a class="panel" href="source-records.html"><h3>Source records</h3><p>Traceable source records with SHA256, retrieval status and provenance notes.</p></a></div></section><section class="panel"><h2>Evidence readiness gates</h2>{gate_html}<p class="muted">{safe(gates.get("notes","External submission remains false until scientific gates, historical backfill, satellite extraction and ground QA pass."))}</p></section>'
    write(UNRED/"index.html", layout("AirQuality26", "Protected unredacted site", "Weekly public-interest air-quality intelligence with protected reviewer evidence, traceability and diagnostics.", index_body, canonical_path="/unredacted/"))
    newhaven_body = f'<section class="panel dark"><h2>Newhaven ERF focus</h2><p>Newhaven remains the AQ26 reference facility for reviewer traceability. The protected hub brings together local evidence files, structured emissions records, official filing search terms and weekly QA signals.</p></section>{metrics}<section class="panel"><h2>Facility context</h2><div class="grid"><article><h3>Reference terms</h3><p>{safe(", ".join(official.get("classification_terms", ["BV8067IL","Newhaven Energy Recovery Facility","Environment Agency","emissions monitoring"])))}</p></article><article><h3>Local evidence files</h3><p><strong>{safe(val(deep,"local_evidence_files", default="511"))}</strong> local/repository evidence files indexed for review.</p></article><article><h3>Drive inventory</h3><p><strong>{safe(val(deep,"drive_inventory_rows", default="0"))}</strong> Drive rows reported by this run; Drive fetch configured: {safe(val(deep,"drive_configured", default="unknown"))}.</p></article></div><div class="callout"><strong>Important:</strong> AQ26 evidence pages are review aids. They do not make regulatory, legal, health, breach or causal conclusions.</div></section><section class="panel"><h2>Newhaven extraction summary</h2>{table(extraction, [("source","Source"),("name","File"),("evidence_type","Evidence type"),("public_safe","Public safe"),("rows_read","Rows read"),("newhaven_matched_rows","Newhaven matched"),("chart_records_extracted","Chart records")])}</section><section class="panel"><h2>Structured emissions measurement records</h2>{table(measurements, [("source_file","Source file"),("facility","Facility"),("date","Date"),("pollutant_or_metric","Metric"),("value","Value"),("unit","Unit"),("public_status","Status")])}</section><section class="panel"><h2>Local evidence inventory sample</h2>{table(inventory, [("source","Source"),("path","Path"),("name","Name"),("suffix","Type"),("size_bytes","Bytes"),("evidence_type","Evidence type"),("public_safe","Public safe")])}</section>'
    write(UNRED/"newhaven.html", layout("Newhaven evidence hub", "AQ26 evidence hub", "Focused Newhaven ERF evidence, source inventory, structured records and local monitoring context.", newhaven_body, canonical_path="/unredacted/newhaven.html"))
    evidence_body = f'<section class="panel dark"><h2>Evidence library restored</h2><p>This page now lists priority evidence, weekly bundles, source indexes, readiness gates and the provenance data already generated by the AQ26 pipeline.</p></section><section class="panel"><h2>High-priority evidence queue</h2>{table(priorities, [("item","Item"),("score","Score"),("reason","Reason")])}</section><section class="panel"><h2>Evidence downloads</h2><div class="download-list"><a href="downloads/AQ26_WEEKLY_REPORT.md">AQ26 weekly report · Markdown</a><a href="downloads/AQ26_WEEKLY_REPORT.pdf">AQ26 weekly report · PDF</a><a href="downloads/AQ26_WEEKLY_EVIDENCE_BUNDLE.zip">AQ26 weekly evidence bundle · ZIP if present on server</a></div><p class="muted">The deploy script should preserve larger existing evidence bundles where already present; small report artefacts are included with this content restore pack.</p></section><section class="panel"><h2>Source index</h2>{table(sources, [("source_name","Source"),("source_type","Type"),("status","Status"),("date_uk","Date"),("record_count","Records"),("sha256","SHA256"),("notes","Notes")])}</section><section class="panel"><h2>Readiness gates</h2>{gate_html}</section>'
    write(UNRED/"evidence.html", layout("Unredacted evidence library", "Protected evidence library", "Unredacted AQ26 evidence bundles, source indexes, readiness gates and reviewer notes.", evidence_body, canonical_path="/unredacted/evidence.html"))
    source_body = f'<section class="panel"><h2>Traceable AQ26 source records</h2><p>These are the weekly source records retained for protected reviewer traceability. Where available, records include status, retrieval time, output path, bytes, SHA256 and record count.</p>{table(sources, [("source_name","Source"),("source_type","Type"),("status","Status"),("http_status","HTTP"),("retrieved_at_uk","Retrieved UK"),("output_path","Output path"),("bytes","Bytes"),("record_count","Records"),("sha256","SHA256"),("notes","Notes")])}</section><section class="panel"><h2>Official filing search index</h2><p><strong>Classification terms:</strong> {safe(", ".join(official.get("classification_terms", [])))}</p>{table(official.get("records", []), [("title","Title"),("url","URL"),("date","Date"),("notes","Notes")], empty="No official filing records were written into this weekly JSON yet; the search/classification terms are retained for the next production pass.")}</section>'
    write(UNRED/"source-records.html", layout("Source records", "Protected unredacted site", "Traceable source records and public-source references used by AQ26.", source_body, canonical_path="/unredacted/source-records.html"))
    weekly_body = f'<section class="panel dark"><h2>{safe(val(latest,"headline",default="Weekly evidence update"))}</h2><p>Generated {safe(val(latest,"generated_utc", default=val(weekly,"generated_at_utc", default="unknown")))} · status {safe(val(weekly,"status",default="controlled_review_weekly_update"))}</p></section>{metrics}<section class="panel"><h2>Weekly status</h2><div class="grid"><article class="callout"><h3>External submission ready</h3><p>{status_badge(val(weekly,"external_submission_ready", default=False))}</p></article><article class="warnbox"><h3>Public release ready</h3><p>{status_badge(val(weekly,"public_release_ready", default=False))}</p></article><article><h3>Caveat</h3><p>{safe(val(weekly,"caveat",default="Controlled-review evidence update only."))}</p></article></div></section><section class="panel"><h2>Missing-date backfill plan</h2>{table(backfill, [("week_start_uk","Week start"),("week_end_uk","Week end"),("status","Status"),("priority","Priority"),("source_classes","Source classes"),("integrity_rule","Integrity rule")])}</section><section class="panel"><h2>Facility backfill readiness</h2>{table(readiness_rows, [("facility","Facility"),("overlay_status","Overlay status"),("best_candidate_site","Best candidate site"),("best_candidate_score","Score"),("best_candidate_class","Class"),("candidate_rows_available","Candidate rows"),("backfill_readiness","Backfill readiness")])}</section>'
    write(UNRED/"weekly-update.html", layout("Weekly update", "AQ26 weekly pulse", "Weekly AQ26 evidence pulse, readiness gates, backfill status and review caveats.", weekly_body, canonical_path="/unredacted/weekly-update.html"))
    candidates_body = f'<section class="panel dark"><h2>Candidate overlay review queue</h2><p>Strong candidates still require human review before any promotion to a validated overlay. This table is for reviewer triage only.</p></section><section class="panel"><h2>Candidate overlays</h2>{table(candidates, [("facility","Facility"),("candidate_monitoring_site","Candidate monitoring site"),("score","Score"),("candidate_class","Class"),("recommended_role","Recommended role"),("review_decision","Review decision"),("promote_to_validated","Promote?")])}</section>'
    write(UNRED/"candidates.html", layout("Candidate review", "Protected reviewer queue", "Candidate monitoring overlays requiring manual reviewer decisions before validation.", candidates_body, canonical_path="/unredacted/candidates.html"))
    diagnostics_body = f'<section class="panel dark"><h2>Internal diagnostics</h2><p>OpenAQ/API diagnostics, backfill status and extraction summaries are restricted to the protected area.</p></section><section class="panel"><h2>Focused backfill summary</h2><div class="grid"><article><h3>Scope</h3><p>{safe(focused.get("scope",""))}</p></article><article><h3>Generated</h3><p>{safe(focused.get("generated_utc",""))}</p></article><article><h3>Diagnostics rows</h3><p>{safe(focused.get("diagnostic_rows",""))}</p></article></div><p>{safe(focused.get("notice",""))}</p></section><section class="panel"><h2>Live OpenAQ probe diagnostics</h2>{table(diagnostics, [("location_id","Location ID"),("url","URL"),("ok","OK"),("status","Status"),("error","Error"),("results_count","Results")])}</section><section class="panel"><h2>Satellite catalogue metadata</h2><pre>{safe(json.dumps(satellite, indent=2, ensure_ascii=False))}</pre></section>'
    write(UNRED/"diagnostics.html", layout("Diagnostics", "Protected diagnostics", "Internal API diagnostics, satellite metadata, backfill status and extraction logs.", diagnostics_body, canonical_path="/unredacted/diagnostics.html"))
    history_body = f'<section class="panel"><h2>AQ26 evidence history</h2><div class="timeline"><article><strong>{safe(val(focused,"generated_utc",default="2026-05-29"))}</strong><p>Focused incinerator backfill generated: {safe(val(focused,"facilities_in_register",default="46"))} facilities, {safe(val(focused,"validated_overlays",default="8"))} validated overlays and {safe(val(focused,"candidate_overlays",default="35"))} candidate overlays.</p></article><article><strong>{safe(val(deep,"generated_utc",default="2026-05-29"))}</strong><p>Newhaven deep-dive summary written with {safe(val(deep,"structured_records",default="1537"))} structured records and {safe(val(deep,"local_evidence_files",default="511"))} local evidence files.</p></article><article><strong>{safe(val(weekly,"generated_at_utc",default="2026-06-03"))}</strong><p>Weekly V2 production wrapper indexed {safe(val(weekly,"repo_files_indexed",default="1449"))} repository files and {safe(val(weekly,"drive_files_indexed",default="18023"))} Drive files.</p></article></div></section>'
    write(UNRED/"history.html", layout("Evidence history", "AQ26 history", "Timeline of AQ26 evidence builds, backfill runs and weekly production states.", history_body, canonical_path="/unredacted/history.html"))
    downloads_body = '<section class="panel"><h2>Downloads</h2><div class="download-list"><a href="downloads/AQ26_WEEKLY_REPORT.md">AQ26 weekly report · Markdown</a><a href="downloads/AQ26_WEEKLY_REPORT.pdf">AQ26 weekly report · PDF</a><a href="downloads/AQ26_WEEKLY_EVIDENCE_BUNDLE.zip">AQ26 weekly evidence bundle · ZIP if present</a></div></section>'
    write(UNRED/"downloads.html", layout("Downloads", "Protected downloads", "AQ26 evidence reports and bundles retained for protected reviewer access.", downloads_body, canonical_path="/unredacted/downloads.html"))
    for name,title,summary,content in [("privacy.html","Privacy","How AQ26 handles privacy and protected reviewer information.","AQ26 protected pages are behind HTTP Basic Auth and marked noindex. Do not publish personal data or credentials into repository files, public pages or evidence bundles."),("terms.html","Terms","Terms for using AQ26 public and protected evidence pages.","AQ26 pages are evidence and provenance aids. They are not legal, medical, regulatory or causal conclusions. Reviewer material must be handled proportionately and checked against original sources."),("cookies.html","Cookies","Cookie and analytics notes for AQ26.","The public website may use privacy-conscious analytics. Protected reviewer pages should avoid unnecessary third-party scripts and are marked noindex."),("accessibility.html","Accessibility","Accessibility statement for AQ26.","AQ26 pages use semantic headings, responsive navigation, high contrast cards, table wrappers and descriptive link text. Corrections are welcome."),("contact.html","Contact","Corrections and contact information for AQ26.","Send corrections, source updates or removal requests through the published SCC Nexus contact route. Include the page URL, source record and requested correction.")]:
        write(UNRED/name, layout(title, "AQ26 site information", summary, f'<section class="panel"><p>{escape(content)}</p></section>', canonical_path="/unredacted/"+name))

def build_public() -> None:
    latest = read_json("data/weekly/latest_alert_unredacted.json", {})
    deep = read_json("data/newhaven/newhaven_deep_dive_summary_unredacted.json", {})
    metrics = card_grid([("facilities tracked", val(latest,"total_facilities",default="46"), "public redacted programme context"),("validated overlays", val(latest,"validated_overlays",default="8"), "reviewed monitoring overlays"),("candidate overlays", val(latest,"candidate_overlays",default="35"), "still under review"),("structured records", val(deep,"structured_records",default="1537"), "protected evidence extraction count")])
    body = f'<section class="panel dark"><h2>Public AQ26 overview</h2><p>AirQuality26 is a public-interest environmental intelligence observatory. Public pages are cautious and redacted; protected evidence remains behind authentication.</p></section>{metrics}<section class="panel"><h2>Protected reviewer evidence</h2><p>The unredacted evidence library contains source records, weekly QA, diagnostics, candidate overlays, Newhaven evidence and downloads.</p><p><a class="badge good" href="/unredacted/">Open protected evidence area</a></p></section><section class="panel"><h2>Current public caveat</h2><p>AQ26 does not make health, legal, regulatory, breach or causal conclusions. Screening signals are review prompts only and must be checked against original sources.</p></section>'
    write(PUBLIC/"index.html", layout("AirQuality26", "Public site", "Public redacted overview of AQ26 evidence-led air-quality monitoring and protected evidence access.", body, public=True, canonical_path="/"))
    new_body = '<section class="panel"><h2>Newhaven public context</h2><p>Newhaven is treated as the AQ26 reference evidence hub. Public pages provide context only; protected pages contain source inventories and diagnostics.</p><p><a href="/unredacted/newhaven.html">Open protected Newhaven evidence hub</a></p></section>'
    write(PUBLIC/"newhaven.html", layout("Newhaven evidence hub", "Public redacted page", "Public redacted Newhaven evidence context with a link to the protected reviewer hub.", new_body, public=True, canonical_path="/newhaven.html"))
    src_body = '<section class="panel"><h2>Public source records</h2><p>Public source records are redacted. The protected area contains detailed source records with SHA256, retrieval status and reviewer notes.</p><p><a href="/unredacted/source-records.html">Open protected source records</a></p></section>'
    write(PUBLIC/"source-records.html", layout("Source records", "Public redacted page", "Public-safe source record summary with protected traceability link.", src_body, public=True, canonical_path="/source-records.html"))
    for name,title,summary,text in [("methodology.html","Methodology","AQ26 public methodology and caveats.","AQ26 combines source inventories, monitoring overlays, official filing search terms, satellite catalogue metadata and weekly readiness gates. Public outputs remain cautious and redacted."),("privacy.html","Privacy","AQ26 privacy policy.","AQ26 public pages avoid protected reviewer material. Protected content is behind HTTP Basic Auth and marked noindex."),("terms.html","Terms","AQ26 terms.","Use AQ26 as an evidence-navigation aid, not as legal, medical, regulatory or causal advice."),("cookies.html","Cookies","AQ26 cookies.","AQ26 may use analytics on the public site. Protected reviewer pages should avoid unnecessary tracking."),("accessibility.html","Accessibility","AQ26 accessibility.","AQ26 aims for readable, responsive, keyboard-friendly pages with semantic headings and clear contrast."),("contact.html","Contact","AQ26 contact and corrections.","Corrections welcome. Please include the page URL, source record and suggested amendment.")]:
        write(PUBLIC/name, layout(title, "AQ26 site information", summary, f'<section class="panel"><p>{escape(text)}</p></section>', public=True, canonical_path="/"+name))
    urls = ["https://sccairquality.com/", "https://sccairquality.com/newhaven.html", "https://sccairquality.com/source-records.html", "https://sccairquality.com/methodology.html", "https://sccairquality.com/privacy.html", "https://sccairquality.com/terms.html", "https://sccairquality.com/cookies.html", "https://sccairquality.com/accessibility.html", "https://sccairquality.com/contact.html"]
    write(PUBLIC/"sitemap.xml", '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + ''.join(f'<url><loc>{escape(u)}</loc></url>' for u in urls) + '</urlset>')
    write(PUBLIC/"robots.txt", "User-agent: *\nAllow: /\nDisallow: /unredacted/\nSitemap: https://sccairquality.com/sitemap.xml\n")

def main() -> None:
    ensure_dirs()
    copy_seed_if_missing()
    build_unredacted()
    build_public()
    print("Built AQ26 evidence-rich public and protected content pages.")
if __name__ == "__main__":
    main()
