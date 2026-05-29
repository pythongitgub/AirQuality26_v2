#!/usr/bin/env python3
"""
AQ26 Newhaven deep-dive, emissions-evidence and anomaly backfill.

Purpose
-------
Builds a public-safe Newhaven / validated-overlay evidence enhancement layer and
a protected unredacted evidence inventory. It is deliberately cautious:

- Public outputs are redacted summaries and review signals.
- It does not make regulatory, legal, health, breach, or causal findings.
- "Anomalies" are statistical review prompts only.
- Emissions charts are only value charts when source tables contain enough
  structured numeric/date/pollutant evidence; otherwise the page shows an
  evidence-readiness status, not invented values.

Data sources
------------
1. Existing repository AQ26 outputs.
2. Optional Google Drive listing/downloading when GDRIVE_SERVICE_ACCOUNT and
   GDRIVE_FOLDER_ID are available and the Drive folder has been shared with the
   service account.
3. Existing site_public/site_unredacted overlay and focused-backfill outputs.

This script is designed to run in GitHub Actions and/or locally.
"""

from __future__ import annotations

import argparse
import base64
import csv
import io
import json
import math
import os
import re
import statistics
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

PUBLIC_NOTICE = (
    "AQ26 is an evidence and provenance observatory. Public outputs are redacted "
    "and do not make regulatory determinations, legal conclusions, health advice, "
    "breach findings or causal attribution. Statistical signals are review prompts only."
)

KEYWORDS = [
    "newhaven", "bv8067il", "veolia es south downs", "south downs",
    "emission", "emissions", "elv", "limit", "throughput", "exceedance",
    "measurement", "incinerator", "35o", "35p", "35pb", "35pc", "36j", "36i", "36hb"
]

CHART_COLORS_SAFE = {
    # Used only in JSON labels; CSS/Chart.js can choose colours.
    "measurement": "measurement",
    "limit_elv": "limit_elv",
    "throughput": "throughput",
    "exceedance": "exceedance",
}

def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def esc(x: Any) -> str:
    import html
    return html.escape("" if x is None else str(x), quote=True)

def norm(x: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(x or "").lower())

def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

def read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default

def read_csv(path: Path, max_rows: int = 500000) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    for enc in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            with path.open("r", encoding=enc, newline="", errors="replace") as f:
                out = []
                for i, row in enumerate(csv.DictReader(f)):
                    if i >= max_rows:
                        break
                    out.append(dict(row))
                return out
        except Exception:
            continue
    return []

def write_csv(path: Path, rows: List[Dict[str, Any]], fieldnames: Optional[List[str]] = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        keys: List[str] = []
        for r in rows:
            for k in r.keys():
                if k not in keys:
                    keys.append(k)
        fieldnames = keys or ["empty"]
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fieldnames})

def safe_float(x: Any) -> Optional[float]:
    if x is None:
        return None
    s = str(x).strip().replace(",", "")
    if not s or s.lower() in {"nan", "none", "null", "<na>", "true", "false"}:
        return None
    # Remove common unit decorations but keep sign/decimal.
    m = re.search(r"[-+]?\d+(?:\.\d+)?", s)
    if not m:
        return None
    try:
        return float(m.group(0))
    except Exception:
        return None

def parse_dateish(x: Any) -> str:
    s = str(x or "").strip()
    if not s:
        return ""
    # ISO-ish
    m = re.search(r"(20\d{2})[-/](\d{1,2})[-/](\d{1,2})", s)
    if m:
        y, mo, d = m.groups()
        return f"{int(y):04d}-{int(mo):02d}-{int(d):02d}"
    # UK dd/mm/yyyy
    m = re.search(r"(\d{1,2})/(\d{1,2})/(20\d{2})", s)
    if m:
        d, mo, y = m.groups()
        return f"{int(y):04d}-{int(mo):02d}-{int(d):02d}"
    # Year only or year-month
    m = re.search(r"(20\d{2})[-/](\d{1,2})", s)
    if m:
        y, mo = m.groups()
        return f"{int(y):04d}-{int(mo):02d}-01"
    m = re.search(r"(20\d{2})", s)
    if m:
        return f"{m.group(1)}-01-01"
    return ""

def classify_file(path: Path, text_hint: str = "") -> str:
    s = f"{path.as_posix()} {text_hint}".lower()
    if any(k in s for k in ["throughput", "waste_throughput"]):
        return "throughput"
    if any(k in s for k in ["exceedance", "count_or_exceedance"]):
        return "exceedance"
    if any(k in s for k in ["limit", "elv"]):
        return "limit_elv"
    if any(k in s for k in ["measurement", "emission", "emissions", "monitoring"]):
        return "measurement"
    if any(k in s for k in ["diagnostic", "openaq"]):
        return "diagnostic"
    return "evidence"

def scan_local_evidence(repo: Path, max_files: int = 2500) -> List[Dict[str, Any]]:
    roots = [
        repo / "site_public" / "data",
        repo / "site_unredacted" / "data",
        repo / "outputs",
        repo / "configs",
        repo / "data",
    ]
    rows: List[Dict[str, Any]] = []
    seen = set()
    for root in roots:
        if not root.exists():
            continue
        for p in root.rglob("*"):
            if len(rows) >= max_files:
                break
            if not p.is_file():
                continue
            if p.suffix.lower() not in {".csv", ".json", ".md", ".txt", ".html", ".parquet"}:
                continue
            rel = p.relative_to(repo).as_posix()
            if rel in seen:
                continue
            seen.add(rel)
            hay = rel.lower()
            try:
                size = p.stat().st_size
            except Exception:
                size = 0
            # include all public/unredacted data plus strongly relevant keyword files
            if not any(k in hay for k in KEYWORDS) and not rel.startswith("site_public/data") and not rel.startswith("site_unredacted/data"):
                continue
            rows.append({
                "source": "repo",
                "path": rel,
                "name": p.name,
                "suffix": p.suffix.lower(),
                "size_bytes": size,
                "evidence_type": classify_file(p),
                "public_safe": "yes" if rel.startswith("site_public/") else "review_required",
            })
    return rows

def load_overlay_status(repo: Path) -> List[Dict[str, str]]:
    paths = [
        repo / "site_public/data/focus/overlays_v3/facility_overlay_status.csv",
        repo / "site_public/data/focus/operational/public_facility_overlay_status.csv",
        repo / "site_public/data/focus/overlays_v2/facility_overlay_status.csv",
    ]
    for p in paths:
        rows = read_csv(p)
        if rows:
            return rows
    return []

def load_summary(repo: Path) -> Dict[str, Any]:
    for p in [
        repo / "site_public/data/focus/operational/public_overlay_summary.json",
        repo / "site_public/data/weekly/latest_alert.json",
        repo / "site_public/data/focus/overlays_v3/incinerator_overlay_summary.json",
    ]:
        d = read_json(p, {})
        if isinstance(d, dict) and d:
            return d
    return {}

def find_col(cols: List[str], *needles: str) -> str:
    lower = {c.lower().strip(): c for c in cols}
    for n in needles:
        if n in lower:
            return lower[n]
    for c in cols:
        lc = c.lower()
        if any(n in lc for n in needles):
            return c
    return ""

def row_text(row: Dict[str, str]) -> str:
    return " | ".join(str(v) for v in row.values())

def table_records_from_csv(repo: Path, inv: List[Dict[str, Any]], max_rows_per_file: int = 50000) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    records: List[Dict[str, Any]] = []
    file_summaries: List[Dict[str, Any]] = []
    for rec in inv:
        if rec.get("source") != "repo":
            continue
        p = repo / rec["path"]
        if p.suffix.lower() != ".csv":
            continue
        rows = read_csv(p, max_rows=max_rows_per_file)
        if not rows:
            continue
        cols = list(rows[0].keys())
        date_col = find_col(cols, "date", "datetime", "period", "year", "month")
        pollutant_col = find_col(cols, "pollutant", "parameter", "substance", "emission_type", "species")
        value_col = find_col(cols, "value", "measurement", "concentration", "emission", "mass", "result", "amount", "tonnes", "mg")
        unit_col = find_col(cols, "unit", "units")
        facility_col = find_col(cols, "facility", "site", "installation", "permit", "asset")
        numeric_cols = []
        for c in cols:
            vals = [safe_float(r.get(c)) for r in rows[:200]]
            n = sum(v is not None for v in vals)
            if n >= max(3, min(20, len(rows[:200]) // 10)):
                numeric_cols.append(c)
        chosen_value_cols = [value_col] if value_col else numeric_cols[:4]
        newhaven_rows = 0
        extracted = 0
        for r in rows:
            txt = row_text(r)
            is_newhaven = bool(re.search(r"newhaven|bv8067il|south downs|veolia", txt, flags=re.I))
            if is_newhaven:
                newhaven_rows += 1
            # Public chart extraction prioritises Newhaven rows; if none, keeps aggregate rows if file is clearly Newhaven.
            if not is_newhaven and not re.search(r"newhaven|bv8067il", rec["path"], flags=re.I):
                continue
            for vc in chosen_value_cols:
                if not vc:
                    continue
                val = safe_float(r.get(vc))
                if val is None:
                    continue
                date_val = parse_dateish(r.get(date_col, "")) if date_col else ""
                if not date_val:
                    # keep but label unknown period
                    date_val = "unknown"
                pollutant = r.get(pollutant_col, "") if pollutant_col else vc
                records.append({
                    "source_file": rec["path"],
                    "evidence_type": rec["evidence_type"],
                    "facility": r.get(facility_col, "Newhaven / matched evidence") if facility_col else "Newhaven / matched evidence",
                    "date": date_val,
                    "pollutant_or_metric": pollutant or vc,
                    "value": val,
                    "unit": r.get(unit_col, "") if unit_col else "",
                    "public_status": "review_summary_only",
                })
                extracted += 1
        file_summaries.append({
            **rec,
            "rows_read": len(rows),
            "newhaven_matched_rows": newhaven_rows,
            "numeric_columns_detected": ";".join(numeric_cols[:20]),
            "chart_records_extracted": extracted,
        })
    return records, file_summaries

def robust_anomalies(records: List[Dict[str, Any]], z_cutoff: float = 3.5) -> List[Dict[str, Any]]:
    # Group by metric/pollutant, compute robust z using median absolute deviation.
    groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in records:
        if r.get("date") == "unknown":
            continue
        groups[str(r.get("pollutant_or_metric") or "metric")].append(r)
    out: List[Dict[str, Any]] = []
    for metric, rows in groups.items():
        vals = [float(r["value"]) for r in rows if isinstance(r.get("value"), (int, float))]
        if len(vals) < 5:
            continue
        med = statistics.median(vals)
        absdev = [abs(v - med) for v in vals]
        mad = statistics.median(absdev) or 0.0
        if mad == 0:
            # fallback to stdev if possible
            try:
                sd = statistics.stdev(vals)
            except Exception:
                sd = 0
            if sd == 0:
                continue
            for r in rows:
                z = (float(r["value"]) - med) / sd
                if abs(z) >= z_cutoff:
                    out.append({**r, "anomaly_method": "z_score", "score": round(z, 2), "review_note": "Statistical outlier review prompt only"})
        else:
            for r in rows:
                rz = 0.6745 * (float(r["value"]) - med) / mad
                if abs(rz) >= z_cutoff:
                    out.append({**r, "anomaly_method": "robust_mad_z", "score": round(rz, 2), "review_note": "Statistical outlier review prompt only"})
    out.sort(key=lambda r: (str(r.get("pollutant_or_metric")), -abs(float(r.get("score", 0)))))
    return out[:100]

def chart_data(records: List[Dict[str, Any]], max_points: int = 1200) -> Dict[str, Any]:
    # Aggregate by month-ish date, metric and evidence type.
    buckets: Dict[Tuple[str, str, str], List[float]] = defaultdict(list)
    for r in records:
        date = str(r.get("date") or "unknown")
        if date != "unknown":
            date = date[:7]
        metric = str(r.get("pollutant_or_metric") or "metric")[:80]
        etype = str(r.get("evidence_type") or "measurement")
        val = r.get("value")
        if isinstance(val, (int, float)):
            buckets[(date, metric, etype)].append(float(val))
    rows = []
    for (date, metric, etype), vals in buckets.items():
        rows.append({
            "date": date,
            "metric": metric,
            "evidence_type": etype,
            "value_mean": round(sum(vals) / len(vals), 6),
            "n": len(vals),
        })
    rows.sort(key=lambda r: (r["date"], r["metric"], r["evidence_type"]))
    if len(rows) > max_points:
        rows = rows[-max_points:]
    by_type = Counter(r["evidence_type"] for r in records)
    by_metric = Counter(str(r.get("pollutant_or_metric") or "metric")[:80] for r in records)
    return {
        "generated_utc": utc_now(),
        "public_notice": PUBLIC_NOTICE,
        "has_structured_emissions_values": bool(rows),
        "timeseries": rows,
        "records_by_evidence_type": dict(by_type),
        "top_metrics": dict(by_metric.most_common(25)),
    }

def optional_drive_inventory(args, out_unredacted: Path) -> List[Dict[str, Any]]:
    if not args.drive_fetch:
        return []
    folder_id = args.gdrive_folder_id or os.environ.get("GDRIVE_FOLDER_ID", "")
    service_raw = os.environ.get("GDRIVE_SERVICE_ACCOUNT", "")
    if not folder_id or not service_raw:
        return [{"source": "google_drive", "status": "not_configured", "note": "GDRIVE_FOLDER_ID or GDRIVE_SERVICE_ACCOUNT missing"}]
    try:
        import google.oauth2.service_account
        from googleapiclient.discovery import build
    except Exception as e:
        return [{"source": "google_drive", "status": "dependency_missing", "error": str(e)}]

    try:
        # Secret may be raw JSON or base64 JSON.
        raw = service_raw.strip()
        if raw.startswith("{"):
            info = json.loads(raw)
        else:
            info = json.loads(base64.b64decode(raw).decode("utf-8"))
        scopes = ["https://www.googleapis.com/auth/drive.readonly"]
        creds = google.oauth2.service_account.Credentials.from_service_account_info(info, scopes=scopes)
        service = build("drive", "v3", credentials=creds, cache_discovery=False)
        rows: List[Dict[str, Any]] = []
        page_token = None
        # Search within the folder. If your AirQuality Drive tree is not shared with the service account,
        # this will return empty.
        q = f"'{folder_id}' in parents and trashed = false"
        while True:
            resp = service.files().list(
                q=q,
                fields="nextPageToken, files(id,name,mimeType,size,modifiedTime,webViewLink)",
                pageSize=1000,
                pageToken=page_token,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
            ).execute()
            for f in resp.get("files", []):
                name = f.get("name", "")
                hay = name.lower()
                if any(k in hay for k in KEYWORDS):
                    rows.append({
                        "source": "google_drive",
                        "id": f.get("id", ""),
                        "name": name,
                        "mimeType": f.get("mimeType", ""),
                        "size_bytes": f.get("size", ""),
                        "modifiedTime": f.get("modifiedTime", ""),
                        "webViewLink": f.get("webViewLink", ""),
                        "evidence_type": classify_file(Path(name), name),
                        "public_safe": "no_unredacted_inventory_only",
                    })
            page_token = resp.get("nextPageToken")
            if not page_token or len(rows) >= args.drive_limit:
                break
        return rows[: args.drive_limit]
    except Exception as e:
        return [{"source": "google_drive", "status": "error", "error": type(e).__name__ + ": " + str(e)}]

def cards(summary: Dict[str, Any]) -> str:
    items = [
        ("Facilities", summary.get("total_facilities", 46), "England/Wales register"),
        ("Validated", summary.get("validated_overlays", 8), "Retained validated overlays"),
        ("Under review", summary.get("candidate_overlays", 35), "Candidate overlays"),
        ("Fallback", summary.get("unresolved_facilities", 3), "Manual discovery cases"),
        ("Structured records", summary.get("structured_records", 0), "Measurement/emission rows extracted"),
        ("Review prompts", summary.get("anomaly_count", 0), "Statistical anomalies, not findings"),
    ]
    return "<section class='aq26-dd-grid'>" + "".join(
        f"<article class='aq26-dd-card'><div class='k'>{esc(k)}</div><div class='v'>{esc(v)}</div><p>{esc(n)}</p></article>"
        for k, v, n in items
    ) + "</section>"

def page_css() -> str:
    return """
.aq26-dd-hero{border-radius:28px;padding:2rem;margin:1rem 0;background:linear-gradient(120deg,#071a30,#0b4d83,#008578);color:#fff;box-shadow:0 18px 45px rgba(7,26,48,.16)}
.aq26-dd-hero h1{font-size:clamp(2rem,5vw,4rem);margin:.25rem 0}.aq26-dd-hero p{max-width:900px;line-height:1.6}
.aq26-dd-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:1rem;margin:1rem 0}
.aq26-dd-card{background:#fff;border:1px solid #dce7f2;border-radius:20px;padding:1rem;box-shadow:0 14px 35px rgba(7,26,48,.08)}
.aq26-dd-card .k{font-size:.75rem;text-transform:uppercase;letter-spacing:.12em;font-weight:900;color:#5d7088}.aq26-dd-card .v{font-size:2rem;font-weight:950;color:#071a30}.aq26-dd-card p{color:#526277}
.aq26-dd-section{background:#fff;border:1px solid #dce7f2;border-radius:24px;padding:1.2rem;margin:1rem 0;box-shadow:0 14px 35px rgba(7,26,48,.08)}
.aq26-dd-warning{border-left:6px solid #f2b84b;background:#fff8e4;padding:1rem;border-radius:14px}
.aq26-dd-table{width:100%;border-collapse:collapse}.aq26-dd-table th,.aq26-dd-table td{padding:.75rem;border-bottom:1px solid #e8eef5;text-align:left;vertical-align:top}.aq26-dd-table th{font-size:.75rem;letter-spacing:.08em;text-transform:uppercase;color:#5d7088}
@media(max-width:850px){.aq26-dd-grid{grid-template-columns:1fr}.aq26-dd-hero{padding:1.25rem}}
"""

def standalone_page(title: str, body: str) -> str:
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(title)} · AQ26</title>
<link rel="icon" href="/favicon.ico?v=aq26-deep" sizes="any"><link rel="icon" href="/favicon.svg?v=aq26-deep" type="image/svg+xml">
<link rel="stylesheet" href="assets/aq26_operational.css?v=operational"><style>{page_css()}</style></head>
<body><header class="header"><div class="wrap"><a class="brand" href="index.html"><img src="assets/air_quality_web.svg" alt="SCC Nexus Air Quality Report"></a><nav class="nav open"><a href="index.html">Home</a><a href="incinerators.html">Incinerators</a><a href="newhaven.html">Newhaven</a><a href="newhaven-deep-dive.html">Deep dive</a><a href="overlays.html">Overlays</a><a href="methodology.html">Methodology</a></nav></div></header><main class="main">{body}</main><footer class="footer"><div class="wrap"><p>{esc(PUBLIC_NOTICE)}</p></div></footer></body></html>"""

def build_deep_dive_page(summary: Dict[str, Any], chart: Dict[str, Any], anomalies: List[Dict[str, Any]], evidence_files: List[Dict[str, Any]]) -> str:
    if chart.get("has_structured_emissions_values"):
        chart_msg = "Structured emissions/measurement values were extracted into review charts. These are evidence prompts only and require provenance review before any public interpretation."
    else:
        chart_msg = "No public-safe structured emissions value chart has been generated yet. The site is showing evidence-readiness and source-inventory charts until the Newhaven row-level tables are wired into the site."
    top_evidence = evidence_files[:12]
    ev_rows = "".join(
        f"<tr><td>{esc(r.get('evidence_type'))}</td><td>{esc(r.get('name') or r.get('path'))}</td><td>{esc(r.get('rows_read',''))}</td><td>{esc(r.get('chart_records_extracted',''))}</td></tr>"
        for r in top_evidence
    )
    an_rows = "".join(
        f"<tr><td>{esc(r.get('date'))}</td><td>{esc(r.get('pollutant_or_metric'))}</td><td>{esc(r.get('value'))}</td><td>{esc(r.get('score'))}</td><td>{esc(r.get('review_note'))}</td></tr>"
        for r in anomalies[:25]
    ) or "<tr><td colspan='5'>No statistical anomaly prompts generated from currently structured records.</td></tr>"
    body = f"""
<section class="aq26-dd-hero">
  <div class="eyebrow">Newhaven deep-dive evidence layer</div>
  <h1>Newhaven ERF / BV8067IL evidence backfill</h1>
  <p>Public-safe enrichment for the validated reference case: official reporting inventory, monitoring-overlay context, row-level evidence readiness, and AI/ML-assisted review prompts.</p>
</section>
{cards(summary)}
<section class="aq26-dd-section"><h2>Are there emissions charts yet?</h2><p>{esc(chart_msg)}</p><div class="aq26-dd-warning"><b>Safety note:</b> emissions values are not presented as breach findings or health conclusions. Any charted values remain subject to source, unit, ELV, reporting-period and provenance review.</div></section>
<section class="aq26-dd-section"><h2>Weekly anomaly review status</h2><p>The weekly run now prepares anomaly-review prompts when enough structured numeric records are present. These are statistical QA signals, not findings.</p><table class="aq26-dd-table"><thead><tr><th>Date</th><th>Metric</th><th>Value</th><th>Score</th><th>Review note</th></tr></thead><tbody>{an_rows}</tbody></table></section>
<section class="aq26-dd-section"><h2>Evidence sources wired into this build</h2><table class="aq26-dd-table"><thead><tr><th>Type</th><th>File</th><th>Rows read</th><th>Chart records</th></tr></thead><tbody>{ev_rows}</tbody></table></section>
<script type="application/json" id="aq26-newhaven-chart-data">{esc(json.dumps(chart))}</script>
"""
    return standalone_page("Newhaven evidence deep dive", body)

def inject_link_into_newhaven(public: Path) -> None:
    p = public / "newhaven.html"
    if not p.exists():
        return
    txt = p.read_text(encoding="utf-8", errors="replace")
    if "newhaven-deep-dive.html" in txt:
        return
    link = "<a class='btn' href='newhaven-deep-dive.html'>Open evidence deep dive</a>"
    # Try to add near first button group/main.
    if "Compare overlay status" in txt:
        txt = txt.replace("Compare overlay status", "Open evidence deep dive</a><a class='btn alt' href='overlays.html'>Compare overlay status", 1)
        # If replacement introduced too much due unknown markup, fall back sanitize below not needed.
    elif "</main>" in txt:
        txt = txt.replace("</main>", f"<section class='card section'><h2>Newhaven evidence deep dive</h2><p>Expanded public-safe source, emissions-readiness and anomaly-review evidence layer.</p>{link}</section></main>")
    p.write_text(txt, encoding="utf-8")

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--public-site", default="site_public")
    ap.add_argument("--unredacted-site", default="site_unredacted")
    ap.add_argument("--drive-fetch", action="store_true")
    ap.add_argument("--gdrive-folder-id", default="")
    ap.add_argument("--drive-limit", type=int, default=500)
    ap.add_argument("--max-files", type=int, default=2500)
    ap.add_argument("--max-rows-per-file", type=int, default=50000)
    ap.add_argument("--deploy-mode", default="build")
    args = ap.parse_args()

    repo = Path(args.repo_root).resolve()
    public = repo / args.public_site
    unred = repo / args.unredacted_site
    pub_out = public / "data/newhaven"
    un_out = unred / "data/newhaven"
    pub_out.mkdir(parents=True, exist_ok=True)
    un_out.mkdir(parents=True, exist_ok=True)

    overlay_rows = load_overlay_status(repo)
    summary_base = load_summary(repo)
    local_inv = scan_local_evidence(repo, max_files=args.max_files)
    drive_inv = optional_drive_inventory(args, un_out)
    chart_records, file_summaries = table_records_from_csv(repo, local_inv, max_rows_per_file=args.max_rows_per_file)

    anomalies = robust_anomalies(chart_records)
    chart = chart_data(chart_records)
    status_counts = Counter(r.get("overlay_status") for r in overlay_rows)
    summary = {
        "generated_utc": utc_now(),
        "total_facilities": int(summary_base.get("total_facilities") or len(overlay_rows) or 46),
        "validated_overlays": int(summary_base.get("validated_overlays") or status_counts.get("validated_existing_overlay", 8)),
        "candidate_overlays": int(summary_base.get("candidate_overlays") or status_counts.get("candidate_overlay_needs_review", 35)),
        "unresolved_facilities": int(summary_base.get("unresolved_facilities") or status_counts.get("no_candidate_selected_yet", 3)),
        "structured_records": len(chart_records),
        "anomaly_count": len(anomalies),
        "local_evidence_files": len(local_inv),
        "drive_inventory_rows": len(drive_inv),
        "has_emissions_value_charts": chart.get("has_structured_emissions_values", False),
        "public_notice": PUBLIC_NOTICE,
    }

    # Redacted public outputs.
    write_json(pub_out / "newhaven_deep_dive_summary.json", summary)
    write_json(pub_out / "emissions_evidence_chart.json", chart)
    write_json(pub_out / "weekly_anomaly_review_public.json", {"generated_utc": utc_now(), "anomaly_count": len(anomalies), "notice": PUBLIC_NOTICE, "top_prompts": anomalies[:10]})
    public_file_summary = [
        {k: r.get(k, "") for k in ["source", "path", "name", "evidence_type", "rows_read", "newhaven_matched_rows", "chart_records_extracted", "public_safe"]}
        for r in file_summaries[:250]
    ]
    write_csv(pub_out / "public_evidence_inventory_summary.csv", public_file_summary)

    # Unredacted outputs.
    write_csv(un_out / "local_evidence_inventory.csv", local_inv)
    write_csv(un_out / "drive_evidence_inventory.csv", drive_inv)
    write_csv(un_out / "file_extraction_summary.csv", file_summaries)
    write_csv(un_out / "structured_emissions_measurement_records.csv", chart_records[:200000])
    write_csv(un_out / "anomaly_review_candidates.csv", anomalies)
    write_json(un_out / "newhaven_deep_dive_summary_unredacted.json", {**summary, "drive_fetch": bool(args.drive_fetch), "drive_configured": bool(os.environ.get("GDRIVE_SERVICE_ACCOUNT"))})

    public.joinpath("newhaven-deep-dive.html").write_text(
        build_deep_dive_page(summary, chart, anomalies, file_summaries or local_inv),
        encoding="utf-8",
    )
    inject_link_into_newhaven(public)

    status = {
        "ok": True,
        "generated_utc": summary["generated_utc"],
        "summary": summary,
        "outputs": [
            str(pub_out / "newhaven_deep_dive_summary.json"),
            str(pub_out / "emissions_evidence_chart.json"),
            str(pub_out / "weekly_anomaly_review_public.json"),
            str(public / "newhaven-deep-dive.html"),
            str(un_out / "anomaly_review_candidates.csv"),
        ],
    }
    write_json(pub_out / "build_status.json", status)
    print(json.dumps(status, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
