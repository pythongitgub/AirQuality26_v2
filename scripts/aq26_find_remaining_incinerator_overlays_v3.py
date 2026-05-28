#!/usr/bin/env python3
"""
AQ26 Remaining Incinerator Overlay Finder V3

Purpose
-------
Production-grade candidate monitoring overlay discovery for the AQ26 England/Wales
incinerator register.

V3 improvements over V2:
  * facility-key aliasing so already validated rows are not re-queued simply due to
    name variants such as Riverside RR ERF vs Riverside Resource Recovery;
  * OpenAQ-safe requests: coordinates are latitude,longitude, radius is capped at
    25 km, iso=GB is used, bbox fallback is lon,lat order;
  * no unsupported OpenAQ sort=distance/order_by=distance parameters;
  * 429 retry handling, Retry-After support, exponential backoff and configurable
    sleep between requests;
  * optional reuse of previously generated V2 candidates to reduce repeated API calls;
  * candidate classification into high-confidence official, local-network,
    supporting/community, weak-distance, and manual-review categories;
  * facility-level overlay status summary for public/incinerator pages.

All new matches remain candidates until reviewed. The script never auto-validates
new overlays.
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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

OPENAQ_BASE = "https://api.openaq.org/v3/locations"
MAX_OPENAQ_RADIUS_M = 25000
DEFAULT_TIMEOUT = 35

CORE_POLLUTANTS = {"no2", "pm25", "pm2.5", "pm10", "so2", "co", "o3", "nox", "no"}
POLLUTANT_WEIGHTS = {
    "pm25": 12, "pm2.5": 12, "pm10": 12,
    "no2": 12, "so2": 10, "nox": 8, "co": 7, "o3": 6, "no": 5,
    "benzene": 5, "voc": 5,
}
OFFICIAL_HINTS = (
    "aurn", "defra", "uk-air", "uk air", "air quality england", "aqe",
    "environment agency", "eea", "governmental", "local authority",
)
LOCAL_NETWORK_HINTS = (
    "london air quality network", "laqn", "king's college", "imperial",
    "air quality england", "local authority",
)
COMMUNITY_HINTS = (
    "airgradient", "purpleair", "sensor.community", "low cost", "opensensemap",
)
FACILITY_ALIAS_OVERRIDES = {
    "riverside_rr": "riverside_resource_recovery",
    "riverside_rr_erf": "riverside_resource_recovery",
    "riverside_resource_recovery": "riverside_resource_recovery",
    "runcorn": "runcorn",
    "runcorn_efw": "runcorn",
    "runcorn_tps": "runcorn",
    "tyseley": "tyseley",
    "tyseley_efw": "tyseley",
    "tyseley_erf": "tyseley",
}
FACILITY_STOPWORDS = {
    "the", "and", "of", "at", "waste", "energy", "from", "resource", "recovery",
    "facility", "plant", "park", "site", "centre", "center", "incinerator", "incineration",
    "efw", "erf", "rerf", "tps", "rr", "wt", "wte", "wrp", "erc", "mf2", "ps",
    "quarry", "management", "gasification", "sludge", "dockyard", "landfill",
}


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


def canonical_facility_key(name: str) -> str:
    raw = slugify(name)
    if raw in FACILITY_ALIAS_OVERRIDES:
        return FACILITY_ALIAS_OVERRIDES[raw]
    # Common suffix variants: make Tyseley EfW / Tyseley ERF collapse to tyseley.
    raw2 = re.sub(r"_(efw|erf|rerf|tps|rr|wte|wt)$", "", raw)
    if raw2 in FACILITY_ALIAS_OVERRIDES:
        return FACILITY_ALIAS_OVERRIDES[raw2]
    tokens = [t for t in raw.split("_") if t and t not in FACILITY_STOPWORDS]
    # Keep first two distinctive tokens when available, but avoid over-collapsing common names.
    if tokens:
        key = "_".join(tokens[:3])
        return FACILITY_ALIAS_OVERRIDES.get(key, key)
    return raw2 or raw


def facility_key(row: Dict[str, Any]) -> str:
    return canonical_facility_key(str(row.get("Facility") or row.get("facility") or row.get("Facility_Name") or ""))


def read_csv_dicts(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"Missing CSV: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: List[Dict[str, Any]], fieldnames: Optional[List[str]] = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        keys: List[str] = []
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


def get_facility_latlon(row: Dict[str, str]) -> Tuple[Optional[float], Optional[float]]:
    return safe_float(row.get("Lat") or row.get("Facility_Lat")), safe_float(row.get("Lon") or row.get("Facility_Lon"))


def get_control_latlon(row: Dict[str, str]) -> Tuple[Optional[float], Optional[float]]:
    return safe_float(row.get("Control_Lat")), safe_float(row.get("Control_Lon"))


def validated_keys(valid_rows: List[Dict[str, str]]) -> set:
    keys = set()
    for r in valid_rows:
        k = facility_key(r)
        if k:
            keys.add(k)
    return keys


def parse_openaq_location(item: Dict[str, Any]) -> Dict[str, Any]:
    coords = item.get("coordinates") or {}
    lat = safe_float(coords.get("latitude"))
    lon = safe_float(coords.get("longitude"))
    name = item.get("name") or item.get("location") or item.get("displayName") or ""
    provider_names: List[str] = []
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


def provider_classification(text: str) -> str:
    t = (text or "").lower()
    if any(h in t for h in COMMUNITY_HINTS):
        return "community_sensor_supporting_context"
    if any(h in t for h in OFFICIAL_HINTS):
        return "official_or_governmental_candidate"
    if any(h in t for h in LOCAL_NETWORK_HINTS):
        return "local_network_candidate"
    return "unknown_provider_candidate"


def classify_candidate(distance_km: Optional[float], pollutants: List[str], provider_text: str, score: int) -> str:
    pset = set(pollutants or [])
    pcore = len(pset & CORE_POLLUTANTS)
    provider_class = provider_classification(provider_text + " ")
    if provider_class == "community_sensor_supporting_context":
        return "supporting_context_community_sensor"
    if distance_km is not None and distance_km > 25:
        return "weak_distance_candidate"
    if provider_class == "official_or_governmental_candidate" and distance_km is not None and distance_km <= 15 and pcore >= 3 and score >= 65:
        return "high_confidence_official_candidate"
    if provider_class in {"official_or_governmental_candidate", "local_network_candidate"} and distance_km is not None and distance_km <= 20 and pcore >= 2 and score >= 55:
        return "local_or_official_candidate_needs_review"
    if pcore >= 2 and score >= 45:
        return "plausible_candidate_needs_review"
    return "manual_review_low_confidence"


def score_candidate(fac: Dict[str, str], point_role: str, point_lat: float, point_lon: float, cand: Dict[str, Any], source_label: str) -> Dict[str, Any]:
    clat, clon = cand.get("monitoring_site_lat"), cand.get("monitoring_site_lon")
    if clat is None or clon is None:
        dist = None
        distance_score = 0
    else:
        dist = haversine_km(point_lat, point_lon, clat, clon)
        distance_score = max(0, min(45, int(45 * (1 - min(dist, 25) / 25))))

    pollutants = cand.get("pollutants") or []
    pollutant_score = min(35, sum(POLLUTANT_WEIGHTS.get(p, 0) for p in pollutants))
    text = " ".join([
        str(cand.get("monitoring_site_name") or ""),
        str(cand.get("monitoring_provider_text") or ""),
        str(cand.get("monitoring_site_locality") or ""),
    ]).lower()
    official_score = 15 if any(h in text for h in OFFICIAL_HINTS) else 0
    source_score = 8 if source_label.startswith("cached") else 5
    total = distance_score + pollutant_score + official_score + source_score
    review_class = classify_candidate(dist, pollutants, cand.get("monitoring_provider_text", ""), total)
    return {
        "facility": fac.get("Facility", ""),
        "facility_key": facility_key(fac),
        "location": fac.get("Location", ""),
        "facility_lat": fac.get("Lat") or fac.get("Facility_Lat") or "",
        "facility_lon": fac.get("Lon") or fac.get("Facility_Lon") or "",
        "control_site": fac.get("Control_Site", ""),
        "control_lat": fac.get("Control_Lat", ""),
        "control_lon": fac.get("Control_Lon", ""),
        "query_point_role": point_role,
        "query_point_lat": point_lat,
        "query_point_lon": point_lon,
        "candidate_source": source_label,
        "candidate_status": "candidate_needs_review",
        "candidate_review_class": review_class,
        "monitoring_site_name": cand.get("monitoring_site_name", ""),
        "openaq_location_id": cand.get("openaq_location_id", ""),
        "monitoring_site_lat": clat,
        "monitoring_site_lon": clon,
        "distance_query_to_monitor_km": round(dist, 3) if dist is not None else "",
        "pollutants": ";".join(pollutants),
        "monitoring_provider_text": cand.get("monitoring_provider_text", ""),
        "provider_class": provider_classification(str(cand.get("monitoring_provider_text", ""))),
        "distance_score": distance_score,
        "pollutant_score": pollutant_score,
        "official_hint_score": official_score,
        "source_score": source_score,
        "relevance_score": total,
        "suggested_action": suggested_action(review_class),
        "review_note": "Candidate only; compare against DEFRA/AURN, local geography, control-site role and source provenance before validation.",
    }


def suggested_action(review_class: str) -> str:
    if review_class == "high_confidence_official_candidate":
        return "review_for_promotion_to_validated_overlay"
    if review_class == "local_or_official_candidate_needs_review":
        return "review_as_local_or_official_overlay_candidate"
    if review_class == "supporting_context_community_sensor":
        return "supporting_context_only_do_not_validate_as_regulatory_overlay"
    if review_class == "weak_distance_candidate":
        return "manual_review_distance_too_high"
    return "manual_review_required"


def openaq_request(params: Dict[str, Any], api_key: Optional[str], timeout: int, max_retries: int, base_sleep: float) -> Tuple[Optional[List[Dict[str, Any]]], Dict[str, Any]]:
    clean_params = {k: str(v) for k, v in params.items() if v is not None and str(v) != ""}
    url = OPENAQ_BASE + "?" + urllib.parse.urlencode(clean_params)
    headers = {"User-Agent": "AQ26-incinerator-overlay-v3/1.0"}
    if api_key:
        headers["X-API-Key"] = api_key
    diag: Dict[str, Any] = {"url": url, "ok": False, "http_status": "", "error_type": "", "error_body": "", "attempts": 0, "retry_after": ""}
    for attempt in range(max(1, max_retries + 1)):
        diag["attempts"] = attempt + 1
        req = urllib.request.Request(url, headers=headers)
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
            if e.code == 429 and attempt < max_retries:
                ra = e.headers.get("Retry-After") if e.headers else None
                diag["retry_after"] = ra or ""
                delay = safe_float(ra) or (base_sleep * (2 ** attempt) + 2.0)
                time.sleep(min(90.0, max(1.0, delay)))
                continue
            return None, diag
        except Exception as e:
            diag.update({"error_type": type(e).__name__, "error_body": str(e)[:4000]})
            if attempt < max_retries:
                time.sleep(min(30.0, base_sleep * (2 ** attempt) + 1.0))
                continue
            return None, diag
    return None, diag


def bbox_around(lat: float, lon: float, km: float) -> str:
    dlat = km / 111.32
    dlon = km / (111.32 * max(0.1, math.cos(math.radians(lat))))
    return f"{lon-dlon:.5f},{lat-dlat:.5f},{lon+dlon:.5f},{lat+dlat:.5f}"


def query_openaq_candidates(lat: float, lon: float, radius_km: float, limit: int, api_key: Optional[str], sleep_s: float, max_retries: int, exhaustive: bool, timeout: int) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], bool]:
    radius_m = int(min(MAX_OPENAQ_RADIUS_M, max(1000, radius_km * 1000)))
    attempts = [
        {"method": "coordinates_lat_lon_radius_capped", "params": {"coordinates": f"{lat:.5f},{lon:.5f}", "radius": radius_m, "limit": limit, "iso": "GB"}},
        {"method": "coordinates_lat_lon_radius_10000", "params": {"coordinates": f"{lat:.5f},{lon:.5f}", "radius": min(10000, radius_m), "limit": limit, "iso": "GB"}},
        {"method": "bbox_25km_lonlat", "params": {"bbox": bbox_around(lat, lon, min(25, radius_km)), "limit": limit, "iso": "GB"}},
    ]
    if exhaustive:
        attempts.extend([
            {"method": "bbox_10km_lonlat", "params": {"bbox": bbox_around(lat, lon, 10), "limit": limit, "iso": "GB"}},
            {"method": "diagnostic_coordinates_lon_lat", "params": {"coordinates": f"{lon:.5f},{lat:.5f}", "radius": min(10000, radius_m), "limit": min(limit, 25), "iso": "GB"}},
        ])
    diagnostics: List[Dict[str, Any]] = []
    unique: Dict[str, Dict[str, Any]] = {}
    hit_rate_limit = False
    for a in attempts:
        results, diag = openaq_request(a["params"], api_key, timeout=timeout, max_retries=max_retries, base_sleep=max(1.0, sleep_s))
        diag["method"] = a["method"]
        diagnostics.append(diag)
        if str(diag.get("http_status")) == "429":
            hit_rate_limit = True
        if results:
            for item in results:
                cand = parse_openaq_location(item)
                key = str(cand.get("openaq_location_id") or cand.get("monitoring_site_name") or json.dumps(item, sort_keys=True)[:120])
                unique[key] = cand
        if sleep_s:
            time.sleep(sleep_s)
    return list(unique.values()), diagnostics, hit_rate_limit


def load_cached_candidates(path: Path, wanted_keys: set) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows = read_csv_dicts(path)
    out: List[Dict[str, Any]] = []
    for r in rows:
        if str(r.get("facility_key") or "") in wanted_keys or canonical_facility_key(str(r.get("facility") or "")) in wanted_keys:
            out.append(r)
    return out


def cached_row_to_candidate(r: Dict[str, Any]) -> Dict[str, Any]:
    pollutants = [x for x in str(r.get("pollutants") or "").split(";") if x]
    return {
        "openaq_location_id": r.get("openaq_location_id", ""),
        "monitoring_site_name": r.get("monitoring_site_name", ""),
        "monitoring_site_lat": safe_float(r.get("monitoring_site_lat")),
        "monitoring_site_lon": safe_float(r.get("monitoring_site_lon")),
        "monitoring_provider_text": r.get("monitoring_provider_text", ""),
        "monitoring_site_locality": "",
        "pollutants": pollutants,
    }


def html_escape(x: Any) -> str:
    return html.escape(str(x if x is not None else ""))


def build_page(path: Path, summary: Dict[str, Any], selected: List[Dict[str, Any]], status_rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cards = "".join([
        f"<div class='card'><div class='num'>{html_escape(summary.get(k,''))}</div><p>{html_escape(label)}</p></div>"
        for k, label in [
            ("broad_facilities", "Facilities in register"),
            ("validated_overlays", "Validated overlays"),
            ("remaining_facilities_total", "Remaining after alias fix"),
            ("facilities_with_selected_candidates", "Facilities with candidates"),
            ("selected_candidates", "Candidate rows for review"),
            ("rate_limited_calls", "Rate-limited calls"),
        ]
    ])
    rows = []
    for r in selected[:250]:
        rows.append(
            "<tr>"
            f"<td>{html_escape(r.get('facility'))}</td>"
            f"<td>{html_escape(r.get('candidate_review_class'))}</td>"
            f"<td>{html_escape(r.get('monitoring_site_name'))}</td>"
            f"<td>{html_escape(r.get('query_point_role'))}</td>"
            f"<td>{html_escape(r.get('distance_query_to_monitor_km'))}</td>"
            f"<td>{html_escape(r.get('pollutants'))}</td>"
            f"<td>{html_escape(r.get('relevance_score'))}</td>"
            "</tr>"
        )
    if not rows:
        rows.append("<tr><td colspan='7'>No selected candidates in this run. Review diagnostics.</td></tr>")
    status_html = []
    for r in status_rows[:80]:
        status_html.append(
            "<tr>"
            f"<td>{html_escape(r.get('facility'))}</td>"
            f"<td>{html_escape(r.get('overlay_status'))}</td>"
            f"<td>{html_escape(r.get('best_candidate_site'))}</td>"
            f"<td>{html_escape(r.get('best_candidate_score'))}</td>"
            f"<td>{html_escape(r.get('best_candidate_class'))}</td>"
            "</tr>"
        )
    html_doc = f"""<!doctype html><html lang='en'><head>
<meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>AQ26 Incinerator Overlay Discovery V3</title>
<style>
body{{font-family:system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif;margin:0;background:#f4f7fb;color:#102033}}
header{{background:#fff;border-bottom:1px solid #d9e2ef;padding:16px 28px;position:sticky;top:0;z-index:2}}
main{{max-width:1220px;margin:0 auto;padding:28px}}
.hero{{background:linear-gradient(135deg,#09213f,#0e6a7b);color:#fff;border-radius:26px;padding:30px;box-shadow:0 18px 50px rgba(14,42,71,.18)}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:14px;margin:18px 0}}
.card{{background:#fff;border:1px solid #d9e2ef;border-radius:18px;padding:18px;box-shadow:0 10px 24px rgba(14,42,71,.08)}}
.num{{font-size:2rem;font-weight:850;color:#0e6a7b}}
table{{border-collapse:collapse;width:100%;background:#fff;border-radius:16px;overflow:hidden;margin-top:10px}}
th,td{{border-bottom:1px solid #e6edf5;text-align:left;padding:10px;vertical-align:top;font-size:.9rem}}
th{{background:#0b2742;color:#fff}}
.badge{{display:inline-block;background:#eaf6f7;color:#0e6a7b;border-radius:999px;padding:6px 10px;font-weight:700}}
</style></head><body>
<header><strong>SCC Nexus · AQ26</strong> · Incinerator monitoring overlay discovery V3</header>
<main>
<section class='hero'><span class='badge'>Candidate discovery · not validation</span><h1>Incinerator monitoring overlay discovery V3</h1><p>Facility aliases are normalised, already validated overlays are preserved, OpenAQ is queried with rate-limit handling, and candidates are classified for review before promotion.</p></section>
<section class='grid'>{cards}</section>
<section class='card'><h2>Facility overlay status</h2><table><thead><tr><th>Facility</th><th>Status</th><th>Best candidate</th><th>Score</th><th>Class</th></tr></thead><tbody>{''.join(status_html)}</tbody></table></section>
<section class='card'><h2>Selected candidates needing review</h2><table><thead><tr><th>Facility</th><th>Class</th><th>Candidate</th><th>Point</th><th>km</th><th>Pollutants</th><th>Score</th></tr></thead><tbody>{''.join(rows)}</tbody></table></section>
</main></body></html>"""
    path.write_text(html_doc, encoding="utf-8")


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--broad-register", default="configs/aq26_incinerator_register/UK_Incinerators_with_Controls_Full_v3.csv")
    ap.add_argument("--validated-overlays", default="configs/aq26_incinerator_register/UK_Incinerators_with_DEFRA_Sites_v3_validated_Full.csv")
    ap.add_argument("--output-root", default="site_public/data/focus/overlays_v3")
    ap.add_argument("--site-root", default="site_public")
    ap.add_argument("--radius-km", type=float, default=25.0)
    ap.add_argument("--limit-per-query", type=int, default=100)
    ap.add_argument("--max-facilities", type=int, default=10, help="0 means all remaining facilities")
    ap.add_argument("--live-openaq", action="store_true")
    ap.add_argument("--write-page", action="store_true")
    ap.add_argument("--min-score", type=int, default=35)
    ap.add_argument("--sleep", type=float, default=2.5)
    ap.add_argument("--max-retries", type=int, default=3)
    ap.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    ap.add_argument("--exhaustive", action="store_true", help="Also run extra bbox/diagnostic lon-lat variants. Use sparingly to avoid rate limiting.")
    ap.add_argument("--use-v2-cache", action="store_true")
    ap.add_argument("--v2-cache", default="site_public/data/focus/overlays_v2/candidate_monitoring_overlays.csv")
    args = ap.parse_args(argv)

    broad_rows = read_csv_dicts(Path(args.broad_register))
    valid_rows = read_csv_dicts(Path(args.validated_overlays))
    done = validated_keys(valid_rows)
    remaining_all = [r for r in broad_rows if facility_key(r) not in done]
    remaining = remaining_all if args.max_facilities == 0 else remaining_all[: max(0, args.max_facilities)]

    out = Path(args.output_root)
    site = Path(args.site_root)
    out.mkdir(parents=True, exist_ok=True)
    site.mkdir(parents=True, exist_ok=True)

    api_key = os.environ.get("OPENAQ_API_KEY", "").strip() or None
    candidate_rows: List[Dict[str, Any]] = []
    diagnostics: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []
    rate_limit_seen = False

    wanted = {facility_key(r) for r in remaining}
    if args.use_v2_cache:
        cached = load_cached_candidates(Path(args.v2_cache), wanted)
        # Re-score cached rows using original query point if possible; this preserves useful prior results without API calls.
        fac_by_key = {facility_key(r): r for r in broad_rows}
        for cr in cached:
            fk = str(cr.get("facility_key") or canonical_facility_key(str(cr.get("facility") or "")))
            fac = fac_by_key.get(fk)
            if not fac:
                continue
            lat = safe_float(cr.get("query_point_lat"))
            lon = safe_float(cr.get("query_point_lon"))
            role = str(cr.get("query_point_role") or "cached")
            if lat is None or lon is None:
                flat, flon = get_facility_latlon(fac)
                lat, lon, role = flat, flon, "facility"
            if lat is not None and lon is not None:
                candidate_rows.append(score_candidate(fac, role, lat, lon, cached_row_to_candidate(cr), "cached_v2_openaq_candidate"))
        diagnostics.append({"ok": True, "method": "v2_cache_import", "result_count": len(cached), "http_status": "cache"})

    if args.live_openaq:
        for idx, fac in enumerate(remaining, start=1):
            points: List[Tuple[str, float, float]] = []
            flat, flon = get_facility_latlon(fac)
            clat, clon = get_control_latlon(fac)
            if flat is not None and flon is not None:
                points.append(("facility", flat, flon))
            if clat is not None and clon is not None:
                points.append(("control", clat, clon))
            if not points:
                errors.append({"facility": fac.get("Facility", ""), "facility_key": facility_key(fac), "error": "no usable lat/lon coordinates in register"})
                continue
            for role, lat, lon in points:
                cands, diags, hit429 = query_openaq_candidates(lat, lon, args.radius_km, args.limit_per_query, api_key, args.sleep, args.max_retries, args.exhaustive, args.timeout)
                if hit429:
                    rate_limit_seen = True
                for d in diags:
                    d.update({"facility": fac.get("Facility", ""), "facility_key": facility_key(fac), "query_point_role": role, "query_lat": lat, "query_lon": lon})
                    diagnostics.append(d)
                for cand in cands:
                    candidate_rows.append(score_candidate(fac, role, lat, lon, cand, "OpenAQ v3 locations"))
    else:
        diagnostics.append({"ok": True, "method": "live_openaq_disabled", "message": "Run with --live-openaq to query OpenAQ."})

    # De-duplicate; keep highest score for each facility + candidate + query role.
    dedup: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
    for r in candidate_rows:
        key = (str(r.get("facility_key", "")), str(r.get("openaq_location_id") or r.get("monitoring_site_name")), str(r.get("query_point_role", "")))
        if key not in dedup or int(r.get("relevance_score") or 0) > int(dedup[key].get("relevance_score") or 0):
            dedup[key] = r
    candidate_rows = sorted(dedup.values(), key=lambda x: (str(x.get("facility", "")), -int(x.get("relevance_score") or 0)))

    selected: List[Dict[str, Any]] = []
    seen_counts: Dict[Tuple[str, str], int] = {}
    for r in candidate_rows:
        if int(r.get("relevance_score") or 0) < args.min_score:
            continue
        key = (str(r.get("facility_key", "")), str(r.get("query_point_role", "")))
        if seen_counts.get(key, 0) >= 3:
            continue
        selected.append(r)
        seen_counts[key] = seen_counts.get(key, 0) + 1

    selected_by_fac: Dict[str, List[Dict[str, Any]]] = {}
    for r in selected:
        selected_by_fac.setdefault(str(r.get("facility_key")), []).append(r)

    valid_by_key = {facility_key(r): r for r in valid_rows}
    status_rows: List[Dict[str, Any]] = []
    for fac in broad_rows:
        fk = facility_key(fac)
        if fk in valid_by_key:
            vr = valid_by_key[fk]
            status_rows.append({
                "facility": fac.get("Facility", ""),
                "facility_key": fk,
                "overlay_status": "validated_existing_overlay",
                "best_candidate_site": vr.get("DEFRA_Site_Name", ""),
                "best_candidate_score": "validated",
                "best_candidate_class": vr.get("DEFRA_Mapping_Confidence", ""),
                "suggested_action": "keep_validated_overlay",
            })
        elif selected_by_fac.get(fk):
            best = sorted(selected_by_fac[fk], key=lambda x: -int(x.get("relevance_score") or 0))[0]
            status_rows.append({
                "facility": fac.get("Facility", ""),
                "facility_key": fk,
                "overlay_status": "candidate_overlay_needs_review",
                "best_candidate_site": best.get("monitoring_site_name", ""),
                "best_candidate_score": best.get("relevance_score", ""),
                "best_candidate_class": best.get("candidate_review_class", ""),
                "suggested_action": best.get("suggested_action", ""),
            })
        else:
            status_rows.append({
                "facility": fac.get("Facility", ""),
                "facility_key": fk,
                "overlay_status": "no_candidate_selected_yet",
                "best_candidate_site": "",
                "best_candidate_score": "",
                "best_candidate_class": "",
                "suggested_action": "needs_defra_local_waqi_manual_discovery_or_retry",
            })

    http_429 = sum(1 for d in diagnostics if str(d.get("http_status")) == "429")
    http_200 = sum(1 for d in diagnostics if str(d.get("http_status")) == "200")
    facilities_with_selected = len({r.get("facility_key") for r in selected})
    summary = {
        "generated_utc": utc_now(),
        "broad_facilities": len(broad_rows),
        "validated_overlays": len(valid_rows),
        "validated_facility_keys_after_aliasing": len(done),
        "remaining_facilities_total": len(remaining_all),
        "remaining_facilities_queried_this_run": len(remaining),
        "live_openaq": bool(args.live_openaq),
        "use_v2_cache": bool(args.use_v2_cache),
        "requested_radius_km": args.radius_km,
        "openaq_point_radius_cap_m": MAX_OPENAQ_RADIUS_M,
        "limit_per_query": args.limit_per_query,
        "sleep_seconds": args.sleep,
        "max_retries": args.max_retries,
        "exhaustive": bool(args.exhaustive),
        "candidate_rows": len(candidate_rows),
        "selected_candidates": len(selected),
        "facilities_with_selected_candidates": facilities_with_selected,
        "diagnostic_rows": len(diagnostics),
        "http_200_calls": http_200,
        "rate_limited_calls": http_429,
        "error_rows": len(errors),
        "rate_limit_seen": bool(rate_limit_seen or http_429),
        "status": "candidate_discovery_complete_with_rate_limit" if http_429 else "candidate_discovery_complete",
        "note": "New candidates are not validated. Promote only after manual/source review. Public pages should show summary counts, not raw diagnostics.",
    }

    write_csv(out / "validated_defra_overlays.csv", valid_rows)
    write_csv(out / "remaining_overlay_queue.csv", remaining_all)
    write_csv(out / "remaining_overlay_batch_queried.csv", remaining)
    write_csv(out / "candidate_monitoring_overlays.csv", candidate_rows)
    write_csv(out / "selected_candidate_overlays_needing_review.csv", selected)
    write_csv(out / "facility_overlay_status.csv", status_rows)
    write_csv(out / "openaq_query_diagnostics.csv", diagnostics)
    write_json(out / "overlay_discovery_errors.json", errors)
    write_json(out / "incinerator_overlay_summary.json", summary)

    if args.write_page:
        build_page(site / "incinerator-overlays.html", summary, selected, status_rows)

    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
