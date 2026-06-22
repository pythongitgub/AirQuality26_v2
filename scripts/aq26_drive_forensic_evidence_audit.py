#!/usr/bin/env python3
"""AQ26 Google Drive forensic evidence audit.

Read-only inventory for the AQ26 evidence lake. It creates a public-safe
summary for the website and a protected review file for /unredacted/.
It does not make causal, health, legal or regulatory findings.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import re
from collections import Counter, deque
from pathlib import Path
from typing import Any

from google.oauth2 import service_account
from googleapiclient.discovery import build

FOLDER_MIME = "application/vnd.google-apps.folder"
SHORTCUT_MIME = "application/vnd.google-apps.shortcut"

REGULATORY = ["bv8067il", "newhaven", "veolia", "erf", "efw", "energy recovery", "incinerator", "annual", "performance", "permit", "epr", "environment agency", "emissions", "monitoring"]
SATELLITE = ["sentinel", "s5p", "tropomi", "satellite", "cdse", "earthdata", "modis", "landsat", "no2", "so2", "hcho", "aod"]
GROUND = ["openaq", "laqn", "ukair", "aurn", "waqi", "purpleair", "monitor", "station", "observed"]
MET = ["metoffice", "met office", "weather", "wind", "meteorology", "cams", "ecmwf", "era5"]
QA = ["qa", "qaqc", "quality", "readiness", "gate", "validation", "maturity", "reviewer", "claim", "controlled"]
SECRET = ["secret", "password", "credential", "token", "apikey", "api_key", ".env", ".htpasswd", "private_key"]
RISK_EXT = {".zip", ".7z", ".tar", ".gz", ".tgz", ".bak", ".sql", ".sqlite", ".db", ".key", ".pem", ".p12"}
RAW_EXT = {".csv", ".json", ".xml", ".xlsx", ".xlsm", ".xls", ".parquet", ".nc", ".h5", ".hdf", ".tif", ".tiff", ".geojson"}


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def sha_text(value: str) -> str:
    return hashlib.sha256((value or "").encode("utf-8", errors="ignore")).hexdigest()


def ext(name: str) -> str:
    return Path(name or "").suffix.lower()


def blob(*parts: Any) -> str:
    return " ".join(str(p or "") for p in parts).lower()


def years(text: str) -> list[int]:
    found = []
    for y in re.findall(r"(?<!\d)(19\d{2}|20\d{2})(?!\d)", text or ""):
        yi = int(y)
        if 1990 <= yi <= dt.datetime.now().year + 1:
            found.append(yi)
    return sorted(set(found))


def classify(name: str, path: str, mime: str) -> tuple[str, list[str]]:
    b = blob(name, path, mime)
    tags: list[str] = []
    if any(t in b for t in REGULATORY): tags.append("regulatory_newhaven_candidate")
    if any(t in b for t in SATELLITE): tags.append("satellite_remote_sensing")
    if any(t in b for t in GROUND): tags.append("ground_monitoring")
    if any(t in b for t in MET): tags.append("meteorology_or_model")
    if any(t in b for t in QA): tags.append("qa_validation_readiness")
    if "dossier" in b or "evidence" in b or "report" in b: tags.append("dossier_or_report")
    if "workflow" in b or "github" in b or "log" in b: tags.append("workflow_or_run_history")
    if ext(name) in RAW_EXT: tags.append("structured_or_raw_data")

    if "regulatory_newhaven_candidate" in tags and ("annual" in b or "performance" in b):
        category = "newhaven_official_annual_performance"
    elif "regulatory_newhaven_candidate" in tags:
        category = "newhaven_regulatory_document"
    elif "satellite_remote_sensing" in tags:
        category = "satellite_or_remote_sensing"
    elif "ground_monitoring" in tags:
        category = "ground_air_quality_monitoring"
    elif "meteorology_or_model" in tags:
        category = "meteorology_or_model_context"
    elif "qa_validation_readiness" in tags:
        category = "quality_gate_or_validation"
    elif "workflow_or_run_history" in tags:
        category = "workflow_or_operational_history"
    elif "dossier_or_report" in tags:
        category = "report_or_dossier"
    elif ext(name) in RAW_EXT:
        category = "raw_or_structured_data"
    else:
        category = "other"
    return category, sorted(set(tags))


def release_class(name: str, path: str, mime: str, category: str) -> tuple[str, list[str]]:
    b = blob(name, path, mime)
    flags: list[str] = []
    if any(t in b for t in SECRET): flags.append("possible_secret_or_auth_material")
    if ext(name) in RISK_EXT: flags.append("archive_or_sensitive_file_type")
    if "/.git" in b or "git-test" in b: flags.append("repository_artifact_not_for_public_web")
    if "__src_" in b: flags.append("source_snapshot_version")
    if category.startswith("newhaven_"): flags.append("high_value_official_candidate")
    if category in {"satellite_or_remote_sensing", "ground_air_quality_monitoring", "meteorology_or_model_context"}:
        flags.append("context_data_requires_qa_before_claims")

    if "possible_secret_or_auth_material" in flags or "repository_artifact_not_for_public_web" in flags:
        release = "never_publish_raw"
    elif ext(name) in RISK_EXT:
        release = "controlled_review_only"
    elif category.startswith("newhaven_"):
        release = "public_citable_after_manual_source_check"
    elif category in {"quality_gate_or_validation", "report_or_dossier"}:
        release = "public_summary_ok_controlled_detail"
    elif category in {"satellite_or_remote_sensing", "ground_air_quality_monitoring", "meteorology_or_model_context"}:
        release = "context_only_until_qa_gate_passes"
    else:
        release = "inventory_only"
    return release, sorted(set(flags))


def service_from_env():
    raw = os.getenv("GDRIVE_SERVICE_ACCOUNT") or os.getenv("GDRIVE_SERVICE_ACCOUNT_JSON") or os.getenv("GDRIVE_CREDENTIALS")
    if not raw:
        raise SystemExit("Missing GDRIVE_SERVICE_ACCOUNT secret")
    info = json.loads(raw)
    creds = service_account.Credentials.from_service_account_info(info, scopes=["https://www.googleapis.com/auth/drive.readonly"])
    return build("drive", "v3", credentials=creds, cache_discovery=False), info.get("client_email", "")


def list_children(service: Any, folder_id: str) -> list[dict[str, Any]]:
    q = f"'{folder_id}' in parents and trashed=false"
    fields = "nextPageToken, files(id,name,mimeType,modifiedTime,createdTime,size,md5Checksum,webViewLink,shortcutDetails)"
    rows: list[dict[str, Any]] = []
    token = None
    while True:
        res = service.files().list(q=q, fields=fields, pageSize=1000, pageToken=token, supportsAllDrives=True, includeItemsFromAllDrives=True).execute()
        rows.extend(res.get("files", []))
        token = res.get("nextPageToken")
        if not token:
            return rows


def crawl(service: Any, root_id: str, max_files: int, max_depth: int) -> tuple[list[dict[str, Any]], list[dict[str, str]], bool]:
    q: deque[tuple[str, str, int]] = deque([(root_id, "ROOT", 0)])
    seen: set[str] = set()
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    truncated = False
    while q:
        folder_id, folder_path, depth = q.popleft()
        if folder_id in seen or depth > max_depth:
            continue
        seen.add(folder_id)
        try:
            children = list_children(service, folder_id)
        except Exception as exc:
            errors.append({"folder_path": folder_path, "folder_id_hash": sha_text(folder_id)[:12], "error": repr(exc)})
            continue
        for item in children:
            name = item.get("name", "")
            mime = item.get("mimeType", "")
            path = f"{folder_path}/{name}"
            category, tags = classify(name, path, mime)
            release, flags = release_class(name, path, mime, category)
            row = {
                "name": name,
                "path": path,
                "id_hash": sha_text(item.get("id", ""))[:16],
                "mimeType": mime,
                "ext": ext(name),
                "createdTime": item.get("createdTime", ""),
                "modifiedTime": item.get("modifiedTime", ""),
                "size": item.get("size", ""),
                "md5_present": bool(item.get("md5Checksum")),
                "year_candidates": ";".join(map(str, years(path))),
                "category": category,
                "tags": ";".join(tags),
                "release_class": release,
                "risk_flags": ";".join(flags),
                "depth": depth,
            }
            rows.append(row)
            if len(rows) >= max_files:
                truncated = True
                return rows, errors, truncated
            if mime == FOLDER_MIME:
                q.append((item["id"], path, depth + 1))
            elif mime == SHORTCUT_MIME:
                target = item.get("shortcutDetails", {}).get("targetId")
                target_mime = item.get("shortcutDetails", {}).get("targetMimeType")
                if target and target_mime == FOLDER_MIME:
                    q.append((target, path + " [shortcut]", depth + 1))
    return rows, errors, truncated


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-files", type=int, default=25000)
    ap.add_argument("--max-depth", type=int, default=12)
    ap.add_argument("--output-root", default="outputs/drive_forensic_audit")
    ap.add_argument("--site-public", default="site_public")
    ap.add_argument("--site-unredacted", default="site_unredacted")
    ap.add_argument("--fail-if-truncated", action="store_true")
    args = ap.parse_args()

    root_id = os.getenv("GDRIVE_FOLDER_ID", "").strip()
    if not root_id:
        raise SystemExit("Missing GDRIVE_FOLDER_ID secret")
    svc, client_email = service_from_env()
    rows, errors, truncated = crawl(svc, root_id, args.max_files, args.max_depth)

    out = Path(args.output_root)
    public_data = Path(args.site_public) / "data"
    private_data = Path(args.site_unredacted) / "data"
    out.mkdir(parents=True, exist_ok=True)
    public_data.mkdir(parents=True, exist_ok=True)
    private_data.mkdir(parents=True, exist_ok=True)

    fields = ["name", "path", "id_hash", "mimeType", "ext", "createdTime", "modifiedTime", "size", "md5_present", "year_candidates", "category", "tags", "release_class", "risk_flags", "depth"]
    public_fields = [f for f in fields if f not in {"path"}]
    public_rows = [{k: v for k, v in r.items() if k in public_fields} for r in rows if r["release_class"] != "never_publish_raw"]

    write_csv(out / "aq26_drive_inventory.csv", rows, fields)
    write_csv(out / "aq26_drive_inventory_public.csv", public_rows, public_fields)

    category_counts = Counter(r["category"] for r in rows)
    release_counts = Counter(r["release_class"] for r in rows)
    flag_counts = Counter(flag for r in rows for flag in str(r["risk_flags"]).split(";") if flag)
    official = [r for r in rows if r["category"].startswith("newhaven_")]

    summary = {
        "generated_utc": utc_now(),
        "scope": "AQ26 Google Drive evidence lake inventory and publication risk screen",
        "root_folder_id_hash": sha_text(root_id)[:16],
        "service_account": client_email,
        "total_items": len(rows),
        "truncated": truncated,
        "max_files": args.max_files,
        "max_depth": args.max_depth,
        "folder_errors": len(errors),
        "category_counts": dict(category_counts),
        "release_class_counts": dict(release_counts),
        "risk_flag_counts": dict(flag_counts),
        "newhaven_official_candidate_count": len(official),
        "scientific_boundary": "Inventory and triage only. No causal attribution, health attribution, permit-breach or regulatory finding is made by this audit.",
        "publication_controls": ["public_citable_after_manual_source_check", "public_summary_ok_controlled_detail", "context_only_until_qa_gate_passes", "controlled_review_only", "never_publish_raw", "inventory_only"],
    }
    review = dict(summary)
    review["folder_errors_detail"] = errors
    review["high_value_candidates"] = official[:500]
    review["never_publish_raw"] = [r for r in rows if r["release_class"] == "never_publish_raw"][:500]

    (out / "aq26_drive_forensic_summary_public.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    (out / "aq26_drive_forensic_review_private.json").write_text(json.dumps(review, indent=2, ensure_ascii=False), encoding="utf-8")
    (public_data / "drive_forensic_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    (private_data / "drive_forensic_review.json").write_text(json.dumps(review, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps(summary, indent=2))
    if truncated and args.fail_if_truncated:
        raise SystemExit("Drive inventory reached max_files and fail-if-truncated was enabled")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
