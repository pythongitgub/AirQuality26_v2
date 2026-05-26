#!/usr/bin/env python3
"""
AQ26 LAQN / Imperial ERG AirQuality API provider probe.

Purpose
-------
Adds London Air Quality Network (LAQN) / Imperial ERG AirQuality API as a
validated urban comparator provider for AQ26.

This first-stage provider:
- Fetches metadata endpoints:
  * /Information/Species/Json
  * /Information/Groups/Json
  * /Information/MonitoringSites/GroupName={GroupName}/Json
  * /Information/MonitoringSiteSpecies/GroupName={GroupName}/Json
  * /Information/IndexHealthAdvice/Json
- Optionally runs a tiny one-site/one-species historical data probe:
  * /Data/SiteSpecies/SiteCode={SiteCode}/SpeciesCode={SpeciesCode}/StartDate={StartDate}/EndDate={EndDate}/Json
- Writes compact AQ26 source records with provenance and temporal_role fields.
- Does not fabricate observations or infer missing values.

Important scientific caveat:
LAQN is a validated London/urban comparator network. It should strengthen
AQ26 control/context evidence, not be presented as Newhaven-specific evidence.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import quote

import requests

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None


DEFAULT_BASE_URL = "https://api.erg.ic.ac.uk/AirQuality"


def now_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def mkdir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, payload: Any) -> None:
    mkdir(path.parent)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    mkdir(path.parent)
    fieldnames: List[str] = []
    for row in rows:
        for k in row:
            if k not in fieldnames:
                fieldnames.append(k)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
        w.writeheader()
        for row in rows:
            w.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v for k, v in row.items()})


def load_config(path: Optional[str]) -> Dict[str, Any]:
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        return {}
    txt = p.read_text(encoding="utf-8")
    if yaml is not None:
        return yaml.safe_load(txt) or {}
    # Very small fallback: config not essential because CLI args have defaults.
    return {}


def normalise_base_url(url: str) -> str:
    return (url or DEFAULT_BASE_URL).rstrip("/")


def endpoint_url(base_url: str, path: str) -> str:
    return normalise_base_url(base_url) + "/" + path.lstrip("/")


def safe_component(value: str) -> str:
    # Keep LAQN path separators intact elsewhere; encode each variable only.
    return quote(str(value), safe="")


def make_source_record(
    *,
    source_type: str = "laqn",
    source_class: str = "validated_urban_comparator",
    title: str,
    url: str,
    status: str,
    http_status: Optional[int],
    output_path: Optional[str],
    record_count: int = 0,
    sha256: Optional[str] = None,
    notes: str = "",
    error: Optional[str] = None,
    temporal_role: str = "reference_metadata",
    observed_start: Optional[str] = None,
    observed_end: Optional[str] = None,
    source_confidence: str = "validated_monitoring_network",
) -> Dict[str, Any]:
    ts = now_utc()
    return {
        "source_type": source_type,
        "source_class": source_class,
        "provider": "London Air Quality Network / Imperial ERG AirQuality API",
        "title": title,
        "status": status,
        "http_status": http_status,
        "url": url,
        "retrieved_at_utc": ts,
        "retrieved_at_uk": ts,  # AQ26 downstream can convert display timezone if required.
        "date_uk": ts[:10],
        "temporal_role": temporal_role,
        "observed_start": observed_start,
        "observed_end": observed_end,
        "source_confidence": source_confidence,
        "provenance_level": "official_or_network_machine_readable",
        "record_count": int(record_count or 0),
        "output_path": output_path,
        "sha256": sha256,
        "notes": notes,
        "error": error,
    }


def request_json(
    *,
    url: str,
    timeout: int,
    retries: int,
    backoff: int,
    user_agent: str,
) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any], Optional[bytes]]:
    headers = {
        "User-Agent": user_agent,
        "Accept": "application/json,text/json,*/*",
    }
    attempts = []
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            r = requests.get(url, headers=headers, timeout=timeout)
            content = r.content or b""
            meta = {
                "url": r.url,
                "http_status": r.status_code,
                "content_type": r.headers.get("content-type", ""),
                "bytes": len(content),
                "sha256": sha256_bytes(content),
                "attempt": attempt,
            }
            attempts.append(meta)
            if r.status_code == 200:
                try:
                    return r.json(), meta, content
                except Exception as exc:
                    last_error = f"json_parse_failed: {exc!r}"
                    return None, {**meta, "error": last_error}, content
            last_error = f"http_status_{r.status_code}"
        except Exception as exc:
            last_error = repr(exc)
            attempts.append({"url": url, "attempt": attempt, "error": last_error, "http_status": None})
            if attempt < retries:
                time.sleep(backoff * attempt)
    return None, {"url": url, "http_status": None, "error": last_error, "attempts": attempts}, None


def deep_count_json_records(payload: Any) -> int:
    """Best-effort count for nested LAQN JSON payloads."""
    if payload is None:
        return 0
    if isinstance(payload, list):
        return len(payload)
    if isinstance(payload, dict):
        # LAQN often wraps arrays under AirQualityData / AirQualitySpecies / etc.
        array_counts = []
        for v in payload.values():
            if isinstance(v, list):
                array_counts.append(len(v))
            elif isinstance(v, dict):
                c = deep_count_json_records(v)
                if c:
                    array_counts.append(c)
        return max(array_counts) if array_counts else (1 if payload else 0)
    return 0


def flatten_dicts(payload: Any) -> List[Dict[str, Any]]:
    """Return a list of dicts found inside nested API payload."""
    out: List[Dict[str, Any]] = []

    def walk(x: Any) -> None:
        if isinstance(x, list):
            for item in x:
                walk(item)
        elif isinstance(x, dict):
            # Prefer actual data rows, not wrapper dicts.
            scalar_keys = [k for k, v in x.items() if not isinstance(v, (dict, list))]
            nested_keys = [k for k, v in x.items() if isinstance(v, (dict, list))]
            if scalar_keys and len(scalar_keys) >= 2:
                out.append(x)
            for k in nested_keys:
                walk(x[k])

    walk(payload)
    # Deduplicate JSON serialisation.
    seen = set()
    rows = []
    for row in out:
        key = json.dumps(row, sort_keys=True, ensure_ascii=False)
        if key not in seen:
            seen.add(key)
            rows.append(row)
    return rows


def find_first_key(row: Dict[str, Any], candidates: Iterable[str]) -> Optional[str]:
    lower = {str(k).lower(): k for k in row.keys()}
    for c in candidates:
        k = lower.get(c.lower())
        if k is not None:
            v = row.get(k)
            if v not in (None, ""):
                return str(v)
    return None


def select_site_species(site_species_payload: Any) -> Tuple[Optional[str], Optional[str]]:
    """Auto-select first plausible site/species pair from MonitoringSiteSpecies JSON."""
    rows = flatten_dicts(site_species_payload)
    for row in rows:
        site_code = find_first_key(row, ["SiteCode", "Site", "site_code", "@SiteCode", "Code"])
        species_code = find_first_key(row, ["SpeciesCode", "Species", "species_code", "@SpeciesCode"])
        if site_code and species_code:
            return site_code, species_code
    return None, None


def date_variants(iso_date: str, formats: List[str]) -> List[str]:
    d = dt.date.fromisoformat(iso_date)
    variants = []
    for fmt in formats:
        variants.append(d.strftime(fmt))
    # Robust fallback variants.
    variants.extend([d.strftime("%d%b%Y"), d.strftime("%d %b %Y"), d.isoformat()])
    # Preserve order, unique.
    seen = set()
    out = []
    for x in variants:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def fetch_endpoint(
    *,
    title: str,
    url: str,
    output_json: Path,
    output_csv: Optional[Path],
    timeout: int,
    retries: int,
    backoff: int,
    user_agent: str,
    temporal_role: str,
    notes: str,
) -> Tuple[Dict[str, Any], Optional[Any]]:
    payload, meta, content = request_json(url=url, timeout=timeout, retries=retries, backoff=backoff, user_agent=user_agent)
    if payload is not None:
        write_json(output_json, {
            "provider": "laqn",
            "title": title,
            "source_url": meta.get("url", url),
            "retrieved_at_utc": now_utc(),
            "payload": payload,
        })
        rows = flatten_dicts(payload)
        if output_csv is not None and rows:
            write_csv(output_csv, rows)
        rec = make_source_record(
            title=title,
            url=meta.get("url", url),
            status="ok",
            http_status=meta.get("http_status"),
            output_path=str(output_json),
            record_count=deep_count_json_records(payload),
            sha256=meta.get("sha256"),
            notes=notes,
            temporal_role=temporal_role,
        )
        return rec, payload
    else:
        # Save failure metadata for provenance rather than failing the workflow.
        write_json(output_json.with_suffix(".failed.json"), {
            "provider": "laqn",
            "title": title,
            "requested_url": url,
            "retrieved_at_utc": now_utc(),
            "meta": meta,
        })
        rec = make_source_record(
            title=title,
            url=url,
            status="warning",
            http_status=meta.get("http_status"),
            output_path=str(output_json.with_suffix(".failed.json")),
            record_count=0,
            sha256=meta.get("sha256"),
            notes=notes,
            error=meta.get("error", "request_failed_or_json_parse_failed"),
            temporal_role=temporal_role,
        )
        return rec, None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--config", default="configs/aq26_laqn.yml")
    ap.add_argument("--base-url", default="")
    ap.add_argument("--group-name", default="")
    ap.add_argument("--out-root", default="")
    ap.add_argument("--site-root", default="")
    ap.add_argument("--timeout", type=int, default=0)
    ap.add_argument("--retries", type=int, default=0)
    ap.add_argument("--backoff", type=int, default=0)
    ap.add_argument("--user-agent", default=os.getenv("AQ26_USER_AGENT", "AQ26/3.4 LAQN provider probe"))
    ap.add_argument("--run-data-probe", action="store_true")
    ap.add_argument("--site-code", default="")
    ap.add_argument("--species-code", default="")
    ap.add_argument("--start-date", default="")
    ap.add_argument("--end-date", default="")
    args = ap.parse_args()

    repo = Path(args.repo_root).resolve()
    cfg = load_config(str(repo / args.config) if args.config else None)

    provider_cfg = cfg.get("provider", {}) if isinstance(cfg, dict) else {}
    runtime_cfg = cfg.get("runtime", {}) if isinstance(cfg, dict) else {}
    probe_cfg = cfg.get("default_probe", {}) if isinstance(cfg, dict) else {}
    outputs_cfg = cfg.get("outputs", {}) if isinstance(cfg, dict) else {}

    base_url = args.base_url or provider_cfg.get("base_url") or DEFAULT_BASE_URL
    group_name = args.group_name or probe_cfg.get("group_name") or "London"
    timeout = args.timeout or int(runtime_cfg.get("timeout_seconds", 45))
    retries = args.retries or int(runtime_cfg.get("max_retries", 3))
    backoff = args.backoff or int(runtime_cfg.get("retry_backoff_seconds", 8))
    out_root = repo / (args.out_root or outputs_cfg.get("root") or "outputs/31_laqn")
    site_root = repo / (args.site_root or outputs_cfg.get("site_root") or "site_public/data/providers/laqn")
    date_fmts = list(probe_cfg.get("date_formats") or ["%d%b%Y", "%d %b %Y"])

    mkdir(out_root)
    mkdir(site_root)

    records: List[Dict[str, Any]] = []

    # Metadata endpoints confirmed by the LAQN help page.
    endpoints = [
        (
            "LAQN pollutant species metadata",
            endpoint_url(base_url, "/Information/Species/Json"),
            site_root / "species.json",
            out_root / "species_rows.csv",
            "reference_metadata",
            "Commonly monitored pollutant/species codes and health-effect metadata.",
        ),
        (
            "LAQN groups metadata",
            endpoint_url(base_url, "/Information/Groups/Json"),
            site_root / "groups.json",
            out_root / "groups_rows.csv",
            "reference_metadata",
            "Monitoring network groups available for other calls.",
        ),
        (
            f"LAQN monitoring sites for {group_name}",
            endpoint_url(base_url, f"/Information/MonitoringSites/GroupName={safe_component(group_name)}/Json"),
            site_root / f"sites_{group_name.lower()}.json",
            out_root / f"sites_{group_name.lower()}_rows.csv",
            "reference_metadata",
            "Monitoring site metadata for selected group.",
        ),
        (
            f"LAQN monitoring site/species for {group_name}",
            endpoint_url(base_url, f"/Information/MonitoringSiteSpecies/GroupName={safe_component(group_name)}/Json"),
            site_root / f"site_species_{group_name.lower()}.json",
            out_root / f"site_species_{group_name.lower()}_rows.csv",
            "reference_metadata",
            "Site/species capability metadata for selected group.",
        ),
        (
            "LAQN index health advice",
            endpoint_url(base_url, "/Information/IndexHealthAdvice/Json"),
            site_root / "index_health_advice.json",
            out_root / "index_health_advice_rows.csv",
            "reference_metadata",
            "Health-advice metadata for AQ index; context only, not AQ26 health-impact attribution.",
        ),
    ]

    site_species_payload = None
    for title, url, json_path, csv_path, temporal_role, notes in endpoints:
        rec, payload = fetch_endpoint(
            title=title,
            url=url,
            output_json=json_path,
            output_csv=csv_path,
            timeout=timeout,
            retries=retries,
            backoff=backoff,
            user_agent=args.user_agent,
            temporal_role=temporal_role,
            notes=notes,
        )
        records.append(rec)
        if "site/species" in title.lower():
            site_species_payload = payload

    # Optional tiny historical data probe.
    run_data_probe = bool(args.run_data_probe or os.getenv("AQ26_LAQN_RUN_DATA_PROBE", "").lower() in ("1", "true", "yes"))
    if run_data_probe:
        site_code = args.site_code or str(probe_cfg.get("site_code") or "")
        species_code = args.species_code or str(probe_cfg.get("species_code") or "")
        if not site_code or not species_code:
            auto_site, auto_species = select_site_species(site_species_payload)
            site_code = site_code or (auto_site or "")
            species_code = species_code or (auto_species or "")

        start_date = args.start_date or probe_cfg.get("start_date") or "2024-07-22"
        end_date = args.end_date or probe_cfg.get("end_date") or "2024-07-23"

        if not site_code or not species_code:
            records.append(make_source_record(
                title="LAQN tiny SiteSpecies historical data probe",
                url=base_url,
                status="warning",
                http_status=None,
                output_path=None,
                record_count=0,
                notes="Data probe requested but no site/species pair could be auto-selected from MonitoringSiteSpecies metadata.",
                error="missing_site_or_species_code",
                temporal_role="historical_observation",
                observed_start=start_date,
                observed_end=end_date,
            ))
        else:
            probe_ok = False
            probe_attempt_records = []
            for sd in date_variants(start_date, date_fmts):
                for ed in date_variants(end_date, date_fmts):
                    data_url = endpoint_url(
                        base_url,
                        f"/Data/SiteSpecies/SiteCode={safe_component(site_code)}/"
                        f"SpeciesCode={safe_component(species_code)}/"
                        f"StartDate={safe_component(sd)}/EndDate={safe_component(ed)}/Json",
                    )
                    rec, payload = fetch_endpoint(
                        title=f"LAQN tiny historical data probe {site_code}/{species_code} {start_date} to {end_date}",
                        url=data_url,
                        output_json=out_root / f"data_probe_{site_code}_{species_code}_{start_date}_{end_date}.json",
                        output_csv=out_root / f"data_probe_{site_code}_{species_code}_{start_date}_{end_date}.csv",
                        timeout=timeout,
                        retries=retries,
                        backoff=backoff,
                        user_agent=args.user_agent,
                        temporal_role="historical_observation",
                        notes="Tiny one-site/one-species historical data probe. Use only to confirm API structure before bulk harvesting.",
                    )
                    rec["observed_start"] = start_date
                    rec["observed_end"] = end_date
                    rec["site_code"] = site_code
                    rec["species_code"] = species_code
                    probe_attempt_records.append(rec)
                    if rec["status"] == "ok" and rec.get("record_count", 0) > 0:
                        records.append(rec)
                        probe_ok = True
                        break
                if probe_ok:
                    break
            if not probe_ok:
                # Keep all failed attempts for debugging, but non-fatal.
                records.extend(probe_attempt_records[:3] or probe_attempt_records)

    # Source record outputs.
    write_json(out_root / "laqn_source_records.json", records)
    write_json(site_root / "source_records.json", records)
    write_csv(out_root / "laqn_source_records.csv", records)

    # Compact summary for integration into AQ26 backfill dashboards.
    ok_records = [r for r in records if r.get("status") == "ok"]
    warnings = [r for r in records if r.get("status") == "warning"]
    summary = {
        "provider": "laqn",
        "name": "London Air Quality Network / Imperial ERG AirQuality API",
        "base_url": base_url,
        "group_name": group_name,
        "retrieved_at_utc": now_utc(),
        "status": "ok" if ok_records else "warning",
        "records_total": len(records),
        "records_ok": len(ok_records),
        "records_warning": len(warnings),
        "metadata_ready": any(r.get("title") == "LAQN pollutant species metadata" and r.get("status") == "ok" for r in records)
                          and any("monitoring sites" in str(r.get("title","")).lower() and r.get("status") == "ok" for r in records),
        "data_probe_requested": run_data_probe,
        "data_probe_ready": any(r.get("temporal_role") == "historical_observation" and r.get("status") == "ok" and int(r.get("record_count") or 0) > 0 for r in records),
        "scientific_caveat": "LAQN is a validated London/urban comparator network. It is not Newhaven-specific evidence unless used explicitly as an urban/control comparator.",
        "source_records_path": str(out_root / "laqn_source_records.json"),
    }
    write_json(out_root / "laqn_summary.json", summary)
    write_json(site_root / "summary.json", summary)

    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
