#!/usr/bin/env python3
"""
AQ26 Remaining Incinerator Overlay Finder V3.1

Facility-led monitoring overlay discovery for England/Wales incinerator register.

Key behaviours:
- Uses the broad incinerator/control register as the spine.
- Uses the validated DEFRA/AURN overlay file to skip already validated facilities.
- Optionally skips facilities that already have selected candidate overlays from a previous V3 run.
- Queries OpenAQ with current v3-compatible geospatial patterns:
  * coordinates=latitude,longitude
  * radius capped at 25,000 metres
  * iso=GB
  * bbox=minLon,minLat,maxLon,maxLat
- Handles 429 Retry-After and exponential backoff.
- Writes reviewable candidate overlays, diagnostics, status and a public-safe summary page.

No candidate is automatically promoted to validated. Promotion should happen in a separate review step.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import math
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

OPENAQ_LOCATIONS = "https://api.openaq.org/v3/locations"
MAX_OPENAQ_RADIUS_M = 25000
DEFAULT_POLLUTANTS = {"no", "no2", "nox", "pm10", "pm2.5", "pm25", "o3", "so2", "co"}
OFFICIAL_HINTS = (
    "defra", "aurn", "uka", "uk-air", "london air quality network", "laqn",
    "environment agency", "air quality england", "scottish air quality", "welsh air quality"
)
COMMUNITY_HINTS = ("airgradient", "purpleair", "sensor.community", "low-cost", "low cost")


def now_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def norm_key(value: Any) -> str:
    s = str(value or "").lower()
    s = s.replace("&", " and ")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    drop = {
        "the", "energy", "recovery", "facility", "resource", "resources", "centre", "center",
        "erf", "efw", "wte", "waste", "management", "plant", "incinerator", "incineration",
        "power", "station", "rr", "tps", "ltd", "limited"
    }
    parts = [p for p in s.split() if p and p not in drop]
    return " ".join(parts).strip()


ALIAS_MAP = {
    "tyseley": {"tyseley", "birmingham tyseley", "tyseley erf", "tyseley efw"},
    "riverside": {"riverside", "riverside rr", "riverside resource recovery", "riverside erf"},
    "runcorn": {"runcorn", "runcorn tps", "runcorn efw", "runcorn energy from waste"},
    "newhaven": {"newhaven", "newhaven erf", "newhaven energy recovery", "veolia newhaven", "bv8067il"},
    "selchp": {"selchp", "south east london combined heat and power", "london selchp"},
    "london ecopark": {"london ecopark", "ecopark", "edmonton ecopark", "london eco park"},
    "leeds": {"leeds rerf", "leeds recycling and energy recovery facility", "leeds"},
    "sheffield": {"sheffield erf", "sheffield energy recovery facility", "sheffield"},
}


def alias_keys(value: Any) -> set[str]:
    raw = str(value or "")
    keys = {norm_key(raw)}
    raw_l = raw.lower()
    for canonical, aliases in ALIAS_MAP.items():
        if any(a in raw_l for a in aliases):
            keys.add(norm_key(canonical))
            keys.update(norm_key(a) for a in aliases)
    return {k for k in keys if k}


def read_csv(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return [dict(r) for r in csv.DictReader(f)]


def write_csv(path: Path, rows: List[Dict[str, Any]], fieldnames: Optional[List[str]] = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fields: List[str] = []
        for r in rows:
            for k in r.keys():
                if k not in fields:
                    fields.append(k)
        fieldnames = fields or ["empty"]
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fieldnames})


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


def first_present(row: Dict[str, Any], names: Iterable[str]) -> str:
    lower = {str(k).lower().strip(): k for k in row.keys()}
    for name in names:
        key = lower.get(name.lower())
        if key is not None and str(row.get(key, "")).strip():
            return str(row.get(key, "")).strip()
    # fuzzy contains
    for name in names:
        nl = name.lower().replace("_", " ")
        for lk, ok in lower.items():
            if nl in lk.replace("_", " ") and str(row.get(ok, "")).strip():
                return str(row.get(ok, "")).strip()
    return ""


def parse_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    s = str(v).strip().replace(",", "")
    if not s or s.lower() in {"nan", "none", "null", "-"}:
        return None
    try:
        return float(s)
    except Exception:
        return None


def lat_lon_from_row(row: Dict[str, Any], prefix: str = "facility") -> Tuple[Optional[float], Optional[float], str]:
    # Facility columns may vary widely. Try named lat/lon first.
    if prefix == "control":
        lat_names = ["Control_Lat", "Control Lat", "control_lat", "control latitude", "control_latitude", "ControlLatitude"]
        lon_names = ["Control_Lon", "Control Long", "Control Longitude", "control_lon", "control longitude", "control_longitude", "ControlLongitude"]
        e_names = ["Control_Easting", "Control Easting", "control_easting", "ControlEasting"]
        n_names = ["Control_Northing", "Control Northing", "control_northing", "ControlNorthing"]
    else:
        lat_names = ["Latitude", "Lat", "Facility_Lat", "Facility Lat", "facility_lat", "facility latitude", "Site Latitude", "site_latitude"]
        lon_names = ["Longitude", "Lon", "Long", "Facility_Lon", "Facility Long", "facility_lon", "facility longitude", "Site Longitude", "site_longitude"]
        e_names = ["Easting", "Facility_Easting", "Facility Easting", "Site Easting", "easting"]
        n_names = ["Northing", "Facility_Northing", "Facility Northing", "Site Northing", "northing"]
    lat = parse_float(first_present(row, lat_names))
    lon = parse_float(first_present(row, lon_names))
    if lat is not None and lon is not None and -90 <= lat <= 90 and -180 <= lon <= 180:
        return lat, lon, "lat_lon_columns"
    # If values are reversed in the file, rescue them.
    if lat is not None and lon is not None and -90 <= lon <= 90 and -180 <= lat <= 180:
        return lon, lat, "reversed_lon_lat_columns_rescued"
    # Optional easting/northing conversion if pyproj is available.
    east = parse_float(first_present(row, e_names))
    north = parse_float(first_present(row, n_names))
    if east is not None and north is not None:
        try:
            from pyproj import Transformer  # type: ignore
            transformer = Transformer.from_crs("EPSG:27700", "EPSG:4326", always_xy=True)
            lon2, lat2 = transformer.transform(east, north)
            if -90 <= lat2 <= 90 and -180 <= lon2 <= 180:
                return float(lat2), float(lon2), "easting_northing_epsg27700"
        except Exception:
            return None, None, "easting_northing_present_pyproj_unavailable_or_failed"
    return None, None, "no_valid_coordinates"


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def bbox_around(lat: float, lon: float, km: float) -> Tuple[float, float, float, float]:
    dlat = km / 111.32
    dlon = km / (111.32 * max(0.2, math.cos(math.radians(lat))))
    return lon - dlon, lat - dlat, lon + dlon, lat + dlat


def opener(api_key: str) -> urllib.request.OpenerDirector:
    op = urllib.request.build_opener()
    if api_key:
        op.addheaders = [("X-API-Key", api_key), ("User-Agent", "AQ26-Incinerator-Overlay-Finder/3.1")]
    else:
        op.addheaders = [("User-Agent", "AQ26-Incinerator-Overlay-Finder/3.1")]
    return op


def fetch_json(url: str, op: urllib.request.OpenerDirector, max_retries: int, sleep_seconds: float) -> Tuple[Optional[dict], Dict[str, Any]]:
    diag: Dict[str, Any] = {"url": url, "http_status": "", "ok": False, "error": "", "response_excerpt": ""}
    for attempt in range(max_retries + 1):
        diag["attempt"] = attempt + 1
        try:
            with op.open(url, timeout=45) as resp:
                status = getattr(resp, "status", 200)
                body = resp.read().decode("utf-8", errors="replace")
                diag.update({"http_status": status, "ok": 200 <= status < 300, "response_excerpt": body[:500]})
                if 200 <= status < 300:
                    return json.loads(body), diag
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace") if hasattr(e, "read") else ""
            diag.update({"http_status": e.code, "ok": False, "error": f"HTTPError: {e}", "response_excerpt": body[:500]})
            if e.code == 429 and attempt < max_retries:
                retry_after = e.headers.get("Retry-After") if e.headers else None
                try:
                    wait = float(retry_after) if retry_after else sleep_seconds * (2 ** attempt)
                except Exception:
                    wait = sleep_seconds * (2 ** attempt)
                time.sleep(max(wait, sleep_seconds))
                continue
            return None, diag
        except Exception as e:
            diag.update({"http_status": "", "ok": False, "error": repr(e), "response_excerpt": ""})
            if attempt < max_retries:
                time.sleep(sleep_seconds * (attempt + 1))
                continue
            return None, diag
    return None, diag


def extract_location_rows(payload: dict) -> List[dict]:
    results = payload.get("results") or payload.get("data") or []
    if isinstance(results, dict):
        results = results.get("results", [])
    return results if isinstance(results, list) else []


def params_from_location(loc: Dict[str, Any]) -> List[str]:
    out: List[str] = []
    for key in ("parameters", "parameter", "sensors"):
        val = loc.get(key)
        if isinstance(val, list):
            for item in val:
                if isinstance(item, dict):
                    name = item.get("name") or item.get("displayName") or item.get("parameter") or item.get("id")
                else:
                    name = item
                if name:
                    out.append(str(name))
    return sorted({p for p in out if p})


def provider_text(loc: Dict[str, Any]) -> str:
    parts: List[str] = []
    for key in ("provider", "owner", "manufacturer", "source", "entity"):
        v = loc.get(key)
        if isinstance(v, dict):
            parts.extend(str(x) for x in v.values() if x)
        elif v:
            parts.append(str(v))
    return " ".join(parts)


def coords_from_location(loc: Dict[str, Any]) -> Tuple[Optional[float], Optional[float]]:
    c = loc.get("coordinates") or {}
    if isinstance(c, dict):
        lat = parse_float(c.get("latitude"))
        lon = parse_float(c.get("longitude"))
        if lat is not None and lon is not None:
            return lat, lon
    return None, None


def score_candidate(fac_lat: float, fac_lon: float, query_lat: float, query_lon: float, query_role: str, loc: Dict[str, Any]) -> Tuple[int, str, List[str], str, float, float]:
    lat, lon = coords_from_location(loc)
    if lat is None or lon is None:
        return 0, "manual_review_low_confidence", [], "", 9999.0, 9999.0
    dist_fac = haversine_km(fac_lat, fac_lon, lat, lon)
    dist_query = haversine_km(query_lat, query_lon, lat, lon)
    params = params_from_location(loc)
    params_l = {p.lower().replace(" ", "") for p in params}
    relevant = [p for p in params if p.lower().replace(" ", "") in DEFAULT_POLLUTANTS]
    prov = provider_text(loc).lower() + " " + str(loc.get("name", "")).lower()
    official = any(h in prov for h in OFFICIAL_HINTS) or bool(re.search(r"\buka\d+\b", prov))
    community = any(h in prov for h in COMMUNITY_HINTS)
    score = 0
    d = dist_query
    if d <= 1: score += 45
    elif d <= 3: score += 40
    elif d <= 5: score += 34
    elif d <= 10: score += 25
    elif d <= 15: score += 17
    elif d <= 25: score += 8
    else: score -= 10
    score += min(30, len(relevant) * 7)
    if "no2" in params_l: score += 8
    if "pm2.5" in {p.lower() for p in params} or "pm25" in params_l: score += 6
    if "pm10" in params_l: score += 6
    if "so2" in params_l: score += 5
    if official: score += 22
    if community: score -= 12
    if query_role == "control": score += 3
    if score >= 85 and official:
        cls = "high_confidence_official_candidate"
    elif score >= 70 and official:
        cls = "local_or_official_candidate_needs_review"
    elif score >= 55:
        cls = "plausible_candidate_needs_review"
    elif community and score >= 35:
        cls = "supporting_context_community_sensor"
    else:
        cls = "manual_review_low_confidence"
    return int(score), cls, relevant, provider_text(loc), dist_fac, dist_query


def facility_name(row: Dict[str, Any]) -> str:
    return first_present(row, ["Facility", "facility", "Facility_Name", "facility_name", "Incinerator", "Site", "site_name", "Name"])


def control_name(row: Dict[str, Any]) -> str:
    return first_present(row, ["Control", "Control_Site", "Control Site", "control_site", "Control_Location", "Control LSOA"])


def validated_keys(rows: List[Dict[str, str]]) -> set[str]:
    keys: set[str] = set()
    for r in rows:
        for field in ["Facility", "facility", "Facility_Name", "facility_name", "Incinerator", "Site", "site_name", "Name"]:
            if r.get(field):
                keys.update(alias_keys(r.get(field)))
        # capture permit aliases too
        for field in ["Permit", "permit", "Permit_Number", "permit_number", "EPR", "EP Permit"]:
            if r.get(field):
                keys.update(alias_keys(r.get(field)))
    return keys


def selected_candidate_keys(path: Path) -> set[str]:
    keys: set[str] = set()
    if not path.exists():
        return keys
    try:
        for r in read_csv(path):
            st = str(r.get("review_status") or r.get("candidate_class") or "").lower()
            if "candidate" in st or "review" in st or "high_confidence" in st or "plausible" in st:
                name = r.get("facility_name") or r.get("facility") or r.get("Facility")
                keys.update(alias_keys(name))
    except Exception:
        pass
    return keys


def load_cache(path: Path) -> List[Dict[str, str]]:
    if path.exists():
        try:
            return read_csv(path)
        except Exception:
            return []
    return []


def query_variants(lat: float, lon: float, radius_km: float, limit: int) -> List[Tuple[str, str]]:
    radius_m = int(min(MAX_OPENAQ_RADIUS_M, max(1000, radius_km * 1000)))
    r10 = min(radius_m, 10000)
    variants: List[Tuple[str, str]] = []
    q1 = {"coordinates": f"{lat:.6f},{lon:.6f}", "radius": str(radius_m), "limit": str(limit), "iso": "GB"}
    q2 = {"coordinates": f"{lat:.6f},{lon:.6f}", "radius": str(r10), "limit": str(limit), "iso": "GB"}
    variants.append(("coordinates_lat_lon_radius_capped", OPENAQ_LOCATIONS + "?" + urllib.parse.urlencode(q1)))
    variants.append(("coordinates_lat_lon_radius_10000", OPENAQ_LOCATIONS + "?" + urllib.parse.urlencode(q2)))
    for label, km in [("bbox_25km_lonlat", min(radius_km, 25.0)), ("bbox_10km_lonlat", min(radius_km, 10.0))]:
        minlon, minlat, maxlon, maxlat = bbox_around(lat, lon, km)
        q = {"bbox": f"{minlon:.6f},{minlat:.6f},{maxlon:.6f},{maxlat:.6f}", "limit": str(limit), "iso": "GB"}
        variants.append((label, OPENAQ_LOCATIONS + "?" + urllib.parse.urlencode(q)))
    return variants


def build_page(path: Path, summary: Dict[str, Any], selected_rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = "".join(
        f"<tr><td>{html(r.get('facility_name'))}</td><td>{html(r.get('candidate_location_name'))}</td><td>{html(r.get('candidate_class'))}</td><td>{html(r.get('score'))}</td><td>{html(r.get('distance_to_query_km'))}</td><td>{html(r.get('pollutants'))}</td></tr>"
        for r in selected_rows[:200]
    )
    text = f"""<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>AQ26 Incinerator Monitoring Overlays</title><link rel='icon' href='assets/favicon.svg'><style>body{{font-family:Arial,sans-serif;margin:0;background:#f6f8fb;color:#102033}}header{{background:#fff;border-bottom:1px solid #dbe3ef;padding:18px 24px}}main{{max-width:1180px;margin:0 auto;padding:24px}}.hero{{background:linear-gradient(135deg,#07233f,#0a6b82);color:white;border-radius:24px;padding:28px;margin:20px 0}}.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:14px}}.card{{background:white;border:1px solid #dbe3ef;border-radius:18px;padding:16px;box-shadow:0 8px 24px rgba(12,33,61,.08)}}.metric{{font-size:2rem;font-weight:800}}table{{width:100%;border-collapse:collapse;background:white;border-radius:16px;overflow:hidden}}th,td{{padding:10px;border-bottom:1px solid #e8eef6;text-align:left;font-size:.92rem}}th{{background:#eaf3f8}}code{{background:#eef3f8;padding:2px 5px;border-radius:5px}}</style></head><body><header><strong>SCC Nexus · AQ26</strong> Incinerator monitoring overlay discovery</header><main><section class='hero'><h1>England & Wales incinerator monitoring overlays</h1><p>Facility-led discovery of validated and candidate air-quality monitoring overlays. Candidate rows require review before promotion.</p></section><section class='cards'><div class='card'><div class='metric'>{summary.get('broad_facilities', 0)}</div><p>Facilities in register</p></div><div class='card'><div class='metric'>{summary.get('validated_overlays', 0)}</div><p>Validated overlays</p></div><div class='card'><div class='metric'>{summary.get('facilities_queried_this_run', 0)}</div><p>Queried this run</p></div><div class='card'><div class='metric'>{summary.get('selected_candidates', 0)}</div><p>Candidates needing review</p></div><div class='card'><div class='metric'>{summary.get('rate_limited_calls', 0)}</div><p>Rate-limited calls</p></div></section><h2>Selected candidates for review</h2><table><thead><tr><th>Facility</th><th>Candidate station</th><th>Class</th><th>Score</th><th>Distance km</th><th>Pollutants</th></tr></thead><tbody>{rows}</tbody></table><p>Generated {html(summary.get('generated_at_utc'))}. Full diagnostics are kept in the unredacted review area.</p></main></body></html>"""
    path.write_text(text, encoding="utf-8")


def html(v: Any) -> str:
    return (str(v or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;"))


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--broad-register", required=True)
    ap.add_argument("--validated-overlays", required=True)
    ap.add_argument("--output-root", default="site_public/data/focus/overlays_v3")
    ap.add_argument("--site-root", default="site_public")
    ap.add_argument("--radius-km", type=float, default=25.0)
    ap.add_argument("--limit-per-query", type=int, default=100)
    ap.add_argument("--max-facilities", type=int, default=10)
    ap.add_argument("--min-score", type=int, default=35)
    ap.add_argument("--sleep-seconds", type=float, default=3.0)
    ap.add_argument("--max-retries", type=int, default=3)
    ap.add_argument("--live-openaq", action="store_true")
    ap.add_argument("--use-v2-cache", action="store_true")
    ap.add_argument("--skip-existing-candidates", action="store_true")
    ap.add_argument("--force-requery", action="store_true")
    ap.add_argument("--exhaustive", action="store_true")
    ap.add_argument("--write-page", action="store_true")
    args = ap.parse_args(argv)

    broad_path = Path(args.broad_register)
    validated_path = Path(args.validated_overlays)
    out = Path(args.output_root)
    site = Path(args.site_root)
    out.mkdir(parents=True, exist_ok=True)

    broad = read_csv(broad_path)
    validated = read_csv(validated_path)
    vkeys = validated_keys(validated)

    prev_selected_path = out / "selected_candidate_overlays_needing_review.csv"
    prev_candidate_keys = selected_candidate_keys(prev_selected_path) if (args.skip_existing_candidates and not args.force_requery) else set()

    rows_status: List[Dict[str, Any]] = []
    remaining: List[Dict[str, Any]] = []
    for idx, r in enumerate(broad):
        name = facility_name(r) or f"facility_{idx+1}"
        keys = alias_keys(name)
        is_validated = bool(keys & vkeys)
        has_prev_candidate = bool(keys & prev_candidate_keys)
        status = "validated_existing_overlay" if is_validated else ("candidate_overlay_needs_review_existing" if has_prev_candidate else "no_candidate_selected_yet")
        rows_status.append({"facility_name": name, "overlay_status": status, "facility_key": "|".join(sorted(keys))})
        if not is_validated and not has_prev_candidate:
            remaining.append(r)

    selected_to_query = remaining if args.max_facilities == 0 else remaining[: max(0, args.max_facilities)]

    diagnostics: List[Dict[str, Any]] = []
    candidates: List[Dict[str, Any]] = []
    selected: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []

    api_key = os.environ.get("OPENAQ_API_KEY", "")
    op = opener(api_key)

    # cache candidates from V2 can be used as supporting input, but we still score/output freshly discovered rows separately.
    if args.use_v2_cache:
        cache = load_cache(Path("site_public/data/focus/overlays_v2/candidate_monitoring_overlays.csv"))
        for cr in cache:
            fname = cr.get("facility_name") or cr.get("facility") or ""
            if fname and any(bool(alias_keys(fname) & alias_keys(facility_name(r))) for r in selected_to_query):
                row = dict(cr)
                row.setdefault("source_layer", "v2_cache")
                candidates.append(row)

    if args.live_openaq:
        for r in selected_to_query:
            fname = facility_name(r)
            flat, flon, fsrc = lat_lon_from_row(r, "facility")
            clat, clon, csrc = lat_lon_from_row(r, "control")
            query_points: List[Tuple[str, Optional[float], Optional[float], str]] = [("facility", flat, flon, fsrc), ("control", clat, clon, csrc)]
            if flat is None or flon is None:
                errors.append({"facility_name": fname, "stage": "coordinate", "error": "facility coordinate missing", "source": fsrc})
                continue
            for role, qlat, qlon, qsrc in query_points:
                if qlat is None or qlon is None:
                    diagnostics.append({"facility_name": fname, "query_role": role, "method": "coordinate_missing", "ok": False, "error": qsrc})
                    continue
                variants = query_variants(qlat, qlon, args.radius_km, args.limit_per_query)
                if not args.exhaustive:
                    variants = variants[:3]
                for method, url in variants:
                    data, diag = fetch_json(url, op, args.max_retries, args.sleep_seconds)
                    diag.update({"facility_name": fname, "query_role": role, "method": method})
                    diagnostics.append(diag)
                    if data:
                        locs = extract_location_rows(data)
                        for loc in locs:
                            score, cls, relevant, prov, dist_fac, dist_query = score_candidate(flat, flon, qlat, qlon, role, loc)
                            lat, lon = coords_from_location(loc)
                            cname = loc.get("name") or loc.get("locality") or loc.get("id") or ""
                            cid = loc.get("id") or loc.get("location_id") or ""
                            cand = {
                                "facility_name": fname,
                                "control_name": control_name(r),
                                "query_role": role,
                                "query_method": method,
                                "coordinate_source": qsrc,
                                "candidate_location_id": cid,
                                "candidate_location_name": cname,
                                "candidate_latitude": lat,
                                "candidate_longitude": lon,
                                "provider": prov,
                                "pollutants": ";".join(relevant),
                                "all_parameters": ";".join(params_from_location(loc)),
                                "distance_to_facility_km": f"{dist_fac:.3f}",
                                "distance_to_query_km": f"{dist_query:.3f}",
                                "score": score,
                                "candidate_class": cls,
                                "review_status": "candidate_needs_review" if score >= args.min_score else "below_threshold",
                                "source_layer": "openaq_live_v3_1",
                            }
                            candidates.append(cand)
                    time.sleep(max(0.0, args.sleep_seconds))

    # Deduplicate candidates by facility + location id/name + role; keep max score.
    best: Dict[str, Dict[str, Any]] = {}
    for c in candidates:
        fname = c.get("facility_name") or c.get("facility") or ""
        locid = c.get("candidate_location_id") or c.get("candidate_location_name") or c.get("location_name") or ""
        role = c.get("query_role") or ""
        key = f"{norm_key(fname)}|{locid}|{role}"
        try:
            sc = int(float(c.get("score", 0)))
        except Exception:
            sc = 0
        if key not in best or sc > int(float(best[key].get("score", 0) or 0)):
            best[key] = c
    candidates = list(best.values())
    for c in candidates:
        try:
            if int(float(c.get("score", 0))) >= args.min_score:
                c["review_status"] = "candidate_needs_review"
                selected.append(c)
        except Exception:
            pass

    facilities_with_selected = {norm_key(c.get("facility_name")) for c in selected}
    for st in rows_status:
        if st["overlay_status"] == "no_candidate_selected_yet" and norm_key(st["facility_name"]) in facilities_with_selected:
            st["overlay_status"] = "candidate_overlay_needs_review"

    write_csv(out / "facility_overlay_status.csv", rows_status)
    write_csv(out / "remaining_overlay_queue.csv", [{"facility_name": facility_name(r), "control_name": control_name(r)} for r in remaining])
    write_csv(out / "queried_facilities_this_run.csv", [{"facility_name": facility_name(r), "control_name": control_name(r)} for r in selected_to_query])
    write_csv(out / "candidate_monitoring_overlays.csv", candidates)
    write_csv(out / "selected_candidate_overlays_needing_review.csv", selected)
    write_csv(out / "openaq_query_diagnostics.csv", diagnostics)
    write_json(out / "overlay_discovery_errors.json", errors)

    status_counts: Dict[str, int] = {}
    for r in rows_status:
        status_counts[r["overlay_status"]] = status_counts.get(r["overlay_status"], 0) + 1
    http_counts: Dict[str, int] = {}
    for d in diagnostics:
        hs = str(d.get("http_status", ""))
        if hs:
            http_counts[hs] = http_counts.get(hs, 0) + 1
    summary = {
        "generated_at_utc": now_utc(),
        "workflow_version": "v3.1_skip_existing_candidates",
        "broad_facilities": len(broad),
        "validated_overlays": len(validated),
        "remaining_facilities_total": len(remaining),
        "previous_candidate_facilities_skipped": len(prev_candidate_keys),
        "facilities_queried_this_run": len(selected_to_query),
        "candidate_rows": len(candidates),
        "selected_candidates": len(selected),
        "facilities_with_selected_candidates_this_run": len(facilities_with_selected),
        "status_counts": status_counts,
        "diagnostic_rows": len(diagnostics),
        "http_status_counts": http_counts,
        "rate_limited_calls": http_counts.get("429", 0),
        "error_rows": len(errors),
        "openaq_radius_cap_m": MAX_OPENAQ_RADIUS_M,
        "live_openaq": bool(args.live_openaq),
        "skip_existing_candidates": bool(args.skip_existing_candidates),
        "force_requery": bool(args.force_requery),
    }
    write_json(out / "incinerator_overlay_summary.json", summary)
    if args.write_page:
        build_page(site / "incinerator-overlays.html", summary, selected)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
