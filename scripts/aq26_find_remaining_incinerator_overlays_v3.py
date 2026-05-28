#!/usr/bin/env python3
"""
AQ26 Remaining Incinerator Overlay Finder V3.3

Stateful batching fix:
- Only skips facilities with existing *selected/review* candidates or validated overlays.
- Does NOT skip based on raw candidate_monitoring_overlays or OpenAQ cache rows.
- Writes fresh this-run files every run.
- Writes cumulative selected candidates without losing previous review candidates.
- Adds manual batch_offset and force_requery escape hatches.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import math
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

FIELD_SELECTED = [
    "facility", "facility_key", "location", "facility_lat", "facility_lon",
    "control_site", "control_lat", "control_lon", "query_point_role",
    "query_point_lat", "query_point_lon", "candidate_source", "candidate_status",
    "candidate_review_class", "monitoring_site_name", "openaq_location_id",
    "monitoring_site_lat", "monitoring_site_lon", "distance_query_to_monitor_km",
    "pollutants", "monitoring_provider_text", "provider_class", "distance_score",
    "pollutant_score", "official_hint_score", "source_score", "relevance_score",
    "suggested_action", "review_note"
]

FIELD_STATUS = [
    "facility", "facility_key", "overlay_status", "best_candidate_site",
    "best_candidate_score", "best_candidate_class", "suggested_action"
]

FIELD_DIAG = [
    "facility", "facility_key", "query_point_role", "method", "url",
    "http_status", "result_count", "attempt", "error_type", "error_message"
]

KNOWN_ALIASES = {
    "tyseley erf": "tyseley", "tyseley efw": "tyseley", "tyseley": "tyseley",
    "riverside resource recovery": "riverside", "riverside rr erf": "riverside", "riverside erf": "riverside", "riverside": "riverside",
    "runcorn tps": "runcorn", "runcorn efw": "runcorn", "runcorn": "runcorn",
    "newhaven energy recovery facility": "newhaven", "newhaven erf": "newhaven", "newhaven": "newhaven",
    "leeds rerf": "leeds", "leeds recycling and energy recovery facility": "leeds",
    "london ecopark": "londonecopark", "edmonton ecopark": "londonecopark",
    "selchp": "selchp", "sheffield erf": "sheffield", "beddington erf": "beddington",
    "allerton waste recovery park": "allerton", "allington quarry waste management facility": "allington",
    "cswdc coventry": "coventry", "coventry erf": "coventry", "crossness sludge plant": "crossness",
    "devonport dockyard": "devonport", "cornwall erc": "cornwall",
}

INCINERATOR_WORDS = {
    "erf", "efw", "energy", "recovery", "facility", "waste", "incinerator", "incineration",
    "resource", "recycling", "park", "plant", "sludge", "dockyard", "quarry", "management",
    "thermal", "treatment", "centre", "center", "rr", "rerf", "wte", "tps", "erc"
}

POLLUTANT_WEIGHT = {"no2": 10, "pm25": 9, "pm2.5": 9, "pm10": 8, "so2": 8, "o3": 6, "co": 5, "nox": 5, "no": 3}
OFFICIAL_HINTS = ["defra", "aurn", "uka", "government", "eea", "uk-air", "london air quality", "laqn", "local authority"]
COMMUNITY_HINTS = ["airgradient", "purpleair", "sensor.community", "unknown", "openaq"]


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def norm_text(s: Any) -> str:
    s = "" if s is None else str(s)
    return re.sub(r"\s+", " ", s.strip())


def facility_key(name: Any) -> str:
    raw = norm_text(name).lower()
    raw = raw.replace("&", " and ")
    raw = re.sub(r"[^a-z0-9]+", " ", raw).strip()
    if raw in KNOWN_ALIASES:
        return KNOWN_ALIASES[raw]
    # contains aliases
    for k, v in KNOWN_ALIASES.items():
        if k and k in raw:
            return v
    toks = [t for t in raw.split() if t not in INCINERATOR_WORDS]
    if not toks:
        toks = raw.split()
    return "".join(toks[:3]) or hashlib.sha1(raw.encode()).hexdigest()[:10]


def read_csv_rows(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return [dict(r) for r in csv.DictReader(f)]


def write_csv_rows(path: Path, rows: List[Dict[str, Any]], fieldnames: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fieldnames})


def safe_float(v: Any) -> Optional[float]:
    try:
        if v is None or str(v).strip() == "" or str(v).lower() == "nan":
            return None
        return float(v)
    except Exception:
        return None


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0088
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def load_broad(path: Path) -> List[Dict[str, Any]]:
    rows = []
    for r in read_csv_rows(path):
        fac = norm_text(r.get("Facility"))
        if not fac:
            continue
        r["facility_key"] = facility_key(fac)
        rows.append(r)
    # de-dupe by key keeping first complete row
    seen = set(); out = []
    for r in rows:
        k = r["facility_key"]
        if k not in seen:
            out.append(r); seen.add(k)
    return out


def load_validated_keys(path: Path) -> set:
    keys = set()
    for r in read_csv_rows(path):
        fac = r.get("Facility") or r.get("facility") or r.get("Facility_Name")
        if fac:
            keys.add(facility_key(fac))
    return keys


def selected_facility_keys_from_previous(output_root: Path) -> set:
    """Only selected/review files count as previous candidate coverage."""
    keys = set()
    selected_files = [
        output_root / "selected_candidate_overlays_needing_review.csv",
        output_root / "selected_candidate_overlays_cumulative.csv",
    ]
    status_files = [output_root / "facility_overlay_status.csv", output_root / "facility_overlay_status_cumulative.csv"]
    for p in selected_files:
        for r in read_csv_rows(p):
            status = norm_text(r.get("candidate_status") or r.get("overlay_status")).lower()
            if status and "candidate" not in status and "review" not in status:
                continue
            k = r.get("facility_key") or facility_key(r.get("facility") or r.get("Facility"))
            if k:
                keys.add(k)
    for p in status_files:
        for r in read_csv_rows(p):
            if norm_text(r.get("overlay_status")).lower() in {"candidate_overlay_needs_review", "candidate_overlay_needs_review_existing"}:
                k = r.get("facility_key") or facility_key(r.get("facility") or r.get("Facility"))
                if k:
                    keys.add(k)
    return keys


def openaq_headers() -> Dict[str, str]:
    h = {"User-Agent": "AQ26-incinerator-overlays-v3.3"}
    key = os.environ.get("OPENAQ_API_KEY", "").strip()
    if key:
        h["X-API-Key"] = key
    return h


def fetch_json(url: str, max_retries: int, sleep_seconds: float) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    headers = openaq_headers()
    last_diag: Dict[str, Any] = {}
    for attempt in range(1, max_retries + 1):
        try:
            req = Request(url, headers=headers)
            with urlopen(req, timeout=35) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data, {"http_status": resp.status, "attempt": attempt, "error_type": "", "error_message": ""}
        except HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8", errors="replace")[:500]
            except Exception:
                pass
            last_diag = {"http_status": e.code, "attempt": attempt, "error_type": "HTTPError", "error_message": body or str(e)}
            if e.code == 429 and attempt < max_retries:
                retry_after = safe_float(e.headers.get("Retry-After")) or sleep_seconds * (2 ** (attempt - 1))
                time.sleep(max(1.0, retry_after))
                continue
            return None, last_diag
        except URLError as e:
            last_diag = {"http_status": "", "attempt": attempt, "error_type": "URLError", "error_message": str(e)[:500]}
            if attempt < max_retries:
                time.sleep(sleep_seconds * (2 ** (attempt - 1)))
                continue
            return None, last_diag
        except Exception as e:
            last_diag = {"http_status": "", "attempt": attempt, "error_type": type(e).__name__, "error_message": str(e)[:500]}
            return None, last_diag
    return None, last_diag


def flatten_provider(loc: Dict[str, Any]) -> str:
    parts = []
    for k in ["provider", "owner", "manufacturer"]:
        v = loc.get(k)
        if isinstance(v, dict):
            parts.extend([norm_text(v.get("name")), norm_text(v.get("organization"))])
        elif v:
            parts.append(norm_text(v))
    for k in ["country", "locality", "timezone"]:
        v = loc.get(k)
        if isinstance(v, dict):
            parts.append(norm_text(v.get("name")))
        elif v:
            parts.append(norm_text(v))
    return " | ".join([p for p in parts if p])


def extract_pollutants(loc: Dict[str, Any]) -> List[str]:
    out = []
    for key in ["parameters", "sensors"]:
        arr = loc.get(key) or []
        if isinstance(arr, list):
            for item in arr:
                if isinstance(item, dict):
                    p = item.get("parameter") or item.get("name") or item.get("displayName")
                    if isinstance(p, dict):
                        p = p.get("name") or p.get("displayName")
                    if p:
                        out.append(str(p).lower().replace(".", ""))
    return sorted(set([p for p in out if p]))


def candidate_from_location(fac: Dict[str, Any], role: str, qlat: float, qlon: float, loc: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    coords = loc.get("coordinates") or {}
    lat = safe_float(coords.get("latitude"))
    lon = safe_float(coords.get("longitude"))
    if lat is None or lon is None:
        return None
    dist = haversine_km(qlat, qlon, lat, lon)
    pollutants = extract_pollutants(loc)
    provider = flatten_provider(loc)
    name = norm_text(loc.get("name") or loc.get("location") or loc.get("id"))
    locid = loc.get("id", "")
    provider_l = provider.lower() + " " + name.lower()
    official_hint = 15 if any(h in provider_l for h in OFFICIAL_HINTS) or "uka" in name.lower() else 0
    source_score = 5 if official_hint else 0
    if any(h in provider_l for h in COMMUNITY_HINTS) and not official_hint:
        provider_class = "community_or_uncertain_candidate"
    elif official_hint:
        provider_class = "official_or_governmental_candidate"
    else:
        provider_class = "unknown_or_local_candidate"
    if dist <= 2:
        distance_score = 45
    elif dist <= 5:
        distance_score = 40
    elif dist <= 10:
        distance_score = 32
    elif dist <= 15:
        distance_score = 25
    elif dist <= 25:
        distance_score = 14
    else:
        distance_score = 4
    pollutant_score = min(35, sum(POLLUTANT_WEIGHT.get(p, 0) for p in pollutants))
    score = distance_score + pollutant_score + official_hint + source_score
    if score >= 80 and official_hint:
        cls = "high_confidence_official_candidate"; action = "review_for_promotion_to_validated_overlay"
    elif score >= 60 and (official_hint or "local" in provider_l or "london" in provider_l):
        cls = "local_or_official_candidate_needs_review"; action = "review_as_local_or_official_overlay_candidate"
    elif score >= 45:
        cls = "plausible_candidate_needs_review"; action = "review_geography_and_source_before_use"
    elif provider_class == "community_or_uncertain_candidate":
        cls = "supporting_context_community_sensor"; action = "use_as_supporting_context_only"
    else:
        cls = "manual_review_low_confidence"; action = "manual_review_or_find_alternative_source"
    return {
        "facility": fac.get("Facility", ""), "facility_key": fac.get("facility_key", ""),
        "location": fac.get("Location", ""), "facility_lat": fac.get("Lat", ""), "facility_lon": fac.get("Lon", ""),
        "control_site": fac.get("Control_Site", ""), "control_lat": fac.get("Control_Lat", ""), "control_lon": fac.get("Control_Lon", ""),
        "query_point_role": role, "query_point_lat": qlat, "query_point_lon": qlon,
        "candidate_source": "OpenAQ v3 locations", "candidate_status": "candidate_needs_review",
        "candidate_review_class": cls, "monitoring_site_name": name, "openaq_location_id": locid,
        "monitoring_site_lat": lat, "monitoring_site_lon": lon, "distance_query_to_monitor_km": round(dist, 3),
        "pollutants": ";".join(pollutants), "monitoring_provider_text": provider, "provider_class": provider_class,
        "distance_score": distance_score, "pollutant_score": pollutant_score, "official_hint_score": official_hint,
        "source_score": source_score, "relevance_score": score, "suggested_action": action,
        "review_note": "Candidate only; compare against DEFRA/AURN, local geography, control-site role and source provenance before validation.",
    }


def query_variants(lat: float, lon: float, radius_km: float, limit: int) -> List[Tuple[str, str]]:
    base = "https://api.openaq.org/v3/locations"
    radius_m = min(25000, max(1, int(radius_km * 1000)))
    variants = []
    for label, radius in [("coordinates_lat_lon_radius_capped", radius_m), ("coordinates_lat_lon_radius_10000", min(10000, radius_m))]:
        qs = urlencode({"coordinates": f"{lat:.5f},{lon:.5f}", "radius": str(radius), "limit": str(limit), "iso": "GB"})
        variants.append((label, base + "?" + qs))
    # bbox fallback, approximate degrees
    km_lat = radius_m / 1000 / 111.32
    km_lon = radius_m / 1000 / max(1e-6, 111.32 * math.cos(math.radians(lat)))
    bbox = f"{lon-km_lon:.5f},{lat-km_lat:.5f},{lon+km_lon:.5f},{lat+km_lat:.5f}"
    variants.append(("bbox_25km_lonlat", base + "?" + urlencode({"bbox": bbox, "limit": str(limit), "iso": "GB"})))
    return variants


def load_cache_rows(root: Path, facilities_to_query: set) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for p in [
        root.parent / "overlays_v2" / "candidate_monitoring_overlays.csv",
        root / "candidate_monitoring_overlays.csv",
    ]:
        for r in read_csv_rows(p):
            k = r.get("facility_key") or facility_key(r.get("facility"))
            if k in facilities_to_query:
                r["facility_key"] = k
                rows.append(r)
    return rows


def dedupe_candidates(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    best: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
    for r in rows:
        k = (str(r.get("facility_key", "")), str(r.get("openaq_location_id") or r.get("monitoring_site_name", "")), str(r.get("query_point_role", "")))
        if not all(k):
            continue
        score = safe_float(r.get("relevance_score")) or 0
        dist = safe_float(r.get("distance_query_to_monitor_km")) or 99999
        old = best.get(k)
        if old is None:
            best[k] = r
        else:
            oscore = safe_float(old.get("relevance_score")) or 0
            odist = safe_float(old.get("distance_query_to_monitor_km")) or 99999
            if (score, -dist) > (oscore, -odist):
                best[k] = r
    return sorted(best.values(), key=lambda x: (x.get("facility_key", ""), -(safe_float(x.get("relevance_score")) or 0), safe_float(x.get("distance_query_to_monitor_km")) or 99999))


def select_candidates(rows: List[Dict[str, Any]], min_score: float) -> List[Dict[str, Any]]:
    selected = []
    # keep top max 8 per facility for review
    by_fac: Dict[str, List[Dict[str, Any]]] = {}
    for r in rows:
        score = safe_float(r.get("relevance_score")) or 0
        if score >= min_score:
            by_fac.setdefault(str(r.get("facility_key", "")), []).append(r)
    for k, arr in by_fac.items():
        arr = sorted(arr, key=lambda x: (-(safe_float(x.get("relevance_score")) or 0), safe_float(x.get("distance_query_to_monitor_km")) or 99999))
        selected.extend(arr[:8])
    return selected


def build_status(broad: List[Dict[str, Any]], validated_keys: set, selected_cumulative: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_fac: Dict[str, List[Dict[str, Any]]] = {}
    for r in selected_cumulative:
        k = r.get("facility_key") or facility_key(r.get("facility"))
        if k:
            by_fac.setdefault(k, []).append(r)
    status = []
    for f in broad:
        k = f["facility_key"]
        if k in validated_keys:
            status.append({"facility": f.get("Facility", ""), "facility_key": k, "overlay_status": "validated_existing_overlay", "best_candidate_site": "", "best_candidate_score": "", "best_candidate_class": "", "suggested_action": "use_validated_overlay"})
        elif k in by_fac:
            arr = sorted(by_fac[k], key=lambda x: -(safe_float(x.get("relevance_score")) or 0))
            b = arr[0]
            status.append({"facility": f.get("Facility", ""), "facility_key": k, "overlay_status": "candidate_overlay_needs_review", "best_candidate_site": b.get("monitoring_site_name", ""), "best_candidate_score": b.get("relevance_score", ""), "best_candidate_class": b.get("candidate_review_class", ""), "suggested_action": b.get("suggested_action", "review_candidate")})
        else:
            status.append({"facility": f.get("Facility", ""), "facility_key": k, "overlay_status": "no_candidate_selected_yet", "best_candidate_site": "", "best_candidate_score": "", "best_candidate_class": "", "suggested_action": "query_or_manual_review"})
    return status


def write_page(site_root: Path, summary: Dict[str, Any], status_rows: List[Dict[str, Any]], selected_rows: List[Dict[str, Any]]) -> None:
    site_root.mkdir(parents=True, exist_ok=True)
    rows_html = []
    for r in status_rows:
        rows_html.append("<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>".format(
            html.escape(str(r.get("facility", ""))), html.escape(str(r.get("overlay_status", ""))),
            html.escape(str(r.get("best_candidate_site", ""))), html.escape(str(r.get("best_candidate_score", ""))),
            html.escape(str(r.get("suggested_action", "")))
        ))
    body = f"""<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>AQ26 Incinerator Monitoring Overlays</title><style>body{{font-family:Arial,sans-serif;margin:0;background:#f5f7fb;color:#102033}}header{{background:#fff;border-bottom:1px solid #d9e2ef;padding:18px 24px}}main{{max-width:1180px;margin:auto;padding:24px}}.hero{{background:linear-gradient(135deg,#0b1f3a,#145c72);color:white;border-radius:24px;padding:28px;margin-bottom:22px}}.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:14px}}.card{{background:white;border-radius:18px;padding:18px;box-shadow:0 8px 22px rgba(9,30,66,.08)}}.num{{font-size:2rem;font-weight:800}}table{{width:100%;border-collapse:collapse;background:white;border-radius:16px;overflow:hidden}}td,th{{padding:10px;border-bottom:1px solid #e7edf5;text-align:left;font-size:.92rem}}th{{background:#edf4fb}}a{{color:#0b5cab}}</style></head><body><header><strong>SCC Nexus · AQ26</strong> Incinerator overlay review</header><main><section class='hero'><h1>Incinerator monitoring overlays</h1><p>Facility-led review of validated and candidate monitoring sites for England and Wales incinerator/EfW evidence.</p></section><section class='cards'>"""
    for k in ["broad_facilities", "validated_overlays", "candidate_facilities_cumulative", "no_candidate_selected_yet", "facilities_queried_this_run", "selected_candidates_this_run", "http_200_calls", "rate_limited_calls"]:
        body += f"<div class='card'><div class='num'>{html.escape(str(summary.get(k,'')))}</div><div>{html.escape(k.replace('_',' ').title())}</div></div>"
    body += "</section><h2>Facility overlay status</h2><table><thead><tr><th>Facility</th><th>Status</th><th>Best candidate</th><th>Score</th><th>Action</th></tr></thead><tbody>" + "\n".join(rows_html) + "</tbody></table>"
    body += "<p><a href='data/focus/overlays_v3/incinerator_overlay_summary.json'>Open summary JSON</a> · <a href='data/focus/overlays_v3/selected_candidate_overlays_needing_review.csv'>Download selected candidates</a></p>"
    body += "</main></body></html>"
    (site_root / "incinerator-overlays.html").write_text(body, encoding="utf-8")


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

    broad = load_broad(Path(args.broad_register))
    validated_keys = load_validated_keys(Path(args.validated_overlays))

    previous_selected = read_csv_rows(output_root / "selected_candidate_overlays_needing_review.csv")
    prev_selected_keys = selected_facility_keys_from_previous(output_root)

    # Build queue. Only selected/review candidates count for skip; raw candidates never count.
    remaining_all = [f for f in broad if f["facility_key"] not in validated_keys]
    if args.force_requery or not args.skip_existing_candidates:
        query_pool = list(remaining_all)
        skipped_existing = 0
    else:
        query_pool = [f for f in remaining_all if f["facility_key"] not in prev_selected_keys]
        skipped_existing = len(remaining_all) - len(query_pool)

    if args.batch_offset > 0:
        query_pool = query_pool[args.batch_offset:]
    if args.max_facilities and args.max_facilities > 0:
        facilities_this_run = query_pool[:args.max_facilities]
    else:
        facilities_this_run = query_pool
    query_keys = {f["facility_key"] for f in facilities_this_run}

    # Fresh this-run files start empty every run.
    all_candidates_this_run: List[Dict[str, Any]] = []
    diagnostics: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []

    if args.use_v2_cache:
        all_candidates_this_run.extend(load_cache_rows(output_root, query_keys))

    if args.live_openaq:
        for fac in facilities_this_run:
            points = []
            flat, flon = safe_float(fac.get("Lat")), safe_float(fac.get("Lon"))
            clat, clon = safe_float(fac.get("Control_Lat")), safe_float(fac.get("Control_Lon"))
            if flat is not None and flon is not None:
                points.append(("facility", flat, flon))
            if clat is not None and clon is not None:
                points.append(("control", clat, clon))
            for role, qlat, qlon in points:
                variants = query_variants(qlat, qlon, args.radius_km, args.limit_per_query)
                if not args.exhaustive:
                    variants = variants[:3]
                for method, url in variants:
                    data, diag = fetch_json(url, args.max_retries, args.sleep_seconds)
                    results = []
                    if isinstance(data, dict):
                        results = data.get("results") or []
                    diagnostics.append({
                        "facility": fac.get("Facility", ""), "facility_key": fac.get("facility_key", ""),
                        "query_point_role": role, "method": method, "url": url,
                        "http_status": diag.get("http_status", ""), "result_count": len(results),
                        "attempt": diag.get("attempt", ""), "error_type": diag.get("error_type", ""), "error_message": diag.get("error_message", ""),
                    })
                    if diag.get("error_type"):
                        errors.append(diagnostics[-1])
                    for loc in results:
                        cand = candidate_from_location(fac, role, qlat, qlon, loc)
                        if cand:
                            all_candidates_this_run.append(cand)
                    time.sleep(max(0.0, args.sleep_seconds))

    all_candidates_this_run = dedupe_candidates(all_candidates_this_run)
    selected_this_run = select_candidates(all_candidates_this_run, args.min_score)

    # Cumulative selected = previous selected + this selected, de-duped.
    cumulative_selected = dedupe_candidates(previous_selected + selected_this_run)
    status_rows = build_status(broad, validated_keys, cumulative_selected)

    # Queues/status outputs.
    no_candidate_rows = [f for f in remaining_all if f["facility_key"] not in {r["facility_key"] for r in cumulative_selected}]
    write_csv_rows(output_root / "remaining_overlay_queue.csv", remaining_all, ["Facility", "Location", "Lat", "Lon", "Easting", "Northing", "Control_Site", "Control_Lat", "Control_Lon", "Control_Easting", "Control_Northing", "facility_key"])
    write_csv_rows(output_root / "remaining_overlay_queue_after_skip.csv", query_pool, ["Facility", "Location", "Lat", "Lon", "Easting", "Northing", "Control_Site", "Control_Lat", "Control_Lon", "Control_Easting", "Control_Northing", "facility_key"])
    write_csv_rows(output_root / "queried_facilities_this_run.csv", facilities_this_run, ["Facility", "Location", "Lat", "Lon", "Easting", "Northing", "Control_Site", "Control_Lat", "Control_Lon", "Control_Easting", "Control_Northing", "facility_key"])
    write_csv_rows(output_root / "candidate_monitoring_overlays_this_run.csv", all_candidates_this_run, FIELD_SELECTED)
    write_csv_rows(output_root / "selected_candidate_overlays_this_run.csv", selected_this_run, FIELD_SELECTED)
    write_csv_rows(output_root / "selected_candidate_overlays_needing_review.csv", cumulative_selected, FIELD_SELECTED)
    write_csv_rows(output_root / "selected_candidate_overlays_cumulative.csv", cumulative_selected, FIELD_SELECTED)
    write_csv_rows(output_root / "facility_overlay_status.csv", status_rows, FIELD_STATUS)
    write_csv_rows(output_root / "facility_overlay_status_cumulative.csv", status_rows, FIELD_STATUS)
    write_csv_rows(output_root / "openaq_query_diagnostics.csv", diagnostics, FIELD_DIAG)
    (output_root / "overlay_discovery_errors.json").write_text(json.dumps(errors, indent=2), encoding="utf-8")
    # Preserve a raw candidate cumulative-ish file for compatibility but do not use for skip.
    write_csv_rows(output_root / "candidate_monitoring_overlays.csv", all_candidates_this_run, FIELD_SELECTED)

    status_counts: Dict[str, int] = {}
    for r in status_rows:
        status_counts[r["overlay_status"]] = status_counts.get(r["overlay_status"], 0) + 1
    http_200 = sum(1 for d in diagnostics if str(d.get("http_status")) == "200")
    rate_limited = sum(1 for d in diagnostics if str(d.get("http_status")) == "429")
    candidate_facilities_cumulative = len({r.get("facility_key") for r in cumulative_selected if r.get("facility_key")})

    summary = {
        "generated_utc": utc_now(),
        "workflow_version": "v3.3_stateful_batching_fixed_skip",
        "broad_facilities": len(broad),
        "validated_overlays": len(validated_keys),
        "remaining_facilities_total": len(remaining_all),
        "previous_selected_facilities_loaded": len(prev_selected_keys),
        "previous_candidate_facilities_skipped": skipped_existing,
        "query_pool_after_skip": len(query_pool),
        "batch_offset": args.batch_offset,
        "facilities_queried_this_run": len(facilities_this_run),
        "queried_facilities": [f.get("Facility", "") for f in facilities_this_run],
        "live_openaq": args.live_openaq,
        "use_v2_cache": args.use_v2_cache,
        "candidate_rows_this_run": len(all_candidates_this_run),
        "selected_candidates_this_run": len(selected_this_run),
        "selected_candidates_cumulative": len(cumulative_selected),
        "candidate_facilities_cumulative": candidate_facilities_cumulative,
        "no_candidate_selected_yet": status_counts.get("no_candidate_selected_yet", 0),
        "status_counts": status_counts,
        "diagnostic_rows": len(diagnostics),
        "http_200_calls": http_200,
        "rate_limited_calls": rate_limited,
        "error_rows": len(errors),
        "status": "candidate_discovery_complete" if facilities_this_run else "no_uncovered_facilities_queried",
        "note": "Skip logic uses selected/review candidate files only; raw candidate rows do not count as coverage.",
    }
    (output_root / "incinerator_overlay_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    # Copy validated file for artifact convenience if available.
    val_rows = read_csv_rows(Path(args.validated_overlays))
    if val_rows:
        write_csv_rows(output_root / "validated_defra_overlays.csv", val_rows, list(val_rows[0].keys()))

    if args.write_page:
        write_page(site_root, summary, status_rows, cumulative_selected)

    print(json.dumps(summary, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
