#!/usr/bin/env python3
"""
AQ26 WeeklyV2 Historical Backfill + Interactive Site Data V3.2

Conservative goals:
- Do not invent historical evidence.
- Build exactly the requested weekly date spine.
- Exclude generated aggregate site files from history ingestion.
- Run date-bound backfill batches only when the underlying collector supports explicit dates.
- Write one immutable history summary per processed week.
- Produce Plotly-ready chart feeds and strict validation reports.
- Keep live/latest observatory state separate from historical backfill state.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

UTC = dt.timezone.utc

STATUS_RANK = {
    "harvested": 100,
    "partial_harvest": 90,
    "failed_validation": 80,
    "source_not_historically_available": 70,
    "pending_source_specific_backfill": 60,
    "not_yet_harvested": 10,
    "unknown": 0,
}

REQUIRED_SOURCE_FIELDS = [
    "source_name", "source_type", "status", "retrieved_at_utc", "retrieved_at_uk",
    "date_uk", "output_path", "sha256",
]

GENERATED_AGGREGATE_NAMES = {
    "weekly_index.json",
    "weekly_index.previous.json",
    "latest_summary.json",
    "source_records_latest.json",
}
GENERATED_AGGREGATE_PARTS = {"/charts/", "/tables/"}


def now_utc() -> str:
    return dt.datetime.now(UTC).isoformat()


def parse_date(value: Any) -> Optional[dt.date]:
    if not value:
        return None
    if isinstance(value, dt.date):
        return value
    text = str(value).strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return dt.datetime.strptime(text[:10], fmt).date()
        except Exception:
            pass
    try:
        return dt.datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except Exception:
        return None


def safe_int(value: Any) -> int:
    try:
        if value in (None, ""):
            return 0
        return int(float(value))
    except Exception:
        return 0


def record_count_where(records: List[Dict[str, Any]], source_type: str = "", source_name_contains: str = "") -> int:
    total = 0
    needle = source_name_contains.lower()
    for r in records:
        if source_type and str(r.get("source_type", "")) != source_type:
            continue
        if needle and needle not in str(r.get("source_name", "")).lower():
            continue
        total += safe_int(r.get("record_count")) or (1 if r.get("status") == "ok" else 0)
    return total


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8", errors="replace") as f:
        return json.load(f)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        f.write("\n")
    tmp.replace(path)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def normalise_window(obj: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    dw = obj.get("date_window") or obj.get("window") or {}
    start = dw.get("start") or obj.get("start") or obj.get("window_start") or obj.get("date_from")
    end = dw.get("end") or obj.get("end") or obj.get("window_end") or obj.get("date_to")
    sd, ed = parse_date(start), parse_date(end)
    return (sd.isoformat() if sd else None, ed.isoformat() if ed else None)


def infer_status(row: Dict[str, Any]) -> str:
    status = row.get("backfill_status") or row.get("status")
    if status:
        status = str(status)
        if status == "validated_historical_summary_loaded":
            return "harvested"
        return status
    return "harvested" if safe_int(row.get("source_record_count")) > 0 else "not_yet_harvested"


def normalise_summary(row: Dict[str, Any], source_path: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    start, end = normalise_window(row)
    if not start or not end:
        return None
    out = dict(row)
    out["date_window"] = {"start": start, "end": end}
    out["backfill_status"] = infer_status(out)
    for key in [
        "source_record_count", "ok_count", "warning_count", "error_count", "skipped_count",
        "redaction_leak_count", "satellite_product_count", "drive_file_count", "drive_folder_count",
        "high_priority_filings", "medium_priority_filings", "openaq_request_count", "news_warning_count",
    ]:
        out[key] = safe_int(out.get(key))
    # Derive counts when a latest collector manifest is used directly.
    recs = out.get("source_records")
    if isinstance(recs, list) and recs:
        out["source_record_count"] = out.get("source_record_count") or len(recs)
        out["ok_count"] = out.get("ok_count") or sum(1 for r in recs if str(r.get("status", "")).lower() == "ok")
        out["warning_count"] = out.get("warning_count") or sum(1 for r in recs if "warn" in str(r.get("status", "")).lower())
        out["error_count"] = out.get("error_count") or sum(1 for r in recs if str(r.get("status", "")).lower() == "error")
        out["skipped_count"] = out.get("skipped_count") or sum(1 for r in recs if str(r.get("status", "")).lower() == "skipped")
        out["satellite_product_count"] = out.get("satellite_product_count") or record_count_where(recs, "satellite_metadata")
        out["drive_file_count"] = out.get("drive_file_count") or record_count_where(recs, "gdrive")
        out["high_priority_filings"] = out.get("high_priority_filings") or record_count_where(recs, "official_search")
        out["openaq_request_count"] = out.get("openaq_request_count") or sum(1 for r in recs if "openaq" in str(r.get("source_name", "")).lower())
        out["news_warning_count"] = out.get("news_warning_count") or sum(1 for r in recs if str(r.get("source_type")) == "news_api_warning" or "warn" in str(r.get("status", "")).lower())
    for key in [
        "external_submission_ready", "redaction_ready", "metoffice_ready", "ground_aq_ready", "openaq_ready",
        "openaq_safety_ready", "satellite_catalogue_ready", "satellite_extraction_ready", "drive_ready",
        "drive_inventory_truncated", "cams_key_present", "cams_endpoint_configured", "cams_data_ready",
        "cdse_download_ready", "cdse_sentinelhub_ready", "gemini_summary_ready",
    ]:
        if key in out and out[key] is not None:
            out[key] = bool(out[key])
    out.pop("source_records", None)
    if source_path:
        out["_source_summary_path"] = source_path.as_posix()
    out.setdefault("run_ts", row.get("run_ts") or f"WINDOW_{start}_{end}")
    if out["source_record_count"] > 0 and out["backfill_status"] in {"not_yet_harvested", "pending_source_specific_backfill"}:
        out["backfill_status"] = "partial_harvest"
    if out["source_record_count"] > 0 and out["backfill_status"] == "validated_historical_summary_loaded":
        out["backfill_status"] = "harvested"
    return out


def is_generated_aggregate(path: Path) -> bool:
    name = path.name.lower()
    p = path.as_posix()
    if name in GENERATED_AGGREGATE_NAMES:
        return True
    return any(part in p for part in GENERATED_AGGREGATE_PARTS)


def discover_summary_rows(output_root: Path, site_root: Path) -> List[Dict[str, Any]]:
    candidates: List[Path] = []
    roots = [
        output_root / "website_history" / "two_year_validated",
        output_root / "website_history" / "history",
        output_root / "10_historical_backfill" / "history",
        output_root / "00_weeklyv2",
        site_root / "data" / "history",
    ]
    for root in roots:
        if root.exists():
            candidates.extend(root.rglob("*.json"))
    rows: List[Dict[str, Any]] = []
    seen: set[Path] = set()
    for path in sorted(candidates):
        if path in seen or is_generated_aggregate(path):
            continue
        seen.add(path)
        try:
            data = load_json(path)
            if isinstance(data, dict) and isinstance(data.get("weeks"), list):
                # Only accept manifest week arrays from immutable history folders, never public aggregate weekly_index.
                for item in data["weeks"]:
                    if isinstance(item, dict):
                        norm = normalise_summary(item, path)
                        if norm:
                            rows.append(norm)
            elif isinstance(data, dict):
                norm = normalise_summary(data, path)
                if norm:
                    rows.append(norm)
        except Exception as exc:
            print(f"[warn] cannot read candidate summary {path}: {exc}", file=sys.stderr)
    return rows


def make_week_slots(end_date: dt.date, weeks: int) -> List[Dict[str, Any]]:
    slots: List[Dict[str, Any]] = []
    for i in range(weeks):
        end = end_date - dt.timedelta(days=7 * i)
        start = end - dt.timedelta(days=7)
        slots.append({
            "run_ts": f"BACKFILL_SLOT_{start.isoformat()}_{end.isoformat()}",
            "date_window": {"start": start.isoformat(), "end": end.isoformat()},
            "backfill_status": "not_yet_harvested",
            "source_record_count": 0,
            "ok_count": 0,
            "warning_count": 0,
            "error_count": 0,
            "skipped_count": 0,
            "satellite_product_count": 0,
            "drive_file_count": 0,
            "high_priority_filings": 0,
            "medium_priority_filings": 0,
            "external_submission_ready": False,
            "final_zip_relpath": "",
            "history_slot_integrity": {
                "date_validated": True,
                "evidence_status": "pending",
                "notes": "Placeholder only. Real source-specific backfill must create evidence before scientific use.",
            },
        })
    return slots


def score_row(row: Dict[str, Any]) -> Tuple[int, int, int, str]:
    status = infer_status(row)
    rank = STATUS_RANK.get(status, 0)
    records = safe_int(row.get("source_record_count"))
    if status == "harvested" and records <= 0:
        rank = 5
    richness = sum(safe_int(row.get(k)) for k in [
        "satellite_product_count", "drive_file_count", "high_priority_filings", "medium_priority_filings", "openaq_request_count",
    ])
    created = str(row.get("created_at_utc") or row.get("run_ts") or "")
    return rank, records, richness, created


def canonical_weekly_index(rows: List[Dict[str, Any]], end_date: dt.date, weeks: int, include_out_of_range: bool = False) -> Dict[str, Any]:
    slots = make_week_slots(end_date, weeks)
    allowed = {(r["date_window"]["start"], r["date_window"]["end"]) for r in slots}
    all_rows = slots + [r for r in rows if include_out_of_range or normalise_window(r) in allowed]
    by_window: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for row in all_rows:
        start, end = normalise_window(row)
        if not start or not end:
            continue
        key = (start, end)
        if key not in by_window or score_row(row) > score_row(by_window[key]):
            by_window[key] = row
    out: List[Dict[str, Any]] = []
    for key in sorted(allowed, key=lambda x: (x[1], x[0]), reverse=True):
        row = by_window.get(key)
        if row is None:
            continue
        norm = normalise_summary(row) or dict(row)
        if safe_int(norm.get("source_record_count")) > 0:
            norm["backfill_status"] = "harvested" if norm.get("backfill_status") not in {"failed_validation"} else norm.get("backfill_status")
        out.append(norm)
    return {
        "created_at_utc": now_utc(),
        "history_end_date": end_date.isoformat(),
        "history_weeks_requested": weeks,
        "canonical_policy": {"unique_by": ["date_window.start", "date_window.end"], "status_preference": STATUS_RANK},
        "weeks": out,
    }


def write_source_records_latest(site_root: Path, output_root: Path) -> None:
    latest = output_root / "00_weeklyv2" / "LATEST_WEEKLYV2.json"
    if not latest.exists():
        return
    try:
        data = load_json(latest)
        records = data.get("source_records") if isinstance(data, dict) else None
        if isinstance(records, list):
            write_json(site_root / "data" / "source_records_latest.json", {"run_ts": data.get("run_ts"), "date_window": data.get("date_window"), "records": records})
    except Exception as exc:
        print(f"[warn] unable to refresh source_records_latest.json: {exc}", file=sys.stderr)


def preserve_latest_summaries(site_root: Path, output_root: Path) -> None:
    """Avoid mixing live/current observatory summary with backfill summaries.

    latest_summary.json remains the public live/current site summary when already
    present. The most recent date-bound batch is written to latest_backfill_summary.json.
    A latest_live_summary.json copy is also created when a live latest_summary exists.
    """
    data_dir = site_root / "data"
    live = data_dir / "latest_summary.json"
    if live.exists():
        try:
            live_data = load_json(live)
            write_json(data_dir / "latest_live_summary.json", live_data)
        except Exception as exc:
            print(f"[warn] unable to preserve latest_live_summary.json: {exc}", file=sys.stderr)
    latest = output_root / "00_weeklyv2" / "LATEST_WEEKLYV2.json"
    if latest.exists():
        try:
            latest_data = load_json(latest)
            latest_data["summary_role"] = "latest_backfill_summary"
            write_json(data_dir / "latest_backfill_summary.json", normalise_summary(latest_data) or latest_data)
        except Exception as exc:
            print(f"[warn] unable to write latest_backfill_summary.json: {exc}", file=sys.stderr)


def build_chart_feeds(site_root: Path, weekly_index: Dict[str, Any]) -> None:
    charts = site_root / "data" / "charts"
    charts.mkdir(parents=True, exist_ok=True)
    weeks = sorted(weekly_index.get("weeks", []), key=lambda x: ((x.get("date_window") or {}).get("end", ""), (x.get("date_window") or {}).get("start", "")))
    labels = [(w.get("date_window") or {}).get("end") or "" for w in weeks]

    def is_real(w: Dict[str, Any]) -> bool:
        return safe_int(w.get("source_record_count")) > 0 and infer_status(w) not in {"not_yet_harvested", "pending_source_specific_backfill"}

    def series_int(key: str) -> List[int]:
        return [safe_int(w.get(key)) if is_real(w) else 0 for w in weeks]

    def series_bool(key: str) -> List[Optional[int]]:
        out: List[Optional[int]] = []
        for w in weeks:
            if not is_real(w) or key not in w or w.get(key) is None:
                out.append(None)
            else:
                out.append(1 if bool(w.get(key)) else 0)
        return out

    write_json(charts / "weekly_record_counts.json", {
        "created_at_utc": now_utc(),
        "labels": labels,
        "series": {
            "source_records": series_int("source_record_count"),
            "ok": series_int("ok_count"),
            "warnings": series_int("warning_count"),
            "errors": series_int("error_count"),
            "skipped": series_int("skipped_count"),
        },
    })
    write_json(charts / "source_coverage_by_week.json", {
        "created_at_utc": now_utc(),
        "labels": labels,
        "series": {
            "satellite_products": series_int("satellite_product_count"),
            "drive_files": series_int("drive_file_count"),
            "high_priority_filings": series_int("high_priority_filings"),
            "medium_priority_filings": series_int("medium_priority_filings"),
            "openaq_requests": series_int("openaq_request_count"),
            "news_warnings": series_int("news_warning_count"),
        },
    })
    write_json(charts / "readiness_trend.json", {
        "created_at_utc": now_utc(),
        "labels": labels,
        "series": {
            "external_submission_ready": series_bool("external_submission_ready"),
            "redaction_ready": series_bool("redaction_ready"),
            "ground_aq_ready": series_bool("ground_aq_ready"),
            "openaq_ready": series_bool("openaq_ready"),
            "satellite_catalogue_ready": series_bool("satellite_catalogue_ready"),
            "satellite_extraction_ready": series_bool("satellite_extraction_ready"),
            "cams_data_ready": series_bool("cams_data_ready"),
            "drive_ready": series_bool("drive_ready"),
            "drive_inventory_truncated": series_bool("drive_inventory_truncated"),
        },
    })
    # Valid placeholders for future source-specific datasets.
    for name in ["pollutant_timeseries.json", "facility_control_comparison.json", "official_filings.json", "satellite_products_by_week.json"]:
        path = charts / name
        if not path.exists():
            write_json(path, {"created_at_utc": now_utc(), "status": "awaiting_source_specific_backfill", "records": []})


def patch_site_assets(site_root: Path) -> None:
    assets = site_root / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    js = assets / "aq26_charts_v3.js"
    js.write_text(r"""
(function(){
  async function getJSON(url){ const r=await fetch(url,{cache:'no-store'}); if(!r.ok) throw new Error(url+' '+r.status); return await r.json(); }
  function traces(feed, type){ const labels=feed.labels||[], series=feed.series||{}; return Object.keys(series).map(k=>({x:labels,y:series[k],type:type,mode:type==='scatter'?'lines+markers':undefined,name:k.replaceAll('_',' '),connectgaps:false})); }
  function layout(title){ return {title,margin:{t:45,l:55,r:20,b:70},paper_bgcolor:'rgba(0,0,0,0)',plot_bgcolor:'rgba(0,0,0,0)',xaxis:{automargin:true},yaxis:{rangemode:'tozero',automargin:true}}; }
  async function plot(id,url,type,title,barmode){ const el=document.getElementById(id); if(!el||typeof Plotly==='undefined') return; const feed=await getJSON(url); const lay=layout(title); if(barmode) lay.barmode=barmode; Plotly.react(id,traces(feed,type),lay,{responsive:true}); }
  async function init(){
    try{ await plot('records-chart','data/charts/weekly_record_counts.json','scatter','Weekly evidence records'); }catch(e){console.warn(e);}
    try{ await plot('coverage-chart','data/charts/source_coverage_by_week.json','bar','Source coverage by week','group'); }catch(e){console.warn(e);}
    try{ await plot('readiness-chart','data/charts/readiness_trend.json','scatter','Readiness gates over time'); }catch(e){console.warn(e);}
    try{ await plot('filings-chart','data/charts/source_coverage_by_week.json','bar','Official filings and coverage','stack'); }catch(e){console.warn(e);}
  }
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',init); else init();
})();
""", encoding="utf-8")
    for html in site_root.glob("*.html"):
        text = html.read_text(encoding="utf-8", errors="ignore")
        if "aq26_charts_v3.js" not in text:
            text = text.replace("<script src='assets/site.js'></script>", "<script src='assets/site.js'></script><script src='assets/aq26_charts_v3.js'></script>")
            text = text.replace('<script src="assets/site.js"></script>', '<script src="assets/site.js"></script><script src="assets/aq26_charts_v3.js"></script>')
            html.write_text(text, encoding="utf-8")


def read_help(script: Path) -> str:
    try:
        proc = subprocess.run([sys.executable, str(script), "--help"], capture_output=True, text=True, timeout=45)
        return (proc.stdout or "") + (proc.stderr or "")
    except Exception:
        return ""


def supported_args(help_text: str, requested: Dict[str, str]) -> List[str]:
    args: List[str] = []
    for flag, value in requested.items():
        if flag in help_text:
            args.extend([flag, value])
    return args


def copy_latest_to_history(output_root: Path, site_root: Path, start: str, end: str) -> Optional[Path]:
    latest = output_root / "00_weeklyv2" / "LATEST_WEEKLYV2.json"
    if not latest.exists():
        return None
    data = load_json(latest)
    if not isinstance(data, dict):
        return None
    data["date_window"] = {"start": start, "end": end}
    data["backfill_status"] = "harvested" if safe_int(data.get("source_record_count")) > 0 else "failed_validation"
    data["history_backfill"] = {
        "created_at_utc": now_utc(),
        "date_bound": True,
        "notes": "Immutable weekly history row generated by aq26_weeklyv2_history_v3.py backfill-batch.",
    }
    target = site_root / "data" / "history" / f"week_{start}_{end}.json"
    write_json(target, normalise_summary(data) or data)
    # Also keep a matching copy under outputs for workflow artifacts.
    normalised = normalise_summary(data) or data
    write_json(output_root / "10_historical_backfill" / "history" / f"week_{start}_{end}.json", normalised)
    write_json(site_root / "data" / "latest_backfill_summary.json", normalised)
    return target


def run_existing_pipeline_for_window(repo_root: Path, output_root: Path, site_root: Path, start: str, end: str, config: str, dry_run: bool = False) -> int:
    env = os.environ.copy()
    env.update({
        "AQ26_BACKFILL_MODE": "true",
        "AQ26_HISTORY_START_DATE": start,
        "AQ26_HISTORY_END_DATE": end,
        "AQ26_WINDOW_START_DATE": start,
        "AQ26_WINDOW_END_DATE": end,
        "AQ26_RUN_DATE_FROM": start,
        "AQ26_RUN_DATE_TO": end,
        "AQ26_NEWSAPI_ENABLED": os.environ.get("AQ26_NEWSAPI_ENABLED", "false"),
        "AQ26_NEWSDATA_ENABLED": os.environ.get("AQ26_NEWSDATA_ENABLED", "false"),
        "AQ26_GDELT_ENABLED": os.environ.get("AQ26_GDELT_ENABLED", "true"),
        "AQ26_GDELT_MIN_SECONDS": os.environ.get("AQ26_GDELT_MIN_SECONDS", "6"),
        "AQ26_GEMINI_ENABLED": os.environ.get("AQ26_GEMINI_ENABLED", "false"),
        "AQ26_GEMINI_MODEL": os.environ.get("AQ26_GEMINI_MODEL") or os.environ.get("GEMINI_MODEL", "gemini-3.5-flash"),
    })
    scripts = repo_root / "scripts"
    collect = scripts / "aq26_weeklyv2_collect.py"
    build_report = scripts / "aq26_weeklyv2_build_report.py"
    if not collect.exists():
        print("[backfill] collector script is missing", file=sys.stderr)
        return 2
    help_text = read_help(collect)
    required = ["--start-date", "--end-date", "--output-root"]
    missing = [flag for flag in required if flag not in help_text]
    if missing:
        print(f"[backfill] collector does not support date-bound backfill flags: {missing}", file=sys.stderr)
        return 2
    collect_cmd = [sys.executable, str(collect), "--config", config, "--output-root", str(output_root), "--start-date", start, "--end-date", end]
    commands = [collect_cmd]
    if build_report.exists():
        report_help = read_help(build_report)
        report_flags = supported_args(report_help, {"--output-root": str(output_root), "--start-date": start, "--end-date": end})
        commands.append([sys.executable, str(build_report)] + report_flags)
    for cmd in commands:
        print("[backfill] RUN", " ".join(map(str, cmd)))
        if dry_run:
            continue
        proc = subprocess.run(cmd, cwd=str(repo_root), env=env, text=True)
        if proc.returncode:
            print(f"[backfill] command failed {proc.returncode}: {cmd}", file=sys.stderr)
            return proc.returncode
    if not dry_run:
        target = copy_latest_to_history(output_root, site_root, start, end)
        if not target:
            print(f"[backfill] no latest summary available for {start}..{end}", file=sys.stderr)
            return 2
        print(f"[backfill] wrote immutable history summary: {target}")
    return 0


def run_backfill_batch(args: argparse.Namespace) -> int:
    repo = Path(args.repo_root).resolve()
    output = Path(args.output_root).resolve()
    site = Path(args.site_root).resolve()
    end = parse_date(args.backfill_end_date) or parse_date(args.history_end_date) or dt.date.today()
    requested_start = str(args.backfill_start_date or "").strip().lower()

    # AQ26 V3.2.1: support backfill_start_date=auto/next and, even with a
    # manual older start date, select the next missing immutable week files
    # before applying the run limit. This prevents accidental repeat-skip runs.
    if requested_start in {"auto", "next", "next-missing", "first-missing"}:
        spine = make_week_slots(end, args.history_weeks)
        missing = []
        for slot in spine:
            s0, e0 = slot["date_window"]["start"], slot["date_window"]["end"]
            target = site / "data" / "history" / f"week_{s0}_{e0}.json"
            if not target.exists() or args.force:
                missing.append((s0, e0))
        if not missing:
            print("[backfill] no missing weekly history slots remain in the canonical spine")
            return 0
        windows = missing[: args.backfill_limit_windows or len(missing)]
        print(f"[backfill] auto-selected {len(windows)} missing windows from canonical {args.history_weeks}-week spine ending {end}")
    else:
        start = parse_date(args.backfill_start_date) or (end - dt.timedelta(days=7 * args.history_weeks))
        if start >= end:
            raise ValueError("backfill_start_date must be earlier than backfill_end_date")
        all_windows: List[Tuple[str, str]] = []
        cur = start
        while cur < end:
            nxt = min(cur + dt.timedelta(days=7), end)
            all_windows.append((cur.isoformat(), nxt.isoformat()))
            cur = nxt
        if args.force:
            windows = all_windows[: args.backfill_limit_windows or len(all_windows)]
        else:
            windows = []
            for start_s, end_s in all_windows:
                target = site / "data" / "history" / f"week_{start_s}_{end_s}.json"
                if target.exists():
                    print(f"[backfill] SKIP existing {target}")
                    continue
                windows.append((start_s, end_s))
                if args.backfill_limit_windows and len(windows) >= args.backfill_limit_windows:
                    break
        print(f"[backfill] selected_windows={len(windows)} requested_range={start}..{end} force={args.force}")

    failures = []
    for start_s, end_s in windows:
        rc = run_existing_pipeline_for_window(repo, output, site, start_s, end_s, args.config, dry_run=args.dry_run)
        if rc:
            failures.append((start_s, end_s, rc))
            if args.stop_on_first_failure:
                break
    if failures:
        print(f"[backfill] failures={failures}", file=sys.stderr)
        return 2
    return 0


def validate_site_data(site_root: Path, output_root: Path, history_weeks: int, history_end_date: dt.date, strict: bool = False) -> Tuple[bool, List[str]]:
    issues: List[str] = []
    for path in list((site_root / "data").rglob("*.json")) + list((output_root / "website_history").rglob("*.json")) + list((output_root / "10_historical_backfill").rglob("*.json")):
        try:
            load_json(path)
        except Exception as exc:
            issues.append(f"JSON parse failed: {path}: {exc}")
    weekly_path = site_root / "data" / "weekly_index.json"
    if weekly_path.exists():
        weeks = load_json(weekly_path).get("weeks", [])
        if len(weeks) != history_weeks:
            issues.append(f"weekly row count mismatch: expected {history_weeks}, found {len(weeks)}")
        expected_keys = {(r["date_window"]["start"], r["date_window"]["end"]) for r in make_week_slots(history_end_date, history_weeks)}
        seen: List[Tuple[Optional[str], Optional[str]]] = []
        for row in weeks:
            key = normalise_window(row)
            seen.append(key)
            if key not in expected_keys:
                issues.append(f"weekly row outside expected date spine: {key[0]}..{key[1]}")
            if infer_status(row) == "harvested" and safe_int(row.get("source_record_count")) <= 0:
                issues.append(f"harvested row has zero records: {key[0]}..{key[1]}")
            src = str(row.get("_source_summary_path") or "")
            if src and any(name in src for name in GENERATED_AGGREGATE_NAMES):
                issues.append(f"generated aggregate used as source summary: {src}")
        duplicates = {k for k in seen if seen.count(k) > 1}
        for key in sorted(duplicates):
            issues.append(f"duplicate weekly window: {key[0]}..{key[1]}")
    else:
        issues.append(f"missing weekly index: {weekly_path}")

    source_path = site_root / "data" / "source_records_latest.json"
    if source_path.exists():
        data = load_json(source_path)
        records = data.get("records", []) if isinstance(data, dict) else []
        for i, record in enumerate(records[:10000]):
            missing = [field for field in REQUIRED_SOURCE_FIELDS if field not in record]
            if missing:
                issues.append(f"source record {i} missing {missing}")
            urlish = f"{record.get('url','')} {record.get('query','')} {record.get('error','')}"
            if re.search(r"(?i)(api[_-]?key|token|secret|password)=([^*&\s]{8,})", urlish) and "REDACTED" not in urlish:
                issues.append(f"secret-like unredacted value in source record {i}")
    for path in output_root.rglob("*.csv"):
        try:
            with path.open("r", encoding="utf-8", errors="replace", newline="") as f:
                reader = csv.reader(f)
                for j, _row in enumerate(reader):
                    if j > 5000:
                        break
        except Exception as exc:
            issues.append(f"CSV read failed: {path}: {exc}")
    for html in site_root.glob("*.html"):
        text = html.read_text(encoding="utf-8", errors="ignore")
        for href in re.findall(r"href=['\"]([^'\"]+)['\"]", text):
            if href.startswith(("http", "#", "mailto:", "tel:")):
                continue
            rel = href.split("#")[0].split("?")[0]
            if not rel:
                continue
            target = (site_root / rel).resolve()
            if not target.exists() and rel.startswith(("downloads/", "data/", "assets/")):
                issues.append(f"missing linked file from {html.name}: {href}")
    ok = not issues
    return ok, issues


def command_build(args: argparse.Namespace) -> int:
    output = Path(args.output_root).resolve()
    site = Path(args.site_root).resolve()
    end = parse_date(args.history_end_date) or dt.date.today()
    rows = discover_summary_rows(output, site)
    index = canonical_weekly_index(rows, end, args.history_weeks)
    write_json(site / "data" / "weekly_index.json", index)
    write_source_records_latest(site, output)
    preserve_latest_summaries(site, output)
    build_chart_feeds(site, index)
    patch_site_assets(site)
    ok, issues = validate_site_data(site, output, args.history_weeks, end, strict=args.strict)
    report = {"created_at_utc": now_utc(), "ok": ok, "issue_count": len(issues), "issues": issues[:500]}
    write_json(output / "99_integrity" / "AQ26_WEEKLYV2_SITE_V3_VALIDATION.json", report)
    for issue in issues[:80]:
        print("[validate]", issue)
    print(f"[done] rows={len(index.get('weeks', []))} harvested={sum(1 for w in index.get('weeks', []) if safe_int(w.get('source_record_count'))>0)}")
    return 3 if args.strict and not ok else 0


def command_validate(args: argparse.Namespace) -> int:
    end = parse_date(args.history_end_date) or dt.date.today()
    ok, issues = validate_site_data(Path(args.site_root).resolve(), Path(args.output_root).resolve(), args.history_weeks, end, strict=args.strict)
    for issue in issues:
        print("[validate]", issue)
    print(f"[validate] ok={ok} issues={len(issues)}")
    return 3 if args.strict and not ok else 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--output-root", default="outputs")
    parser.add_argument("--site-root", default="site_public")
    parser.add_argument("--history-weeks", type=int, default=int(os.getenv("AQ26_HISTORY_WEEKS", "104")))
    parser.add_argument("--history-end-date", default=os.getenv("AQ26_HISTORY_END_DATE") or dt.date.today().isoformat())
    parser.add_argument("--config", default="configs/aq26_weekly_v2_sources.yml")
    parser.add_argument("--strict", action="store_true")
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("build-site-data")
    sub.add_parser("validate")
    bp = sub.add_parser("backfill-batch")
    bp.add_argument("--backfill-start-date", default=os.getenv("AQ26_BACKFILL_START_DATE", ""))
    bp.add_argument("--backfill-end-date", default=os.getenv("AQ26_BACKFILL_END_DATE", ""))
    bp.add_argument("--backfill-limit-windows", type=int, default=int(os.getenv("AQ26_BACKFILL_LIMIT_WINDOWS", "4")))
    bp.add_argument("--force", action="store_true")
    bp.add_argument("--dry-run", action="store_true")
    bp.add_argument("--stop-on-first-failure", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.cmd == "backfill-batch":
            return run_backfill_batch(args)
        if args.cmd == "validate":
            return command_validate(args)
        return command_build(args)
    except Exception:
        traceback.print_exc()
        return 99


if __name__ == "__main__":
    raise SystemExit(main())
