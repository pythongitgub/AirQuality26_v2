
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import json
import os
import shutil
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional

NAV = [
    ("index.html", "Observatory"),
    ("archive.html", "Weekly Archive"),
    ("comparisons.html", "Comparisons"),
    ("source-records.html", "Source Records"),
    ("readiness.html", "Readiness"),
    ("methodology.html", "Methodology"),
    ("downloads.html", "Downloads"),
]

def read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        obj = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}

def write_json(path: Path, obj: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return path

def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value))

def safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except Exception:
        return default

def sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

def latest_zip(output_root: Path) -> Optional[Path]:
    latest = output_root / "weeklyv2_reports" / "LATEST_ZIP.txt"
    if latest.exists():
        p = Path(latest.read_text(encoding="utf-8", errors="replace").strip())
        if p.exists():
            return p
    zips = sorted((output_root / "weeklyv2_reports").glob("AQ26_WEEKLYV2_EVIDENCE_*.zip"))
    return zips[-1] if zips else None

def final_zip_status(zip_path: Optional[Path]) -> Dict[str, Any]:
    if not zip_path or not zip_path.exists():
        return {"zip_present": False, "zip_entry_count": 0, "ledger_rows": 0, "ledger_present": False}
    with zipfile.ZipFile(zip_path, "r") as z:
        names = z.namelist()
        ledger_names = [n for n in names if n.endswith("AQ26_FINAL_ZIP_LEDGER.csv")]
        rows = 0
        if ledger_names:
            with z.open(ledger_names[-1]) as f:
                rows = max(0, len(f.read().decode("utf-8", errors="replace").splitlines()) - 1)
    return {
        "zip_present": True,
        "zip_name": zip_path.name,
        "zip_sha256": sha_file(zip_path),
        "zip_entry_count": len(names),
        "ledger_rows": rows,
        "ledger_present": bool(ledger_names),
    }

def latest_reports(output_root: Path) -> List[Path]:
    return sorted((output_root / "weeklyv2_reports").rglob("AQ26_WEEKLYV2_REPORT_*.*"))[-8:]

def source_records(output_root: Path) -> List[Dict[str, Any]]:
    latest = read_json(output_root / "00_weeklyv2" / "LATEST_WEEKLYV2.json")
    rows = latest.get("source_records")
    return rows if isinstance(rows, list) else []

def load_summary(output_root: Path, remote_subdir: str) -> Dict[str, Any]:
    latest = read_json(output_root / "00_weeklyv2" / "LATEST_WEEKLYV2.json") or read_json(output_root / "00_live_harvest" / "LATEST_HARVEST.json")
    gates = read_json(output_root / "12_scoring" / "evidence_readiness_gates.json")
    redaction = read_json(output_root / "99_integrity" / "redaction_audit.json")
    satellite = read_json(output_root / "07_satellite_cdse" / "satellite_catalogue_metadata.json")
    drive = read_json(output_root / "08_gdrive_snapshot" / "gdrive_recursive_inventory.json")
    official = read_json(output_root / "06_official_filings" / "official_priority_summary.json")
    openaq = read_json(output_root / "04_ground_aq_providers" / "openaq_safety_manifest.json")
    cams = read_json(output_root / "09_cams" / "cams_readiness.json")
    cdse = read_json(output_root / "15_optional_sources" / "cdse_auth_readiness.json")
    sanitize = read_json(output_root / "15_optional_sources" / "provider_sanitization_manifest.json")
    warnings = read_json(output_root / "03_news_context" / "news_provider_warnings.json")
    zip_path = latest_zip(output_root)
    zip_status = final_zip_status(zip_path)
    run_ts = latest.get("run_ts") or dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return {
        "run_ts": run_ts,
        "created_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "date_window": latest.get("date_window") or {},
        "source_record_count": safe_int(latest.get("source_record_count")),
        "ok_count": safe_int(latest.get("ok_count")),
        "warning_count": safe_int(latest.get("warning_count")),
        "error_count": safe_int(latest.get("error_count")),
        "skipped_count": safe_int(latest.get("skipped_count")),
        "redaction_leak_count": safe_int(redaction.get("leak_count")),
        "redaction_ready": bool(gates.get("redaction_ready")),
        "external_submission_ready": bool(gates.get("external_submission_ready")),
        "metoffice_ready": bool(gates.get("metoffice_ready")),
        "ground_aq_ready": bool(gates.get("ground_aq_ready")),
        "openaq_ready": bool(gates.get("openaq_ready")),
        "openaq_safety_ready": bool(gates.get("openaq_safety_ready")),
        "satellite_catalogue_ready": bool(gates.get("satellite_catalogue_ready")),
        "satellite_extraction_ready": bool(gates.get("satellite_extraction_ready")),
        "satellite_product_count": safe_int(satellite.get("product_count")),
        "drive_ready": bool(gates.get("drive_ready")),
        "drive_file_count": safe_int(drive.get("file_count")),
        "drive_inventory_truncated": bool(drive.get("drive_inventory_truncated")),
        "drive_folder_count": safe_int(drive.get("folder_count")),
        "high_priority_filings": len(official.get("high", []) or []),
        "medium_priority_filings": len(official.get("medium", []) or []),
        "openaq_request_count": safe_int(openaq.get("request_count")),
        "openaq_rate_limit_seen": bool(openaq.get("rate_limit_seen")),
        "cams_key_present": bool(cams.get("cams_key_present")),
        "cams_endpoint_configured": bool(cams.get("cams_endpoint_configured")),
        "cams_data_ready": bool(cams.get("cams_data_ready")),
        "cdse_download_ready": bool(cdse.get("cdse_download_ready") or gates.get("cdse_download_ready")),
        "cdse_sentinelhub_ready": bool(cdse.get("cdse_sentinelhub_ready") or gates.get("cdse_sentinelhub_client_credentials_ready")),
        "gemini_summary_ready": bool(gates.get("gemini_summary_ready")),
        "provider_sanitized_files": safe_int(sanitize.get("files_changed")),
        "news_warning_count": safe_int(warnings.get("warning_count")),
        "final_zip_name": zip_path.name if zip_path else "",
        "final_zip_sha256": zip_status.get("zip_sha256", ""),
        "final_zip_relpath": f"downloads/{zip_path.name}" if zip_path else "",
        "final_zip_status": zip_status,
        "github_repository": os.getenv("GITHUB_REPOSITORY_VALUE", os.getenv("GITHUB_REPOSITORY", "")),
        "github_run_id": os.getenv("GITHUB_RUN_ID_VALUE", os.getenv("GITHUB_RUN_ID", "")),
        "github_sha": os.getenv("GITHUB_SHA_VALUE", os.getenv("GITHUB_SHA", "")),
        "remote_subdir": remote_subdir,
    }

def load_existing_history(output_root: Path) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    hist = output_root / "website_history"
    if hist.exists():
        for p in sorted(hist.glob("*.json")):
            if p.name.startswith("weekly_index"):
                continue
            obj = read_json(p)
            if obj.get("run_ts"):
                out.append(obj)
        prev = read_json(hist / "weekly_index.previous.json")
        if isinstance(prev.get("weeks"), list):
            out.extend([x for x in prev["weeks"] if isinstance(x, dict) and x.get("run_ts")])
    by_ts: Dict[str, Dict[str, Any]] = {}
    for row in out:
        by_ts[str(row.get("run_ts"))] = row
    return sorted(by_ts.values(), key=lambda x: str(x.get("run_ts", "")))

def build_history(current: Dict[str, Any], existing: List[Dict[str, Any]], weeks: int) -> List[Dict[str, Any]]:
    by_ts = {str(x.get("run_ts")): x for x in existing if x.get("run_ts")}
    by_ts[str(current["run_ts"])] = current
    today = dt.datetime.now(dt.timezone.utc).date()
    by_window = {}
    for row in by_ts.values():
        w = row.get("date_window") or {}
        if w.get("start") and w.get("end"):
            by_window[(w["start"], w["end"])] = row
    rows: List[Dict[str, Any]] = []
    for i in range(weeks):
        end = today - dt.timedelta(days=i * 7)
        start = end - dt.timedelta(days=7)
        key = (start.isoformat(), end.isoformat())
        rows.append(by_window.get(key, {
            "run_ts": f"BACKFILL_SLOT_{start.isoformat()}_{end.isoformat()}",
            "date_window": {"start": start.isoformat(), "end": end.isoformat()},
            "backfill_status": "not_yet_harvested",
            "source_record_count": 0,
            "ok_count": 0,
            "warning_count": 0,
            "error_count": 0,
            "satellite_product_count": 0,
            "drive_file_count": 0,
            "high_priority_filings": 0,
            "medium_priority_filings": 0,
            "external_submission_ready": False,
            "final_zip_relpath": "",
        }))
    seen = {x.get("run_ts") for x in rows}
    for row in by_ts.values():
        if row.get("run_ts") not in seen:
            rows.append(row)
    return sorted(rows, key=lambda x: (str((x.get("date_window") or {}).get("end", "")), str(x.get("run_ts", ""))), reverse=True)

def copy_assets(asset_root: Path, site_root: Path) -> None:
    target = site_root / "assets"
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True, exist_ok=True)
    if asset_root.exists():
        shutil.copytree(asset_root, target, dirs_exist_ok=True)
    (target / "site.css").write_text(site_css(), encoding="utf-8")
    (target / "site.js").write_text(site_js(), encoding="utf-8")
    manifest = {"name": "AQ26 Environmental Intelligence Observatory", "short_name": "AQ26", "start_url": "./index.html", "display": "standalone", "background_color": "#eef7fb", "theme_color": "#0b2245", "icons": [{"src": "brand/air_quality_web.svg", "sizes": "any", "type": "image/svg+xml"}]}
    (target / "site.webmanifest").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    icon = target / "brand" / "air_quality_web.svg"
    if icon.exists():
        shutil.copy2(icon, target / "favicon.svg")

def copy_downloads(output_root: Path, site_root: Path) -> List[Dict[str, Any]]:
    downloads = site_root / "downloads"
    downloads.mkdir(parents=True, exist_ok=True)
    rows: List[Dict[str, Any]] = []
    z = latest_zip(output_root)
    if z and z.exists():
        dst = downloads / z.name
        shutil.copy2(z, dst)
        rows.append({"name": z.name, "path": f"downloads/{z.name}", "bytes": dst.stat().st_size, "sha256": sha_file(dst), "type": "evidence_zip"})
    for p in latest_reports(output_root):
        if p.is_file() and p.suffix.lower() in {".pdf", ".md"}:
            dst = downloads / p.name
            shutil.copy2(p, dst)
            rows.append({"name": p.name, "path": f"downloads/{p.name}", "bytes": dst.stat().st_size, "sha256": sha_file(dst), "type": "report"})
    return rows

def topbar(summary: Dict[str, Any]) -> str:
    window = summary.get("date_window") or {}
    return f"<div class='topbar'><div class='topbar-inner'><span>SCC Nexus - AQ26 controlled-review environmental intelligence</span><span>Run {esc(summary.get('run_ts'))} - Window {esc(window.get('start'))} to {esc(window.get('end'))}</span></div></div>"

def header(active: str) -> str:
    links = "".join(f"<a class='{ 'active' if href == active else '' }' href='{href}'>{label}</a>" for href, label in NAV)
    return f"<header class='header'><div class='header-inner'><a href='index.html'><img class='logo' src='assets/brand/logo_web.svg' alt='SCC Nexus'></a><nav class='nav'>{links}</nav></div></header>"

def layout(title: str, active: str, body: str, summary: Dict[str, Any]) -> str:
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="index,follow"><title>{esc(title)} - AQ26</title><link rel="icon" href="assets/favicon.svg" type="image/svg+xml"><link rel="manifest" href="assets/site.webmanifest"><link rel="stylesheet" href="assets/site.css"><script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script></head><body>{topbar(summary)}{header(active)}{body}<footer class="footer"><div class="footer-inner"><strong>AQ26 WeeklyV2</strong><span>Controlled-review evidence dashboard - no external endorsement or causal attribution claimed - external submission ready: {esc(summary.get('external_submission_ready'))}</span></div></footer><script src="assets/site.js"></script></body></html>"""

def hero(summary: Dict[str, Any]) -> str:
    return f"""<section class="hero"><video class="hero-video" autoplay muted loop playsinline poster="assets/banners/desktop_banner_1_web.svg"><source src="assets/banners/desktop_banner_2.webm" type="video/webm"></video><div class="hero-inner"><div><p class="kicker">AQ26 Environmental Intelligence Observatory</p><h1>Weekly evidence, provenance and target-control air-quality intelligence.</h1><p>Website-ready monitoring around Newhaven Energy Recovery Facility and contextual control sites, with source records, integrity ledgers, readiness gates and historical comparison slots.</p><a class="btn primary" href="archive.html">View weekly archive</a><a class="btn ghost" href="{esc(summary.get('final_zip_relpath') or '#')}">Download evidence ZIP</a></div><div class="banner-card"><div class="slide active"><h3>Controlled review</h3><p>No external endorsement or causal attribution is claimed. Evidence gates make limitations visible.</p></div><div class="slide"><h3>Integrity ledgers</h3><p>Final ZIP entries, redaction status and source records are bundled for audit-ready weekly review.</p></div><div class="slide"><h3>Historical trajectory</h3><p>Weekly slots and charts support trend comparison and future historical backfill.</p></div><div class="dots"><span class="dot active"></span><span class="dot"></span><span class="dot"></span></div></div></div></section>"""

def metric(title: str, value: Any, note: str = "", cls: str = "") -> str:
    return f"<div class='metric'><span>{esc(title)}</span><strong class='{cls}'>{esc(value)}</strong><small>{esc(note)}</small></div>"

def gate(title: str, value: Any, invert: bool = False) -> str:
    truth = bool(value)
    cls = "danger" if (truth and invert) or ((not truth) and not invert) else "ok"
    return f"<div class='card'><h3>{esc(title)}</h3><p class='{cls}'><strong>{esc(value)}</strong></p></div>"

def download_card(d: Dict[str, Any]) -> str:
    return f"<a class='report-card' href='{esc(d.get('path'))}'><strong>{esc(d.get('name'))}</strong><span>{esc(d.get('type'))} - {safe_int(d.get('bytes')):,} bytes</span><code>{esc(str(d.get('sha256',''))[:16])}...</code></a>"

def render_index(root: Path, summary: Dict[str, Any], weeks: List[Dict[str, Any]], downloads: List[Dict[str, Any]]) -> None:
    cards = [
        metric("Source records", summary.get("source_record_count"), "All source classes"),
        metric("OK records", summary.get("ok_count"), "Successful harvests", "ok"),
        metric("Warnings", summary.get("warning_count"), "Provider warnings", "warn"),
        metric("Errors", summary.get("error_count"), "Should remain zero", "danger" if summary.get("error_count") else "ok"),
        metric("Satellite products", summary.get("satellite_product_count"), "Catalogue records"),
        metric("Drive files", summary.get("drive_file_count"), "Recursive metadata inventory"),
        metric("Redaction leaks", summary.get("redaction_leak_count"), "Fail-closed audit", "danger" if summary.get("redaction_leak_count") else "ok"),
        metric("High filings", summary.get("high_priority_filings"), "Official relevance queue"),
    ]
    data = esc(json.dumps({"summary": summary, "weeks": weeks}, ensure_ascii=False))
    body = hero(summary) + f"""<main><section class="section"><div class="section-title"><h2>Latest evidence status</h2><p>Current GitHub weekly run, source coverage and readiness state.</p></div><div class="grid grid-4">{''.join(cards)}</div></section><section class="section"><div class="section-title"><h2>Interactive comparison charts</h2><p>Weekly record counts, satellite coverage and filings.</p></div><div class="grid grid-2"><div class="viz-card"><div id="records-chart"></div></div><div class="viz-card"><div id="coverage-chart"></div></div></div></section><section class="section"><div class="section-title"><h2>Evidence gates</h2><p>External submission remains false until science gates pass.</p></div><div class="grid grid-3">{gate("Redaction ready", summary.get("redaction_ready"))}{gate("CDSE download ready", summary.get("cdse_download_ready"))}{gate("CAMS data ready", summary.get("cams_data_ready"))}{gate("Satellite extraction ready", summary.get("satellite_extraction_ready"))}{gate("Drive inventory truncated", summary.get("drive_inventory_truncated"), True)}{gate("External submission ready", summary.get("external_submission_ready"), True)}</div></section><section class="section"><div class="section-title"><h2>Latest downloads</h2><p>Evidence bundles and report files generated by the latest run.</p></div><div class="report-list">{''.join(download_card(d) for d in downloads)}</div></section></main><script id="aq26-data" type="application/json">{data}</script>"""
    (root / "index.html").write_text(layout("AQ26 Environmental Intelligence Observatory", "index.html", body, summary), encoding="utf-8")

def render_archive(root: Path, summary: Dict[str, Any], weeks: List[Dict[str, Any]]) -> None:
    rows = []
    for w in weeks:
        win = w.get("date_window") or {}
        status = w.get("backfill_status") or ("harvested" if safe_int(w.get("source_record_count")) else "not_yet_harvested")
        link = w.get("final_zip_relpath") or "#"
        rows.append(f"<tr><td>{esc(win.get('start'))}</td><td>{esc(win.get('end'))}</td><td><span class='tag'>{esc(status)}</span></td><td>{esc(w.get('source_record_count',0))}</td><td>{esc(w.get('ok_count',0))}</td><td>{esc(w.get('warning_count',0))}</td><td>{esc(w.get('error_count',0))}</td><td>{esc(w.get('satellite_product_count',0))}</td><td>{esc(w.get('high_priority_filings',0))}</td><td><a href='{esc(link)}'>Open</a></td></tr>")
    body = f"<main><section class='section'><div class='section-title'><h2>Weekly archive and historical backfill slots</h2><p>At least 52 weekly windows are maintained. Slots become evidence links as backfill runs are completed.</p></div><input class='filter' placeholder='Filter by date/status...' oninput=\"AQ26.filterTable('weekly-table', this.value)\"><div class='table-wrap'><table id='weekly-table'><thead><tr><th>Start</th><th>End</th><th>Status</th><th>Records</th><th>OK</th><th>Warnings</th><th>Errors</th><th>Satellite</th><th>High filings</th><th>Evidence</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div></section></main>"
    (root / "archive.html").write_text(layout("Weekly Archive", "archive.html", body, summary), encoding="utf-8")

def render_comparisons(root: Path, summary: Dict[str, Any], weeks: List[Dict[str, Any]]) -> None:
    data = esc(json.dumps({"summary": summary, "weeks": weeks}, ensure_ascii=False))
    body = f"<main><section class='section'><div class='section-title'><h2>Comparison charts</h2><p>Interactive weekly comparisons across source coverage, readiness and filings.</p></div><div class='grid grid-2'><div class='viz-card'><div id='records-chart'></div></div><div class='viz-card'><div id='coverage-chart'></div></div><div class='viz-card'><div id='filings-chart'></div></div><div class='viz-card'><div id='readiness-chart'></div></div></div></section></main><script id='aq26-data' type='application/json'>{data}</script>"
    (root / "comparisons.html").write_text(layout("Comparisons", "comparisons.html", body, summary), encoding="utf-8")

def render_source_records(root: Path, summary: Dict[str, Any], records: List[Dict[str, Any]]) -> None:
    rows = "".join(f"<tr><td>{esc(r.get('source_name'))}</td><td>{esc(r.get('source_type'))}</td><td>{esc(r.get('status'))}</td><td>{esc(r.get('http_status'))}</td><td>{esc(r.get('record_count'))}</td><td>{esc(r.get('retrieved_at_uk'))}</td><td>{esc(r.get('query'))}</td></tr>" for r in records)
    body = f"<main><section class='section'><div class='section-title'><h2>Source records</h2><p>Redacted provenance records generated by the latest WeeklyV2 run.</p></div><input class='filter' placeholder='Filter source records...' oninput=\"AQ26.filterTable('source-table', this.value)\"><div class='table-wrap'><table id='source-table'><thead><tr><th>Source</th><th>Type</th><th>Status</th><th>HTTP</th><th>Records</th><th>Retrieved UK</th><th>Query/site</th></tr></thead><tbody>{rows}</tbody></table></div></section></main>"
    (root / "source-records.html").write_text(layout("Source Records", "source-records.html", body, summary), encoding="utf-8")

def render_readiness(root: Path, summary: Dict[str, Any]) -> None:
    body = f"<main><section class='section'><div class='section-title'><h2>Readiness and governance gates</h2><p>These gates prevent overclaiming and separate evidence harvesting from scientific attribution.</p></div><div class='grid grid-3'>{gate('Redaction ready', summary.get('redaction_ready'))}{gate('Ground AQ ready', summary.get('ground_aq_ready'))}{gate('Met Office ready', summary.get('metoffice_ready'))}{gate('OpenAQ safety ready', summary.get('openaq_safety_ready'))}{gate('Satellite catalogue ready', summary.get('satellite_catalogue_ready'))}{gate('Satellite extraction ready', summary.get('satellite_extraction_ready'))}{gate('CDSE download ready', summary.get('cdse_download_ready'))}{gate('CAMS data ready', summary.get('cams_data_ready'))}{gate('Drive inventory truncated', summary.get('drive_inventory_truncated'), True)}{gate('External submission ready', summary.get('external_submission_ready'), True)}</div></section><section class='section'><div class='callout'><strong>Current boundary:</strong> controlled-review evidence, not regulatory proof, not health-burden attribution, and not causal facility attribution.</div></section></main>"
    (root / "readiness.html").write_text(layout("Readiness", "readiness.html", body, summary), encoding="utf-8")

def render_methodology(root: Path, summary: Dict[str, Any]) -> None:
    items = [
        ("Maria Neira / WHO framing", "Health-protective guideline context and cautious public-health language."),
        ("Frank Kelly-style QA", "Station quality, representativeness, averaging periods and traffic/background confounding."),
        ("Helen ApSimon-style source-receptor logic", "Wind, dispersion, emissions inventory and uncertainty before attribution."),
        ("Prashant Kumar-style sensor governance", "Low-cost sensor provenance, siting, calibration and spatial representativeness."),
        ("Dominici-style causal epidemiology", "No causal health inference without confounder control, exposure windows and uncertainty."),
        ("Randall Martin-style satellite fusion", "Remote-sensing context requires extraction, QA and ground validation."),
        ("Michael Brauer / GBD integration", "Exposure screening is separated from health-burden calculation."),
        ("Susan Anenberg-style emissions-health modelling", "Trace-gas and emissions-related indicators are prioritised for screening."),
        ("Theo Damoulas-style digital twin readiness", "Weekly historical structure and target/control sites support future spatiotemporal models."),
    ]
    body = "<main><section class='section'><div class='section-title'><h2>Methodology alignment</h2><p>Scientific influences used as design benchmarks, not endorsements.</p></div><div class='grid grid-3'>" + "".join(f"<div class='card'><h3>{esc(t)}</h3><p>{esc(d)}</p></div>" for t,d in items) + "</div></section></main>"
    (root / "methodology.html").write_text(layout("Methodology", "methodology.html", body, summary), encoding="utf-8")

def render_downloads(root: Path, summary: Dict[str, Any], downloads: List[Dict[str, Any]]) -> None:
    body = f"<main><section class='section'><div class='section-title'><h2>Downloads</h2><p>Latest evidence bundles, reports and machine-readable indexes.</p></div><div class='report-list'>{''.join(download_card(d) for d in downloads)}<a class='report-card' href='data/latest_summary.json'><strong>latest_summary.json</strong><span>machine-readable latest run summary</span></a><a class='report-card' href='data/weekly_index.json'><strong>weekly_index.json</strong><span>weekly historical index and backfill slots</span></a></div></section></main>"
    (root / "downloads.html").write_text(layout("Downloads", "downloads.html", body, summary), encoding="utf-8")

def write_data(root: Path, summary: Dict[str, Any], weeks: List[Dict[str, Any]], records: List[Dict[str, Any]]) -> None:
    data = root / "data"
    hist = data / "history"
    hist.mkdir(parents=True, exist_ok=True)
    write_json(data / "latest_summary.json", summary)
    write_json(data / "weekly_index.json", {"created_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(), "weeks": weeks})
    write_json(data / "source_records_latest.json", {"run_ts": summary.get("run_ts"), "records": records})
    write_json(hist / f"{summary['run_ts']}.json", summary)

def site_css() -> str:
    return """:root{--navy:#0b2245;--navy2:#123d73;--cyan:#20b5aa;--gold:#c79533;--ink:#132238;--muted:#607083;--line:#d9e3ec;--soft:#f7fafc;--ok:#217a50;--warn:#b7791f;--danger:#b83232;--shadow:0 12px 30px rgba(13,43,87,.08);--radius:18px}*{box-sizing:border-box}body{margin:0;background:linear-gradient(180deg,#e9f0f6 0,#f8fafc 360px,#fff);color:var(--ink);font-family:Aptos,Segoe UI,Roboto,Arial,sans-serif;line-height:1.55;-webkit-font-smoothing:antialiased;position:relative}body:before{content:"";position:fixed;right:-110px;bottom:4vh;width:min(46vw,620px);aspect-ratio:1;background:url("brand/air_quality_web.svg") center/contain no-repeat;opacity:.035;pointer-events:none;z-index:0}.topbar,.header,.hero,main,.footer{position:relative;z-index:1}a{color:var(--navy2)}.topbar{background:#06172e;color:#d9e8f6;font-size:13px;padding:8px 22px}.topbar-inner{max-width:1380px;margin:0 auto;display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap}.header{background:rgba(255,255,255,.97);border-bottom:1px solid var(--line);position:sticky;top:0;z-index:50;box-shadow:0 4px 20px rgba(10,28,55,.08);backdrop-filter:blur(10px)}.header-inner{max-width:1380px;margin:0 auto;padding:12px 22px;display:flex;align-items:center;justify-content:space-between;gap:18px}.logo{width:min(320px,62vw);height:56px;display:block;object-fit:contain}.nav{display:flex;gap:7px;align-items:center;flex-wrap:wrap;justify-content:flex-end}.nav a{text-decoration:none;color:var(--navy);font-size:12.5px;font-weight:800;padding:8px 10px;border-radius:999px;white-space:nowrap}.nav a.active,.nav a:hover{background:#e8f1fb;color:#09254d}.hero{background:linear-gradient(135deg,rgba(6,23,46,.92),rgba(9,47,84,.78) 52%,rgba(8,127,121,.7)),url("banners/desktop_banner_1_web.svg");background-size:cover;background-position:center;color:#fff;position:relative;overflow:hidden}.hero-video{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;opacity:.22}.hero:after{content:"";position:absolute;right:-190px;top:-160px;width:650px;height:650px;border-radius:50%;background:rgba(255,255,255,.07)}.hero-inner{max-width:1380px;margin:0 auto;padding:54px 22px 58px;position:relative;z-index:1;display:grid;grid-template-columns:minmax(0,1.25fr) minmax(320px,.75fr);gap:30px;align-items:center}.kicker{text-transform:uppercase;letter-spacing:.13em;font-size:12px;font-weight:900;color:#bcebe7}.hero h1{font-size:clamp(34px,4.2vw,58px);line-height:1.04;margin:12px 0 16px;max-width:940px}.hero p{font-size:clamp(16px,1.6vw,19px);color:#e5f1fb;max-width:860px}.btn{display:inline-block;padding:11px 16px;border-radius:10px;text-decoration:none;font-weight:900;border:1px solid rgba(255,255,255,.28);margin:6px 8px 0 0;cursor:pointer}.btn.primary{background:#fff;color:var(--navy)}.btn.ghost{color:#fff;background:rgba(255,255,255,.08)}.banner-card{background:rgba(255,255,255,.13);border:1px solid rgba(255,255,255,.27);border-radius:22px;padding:24px;backdrop-filter:blur(8px);box-shadow:0 24px 60px rgba(0,0,0,.13)}.slide{display:none}.slide.active{display:block}.slide h3{font-size:24px;margin:0 0 10px;color:#fff}.slide p{font-size:15px;color:#e7f2fb}.dots{display:flex;gap:8px;margin-top:18px}.dot{width:9px;height:9px;border-radius:50%;background:rgba(255,255,255,.38);cursor:pointer}.dot.active{background:#fff}main{max-width:1380px;margin:0 auto;padding:30px 22px 58px}.section{margin:0 0 28px}.section-title{display:flex;align-items:flex-end;justify-content:space-between;gap:18px;margin-bottom:14px}.section-title h2{font-size:clamp(23px,2.4vw,30px);margin:0;color:var(--navy)}.section-title p{margin:0;color:var(--muted);max-width:720px}.grid{display:grid;gap:16px}.grid-4{grid-template-columns:repeat(4,minmax(0,1fr))}.grid-3{grid-template-columns:repeat(3,minmax(0,1fr))}.grid-2{grid-template-columns:repeat(2,minmax(0,1fr))}.card,.metric,.panel,.callout,.viz-card{background:#fff;border:1px solid var(--line);border-radius:var(--radius);padding:20px;box-shadow:var(--shadow)}.card h3{margin:0 0 8px;color:var(--navy);font-size:19px}.card p{margin:0 0 10px;color:#34465e}.metric span{display:block;text-transform:uppercase;letter-spacing:.08em;font-size:12px;color:var(--muted);font-weight:900}.metric strong{display:block;font-size:clamp(30px,4vw,46px);color:var(--navy);line-height:1.05;margin:8px 0}.metric small{color:var(--muted)}.ok{color:var(--ok)!important}.warn{color:var(--warn)!important}.danger{color:var(--danger)!important}.tag{display:inline-block;border-radius:999px;background:#e8f1fb;color:var(--navy);font-weight:900;font-size:12px;padding:3px 8px}.table-wrap{overflow:auto;border:1px solid var(--line);border-radius:var(--radius);box-shadow:var(--shadow);background:#fff}table{border-collapse:collapse;width:100%;min-width:860px}th,td{padding:11px 12px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top;font-size:14px}th{background:#f0f5fa;color:var(--navy);position:sticky;top:0}tbody tr:hover{background:#f7fbff}.filter{width:100%;padding:13px 14px;border:1px solid var(--line);border-radius:12px;margin:0 0 12px;font-size:15px}.viz-card{min-height:420px}.report-list{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:14px}.report-card{display:block;text-decoration:none;background:#fff;border:1px solid var(--line);border-radius:16px;padding:16px;box-shadow:var(--shadow)}.report-card strong{display:block;color:var(--navy);margin-bottom:6px}.report-card span{display:block;color:var(--muted);font-size:13px}.report-card code{display:block;margin-top:8px;color:#456;font-size:12px}.callout{border-left:5px solid var(--gold);background:#fffaf0}.footer{background:#06172e;color:#d9e8f6;padding:24px 22px}.footer-inner{max-width:1380px;margin:0 auto;display:flex;justify-content:space-between;gap:16px;flex-wrap:wrap}.footer span{color:#9eb6cf}@media(max-width:980px){.hero-inner,.grid-4,.grid-3,.grid-2{grid-template-columns:1fr}.nav{justify-content:flex-start}.header-inner{align-items:flex-start;flex-direction:column}.logo{height:48px}}"""

def site_js() -> str:
    return """const AQ26={};AQ26.filterTable=function(id,q){q=(q||'').toLowerCase();document.querySelectorAll('#'+id+' tbody tr').forEach(tr=>{tr.style.display=tr.innerText.toLowerCase().includes(q)?'':'none';});};(function(){function initSlider(){const slides=[...document.querySelectorAll('.slide')],dots=[...document.querySelectorAll('.dot')];if(!slides.length)return;let i=0;function show(n){i=n%slides.length;slides.forEach((x,j)=>x.classList.toggle('active',j===i));dots.forEach((x,j)=>x.classList.toggle('active',j===i));}dots.forEach((x,j)=>x.addEventListener('click',()=>show(j)));setInterval(()=>show(i+1),5600);}function data(){const el=document.getElementById('aq26-data');if(!el)return null;try{return JSON.parse(el.textContent);}catch(e){return null;}}function labels(weeks){return weeks.slice().reverse().map(x=>((x.date_window||{}).end||x.run_ts||'').slice(0,10));}function arr(weeks,key){return weeks.slice().reverse().map(x=>Number(x[key]||0));}function plot(){const d=data();if(!d||typeof Plotly==='undefined')return;const weeks=d.weeks||[];const l=labels(weeks);const layout={paper_bgcolor:'rgba(0,0,0,0)',plot_bgcolor:'rgba(0,0,0,0)',font:{color:'#132238'},xaxis:{gridcolor:'#d9e3ec'},yaxis:{gridcolor:'#d9e3ec'},margin:{t:50,l:52,r:24,b:48}};if(document.getElementById('records-chart'))Plotly.newPlot('records-chart',[{x:l,y:arr(weeks,'source_record_count'),type:'scatter',mode:'lines+markers',name:'Records'},{x:l,y:arr(weeks,'ok_count'),type:'scatter',mode:'lines+markers',name:'OK'},{x:l,y:arr(weeks,'warning_count'),type:'scatter',mode:'lines+markers',name:'Warnings'},{x:l,y:arr(weeks,'error_count'),type:'scatter',mode:'lines+markers',name:'Errors'}],{...layout,title:'Weekly evidence records'},{responsive:true});if(document.getElementById('coverage-chart'))Plotly.newPlot('coverage-chart',[{x:l,y:arr(weeks,'satellite_product_count'),type:'bar',name:'Satellite products'},{x:l,y:arr(weeks,'drive_file_count'),type:'bar',name:'Drive files'},{x:l,y:arr(weeks,'high_priority_filings'),type:'bar',name:'High filings'}],{...layout,barmode:'group',title:'Evidence coverage'},{responsive:true});if(document.getElementById('filings-chart'))Plotly.newPlot('filings-chart',[{x:l,y:arr(weeks,'high_priority_filings'),type:'bar',name:'High priority'},{x:l,y:arr(weeks,'medium_priority_filings'),type:'bar',name:'Medium priority'}],{...layout,barmode:'stack',title:'Official filing queue'},{responsive:true});if(document.getElementById('readiness-chart'))Plotly.newPlot('readiness-chart',[{labels:['External ready','Needs validation'],values:[d.summary.external_submission_ready?1:0,d.summary.external_submission_ready?0:1],type:'pie',hole:.58}],{...layout,title:'External submission gate'},{responsive:true});}if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',()=>{initSlider();plot();});else{initSlider();plot();}})();"""

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", default="outputs")
    parser.add_argument("--site-root", default="site_public")
    parser.add_argument("--history-weeks", default="52")
    parser.add_argument("--asset-root", default="website/assets")
    parser.add_argument("--remote-subdir", default="airquality26")
    args = parser.parse_args()
    output_root = Path(args.output_root)
    site_root = Path(args.site_root)
    if site_root.exists():
        shutil.rmtree(site_root)
    site_root.mkdir(parents=True, exist_ok=True)
    copy_assets(Path(args.asset_root), site_root)
    summary = load_summary(output_root, args.remote_subdir)
    weeks = build_history(summary, load_existing_history(output_root), int(args.history_weeks))
    downloads = copy_downloads(output_root, site_root)
    records = source_records(output_root)
    write_data(site_root, summary, weeks, records)
    render_index(site_root, summary, weeks, downloads)
    render_archive(site_root, summary, weeks)
    render_comparisons(site_root, summary, weeks)
    render_source_records(site_root, summary, records)
    render_readiness(site_root, summary)
    render_methodology(site_root, summary)
    render_downloads(site_root, summary, downloads)
    (site_root / "robots.txt").write_text("User-agent: *\\nAllow: /\\n", encoding="utf-8")
    (site_root / "sitemap.txt").write_text("\\n".join([x[0] for x in NAV] + ["data/latest_summary.json", "data/weekly_index.json"]), encoding="utf-8")
    print(json.dumps({"site_root": str(site_root), "pages": [x[0] for x in NAV], "history_weeks": len(weeks), "latest_run_ts": summary.get("run_ts"), "downloads": len(downloads)}, indent=2))

if __name__ == "__main__":
    main()
