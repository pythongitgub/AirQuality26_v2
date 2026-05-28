#!/usr/bin/env python3
"""
AQ26 Remaining Incinerator Overlay Finder V3.2
Stateful batching replacement.

Purpose:
- Use the England/Wales incinerator register as the spine.
- Keep already validated facilities out of the query queue.
- Keep facilities with previous candidate overlays out of subsequent batches unless forced.
- Query OpenAQ safely with latitude,longitude, <=25 km radius, bbox fallback, retry/backoff.
- Write this-run + cumulative candidate files and a facility status table.

No candidate is promoted to validated automatically. All new matches remain review candidates.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
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

ALIAS_CANONICAL = {
    "tyseley erf": "tyseley",
    "tyseley efw": "tyseley",
    "tyseley energy recovery facility": "tyseley",
    "riverside rr erf": "riverside_resource_recovery",
    "riverside resource recovery": "riverside_resource_recovery",
    "riverside resource recovery facility": "riverside_resource_recovery",
    "runcorn efw": "runcorn",
    "runcorn tps": "runcorn",
    "runcorn thermal power station": "runcorn",
    "newhaven erf": "newhaven",
    "newhaven energy recovery facility": "newhaven",
    "veolia newhaven": "newhaven",
    "selchp": "selchp",
    "south east london combined heat and power": "selchp",
    "london ecopark": "london_ecopark",
    "leeds rerf": "leeds_rerf",
    "leeds recycling and energy recovery facility": "leeds_rerf",
    "sheffield erf": "sheffield",
    "sheffield energy recovery facility": "sheffield",
}

FACILITY_COLS = [
    "facility", "facility_name", "Facility", "Facility Name", "Incinerator", "Site", "site_name", "name", "Name"
]
OPERATOR_COLS = ["operator", "Operator", "Operator Name", "company", "Company"]
LAT_COLS = ["latitude", "lat", "Latitude", "Lat", "Facility_Latitude", "Facility Latitude", "Facility_Lat", "Facility Lat", "facility_lat"]
LON_COLS = ["longitude", "lon", "lng", "Longitude", "Lon", "Lng", "Facility_Longitude", "Facility Longitude", "Facility_Lon", "Facility Lon", "facility_lon"]
EASTING_COLS = ["easting", "Easting", "Facility_Easting", "Facility Easting", "facility_easting"]
NORTHING_COLS = ["northing", "Northing", "Facility_Northing", "Facility Northing", "facility_northing"]
CTRL_LAT_COLS = ["control_latitude", "control_lat", "Control_Latitude", "Control Latitude", "Control_Lat", "Control Lat"]
CTRL_LON_COLS = ["control_longitude", "control_lon", "control_lng", "Control_Longitude", "Control Longitude", "Control_Lon", "Control Lon"]
CTRL_EASTING_COLS = ["control_easting", "Control_Easting", "Control Easting"]
CTRL_NORTHING_COLS = ["control_northing", "Control_Northing", "Control Northing"]
CONTROL_NAME_COLS = ["control_site", "Control Site", "Control_Site", "control_name", "Control Name", "Control"]
VALIDATED_SITE_COLS = ["defra_site_name", "DEFRA_Site_Name", "DEFRA Site Name", "AURN Site", "aurn_site", "Monitoring Site", "site_name"]
VALIDATED_CODE_COLS = ["defra_site_code", "DEFRA_Site_Code", "DEFRA Site Code", "site_code", "Site Code", "AURN Code"]

POLLUTANT_WEIGHTS = {
    "no2": 10, "pm25": 10, "pm2.5": 10, "pm10": 10, "so2": 8, "o3": 6, "co": 5,
    "nox": 5, "no": 3, "voc": 4, "benzene": 4, "black carbon": 3,
}
OFFICIAL_TERMS = ["defra", "aurn", "uka", "uk-a", "london air quality", "laqn", "air quality england", "government"]
COMMUNITY_TERMS = ["airgradient", "purpleair", "sensor.community", "uradmonitor", "low cost"]


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def norm_text(s: Any) -> str:
    if s is None:
        return ""
    return str(s).strip()


def slug(s: str) -> str:
    s = norm_text(s).lower()
    s = s.replace("&", " and ")
    s = re.sub(r"\b(energy recovery facility|resource recovery facility|energy from waste|waste to energy)\b", "", s)
    s = re.sub(r"\b(erf|efw|wt[e]|incinerator|facility|plant|power station|thermal power station)\b", "", s)
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return s


def facility_key(name: str) -> str:
    raw = norm_text(name).lower()
    raw_clean = re.sub(r"[^a-z0-9]+", " ", raw).strip()
    if raw_clean in ALIAS_CANONICAL:
        return ALIAS_CANONICAL[raw_clean]
    s = slug(name)
    # extra broad aliases after generic cleanup
    for k, v in ALIAS_CANONICAL.items():
        if slug(k) == s or slug(v) == s:
            return v
    return s


def pick(row: Dict[str, Any], candidates: Iterable[str]) -> str:
    for c in candidates:
        if c in row and norm_text(row.get(c)) != "":
            return norm_text(row.get(c))
    # case-insensitive fallback
    lower = {k.lower().strip(): k for k in row.keys()}
    for c in candidates:
        k = lower.get(c.lower().strip())
        if k and norm_text(row.get(k)) != "":
            return norm_text(row.get(k))
    return ""


def to_float(v: Any) -> Optional[float]:
    s = norm_text(v).replace(",", "")
    if not s:
        return None
    try:
        return float(s)
    except Exception:
        return None


def load_csv(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return [dict(r) for r in csv.DictReader(f)]


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
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


def bng_to_wgs84(easting: Optional[float], northing: Optional[float]) -> Tuple[Optional[float], Optional[float]]:
    if easting is None or northing is None:
        return None, None
    try:
        from pyproj import Transformer  # type: ignore
        transformer = Transformer.from_crs("EPSG:27700", "EPSG:4326", always_xy=True)
        lon, lat = transformer.transform(easting, northing)
        return float(lat), float(lon)
    except Exception:
        return None, None


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0088
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def point_from_row(row: Dict[str, Any], lat_cols: List[str], lon_cols: List[str], east_cols: List[str], north_cols: List[str]) -> Tuple[Optional[float], Optional[float], str]:
    lat = to_float(pick(row, lat_cols))
    lon = to_float(pick(row, lon_cols))
    if lat is not None and lon is not None:
        return lat, lon, "lat_lon"
    east = to_float(pick(row, east_cols))
    north = to_float(pick(row, north_cols))
    lat2, lon2 = bng_to_wgs84(east, north)
    if lat2 is not None and lon2 is not None:
        return lat2, lon2, "bng_converted"
    return None, None, "missing"


@dataclass
class Facility:
    facility_name: str
    facility_key: str
    operator: str
    control_name: str
    facility_lat: Optional[float]
    facility_lon: Optional[float]
    facility_coord_source: str
    control_lat: Optional[float]
    control_lon: Optional[float]
    control_coord_source: str
    raw: Dict[str, Any]


def parse_facilities(rows: List[Dict[str, str]]) -> List[Facility]:
    facilities: List[Facility] = []
    for row in rows:
        name = pick(row, FACILITY_COLS)
        if not name:
            continue
        flat, flon, fsrc = point_from_row(row, LAT_COLS, LON_COLS, EASTING_COLS, NORTHING_COLS)
        clat, clon, csrc = point_from_row(row, CTRL_LAT_COLS, CTRL_LON_COLS, CTRL_EASTING_COLS, CTRL_NORTHING_COLS)
        facilities.append(Facility(
            facility_name=name,
            facility_key=facility_key(name),
            operator=pick(row, OPERATOR_COLS),
            control_name=pick(row, CONTROL_NAME_COLS),
            facility_lat=flat,
            facility_lon=flon,
            facility_coord_source=fsrc,
            control_lat=clat,
            control_lon=clon,
            control_coord_source=csrc,
            raw=row,
        ))
    # de-dupe by key, keep first complete coord row
    out: Dict[str, Facility] = {}
    for f in facilities:
        old = out.get(f.facility_key)
        if old is None:
            out[f.facility_key] = f
        elif old.facility_lat is None and f.facility_lat is not None:
            out[f.facility_key] = f
    return list(out.values())


def validated_keys(rows: List[Dict[str, str]]) -> set:
    keys = set()
    for row in rows:
        name = pick(row, FACILITY_COLS)
        if name:
            keys.add(facility_key(name))
    return keys


def read_existing_candidate_keys(paths: List[Path]) -> set:
    keys = set()
    for path in paths:
        for row in load_csv(path):
            name = pick(row, ["facility_name", "facility", "Facility", "Facility Name"])
            key = pick(row, ["facility_key", "facility_id", "Facility Key"])
            status = pick(row, ["status", "overlay_status", "review_status"])
            if key:
                keys.add(facility_key(key)) if " " in key else keys.add(key)
            elif name:
                keys.add(facility_key(name))
            # facility_overlay_status rows can indicate candidates under review
            if name and status and "candidate" in status.lower():
                keys.add(facility_key(name))
    return {k for k in keys if k}


def load_v2_cache(output_root: Path) -> List[Dict[str, str]]:
    candidates = []
    for p in [
        output_root.parent / "overlays_v2" / "candidate_monitoring_overlays.csv",
        output_root.parent / "overlays_v2" / "selected_candidate_overlays_needing_review.csv",
        output_root / "candidate_monitoring_overlays.csv",
    ]:
        candidates.extend(load_csv(p))
    return candidates


def extract_parameters(loc: Dict[str, Any]) -> List[str]:
    vals: List[str] = []
    for key in ["parameters", "parameter", "sensors"]:
        x = loc.get(key)
        if isinstance(x, list):
            for item in x:
                if isinstance(item, dict):
                    vals.append(norm_text(item.get("name") or item.get("parameter") or item.get("displayName") or item.get("parameter_name") or item.get("id")))
                else:
                    vals.append(norm_text(item))
    return sorted({v for v in vals if v})


def loc_coord(loc: Dict[str, Any]) -> Tuple[Optional[float], Optional[float]]:
    c = loc.get("coordinates")
    if isinstance(c, dict):
        return to_float(c.get("latitude")), to_float(c.get("longitude"))
    return None, None


def source_name(loc: Dict[str, Any]) -> str:
    parts = []
    for k in ["provider", "owner", "manufacturer"]:
        v = loc.get(k)
        if isinstance(v, dict):
            parts.append(norm_text(v.get("name") or v.get("id")))
        else:
            parts.append(norm_text(v))
    return " | ".join([p for p in parts if p])


def make_request(url: str, api_key: str, max_retries: int, sleep_seconds: float) -> Tuple[int, str, Dict[str, Any], float]:
    headers = {"User-Agent": "AQ26-incinerator-overlay-v3.2"}
    if api_key:
        headers["X-API-Key"] = api_key
    last_text = ""
    for attempt in range(max_retries + 1):
        t0 = time.time()
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                text = resp.read().decode("utf-8", errors="replace")
                return int(resp.status), text[:1000], json.loads(text), time.time() - t0
        except urllib.error.HTTPError as e:
            last_text = e.read().decode("utf-8", errors="replace")[:1500]
            if e.code == 429 and attempt < max_retries:
                retry_after = e.headers.get("Retry-After")
                try:
                    wait = float(retry_after) if retry_after else sleep_seconds * (attempt + 2)
                except Exception:
                    wait = sleep_seconds * (attempt + 2)
                time.sleep(max(wait, sleep_seconds))
                continue
            return int(e.code), last_text, {}, time.time() - t0
        except Exception as e:
            last_text = repr(e)
            if attempt < max_retries:
                time.sleep(sleep_seconds * (attempt + 1))
                continue
            return 0, last_text, {}, 0.0
    return 0, last_text, {}, 0.0


def bbox_for(lat: float, lon: float, radius_km: float) -> str:
    dlat = radius_km / 111.0
    dlon = radius_km / max(20.0, 111.0 * math.cos(math.radians(lat)))
    return f"{lon-dlon:.5f},{lat-dlat:.5f},{lon+dlon:.5f},{lat+dlat:.5f}"


def build_urls(lat: float, lon: float, radius_km: float, limit: int, exhaustive: bool) -> List[Tuple[str, str]]:
    r_m = int(min(max(radius_km, 0.5), 25.0) * 1000)
    urls = []
    base_params = {"limit": str(limit), "iso": "GB"}
    for label, rad in [("coordinates_lat_lon_radius_capped", r_m), ("coordinates_lat_lon_radius_10000", min(r_m, 10000))]:
        params = dict(base_params)
        params.update({"coordinates": f"{lat:.5f},{lon:.5f}", "radius": str(rad)})
        urls.append((label, OPENAQ_BASE + "?" + urllib.parse.urlencode(params)))
    for label, rk in [("bbox_25km_lonlat", min(radius_km, 25.0)), ("bbox_10km_lonlat", min(radius_km, 10.0))]:
        params = dict(base_params)
        params.update({"bbox": bbox_for(lat, lon, rk)})
        urls.append((label, OPENAQ_BASE + "?" + urllib.parse.urlencode(params)))
    if exhaustive:
        # diagnostic only; OpenAQ docs expect lat,lon for coordinates, so this should not dominate scoring
        params = dict(base_params)
        params.update({"coordinates": f"{lon:.5f},{lat:.5f}", "radius": str(min(r_m, 10000))})
        urls.append(("diagnostic_lon_lat_coordinates", OPENAQ_BASE + "?" + urllib.parse.urlencode(params)))
    return urls


def score_candidate(f: Facility, query_role: str, query_lat: float, query_lon: float, loc: Dict[str, Any]) -> Dict[str, Any]:
    lat, lon = loc_coord(loc)
    if lat is None or lon is None:
        dist_query = None
    else:
        dist_query = haversine_km(query_lat, query_lon, lat, lon)
    dist_fac = haversine_km(f.facility_lat, f.facility_lon, lat, lon) if (lat is not None and lon is not None and f.facility_lat is not None and f.facility_lon is not None) else None
    dist_ctrl = haversine_km(f.control_lat, f.control_lon, lat, lon) if (lat is not None and lon is not None and f.control_lat is not None and f.control_lon is not None) else None
    params = extract_parameters(loc)
    params_l = [p.lower().replace("µ", "u") for p in params]
    provider = source_name(loc)
    name = norm_text(loc.get("name") or loc.get("locality") or loc.get("id"))
    name_l = name.lower()
    provider_l = provider.lower()
    score = 25
    d = dist_query if dist_query is not None else 99
    if d <= 1: score += 35
    elif d <= 3: score += 30
    elif d <= 5: score += 24
    elif d <= 10: score += 16
    elif d <= 15: score += 10
    elif d <= 25: score += 5
    else: score -= 10
    for p, w in POLLUTANT_WEIGHTS.items():
        if any(p in x for x in params_l):
            score += w
    if any(t in provider_l or t in name_l for t in OFFICIAL_TERMS) or re.search(r"\bUKA\d{5}\b", name):
        score += 18
    if any(t in provider_l or t in name_l for t in COMMUNITY_TERMS):
        score -= 12
    score = max(0, min(100, score))
    if score >= 85:
        cls = "high_confidence_official_candidate" if (any(t in provider_l or t in name_l for t in OFFICIAL_TERMS) or "uka" in name_l) else "high_confidence_candidate_needs_review"
    elif score >= 70:
        cls = "local_or_official_candidate_needs_review"
    elif score >= 50:
        cls = "plausible_candidate_needs_review"
    elif any(t in provider_l or t in name_l for t in COMMUNITY_TERMS):
        cls = "supporting_context_community_sensor"
    else:
        cls = "manual_review_low_confidence"
    return {
        "facility_name": f.facility_name,
        "facility_key": f.facility_key,
        "operator": f.operator,
        "control_name": f.control_name,
        "query_role": query_role,
        "candidate_location_id": norm_text(loc.get("id")),
        "candidate_location_name": name,
        "candidate_provider": provider,
        "candidate_latitude": lat if lat is not None else "",
        "candidate_longitude": lon if lon is not None else "",
        "distance_from_query_km": round(dist_query, 3) if dist_query is not None else "",
        "distance_from_facility_km": round(dist_fac, 3) if dist_fac is not None else "",
        "distance_from_control_km": round(dist_ctrl, 3) if dist_ctrl is not None else "",
        "pollutants": "; ".join(params),
        "score": score,
        "candidate_class": cls,
        "review_status": "candidate_needs_review",
    }


def dedupe_candidates(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    best: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
    for r in rows:
        loc_key = norm_text(r.get("candidate_location_id")) or slug(norm_text(r.get("candidate_location_name")))
        key = (norm_text(r.get("facility_key")), loc_key, norm_text(r.get("query_role")))
        old = best.get(key)
        if old is None or float(r.get("score") or 0) > float(old.get("score") or 0):
            best[key] = r
    return sorted(best.values(), key=lambda x: (x.get("facility_name", ""), -float(x.get("score") or 0)))


def selected_candidates(rows: List[Dict[str, Any]], min_score: float) -> List[Dict[str, Any]]:
    return [r for r in dedupe_candidates(rows) if float(r.get("score") or 0) >= min_score]


def merge_cumulative(existing: List[Dict[str, str]], new: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    combined: List[Dict[str, Any]] = []
    combined.extend(existing)
    combined.extend(new)
    best: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
    for r in combined:
        fk = norm_text(r.get("facility_key")) or facility_key(norm_text(r.get("facility_name")))
        loc = norm_text(r.get("candidate_location_id")) or slug(norm_text(r.get("candidate_location_name")))
        role = norm_text(r.get("query_role"))
        key = (fk, loc, role)
        old = best.get(key)
        if old is None or float(r.get("score") or 0) > float(old.get("score") or 0):
            rr = dict(r)
            rr["facility_key"] = fk
            best[key] = rr
    return sorted(best.values(), key=lambda x: (x.get("facility_name", ""), -float(x.get("score") or 0)))


def build_page(site_root: Path, summary: Dict[str, Any], status_rows: List[Dict[str, Any]], selected_rows: List[Dict[str, Any]]) -> None:
    site_root.mkdir(parents=True, exist_ok=True)
    css = """
    body{margin:0;font-family:Inter,Arial,sans-serif;background:#f6fbff;color:#102033} .top{background:#fff;border-bottom:1px solid #d9e7f2;padding:18px 24px;display:flex;gap:18px;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:5}.brand{font-weight:900;color:#0b3558}.nav a{margin:0 8px;color:#0b5c7a;text-decoration:none;font-weight:700}.hero{background:linear-gradient(120deg,#073b63,#0f766e,#3b82f6);color:white;padding:46px 24px}.wrap{max-width:1180px;margin:auto}.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:14px;margin:22px 0}.card{background:white;color:#102033;border-radius:18px;padding:18px;box-shadow:0 8px 24px rgba(0,0,0,.08)}.num{font-size:32px;font-weight:900;color:#073b63}.pill{display:inline-block;border-radius:999px;padding:5px 10px;background:#e7f3ff;margin:3px;font-size:12px;font-weight:700}table{width:100%;border-collapse:collapse;background:white;border-radius:14px;overflow:hidden}th,td{border-bottom:1px solid #e5eef6;padding:10px;text-align:left;vertical-align:top}th{background:#eaf5ff;color:#073b63} .small{font-size:12px;color:#536173} .status-good{color:#087f5b;font-weight:800}.status-warn{color:#b45309;font-weight:800}.status-miss{color:#b91c1c;font-weight:800}
    """
    head_rows = "".join(
        f"<tr><td>{r.get('facility_name','')}</td><td>{r.get('overlay_status','')}</td><td>{r.get('best_candidate','')}</td><td>{r.get('best_score','')}</td><td>{r.get('notes','')}</td></tr>"
        for r in status_rows[:80]
    )
    cand_rows = "".join(
        f"<tr><td>{r.get('facility_name','')}</td><td>{r.get('candidate_location_name','')}</td><td>{r.get('candidate_provider','')}</td><td>{r.get('distance_from_query_km','')}</td><td>{r.get('pollutants','')}</td><td>{r.get('score','')}</td><td>{r.get('candidate_class','')}</td></tr>"
        for r in selected_rows[:120]
    )
    html = f"""<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>AQ26 Incinerator Monitoring Overlays</title><style>{css}</style></head><body>
    <header class='top'><div class='brand'>SCC Nexus · AQ26 Incinerator Overlays</div><nav class='nav'><a href='index.html'>Home</a><a href='incinerators.html'>Incinerators</a><a href='newhaven.html'>Newhaven</a><a href='unredacted/'>Unredacted</a></nav></header>
    <section class='hero'><div class='wrap'><p class='small' style='color:#dff7ff'>Facility-led evidence spine</p><h1>Incinerator monitoring overlay discovery</h1><p>Validated and candidate monitoring overlays for England/Wales incinerator and energy-from-waste facilities. Candidates require review before promotion.</p></div></section>
    <main class='wrap'>
    <section class='cards'>
      <div class='card'><div class='num'>{summary.get('broad_facilities',0)}</div><b>Facilities in register</b></div>
      <div class='card'><div class='num'>{summary.get('validated_overlays',0)}</div><b>Validated overlays</b></div>
      <div class='card'><div class='num'>{summary.get('cumulative_candidate_facilities',0)}</div><b>Candidate-covered facilities</b></div>
      <div class='card'><div class='num'>{summary.get('no_candidate_selected_total',0)}</div><b>Still in discovery</b></div>
      <div class='card'><div class='num'>{summary.get('rate_limited_calls',0)}</div><b>Rate-limited calls this run</b></div>
    </section>
    <section class='card'><h2>Status by facility</h2><table><thead><tr><th>Facility</th><th>Status</th><th>Best candidate</th><th>Score</th><th>Notes</th></tr></thead><tbody>{head_rows}</tbody></table></section>
    <section class='card'><h2>Review candidates</h2><p class='small'>These are not validated overlays. Use the unredacted CSVs for full scoring and diagnostics.</p><table><thead><tr><th>Facility</th><th>Candidate site</th><th>Provider</th><th>Distance km</th><th>Pollutants</th><th>Score</th><th>Class</th></tr></thead><tbody>{cand_rows}</tbody></table></section>
    </main><footer class='wrap small' style='padding:30px 0'>© SCC Nexus / AQ26 · Candidate monitoring overlays require review before external use.</footer></body></html>"""
    (site_root / "incinerator-overlays.html").write_text(html, encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--broad-register", default="configs/aq26_incinerator_register/UK_Incinerators_with_Controls_Full_v3.csv")
    ap.add_argument("--validated-overlays", default="configs/aq26_incinerator_register/UK_Incinerators_with_DEFRA_Sites_v3_validated_Full.csv")
    ap.add_argument("--output-root", default="site_public/data/focus/overlays_v3")
    ap.add_argument("--site-root", default="site_public")
    ap.add_argument("--live-openaq", action="store_true")
    ap.add_argument("--use-v2-cache", action="store_true")
    ap.add_argument("--skip-existing-candidates", action="store_true")
    ap.add_argument("--force-requery", action="store_true")
    ap.add_argument("--batch-offset", type=int, default=0)
    ap.add_argument("--max-facilities", type=int, default=10)
    ap.add_argument("--radius-km", type=float, default=25.0)
    ap.add_argument("--limit-per-query", type=int, default=100)
    ap.add_argument("--min-score", type=float, default=35.0)
    ap.add_argument("--sleep-seconds", type=float, default=3.0)
    ap.add_argument("--max-retries", type=int, default=3)
    ap.add_argument("--exhaustive", action="store_true")
    ap.add_argument("--write-page", action="store_true")
    args = ap.parse_args()

    output_root = Path(args.output_root)
    site_root = Path(args.site_root)
    output_root.mkdir(parents=True, exist_ok=True)

    broad_rows = load_csv(Path(args.broad_register))
    validated_rows = load_csv(Path(args.validated_overlays))
    facilities = parse_facilities(broad_rows)
    val_keys = validated_keys(validated_rows)

    prev_selected_paths = [
        output_root / "selected_candidate_overlays_cumulative.csv",
        output_root / "selected_candidate_overlays_needing_review.csv",
        output_root / "selected_candidate_overlays_this_run.csv",
        output_root / "facility_overlay_status_cumulative.csv",
        output_root / "facility_overlay_status.csv",
    ]
    existing_candidate_keys = read_existing_candidate_keys(prev_selected_paths)

    base_remaining = [f for f in facilities if f.facility_key not in val_keys]
    skip_keys = set()
    if args.skip_existing_candidates and not args.force_requery:
        skip_keys |= existing_candidate_keys
    query_pool = [f for f in base_remaining if f.facility_key not in skip_keys]
    if args.batch_offset:
        query_pool = query_pool[max(0, args.batch_offset):]
    if args.max_facilities and args.max_facilities > 0:
        query_facilities = query_pool[: args.max_facilities]
    else:
        query_facilities = query_pool

    queue_rows = []
    for f in base_remaining:
        queue_rows.append({
            "facility_name": f.facility_name,
            "facility_key": f.facility_key,
            "operator": f.operator,
            "control_name": f.control_name,
            "facility_lat": f.facility_lat if f.facility_lat is not None else "",
            "facility_lon": f.facility_lon if f.facility_lon is not None else "",
            "control_lat": f.control_lat if f.control_lat is not None else "",
            "control_lon": f.control_lon if f.control_lon is not None else "",
            "queue_status": "skipped_existing_candidate" if f.facility_key in skip_keys else "queued_for_query",
        })

    api_key = os.getenv("OPENAQ_API_KEY", "")
    diagnostics: List[Dict[str, Any]] = []
    candidates: List[Dict[str, Any]] = []

    # optional cached candidates for scoring only; not counted as this-run API diagnostics
    if args.use_v2_cache:
        for r in load_v2_cache(output_root):
            fk = norm_text(r.get("facility_key")) or facility_key(norm_text(r.get("facility_name")))
            if fk and (not args.skip_existing_candidates or args.force_requery or fk not in skip_keys):
                rr = dict(r)
                rr["source_layer"] = rr.get("source_layer") or "v2_cache"
                candidates.append(rr)

    if args.live_openaq:
        for f in query_facilities:
            query_points = []
            if f.facility_lat is not None and f.facility_lon is not None:
                query_points.append(("facility", f.facility_lat, f.facility_lon))
            if f.control_lat is not None and f.control_lon is not None:
                query_points.append(("control", f.control_lat, f.control_lon))
            if not query_points:
                diagnostics.append({"facility_name": f.facility_name, "facility_key": f.facility_key, "method": "no_coordinates", "status": "skipped", "url": "", "result_count": 0, "error_excerpt": "no usable latitude/longitude or converted easting/northing"})
                continue
            for role, lat, lon in query_points:
                for method, url in build_urls(lat, lon, args.radius_km, args.limit_per_query, args.exhaustive):
                    status, text, payload, elapsed = make_request(url, api_key, args.max_retries, args.sleep_seconds)
                    results = payload.get("results") if isinstance(payload, dict) else []
                    if not isinstance(results, list):
                        results = []
                    diagnostics.append({
                        "facility_name": f.facility_name,
                        "facility_key": f.facility_key,
                        "query_role": role,
                        "method": method,
                        "status": status,
                        "url": url,
                        "result_count": len(results),
                        "elapsed_seconds": round(elapsed, 3),
                        "error_excerpt": text if status not in (200, 201) else "",
                    })
                    if status in (200, 201):
                        for loc in results:
                            if isinstance(loc, dict):
                                row = score_candidate(f, role, lat, lon, loc)
                                row["source_layer"] = "openaq_live"
                                row["query_method"] = method
                                candidates.append(row)
                    time.sleep(max(0.0, args.sleep_seconds))

    candidates_this_run = [r for r in candidates if r.get("source_layer") == "openaq_live"]
    candidate_rows = dedupe_candidates(candidates_this_run)
    selected_this_run = selected_candidates(candidate_rows, args.min_score)

    existing_cumulative = load_csv(output_root / "selected_candidate_overlays_cumulative.csv")
    # If no cumulative yet, seed from prior selected file if present.
    if not existing_cumulative:
        existing_cumulative = load_csv(output_root / "selected_candidate_overlays_needing_review.csv")
    selected_cumulative = merge_cumulative(existing_cumulative, selected_this_run)

    cumulative_keys = {norm_text(r.get("facility_key")) or facility_key(norm_text(r.get("facility_name"))) for r in selected_cumulative}
    cumulative_keys = {k for k in cumulative_keys if k}

    # best candidate by facility from cumulative
    best_by_fac: Dict[str, Dict[str, Any]] = {}
    for r in selected_cumulative:
        fk = norm_text(r.get("facility_key")) or facility_key(norm_text(r.get("facility_name")))
        if not fk:
            continue
        old = best_by_fac.get(fk)
        if old is None or float(r.get("score") or 0) > float(old.get("score") or 0):
            best_by_fac[fk] = r

    status_rows: List[Dict[str, Any]] = []
    for f in facilities:
        if f.facility_key in val_keys:
            st = "validated_existing_overlay"
            best = "validated overlay file"
            score = ""
            notes = "Already in validated DEFRA/AURN overlay register."
        elif f.facility_key in cumulative_keys:
            st = "candidate_overlay_needs_review"
            b = best_by_fac.get(f.facility_key, {})
            best = b.get("candidate_location_name", "candidate present")
            score = b.get("score", "")
            notes = b.get("candidate_class", "Candidate requires review before validation.")
        else:
            st = "no_candidate_selected_yet"
            best = ""
            score = ""
            notes = "Needs further discovery, lower threshold, local source/DEFRA lookup, or manual review."
        status_rows.append({
            "facility_name": f.facility_name,
            "facility_key": f.facility_key,
            "operator": f.operator,
            "control_name": f.control_name,
            "overlay_status": st,
            "best_candidate": best,
            "best_score": score,
            "notes": notes,
        })

    field_candidate = [
        "facility_name", "facility_key", "operator", "control_name", "query_role", "candidate_location_id", "candidate_location_name", "candidate_provider",
        "candidate_latitude", "candidate_longitude", "distance_from_query_km", "distance_from_facility_km", "distance_from_control_km", "pollutants", "score", "candidate_class", "review_status", "source_layer", "query_method",
    ]
    write_csv(output_root / "remaining_overlay_queue.csv", queue_rows)
    write_csv(output_root / "candidate_monitoring_overlays_this_run.csv", candidate_rows, field_candidate)
    write_csv(output_root / "selected_candidate_overlays_this_run.csv", selected_this_run, field_candidate)
    write_csv(output_root / "selected_candidate_overlays_cumulative.csv", selected_cumulative, field_candidate)
    # Backward-compatible filename expected by previous workflows/site
    write_csv(output_root / "selected_candidate_overlays_needing_review.csv", selected_cumulative, field_candidate)
    write_csv(output_root / "openaq_query_diagnostics.csv", diagnostics)
    write_csv(output_root / "facility_overlay_status_cumulative.csv", status_rows)
    write_csv(output_root / "facility_overlay_status.csv", status_rows)

    counts = {}
    for r in status_rows:
        counts[r["overlay_status"]] = counts.get(r["overlay_status"], 0) + 1
    summary = {
        "workflow_version": "v3.2_stateful_batching",
        "generated_at_utc": now_utc(),
        "broad_facilities": len(facilities),
        "validated_overlays": len(val_keys),
        "remaining_facilities_total": len(base_remaining),
        "existing_candidate_facilities_loaded": len(existing_candidate_keys),
        "previous_candidate_facilities_skipped": len([f for f in base_remaining if f.facility_key in skip_keys]),
        "query_pool_after_skip": len(query_pool),
        "batch_offset": args.batch_offset,
        "facilities_queried_this_run": len(query_facilities),
        "queried_facilities": [f.facility_name for f in query_facilities],
        "candidate_rows_this_run": len(candidate_rows),
        "selected_candidates_this_run": len(selected_this_run),
        "cumulative_selected_candidates": len(selected_cumulative),
        "cumulative_candidate_facilities": len(cumulative_keys),
        "status_counts": counts,
        "no_candidate_selected_total": counts.get("no_candidate_selected_yet", 0),
        "diagnostic_rows": len(diagnostics),
        "http_200_calls": sum(1 for d in diagnostics if str(d.get("status")) == "200"),
        "rate_limited_calls": sum(1 for d in diagnostics if str(d.get("status")) == "429"),
        "error_rows": sum(1 for d in diagnostics if str(d.get("status")) not in ("200", "201", "skipped")),
        "skip_existing_candidates": bool(args.skip_existing_candidates),
        "force_requery": bool(args.force_requery),
        "status": "candidate_discovery_complete",
    }
    write_json(output_root / "incinerator_overlay_summary.json", summary)

    if args.write_page:
        build_page(site_root, summary, status_rows, selected_cumulative)

    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
