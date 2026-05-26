#!/usr/bin/env python3
"""
AQ26 UK-AIR SOS observation probe scaffold.

This script is deliberately conservative. It reads the verified UK-AIR SOS
offering inventory and tries a very small number of GetObservation requests for
explicit date windows. It writes raw responses and source records, but it does
not add observations to public pollutant time-series until parsing/QA rules are
confirmed.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import urlencode

import requests


def now_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def mkdir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def write_json(p: Path, payload: Any) -> None:
    mkdir(p.parent)
    p.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def source_record(**kw) -> Dict[str, Any]:
    ts = now_utc()
    rec = {
        "source_type": "ukair_sos_observation_probe",
        "source_class": "official_ground_air",
        "provider": "Defra UK-AIR Sensor Observation Service",
        "retrieved_at_utc": ts,
        "retrieved_at_uk": ts,
        "date_uk": ts[:10],
        "temporal_role": "historical_observation_probe",
        "source_confidence": "official_regulatory_machine_readable",
        "provenance_level": "official_machine_readable",
        "current_context_only": False,
    }
    rec.update(kw)
    return rec


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--repo-root", default=".")
    p.add_argument("--start-date", required=True)
    p.add_argument("--end-date", required=True)
    p.add_argument("--limit", type=int, default=3)
    p.add_argument("--sleep", type=float, default=2.0)
    p.add_argument("--timeout", type=int, default=60)
    p.add_argument("--capabilities-url", default="https://uk-air.defra.gov.uk/sos-ukair/sos")
    p.add_argument("--offerings-path", default="outputs/30_ukair_sos/ukair_sos_offerings_full.json")
    p.add_argument("--out-root", default="outputs/30_ukair_sos/observations_probe")
    p.add_argument("--user-agent", default=os.getenv("AQ26_USER_AGENT", "AQ26/3.4 ukair-sos observation-probe"))
    args = p.parse_args()

    repo = Path(args.repo_root).resolve()
    offerings_path = repo / args.offerings_path
    out_root = repo / args.out_root / f"week_{args.start_date}_{args.end_date}"
    mkdir(out_root)

    if not offerings_path.exists():
        recs = [source_record(
            title="UK-AIR SOS observation probe skipped",
            status="skipped",
            url=args.capabilities_url,
            http_status=None,
            record_count=0,
            output_path=None,
            observed_start=args.start_date,
            observed_end=args.end_date,
            notes=f"Missing offerings inventory: {offerings_path}",
            error="missing_offerings_inventory",
        )]
        write_json(out_root / "source_records.json", recs)
        print(json.dumps({"ok": False, "records": recs}, indent=2))
        return 0

    offerings = json.loads(offerings_path.read_text(encoding="utf-8"))
    headers = {"User-Agent": args.user_agent, "Accept": "application/json,application/xml,text/xml,*/*"}

    recs: List[Dict[str, Any]] = []
    completed = 0
    for off in offerings:
        if completed >= args.limit:
            break
        off_id = off.get("identifier")
        props = off.get("observable_properties") or []
        if not off_id or not props:
            continue
        prop = props[0]
        params = {
            "service": "SOS",
            "version": "2.0.0",
            "request": "GetObservation",
            "offering": off_id,
            "observedProperty": prop,
            "temporalFilter": f"om:phenomenonTime,{args.start_date}T00:00:00Z/{args.end_date}T00:00:00Z",
            "responseFormat": "application/json",
        }
        url = args.capabilities_url + "?" + urlencode(params)
        try:
            r = requests.get(args.capabilities_url, params=params, headers=headers, timeout=args.timeout)
            raw = r.content or b""
            suffix = "json" if "json" in (r.headers.get("content-type","").lower()) else "xml"
            out = out_root / f"observation_probe_{completed+1}.{suffix}"
            out.write_bytes(raw)
            status = "ok" if r.status_code == 200 else "warning"
            recs.append(source_record(
                title="UK-AIR SOS GetObservation probe",
                status=status,
                url=r.url,
                http_status=r.status_code,
                record_count=0,
                output_path=str(out),
                sha256=sha256_bytes(raw),
                observed_start=args.start_date,
                observed_end=args.end_date,
                notes="Raw observation probe saved. Do not treat as validated timeseries until parser/QA confirms payload semantics.",
                error=None if status == "ok" else raw[:500].decode("utf-8", "ignore"),
                offering=off_id,
                observedProperty=prop,
            ))
        except Exception as exc:
            recs.append(source_record(
                title="UK-AIR SOS GetObservation probe",
                status="warning",
                url=url,
                http_status=None,
                record_count=0,
                output_path=None,
                observed_start=args.start_date,
                observed_end=args.end_date,
                notes="GetObservation probe failed; retained as non-blocking provider-development evidence.",
                error=repr(exc),
                offering=off_id,
                observedProperty=prop,
            ))
        completed += 1
        if completed < args.limit:
            time.sleep(args.sleep)

    write_json(out_root / "source_records.json", recs)
    print(json.dumps({"ok": any(r.get("status") == "ok" for r in recs), "records": recs}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
