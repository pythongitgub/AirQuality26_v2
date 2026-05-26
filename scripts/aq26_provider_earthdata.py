#!/usr/bin/env python3
"""
AQ26 NASA Earthdata / CMR provider probe v0.1.

This is intentionally discovery-first:
- Searches CMR collections for atmosphere/air-quality candidates.
- Searches a small number of granules for candidate collections.
- Writes source records and a public website summary.
- Does not require Earthdata Login for discovery.
- Does not download large data files in GitHub Actions.

Next stage after this probe:
Use Earthdata Login and OPeNDAP/Hyrax only for selected collection/granule subsets.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import requests
try:
    import yaml  # type: ignore
except Exception:
    yaml = None

CMR = "https://cmr.earthdata.nasa.gov/search"


def mkdir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def write_json(p: Path, obj: Any) -> None:
    mkdir(p.parent)
    p.write_text(json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def load_config(path: Path) -> Dict[str, Any]:
    if path.exists() and yaml is not None:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {}


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_text(txt: str) -> str:
    return hashlib.sha256(txt.encode("utf-8")).hexdigest()


def get_json(url: str, params: Dict[str, Any], timeout: int, user_agent: str) -> Dict[str, Any]:
    headers = {"User-Agent": user_agent, "Accept": "application/json"}
    r = requests.get(url, params=params, headers=headers, timeout=timeout)
    content = r.text
    meta = {
        "url": r.url,
        "http_status": r.status_code,
        "content_type": r.headers.get("content-type", ""),
        "bytes": len(content.encode("utf-8")),
        "sha256": sha256_text(content),
    }
    if r.status_code != 200:
        return {"_meta": meta, "_error": content[:1000]}
    try:
        payload = r.json()
    except Exception as exc:
        return {"_meta": {**meta, "error": repr(exc)}, "_error": content[:1000]}
    payload["_meta"] = meta
    return payload


def cmr_collection_rows(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    entries = payload.get("feed", {}).get("entry", [])
    rows: List[Dict[str, Any]] = []
    for e in entries:
        rows.append({
            "id": e.get("id"),
            "concept_id": e.get("id"),
            "short_name": e.get("short_name"),
            "version_id": e.get("version_id"),
            "title": e.get("title"),
            "data_center": e.get("data_center"),
            "time_start": e.get("time_start"),
            "time_end": e.get("time_end"),
            "summary": e.get("summary", "")[:500],
            "links": e.get("links", []),
        })
    return rows


def cmr_granule_rows(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    entries = payload.get("feed", {}).get("entry", [])
    rows: List[Dict[str, Any]] = []
    for e in entries:
        links = e.get("links", [])
        hrefs = [l.get("href") for l in links if isinstance(l, dict) and l.get("href")]
        rows.append({
            "id": e.get("id"),
            "title": e.get("title"),
            "collection_concept_id": e.get("collection_concept_id"),
            "time_start": e.get("time_start"),
            "time_end": e.get("time_end"),
            "updated": e.get("updated"),
            "producer_granule_id": e.get("producer_granule_id"),
            "links_count": len(hrefs),
            "opendap_links": [h for h in hrefs if "opendap" in h.lower() or "dap" in h.lower()][:10],
            "download_links": hrefs[:10],
        })
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--config", default="configs/aq26_earthdata.yml")
    ap.add_argument("--max-collections", type=int, default=10)
    ap.add_argument("--max-granules-per-collection", type=int, default=3)
    ap.add_argument("--timeout", type=int, default=60)
    ap.add_argument("--user-agent", default=os.getenv("AQ26_USER_AGENT", "AQ26/earthdata-cmr-probe contact=not-set"))
    args = ap.parse_args()

    repo = Path(args.repo_root).resolve()
    cfg = load_config(repo / args.config)
    out_root = repo / cfg.get("outputs", {}).get("root", "outputs/32_earthdata")
    site_root = repo / cfg.get("outputs", {}).get("site_root", "site_public/data/providers/earthdata")
    mkdir(out_root); mkdir(site_root)

    bbox = cfg.get("search", {}).get("bounding_box", "-1.1,50.6,0.7,51.6")
    temporal = cfg.get("search", {}).get("temporal", "2024-01-01T00:00:00Z,2026-05-26T23:59:59Z")
    keywords = cfg.get("search", {}).get("keywords", ["air quality", "aerosol", "nitrogen dioxide", "sulfur dioxide", "carbon monoxide", "ozone"])
    page_size = min(int(args.max_collections), 50)

    collection_results = []
    seen = set()
    for kw in keywords:
        payload = get_json(
            f"{CMR}/collections.json",
            {
                "keyword": kw,
                "bounding_box": bbox,
                "temporal": temporal,
                "page_size": page_size,
                "sort_key": "-score",
            },
            args.timeout,
            args.user_agent,
        )
        write_json(out_root / f"collections_{kw.replace(' ', '_')}.json", payload)
        for row in cmr_collection_rows(payload):
            cid = row.get("concept_id")
            if cid and cid not in seen:
                seen.add(cid)
                row["matched_keyword"] = kw
                collection_results.append(row)

    collection_results = collection_results[: args.max_collections]
    write_json(out_root / "collection_candidates.json", collection_results)
    write_json(site_root / "collection_candidates.json", collection_results)

    granule_results = []
    for coll in collection_results:
        cid = coll.get("concept_id")
        if not cid:
            continue
        payload = get_json(
            f"{CMR}/granules.json",
            {
                "collection_concept_id": cid,
                "bounding_box": bbox,
                "temporal": temporal,
                "page_size": args.max_granules_per_collection,
                "sort_key": "-start_date",
            },
            args.timeout,
            args.user_agent,
        )
        write_json(out_root / f"granules_{cid}.json", payload)
        for row in cmr_granule_rows(payload):
            row["collection_title"] = coll.get("title")
            row["collection_short_name"] = coll.get("short_name")
            granule_results.append(row)
        time.sleep(0.2)

    write_json(out_root / "granule_candidates.json", granule_results)
    write_json(site_root / "granule_candidates.json", granule_results)

    records = [
        {
            "source_type": "nasa_earthdata_cmr",
            "source_class": "satellite_or_reanalysis_discovery",
            "provider": "NASA Earthdata Common Metadata Repository",
            "title": "NASA Earthdata CMR air-quality collection discovery",
            "status": "ok" if collection_results else "warning",
            "retrieved_at_utc": now(),
            "temporal_role": "catalogue_discovery",
            "record_count": len(collection_results),
            "output_path": "outputs/32_earthdata/collection_candidates.json",
            "provenance_level": "official_machine_readable_catalogue",
            "notes": "Discovery only. Do not treat catalogue candidates as extracted pollutant observations.",
        },
        {
            "source_type": "nasa_earthdata_cmr",
            "source_class": "satellite_or_reanalysis_discovery",
            "provider": "NASA Earthdata Common Metadata Repository",
            "title": "NASA Earthdata CMR air-quality granule probe",
            "status": "ok" if granule_results else "warning",
            "retrieved_at_utc": now(),
            "temporal_role": "granule_discovery",
            "record_count": len(granule_results),
            "output_path": "outputs/32_earthdata/granule_candidates.json",
            "provenance_level": "official_machine_readable_catalogue",
            "notes": "Tiny granule probe only. Next stage should select a small subset via Earthdata Login/OPeNDAP.",
        },
    ]
    summary = {
        "provider": "nasa_earthdata",
        "status": "ok" if collection_results else "warning",
        "retrieved_at_utc": now(),
        "cmr_collections": len(collection_results),
        "cmr_granules": len(granule_results),
        "bounding_box": bbox,
        "temporal": temporal,
        "next_api_order": ["CMR Search APIs", "Earthdata Login APIs", "OPeNDAP/Hyrax", "GIBS", "DAAC-specific APIs"],
        "caveat": "Discovery output is not observational evidence until a selected product is downloaded/subsetted and validated.",
    }
    write_json(out_root / "earthdata_source_records.json", records)
    write_json(out_root / "earthdata_summary.json", summary)
    write_json(site_root / "source_records.json", records)
    write_json(site_root / "summary.json", summary)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
