#!/usr/bin/env python3
"""
AQ26 WeeklyV2 Science Backfill V3.3
===================================

A conservative, provenance-first historical backfill and site-data builder for the
AirQuality26 / SCC Nexus controlled-review evidence platform.

Design principles
-----------------
1. Do not invent evidence. Missing historical weeks remain not_yet_harvested.
2. Date-bound backfill only. A harvested week must have a collector summary whose
   date_window exactly matches the requested weekly window.
3. Preserve provenance. Every harvested week is written as an immutable JSON file
   under site_public/data/history/week_YYYY-MM-DD_YYYY-MM-DD.json.
4. Separate live observatory state from historical backfill state.
5. Keep external submission false until science gates pass.
6. Make validation strict enough for institutional review by WHO/UNEP/EEA/C40 style
   audiences and expert critique, while clearly separating warnings from blockers.

Typical use
-----------
Run next earliest missing four weeks and rebuild site data:

  python scripts/aq26_weeklyv2_science_backfill_v33.py run-batch \
    --repo-root . \
    --collector-script scripts/aq26_weeklyv2_collect.py \
    --config configs/aq26_weekly_v2_sources.yml \
    --output-root outputs \
    --site-root site_public \
    --history-end-date 2026-05-25 \
    --history-weeks 104 \
    --backfill-start-date auto \
    --auto-mode earliest_missing \
    --backfill-limit-windows 4 \
    --strict

Then the script writes:
  site_public/data/weekly_index.json
  site_public/data/latest_backfill_summary.json
  site_public/data/charts/*.json
  outputs/99_integrity/AQ26_WEEKLYV2_SCIENCE_V33_VALIDATION.json
"""
from __future__ import annotations

import argparse
import csv
import dataclasses
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

UTC = dt.timezone.utc

STATUS_RANK = {
    "harvested": 100,
    "partial_harvest": 90,
    "failed_validation": 80,
    "source_not_historically_available": 70,
    "pending_source_specific_backfill": 50,
    "not_yet_harvested": 10,
    "unknown": 0,
}

SCIENCE_REQUIRED_GATES = [
    "ground_aq_ready",
    "openaq_ready",
    "satellite_catalogue_ready",
    "redaction_ready",
]

EXTERNAL_REQUIRED_GATES = [
    "ground_aq_ready",
    "openaq_ready",
    "satellite_catalogue_ready",
    "satellite_extraction_ready",
    "cams_data_ready",
    "redaction_ready",
]

REQUIRED_SOURCE_FIELDS = [
    "source_name",
    "source_type",
    "status",
    "retrieved_at_utc",
    "retrieved_at_uk",
    "date_uk",
    "output_path",
    "sha256",
]

AGGREGATE_NAMES_EXCLUDE = {
    "weekly_index.json",
    "latest_summary.json",
    "latest_live_summary.json",
    "latest_backfill_summary.json",
    "source_records_latest.json",
}

# ---------------------------------------------------------------------------
# Basic utilities
# ---------------------------------------------------------------------------

def now_utc_dt() -> dt.datetime:
    return dt.datetime.now(UTC)


def now_utc() -> str:
    return now_utc_dt().replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_date(value: Any) -> Optional[dt.date]:
    if value is None:
        return None
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    s = str(value).strip()
    if not s:
        return None
    # Common AQ26 formats.
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y%m%d"):
        try:
            return dt.datetime.strptime(s[:10] if fmt != "%Y%m%d" else s[:8], fmt).date()
        except Exception:
            pass
    try:
        return dt.datetime.fromisoformat(s.replace("Z", "+00:00")).date()
    except Exception:
        return None


def iso(d: dt.date) -> str:
    return d.isoformat()


def safe_int(value: Any) -> int:
    try:
        if value is None or value == "":
            return 0
        return int(float(value))
    except Exception:
        return 0


def safe_bool(value: Any) -> Optional[bool]:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    s = str(value).strip().lower()
    if s in {"true", "1", "yes", "y", "ok", "ready"}:
        return True
    if s in {"false", "0", "no", "n", "not_ready", "missing"}:
        return False
    return None


def mkdir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data: Any) -> None:
    mkdir(path.parent)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, sort_keys=False, default=str)
        f.write("\n")
    tmp.replace(path)


def relpath(path: Optional[Path], root: Path) -> str:
    if not path:
        return ""
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except Exception:
        return path.as_posix()


def redact_text(s: str) -> str:
    if not s:
        return s
    # Basic secret redaction for validation/reporting. Does not mutate evidence files except
    # for newly generated validation metadata.
    s = re.sub(r"(?i)(api[_-]?key|token|secret|password|client_secret|authorization)[=:\s]+[A-Za-z0-9_\-\.]{8,}", r"\1=***REDACTED***", s)
    s = re.sub(r"(?i)(Bearer\s+)[A-Za-z0-9_\-\.]{12,}", r"\1***REDACTED***", s)
    return s


def list_dicts_from_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                if isinstance(obj, dict):
                    rows.append(obj)
            except Exception:
                pass
    return rows

# ---------------------------------------------------------------------------
# Environment aliases
# ---------------------------------------------------------------------------

def env_first(*names: str) -> str:
    for name in names:
        v = os.getenv(name)
        if v:
            return v.strip()
    return ""


def apply_secret_aliases() -> Dict[str, bool]:
    """Populate common aliases expected by older/newer AQ26 scripts.

    Values are not printed. The returned diagnostics only say whether a family is present.
    """
    alias_groups = {
        "CDSE_USERNAME": ["CDSE_USERNAME"],
        "CDSE_PASSWORD": ["CDSE_PASSWORD"],
        "CDSE_ID": ["CDSE_ID", "CDSE_CLIENT_ID"],
        "CDSE_SECRET": ["CDSE_SECRET", "CDSE_CLIENT_SECRET"],
        "CDSE_CLIENT_ID": ["CDSE_CLIENT_ID", "CDSE_ID"],
        "CDSE_CLIENT_SECRET": ["CDSE_CLIENT_SECRET", "CDSE_SECRET"],
        "GEMINI_MODEL": ["GEMINI_MODEL", "AQ26_GEMINI_MODEL"],
        "AQ26_GEMINI_MODEL": ["AQ26_GEMINI_MODEL", "GEMINI_MODEL"],
        "NEWSAPI_KEY": ["NEWSAPI_KEY", "NEWS_API_KEY"],
        "NEWS_API_KEY": ["NEWS_API_KEY", "NEWSAPI_KEY"],
        "NEWSDATA_API_KEY": ["NEWSDATA_API_KEY", "NEWS_DATA_IO_KEY"],
        "NEWS_DATA_IO_KEY": ["NEWS_DATA_IO_KEY", "NEWSDATA_API_KEY"],
        "METOFFICE_API_KEY": ["METOFFICE_API_KEY", "MET_OFFICE_API_KEY"],
        "MET_OFFICE_API_KEY": ["MET_OFFICE_API_KEY", "METOFFICE_API_KEY"],
    }
    for target, names in alias_groups.items():
        if not os.getenv(target):
            v = env_first(*names)
            if v:
                os.environ[target] = v
    # Backfill-safe defaults. The workflow can override these explicitly.
    os.environ.setdefault("AQ26_NEWSAPI_ENABLED", "false")
    os.environ.setdefault("AQ26_NEWSDATA_ENABLED", "false")
    os.environ.setdefault("AQ26_GEMINI_ENABLED", "false")
    os.environ.setdefault("AQ26_GDELT_ENABLED", "true")
    os.environ.setdefault("AQ26_GDELT_MIN_SECONDS", "8")
    os.environ.setdefault("AQ26_BACKFILL_NEWS_QUERY_LIMIT", "2")
    os.environ.setdefault("AQ26_GEMINI_MODEL", env_first("AQ26_GEMINI_MODEL", "GEMINI_MODEL") or "gemini-3.5-flash")
    os.environ.setdefault("GEMINI_MODEL", env_first("GEMINI_MODEL", "AQ26_GEMINI_MODEL") or "gemini-3.5-flash")
    return {
        "cdse_username_password_present": bool(env_first("CDSE_USERNAME") and env_first("CDSE_PASSWORD")),
        "cdse_client_alias_present": bool(env_first("CDSE_ID", "CDSE_CLIENT_ID") and env_first("CDSE_SECRET", "CDSE_CLIENT_SECRET")),
        "gdrive_present": bool(env_first("GDRIVE_FOLDER_ID") and env_first("GDRIVE_SERVICE_ACCOUNT")),
        "gemini_present": bool(env_first("GEMINI_API_KEY")),
        "openaq_present": bool(env_first("OPENAQ_API_KEY")),
        "metoffice_present": bool(env_first("METOFFICE_API_KEY", "MET_OFFICE_API_KEY")),
        "openweather_present": bool(env_first("OPENWEATHER_KEY")),
        "cams_present": bool(env_first("CAMS_API_KEY", "CAMS_ENDPOINT")),
    }

# ---------------------------------------------------------------------------
# Weekly windows and history
# ---------------------------------------------------------------------------

@dataclasses.dataclass(frozen=True)
class Window:
    start: dt.date
    end: dt.date

    @property
    def key(self) -> str:
        return f"{self.start.isoformat()}_{self.end.isoformat()}"

    @property
    def filename(self) -> str:
        return f"week_{self.key}.json"

    def as_dict(self) -> Dict[str, str]:
        return {"start": self.start.isoformat(), "end": self.end.isoformat()}


def generate_week_windows(history_end_date: dt.date, history_weeks: int) -> List[Window]:
    windows: List[Window] = []
    for i in range(history_weeks):
        end = history_end_date - dt.timedelta(days=7 * i)
        start = end - dt.timedelta(days=7)
        windows.append(Window(start=start, end=end))
    # Return chronological order by default for systematic backfill.
    return sorted(windows, key=lambda w: (w.start, w.end))


def window_from_row(row: Dict[str, Any]) -> Optional[Window]:
    dw = row.get("date_window") or {}
    start = parse_date(dw.get("start") or row.get("start") or row.get("window_start") or row.get("date_from"))
    end = parse_date(dw.get("end") or row.get("end") or row.get("window_end") or row.get("date_to"))
    if not start or not end:
        return None
    return Window(start=start, end=end)


def history_file(site_root: Path, window: Window) -> Path:
    return site_root / "data" / "history" / window.filename


def existing_history_windows(site_root: Path) -> Dict[Window, Path]:
    out: Dict[Window, Path] = {}
    hist = site_root / "data" / "history"
    if not hist.exists():
        return out
    for p in sorted(hist.glob("week_*.json")):
        try:
            data = read_json(p)
            if isinstance(data, dict):
                w = window_from_row(data)
                if w:
                    out[w] = p
        except Exception:
            pass
    return out


def choose_windows(
    all_windows: List[Window],
    site_root: Path,
    backfill_start_date: str,
    backfill_end_date: dt.date,
    limit: int,
    auto_mode: str,
    force: bool,
) -> List[Window]:
    existing = existing_history_windows(site_root)
    start_date = parse_date(backfill_start_date) if backfill_start_date.lower() != "auto" else None
    candidates = [w for w in all_windows if w.end <= backfill_end_date]
    if start_date:
        candidates = [w for w in candidates if w.start >= start_date]
    if not force:
        candidates = [w for w in candidates if w not in existing]
    auto_mode = auto_mode.lower().strip()
    if auto_mode not in {"earliest_missing", "latest_missing", "chronological", "reverse_chronological"}:
        raise ValueError(f"Unsupported auto_mode={auto_mode!r}")
    if backfill_start_date.lower() == "auto":
        reverse = auto_mode in {"latest_missing", "reverse_chronological"}
    else:
        # Explicit start date should continue forward chronologically unless explicitly reverse.
        reverse = auto_mode in {"latest_missing", "reverse_chronological"}
    candidates = sorted(candidates, key=lambda w: (w.start, w.end), reverse=reverse)
    if limit and limit > 0:
        candidates = candidates[:limit]
    return candidates

# ---------------------------------------------------------------------------
# Collector invocation and summary normalisation
# ---------------------------------------------------------------------------

def collector_supports_dates(repo_root: Path, collector_script: Path) -> bool:
    script = collector_script if collector_script.is_absolute() else repo_root / collector_script
    if not script.exists():
        return False
    try:
        cp = subprocess.run(
            [sys.executable, str(script), "--help"],
            cwd=str(repo_root),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=30,
            check=False,
        )
        help_text = cp.stdout or ""
        return "--start-date" in help_text and "--end-date" in help_text
    except Exception:
        return False


def run_collector_for_window(
    repo_root: Path,
    collector_script: Path,
    config: Path,
    run_output_root: Path,
    window: Window,
    strict: bool,
) -> Tuple[int, str]:
    script = collector_script if collector_script.is_absolute() else repo_root / collector_script
    cfg = config if config.is_absolute() else repo_root / config
    mkdir(run_output_root)
    supports_dates = collector_supports_dates(repo_root, collector_script)
    if not supports_dates:
        msg = (
            f"Collector {script} does not advertise --start-date/--end-date. "
            "Refusing date-bound backfill in strict mode to avoid fake historical evidence."
        )
        if strict:
            return 98, msg
        # Non-strict fallback is still marked failed later if dates do not match.
        lookback = max((window.end - window.start).days, 7)
        cmd = [sys.executable, str(script), "--config", str(cfg), "--output-root", str(run_output_root), "--lookback-days", str(lookback)]
    else:
        cmd = [
            sys.executable,
            str(script),
            "--config",
            str(cfg),
            "--output-root",
            str(run_output_root),
            "--start-date",
            window.start.isoformat(),
            "--end-date",
            window.end.isoformat(),
        ]
    started = time.time()
    cp = subprocess.run(
        cmd,
        cwd=str(repo_root),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=int(os.getenv("AQ26_COLLECTOR_TIMEOUT_SECONDS", "2700")),
        check=False,
    )
    elapsed = time.time() - started
    log = f"$ {' '.join(cmd)}\n# elapsed_seconds={elapsed:.1f}\n" + (cp.stdout or "")
    return cp.returncode, log


def find_latest_collector_summary(run_output_root: Path) -> Optional[Path]:
    candidates = [
        run_output_root / "00_weeklyv2" / "LATEST_WEEKLYV2.json",
        run_output_root / "00_live_harvest" / "LATEST_HARVEST.json",
    ]
    candidates.extend(sorted((run_output_root / "00_weeklyv2").glob("AQ26_WEEKLYV2_*/*MANIFEST*.json")) if (run_output_root / "00_weeklyv2").exists() else [])
    candidates = [p for p in candidates if p.exists()]
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def find_source_records(run_output_root: Path, summary: Dict[str, Any]) -> List[Dict[str, Any]]:
    records = summary.get("source_records")
    if isinstance(records, list):
        return [r for r in records if isinstance(r, dict)]
    # Fallback to source_history JSONL.
    return list_dicts_from_jsonl(run_output_root / "source_history" / "source_index.jsonl")


def load_readiness_gates(run_output_root: Path) -> Dict[str, Any]:
    p = run_output_root / "12_scoring" / "evidence_readiness_gates.json"
    if p.exists():
        try:
            obj = read_json(p)
            return obj if isinstance(obj, dict) else {}
        except Exception:
            return {}
    return {}


def count_by(records: List[Dict[str, Any]], field: str) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for r in records:
        k = str(r.get(field) or "unknown")
        out[k] = out.get(k, 0) + 1
    return dict(sorted(out.items()))


def sum_record_counts(records: List[Dict[str, Any]], source_type: str) -> int:
    return sum(safe_int(r.get("record_count")) for r in records if str(r.get("source_type") or "") == source_type)


def records_count_type(records: List[Dict[str, Any]], source_type: str) -> int:
    return sum(1 for r in records if str(r.get("source_type") or "") == source_type)


def normalise_collector_summary(
    raw: Dict[str, Any],
    records: List[Dict[str, Any]],
    gates: Dict[str, Any],
    run_output_root: Path,
    repo_root: Path,
    window: Window,
    collector_exit_code: int,
    collector_log_path: Path,
) -> Dict[str, Any]:
    # Strict date-window match; no silent current-window contamination.
    raw_w = window_from_row(raw) or Window(parse_date(raw.get("start")) or window.start, parse_date(raw.get("end")) or window.end)
    exact_window = raw_w == window
    status_counts = count_by(records, "status")
    type_counts = count_by(records, "source_type")

    official_summary = {}
    for p in [run_output_root / "06_official_filings" / "official_priority_summary.json", run_output_root / "06_official_filings" / "official_filing_index.json"]:
        if p.exists():
            try:
                official_summary[p.name] = read_json(p)
            except Exception:
                pass

    satellite_meta = {}
    sat_path = run_output_root / "07_satellite_cdse" / "satellite_catalogue_metadata.json"
    if sat_path.exists():
        try:
            satellite_meta = read_json(sat_path)
        except Exception:
            satellite_meta = {}

    drive_inventory_truncated = None
    drive_limit = None
    drive_path = run_output_root / "08_gdrive_snapshot" / "gdrive_recursive_inventory.json"
    if drive_path.exists():
        try:
            drive_obj = read_json(drive_path)
            if isinstance(drive_obj, dict):
                drive_inventory_truncated = safe_bool(drive_obj.get("drive_inventory_truncated"))
                drive_limit = safe_int(drive_obj.get("max_files") or drive_obj.get("limit") or drive_obj.get("record_limit")) or None
        except Exception:
            pass

    high_filings = safe_int(raw.get("high_priority_filings"))
    med_filings = safe_int(raw.get("medium_priority_filings"))
    # Support likely official priority summary structures.
    for obj in official_summary.values():
        if isinstance(obj, dict):
            high_filings = high_filings or safe_int(obj.get("high_priority_filings") or obj.get("high_priority_count") or obj.get("high") or obj.get("priority_high"))
            med_filings = med_filings or safe_int(obj.get("medium_priority_filings") or obj.get("medium_priority_count") or obj.get("medium") or obj.get("priority_medium"))

    satellite_count = safe_int(raw.get("satellite_product_count"))
    if not satellite_count:
        satellite_count = safe_int(satellite_meta.get("product_count") or satellite_meta.get("record_count") or satellite_meta.get("count"))
        if not satellite_count and isinstance(satellite_meta.get("products"), list):
            satellite_count = len(satellite_meta["products"])
    if not satellite_count:
        satellite_count = sum_record_counts(records, "satellite_metadata")

    drive_count = safe_int(raw.get("drive_file_count")) or sum_record_counts(records, "gdrive")

    source_record_count = len(records) if records else safe_int(raw.get("source_record_count"))
    ok_count = status_counts.get("ok", safe_int(raw.get("ok_count")))
    warning_count = status_counts.get("warning", safe_int(raw.get("warning_count")))
    error_count = status_counts.get("error", safe_int(raw.get("error_count")))
    skipped_count = status_counts.get("skipped", safe_int(raw.get("skipped_count")))

    backfill_status = "harvested" if collector_exit_code == 0 and exact_window and source_record_count > 0 else "failed_validation"
    if collector_exit_code == 0 and exact_window and error_count > 0 and source_record_count > 0:
        # Evidence exists but needs attention; do not pretend all-clean.
        backfill_status = "partial_harvest"

    readiness = {}
    for key in set(SCIENCE_REQUIRED_GATES + EXTERNAL_REQUIRED_GATES + [
        "metoffice_ready", "openaq_safety_ready", "drive_ready", "drive_inventory_truncated",
        "cams_key_present", "cams_endpoint_configured", "cdse_auth_ready", "cdse_download_ready",
        "cdse_sentinelhub_ready", "gemini_summary_ready", "backfill_ready", "external_submission_ready",
    ]):
        if key in gates:
            readiness[key] = safe_bool(gates.get(key))
        elif key in raw:
            readiness[key] = safe_bool(raw.get(key))
        else:
            readiness[key] = None

    # External readiness is fail-closed.
    readiness["external_submission_ready"] = bool(readiness.get("external_submission_ready")) and all(readiness.get(k) is True for k in EXTERNAL_REQUIRED_GATES)

    out: Dict[str, Any] = {
        "schema_version": "AQ26_WEEKLYV2_SCIENCE_V33_HISTORY_1",
        "created_at_utc": now_utc(),
        "run_ts": raw.get("run_ts") or now_utc_dt().strftime("%Y%m%dT%H%M%SZ"),
        "date_window": window.as_dict(),
        "status": backfill_status,
        "backfill_status": backfill_status,
        "collector_exit_code": collector_exit_code,
        "collector_date_window_exact_match": exact_window,
        "collector_raw_date_window": raw_w.as_dict(),
        "source_record_count": source_record_count,
        "ok_count": ok_count,
        "warning_count": warning_count,
        "error_count": error_count,
        "skipped_count": skipped_count,
        "source_type_counts": type_counts,
        "source_status_counts": status_counts,
        "satellite_product_count": satellite_count,
        "drive_file_count": drive_count,
        "drive_inventory_truncated": drive_inventory_truncated,
        "drive_inventory_limit": drive_limit,
        "high_priority_filings": high_filings,
        "medium_priority_filings": med_filings,
        "openaq_request_count": records_count_type(records, "ground_aq") + records_count_type(records, "openaq") + safe_int(raw.get("openaq_request_count")),
        "news_warning_count": records_count_type(records, "news_api_warning") + safe_int(raw.get("news_warning_count")),
        "readiness": readiness,
        "external_submission_ready": readiness.get("external_submission_ready") is True,
        "controlled_use_boundary": raw.get("controlled_use_boundary") or "Controlled-review environmental intelligence only; no endorsement, regulatory determination, medical advice, legal conclusion or causal attribution is claimed.",
        "provenance": {
            "collector_output_root": relpath(run_output_root, repo_root),
            "collector_summary_relpath": relpath(find_latest_collector_summary(run_output_root), repo_root),
            "collector_log_relpath": relpath(collector_log_path, repo_root),
            "source_records_present": bool(records),
            "source_records_required_fields": REQUIRED_SOURCE_FIELDS,
        },
        "review_positioning": {
            "intended_review_audience": ["WHO", "UNEP", "EEA", "C40 Cities", "independent academic expert review"],
            "expert_critique_guardrail": "Outputs are framed for scrutiny by air-quality, exposure-science, atmospheric-modelling and environmental-policy experts; causal claims remain gated until source, confounder, uncertainty and validation requirements pass.",
            "not_for_claims": ["endorsement", "regulatory breach determination", "health outcome attribution", "single-source causal attribution"],
        },
    }
    return out


def run_one_window(args: argparse.Namespace, window: Window) -> Dict[str, Any]:
    repo_root = Path(args.repo_root).resolve()
    output_root = (repo_root / args.output_root).resolve() if not Path(args.output_root).is_absolute() else Path(args.output_root).resolve()
    site_root = (repo_root / args.site_root).resolve() if not Path(args.site_root).is_absolute() else Path(args.site_root).resolve()
    run_output_root = output_root / "10_historical_backfill" / f"week_{window.key}"
    log_path = output_root / "98_logs" / f"collector_{window.key}.log"
    mkdir(log_path.parent)

    rc, log = run_collector_for_window(
        repo_root=repo_root,
        collector_script=Path(args.collector_script),
        config=Path(args.config),
        run_output_root=run_output_root,
        window=window,
        strict=args.strict,
    )
    log_path.write_text(redact_text(log), encoding="utf-8")
    summary_path = find_latest_collector_summary(run_output_root)
    if not summary_path:
        raw = {"run_ts": now_utc_dt().strftime("%Y%m%dT%H%M%SZ"), "date_window": window.as_dict(), "source_record_count": 0}
        records: List[Dict[str, Any]] = []
        gates: Dict[str, Any] = {}
        rc = rc if rc != 0 else 97
    else:
        raw = read_json(summary_path)
        if not isinstance(raw, dict):
            raw = {"date_window": window.as_dict(), "source_record_count": 0}
        records = find_source_records(run_output_root, raw)
        gates = load_readiness_gates(run_output_root)
    hist = normalise_collector_summary(raw, records, gates, run_output_root, repo_root, window, rc, log_path)

    hist_path = history_file(site_root, window)
    write_json(hist_path, hist)
    # Mirror into outputs for artifact/history durability.
    write_json(output_root / "10_historical_backfill" / "history" / window.filename, hist)
    # Latest source records for public table; write most recently run window.
    source_records_latest = {
        "created_at_utc": now_utc(),
        "date_window": window.as_dict(),
        "history_file": relpath(hist_path, repo_root),
        "records": records,
    }
    write_json(site_root / "data" / "source_records_latest.json", source_records_latest)
    write_json(output_root / "10_historical_backfill" / "source_records_latest.json", source_records_latest)
    return hist

# ---------------------------------------------------------------------------
# Weekly index, charts, validation
# ---------------------------------------------------------------------------

def placeholder_for_window(window: Window) -> Dict[str, Any]:
    return {
        "schema_version": "AQ26_WEEKLYV2_SCIENCE_V33_HISTORY_1",
        "run_ts": f"BACKFILL_SLOT_{window.key}",
        "date_window": window.as_dict(),
        "status": "not_yet_harvested",
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
        "openaq_request_count": 0,
        "news_warning_count": 0,
        "readiness": {},
        "external_submission_ready": False,
        "history_slot_integrity": {
            "evidence_status": "pending",
            "notes": "Placeholder only. This row must not be used as historical evidence until source-specific backfill creates real source records.",
        },
    }


def score_history(row: Dict[str, Any]) -> Tuple[int, int, int, str]:
    st = str(row.get("backfill_status") or row.get("status") or "unknown")
    rank = STATUS_RANK.get(st, 0)
    records = safe_int(row.get("source_record_count"))
    richness = sum(safe_int(row.get(k)) for k in ["satellite_product_count", "drive_file_count", "high_priority_filings", "medium_priority_filings", "openaq_request_count"])
    created = str(row.get("created_at_utc") or row.get("run_ts") or "")
    if st in {"harvested", "partial_harvest"} and records <= 0:
        rank = 5
    return rank, records, richness, created


def load_history_rows(site_root: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    hist_dir = site_root / "data" / "history"
    if not hist_dir.exists():
        return rows
    for p in sorted(hist_dir.glob("week_*.json")):
        if p.name in AGGREGATE_NAMES_EXCLUDE:
            continue
        try:
            obj = read_json(p)
            if isinstance(obj, dict):
                w = window_from_row(obj)
                if not w:
                    continue
                obj["date_window"] = w.as_dict()
                obj.setdefault("status", obj.get("backfill_status") or "unknown")
                obj.setdefault("backfill_status", obj.get("status") or "unknown")
                obj["status"] = obj.get("status") or obj.get("backfill_status")
                obj["backfill_status"] = obj.get("backfill_status") or obj.get("status")
                obj.setdefault("_source_summary_path", p.as_posix())
                rows.append(obj)
        except Exception:
            continue
    return rows


def build_weekly_index(site_root: Path, history_end_date: dt.date, history_weeks: int) -> Dict[str, Any]:
    expected = generate_week_windows(history_end_date, history_weeks)
    best: Dict[Window, Dict[str, Any]] = {w: placeholder_for_window(w) for w in expected}
    for row in load_history_rows(site_root):
        w = window_from_row(row)
        if not w or w not in best:
            continue
        if score_history(row) > score_history(best[w]):
            best[w] = row
    weeks = [best[w] for w in sorted(best.keys(), key=lambda x: (x.end, x.start), reverse=True)]
    for row in weeks:
        st = row.get("backfill_status") or row.get("status") or "unknown"
        row["backfill_status"] = st
        row["status"] = st
        if st in {"harvested", "partial_harvest"} and safe_int(row.get("source_record_count")) <= 0:
            row["backfill_status"] = row["status"] = "failed_validation"
    index = {
        "schema_version": "AQ26_WEEKLYV2_SCIENCE_V33_INDEX_1",
        "created_at_utc": now_utc(),
        "history_end_date": history_end_date.isoformat(),
        "history_weeks_requested": history_weeks,
        "canonical_policy": {
            "unique_by": ["date_window.start", "date_window.end"],
            "placeholder_rows_are_not_evidence": True,
            "status_rank": STATUS_RANK,
        },
        "weeks": weeks,
    }
    write_json(site_root / "data" / "weekly_index.json", index)
    # latest_backfill_summary: most recent completed collector run, then newest date window.
    harvested = [w for w in weeks if str(w.get("backfill_status")) in {"harvested", "partial_harvest", "failed_validation"} and safe_int(w.get("source_record_count")) > 0]
    if harvested:
        latest = max(harvested, key=lambda r: (str(r.get("created_at_utc") or ""), (r.get("date_window") or {}).get("end", "")))
        write_json(site_root / "data" / "latest_backfill_summary.json", latest)
    # Keep latest_live_summary as a separate concept. If existing latest_summary exists, preserve a copy.
    latest_summary = site_root / "data" / "latest_summary.json"
    if latest_summary.exists() and not (site_root / "data" / "latest_live_summary.json").exists():
        try:
            write_json(site_root / "data" / "latest_live_summary.json", read_json(latest_summary))
        except Exception:
            pass
    return index


def value_or_none_for_placeholder(row: Dict[str, Any], field: str) -> Optional[int]:
    if str(row.get("backfill_status") or row.get("status")) == "not_yet_harvested":
        return None
    return safe_int(row.get(field))


def readiness_value(row: Dict[str, Any], key: str) -> Optional[int]:
    if str(row.get("backfill_status") or row.get("status")) == "not_yet_harvested":
        return None
    readiness = row.get("readiness") if isinstance(row.get("readiness"), dict) else {}
    val = readiness.get(key, row.get(key))
    b = safe_bool(val)
    if b is None:
        return None
    return 1 if b else 0


def write_chart_feeds(site_root: Path, index: Dict[str, Any]) -> None:
    charts = mkdir(site_root / "data" / "charts")
    weeks = sorted(index.get("weeks", []), key=lambda r: ((r.get("date_window") or {}).get("end", ""), (r.get("date_window") or {}).get("start", "")))
    labels = [(w.get("date_window") or {}).get("end", "") for w in weeks]
    write_json(charts / "weekly_record_counts.json", {
        "schema_version": "AQ26_CHART_WEEKLY_RECORD_COUNTS_V33_1",
        "created_at_utc": now_utc(),
        "labels": labels,
        "series": {
            "source_records": [value_or_none_for_placeholder(w, "source_record_count") for w in weeks],
            "ok": [value_or_none_for_placeholder(w, "ok_count") for w in weeks],
            "warnings": [value_or_none_for_placeholder(w, "warning_count") for w in weeks],
            "errors": [value_or_none_for_placeholder(w, "error_count") for w in weeks],
            "skipped": [value_or_none_for_placeholder(w, "skipped_count") for w in weeks],
        },
        "weeks": [{"start": (w.get("date_window") or {}).get("start"), "end": (w.get("date_window") or {}).get("end"), "status": w.get("status")} for w in weeks],
    })
    write_json(charts / "source_coverage_by_week.json", {
        "schema_version": "AQ26_CHART_SOURCE_COVERAGE_V33_1",
        "created_at_utc": now_utc(),
        "labels": labels,
        "series": {
            "satellite_products": [value_or_none_for_placeholder(w, "satellite_product_count") for w in weeks],
            "drive_files": [value_or_none_for_placeholder(w, "drive_file_count") for w in weeks],
            "high_priority_filings": [value_or_none_for_placeholder(w, "high_priority_filings") for w in weeks],
            "medium_priority_filings": [value_or_none_for_placeholder(w, "medium_priority_filings") for w in weeks],
            "openaq_requests": [value_or_none_for_placeholder(w, "openaq_request_count") for w in weeks],
            "news_warnings": [value_or_none_for_placeholder(w, "news_warning_count") for w in weeks],
        },
    })
    readiness_keys = sorted(set(SCIENCE_REQUIRED_GATES + EXTERNAL_REQUIRED_GATES + [
        "metoffice_ready", "openaq_safety_ready", "drive_ready", "drive_inventory_truncated", "cdse_auth_ready", "cdse_download_ready", "gemini_summary_ready",
    ]))
    write_json(charts / "readiness_trend.json", {
        "schema_version": "AQ26_CHART_READINESS_TREND_V33_1",
        "created_at_utc": now_utc(),
        "labels": labels,
        "series": {k: [readiness_value(w, k) for w in weeks] for k in readiness_keys},
        "note": "Null means the week is not harvested or the gate was not measured; zero means measured false.",
    })
    harvested = [w for w in weeks if str(w.get("backfill_status")) in {"harvested", "partial_harvest"}]
    latest = harvested[-1] if harvested else {}
    write_json(charts / "source_class_summary_latest.json", {
        "schema_version": "AQ26_CHART_SOURCE_CLASS_LATEST_V33_1",
        "created_at_utc": now_utc(),
        "date_window": latest.get("date_window", {}),
        "source_type_counts": latest.get("source_type_counts", {}),
        "source_status_counts": latest.get("source_status_counts", {}),
    })
    write_json(charts / "satellite_products_by_week.json", {
        "schema_version": "AQ26_CHART_SATELLITE_PRODUCTS_V33_1",
        "created_at_utc": now_utc(),
        "labels": labels,
        "series": {
            "catalogue_products": [value_or_none_for_placeholder(w, "satellite_product_count") for w in weeks],
            "extracted_products": [readiness_value(w, "satellite_extraction_ready") for w in weeks],
        },
        "note": "Catalogue counts are not equivalent to pollutant raster extraction. Extraction remains separately gated.",
    })
    # These remain methodologically explicit placeholders until true source-specific outputs exist.
    for name, note in {
        "pollutant_timeseries.json": "Awaiting source-specific pollutant time-series extraction from ground AQ/DEFRA/OpenAQ and satellite products.",
        "facility_control_comparison.json": "Awaiting target/control comparable site-pollutant time-series with wind/confounder annotations.",
        "official_filings.json": "Awaiting official-document table with publication date, source date, relevance date, checksum and review status.",
    }.items():
        p = charts / name
        existing = None
        if p.exists():
            try:
                existing = read_json(p)
            except Exception:
                existing = None
        if not existing or existing.get("status") == "awaiting_source_specific_backfill":
            write_json(p, {"schema_version": f"AQ26_{name.upper()}_V33_1", "created_at_utc": now_utc(), "status": "awaiting_source_specific_backfill", "note": note, "records": []})
    write_chart_loader(site_root)


def write_chart_loader(site_root: Path) -> None:
    js = r'''
// AQ26 WeeklyV2 science chart loader V3.3
(function(){
  async function getJSON(path){ const r = await fetch(path, {cache:'no-store'}); if(!r.ok) throw new Error(path+': '+r.status); return r.json(); }
  function el(id){ return document.getElementById(id); }
  function lineChart(id, data, title){
    const node = el(id); if(!node || !window.Plotly) return;
    const labels = data.labels || [];
    const series = data.series || {};
    const traces = Object.keys(series).map(k => ({x: labels, y: series[k], mode:'lines+markers', name:k.replaceAll('_',' '), connectgaps:false}));
    Plotly.newPlot(node, traces, {title:title, margin:{t:45,l:45,r:20,b:80}, legend:{orientation:'h'}}, {responsive:true, displaylogo:false});
  }
  function barChart(id, obj, title){
    const node = el(id); if(!node || !window.Plotly) return;
    const counts = obj.source_type_counts || obj.source_status_counts || {};
    Plotly.newPlot(node, [{x:Object.keys(counts), y:Object.values(counts), type:'bar'}], {title:title, margin:{t:45,l:45,r:20,b:110}}, {responsive:true, displaylogo:false});
  }
  async function boot(){
    try { lineChart('aq26-weekly-record-chart', await getJSON('data/charts/weekly_record_counts.json'), 'Weekly source-record quality'); } catch(e){ console.warn(e); }
    try { lineChart('aq26-source-coverage-chart', await getJSON('data/charts/source_coverage_by_week.json'), 'Source coverage by week'); } catch(e){ console.warn(e); }
    try { lineChart('aq26-readiness-trend-chart', await getJSON('data/charts/readiness_trend.json'), 'Readiness gates by week'); } catch(e){ console.warn(e); }
    try { barChart('aq26-source-class-chart', await getJSON('data/charts/source_class_summary_latest.json'), 'Latest source classes'); } catch(e){ console.warn(e); }
  }
  if(document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot); else boot();
})();
'''.strip() + "\n"
    mkdir(site_root / "assets")
    (site_root / "assets" / "aq26_charts_v3.js").write_text(js, encoding="utf-8")

# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class ValidationIssue:
    severity: str
    code: str
    message: str
    path: str = ""

    def as_dict(self) -> Dict[str, str]:
        return dataclasses.asdict(self)


def validate_csv_readable(path: Path) -> Optional[str]:
    try:
        with path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.reader(f)
            for i, _ in enumerate(reader):
                if i > 10:
                    break
        return None
    except Exception as exc:
        return str(exc)


def detect_secret_like_text(path: Path, max_bytes: int = 400_000) -> Optional[str]:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")[:max_bytes]
    except Exception:
        return None
    patterns = [
        r"(?i)(api[_-]?key|token|secret|password|client_secret)[=:\s]+[A-Za-z0-9_\-\.]{12,}",
        r"(?i)Bearer\s+[A-Za-z0-9_\-\.]{20,}",
    ]
    for pat in patterns:
        if re.search(pat, text):
            return "secret-like token pattern detected"
    return None


def validate(site_root: Path, output_root: Path, history_end_date: dt.date, history_weeks: int, strict: bool, external_grade: bool) -> Dict[str, Any]:
    issues: List[ValidationIssue] = []
    index_path = site_root / "data" / "weekly_index.json"
    if not index_path.exists():
        issues.append(ValidationIssue("error", "missing_weekly_index", "site_public/data/weekly_index.json was not generated", str(index_path)))
        index = {"weeks": []}
    else:
        try:
            index = read_json(index_path)
        except Exception as exc:
            issues.append(ValidationIssue("error", "bad_weekly_index_json", f"weekly_index.json is invalid JSON: {exc}", str(index_path)))
            index = {"weeks": []}
    weeks = index.get("weeks", []) if isinstance(index, dict) else []
    if len(weeks) != history_weeks:
        issues.append(ValidationIssue("error", "wrong_week_count", f"Expected {history_weeks} weekly rows; found {len(weeks)}", str(index_path)))
    seen = set()
    for row in weeks:
        w = window_from_row(row) if isinstance(row, dict) else None
        if not w:
            issues.append(ValidationIssue("error", "bad_week_window", "A weekly row lacks a valid date_window", str(index_path)))
            continue
        if w in seen:
            issues.append(ValidationIssue("error", "duplicate_week_window", f"Duplicate weekly window {w.key}", str(index_path)))
        seen.add(w)
        st = str(row.get("backfill_status") or row.get("status") or "")
        records = safe_int(row.get("source_record_count"))
        if st in {"harvested", "partial_harvest"} and records <= 0:
            issues.append(ValidationIssue("error", "harvested_zero_records", f"{w.key} is {st} but has zero source records", str(index_path)))
        if st == "not_yet_harvested" and records > 0:
            issues.append(ValidationIssue("error", "placeholder_has_records", f"{w.key} is not_yet_harvested but has source records", str(index_path)))
        if safe_int(row.get("error_count")) > 0 and st in {"harvested", "partial_harvest"}:
            sev = "error" if external_grade else "warning"
            issues.append(ValidationIssue(sev, "harvested_week_has_errors", f"{w.key} has {row.get('error_count')} source errors", str(index_path)))
        readiness = row.get("readiness") if isinstance(row.get("readiness"), dict) else {}
        if st in {"harvested", "partial_harvest"}:
            missing_gate_values = [g for g in SCIENCE_REQUIRED_GATES if readiness.get(g) is None and row.get(g) is None]
            if missing_gate_values:
                issues.append(ValidationIssue("warning", "missing_science_gate_values", f"{w.key} lacks readiness values for {missing_gate_values}", str(index_path)))
    # JSON and CSV sanity.
    for p in list((site_root / "data").rglob("*.json")) + list((output_root / "99_integrity").rglob("*.json")):
        if p.exists():
            try:
                read_json(p)
            except Exception as exc:
                issues.append(ValidationIssue("error", "bad_json", f"Invalid JSON: {exc}", str(p)))
    for p in output_root.rglob("*.csv") if output_root.exists() else []:
        err = validate_csv_readable(p)
        if err:
            issues.append(ValidationIssue("error", "bad_csv", f"CSV is not readable: {err}", str(p)))
    # Secret redaction check for public site data/assets.
    for root in [site_root / "data", site_root / "assets"]:
        if root.exists():
            for p in root.rglob("*"):
                if p.is_file() and p.suffix.lower() in {".json", ".js", ".html", ".csv", ".txt"}:
                    hit = detect_secret_like_text(p)
                    if hit:
                        issues.append(ValidationIssue("error", "public_secret_like_text", hit, str(p)))
    # External submission fail-closed.
    for row in weeks:
        if isinstance(row, dict) and safe_bool(row.get("external_submission_ready")):
            readiness = row.get("readiness") if isinstance(row.get("readiness"), dict) else {}
            missing = [g for g in EXTERNAL_REQUIRED_GATES if readiness.get(g) is not True and row.get(g) is not True]
            if missing:
                issues.append(ValidationIssue("error", "external_ready_without_gates", f"external_submission_ready true but gates are missing/false: {missing}", str(index_path)))
    # Chart existence.
    required_charts = [
        "weekly_record_counts.json", "source_coverage_by_week.json", "readiness_trend.json",
        "satellite_products_by_week.json", "source_class_summary_latest.json",
        "pollutant_timeseries.json", "facility_control_comparison.json", "official_filings.json",
    ]
    for name in required_charts:
        p = site_root / "data" / "charts" / name
        if not p.exists():
            issues.append(ValidationIssue("error", "missing_chart_feed", f"Missing chart feed {name}", str(p)))
    # Overall status.
    error_count = sum(1 for i in issues if i.severity == "error")
    warning_count = sum(1 for i in issues if i.severity == "warning")
    result = {
        "schema_version": "AQ26_WEEKLYV2_SCIENCE_V33_VALIDATION_1",
        "created_at_utc": now_utc(),
        "ok": error_count == 0,
        "strict": bool(strict),
        "external_grade": bool(external_grade),
        "issue_count": len(issues),
        "error_count": error_count,
        "warning_count": warning_count,
        "issues": [i.as_dict() for i in issues],
        "summary": {
            "history_weeks_requested": history_weeks,
            "weekly_rows": len(weeks),
            "harvested_rows": sum(1 for w in weeks if isinstance(w, dict) and str(w.get("backfill_status") or w.get("status")) == "harvested"),
            "partial_harvest_rows": sum(1 for w in weeks if isinstance(w, dict) and str(w.get("backfill_status") or w.get("status")) == "partial_harvest"),
            "not_yet_harvested_rows": sum(1 for w in weeks if isinstance(w, dict) and str(w.get("backfill_status") or w.get("status")) == "not_yet_harvested"),
        },
    }
    mkdir(output_root / "99_integrity")
    write_json(output_root / "99_integrity" / "AQ26_WEEKLYV2_SCIENCE_V33_VALIDATION.json", result)
    write_json(site_root / "data" / "science_validation_latest.json", result)
    return result

# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def build_site_data(args: argparse.Namespace) -> Dict[str, Any]:
    repo_root = Path(args.repo_root).resolve()
    output_root = (repo_root / args.output_root).resolve() if not Path(args.output_root).is_absolute() else Path(args.output_root).resolve()
    site_root = (repo_root / args.site_root).resolve() if not Path(args.site_root).is_absolute() else Path(args.site_root).resolve()
    mkdir(site_root / "data" / "history")
    history_end_date = parse_date(args.history_end_date)
    if not history_end_date:
        raise SystemExit(f"Invalid --history-end-date: {args.history_end_date}")
    index = build_weekly_index(site_root, history_end_date, int(args.history_weeks))
    write_chart_feeds(site_root, index)
    result = validate(site_root, output_root, history_end_date, int(args.history_weeks), bool(args.strict), bool(args.external_grade_validation))
    if args.strict and not result.get("ok"):
        print(json.dumps(result, indent=2), file=sys.stderr)
        raise SystemExit(2)
    return result


def run_batch(args: argparse.Namespace) -> Dict[str, Any]:
    apply_secret_aliases()
    repo_root = Path(args.repo_root).resolve()
    output_root = (repo_root / args.output_root).resolve() if not Path(args.output_root).is_absolute() else Path(args.output_root).resolve()
    site_root = (repo_root / args.site_root).resolve() if not Path(args.site_root).is_absolute() else Path(args.site_root).resolve()
    mkdir(site_root / "data" / "history")
    history_end_date = parse_date(args.history_end_date)
    backfill_end_date = parse_date(args.backfill_end_date) or history_end_date
    if not history_end_date or not backfill_end_date:
        raise SystemExit("Invalid history/backfill end date")
    all_windows = generate_week_windows(history_end_date, int(args.history_weeks))
    selected = choose_windows(
        all_windows=all_windows,
        site_root=site_root,
        backfill_start_date=str(args.backfill_start_date),
        backfill_end_date=backfill_end_date,
        limit=int(args.backfill_limit_windows),
        auto_mode=str(args.auto_mode),
        force=bool(args.force),
    )
    plan = {
        "schema_version": "AQ26_WEEKLYV2_SCIENCE_V33_BATCH_PLAN_1",
        "created_at_utc": now_utc(),
        "backfill_start_date": args.backfill_start_date,
        "backfill_end_date": backfill_end_date.isoformat(),
        "auto_mode": args.auto_mode,
        "force": bool(args.force),
        "selected_windows": [w.as_dict() for w in selected],
        "selected_count": len(selected),
    }
    write_json(output_root / "10_historical_backfill" / "latest_batch_plan.json", plan)
    print(json.dumps(plan, indent=2))
    histories: List[Dict[str, Any]] = []
    for w in selected:
        print(f"[AQ26 V3.3] harvesting {w.start} -> {w.end}", flush=True)
        hist = run_one_window(args, w)
        histories.append(hist)
        print(json.dumps({"window": w.as_dict(), "status": hist.get("backfill_status"), "records": hist.get("source_record_count"), "errors": hist.get("error_count"), "warnings": hist.get("warning_count")}, indent=2), flush=True)
    write_json(output_root / "10_historical_backfill" / "latest_batch_results.json", {"created_at_utc": now_utc(), "histories": histories})
    return build_site_data(args)


def diagnose_secrets(args: argparse.Namespace) -> Dict[str, Any]:
    diag = apply_secret_aliases()
    safe = {
        "schema_version": "AQ26_WEEKLYV2_SCIENCE_V33_SECRET_DIAGNOSTICS_1",
        "created_at_utc": now_utc(),
        "families_present": diag,
        "booleans_only": True,
        "notes": "No secret values are emitted. This only confirms whether secret families are present after alias mapping.",
    }
    repo_root = Path(args.repo_root).resolve()
    output_root = (repo_root / args.output_root).resolve() if not Path(args.output_root).is_absolute() else Path(args.output_root).resolve()
    write_json(output_root / "99_integrity" / "AQ26_WEEKLYV2_SECRET_DIAGNOSTICS.json", safe)
    print(json.dumps(safe, indent=2))
    return safe


def add_common_args(ap: argparse.ArgumentParser) -> None:
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--collector-script", default="scripts/aq26_weeklyv2_collect.py")
    ap.add_argument("--config", default="configs/aq26_weekly_v2_sources.yml")
    ap.add_argument("--output-root", default="outputs")
    ap.add_argument("--site-root", default="site_public")
    ap.add_argument("--history-end-date", default=os.getenv("AQ26_HISTORY_END_DATE") or dt.date.today().isoformat())
    ap.add_argument("--history-weeks", type=int, default=int(os.getenv("AQ26_HISTORY_WEEKS", "104")))
    ap.add_argument("--strict", action="store_true", default=os.getenv("AQ26_STRICT_VALIDATION", "false").lower() == "true")
    ap.add_argument("--external-grade-validation", action="store_true", default=os.getenv("AQ26_EXTERNAL_GRADE_VALIDATION", "false").lower() == "true")


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="AQ26 WeeklyV2 science-grade backfill and site data builder V3.3")
    sub = ap.add_subparsers(dest="command", required=True)
    p = sub.add_parser("run-batch", help="Run a controlled date-bound historical backfill batch and rebuild site data")
    add_common_args(p)
    p.add_argument("--backfill-start-date", default=os.getenv("AQ26_BACKFILL_START_DATE", "auto"), help="YYYY-MM-DD or auto")
    p.add_argument("--backfill-end-date", default=os.getenv("AQ26_BACKFILL_END_DATE") or os.getenv("AQ26_HISTORY_END_DATE") or dt.date.today().isoformat())
    p.add_argument("--backfill-limit-windows", type=int, default=int(os.getenv("AQ26_BACKFILL_LIMIT_WINDOWS", "4")))
    p.add_argument("--auto-mode", default=os.getenv("AQ26_BACKFILL_AUTO_MODE", "earliest_missing"), choices=["earliest_missing", "latest_missing", "chronological", "reverse_chronological"])
    p.add_argument("--force", action="store_true", default=os.getenv("AQ26_BACKFILL_FORCE", "false").lower() == "true")
    p.set_defaults(func=run_batch)

    p = sub.add_parser("build-site-data", help="Rebuild weekly index, charts and validation from existing history files")
    add_common_args(p)
    p.set_defaults(func=build_site_data)

    p = sub.add_parser("validate", help="Validate existing site data without running collectors")
    add_common_args(p)
    def _val(args: argparse.Namespace) -> Dict[str, Any]:
        repo_root = Path(args.repo_root).resolve()
        output_root = (repo_root / args.output_root).resolve() if not Path(args.output_root).is_absolute() else Path(args.output_root).resolve()
        site_root = (repo_root / args.site_root).resolve() if not Path(args.site_root).is_absolute() else Path(args.site_root).resolve()
        hed = parse_date(args.history_end_date)
        if not hed:
            raise SystemExit("bad history end date")
        res = validate(site_root, output_root, hed, int(args.history_weeks), bool(args.strict), bool(args.external_grade_validation))
        print(json.dumps(res, indent=2))
        if args.strict and not res.get("ok"):
            raise SystemExit(2)
        return res
    p.set_defaults(func=_val)

    p = sub.add_parser("diagnose-secrets", help="Write boolean-only secret alias diagnostics")
    add_common_args(p)
    p.set_defaults(func=diagnose_secrets)
    return ap


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        args.func(args)
        return 0
    except subprocess.TimeoutExpired as exc:
        print(f"[AQ26 V3.3] ERROR: timed out: {exc}", file=sys.stderr)
        return 124
    except SystemExit as exc:
        raise exc
    except Exception as exc:
        print(f"[AQ26 V3.3] ERROR: {exc}", file=sys.stderr)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
