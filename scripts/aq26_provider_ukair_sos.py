#!/usr/bin/env python3
"""
AQ26 UK-AIR SOS provider verifier and inventory builder (V3.4).

Verified from first AQ26 run:
- The endpoint https://uk-air.defra.gov.uk/sos-ukair/sos responded HTTP 200
  to GetCapabilities with application/xml and a large official capabilities document.
- The previous parser under-counted observed properties because the capabilities
  use `observableProperty` in offerings, not only `observedProperty`.

This version:
- Prefers the verified /sos endpoint before trying legacy guesses.
- Parses offerings, procedures, observableProperty values and response formats.
- Produces compact site JSON inventories rather than requiring the raw 12 MB XML
  to be committed to the repo.
- Compresses the raw XML for artifact/provenance.
- Adds temporal/source-confidence fields for scientific audit.
- Supports a dry observation probe scaffold but does not fabricate observations.
"""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import gzip
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urlencode

import requests
import xml.etree.ElementTree as ET


VERIFIED_CAPABILITIES_URLS = [
    "https://uk-air.defra.gov.uk/sos-ukair/sos",
    # Retained as fallbacks only; first run showed /api/v1/sos/kvp returns 404.
    "https://uk-air.defra.gov.uk/sos-ukair/api/v1/sos/kvp",
    "https://uk-air.defra.gov.uk/sos-ukair/api/v1/sos",
]

POLLUTANT_CODE_HINTS = {
    "1": "SO2",
    "5": "PM10",
    "7": "O3",
    "8": "NO2",
    "9": "NOx",
    "10": "CO",
    "20": "Benzene",
    "38": "PM2.5",
    "6001": "AQI_or_summary_indicator",
}

SECRET_PATTERNS = [
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"(?i)(api[_-]?key|secret|password|token)\s*[:=]\s*['\"][^'\"]{8,}['\"]"),
    re.compile(r"(?i)bearer\s+[a-z0-9._~+/=-]{16,}"),
]


def now_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def mkdir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, payload: Any) -> None:
    mkdir(path.parent)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def read_json_if_exists(path: Path, default: Any) -> Any:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return default


def strip_ns(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def xml_text(el: ET.Element) -> str:
    return "".join(el.itertext()).strip()


def iter_by_localname(root: ET.Element, localname: str) -> Iterable[ET.Element]:
    for el in root.iter():
        if strip_ns(el.tag) == localname:
            yield el


def uri_last(uri: str) -> str:
    return (uri or "").rstrip("/").rsplit("/", 1)[-1]


def pollutant_hint(uri: str) -> Dict[str, Optional[str]]:
    code = uri_last(uri)
    return {"pollutant_code": code, "pollutant_hint": POLLUTANT_CODE_HINTS.get(code)}


def station_process_id(uri: str) -> str:
    m = re.search(r"GB_StationProcess_([^/]+)$", uri or "")
    return m.group(1) if m else uri_last(uri)


def offering_id(uri: str) -> str:
    m = re.search(r"GB_Offering_([^/]+)$", uri or "")
    return m.group(1) if m else uri_last(uri)


def redact_check_files(paths: List[Path]) -> List[Dict[str, str]]:
    issues = []
    for p in paths:
        if not p.exists() or p.is_dir():
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for rx in SECRET_PATTERNS:
            if rx.search(text):
                issues.append({"path": str(p), "pattern": rx.pattern})
    return issues


def request_get(url: str, params: Dict[str, str], timeout: int, retries: int, backoff: int, user_agent: str) -> requests.Response:
    headers = {"User-Agent": user_agent, "Accept": "application/xml,text/xml,application/json,*/*"}
    last_exc = None
    for attempt in range(1, retries + 1):
        try:
            return requests.get(url, params=params, headers=headers, timeout=timeout)
        except Exception as exc:
            last_exc = exc
            if attempt < retries:
                time.sleep(backoff * attempt)
    raise RuntimeError(f"request failed after {retries} attempts: {last_exc}")


def probe_capabilities(base_urls: List[str], timeout: int, retries: int, backoff: int, user_agent: str) -> Tuple[Optional[requests.Response], List[Dict[str, Any]]]:
    params_variants = [
        {"service": "SOS", "request": "GetCapabilities", "AcceptVersions": "2.0.0"},
        {"service": "SOS", "request": "GetCapabilities", "version": "2.0.0"},
        {"service": "SOS", "request": "GetCapabilities"},
    ]

    attempts: List[Dict[str, Any]] = []
    seen = set()
    for base_url in base_urls:
        if not base_url:
            continue
        for params in params_variants:
            key = (base_url, tuple(sorted(params.items())))
            if key in seen:
                continue
            seen.add(key)
            try:
                r = request_get(base_url, params, timeout, retries, backoff, user_agent)
                content = r.content or b""
                text_start = content[:200].lstrip().decode("utf-8", "ignore").lower()
                looks_xml = text_start.startswith("<")
                attempts.append({
                    "url": r.url,
                    "http_status": r.status_code,
                    "content_type": r.headers.get("content-type", ""),
                    "bytes": len(content),
                    "looks_xml": looks_xml,
                    "sha256": sha256_bytes(content),
                })
                # Avoid accepting small 404 HTML/XML-like error pages.
                if r.status_code == 200 and looks_xml and len(content) > 10000:
                    return r, attempts
            except Exception as exc:
                attempts.append({"url": base_url, "params": params, "http_status": None, "error": repr(exc)})
    return None, attempts


def parse_operation_urls(root: ET.Element) -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {}
    for op in iter_by_localname(root, "Operation"):
        op_name = op.attrib.get("name")
        if not op_name:
            continue
        urls = set()
        for el in op.iter():
            if strip_ns(el.tag) in {"Get", "Post"}:
                for k, v in el.attrib.items():
                    if strip_ns(k) == "href" and v:
                        urls.add(v)
        out[op_name] = sorted(urls)
    return out


def parse_capabilities_xml(xml_bytes: bytes, *, max_offerings_site: int = 500) -> Dict[str, Any]:
    root = ET.fromstring(xml_bytes)

    operations = sorted({op.attrib.get("name") for op in iter_by_localname(root, "Operation") if op.attrib.get("name")})
    operation_urls = parse_operation_urls(root)

    offerings: List[Dict[str, Any]] = []
    observable_counter: collections.Counter[str] = collections.Counter()
    procedure_counter: collections.Counter[str] = collections.Counter()
    response_counter: collections.Counter[str] = collections.Counter()

    for off in iter_by_localname(root, "ObservationOffering"):
        rec: Dict[str, Any] = {
            "identifier": None,
            "offering_id": None,
            "name": None,
            "procedures": [],
            "station_process_ids": [],
            "observable_properties": [],
            "pollutants": [],
            "response_formats": [],
            "observation_types": [],
        }
        for child in off.iter():
            lname = strip_ns(child.tag)
            txt = xml_text(child)
            if not txt:
                continue
            if lname == "identifier" and not rec["identifier"]:
                rec["identifier"] = txt
                rec["offering_id"] = offering_id(txt)
            elif lname == "name" and not rec["name"]:
                rec["name"] = txt
            elif lname == "procedure":
                rec["procedures"].append(txt)
                rec["station_process_ids"].append(station_process_id(txt))
                procedure_counter[txt] += 1
            elif lname in ("observableProperty", "observedProperty"):
                rec["observable_properties"].append(txt)
                hint = pollutant_hint(txt)
                rec["pollutants"].append({"uri": txt, **hint})
                observable_counter[txt] += 1
            elif lname == "responseFormat":
                rec["response_formats"].append(txt)
                response_counter[txt] += 1
            elif lname == "observationType":
                rec["observation_types"].append(txt)

        # Deduplicate preserving order.
        for key in ["procedures", "station_process_ids", "observable_properties", "response_formats", "observation_types"]:
            seen = set()
            rec[key] = [x for x in rec[key] if not (x in seen or seen.add(x))]
        seen_poll = set()
        rec["pollutants"] = [p for p in rec["pollutants"] if not ((p["uri"], p.get("pollutant_code")) in seen_poll or seen_poll.add((p["uri"], p.get("pollutant_code"))))]
        offerings.append(rec)

    observable_properties = [
        {"uri": uri, "count": count, **pollutant_hint(uri)}
        for uri, count in observable_counter.most_common()
    ]
    procedures = [
        {"uri": uri, "station_process_id": station_process_id(uri), "count": count}
        for uri, count in procedure_counter.most_common()
    ]
    response_formats = [{"format": fmt, "count": count} for fmt, count in response_counter.most_common()]

    service_identification: Dict[str, Any] = {}
    for el in iter_by_localname(root, "ServiceIdentification"):
        for child in el:
            service_identification[strip_ns(child.tag)] = xml_text(child)

    counts = {
        "operations": len(operations),
        "offerings": len(offerings),
        "procedures_unique": len(procedure_counter),
        "observable_properties_unique": len(observable_counter),
        "observable_property_links": sum(observable_counter.values()),
        "response_formats_unique": len(response_counter),
    }

    return {
        "root_tag": strip_ns(root.tag),
        "service_identification": service_identification,
        "operations": operations,
        "operation_urls": operation_urls,
        "counts": counts,
        "observable_properties": observable_properties,
        "procedures": procedures,
        "response_formats": response_formats,
        "offerings_sample": offerings[:max_offerings_site],
        "offerings_full": offerings,
    }


def compact_capabilities(parsed: Dict[str, Any]) -> Dict[str, Any]:
    c = dict(parsed)
    c.pop("offerings_full", None)
    return c


def source_record(
    *,
    status: str,
    title: str,
    url: str,
    output_path: Optional[str],
    http_status: Optional[int],
    record_count: int,
    notes: str,
    sha256: Optional[str] = None,
    error: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    ts = now_utc()
    rec = {
        "source_type": "ukair_sos",
        "source_class": "official_ground_air",
        "provider": "Defra UK-AIR Sensor Observation Service",
        "title": title,
        "status": status,
        "http_status": http_status,
        "url": url,
        "retrieved_at_utc": ts,
        "retrieved_at_uk": ts,
        "date_uk": ts[:10],
        "temporal_role": "historical_observation_provider_capability",
        "source_confidence": "official_regulatory_machine_readable",
        "provenance_level": "official_machine_readable",
        "record_count": record_count,
        "output_path": output_path,
        "sha256": sha256,
        "notes": notes,
        "error": error,
        "observed_start": None,
        "observed_end": None,
        "published_at": None,
        "current_context_only": False,
    }
    if extra:
        rec.update(extra)
    return rec


def build_observation_probe_urls(cap_url: str, offerings: List[Dict[str, Any]], start_date: str, end_date: str, limit: int) -> List[Dict[str, Any]]:
    base = cap_url.split("?", 1)[0]
    probes = []
    for off in offerings[:max(0, limit)]:
        off_id = off.get("identifier")
        props = off.get("observable_properties") or []
        if not off_id or not props:
            continue
        params = {
            "service": "SOS",
            "version": "2.0.0",
            "request": "GetObservation",
            "offering": off_id,
            "observedProperty": props[0],
            "temporalFilter": f"om:phenomenonTime,{start_date}T00:00:00Z/{end_date}T00:00:00Z",
            "responseFormat": "application/json",
        }
        probes.append({"offering": off_id, "observedProperty": props[0], "url": base + "?" + urlencode(params)})
    return probes


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--repo-root", default=".")
    p.add_argument("--capabilities-url", default=os.getenv("AQ26_UKAIR_SOS_CAPABILITIES_URL", "https://uk-air.defra.gov.uk/sos-ukair/sos"))
    p.add_argument("--out-root", default="outputs/30_ukair_sos")
    p.add_argument("--site-root", default="site_public/data/providers/ukair_sos")
    p.add_argument("--timeout", type=int, default=int(os.getenv("AQ26_UKAIR_SOS_TIMEOUT", "60")))
    p.add_argument("--retries", type=int, default=int(os.getenv("AQ26_UKAIR_SOS_RETRIES", "3")))
    p.add_argument("--backoff", type=int, default=int(os.getenv("AQ26_UKAIR_SOS_BACKOFF", "8")))
    p.add_argument("--user-agent", default=os.getenv("AQ26_USER_AGENT", "AQ26/3.4 ukair-sos scientific-backfill"))
    p.add_argument("--max-offerings-site", type=int, default=int(os.getenv("AQ26_UKAIR_SOS_MAX_OFFERINGS_SITE", "500")))
    p.add_argument("--observation-probe-start", default=os.getenv("AQ26_UKAIR_OBS_PROBE_START", "2024-07-22"))
    p.add_argument("--observation-probe-end", default=os.getenv("AQ26_UKAIR_OBS_PROBE_END", "2024-07-23"))
    p.add_argument("--observation-probe-limit", type=int, default=int(os.getenv("AQ26_UKAIR_OBS_PROBE_LIMIT", "0")))
    args = p.parse_args()

    repo = Path(args.repo_root).resolve()
    out_root = repo / args.out_root
    site_root = repo / args.site_root
    mkdir(out_root)
    mkdir(site_root)

    urls = [args.capabilities_url] + [u for u in VERIFIED_CAPABILITIES_URLS if u != args.capabilities_url]
    r, attempts = probe_capabilities(urls, args.timeout, args.retries, args.backoff, args.user_agent)
    write_json(out_root / "ukair_sos_probe_attempts.json", attempts)
    write_json(site_root / "probe_attempts.json", attempts)

    records: List[Dict[str, Any]] = []

    if r is None:
        rec = source_record(
            status="warning",
            title="UK-AIR SOS GetCapabilities probe",
            url=args.capabilities_url,
            output_path=str(out_root / "ukair_sos_probe_attempts.json"),
            http_status=None,
            record_count=0,
            notes="No working UK-AIR SOS GetCapabilities endpoint was confirmed.",
            error="capabilities_probe_failed",
        )
        records.append(rec)
        write_json(out_root / "ukair_sos_source_records.json", records)
        write_json(site_root / "source_records.json", records)
        print(json.dumps({"ok": False, "records": records, "attempts": attempts}, indent=2))
        return 0

    content = r.content or b""
    raw_hash = sha256_bytes(content)

    # Store raw XML compressed for provenance, but do not require committing a huge raw XML file.
    raw_gz = out_root / "ukair_sos_capabilities.xml.gz"
    with gzip.open(raw_gz, "wb") as f:
        f.write(content)

    try:
        parsed = parse_capabilities_xml(content, max_offerings_site=args.max_offerings_site)
        parsed["retrieved_at_utc"] = now_utc()
        parsed["source_url"] = r.url
        parsed["raw_sha256"] = raw_hash
        parsed["raw_gzip_path"] = str(raw_gz)
        parsed["parser_version"] = "AQ26_UKAIR_SOS_V3_4"

        compact = compact_capabilities(parsed)
        write_json(out_root / "ukair_sos_capabilities_parsed.json", compact)
        write_json(site_root / "capabilities.json", compact)

        offerings_full = parsed["offerings_full"]
        write_json(out_root / "ukair_sos_offerings_full.json", offerings_full)
        write_json(site_root / "offering_inventory.json", {
            "provider": "ukair_sos",
            "retrieved_at_utc": parsed["retrieved_at_utc"],
            "source_url": r.url,
            "count_total": len(offerings_full),
            "count_in_site_sample": len(parsed.get("offerings_sample", [])),
            "sample": parsed.get("offerings_sample", []),
        })

        write_json(site_root / "pollutant_inventory.json", {
            "provider": "ukair_sos",
            "observed_properties": parsed.get("observable_properties", []),
            "count": len(parsed.get("observable_properties", [])),
            "source_url": r.url,
            "retrieved_at_utc": parsed["retrieved_at_utc"],
        })

        write_json(site_root / "station_inventory.json", {
            "provider": "ukair_sos",
            "procedures": parsed.get("procedures", []),
            "counts": {
                "procedures_unique": parsed["counts"]["procedures_unique"],
                "offerings": parsed["counts"]["offerings"],
            },
            "source_url": r.url,
            "retrieved_at_utc": parsed["retrieved_at_utc"],
        })

        observation_probe_urls = build_observation_probe_urls(
            r.url, offerings_full, args.observation_probe_start, args.observation_probe_end, args.observation_probe_limit
        )
        write_json(out_root / "ukair_sos_observation_probe_urls.json", observation_probe_urls)
        write_json(site_root / "observation_probe_urls.json", observation_probe_urls)

        provider_summary = {
            "provider": "ukair_sos",
            "status": "verified_capabilities_ready",
            "source_url": r.url,
            "retrieved_at_utc": parsed["retrieved_at_utc"],
            "raw_sha256": raw_hash,
            "counts": parsed["counts"],
            "operations": parsed["operations"],
            "top_pollutants": parsed["observable_properties"][:25],
            "science_notes": [
                "Capabilities readiness is confirmed; this is not yet observation harvesting.",
                "Use explicit GetObservation/GetResult windows before adding UK-AIR SOS to pollutant timeseries.",
                "The raw capabilities XML was compressed to avoid large uncompressed XML commits."
            ],
        }
        write_json(site_root / "provider_summary.json", provider_summary)

        rec = source_record(
            status="ok",
            title="UK-AIR SOS GetCapabilities verified",
            url=r.url,
            output_path=str(out_root / "ukair_sos_capabilities_parsed.json"),
            http_status=r.status_code,
            record_count=(
                parsed["counts"]["offerings"]
                + parsed["counts"]["procedures_unique"]
                + parsed["counts"]["observable_properties_unique"]
            ),
            notes="UK-AIR SOS capabilities parsed successfully with offerings, procedures and observableProperty values. Observation harvesting remains a separate explicit-date-window step.",
            sha256=raw_hash,
            extra={
                "ukair_sos_counts": parsed["counts"],
                "ukair_sos_operations": parsed["operations"],
            },
        )
        records.append(rec)

    except Exception as exc:
        rec = source_record(
            status="error",
            title="UK-AIR SOS GetCapabilities parse",
            url=r.url,
            output_path=str(raw_gz),
            http_status=r.status_code,
            record_count=0,
            notes="Capabilities endpoint responded, but XML parsing failed.",
            sha256=raw_hash,
            error=repr(exc),
        )
        records.append(rec)

    write_json(out_root / "ukair_sos_source_records.json", records)
    write_json(site_root / "source_records.json", records)

    # Redaction / secret-like scan over generated JSON only.
    generated_json = list(out_root.glob("*.json")) + list(site_root.glob("*.json"))
    leak_issues = redact_check_files(generated_json)
    if leak_issues:
        write_json(out_root / "ukair_sos_redaction_issues.json", leak_issues)
        print(json.dumps({"ok": False, "redaction_issues": leak_issues}, indent=2))
        return 2

    print(json.dumps({
        "ok": any(x["status"] == "ok" for x in records),
        "records": records,
        "attempts": attempts,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
