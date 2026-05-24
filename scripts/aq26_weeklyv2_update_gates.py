#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, datetime as dt
from pathlib import Path

def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}

def write(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output-root", default="outputs")
    args = ap.parse_args()
    root = Path(args.output_root)
    gates_path = root / "12_scoring" / "evidence_readiness_gates.json"
    gates = load(gates_path)
    red = load(root / "99_integrity" / "redaction_audit.json")
    cams = load(root / "09_cams" / "cams_readiness.json")
    drive = load(root / "08_gdrive_snapshot" / "gdrive_recursive_inventory.json")
    openaq = load(root / "04_ground_aq_providers" / "openaq_safety_manifest.json")
    earthdata = load(root / "15_optional_sources" / "earthdata_readiness.json")
    cdse = load(root / "15_optional_sources" / "cdse_auth_readiness.json")
    gemini = load(root / "14_ai" / "gemini_summary.json")

    gates["updated_at_utc"] = dt.datetime.now(dt.timezone.utc).isoformat()
    gates["redaction_ready"] = (red.get("leak_count") == 0)
    gates["cams_key_present"] = bool(cams.get("cams_key_present"))
    gates["cams_endpoint_configured"] = bool(cams.get("cams_endpoint_configured"))
    gates["cams_data_ready"] = bool(cams.get("cams_data_ready"))
    gates["drive_inventory_truncated"] = bool(drive.get("drive_inventory_truncated"))
    gates["openaq_safety_ready"] = bool(openaq.get("enabled")) and not bool(openaq.get("rate_limit_seen")) and not bool(openaq.get("auth_error_seen"))
    gates["earthdata_key_present"] = bool(earthdata.get("earthdata_key_present"))
    gates["earthdata_cmr_ready"] = bool(earthdata.get("earthdata_cmr_ready"))
    gates["cdse_auth_ready"] = bool(cdse.get("cdse_token_ready"))
    gates["gemini_summary_ready"] = bool(gemini.get("gemini_summary_ready"))
    gates["external_submission_ready"] = False

    write(gates_path, gates)
    print(json.dumps(gates, indent=2))

if __name__ == "__main__":
    main()
