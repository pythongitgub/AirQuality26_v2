#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple


def read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        obj = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def parse_date(value: str) -> dt.date:
    return dt.date.fromisoformat(value)


def week_windows(end_date: dt.date, history_weeks: int) -> List[Tuple[dt.date, dt.date]]:
    """Return weekly windows ending at end_date and stepping back.

    Windows are [start, end] date labels for display and validation.
    The current AQ26 convention is controlled-review weekly slots, not legal sampling periods.
    """
    out = []
    for i in range(history_weeks):
        end = end_date - dt.timedelta(days=i * 7)
        start = end - dt.timedelta(days=6)
        out.append((start, end))
    return out


def load_existing(output_root: Path) -> Dict[Tuple[str, str], Dict[str, Any]]:
    locations = [
        output_root / "website_history",
        output_root / "website_history" / "two_year_validated",
        output_root / "10_historical_backfill" / "history",
        output_root / "10_historical_backfill" / "site_history",
        output_root / "historical_site" / "history",
    ]
    by_window: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for folder in locations:
        if not folder.exists():
            continue
        for p in sorted(folder.glob("*.json")):
            if p.name.startswith("weekly_index"):
                continue
            obj = read_json(p)
            if not obj:
                continue
            win = obj.get("date_window") or {}
            start, end = win.get("start"), win.get("end")
            if start and end:
                by_window[(start, end)] = obj
        previous = read_json(folder / "weekly_index.previous.json")
        for obj in previous.get("weeks", []) if isinstance(previous.get("weeks"), list) else []:
            if not isinstance(obj, dict):
                continue
            win = obj.get("date_window") or {}
            start, end = win.get("start"), win.get("end")
            if start and end:
                by_window[(start, end)] = obj
    return by_window


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output-root", default="outputs")
    ap.add_argument("--history-weeks", type=int, default=104)
    ap.add_argument("--end-date", default="2026-05-25")
    args = ap.parse_args()

    output_root = Path(args.output_root)
    out_dir = output_root / "website_history" / "two_year_validated"
    end_date = parse_date(args.end_date)
    existing = load_existing(output_root)

    rows: List[Dict[str, Any]] = []
    completed = 0
    pending = 0

    for start, end in week_windows(end_date, args.history_weeks):
        key = (start.isoformat(), end.isoformat())
        found = existing.get(key)
        if found and int(found.get("source_record_count") or 0) > 0:
            found = dict(found)
            found.setdefault("backfill_status", "validated_historical_summary_loaded")
            found["history_slot_integrity"] = {
                "date_validated": True,
                "slot_sha256": sha256_text(f"{key[0]}|{key[1]}|{found.get('run_ts')}|{found.get('source_record_count')}"),
                "evidence_status": "completed_summary_available",
                "notes": "Loaded from existing weekly history/backfill summary. Source-level evidence remains governed by its own manifests and ledgers."
            }
            completed += 1
            rows.append(found)
        else:
            pending += 1
            rows.append({
                "run_ts": f"BACKFILL_SLOT_{key[0]}_{key[1]}",
                "date_window": {"start": key[0], "end": key[1]},
                "backfill_status": "pending_source_specific_backfill",
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
                "history_slot_integrity": {
                    "date_validated": True,
                    "slot_sha256": sha256_text(f"{key[0]}|{key[1]}|pending_source_specific_backfill"),
                    "evidence_status": "pending",
                    "notes": "Date window validated. Real historical evidence records must be generated by controlled source-specific backfill before scientific use."
                }
            })

    manifest = {
        "created_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "history_end_date": end_date.isoformat(),
        "history_weeks": args.history_weeks,
        "first_window": rows[-1]["date_window"] if rows else None,
        "last_window": rows[0]["date_window"] if rows else None,
        "completed_summary_slots": completed,
        "pending_backfill_slots": pending,
        "date_validation_ready": True,
        "evidence_complete": pending == 0,
        "external_submission_ready": False,
        "integrity_sha256": sha256_text(json.dumps(rows, sort_keys=True, default=str)),
        "controlled_review_notes": [
            "This validates the two-year weekly date spine up to the requested end date.",
            "Completed historical weekly summaries are collated where available.",
            "Pending slots are not represented as harvested evidence.",
            "No WHO/UNEP/EEA/C40 or named-expert endorsement or representation is claimed.",
            "No causal attribution is claimed."
        ],
        "weeks": rows,
    }

    write_json(output_root / "website_history" / "two_year_weekly_history_manifest.json", manifest)
    for row in rows:
        write_json(out_dir / f"{row['run_ts']}.json", row)

    print(json.dumps({
        "history_end_date": end_date.isoformat(),
        "history_weeks": args.history_weeks,
        "completed_summary_slots": completed,
        "pending_backfill_slots": pending,
        "evidence_complete": pending == 0,
        "manifest": str(output_root / "website_history" / "two_year_weekly_history_manifest.json")
    }, indent=2))


if __name__ == "__main__":
    main()
