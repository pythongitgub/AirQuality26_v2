#!/usr/bin/env python3
"""
AQ26 LAQN / Imperial ERG AirQuality API provider probe v3.5.

Purpose
-------
Hardens the v3.4 LAQN provider for GitHub Actions and the AQ26 public site.

Fixes in v3.5
-------------
- Adds annual monitoring-objective XML endpoint support:
  /Annual/MonitoringObjective/GroupName={GroupName}
- Keeps IndexHealthAdvice as non-fatal and probes both original-case and lower-case help paths.
- Writes chart-safe JSON/CSV tables with normalised column names.
- Avoids absolute runner paths in public source records by writing repo-relative paths.
- Adds Europe/London date fields while keeping UTC provenance timestamps.
- Adds schema/readiness flags so the website can show "metadata ready" without implying
  "observation data ready".
- Does not fabricate observations or infer missing values.

Scientific caveat
-----------------
LAQN is a validated London/urban comparator network. It strengthens AQ26 contextual
and control evidence, but must not be presented as Newhaven-specific exposure evidence.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import quote

import requests

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None  # type: ignore

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None


DEFAULT_BASE_URL = "https://api.erg.ic.ac.uk/AirQuality"
UK_TZ = "Europe/London"


def now_utc_dt() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0)


def iso_z(d: dt.datetime) -> str:
    return d.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def uk_date_from_utc(d: dt.datetime) -> str:
    if ZoneInfo is None:
        return d.date().isoformat()
    return d.astimezone(ZoneInfo(UK_TZ)).date().isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def mkdir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def repo_relative(repo: Path, path: Optional[Path]) -> Optional[str]:
    if path is None:
        return None
    try:
        return str(path.resolve().relative_to(repo.resolve())).replace("\\", "/")
    except Exception:
        return str(path).replace("\\", "/")


def write_json(path: Path, payload: Any) -> None:
    mkdir(path.parent)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")


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
            clean = {}
            for k, v in row.items():
                if isinstance(v, (dict, list)):
                    clean[k] = json.dumps(v, ensure_ascii=False, sort_keys=True)
                else:
                    clean[k] = v
            w.writerow(clean)


def load_config(path: Optional[str]) -> Dict[str, Any]:
    if not path:
        return {}
    p = Path(path)
    if not p.exists():
        return {}
    txt = p.read_text(encoding="utf-8")
    if yaml is not None:
        return yaml.safe_load(txt) or {}
    return {}


def normalise_base_url(url: str) -> str:
    return (url or DEFAULT_BASE_URL).rstrip("/")


def endpoint_url(base_url: str, path: str) -> str:
    return normalise_base_url(base_url) + "/" + path.lstrip("/")


def safe_component(value: str) -> str:
    return quote(str(value), safe="")


def safe_col(name: str) -> str:
    x = str(name).strip().replace("@", "")
    x = "".join(ch if ch.isalnum() else "_" for ch in x)
    x = "_".join(part for part in x.split("_") if part)
    return x.lower() or "value"


def flatten_dicts(payload: Any) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []

    def walk(x: Any) -> None:
        if isinstance(x, list):
            for item in x:
                walk(item)
        elif isinstance(x, dict):
            scalar_keys = [k for k, v in x.items() if not isinstance(v, (dict, list))]
            nested_keys = [k for k, v in x.items() if isinstance(v, (dict, list))]
            if scalar_keys and len(scalar_keys) >= 2:
                out.append(dict(x))
            for k in nested_keys:
                walk(x[k])

    walk(payload)
    seen = set()
    rows = []
    for row in out:
        key = json.dumps(row, sort_keys=True, ensure_ascii=False)
        if key not in seen:
            seen.add(key)
            rows.append(row)
    return rows


def flatten_xml(content: bytes) -> List[Dict[str, Any]]:
    try:
        root = ET.fromstring(content)
    except Exception:
        return []
    rows: List[Dict[str, Any]] = []
    for elem in root.iter():
        row: Dict[str, Any] = {}
        row.update({f"@{k}": v for k, v in elem.attrib.items()})
        txt = (elem.text or "").strip()
        if txt and len(list(elem)) == 0:
            row["text"] = txt
        if len(row) >= 2:
            row["_tag"] = elem.tag.split("}")[-1]
            rows.append(row)
    # Deduplicate
    dedup, seen = [], set()
    for row in rows:
        key = json.dumps(row, sort_keys=True, ensure_ascii=False)
        if key not in seen:
            seen.add(key)
            dedup.append(row)
    return dedup


def normalise_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for row in rows:
        nr: Dict[str, Any] = {}
        for k, v in row.items():
            if isinstance(v, (dict, list)):
                continue
            nr[safe_col(k)] = v
        # Front-end convenience aliases.
        if "sitecode" in nr and "site_code" not in nr:
            nr["site_code"] = nr["sitecode"]
        if "speciescode" in nr and "species_code" not in nr:
            nr["species_code"] = nr["speciescode"]
        if "groupname" in nr and "group_name" not in nr:
            nr["group_name"] = nr["groupname"]
        if "websiteurl" in nr and "website_url" not in nr:
            nr["website_url"] = nr["websiteurl"]
        if "latitude" in nr and "lat" not in nr:
            try:
                nr["lat"] = float(nr["latitude"])
            except Exception:
                pass
        if "longitude" in nr and "lon" not in nr:
            try:
                nr["lon"] = float(nr["longitude"])
            except Exception:
                pass
        out.append(nr)
    return out


def request_payload(url: str, timeout: int, retries: int, backoff: int, user_agent: str) -> Tuple[Optional[Any], Dict[str, Any], bytes]:
    headers = {"User-Agent": user_agent, "Accept": "application/json, application/xml, text/xml, text/json, */*"}
    last_meta: Dict[str, Any] = {}
    last_content = b""
    for attempt in range(1, retries + 1):
        try:
            r = requests.get(url, headers=headers, timeout=timeout)
            content = r.content or b""
            ctype = r.headers.get("content-type", "")
            meta = {
                "url": r.url,
                "http_status": r.status_code,
                "content_type": ctype,
                "bytes": len(content),
                "sha256": sha256_bytes(content),
                "attempt": attempt,
            }
            last_meta, last_content = meta, content
            if r.status_code == 200:
                if "json" in ctype.lower() or url.lower().endswith("/json"):
                    try:
                        return r.json(), meta, content
                    except Exception as exc:
                        meta["error"] = f"json_parse_failed: {exc!r}"
                        return None, meta, content
                return {"_xml_rows": flatten_xml(content)}, meta, content
            last_meta["error"] = f"http_status_{r.status_code}"
        except Exception as exc:
            last_meta = {"url": url, "attempt": attempt, "error": repr(exc), "http_status": None}
            last_content = b""
        if attempt < retries:
            time.sleep(max(0, backoff))
    return None, last_meta, last_content


def make_source_record(repo: Path, **kw: Any) -> Dict[str, Any]:
    now = now_utc_dt()
    rec = {
        "source_type": "laqn",
        "source_class": "validated_urban_comparator",
        "provider": "London Air Quality Network / Imperial ERG AirQuality API",
        "title": kw.get("title", ""),
        "status": kw.get("status", "warning"),
        "http_status": kw.get("http_status"),
        "url": kw.get("url", ""),
        "retrieved_at_utc": iso_z(now),
        "retrieved_at_uk": now.astimezone(ZoneInfo(UK_TZ)).isoformat() if ZoneInfo is not None else iso_z(now),
        "date_uk": uk_date_from_utc(now),
        "temporal_role": kw.get("temporal_role", "reference_metadata"),
        "observed_start": kw.get("observed_start"),
        "observed_end": kw.get("observed_end"),
        "source_confidence": "validated_monitoring_network",
        "provenance_level": "official_or_network_machine_readable",
        "record_count": int(kw.get("record_count") or 0),
        "output_path": repo_relative(repo, kw.get("output_path")),
        "chart_safe_path": repo_relative(repo, kw.get("chart_safe_path")),
        "sha256": kw.get("sha256"),
        "notes": kw.get("notes", ""),
        "error": kw.get("error"),
    }
    return rec


def fetch_endpoint(repo: Path, title: str, url: str, output_json: Path, output_csv: Path, chart_json: Path,
                   timeout: int, retries: int, backoff: int, user_agent: str,
                   notes: str, temporal_role: str = "reference_metadata") -> Tuple[Dict[str, Any], Optional[Any], List[Dict[str, Any]]]:
    payload, meta, content = request_payload(url, timeout, retries, backoff, user_agent)
    http = meta.get("http_status")
    if payload is not None and http == 200:
        write_json(output_json, payload)
        rows = payload.get("_xml_rows") if isinstance(payload, dict) and "_xml_rows" in payload else flatten_dicts(payload)
        rows = rows or []
        write_csv(output_csv, rows)
        norm = normalise_rows(rows)
        write_json(chart_json, norm)
        return make_source_record(
            repo, title=title, url=url, status="ok", http_status=http, output_path=output_json,
            chart_safe_path=chart_json, record_count=len(rows), sha256=meta.get("sha256"),
            notes=notes, temporal_role=temporal_role
        ), payload, norm
    failed = {
        "url": url,
        "meta": meta,
        "content_preview": (content[:500].decode("utf-8", errors="replace") if content else ""),
    }
    failed_path = output_json.with_suffix(".failed.json")
    write_json(failed_path, failed)
    return make_source_record(
        repo, title=title, url=url, status="warning", http_status=http, output_path=failed_path,
        record_count=0, sha256=meta.get("sha256"), notes=notes, temporal_role=temporal_role,
        error=meta.get("error") or "request_failed_or_unparseable"
    ), payload, []


def find_first_key(row: Dict[str, Any], candidates: Iterable[str]) -> Optional[str]:
    lower = {str(k).lower(): k for k in row.keys()}
    for c in candidates:
        k = lower.get(c.lower())
        if k is not None and row.get(k) not in (None, ""):
            return str(row.get(k))
    return None


def select_site_species(rows: List[Dict[str, Any]]) -> Tuple[str, str]:
    for row in rows:
        site = find_first_key(row, ["site_code", "sitecode", "SiteCode", "@SiteCode"])
        species = find_first_key(row, ["species_code", "speciescode", "SpeciesCode", "@SpeciesCode"])
        if site and species:
            return site, species
    return "", ""


def date_variants(iso_date: str, formats: List[str]) -> List[str]:
    d = dt.date.fromisoformat(iso_date)
    variants = [d.strftime(fmt) for fmt in formats]
    variants.extend([d.strftime("%d%b%Y"), d.strftime("%d %b %Y"), d.isoformat()])
    out, seen = [], set()
    for v in variants:
        if v not in seen:
            seen.add(v)
            out.append(v)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--config", default="configs/aq26_laqn.yml")
    ap.add_argument("--base-url", default="")
    ap.add_argument("--group-name", default="")
    ap.add_argument("--timeout", type=int, default=0)
    ap.add_argument("--retries", type=int, default=0)
    ap.add_argument("--backoff", type=int, default=0)
    ap.add_argument("--user-agent", default=os.getenv("AQ26_USER_AGENT", "AQ26/3.5 LAQN provider probe"))
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
    out_root = repo / (outputs_cfg.get("root") or "outputs/31_laqn")
    site_root = repo / (outputs_cfg.get("site_root") or "site_public/data/providers/laqn")
    chart_root = site_root / "chart_safe"
    date_fmts = list(probe_cfg.get("date_formats") or ["%d%b%Y", "%d %b %Y"])

    mkdir(out_root); mkdir(site_root); mkdir(chart_root)
    records: List[Dict[str, Any]] = []
    chart_payload: Dict[str, Any] = {"provider": "laqn", "group_name": group_name, "tables": {}}
    site_species_rows: List[Dict[str, Any]] = []

    endpoint_specs = [
        ("LAQN pollutant species metadata", "/Information/Species/Json", "species", "Commonly monitored pollutant/species codes and health-effect metadata."),
        ("LAQN groups metadata", "/Information/Groups/Json", "groups", "Monitoring network groups available for other calls. Empty WebsiteURL values are valid and are not broken AQ26 links."),
        (f"LAQN monitoring sites for {group_name}", f"/Information/MonitoringSites/GroupName={safe_component(group_name)}/Json", f"sites_{group_name.lower()}", "Monitoring site metadata for selected group."),
        (f"LAQN monitoring site/species for {group_name}", f"/Information/MonitoringSiteSpecies/GroupName={safe_component(group_name)}/Json", f"site_species_{group_name.lower()}", "Site/species capability metadata for selected group."),
        (f"LAQN annual monitoring objectives for {group_name}", f"/Annual/MonitoringObjective/GroupName={safe_component(group_name)}", f"annual_objectives_{group_name.lower()}", "Annual air-quality objectives endpoint. This is XML, not JSON."),
        ("LAQN index health advice", "/Information/IndexHealthAdvice/Json", "index_health_advice", "Health-advice metadata; context only, not AQ26 health-impact attribution."),
    ]

    for title, path, stem, notes in endpoint_specs:
        rec, payload, norm = fetch_endpoint(
            repo, title, endpoint_url(base_url, path), site_root / f"{stem}.json",
            out_root / f"{stem}_rows.csv", chart_root / f"{stem}.json",
            timeout, retries, backoff, args.user_agent, notes
        )
        records.append(rec)
        chart_payload["tables"][stem] = {"rows": len(norm), "path": repo_relative(repo, chart_root / f"{stem}.json"), "status": rec["status"]}
        if stem.startswith("site_species"):
            site_species_rows = norm

    run_data_probe = bool(args.run_data_probe or os.getenv("AQ26_LAQN_RUN_DATA_PROBE", "").lower() in ("1", "true", "yes"))
    if run_data_probe:
        site_code = args.site_code or str(probe_cfg.get("site_code") or "")
        species_code = args.species_code or str(probe_cfg.get("species_code") or "")
        if not site_code or not species_code:
            auto_site, auto_species = select_site_species(site_species_rows)
            site_code = site_code or auto_site
            species_code = species_code or auto_species
        start_date = args.start_date or probe_cfg.get("start_date") or "2024-07-22"
        end_date = args.end_date or probe_cfg.get("end_date") or "2024-07-23"
        if not site_code or not species_code:
            records.append(make_source_record(
                repo, title="LAQN tiny SiteSpecies historical data probe", url=base_url, status="warning",
                http_status=None, record_count=0, notes="Data probe requested but no site/species pair could be selected.",
                error="missing_site_or_species_code", temporal_role="historical_observation",
                observed_start=start_date, observed_end=end_date
            ))
        else:
            success = False
            failures: List[Dict[str, Any]] = []
            for sd in date_variants(start_date, date_fmts):
                for ed in date_variants(end_date, date_fmts):
                    stem = f"data_probe_{site_code}_{species_code}_{start_date}_{end_date}".replace("/", "_")
                    data_path = f"/Data/SiteSpecies/SiteCode={safe_component(site_code)}/SpeciesCode={safe_component(species_code)}/StartDate={safe_component(sd)}/EndDate={safe_component(ed)}/Json"
                    rec, payload, norm = fetch_endpoint(
                        repo, f"LAQN tiny historical data probe {site_code}/{species_code} {start_date} to {end_date}",
                        endpoint_url(base_url, data_path), out_root / f"{stem}.json", out_root / f"{stem}.csv",
                        chart_root / f"{stem}.json", timeout, retries, backoff, args.user_agent,
                        "Tiny one-site/one-species data probe. Use only to confirm API structure before bulk harvesting.",
                        "historical_observation"
                    )
                    rec["observed_start"] = start_date; rec["observed_end"] = end_date
                    rec["site_code"] = site_code; rec["species_code"] = species_code
                    if rec["status"] == "ok" and int(rec.get("record_count") or 0) > 0:
                        records.append(rec); success = True
                        chart_payload["tables"]["data_probe"] = {"rows": len(norm), "path": rec.get("chart_safe_path"), "status": "ok"}
                        break
                    failures.append(rec)
                if success:
                    break
            if not success:
                records.extend(failures[:3])

    ok_records = [r for r in records if r.get("status") == "ok"]
    warnings = [r for r in records if r.get("status") == "warning"]
    metadata_ready = any("species" in r.get("title", "").lower() and r.get("status") == "ok" for r in records) and any("monitoring sites" in r.get("title", "").lower() and r.get("status") == "ok" for r in records)
    data_ready = any(r.get("temporal_role") == "historical_observation" and r.get("status") == "ok" and int(r.get("record_count") or 0) > 0 for r in records)

    summary = {
        "provider": "laqn",
        "name": "London Air Quality Network / Imperial ERG AirQuality API",
        "base_url": base_url,
        "group_name": group_name,
        "retrieved_at_utc": iso_z(now_utc_dt()),
        "status": "ok" if metadata_ready else "warning",
        "records_total": len(records),
        "records_ok": len(ok_records),
        "records_warning": len(warnings),
        "metadata_ready": metadata_ready,
        "data_probe_requested": run_data_probe,
        "data_probe_ready": data_ready,
        "chart_safe_ready": True,
        "scientific_caveat": "LAQN is a validated London/urban comparator network. It is not Newhaven-specific evidence unless used explicitly as an urban/control comparator.",
        "source_records_path": "outputs/31_laqn/laqn_source_records.json",
        "chart_safe_index_path": "site_public/data/providers/laqn/chart_safe/index.json",
    }
    chart_payload["summary"] = summary

    write_json(out_root / "laqn_source_records.json", records)
    write_csv(out_root / "laqn_source_records.csv", records)
    write_json(site_root / "source_records.json", records)
    write_json(out_root / "laqn_summary.json", summary)
    write_json(site_root / "summary.json", summary)
    write_json(chart_root / "index.json", chart_payload)

    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
