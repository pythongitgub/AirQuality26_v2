#!/usr/bin/env python3
"""
AQ26 Remaining Incinerator Overlay Finder V2

Purpose
-------
Find candidate monitoring-site overlays for the incinerator facility register.
This version fixes the earlier OpenAQ 422 failures by:
  * capping OpenAQ point-radius requests at 25,000 metres;
  * using coordinates as latitude,longitude for OpenAQ v3 point queries;
  * removing unsupported sort=distance/order_by=distance parameters;
  * using iso=GB instead of countries_id=GB;
  * trying several safe query variants including bbox fallback;
  * recording exact URLs and HTTP bodies for rejected queries;
  * using validated DEFRA/AURN overlays as already-confirmed rows;
  * keeping all new matches as candidate_needs_review, not auto-validated.

Inputs
------
configs/aq26_incinerator_register/UK_Incinerators_with_Controls_Full_v3.csv
configs/aq26_incinerator_register/UK_Incinerators_with_DEFRA_Sites_v3_validated_Full.csv

Outputs
-------
site_public/data/focus/overlays_v2/incinerator_overlay_summary.json
site_public/data/focus/overlays_v2/validated_defra_overlays.csv
site_public/data/focus/overlays_v2/remaining_overlay_queue.csv
site_public/data/focus/overlays_v2/openaq_query_diagnostics.csv
site_public/data/focus/overlays_v2/candidate_monitoring_overlays.csv
site_public/data/focus/overlays_v2/selected_candidate_overlays_needing_review.csv
site_public/data/focus/overlays_v2/overlay_discovery_errors.json
site_public/incinerator-overlays.html
"""
from __future__ import annotations

import argparse
import csv
import html
import json
import math
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

OPENAQ_BASE = "https://api.openaq.org/v3/locations"
MAX_OPENAQ_RADIUS_M = 25000
DEFAULT_TIMEOUT = 35

POLLUTANT_WEIGHTS = {
    "pm25": 12, "pm2.5": 12, "pm10": 12,
    "no2": 10, "so2": 10, "co": 7, "o3": 6,
    "nox": 8, "no": 5, "benzene": 5, "voc": 5,
}
OFFICIAL_HINTS = ("aurn", "defra", "uk-air", "uk air", "air quality england", "aqe", "local authority")


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def safe_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    s = str(v).strip()
    if not s or s.lower() in {"nan", "none", "null"}:
        return None
    try:
        return float(s)
    except Exception:
        return None


def slugify(s: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "_", (s or "").strip().lower()).strip("_")
    return s or "unknown"


def read_csv_dicts(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"Missing CSV: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: List[Dict[str, Any]], fieldnames: Optional[List[str]] = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        keys = []
        for r in rows:
            for k in r.keys():
                if k not in keys:
                    keys.append(k)
        fieldnames = keys or ["empty"]
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fieldnames})


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def row_facility_key(row: Dict[str, Any]) -> str:
    return slugify(row.get("Facility") or row.get("facility") or row.get("Facility_Name") or "")


def validated_keys(validated_rows: List[Dict[str, str]]) -> set:
    return {row_facility_key(r) for r in validated_rows if row_facility_key(r)}


def parse_openaq_location(item: Dict[str, Any]) -> Dict[str, Any]:
    coords = item.get("coordinates") or {}
    lat = safe_float(coords.get("latitude"))
    lon = safe_float(coords.get("longitude"))
    name = item.get("name") or item.get("location") or item.get("displayName") or ""
    provider_names = []
    for key in ("provider", "owner", "manufacturer", "country", "locality", "timezone"):
        val = item.get(key)
        if isinstance(val, dict):
            provider_names.append(str(val.get("name") or val.get("id") or ""))
        elif val:
            provider_names.append(str(val))
    sensors = item.get("sensors") or []
    parameters = item.get("parameters") or []
    parameter_names: List[str] = []
    for seq in (sensors, parameters):
        if isinstance(seq, list):
            for p in seq:
                if isinstance(p, dict):
                    for pk in ("parameter", "name", "displayName"):
                        v = p.get(pk)
                        if isinstance(v, dict):
                            v = v.get("name") or v.get("displayName")
                        if v:
                            parameter_names.append(str(v))
                            break
                elif p:
                    parameter_names.append(str(p))
    return {
        "openaq_location_id": item.get("id", ""),
        "monitoring_site_name": name,
        "monitoring_site_lat": lat,
        "monitoring_site_lon": lon,
        "monitoring_site_locality": item.get("locality") or "",
        "monitoring_site_country": (item.get("country") or {}).get("name") if isinstance(item.get("country"), dict) else item.get("country", ""),
        "monitoring_provider_text": " | ".join([x for x in provider_names if x]),
        "pollutants": sorted(set([p.lower().replace(" ", "") for p in parameter_names if p])),
        "raw": item,
    }


def score_candidate(fac: Dict[str, str], point_role: str, point_lat: float, point_lon: float, cand: Dict[str, Any]) -> Dict[str, Any]:
    clat, clon = cand.get("monitoring_site_lat"), cand.get("monitoring_site_lon")
    if clat is None or clon is None:
        dist = None
        distance_score = 0
    else:
        dist = haversine_km(point_lat, point_lon, clat, clon)
        # 25 km = low score; <= 3 km = high score
        distance_score = max(0, min(45, int(45 * (1 - min(dist, 25) / 25))))

    pollutants = cand.get("pollutants") or []
    pollutant_score = 0
    for p in pollutants:
        pollutant_score += POLLUTANT_WEIGHTS.get(p, 0)
    pollutant_score = min(35, pollutant_score)

    text = " ".join([
        str(cand.get("monitoring_site_name") or ""),
        str(cand.get("monitoring_provider_text") or ""),
        str(cand.get("monitoring_site_locality") or ""),
    ]).lower()
    official_score = 15 if any(h in text for h in OFFICIAL_HINTS) else 0
    source_score = 5  # found by official OpenAQ endpoint
    total = distance_score + pollutant_score + official_score + source_score
    return {
        "facility": fac.get("Facility", ""),
        "facility_key": row_facility_key(fac),
        "location": fac.get("Location", ""),
        "facility_lat": fac.get("Lat") or fac.get("Facility_Lat") or "",
        "facility_lon": fac.get("Lon") or fac.get("Facility_Lon") or "",
        "control_site": fac.get("Control_Site", ""),
        "control_lat": fac.get("Control_Lat", ""),
        "control_lon": fac.get("Control_Lon", ""),
        "query_point_role": point_role,
        "query_point_lat": point_lat,
        "query_point_lon": point_lon,
        "candidate_source": "OpenAQ v3 locations",
        "candidate_status": "candidate_needs_review",
        "monitoring_site_name": cand.get("monitoring_site_name", ""),
        "openaq_location_id": cand.get("openaq_location_id", ""),
        "monitoring_site_lat": clat,
        "monitoring_site_lon": clon,
        "distance_query_to_monitor_km": round(dist, 3) if dist is not None else "",
        "pollutants": ";".join(pollutants),
        "monitoring_provider_text": cand.get("monitoring_provider_text", ""),
        "distance_score": distance_score,
        "pollutant_score": pollutant_score,
        "official_hint_score": official_score,
        "source_score": source_score,
        "relevance_score": total,
        "review_note": "Candidate only; compare against DEFRA/AURN, local context and source provenance before validation.",
    }


def openaq_request(params: Dict[str, Any], api_key: Optional[str], timeout: int = DEFAULT_TIMEOUT) -> Tuple[Optional[List[Dict[str, Any]]], Dict[str, Any]]:
    clean_params = {k: str(v) for k, v in params.items() if v is not None and str(v) != ""}
    url = OPENAQ_BASE + "?" + urllib.parse.urlencode(clean_params)
    headers = {"User-Agent": "AQ26-incinerator-overlay-v2/1.0"}
    if api_key:
        # OpenAQ has used both header conventions in examples; X-API-Key is the documented/current v3 pattern.
        headers["X-API-Key"] = api_key
    req = urllib.request.Request(url, headers=headers)
    diag = {"url": url, "ok": False, "http_status": "", "error_type": "", "error_body": ""}
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            data = json.loads(body) if body else {}
            results = data.get("results") or []
            diag.update({"ok": True, "http_status": getattr(resp, "status", 200), "result_count": len(results)})
            return results, diag
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:4000]
        diag.update({"http_status": e.code, "error_type": "HTTPError", "error_body": body})
        return None, diag
    except Exception as e:
        diag.update({"error_type": type(e).__name__, "error_body": str(e)[:4000]})
        return None, diag


def bbox_around(lat: float, lon: float, km: float) -> str:
    # Approximate WGS84 bounding box. OpenAQ expects minLon,minLat,maxLon,maxLat.
    dlat = km / 111.32
    dlon = km / (111.32 * max(0.1, math.cos(math.radians(lat))))
    return f"{lon-dlon:.5f},{lat-dlat:.5f},{lon+dlon:.5f},{lat+dlat:.5f}"


def query_openaq_candidates(lat: float, lon: float, radius_km: float, limit: int, api_key: Optional[str], sleep_s: float) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    radius_m = int(min(MAX_OPENAQ_RADIUS_M, max(1000, radius_km * 1000)))
    attempts = []
    # Correct v3 style: coordinates=latitude,longitude; radius metres max 25000; iso=GB.
    attempts.append({"method": "coordinates_lat_lon_radius_capped", "params": {"coordinates": f"{lat:.5f},{lon:.5f}", "radius": radius_m, "limit": limit, "iso": "GB"}})
    # Smaller radius can sometimes reduce backend rejection/ambiguity and improves relevance.
    attempts.append({"method": "coordinates_lat_lon_radius_10000", "params": {"coordinates": f"{lat:.5f},{lon:.5f}", "radius": min(10000, radius_m), "limit": limit, "iso": "GB"}})
    # Intentional diagnostic only: lon,lat ordering. Should usually be rejected or poor, but captures ambiguity.
    attempts.append({"method": "diagnostic_coordinates_lon_lat", "params": {"coordinates": f"{lon:.5f},{lat:.5f}", "radius": min(10000, radius_m), "limit": min(limit, 25), "iso": "GB"}})
    # BBox fallback: OpenAQ expects min lon,min lat,max lon,max lat; do not combine with coordinates/radius.
    attempts.append({"method": "bbox_25km_lonlat", "params": {"bbox": bbox_around(lat, lon, min(25, radius_km)), "limit": limit, "iso": "GB"}})
    attempts.append({"method": "bbox_10km_lonlat", "params": {"bbox": bbox_around(lat, lon, 10), "limit": limit, "iso": "GB"}})

    diagnostics: List[Dict[str, Any]] = []
    unique: Dict[str, Dict[str, Any]] = {}
    for a in attempts:
        results, diag = openaq_request(a["params"], api_key)
        diag["method"] = a["method"]
        diagnostics.append(diag)
        if results:
            for item in results:
                cand = parse_openaq_location(item)
                key = str(cand.get("openaq_location_id") or cand.get("monitoring_site_name") or json.dumps(item, sort_keys=True)[:120])
                unique[key] = cand
        if sleep_s:
            time.sleep(sleep_s)
    return list(unique.values()), diagnostics


def build_page(path: Path, summary: Dict[str, Any], selected: List[Dict[str, Any]], queue: List[Dict[str, Any]], diagnostics: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for r in selected[:200]:
        rows.append(
            "<tr>"
            f"<td>{html.escape(str(r.get('facility','')))}</td>"
            f"<td>{html.escape(str(r.get('query_point_role','')))}</td>"
            f"<td>{html.escape(str(r.get('monitoring_site_name','')))}</td>"
            f"<td>{html.escape(str(r.get('distance_query_to_monitor_km','')))}</td>"
            f"<td>{html.escape(str(r.get('pollutants','')))}</td>"
            f"<td>{html.escape(str(r.get('relevance_score','')))}</td>"
            "</tr>"
        )
    if not rows:
        rows.append("<tr><td colspan='6'>No candidates selected yet. Check diagnostics and queue.</td></tr>")
    html_doc = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>AQ26 Incinerator Overlay Discovery</title>
  <style>
    body{{font-family:system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif;margin:0;background:#f4f7fb;color:#102033}}
    header{{background:#fff;border-bottom:1px solid #d9e2ef;padding:18px 28px;position:sticky;top:0;z-index:2}}
    main{{max-width:1180px;margin:0 auto;padding:28px}}
    .hero{{background:linear-gradient(135deg,#09213f,#0e6a7b);color:#fff;border-radius:24px;padding:28px;box-shadow:0 18px 50px rgba(14,42,71,.18)}}
    .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:14px;margin:18px 0}}
    .card{{background:#fff;border:1px solid #d9e2ef;border-radius:18px;padding:18px;box-shadow:0 10px 24px rgba(14,42,71,.08)}}
    .num{{font-size:2rem;font-weight:800;color:#0e6a7b}}
    table{{border-collapse:collapse;width:100%;background:#fff;border-radius:16px;overflow:hidden}}
    th,td{{border-bottom:1px solid #e6edf5;text-align:left;padding:10px;vertical-align:top;font-size:.92rem}}
    th{{background:#0b2742;color:#fff}}
    code{{background:#edf3f9;padding:2px 5px;border-radius:5px}}
  </style>
</head>
<body>
<header><strong>SCC Nexus · AQ26</strong> · Incinerator monitoring overlay discovery</header>
<main>
<section class="hero">
  <h1>Incinerator monitoring overlay discovery V2</h1>
  <p>DEFRA/AURN validated overlays are preserved. Remaining England/Wales facilities are queried using OpenAQ-safe coordinate, radius and bbox patterns. All new matches remain candidates until reviewed.</p>
</section>
<section class="grid">
  <div class="card"><div class="num">{summary.get('broad_facilities')}</div><p>Broad facilities</p></div>
  <div class="card"><div class="num">{summary.get('validated_overlays')}</div><p>Validated overlays</p></div>
  <div class="card"><div class="num">{summary.get('remaining_facilities')}</div><p>Remaining queue</p></div>
  <div class="card"><div class="num">{summary.get('candidate_rows')}</div><p>Candidate rows</p></div>
  <div class="card"><div class="num">{summary.get('selected_candidates')}</div><p>Selected for review</p></div>
</section>
<section class="card">
  <h2>Selected candidates needing review</h2>
  <table><thead><tr><th>Facility</th><th>Query point</th><th>Candidate site</th><th>km</th><th>Pollutants</th><th>Score</th></tr></thead><tbody>{''.join(rows)}</tbody></table>
</section>
<section class="card">
  <h2>Outputs</h2>
  <p><code>site_public/data/focus/overlays_v2/candidate_monitoring_overlays.csv</code></p>
  <p><code>site_public/data/focus/overlays_v2/openaq_query_diagnostics.csv</code></p>
  <p><code>site_public/data/focus/overlays_v2/remaining_overlay_queue.csv</code></p>
</section>
</main>
</body></html>"""
    path.write_text(html_doc, encoding="utf-8")


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--broad-register", default="configs/aq26_incinerator_register/UK_Incinerators_with_Controls_Full_v3.csv")
    ap.add_argument("--validated-overlays", default="configs/aq26_incinerator_register/UK_Incinerators_with_DEFRA_Sites_v3_validated_Full.csv")
    ap.add_argument("--output-root", default="site_public/data/focus/overlays_v2")
    ap.add_argument("--site-root", default="site_public")
    ap.add_argument("--radius-km", type=float, default=25.0, help="Requested search radius. OpenAQ point radius is capped at 25 km.")
    ap.add_argument("--limit-per-query", type=int, default=100)
    ap.add_argument("--max-facilities", type=int, default=0, help="0 means all remaining facilities")
    ap.add_argument("--live-openaq", action="store_true")
    ap.add_argument("--write-page", action="store_true")
    ap.add_argument("--min-score", type=int, default=35)
    ap.add_argument("--sleep", type=float, default=0.2)
    args = ap.parse_args(argv)

    broad_path = Path(args.broad_register)
    valid_path = Path(args.validated_overlays)
    out = Path(args.output_root)
    site = Path(args.site_root)
    out.mkdir(parents=True, exist_ok=True)
    site.mkdir(parents=True, exist_ok=True)

    broad_rows = read_csv_dicts(broad_path)
    valid_rows = read_csv_dicts(valid_path)
    done = validated_keys(valid_rows)
    remaining = [r for r in broad_rows if row_facility_key(r) not in done]
    if args.max_facilities and args.max_facilities > 0:
        remaining = remaining[: args.max_facilities]

    candidate_rows: List[Dict[str, Any]] = []
    diagnostics: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []
    api_key = os.environ.get("OPENAQ_API_KEY", "").strip() or None

    if args.live_openaq:
        for idx, fac in enumerate(remaining, start=1):
            points = []
            flat, flon = safe_float(fac.get("Lat") or fac.get("Facility_Lat")), safe_float(fac.get("Lon") or fac.get("Facility_Lon"))
            clat, clon = safe_float(fac.get("Control_Lat")), safe_float(fac.get("Control_Lon"))
            if flat is not None and flon is not None:
                points.append(("facility", flat, flon))
            if clat is not None and clon is not None:
                points.append(("control", clat, clon))
            if not points:
                errors.append({"facility": fac.get("Facility", ""), "error": "no usable lat/lon coordinates in register"})
                continue
            for role, lat, lon in points:
                cands, diags = query_openaq_candidates(lat, lon, args.radius_km, args.limit_per_query, api_key, args.sleep)
                for d in diags:
                    d.update({"facility": fac.get("Facility", ""), "facility_key": row_facility_key(fac), "query_point_role": role, "query_lat": lat, "query_lon": lon})
                    diagnostics.append(d)
                for cand in cands:
                    candidate_rows.append(score_candidate(fac, role, lat, lon, cand))
    else:
        diagnostics.append({"ok": True, "method": "live_openaq_disabled", "message": "Run with --live-openaq to query OpenAQ."})

    # De-duplicate by facility + location id/site name + query role. Keep highest score.
    dedup: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
    for r in candidate_rows:
        key = (r.get("facility_key", ""), str(r.get("openaq_location_id") or r.get("monitoring_site_name")), r.get("query_point_role", ""))
        if key not in dedup or int(r.get("relevance_score") or 0) > int(dedup[key].get("relevance_score") or 0):
            dedup[key] = r
    candidate_rows = sorted(dedup.values(), key=lambda x: (x.get("facility", ""), -int(x.get("relevance_score") or 0)))

    # Select top candidates per facility and role above threshold.
    selected = []
    seen_counts: Dict[Tuple[str, str], int] = {}
    for r in candidate_rows:
        if int(r.get("relevance_score") or 0) < args.min_score:
            continue
        key = (r.get("facility_key", ""), r.get("query_point_role", ""))
        if seen_counts.get(key, 0) >= 3:
            continue
        selected.append(r)
        seen_counts[key] = seen_counts.get(key, 0) + 1

    summary = {
        "generated_utc": utc_now(),
        "broad_facilities": len(broad_rows),
        "validated_overlays": len(valid_rows),
        "remaining_facilities_total": len([r for r in broad_rows if row_facility_key(r) not in done]),
        "remaining_facilities": len(remaining),
        "live_openaq": bool(args.live_openaq),
        "requested_radius_km": args.radius_km,
        "openaq_point_radius_cap_m": MAX_OPENAQ_RADIUS_M,
        "limit_per_query": args.limit_per_query,
        "candidate_rows": len(candidate_rows),
        "selected_candidates": len(selected),
        "diagnostic_rows": len(diagnostics),
        "error_rows": len(errors),
        "status": "candidate_discovery_complete" if args.live_openaq else "queue_only_live_openaq_disabled",
        "note": "New candidates are not validated. Promote only after manual/source review.",
    }

    write_csv(out / "validated_defra_overlays.csv", valid_rows)
    write_csv(out / "remaining_overlay_queue.csv", remaining)
    write_csv(out / "candidate_monitoring_overlays.csv", candidate_rows)
    write_csv(out / "selected_candidate_overlays_needing_review.csv", selected)
    write_csv(out / "openaq_query_diagnostics.csv", diagnostics)
    write_json(out / "overlay_discovery_errors.json", errors)
    write_json(out / "incinerator_overlay_summary.json", summary)

    if args.write_page:
        build_page(site / "incinerator-overlays.html", summary, selected, remaining, diagnostics)

    print(json.dumps(summary, indent=2))
    # This workflow should not fail just because no candidates are found; diagnostics are the output.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
