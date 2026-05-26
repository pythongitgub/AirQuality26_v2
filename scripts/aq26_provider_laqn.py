#!/usr/bin/env python3
"""
AQ26 LAQN / Imperial ERG AirQuality API provider probe v3.6.

Drop-in replacement for: scripts/aq26_provider_laqn.py

What this fixes over v3.5
-------------------------
1. Builds a canonical flat site/species table from the nested LAQN MonitoringSiteSpecies
   payload.  The v3.5 auto-selector could fail because parent site rows and child species
   rows were separated.
2. Auto-selects a valid site/species pair from the flat table, preferring active London
   health-relevant pollutants and stable comparator sites.
3. Keeps the existing v3.5 behaviour: XML objective support, chart-safe exports,
   non-fatal health-advice warnings, repo-relative provenance, and data-probe readiness
   flags.
4. Writes extra debugging outputs so failures are diagnosable:
   - outputs/31_laqn/site_species_london_flat_rows.csv
   - site_public/data/providers/laqn/chart_safe/site_species_london_flat.json
   - outputs/31_laqn/laqn_probe_selection.json

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
import re
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
PRIORITY_SPECIES = ["NO2", "PM25", "PM10", "O3", "SO2", "CO"]
PREFERRED_SITE_ORDER = ["BL0", "MY1", "WM0", "KC1", "BX2", "CT3", "TD0", "HR1"]


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


def sha256_file(path: Path) -> Optional[str]:
    if not path.exists() or not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


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


def value_from(row: Dict[str, Any], candidates: Iterable[str], default: Any = "") -> Any:
    if not isinstance(row, dict):
        return default
    by_lower = {str(k).lower(): k for k in row.keys()}
    for cand in candidates:
        k = by_lower.get(str(cand).lower())
        if k is not None:
            v = row.get(k)
            if v not in (None, ""):
                return v
    return default


def listify(x: Any) -> List[Any]:
    if x is None:
        return []
    if isinstance(x, list):
        return x
    return [x]


def flatten_dicts(payload: Any) -> List[Dict[str, Any]]:
    """Generic fallback flattener used for CSV/debug outputs."""
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
        alias_pairs = {
            "sitecode": "site_code",
            "sitename": "site_name",
            "sitetype": "site_type",
            "speciescode": "species_code",
            "speciesdescription": "species_description",
            "groupname": "group_name",
            "websiteurl": "website_url",
            "datemeasurementstarted": "date_measurement_started",
            "datemeasurementfinished": "date_measurement_finished",
        }
        for src, dst in alias_pairs.items():
            if src in nr and dst not in nr:
                nr[dst] = nr[src]
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


def nested_lookup_any(obj: Any, key_names: Iterable[str]) -> List[Any]:
    """Return all values whose key matches any supplied name ignoring @ and case."""
    wanted = {str(k).lower().lstrip("@") for k in key_names}
    found: List[Any] = []

    def walk(x: Any) -> None:
        if isinstance(x, dict):
            for k, v in x.items():
                if str(k).lower().lstrip("@") in wanted:
                    found.append(v)
                if isinstance(v, (dict, list)):
                    walk(v)
        elif isinstance(x, list):
            for item in x:
                walk(item)

    walk(obj)
    return found


def species_items_from_site(site_node: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract species dictionaries from a site node, supporting several LAQN JSON shapes."""
    candidates: List[Any] = []
    for key in ["Species", "species", "SiteSpecies", "siteSpecies"]:
        if key in site_node:
            candidates.extend(listify(site_node[key]))

    # In LAQN JSON the site may contain {'Species': {'Species': [{...}, {...}]}}
    expanded: List[Any] = []
    for item in candidates:
        if isinstance(item, dict):
            inner_added = False
            for key in ["Species", "species", "SiteSpecies", "siteSpecies"]:
                if key in item:
                    expanded.extend(listify(item[key]))
                    inner_added = True
            if not inner_added:
                expanded.append(item)
        elif isinstance(item, list):
            expanded.extend(item)

    species_rows: List[Dict[str, Any]] = []
    for item in expanded:
        if isinstance(item, dict):
            code = value_from(item, ["@SpeciesCode", "SpeciesCode", "species_code", "speciescode"])
            if code:
                species_rows.append(item)
    return species_rows


def build_site_species_flat_from_payload(payload: Any, fallback_rows: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    """
    Build canonical flat rows: one row per site/species capability.

    This is intentionally separate from the generic flattening, because LAQN emits nested
    site rows where the site attributes live on the parent and species attributes live on
    children.  A flat table is needed for auto-selection and charts.
    """
    flat: List[Dict[str, Any]] = []

    def emit(site: Dict[str, Any], species: Dict[str, Any]) -> None:
        site_code = value_from(site, ["@SiteCode", "SiteCode", "site_code", "sitecode"])
        species_code = value_from(species, ["@SpeciesCode", "SpeciesCode", "species_code", "speciescode"])
        if not site_code or not species_code:
            return
        row: Dict[str, Any] = {
            "site_code": str(site_code),
            "site_name": value_from(site, ["@SiteName", "SiteName", "site_name", "sitename"]),
            "site_type": value_from(site, ["@SiteType", "SiteType", "site_type", "sitetype"]),
            "local_authority_code": value_from(site, ["@LocalAuthorityCode", "LocalAuthorityCode", "local_authority_code"]),
            "local_authority_name": value_from(site, ["@LocalAuthorityName", "LocalAuthorityName", "local_authority_name"]),
            "latitude": value_from(site, ["@Latitude", "Latitude", "lat"]),
            "longitude": value_from(site, ["@Longitude", "Longitude", "lon"]),
            "species_code": str(species_code),
            "species_description": value_from(species, ["@SpeciesDescription", "SpeciesDescription", "species_description", "speciesdescription"]),
            "measurement_started": value_from(species, ["@DateMeasurementStarted", "DateMeasurementStarted", "date_measurement_started", "datemeasurementstarted"]),
            "measurement_finished": value_from(species, ["@DateMeasurementFinished", "DateMeasurementFinished", "date_measurement_finished", "datemeasurementfinished"]),
            "units": value_from(species, ["@Units", "Units", "units"]),
        }
        try:
            row["lat"] = float(row["latitude"])
        except Exception:
            pass
        try:
            row["lon"] = float(row["longitude"])
        except Exception:
            pass
        row["is_current_or_unknown"] = is_current_measurement(row.get("measurement_finished"))
        flat.append(row)

    def walk(x: Any) -> None:
        if isinstance(x, dict):
            site_code = value_from(x, ["@SiteCode", "SiteCode", "site_code", "sitecode"])
            species_rows = species_items_from_site(x)
            if site_code and species_rows:
                for sp in species_rows:
                    emit(x, sp)
            for v in x.values():
                if isinstance(v, (dict, list)):
                    walk(v)
        elif isinstance(x, list):
            for item in x:
                walk(item)

    walk(payload)

    # Fallback for already-flattened/CSV-style rows: forward-fill parent site fields into
    # following child species rows.  This catches the exact v3.5 failure mode.
    if not flat and fallback_rows:
        current_site: Dict[str, Any] = {}
        for raw in fallback_rows:
            row = dict(raw)
            site_code = value_from(row, ["site_code", "sitecode", "SiteCode", "@SiteCode"])
            if site_code:
                current_site = {
                    "site_code": site_code,
                    "site_name": value_from(row, ["site_name", "sitename", "SiteName", "@SiteName"]),
                    "site_type": value_from(row, ["site_type", "sitetype", "SiteType", "@SiteType"]),
                    "local_authority_code": value_from(row, ["local_authority_code", "LocalAuthorityCode", "@LocalAuthorityCode"]),
                    "local_authority_name": value_from(row, ["local_authority_name", "LocalAuthorityName", "@LocalAuthorityName"]),
                    "latitude": value_from(row, ["latitude", "Latitude", "@Latitude"]),
                    "longitude": value_from(row, ["longitude", "Longitude", "@Longitude"]),
                }
            species_code = value_from(row, ["species_code", "speciescode", "SpeciesCode", "@SpeciesCode"])
            if species_code and current_site.get("site_code"):
                sp = {
                    "species_code": species_code,
                    "species_description": value_from(row, ["species_description", "speciesdescription", "SpeciesDescription", "@SpeciesDescription"]),
                    "measurement_started": value_from(row, ["date_measurement_started", "datemeasurementstarted", "DateMeasurementStarted", "@DateMeasurementStarted"]),
                    "measurement_finished": value_from(row, ["date_measurement_finished", "datemeasurementfinished", "DateMeasurementFinished", "@DateMeasurementFinished"]),
                    "units": value_from(row, ["units", "Units", "@Units"]),
                }
                emit(current_site, sp)

    # Deduplicate while preserving order.
    dedup: List[Dict[str, Any]] = []
    seen = set()
    for row in flat:
        key = (str(row.get("site_code", "")), str(row.get("species_code", "")), str(row.get("measurement_started", "")), str(row.get("measurement_finished", "")))
        if key not in seen:
            seen.add(key)
            dedup.append(row)
    return dedup


def parse_date_loose(value: Any) -> Optional[dt.date]:
    if value in (None, ""):
        return None
    s = str(value).strip()
    if not s:
        return None
    # Common LAQN formats include dd/mm/yyyy, yyyy-mm-dd, and dd Mon yyyy.
    for fmt in ["%d/%m/%Y", "%Y-%m-%d", "%d%b%Y", "%d %b %Y", "%d-%m-%Y", "%Y/%m/%d"]:
        try:
            return dt.datetime.strptime(s, fmt).date()
        except Exception:
            pass
    try:
        return dt.date.fromisoformat(s[:10])
    except Exception:
        return None


def is_current_measurement(measurement_finished: Any) -> bool:
    d = parse_date_loose(measurement_finished)
    if d is None:
        return True
    return d >= dt.date.today()


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
    for optional in ["site_code", "species_code"]:
        if optional in kw:
            rec[optional] = kw.get(optional)
    return rec


def fetch_endpoint(repo: Path, title: str, url: str, output_json: Path, output_csv: Path, chart_json: Path,
                   timeout: int, retries: int, backoff: int, user_agent: str,
                   notes: str, temporal_role: str = "reference_metadata") -> Tuple[Dict[str, Any], Optional[Any], List[Dict[str, Any]], List[Dict[str, Any]]]:
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
        ), payload, norm, rows
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
    ), payload, [], []


def find_first_key(row: Dict[str, Any], candidates: Iterable[str]) -> Optional[str]:
    v = value_from(row, candidates)
    return str(v) if v not in (None, "") else None


def select_site_species(flat_rows: List[Dict[str, Any]], requested_start: Optional[str] = None) -> Tuple[str, str, Dict[str, Any]]:
    """Select a deterministic, explainable data-probe pair from canonical flat rows."""
    if not flat_rows:
        return "", "", {"reason": "empty_flat_site_species"}

    start_d = parse_date_loose(requested_start) if requested_start else None
    scored: List[Tuple[int, Dict[str, Any]]] = []
    for row in flat_rows:
        site = str(row.get("site_code") or "").strip()
        species = str(row.get("species_code") or "").strip().upper()
        if not site or not species:
            continue
        score = 0
        if species in PRIORITY_SPECIES:
            score += 100 - PRIORITY_SPECIES.index(species) * 5
        if row.get("is_current_or_unknown"):
            score += 40
        if site in PREFERRED_SITE_ORDER:
            score += 30 - PREFERRED_SITE_ORDER.index(site)
        site_type = str(row.get("site_type") or "").lower()
        if "background" in site_type:
            score += 8
        if "roadside" in site_type:
            score += 4
        # Prefer rows whose measurement period covers the requested start date.
        if start_d:
            started = parse_date_loose(row.get("measurement_started"))
            finished = parse_date_loose(row.get("measurement_finished"))
            if started is None or started <= start_d:
                score += 5
            if finished is None or finished >= start_d:
                score += 10
        scored.append((score, row))

    if not scored:
        return "", "", {"reason": "no_rows_with_site_and_species", "flat_rows": len(flat_rows)}
    scored.sort(key=lambda x: x[0], reverse=True)
    chosen = dict(scored[0][1])
    chosen["selection_score"] = scored[0][0]
    chosen["reason"] = "auto_selected_from_flat_site_species"
    return str(chosen.get("site_code", "")), str(chosen.get("species_code", "")), chosen


def date_variants(iso_date: str, formats: List[str]) -> List[str]:
    d = dt.date.fromisoformat(iso_date)
    variants = [d.strftime(fmt) for fmt in formats]
    variants.extend([d.strftime("%d%b%Y"), d.strftime("%d %b %Y"), d.isoformat(), d.strftime("%d/%m/%Y")])
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
    ap.add_argument("--user-agent", default=os.getenv("AQ26_USER_AGENT", "AQ26/3.6 LAQN provider probe"))
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

    mkdir(out_root)
    mkdir(site_root)
    mkdir(chart_root)
    records: List[Dict[str, Any]] = []
    chart_payload: Dict[str, Any] = {"provider": "laqn", "group_name": group_name, "tables": {}}
    site_species_payload: Optional[Any] = None
    site_species_norm_rows: List[Dict[str, Any]] = []
    site_species_raw_rows: List[Dict[str, Any]] = []

    endpoint_specs = [
        ("LAQN pollutant species metadata", "/Information/Species/Json", "species", "Commonly monitored pollutant/species codes and health-effect metadata."),
        ("LAQN groups metadata", "/Information/Groups/Json", "groups", "Monitoring network groups available for other calls. Empty WebsiteURL values are valid and are not broken AQ26 links."),
        (f"LAQN monitoring sites for {group_name}", f"/Information/MonitoringSites/GroupName={safe_component(group_name)}/Json", f"sites_{group_name.lower()}", "Monitoring site metadata for selected group."),
        (f"LAQN monitoring site/species for {group_name}", f"/Information/MonitoringSiteSpecies/GroupName={safe_component(group_name)}/Json", f"site_species_{group_name.lower()}", "Site/species capability metadata for selected group."),
        (f"LAQN annual monitoring objectives for {group_name}", f"/Annual/MonitoringObjective/GroupName={safe_component(group_name)}", f"annual_objectives_{group_name.lower()}", "Annual air-quality objectives endpoint. This is XML, not JSON."),
        ("LAQN index health advice", "/Information/IndexHealthAdvice/Json", "index_health_advice", "Health-advice metadata; context only, not AQ26 health-impact attribution."),
    ]

    for title, path, stem, notes in endpoint_specs:
        rec, payload, norm, raw_rows = fetch_endpoint(
            repo,
            title,
            endpoint_url(base_url, path),
            site_root / f"{stem}.json",
            out_root / f"{stem}_rows.csv",
            chart_root / f"{stem}.json",
            timeout,
            retries,
            backoff,
            args.user_agent,
            notes,
        )
        records.append(rec)
        chart_payload["tables"][stem] = {"rows": len(norm), "path": repo_relative(repo, chart_root / f"{stem}.json"), "status": rec["status"]}
        if stem.startswith("site_species"):
            site_species_payload = payload
            site_species_norm_rows = norm
            site_species_raw_rows = raw_rows

    # Build canonical flat site/species table and make it public/chart-safe.
    flat_stem = f"site_species_{group_name.lower()}_flat"
    flat_rows = build_site_species_flat_from_payload(site_species_payload, site_species_norm_rows or site_species_raw_rows)
    flat_csv = out_root / f"{flat_stem}_rows.csv"
    flat_json = chart_root / f"{flat_stem}.json"
    write_csv(flat_csv, flat_rows)
    write_json(flat_json, flat_rows)
    flat_rec = make_source_record(
        repo,
        title=f"LAQN canonical flat monitoring site/species for {group_name}",
        url=endpoint_url(base_url, f"/Information/MonitoringSiteSpecies/GroupName={safe_component(group_name)}/Json"),
        status="ok" if flat_rows else "warning",
        http_status=200 if flat_rows else None,
        output_path=flat_csv,
        chart_safe_path=flat_json,
        record_count=len(flat_rows),
        sha256=sha256_file(flat_csv),
        notes="Canonical one-row-per-site/species table used for charts and automatic data-probe selection.",
        temporal_role="reference_metadata",
        error=None if flat_rows else "site_species_flat_empty",
    )
    records.append(flat_rec)
    chart_payload["tables"][flat_stem] = {"rows": len(flat_rows), "path": repo_relative(repo, flat_json), "status": flat_rec["status"]}

    run_data_probe = bool(args.run_data_probe or os.getenv("AQ26_LAQN_RUN_DATA_PROBE", "").lower() in ("1", "true", "yes"))
    probe_selection: Dict[str, Any] = {
        "run_data_probe": run_data_probe,
        "flat_site_species_rows": len(flat_rows),
        "requested_site_code": args.site_code or str(probe_cfg.get("site_code") or ""),
        "requested_species_code": args.species_code or str(probe_cfg.get("species_code") or ""),
    }

    if run_data_probe:
        site_code = args.site_code or str(probe_cfg.get("site_code") or "")
        species_code = args.species_code or str(probe_cfg.get("species_code") or "")
        start_date = args.start_date or probe_cfg.get("start_date") or "2024-07-22"
        end_date = args.end_date or probe_cfg.get("end_date") or "2024-07-23"

        if not site_code or not species_code:
            auto_site, auto_species, chosen = select_site_species(flat_rows, requested_start=start_date)
            site_code = site_code or auto_site
            species_code = species_code or auto_species
            probe_selection["auto_selected"] = chosen
        else:
            probe_selection["auto_selected"] = None
            probe_selection["manual_pair_used"] = {"site_code": site_code, "species_code": species_code}

        probe_selection.update({"final_site_code": site_code, "final_species_code": species_code, "start_date": start_date, "end_date": end_date})
        write_json(out_root / "laqn_probe_selection.json", probe_selection)

        if not site_code or not species_code:
            records.append(make_source_record(
                repo,
                title="LAQN tiny SiteSpecies historical data probe",
                url=base_url,
                status="warning",
                http_status=None,
                record_count=0,
                notes="Data probe requested but no site/species pair could be selected from the canonical flat table.",
                error="missing_site_or_species_code",
                temporal_role="historical_observation",
                observed_start=start_date,
                observed_end=end_date,
            ))
        else:
            success = False
            failures: List[Dict[str, Any]] = []
            for sd in date_variants(start_date, date_fmts):
                for ed in date_variants(end_date, date_fmts):
                    stem = f"data_probe_{site_code}_{species_code}_{start_date}_{end_date}".replace("/", "_").replace(" ", "_")
                    data_path = f"/Data/SiteSpecies/SiteCode={safe_component(site_code)}/SpeciesCode={safe_component(species_code)}/StartDate={safe_component(sd)}/EndDate={safe_component(ed)}/Json"
                    rec, payload, norm, raw_rows = fetch_endpoint(
                        repo,
                        f"LAQN tiny historical data probe {site_code}/{species_code} {start_date} to {end_date}",
                        endpoint_url(base_url, data_path),
                        out_root / f"{stem}.json",
                        out_root / f"{stem}.csv",
                        chart_root / f"{stem}.json",
                        timeout,
                        retries,
                        backoff,
                        args.user_agent,
                        "Tiny one-site/one-species data probe. Use only to confirm API structure before bulk harvesting.",
                        "historical_observation",
                    )
                    rec["observed_start"] = start_date
                    rec["observed_end"] = end_date
                    rec["site_code"] = site_code
                    rec["species_code"] = species_code
                    rec["date_format_attempt_start"] = sd
                    rec["date_format_attempt_end"] = ed
                    if rec["status"] == "ok" and int(rec.get("record_count") or 0) > 0:
                        records.append(rec)
                        success = True
                        chart_payload["tables"]["data_probe"] = {"rows": len(norm), "path": rec.get("chart_safe_path"), "status": "ok"}
                        break
                    failures.append(rec)
                if success:
                    break
            if not success:
                # Keep first few failures for diagnosis without flooding source_records.
                records.extend(failures[:5])

    else:
        write_json(out_root / "laqn_probe_selection.json", probe_selection)

    ok_records = [r for r in records if r.get("status") == "ok"]
    warnings = [r for r in records if r.get("status") == "warning"]
    metadata_ready = any("species" in r.get("title", "").lower() and r.get("status") == "ok" for r in records) and any("monitoring sites" in r.get("title", "").lower() and r.get("status") == "ok" for r in records)
    flat_ready = len(flat_rows) > 0
    data_ready = any(r.get("temporal_role") == "historical_observation" and r.get("status") == "ok" and int(r.get("record_count") or 0) > 0 for r in records)

    summary = {
        "provider": "laqn",
        "provider_version": "v3.6_fixed_site_species_selection",
        "name": "London Air Quality Network / Imperial ERG AirQuality API",
        "base_url": base_url,
        "group_name": group_name,
        "retrieved_at_utc": iso_z(now_utc_dt()),
        "status": "ok" if metadata_ready else "warning",
        "records_total": len(records),
        "records_ok": len(ok_records),
        "records_warning": len(warnings),
        "metadata_ready": metadata_ready,
        "site_species_flat_ready": flat_ready,
        "site_species_flat_rows": len(flat_rows),
        "data_probe_requested": run_data_probe,
        "data_probe_ready": data_ready,
        "chart_safe_ready": True,
        "scientific_caveat": "LAQN is a validated London/urban comparator network. It is not Newhaven-specific evidence unless used explicitly as an urban/control comparator.",
        "source_records_path": "outputs/31_laqn/laqn_source_records.json",
        "chart_safe_index_path": "site_public/data/providers/laqn/chart_safe/index.json",
        "flat_site_species_path": repo_relative(repo, flat_json),
        "probe_selection_path": "outputs/31_laqn/laqn_probe_selection.json",
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
