#!/usr/bin/env python3
"""
AQ26 UK-AIR SOS provider probe.

Purpose:
- Adds Defra UK-AIR Sensor Observation Service as an official machine-readable
  ground-air provider.
- Probes GetCapabilities.
- Saves provenance, raw capabilities XML, parsed offerings/procedures/observed properties.
- Produces AQ26-compatible source records.
- Does not fabricate observations.

Next extension:
- Use parsed offerings + observed properties to call GetObservation/GetResult
  for explicit weekly windows.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import requests
import xml.etree.ElementTree as ET


DEFAULT_CAPABILITIES_URLS = [
    "https://uk-air.defra.gov.uk/sos-ukair/api/v1/sos/kvp",
    "https://uk-air.defra.gov.uk/sos-ukair/sos",
    "https://uk-air.defra.gov.uk/sos-ukair/api/v1/sos",
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


def safe_text(x: Optional[str]) -> str:
    return (x or "").strip()


def strip_ns(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def xml_text(el: ET.Element) -> str:
    return "".join(el.itertext()).strip()


def iter_by_localname(root: ET.Element, localname: str):
    for el in root.iter():
        if strip_ns(el.tag) == localname:
            yield el


def get_attr_any(el: ET.Element, names: List[str]) -> Optional[str]:
    for k, v in el.attrib.items():
        if strip_ns(k) in names:
            return v
    return None


def request_get(url: str, params: Dict[str, str], timeout: int, retries: int, backoff: int, user_agent: str):
    headers = {
        "User-Agent": user_agent,
        "Accept": "application/xml,text/xml,*/*",
    }

    last_exc = None
    final_url = url + ("?" + urlencode(params) if params else "")

    for attempt in range(1, retries + 1):
        try:
            r = requests.get(url, params=params, headers=headers, timeout=timeout)
            return r
        except Exception as exc:
            last_exc = exc
            if attempt < retries:
                time.sleep(backoff * attempt)

    raise RuntimeError(f"UK-AIR SOS request failed after {retries} attempts: {last_exc}; url={final_url}")


def probe_capabilities(base_urls: List[str], timeout: int, retries: int, backoff: int, user_agent: str):
    params_variants = [
        {"service": "SOS", "request": "GetCapabilities", "AcceptVersions": "2.0.0"},
        {"service": "SOS", "request": "GetCapabilities", "version": "2.0.0"},
        {"service": "SOS", "request": "GetCapabilities"},
    ]

    attempts = []
    for base_url in base_urls:
        for params in params_variants:
            try:
                r = request_get(base_url, params, timeout, retries, backoff, user_agent)
                text = r.text or ""
                attempts.append({
                    "url": r.url,
                    "http_status": r.status_code,
                    "content_type": r.headers.get("content-type", ""),
                    "bytes": len(r.content or b""),
                    "looks_xml": text.lstrip().startswith("<"),
                    "sha256": sha256_bytes(r.content or b""),
                })
                if r.status_code == 200 and text.lstrip().startswith("<"):
                    return r, attempts
            except Exception as exc:
                attempts.append({
                    "url": base_url,
                    "http_status": None,
                    "error": repr(exc),
                })

    return None, attempts


def parse_capabilities_xml(xml_bytes: bytes) -> Dict[str, Any]:
    root = ET.fromstring(xml_bytes)

    operations = []
    for op in iter_by_localname(root, "Operation"):
        name = op.attrib.get("name")
        if name:
            operations.append(name)

    observed_properties = sorted({
        xml_text(el)
        for el in iter_by_localname(root, "observedProperty")
        if xml_text(el)
    })

    procedures = sorted({
        xml_text(el)
        for el in iter_by_localname(root, "procedure")
        if xml_text(el)
    })

    offerings = []
    for off in list(iter_by_localname(root, "ObservationOffering")) + list(iter_by_localname(root, "ObservationOfferingType")):
        identifier = None
        name = None
        for child in off.iter():
            lname = strip_ns(child.tag)
            if lname in ("identifier", "Identifier") and not identifier:
                identifier = xml_text(child)
            if lname in ("name", "Name") and not name:
                name = xml_text(child)
        offerings.append({
            "identifier": identifier,
            "name": name,
        })

    offerings = [x for x in offerings if x.get("identifier") or x.get("name")]

    service_identification = {}
    for el in iter_by_localname(root, "ServiceIdentification"):
        for child in el:
            service_identification[strip_ns(child.tag)] = xml_text(child)

    return {
        "root_tag": strip_ns(root.tag),
        "service_identification": service_identification,
        "operations": sorted(set(operations)),
        "observed_properties": observed_properties,
        "procedures": procedures,
        "offerings": offerings,
        "counts": {
            "operations": len(set(operations)),
            "observed_properties": len(observed_properties),
            "procedures": len(procedures),
            "offerings": len(offerings),
        },
    }


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
) -> Dict[str, Any]:
    ts = now_utc()
    return {
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
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--repo-root", default=".")
    p.add_argument("--config-url", default="")
    p.add_argument("--out-root", default="outputs/30_ukair_sos")
    p.add_argument("--site-root", default="site_public/data/providers/ukair_sos")
    p.add_argument("--timeout", type=int, default=int(os.getenv("AQ26_UKAIR_SOS_TIMEOUT", "45")))
    p.add_argument("--retries", type=int, default=int(os.getenv("AQ26_UKAIR_SOS_RETRIES", "3")))
    p.add_argument("--backoff", type=int, default=int(os.getenv("AQ26_UKAIR_SOS_BACKOFF", "8")))
    p.add_argument("--user-agent", default=os.getenv("AQ26_USER_AGENT", "AQ26/3.4 scientific-backfill"))
    args = p.parse_args()

    repo = Path(args.repo_root).resolve()
    out_root = repo / args.out_root
    site_root = repo / args.site_root
    mkdir(out_root)
    mkdir(site_root)

    urls = []
    if args.config_url:
        urls.append(args.config_url)
    urls.extend(DEFAULT_CAPABILITIES_URLS)

    r, attempts = probe_capabilities(urls, args.timeout, args.retries, args.backoff, args.user_agent)

    write_json(out_root / "ukair_sos_probe_attempts.json", attempts)
    write_json(site_root / "probe_attempts.json", attempts)

    records = []

    if r is None:
        rec = source_record(
            status="warning",
            title="UK-AIR SOS GetCapabilities probe",
            url=urls[0],
            output_path=str(out_root / "ukair_sos_probe_attempts.json"),
            http_status=None,
            record_count=0,
            notes="No working UK-AIR SOS GetCapabilities endpoint was confirmed. Check endpoint URL/binding.",
            error="capabilities_probe_failed",
        )
        records.append(rec)
        write_json(out_root / "ukair_sos_source_records.json", records)
        write_json(site_root / "source_records.json", records)
        print(json.dumps({"ok": False, "records": records, "attempts": attempts}, indent=2))
        return 0

    raw_path = out_root / "ukair_sos_capabilities.xml"
    raw_path.write_bytes(r.content)
    raw_hash = sha256_bytes(r.content)

    try:
        parsed = parse_capabilities_xml(r.content)
        parsed["retrieved_at_utc"] = now_utc()
        parsed["source_url"] = r.url
        parsed["raw_sha256"] = raw_hash

        write_json(out_root / "ukair_sos_capabilities_parsed.json", parsed)
        write_json(site_root / "capabilities.json", parsed)

        # Convenience split files for the website / later collector.
        write_json(site_root / "pollutant_inventory.json", {
            "provider": "ukair_sos",
            "observed_properties": parsed.get("observed_properties", []),
            "count": len(parsed.get("observed_properties", [])),
            "source_url": r.url,
            "retrieved_at_utc": parsed["retrieved_at_utc"],
        })
        write_json(site_root / "station_inventory.json", {
            "provider": "ukair_sos",
            "procedures": parsed.get("procedures", []),
            "offerings": parsed.get("offerings", []),
            "counts": {
                "procedures": len(parsed.get("procedures", [])),
                "offerings": len(parsed.get("offerings", [])),
            },
            "source_url": r.url,
            "retrieved_at_utc": parsed["retrieved_at_utc"],
        })

        rec = source_record(
            status="ok",
            title="UK-AIR SOS GetCapabilities",
            url=r.url,
            output_path=str(raw_path),
            http_status=r.status_code,
            record_count=parsed["counts"]["offerings"] + parsed["counts"]["observed_properties"] + parsed["counts"]["procedures"],
            notes="UK-AIR SOS capabilities parsed successfully. This establishes provider readiness; observation harvesting should use explicit date windows.",
            sha256=raw_hash,
        )
        records.append(rec)

    except Exception as exc:
        rec = source_record(
            status="warning",
            title="UK-AIR SOS GetCapabilities parse",
            url=r.url,
            output_path=str(raw_path),
            http_status=r.status_code,
            record_count=0,
            notes="Capabilities endpoint responded, but XML parsing failed.",
            sha256=raw_hash,
            error=repr(exc),
        )
        records.append(rec)

    write_json(out_root / "ukair_sos_source_records.json", records)
    write_json(site_root / "source_records.json", records)

    print(json.dumps({
        "ok": any(x["status"] == "ok" for x in records),
        "records": records,
        "attempts": attempts,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
