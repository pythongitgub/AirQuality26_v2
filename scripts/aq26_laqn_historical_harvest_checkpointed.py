#!/usr/bin/env python3
"""
AQ26 checkpointed LAQN historical observation harvester.

This performs a deliberately controlled harvest. It reads LAQN site/species
capability rows already produced by the provider, selects a limited number of
site/species pairs, downloads one pair at a time, and checkpoints after each.

The script tries several known ERG/LAQN URL templates because the API is
XML-first and endpoint syntax can be strict. Successful raw responses are saved
as-is, then a compact run manifest is written.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

BASE = "https://api.erg.ic.ac.uk/AirQuality"

URL_TEMPLATES = [
    # JSON-first attempts
    BASE + "/Data/Site/SiteCode={site}/SpeciesCode={species}/StartDate={start}/EndDate={end}/Json",
    BASE + "/Data/Site/SiteCode={site}/SpeciesCode={species}/StartDate={start}/EndDate={end}",
    BASE + "/Data/SiteSpecies/SiteCode={site}/SpeciesCode={species}/StartDate={start}/EndDate={end}/Json",
    BASE + "/Data/SiteSpecies/SiteCode={site}/SpeciesCode={species}/StartDate={start}/EndDate={end}",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def read_csv_rows(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def first_value(row: Dict[str, str], names: Iterable[str]) -> str:
    for n in names:
        if n in row and str(row[n]).strip():
            return str(row[n]).strip()
    return ""


def candidate_pairs(site_species_csv: Path, max_pairs: int, priority_species: List[str]) -> List[Tuple[str, str]]:
    rows = read_csv_rows(site_species_csv)
    pairs: List[Tuple[str, str]] = []
    seen = set()
    priority = [s.upper() for s in priority_species]

    def row_pair(row):
        site = first_value(row, ["@SiteCode", "SiteCode", "site_code", "site"])
        species = first_value(row, ["@SpeciesCode", "SpeciesCode", "species_code", "species"])
        return site, species.upper()

    # priority pollutants first
    for wanted in priority:
        for r in rows:
            site, species = row_pair(r)
            if not site or not species or species != wanted:
                continue
            key = (site, species)
            if key not in seen:
                pairs.append(key); seen.add(key)
            if len(pairs) >= max_pairs:
                return pairs
    # then any remaining
    for r in rows:
        site, species = row_pair(r)
        if not site or not species:
            continue
        key = (site, species)
        if key not in seen:
            pairs.append(key); seen.add(key)
        if len(pairs) >= max_pairs:
            break
    return pairs


def fetch_url(url: str, timeout: int = 45) -> Tuple[int, str, str]:
    req = urllib.request.Request(url, headers={"User-Agent": "AQ26-LAQN-Harvester/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read().decode("utf-8", errors="replace")
            return int(getattr(r, "status", 200)), body, r.headers.get("content-type", "")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace") if e.fp else ""
        return int(e.code), body, e.headers.get("content-type", "") if e.headers else ""
    except Exception as e:
        return 0, str(e), "error"


def body_has_data(body: str) -> bool:
    if not body or len(body.strip()) < 20:
        return False
    low = body.lower()
    if "error" in low and len(body) < 500:
        return False
    # Count rough occurrences. LAQN can emit Measurement/Data tags or JSON arrays.
    return any(token in low for token in ["measurement", "reading", "@speciescode", "sitecode", "data"])


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, obj) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--site-species-csv", required=True, help="site_species_london_rows.csv from LAQN provider output")
    ap.add_argument("--out-root", required=True, help="Google Drive data/raw/laqn or repo output folder")
    ap.add_argument("--start-date", required=True, help="YYYY-MM-DD")
    ap.add_argument("--end-date", required=True, help="YYYY-MM-DD")
    ap.add_argument("--max-pairs", type=int, default=10)
    ap.add_argument("--sleep-seconds", type=float, default=1.0)
    ap.add_argument("--priority-species", default="NO2,PM25,PM10,O3,SO2,CO")
    args = ap.parse_args()

    run_ts = utc_now()
    out_root = Path(args.out_root).expanduser().resolve() / "runs" / run_ts
    raw_root = out_root / "raw_responses"
    pairs = candidate_pairs(Path(args.site_species_csv), args.max_pairs, [x.strip() for x in args.priority_species.split(",") if x.strip()])

    records = []
    for i, (site, species) in enumerate(pairs, start=1):
        status = "failed"
        selected_url = ""
        selected_body = ""
        selected_code = 0
        selected_content_type = ""
        attempts = []
        for tmpl in URL_TEMPLATES:
            url = tmpl.format(
                site=urllib.parse.quote(site),
                species=urllib.parse.quote(species),
                start=urllib.parse.quote(args.start_date),
                end=urllib.parse.quote(args.end_date),
            )
            code, body, ctype = fetch_url(url)
            ok = 200 <= code < 300 and body_has_data(body)
            attempts.append({"url": url, "http_status": code, "content_type": ctype, "ok": ok, "bytes": len(body.encode('utf-8', errors='replace'))})
            if ok:
                status = "ok"
                selected_url, selected_body, selected_code, selected_content_type = url, body, code, ctype
                break
            time.sleep(0.25)
        if selected_body:
            suffix = ".json" if "json" in selected_content_type.lower() or selected_body.lstrip().startswith(("{", "[")) else ".xml"
            raw_path = raw_root / f"{site}_{species}_{args.start_date}_{args.end_date}{suffix}"
            ensure_dir(raw_path.parent)
            raw_path.write_text(selected_body, encoding="utf-8")
            sha = sha256_text(selected_body)
            size = raw_path.stat().st_size
        else:
            raw_path = raw_root / f"{site}_{species}_{args.start_date}_{args.end_date}.error.txt"
            ensure_dir(raw_path.parent)
            raw_path.write_text(json.dumps(attempts, indent=2), encoding="utf-8")
            sha = sha256_text(raw_path.read_text(encoding="utf-8"))
            size = raw_path.stat().st_size

        rec = {
            "run_ts": run_ts,
            "sequence": i,
            "site_code": site,
            "species_code": species,
            "start_date": args.start_date,
            "end_date": args.end_date,
            "status": status,
            "selected_url": selected_url,
            "http_status": selected_code,
            "content_type": selected_content_type,
            "raw_path": str(raw_path),
            "size_bytes": size,
            "sha256": sha,
            "attempts": attempts,
            "retrieved_at_utc": iso_now(),
        }
        records.append(rec)
        write_json(out_root / "checkpoint_latest.json", {"run_ts": run_ts, "completed": len(records), "records": records})
        print(json.dumps({k: rec[k] for k in ["sequence", "site_code", "species_code", "status", "http_status", "size_bytes"]}, indent=2))
        time.sleep(args.sleep_seconds)

    summary = {
        "run_ts": run_ts,
        "created_at_utc": iso_now(),
        "start_date": args.start_date,
        "end_date": args.end_date,
        "pairs_requested": len(pairs),
        "ok_records": sum(1 for r in records if r["status"] == "ok"),
        "failed_records": sum(1 for r in records if r["status"] != "ok"),
        "status": "ok" if any(r["status"] == "ok" for r in records) else "warning_no_successful_observation_downloads",
    }
    write_json(out_root / "harvest_summary.json", summary)
    write_json(out_root / "harvest_records.json", records)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
