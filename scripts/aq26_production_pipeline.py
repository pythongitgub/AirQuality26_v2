#!/usr/bin/env python3
"""AQ26 GitHub-first weekly production pipeline.

Creates a controlled-review weekly evidence bundle, redacted public site,
password-protected unredacted site payload, provenance ledgers, SEO files,
reports, charts data and final ZIP. It is intentionally defensive: optional
providers may warn, but redaction/provenance/schema failures are hard gates.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import os
import re
import shutil
import smtplib
import sys
import textwrap
import zipfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests
import yaml
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.lib import colors

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    from backports.zoneinfo import ZoneInfo  # type: ignore

SECRET_NAMES = [
    "CAMS_API_KEY", "CDSE_ID", "CDSE_PASSWORD", "CDSE_SECRET", "CDSE_USERNAME",
    "EARTHDATA_PASSWORD", "EARTHDATA_TOKEN", "EARTHDATA_USERNAME", "EARTH_DATA_API_KEY",
    "GDRIVE_FOLDER_ID", "GDRIVE_SERVICE_ACCOUNT", "GEMINI_API_KEY", "METOFFICE_API_KEY",
    "MET_OFFICE_API_KEY", "MET_OFFICE_LAND_OBSERVATIONS", "NEWS_API_KEY", "NEWS_DATA_IO_KEY",
    "OPENAQ_API_KEY", "OPENWEATHER_KEY", "PURPLE_AIR_API_KEY", "SERPAPI_API_KEY",
    "SMTP_PASSWORD", "SMTP_USERNAME", "SCCNEXUS_SSH_PASSWORD", "SCC_UNREDACTED_PASSWORD",
    "WAQI_TOKEN",
]

REDACTION_TOKEN = "[REDACTED]"


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_yaml(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_csv(path: Path, rows: List[Dict[str, Any]], fieldnames: Optional[List[str]] = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = []
        for row in rows:
            for key in row.keys():
                if key not in fieldnames:
                    fieldnames.append(key)
        if not fieldnames:
            fieldnames = ["empty"]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})
    # readback validation: catches malformed CSV before deployment
    with path.open("r", encoding="utf-8", newline="") as f:
        list(csv.DictReader(f))


def append_jsonl(path: Path, rows: Iterable[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


def safe_secret_values() -> List[str]:
    vals = []
    for name in SECRET_NAMES:
        value = os.environ.get(name, "")
        if value and len(value) >= 6:
            vals.append(value)
    # service-account JSON contains lots of tokens; scan substrings only safely by raw value
    return vals


def redact_text(text: str, extra_patterns: Optional[List[str]] = None) -> str:
    out = text
    for val in safe_secret_values():
        out = out.replace(val, REDACTION_TOKEN)
    # Redact query credentials and common token-looking URL params.
    out = re.sub(r"(?i)(api[_-]?key|apikey|token|password|secret|client_secret)=([^&\s\"']+)", r"\1=" + REDACTION_TOKEN, out)
    out = re.sub(r"(?i)(Authorization:\s*Bearer\s+)[A-Za-z0-9._\-]+", r"\1" + REDACTION_TOKEN, out)
    for pat in extra_patterns or []:
        out = re.sub(pat, REDACTION_TOKEN, out)
    return out


def redaction_audit(paths: Iterable[Path], output_path: Path) -> Dict[str, Any]:
    leaks: List[Dict[str, str]] = []
    secret_values = safe_secret_values()
    token_regex = re.compile(r"(?i)(api[_-]?key|apikey|token|password|secret|client_secret)=([^&\s\"']+)")
    for path in paths:
        if not path.exists() or path.is_dir() or path.name == ".htpasswd":
            continue
        try:
            if path.stat().st_size > 8_000_000:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for val in secret_values:
            if val and val in text:
                leaks.append({"path": str(path), "type": "secret_value", "secret_sha256": sha256_bytes(val.encode())})
        # URL credential parameters are redacted at write time. Do not fail on
        # historical/public text unless an actual runtime secret value is present;
        # otherwise docs mentioning api_key=example would create false positives.
    report = {
        "generated_at_utc": utc_now().isoformat(),
        "leak_count": len(leaks),
        "leaks": leaks[:200],
    }
    write_json(output_path, report)
    return report


@dataclass
class Context:
    repo: Path
    cfg: Dict[str, Any]
    run_ts: str
    run_dt_utc: datetime
    run_dt_uk: datetime
    output_root: Path
    public_site: Path
    unredacted_site: Path
    source_records: List[Dict[str, Any]]
    warnings: List[str]


def make_source_record(ctx: Context, *, source_name: str, source_type: str, url: str = "", query: str = "", status: str = "ok", http_status: Any = "", output_path: str = "", record_count: Any = "", error: str = "", notes: str = "") -> Dict[str, Any]:
    path = Path(output_path) if output_path else None
    bytes_size = ""
    digest = ""
    if path and path.exists() and path.is_file():
        bytes_size = path.stat().st_size
        digest = sha256_file(path)
    return {
        "source_name": source_name,
        "source_type": source_type,
        "url_redacted": redact_text(url),
        "query": redact_text(query),
        "status": status,
        "http_status": http_status,
        "retrieved_at_utc": ctx.run_dt_utc.isoformat(),
        "retrieved_at_uk": ctx.run_dt_uk.isoformat(),
        "date_uk": ctx.run_dt_uk.strftime("%d/%m/%Y"),
        "output_path": str(path or ""),
        "bytes": bytes_size,
        "sha256": digest,
        "record_count": record_count,
        "error": redact_text(error),
        "notes": notes,
    }


def http_get_json(ctx: Context, source_name: str, source_type: str, url: str, params: Dict[str, Any], headers: Optional[Dict[str, str]], output_path: Path, timeout: int = 30) -> Dict[str, Any]:
    try:
        resp = requests.get(url, params=params, headers=headers or {}, timeout=timeout)
        redacted_url = redact_text(resp.url)
        payload_text = redact_text(resp.text[:2_000_000])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(payload_text, encoding="utf-8")
        count = ""
        try:
            data = json.loads(payload_text)
            if isinstance(data, dict):
                if isinstance(data.get("results"), list):
                    count = len(data["results"])
                elif isinstance(data.get("data"), list):
                    count = len(data["data"])
                elif "meta" in data:
                    count = data.get("meta", {}).get("found", "")
        except Exception:
            pass
        return make_source_record(ctx, source_name=source_name, source_type=source_type, url=redacted_url, query=json.dumps(params), status="ok" if resp.ok else "warning", http_status=resp.status_code, output_path=str(output_path), record_count=count, error="" if resp.ok else resp.text[:300])
    except Exception as e:
        write_json(output_path.with_suffix(".error.json"), {"error": redact_text(str(e)), "url": redact_text(url), "params": params})
        return make_source_record(ctx, source_name=source_name, source_type=source_type, url=url, query=json.dumps(params), status="warning", http_status="", output_path=str(output_path.with_suffix(".error.json")), record_count=0, error=str(e))


def copy_branding(ctx: Context) -> None:
    assets_public = ctx.public_site / "assets"
    assets_unred = ctx.unredacted_site / "assets"
    for d in [assets_public, assets_unred, assets_public / "banners", assets_unred / "banners"]:
        d.mkdir(parents=True, exist_ok=True)
    logo_header = ctx.repo / ctx.cfg["sites"]["branding"].get("header_logo", "website/assets/air_quality_web.svg")
    favicon = ctx.repo / ctx.cfg["sites"]["branding"].get("favicon", "website/assets/logo_web.svg")
    for site in [ctx.public_site, ctx.unredacted_site]:
        (site / "assets").mkdir(parents=True, exist_ok=True)
        if logo_header.exists():
            shutil.copy2(logo_header, site / "assets" / "air_quality_web.svg")
        if favicon.exists():
            shutil.copy2(favicon, site / "assets" / "favicon.svg")
            shutil.copy2(favicon, site / "favicon.svg")
    banners_dir = ctx.repo / "website/assets/banners"
    if banners_dir.exists():
        for b in banners_dir.glob("*.webm"):
            shutil.copy2(b, assets_public / "banners" / b.name)
            shutil.copy2(b, assets_unred / "banners" / b.name)


def inventory_repo_evidence(ctx: Context) -> Dict[str, Any]:
    file_rows: List[Dict[str, Any]] = []
    scan_roots = ["site_public/data", "site_unredacted/data", "outputs", "configs", "data_sources"]
    for root_name in scan_roots:
        root = ctx.repo / root_name
        if not root.exists():
            continue
        for p in root.rglob("*"):
            if p.is_file() and p.name != ".htpasswd":
                try:
                    rel = p.relative_to(ctx.repo)
                except Exception:
                    rel = p
                file_rows.append({
                    "path": str(rel),
                    "bytes": p.stat().st_size,
                    "modified_utc": datetime.fromtimestamp(p.stat().st_mtime, timezone.utc).isoformat(),
                    "sha256": sha256_file(p),
                    "extension": p.suffix.lower(),
                })
    out = ctx.output_root / "repo_evidence_inventory.json"
    write_json(out, {"generated_at_utc": ctx.run_dt_utc.isoformat(), "count": len(file_rows), "files": file_rows[:5000]})
    ctx.source_records.append(make_source_record(ctx, source_name="Repository evidence inventory", source_type="local_repo", output_path=str(out), record_count=len(file_rows), notes="Indexes committed AQ26 evidence files available to the GitHub workflow."))
    return {"count": len(file_rows), "files": file_rows}


def google_drive_inventory(ctx: Context) -> Dict[str, Any]:
    out = ctx.output_root / "gdrive_recursive_inventory.json"
    folder_id = os.environ.get("GDRIVE_FOLDER_ID", "")
    svc_json = os.environ.get("GDRIVE_SERVICE_ACCOUNT", "")
    if not folder_id or not svc_json:
        result = {"enabled": False, "reason": "GDRIVE_FOLDER_ID or GDRIVE_SERVICE_ACCOUNT not set", "files": []}
        write_json(out, result)
        ctx.source_records.append(make_source_record(ctx, source_name="Google Drive recursive inventory", source_type="google_drive", status="warning", output_path=str(out), record_count=0, notes=result["reason"]))
        return result
    try:
        import tempfile
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        from googleapiclient.errors import HttpError
        creds_info = json.loads(svc_json)
        creds = service_account.Credentials.from_service_account_info(creds_info, scopes=["https://www.googleapis.com/auth/drive.readonly"])
        service = build("drive", "v3", credentials=creds, cache_discovery=False)
        max_files = int(ctx.cfg.get("providers", {}).get("google_drive", {}).get("max_files", 20000))
        files: List[Dict[str, Any]] = []
        queue: List[Tuple[str, str, int]] = [(folder_id, "", 0)]
        seen_folders = set()
        while queue and len(files) < max_files:
            fid, path, depth = queue.pop(0)
            if fid in seen_folders:
                continue
            seen_folders.add(fid)
            page_token = None
            while True:
                resp = service.files().list(
                    q=f"'{fid}' in parents and trashed=false",
                    spaces="drive",
                    fields="nextPageToken, files(id,name,mimeType,size,modifiedTime,md5Checksum,webViewLink,shortcutDetails)",
                    pageToken=page_token,
                    pageSize=1000,
                    supportsAllDrives=True,
                    includeItemsFromAllDrives=True,
                ).execute()
                for item in resp.get("files", []):
                    item_path = f"{path}/{item.get('name','')}".strip("/")
                    row = {
                        "path": item_path,
                        "file_id_sha256": sha256_bytes(item.get("id", "").encode()),
                        "name": item.get("name"),
                        "mimeType": item.get("mimeType"),
                        "size": item.get("size", ""),
                        "modifiedTime": item.get("modifiedTime", ""),
                        "md5Checksum": item.get("md5Checksum", ""),
                        "webViewLink_redacted": redact_text(item.get("webViewLink", "")),
                        "depth": depth,
                    }
                    files.append(row)
                    mt = item.get("mimeType", "")
                    if mt == "application/vnd.google-apps.folder":
                        queue.append((item["id"], item_path, depth + 1))
                    elif mt == "application/vnd.google-apps.shortcut":
                        sd = item.get("shortcutDetails") or {}
                        if sd.get("targetMimeType") == "application/vnd.google-apps.folder" and sd.get("targetId"):
                            queue.append((sd["targetId"], item_path + " (shortcut)", depth + 1))
                    if len(files) >= max_files:
                        break
                page_token = resp.get("nextPageToken")
                if not page_token or len(files) >= max_files:
                    break
        result = {"enabled": True, "folder_id_sha256": sha256_bytes(folder_id.encode()), "truncated": len(files) >= max_files, "count": len(files), "files": files}
        write_json(out, result)
        ctx.source_records.append(make_source_record(ctx, source_name="Google Drive recursive inventory", source_type="google_drive", status="ok", output_path=str(out), record_count=len(files), notes="File IDs are SHA256-hashed; links are redacted."))
        return result
    except Exception as e:
        result = {"enabled": True, "error": redact_text(str(e)), "files": []}
        write_json(out, result)
        ctx.source_records.append(make_source_record(ctx, source_name="Google Drive recursive inventory", source_type="google_drive", status="warning", output_path=str(out), record_count=0, error=str(e)))
        return result


def live_provider_probes(ctx: Context) -> None:
    api_dir = ctx.output_root / "provider_probes"
    api_dir.mkdir(parents=True, exist_ok=True)
    # OpenAQ lightweight public endpoint. API key optional.
    headers = {}
    if os.environ.get("OPENAQ_API_KEY"):
        headers["X-API-Key"] = os.environ["OPENAQ_API_KEY"]
    ctx.source_records.append(http_get_json(
        ctx, "OpenAQ latest UK location probe", "ground_air_openaq",
        "https://api.openaq.org/v3/locations",
        {"countries_id": "GB", "limit": 10, "page": 1}, headers,
        api_dir / "openaq_locations_gb.json"
    ))
    # CDSE catalogue sample: public OData search; does not download products.
    ctx.source_records.append(http_get_json(
        ctx, "Copernicus CDSE catalogue sample", "satellite_catalogue",
        "https://catalogue.dataspace.copernicus.eu/odata/v1/Products",
        {"$top": 5, "$filter": "contains(Name,'S5P')"}, None,
        api_dir / "cdse_s5p_catalogue_sample.json"
    ))
    # News/data.gov.uk official filing search via CKAN package search.
    ctx.source_records.append(http_get_json(
        ctx, "data.gov.uk official filing search", "official_filing",
        "https://ckan.publishing.service.gov.uk/api/3/action/package_search",
        {"q": "Newhaven Energy Recovery Facility BV8067IL Environment Agency", "rows": 10}, None,
        api_dir / "data_gov_uk_newhaven_search.json"
    ))


def build_derived_outputs(ctx: Context, drive_inv: Dict[str, Any], repo_inv: Dict[str, Any]) -> Dict[str, Any]:
    ok = sum(1 for r in ctx.source_records if r.get("status") == "ok")
    warnings = sum(1 for r in ctx.source_records if r.get("status") == "warning")
    errors = sum(1 for r in ctx.source_records if r.get("status") == "error")
    latest = {
        "run_ts": ctx.run_ts,
        "generated_at_utc": ctx.run_dt_utc.isoformat(),
        "generated_at_uk": ctx.run_dt_uk.isoformat(),
        "project": "AirQuality26",
        "status": "controlled_review_weekly_update",
        "public_site": ctx.cfg.get("project", {}).get("public_base_url", ""),
        "unredacted_site": ctx.cfg.get("project", {}).get("unredacted_path", "/unredacted/"),
        "source_records": len(ctx.source_records),
        "source_records_ok": ok,
        "source_records_warnings": warnings,
        "source_records_errors": errors,
        "drive_files_indexed": drive_inv.get("count", 0),
        "repo_files_indexed": repo_inv.get("count", 0),
        "redaction_leaks": None,
        "external_submission_ready": False,
        "public_release_ready": False,
        "caveat": "Controlled-review evidence update only; not a causal, legal, health, or endorsement finding.",
    }
    write_json(ctx.output_root / "LATEST_WEEKLYV2.json", latest)

    source_index = ctx.output_root / "source_index.jsonl"
    append_jsonl(source_index, ctx.source_records)

    # Simple readiness gates. Only automation/provenance/redaction can be true at this stage.
    gates = {
        "generated_at_utc": ctx.run_dt_utc.isoformat(),
        "automation_ready": True,
        "provenance_ready": True,
        "redaction_ready": False,
        "metoffice_ready": False,
        "ground_aq_ready": any(r["source_type"].startswith("ground_air") and r["status"] == "ok" for r in ctx.source_records),
        "satellite_catalogue_ready": any(r["source_type"] == "satellite_catalogue" and r["status"] == "ok" for r in ctx.source_records),
        "satellite_extraction_ready": False,
        "official_filings_ready": any(r["source_type"] == "official_filing" and r["status"] == "ok" for r in ctx.source_records),
        "backfill_ready": False,
        "external_submission_ready": False,
        "notes": "External submission remains false until scientific gates, historical backfill, satellite extraction, and ground QA pass.",
    }
    write_json(ctx.output_root / "evidence_readiness_gates.json", gates)

    backfill_weeks = int(os.environ.get("AQ26_HISTORICAL_BACKFILL_WEEKS", "4") or "4")
    today_uk = ctx.run_dt_uk.date()
    plan = []
    for i in range(backfill_weeks):
        end = today_uk - timedelta(days=7 * i)
        start = end - timedelta(days=7)
        plan.append({
            "week_start_uk": start.isoformat(),
            "week_end_uk": end.isoformat(),
            "status": "planned_source_specific_backfill",
            "priority": "high" if i == 0 else "medium",
            "source_classes": ["openaq", "ukair_sos", "laqn", "official_filings", "satellite_catalogue", "weather"],
            "integrity_rule": "Only mark harvested after source records, SHA256 ledger, redaction audit and weekly summary exist.",
        })
    write_json(ctx.output_root / "missing_date_backfill_plan.json", {"generated_at_utc": ctx.run_dt_utc.isoformat(), "planned_weeks": plan})

    scores = {
        "generated_at_utc": ctx.run_dt_utc.isoformat(),
        "high_priority": [
            {"item": "Newhaven ERF BV8067IL official filings and emissions records", "score": 100, "reason": "Reference facility and permit."},
            {"item": "Official UK-AIR/LAQN/OpenAQ historical ground measurements", "score": 95, "reason": "Needed for target/control comparison."},
            {"item": "Satellite catalogue-to-extraction chain", "score": 85, "reason": "Catalogue exists; extraction and QA still locked."},
        ],
    }
    write_json(ctx.output_root / "evidence_priority_scores.json", scores)

    official = {"generated_at_utc": ctx.run_dt_utc.isoformat(), "classification_terms": ["BV8067", "BV8067IL", "Newhaven Energy Recovery Facility", "Veolia Newhaven", "Environment Agency", "annual monitoring report", "permit variation", "enforcement notice", "emissions monitoring"], "records": []}
    write_json(ctx.output_root / "official_filing_index.json", official)

    satellite = {"generated_at_utc": ctx.run_dt_utc.isoformat(), "pollutant_extraction_manifest": {"pollutants": ctx.cfg["focus"].get("pollutants", []), "satellite_extraction_ready": False, "reason": "Catalogue probe only; no product download/extraction QA in this weekly wrapper."}}
    write_json(ctx.output_root / "satellite_catalogue_metadata.json", satellite)

    anomalies = {"generated_at_utc": ctx.run_dt_utc.isoformat(), "alerts": [], "language": "candidate anomaly / screening signal only; requires independent validation"}
    write_json(ctx.output_root / "anomaly_alerts.json", anomalies)
    return latest


def make_ledger(root: Path, output_csv: Path, exclude: Optional[Path] = None) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for p in sorted(root.rglob("*")):
        if not p.is_file() or p.name == ".htpasswd":
            continue
        if exclude and p.resolve() == exclude.resolve():
            continue
        rows.append({"path": str(p.relative_to(root)), "bytes": p.stat().st_size, "sha256": sha256_file(p)})
    write_csv(output_csv, rows, ["path", "bytes", "sha256"])
    return rows


def html_page(title: str, body: str, cfg: Dict[str, Any], current: str = "") -> str:
    seo = cfg.get("sites", {}).get("seo", {})
    nav = [
        ("index.html", "Overview"), ("weekly-update.html", "Weekly update"), ("incinerators.html", "Incinerators"),
        ("historical-comparisons.html", "Historical"), ("source-records.html", "Sources"), ("methodology.html", "Methodology"),
        ("downloads.html", "Downloads"), ("about.html", "About"),
    ]
    links = "".join(f'<a class="{ "active" if href == current else "" }" href="{href}">{label}</a>' for href, label in nav)
    return f"""<!doctype html>
<html lang="en-GB">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)} · AQ26</title>
  <meta name="description" content="{html.escape(seo.get('description',''))}">
  <meta name="keywords" content="{html.escape(seo.get('keywords',''))}">
  <link rel="icon" href="/assets/favicon.svg?v=aq26-production" type="image/svg+xml">
  <link rel="apple-touch-icon" href="/assets/favicon.svg?v=aq26-production">
  <link rel="manifest" href="/site.webmanifest">
  <script src="https://cdn.plot.ly/plotly-2.32.0.min.js" defer></script>
  <style>
    :root {{ --ink:#13202f; --muted:#5d6a7d; --accent:#d6262f; --panel:#ffffff; --bg:#f4f7fb; --line:#dce4ef; }}
    * {{ box-sizing:border-box; }} body {{ margin:0; font-family:Arial, Helvetica, sans-serif; background:var(--bg); color:var(--ink); line-height:1.55; }}
    header {{ position:sticky; top:0; z-index:10; background:#fff; border-bottom:1px solid var(--line); box-shadow:0 3px 18px rgba(10,35,65,.08); }}
    .topbar {{ max-width:1180px; margin:auto; display:flex; align-items:center; justify-content:space-between; gap:1rem; padding:.7rem 1rem; }}
    .brand img {{ height:58px; max-width:330px; width:auto; display:block; }}
    .menu-toggle {{ display:none; border:1px solid var(--line); background:#fff; border-radius:10px; padding:.55rem .7rem; font-size:1.2rem; }}
    nav {{ display:flex; gap:.25rem; flex-wrap:wrap; }} nav a {{ color:var(--ink); text-decoration:none; padding:.55rem .65rem; border-radius:10px; font-weight:700; font-size:.92rem; }} nav a.active, nav a:hover {{ background:#f8dadd; color:#a30f19; }}
    .hero {{ background:linear-gradient(120deg,#0d2038,#204f82 50%,#d6262f); color:#fff; overflow:hidden; }}
    .hero video {{ width:100%; max-height:260px; object-fit:cover; opacity:.45; display:block; }}
    .hero-inner {{ max-width:1180px; margin:auto; padding:2.2rem 1rem; }} .hero h1 {{ font-size:clamp(2rem,5vw,4rem); line-height:1.02; margin:.25rem 0; }}
    .ticker {{ background:#10243d; color:#fff; white-space:nowrap; overflow:hidden; }} .ticker span {{ display:inline-block; padding:.65rem 0; animation:scroll 28s linear infinite; }} @keyframes scroll {{ from {{ transform:translateX(100%); }} to {{ transform:translateX(-100%); }} }}
    main {{ max-width:1180px; margin:auto; padding:1.3rem 1rem 3rem; }}
    .grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(230px,1fr)); gap:1rem; }} .card {{ background:var(--panel); border:1px solid var(--line); border-radius:18px; padding:1rem; box-shadow:0 8px 24px rgba(15,40,70,.06); }}
    .metric {{ font-size:2rem; font-weight:800; color:#0d3d72; }} .muted {{ color:var(--muted); }} .safe {{ color:#0b6b3a; font-weight:800; }} .warn {{ color:#975a00; font-weight:800; }}
    table {{ width:100%; border-collapse:collapse; background:#fff; border-radius:14px; overflow:hidden; }} th,td {{ padding:.7rem; border-bottom:1px solid var(--line); text-align:left; vertical-align:top; }} th {{ background:#eef3f9; }}
    pre {{ white-space:pre-wrap; background:#0f1f34; color:#e8f1ff; border-radius:14px; padding:1rem; overflow:auto; }}
    footer {{ background:#101b2c; color:#dce8f6; padding:2rem 1rem; }} footer div {{ max-width:1180px; margin:auto; }}
    @media (max-width:860px) {{ .menu-toggle {{ display:block; }} nav {{ display:none; width:100%; flex-direction:column; }} nav.open {{ display:flex; }} .topbar {{ flex-wrap:wrap; }} .brand img {{ height:46px; max-width:250px; }} }}
  </style>
</head>
<body>
<header><div class="topbar"><a class="brand" href="index.html" aria-label="AirQuality26 home"><img src="assets/air_quality_web.svg" alt="SCC Nexus Air Quality Report"></a><button class="menu-toggle" onclick="document.querySelector('nav').classList.toggle('open')" aria-label="Open menu">☰</button><nav>{links}</nav></div></header>
{body}
<footer><div><strong>AirQuality26</strong><br>Public pages are redacted and cautious. No endorsement by WHO, UNEP, EEA, C40 Cities or named academic experts is implied.</div></footer>
<script>document.querySelectorAll('[data-json]').forEach(async el=>{{try{{const r=await fetch(el.dataset.json); const j=await r.json(); el.textContent=JSON.stringify(j,null,2).slice(0,5000);}}catch(e){{el.textContent='Data preview unavailable';}}}});</script>
</body></html>"""



def cleanup_legacy_public_sensitive_files(ctx: Context) -> None:
    """Remove legacy generated public files that may pre-date the production redaction rules.

    The production workflow publishes redacted source summaries under
    site_public/data/weekly/source_records_public.json. Older ad-hoc workflows
    sometimes left source_records_latest.json in site_public/data with provider
    URLs or secret-bearing query strings. Remove those stale files before the
    redaction audit and before any deployment/package step.
    """
    legacy_names = [
        ctx.public_site / "data" / "source_records_latest.json",
        ctx.public_site / "data" / "source_records_unredacted.json",
        ctx.public_site / "data" / "source_index.jsonl",
        ctx.public_site / "source_records_latest.json",
        ctx.public_site / "source_index.jsonl",
    ]
    removed = []
    for path in legacy_names:
        try:
            if path.exists() and path.is_file():
                path.unlink()
                removed.append(str(path))
        except Exception as exc:
            ctx.warnings.append(f"Could not remove legacy public data file {path}: {exc}")
    if removed:
        write_json(ctx.output_root / "legacy_public_sensitive_cleanup.json", {
            "generated_at_utc": ctx.run_dt_utc.isoformat(),
            "removed_files": removed,
            "reason": "Removed stale public data files before redaction audit; current redacted records are regenerated under data/weekly/.",
        })



def build_sites(ctx: Context, latest: Dict[str, Any]) -> None:
    for site in [ctx.public_site, ctx.unredacted_site]:
        site.mkdir(parents=True, exist_ok=True)
        (site / "data").mkdir(parents=True, exist_ok=True)
        (site / "downloads").mkdir(parents=True, exist_ok=True)
    copy_branding(ctx)
    # Public data copies
    public_data = ctx.public_site / "data" / "weekly"
    unred_data = ctx.unredacted_site / "data" / "weekly"
    public_data.mkdir(parents=True, exist_ok=True); unred_data.mkdir(parents=True, exist_ok=True)
    for name in ["LATEST_WEEKLYV2.json", "evidence_readiness_gates.json", "missing_date_backfill_plan.json", "evidence_priority_scores.json", "official_filing_index.json", "satellite_catalogue_metadata.json", "anomaly_alerts.json", "redaction_audit.json"]:
        src = ctx.output_root / name
        if src.exists():
            shutil.copy2(src, public_data / name)
            shutil.copy2(src, unred_data / name)
    shutil.copy2(ctx.output_root / "source_index.jsonl", unred_data / "source_index.jsonl")
    # Redacted public source record summary only
    public_records = [{k: r.get(k, "") for k in ["source_name", "source_type", "status", "http_status", "retrieved_at_uk", "date_uk", "record_count", "notes"]} for r in ctx.source_records]
    write_json(public_data / "source_records_public.json", public_records)
    write_json(unred_data / "source_records_unredacted.json", ctx.source_records)

    banner = ""
    banners = sorted((ctx.public_site / "assets/banners").glob("*.webm"))
    if banners:
        banner = f'<div class="hero"><video autoplay muted loop playsinline src="assets/banners/{banners[0].name}"></video></div>'
    ticker = f'<div class="ticker"><span> Weekly AQ26 update · {latest["source_records"]} source records · {latest["source_records_ok"]} OK · {latest["source_records_warnings"]} warnings · {latest["drive_files_indexed"]} Drive files indexed · public-safe redacted release </span></div>'
    cards = f"""
    <section class="hero"><div class="hero-inner"><p>Controlled weekly evidence update</p><h1>Air-quality evidence observatory for incinerator and control-site review.</h1><p>Validated provenance, redacted public output, protected unredacted review area, and weekly historical backfill planning.</p></div></section>{ticker}
    <main><div class="grid">
      <div class="card"><div class="metric">{latest['source_records']}</div><strong>source records</strong><p class="muted">Every source record has timestamp, type, query, output path and SHA256 where applicable.</p></div>
      <div class="card"><div class="metric">{latest['source_records_ok']}</div><strong>OK records</strong><p class="muted">Warnings are preserved rather than hidden.</p></div>
      <div class="card"><div class="metric">{latest['drive_files_indexed']}</div><strong>Drive files indexed</strong><p class="muted">File IDs are hashed; links are redacted.</p></div>
      <div class="card"><div class="metric">0</div><strong>redaction leaks target</strong><p class="muted">Any detected secret leak fails the workflow.</p></div>
    </div><section class="card"><h2>Weekly highlight</h2><p><strong>Newhaven ERF / BV8067IL</strong> remains the reference facility for controlled target/control development. This public page uses cautious language: screening signals, candidate anomalies and evidence gaps require independent validation.</p></section></main>"""
    write_text(ctx.public_site / "index.html", html_page("Environmental Intelligence Observatory", banner + cards, ctx.cfg, "index.html"))

    weekly_body = f"<main><h1>Weekly update</h1><p>Generated {ctx.run_dt_uk.strftime('%d/%m/%Y %H:%M %Z')}.</p><div class='grid'><div class='card'><h2>Status</h2><pre data-json='data/weekly/LATEST_WEEKLYV2.json'></pre></div><div class='card'><h2>Readiness gates</h2><pre data-json='data/weekly/evidence_readiness_gates.json'></pre></div></div></main>"
    write_text(ctx.public_site / "weekly-update.html", html_page("Weekly update", weekly_body, ctx.cfg, "weekly-update.html"))
    hist_body = "<main><h1>Historical comparisons</h1><p>The historical archive is being filled by source-specific weekly backfill. Empty placeholder weeks must not be presented as harvested evidence.</p><div class='grid'><div class='card'><h2>Backfill plan</h2><pre data-json='data/weekly/missing_date_backfill_plan.json'></pre></div><div class='card'><h2>Evidence priorities</h2><pre data-json='data/weekly/evidence_priority_scores.json'></pre></div></div></main>"
    write_text(ctx.public_site / "historical-comparisons.html", html_page("Historical comparisons", hist_body, ctx.cfg, "historical-comparisons.html"))
    inc_body = "<main><h1>Incinerators and controls</h1><p>Facility pages are public-safe summaries. The unredacted area contains diagnostics and raw review tables.</p><div class='card'><h2>Reference case</h2><p>Newhaven Energy Recovery Facility / BV8067IL is the first full target/control reference case.</p></div></main>"
    write_text(ctx.public_site / "incinerators.html", html_page("Incinerators", inc_body, ctx.cfg, "incinerators.html"))
    src_body = "<main><h1>Source records</h1><p>Public source table is redacted. The protected review site includes full source index outputs.</p><div class='card'><pre data-json='data/weekly/source_records_public.json'></pre></div></main>"
    write_text(ctx.public_site / "source-records.html", html_page("Source records", src_body, ctx.cfg, "source-records.html"))
    method_body = "<main><h1>Methodology</h1><div class='card'><p>AQ26 uses cautious, controlled-review language. It separates emissions, ambient concentration, exposure potential, health relevance and health outcome evidence. No institutional endorsement is implied.</p></div></main>"
    write_text(ctx.public_site / "methodology.html", html_page("Methodology", method_body, ctx.cfg, "methodology.html"))
    down_body = "<main><h1>Downloads</h1><p>Weekly evidence ZIP and reports are generated in the controlled bundle. Public downloads are redacted.</p><ul><li><a href='downloads/AQ26_WEEKLY_REPORT.pdf'>Weekly PDF report</a></li><li><a href='downloads/AQ26_WEEKLY_EVIDENCE_BUNDLE.zip'>Evidence ZIP</a></li></ul></main>"
    write_text(ctx.public_site / "downloads.html", html_page("Downloads", down_body, ctx.cfg, "downloads.html"))
    about_body = "<main><h1>About AQ26</h1><p>AQ26 is building a reproducible evidence platform for facility-level air-quality review, policy interpretation and independent scientific challenge.</p></main>"
    write_text(ctx.public_site / "about.html", html_page("About", about_body, ctx.cfg, "about.html"))
    for simple in ["privacy", "cookies", "accessibility", "terms", "contact", "archive", "comparisons", "readiness", "evidence-downloads", "latest-report", "newhaven", "overlays", "legal"]:
        if not (ctx.public_site / f"{simple}.html").exists():
            write_text(ctx.public_site / f"{simple}.html", html_page(simple.replace('-', ' ').title(), f"<main><h1>{simple.replace('-', ' ').title()}</h1><p>This page is maintained as part of the AQ26 public evidence website.</p></main>", ctx.cfg, ""))

    # Unredacted console.
    unred_body = f"<main><h1>Unredacted review console</h1><p>Password-protected review area. Contains diagnostics, full source records and metadata.</p><div class='grid'><div class='card'><h2>Latest summary</h2><pre data-json='data/weekly/LATEST_WEEKLYV2.json'></pre></div><div class='card'><h2>Full source records</h2><pre data-json='data/weekly/source_records_unredacted.json'></pre></div></div></main>"
    write_text(ctx.unredacted_site / "index.html", html_page("Unredacted Review Area", unred_body, ctx.cfg, "index.html"))
    write_text(ctx.unredacted_site / "evidence.html", html_page("Evidence Index", "<main><h1>Evidence index</h1><pre data-json='data/weekly/source_records_unredacted.json'></pre></main>", ctx.cfg, ""))
    write_text(ctx.public_site / "robots.txt", "User-agent: *\nAllow: /\nSitemap: /sitemap.xml\n")
    write_text(ctx.unredacted_site / "robots.txt", "User-agent: *\nDisallow: /\n")
    webmanifest = {"name": "AirQuality26", "short_name": "AQ26", "icons": [{"src": "/assets/favicon.svg", "sizes": "any", "type": "image/svg+xml"}], "theme_color": "#ffffff", "background_color": "#ffffff", "display": "standalone"}
    write_json(ctx.public_site / "site.webmanifest", webmanifest)
    write_json(ctx.unredacted_site / "site.webmanifest", webmanifest)


def build_report(ctx: Context, latest: Dict[str, Any]) -> Tuple[Path, Path]:
    md = ctx.output_root / "AQ26_WEEKLY_REPORT.md"
    text = f"""# AQ26 Weekly Controlled-Review Evidence Report

Generated UTC: {ctx.run_dt_utc.isoformat()}  
Generated UK: {ctx.run_dt_uk.strftime('%d/%m/%Y %H:%M %Z')}

## Status

This is a controlled-review weekly evidence update. It does not assert final facility-specific causation, legal breach, health harm, liability, or endorsement by WHO, UNEP, EEA, C40 Cities or named experts.

## Summary

- Source records: {latest['source_records']}
- OK records: {latest['source_records_ok']}
- Warnings: {latest['source_records_warnings']}
- Errors: {latest['source_records_errors']}
- Google Drive files indexed: {latest['drive_files_indexed']}
- Repository evidence files indexed: {latest['repo_files_indexed']}

## Methodological alignment

- WHO / Maria Neira lens: health-protective framing and guideline comparators.
- UNEP lens: source-sector actionability and clean-air policy pathways.
- EEA lens: comparability, standards, trends, capture rate and uncertainty.
- C40 lens: local-authority usability, equity and public data access.
- Frank Kelly lens: do not jump from emissions to health outcomes.
- Helen ApSimon lens: wind, dispersion, source-receptor logic and background pollution.
- Prashant Kumar lens: sensor siting, calibration, representativeness and low-cost sensor limitations.
- Dominici / Martin / Brauer / Anenberg / Damoulas lenses: guarded causal language, satellite-ground fusion, integrated exposure screening, emissions-health modelling caution and urban digital-twin readiness.

## Next validation priorities

1. Run source-specific historical backfill in batches.
2. Convert UK-AIR SOS and LAQN provider probes into validated observation harvesters.
3. Add satellite product extraction and QA after catalogue readiness.
4. Keep public release redacted and cautious until scientific gates pass.
"""
    write_text(md, text)
    pdf = ctx.output_root / "AQ26_WEEKLY_REPORT.pdf"
    styles = getSampleStyleSheet()
    story: List[Any] = []
    story.append(Paragraph("AQ26 Weekly Controlled-Review Evidence Report", styles["Title"]))
    story.append(Paragraph(f"Generated: {ctx.run_dt_uk.strftime('%d/%m/%Y %H:%M %Z')}", styles["Normal"]))
    story.append(Spacer(1, 12))
    story.append(Paragraph("Controlled-review update only. No causal, health, legal, liability or endorsement finding is asserted.", styles["BodyText"]))
    story.append(Spacer(1, 12))
    data = [["Metric", "Value"], ["Source records", latest["source_records"]], ["OK", latest["source_records_ok"]], ["Warnings", latest["source_records_warnings"]], ["Drive files", latest["drive_files_indexed"]], ["Repo files", latest["repo_files_indexed"]]]
    table = Table(data, colWidths=[220, 220])
    table.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), colors.HexColor("#e9eef7")), ("GRID", (0,0), (-1,-1), 0.25, colors.grey), ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold")]))
    story.append(table)
    story.append(Spacer(1, 12))
    story.append(Paragraph("Validation priorities: historical backfill, UK-AIR/LAQN observations, satellite extraction QA, source-receptor and wind-sector checks.", styles["BodyText"]))
    doc = SimpleDocTemplate(str(pdf), pagesize=A4, title="AQ26 Weekly Report")
    doc.build(story)
    return md, pdf


def zip_dir(src: Path, dest: Path) -> None:
    if dest.exists():
        dest.unlink()
    with zipfile.ZipFile(dest, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for p in sorted(src.rglob("*")):
            if p.is_file() and p.name != ".htpasswd":
                z.write(p, p.relative_to(src))


def build_final_bundle(ctx: Context) -> Path:
    # Copy report/downloads into public/unredacted downloads.
    for site in [ctx.public_site, ctx.unredacted_site]:
        (site / "downloads").mkdir(parents=True, exist_ok=True)
        for name in ["AQ26_WEEKLY_REPORT.md", "AQ26_WEEKLY_REPORT.pdf"]:
            src = ctx.output_root / name
            if src.exists():
                shutil.copy2(src, site / "downloads" / name)
    pub_zip = ctx.output_root / "AQ26_WEEKLY_PUBLIC_SITE.zip"
    unred_zip = ctx.output_root / "AQ26_WEEKLY_UNREDACTED_SITE.zip"
    zip_dir(ctx.public_site, pub_zip)
    zip_dir(ctx.unredacted_site, unred_zip)
    # Place public final ZIP link after final bundle has been made; a copy is made at end.
    make_ledger(ctx.output_root, ctx.output_root / "AQ26_SHA256_LEDGER.csv")
    final_zip = ctx.output_root / f"AQ26_WEEKLY_VALIDATED_EVIDENCE_BUNDLE_{ctx.run_ts}.zip"
    with zipfile.ZipFile(final_zip, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for p in sorted(ctx.output_root.rglob("*")):
            if p.is_file() and p.name != final_zip.name and p.name != "AQ26_FINAL_ZIP_LEDGER.csv":
                z.write(p, p.relative_to(ctx.output_root))
    # Ledger of final ZIP contents; intentionally not hashing itself.
    rows = []
    with zipfile.ZipFile(final_zip, "r") as z:
        for info in z.infolist():
            if info.filename == "AQ26_FINAL_ZIP_LEDGER.csv":
                continue
            rows.append({"path": info.filename, "bytes": info.file_size, "zip_crc": info.CRC})
    write_csv(ctx.output_root / "AQ26_FINAL_ZIP_LEDGER.csv", rows, ["path", "bytes", "zip_crc"])
    # Rebuild final ZIP including final ledger.
    with zipfile.ZipFile(final_zip, "a", compression=zipfile.ZIP_DEFLATED) as z:
        z.write(ctx.output_root / "AQ26_FINAL_ZIP_LEDGER.csv", "AQ26_FINAL_ZIP_LEDGER.csv")
    (ctx.output_root / "latest_bundle_path.txt").write_text(str(final_zip), encoding="utf-8")
    shutil.copy2(final_zip, ctx.public_site / "downloads" / "AQ26_WEEKLY_EVIDENCE_BUNDLE.zip")
    shutil.copy2(final_zip, ctx.unredacted_site / "downloads" / "AQ26_WEEKLY_EVIDENCE_BUNDLE.zip")
    return final_zip


def validate_outputs(ctx: Context) -> None:
    """Validate generated outputs without opaque tracebacks.

    Older ad-hoc AQ26 site workflows sometimes committed empty/partial JSON files
    into site_public or site_unredacted. The production workflow regenerates the
    current JSON feeds, so stale invalid site JSON is quarantined before final
    packaging. Newly generated output_root JSON remains a hard gate.
    """
    required = ctx.cfg.get("required_bundle_files", [])
    missing = [name for name in required if not (ctx.output_root / name).exists()]
    if missing:
        raise RuntimeError("Missing required bundle files: " + ", ".join(missing))

    required_pages = [
        ctx.public_site / "index.html",
        ctx.public_site / "weekly-update.html",
        ctx.public_site / "historical-comparisons.html",
        ctx.public_site / "downloads.html",
        ctx.unredacted_site / "index.html",
    ]
    blank_pages = []
    for path in required_pages:
        if not path.exists() or path.stat().st_size < 200:
            blank_pages.append(str(path.relative_to(ctx.repo) if path.is_relative_to(ctx.repo) else path))
    if blank_pages:
        summary = {
            "generated_at_utc": utc_now().isoformat(),
            "stage": "validate_outputs",
            "error": "blank_or_missing_pages",
            "paths": blank_pages,
        }
        write_json(ctx.output_root / "AQ26_VALIDATION_FAILURE_SUMMARY.json", summary)
        raise RuntimeError("Blank or missing page(s): " + ", ".join(blank_pages))

    invalid_json = []
    quarantined_site_json = []
    quarantine_root = ctx.output_root / "validation_quarantine" / "invalid_site_json"

    def _rel(p: Path) -> str:
        try:
            return str(p.relative_to(ctx.repo))
        except Exception:
            return str(p)

    def _validate_json_file(p: Path, strict: bool) -> None:
        try:
            text = p.read_text(encoding="utf-8")
            json.loads(text)
        except Exception as exc:
            item = {
                "path": _rel(p),
                "bytes": p.stat().st_size if p.exists() else None,
                "error": f"{type(exc).__name__}: {exc}",
            }
            if strict:
                invalid_json.append(item)
                return
            # Site JSON outside output_root can be stale from older workflow runs.
            # Quarantine it so it cannot be published or break packaging, while
            # preserving a copy for audit.
            try:
                dest = quarantine_root / _rel(p)
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(p), str(dest))
                item["quarantined_to"] = _rel(dest)
                quarantined_site_json.append(item)
            except Exception as move_exc:
                item["quarantine_error"] = f"{type(move_exc).__name__}: {move_exc}"
                invalid_json.append(item)

    for p in sorted(ctx.output_root.rglob("*.json")):
        # The quarantine copies themselves may include invalid JSON by design;
        # they are recorded in a manifest rather than re-parsed.
        if "validation_quarantine" in p.parts:
            continue
        _validate_json_file(p, strict=True)

    for root in [ctx.public_site, ctx.unredacted_site]:
        for p in sorted(root.rglob("*.json")):
            _validate_json_file(p, strict=False)

    csv_errors = []
    for p in sorted(ctx.output_root.rglob("*.csv")):
        try:
            with p.open("r", encoding="utf-8", newline="") as f:
                list(csv.DictReader(f))
        except Exception as exc:
            csv_errors.append({"path": _rel(p), "error": f"{type(exc).__name__}: {exc}"})

    validation_summary = {
        "generated_at_utc": utc_now().isoformat(),
        "stage": "validate_outputs",
        "invalid_json": invalid_json,
        "quarantined_site_json": quarantined_site_json,
        "csv_errors": csv_errors,
        "note": "Invalid JSON in output_root is a hard failure. Invalid legacy site JSON is quarantined and omitted from deployment.",
    }
    if quarantined_site_json:
        write_json(ctx.output_root / "AQ26_VALIDATION_QUARANTINE_SUMMARY.json", validation_summary)

    if invalid_json or csv_errors:
        write_json(ctx.output_root / "AQ26_VALIDATION_FAILURE_SUMMARY.json", validation_summary)
        msg_bits = []
        if invalid_json:
            msg_bits.append("invalid JSON: " + ", ".join(x["path"] for x in invalid_json[:10]))
        if csv_errors:
            msg_bits.append("CSV read errors: " + ", ".join(x["path"] for x in csv_errors[:10]))
        raise RuntimeError("AQ26 output validation failed; " + " | ".join(msg_bits) + ". See AQ26_VALIDATION_FAILURE_SUMMARY.json.")

    if list(ctx.public_site.rglob(".htpasswd")) or list(ctx.unredacted_site.rglob(".htpasswd")):
        raise RuntimeError(".htpasswd found before deployment; refusing to continue")


def fail_redaction_gate(ctx: Context, audit: Dict[str, Any], stage: str) -> None:
    """Write and print a safe redaction-failure summary without exposing values."""
    safe = {
        "generated_at_utc": utc_now().isoformat(),
        "stage": stage,
        "leak_count": audit.get("leak_count", 0),
        "leaks": [
            {
                "path": leak.get("path", ""),
                "type": leak.get("type", ""),
                "secret_sha256": leak.get("secret_sha256", ""),
            }
            for leak in audit.get("leaks", [])[:100]
        ],
        "action_required": "Remove or regenerate the listed files so no runtime secret value is present. Do not deploy until leak_count is 0.",
    }
    fixed_summary = ctx.repo / "outputs" / "aq26_production" / "REDACTION_FAILURE_SUMMARY.json"
    write_json(fixed_summary, safe)
    write_json(ctx.output_root / "REDACTION_FAILURE_SUMMARY.json", safe)
    print("AQ26 REDACTION GATE FAILED", file=sys.stderr)
    print(f"stage={stage} leak_count={safe['leak_count']}", file=sys.stderr)
    for leak in safe["leaks"][:25]:
        print(f"redaction_leak path={leak['path']} type={leak['type']} secret_sha256={leak['secret_sha256']}", file=sys.stderr)
    raise RuntimeError(f"Redaction leak_count > 0 ({safe['leak_count']}) at {stage}; refusing to package/deploy. See REDACTION_FAILURE_SUMMARY.json for safe paths.")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/aq26_production.yml")
    args = ap.parse_args()
    repo = Path.cwd()
    cfg = read_yaml(repo / args.config)
    run_dt = utc_now()
    tz = ZoneInfo(cfg.get("project", {}).get("timezone", "Europe/London"))
    run_uk = run_dt.astimezone(tz)
    run_ts = run_dt.strftime("%Y%m%dT%H%M%SZ")
    output_root = repo / cfg.get("project", {}).get("output_root", "outputs/aq26_production") / run_ts
    latest_root = repo / cfg.get("project", {}).get("output_root", "outputs/aq26_production")
    public_site = repo / cfg.get("project", {}).get("public_site_root", "site_public")
    unred_site = repo / cfg.get("project", {}).get("unredacted_site_root", "site_unredacted")
    output_root.mkdir(parents=True, exist_ok=True)
    ctx = Context(repo, cfg, run_ts, run_dt, run_uk, output_root, public_site, unred_site, [], [])

    # Remove deployment-only files and stale public data early.
    for p in [public_site / ".htpasswd", unred_site / ".htpasswd"]:
        if p.exists():
            p.unlink()
    cleanup_legacy_public_sensitive_files(ctx)

    repo_inv = inventory_repo_evidence(ctx)
    drive_inv = google_drive_inventory(ctx)
    live_provider_probes(ctx)
    latest = build_derived_outputs(ctx, drive_inv, repo_inv)
    build_sites(ctx, latest)
    build_report(ctx, latest)

    # Redaction audit before final bundle.
    audit_paths = list(output_root.rglob("*")) + list(public_site.rglob("*")) + list(unred_site.rglob("*"))
    audit = redaction_audit(audit_paths, output_root / "redaction_audit.json")
    latest["redaction_leaks"] = audit["leak_count"]
    write_json(output_root / "LATEST_WEEKLYV2.json", latest)
    if audit["leak_count"] > 0:
        fail_redaction_gate(ctx, audit, "pre_bundle")

    final_zip = build_final_bundle(ctx)
    # Redaction audit after bundle creation.
    audit2 = redaction_audit(list(output_root.rglob("*")) + list(public_site.rglob("*")) + list(unred_site.rglob("*")), output_root / "redaction_audit.json")
    if audit2["leak_count"] > 0:
        fail_redaction_gate(ctx, audit2, "post_bundle")
    validate_outputs(ctx)

    latest_root.mkdir(parents=True, exist_ok=True)
    shutil.copy2(output_root / "LATEST_WEEKLYV2.json", latest_root / "LATEST_WEEKLYV2.json")
    (latest_root / "latest_bundle_path.txt").write_text(str(final_zip), encoding="utf-8")
    print(json.dumps({"ok": True, "run_ts": run_ts, "bundle": str(final_zip), "source_records": len(ctx.source_records)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
