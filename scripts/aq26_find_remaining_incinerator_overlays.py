#!/usr/bin/env python3
"""
AQ26 remaining incinerator overlay finder.

Purpose
-------
Use the broad England/Wales incinerator/control-site register as the spine,
retain the existing validated DEFRA/AURN overlays, then discover/score candidate
monitoring overlays for the remaining facilities from:

1) existing validated DEFRA overlay CSV;
2) optional local/public provider inventories already generated in site_public/data;
3) OpenAQ live locations, when OPENAQ_API_KEY is available.

Outputs are written under site_public/data/focus/ and can be used by the public
site and the protected unredacted review site.

This script is intentionally conservative: it does not claim an overlay is
validated unless it came from the validated CSV or is explicitly accepted later.
Live-discovered candidates are marked as candidate_needs_review.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

POLLUTANT_HINTS = {
    "pm25": "PM2.5", "pm2.5": "PM2.5", "pm10": "PM10", "no2": "NO2", "nitrogen dioxide": "NO2",
    "so2": "SO2", "sulphur dioxide": "SO2", "sulfur dioxide": "SO2", "o3": "O3", "ozone": "O3",
    "co": "CO", "carbon monoxide": "CO", "nox": "NOx", "benzene": "benzene"
}
CORE_POLLUTANTS = {"NO2", "PM2.5", "PM10", "SO2", "O3", "CO", "NOx", "benzene"}


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def norm_text(value: Any) -> str:
    s = str(value or "").lower()
    s = re.sub(r"\b(energy recovery facility|energy from waste|waste recovery park|resource recovery facility|resource recovery|incinerator|efw|erf|rerf|rrf|wrp|wte|tps|ps|mf2)\b", " ", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return " ".join(s.split())


def safe_float(value: Any) -> Optional[float]:
    try:
        if value is None or str(value).strip() == "":
            return None
        return float(value)
    except Exception:
        return None


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0088
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def read_csv_rows(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=False), encoding="utf-8")


def write_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cols: List[str] = []
    for row in rows:
        for k in row.keys():
            if k not in cols:
                cols.append(k)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for row in rows:
            w.writerow(row)


def facility_id(name: str) -> str:
    s = norm_text(name)
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "unknown-facility"


def rows_match_facility(a: str, b: str) -> bool:
    na, nb = norm_text(a), norm_text(b)
    if not na or not nb:
        return False
    return na == nb or na in nb or nb in na


def pollutant_names_from_location(loc: Dict[str, Any]) -> List[str]:
    found = set()
    for key in ("parameters", "sensors"):
        vals = loc.get(key) or []
        if isinstance(vals, dict):
            vals = list(vals.values())
        for item in vals:
            if isinstance(item, str):
                text = item
            elif isinstance(item, dict):
                text = " ".join(str(item.get(k, "")) for k in ("name", "displayName", "parameter", "parameter_name", "id"))
            else:
                text = str(item)
            low = text.lower()
            for hint, canonical in POLLUTANT_HINTS.items():
                if hint in low:
                    found.add(canonical)
    return sorted(found)


def opaq_headers() -> Dict[str, str]:
    headers = {"User-Agent": "AQ26-incinerator-overlay/1.0"}
    key = os.environ.get("OPENAQ_API_KEY", "").strip()
    if key:
        headers["X-API-Key"] = key
    return headers


def fetch_json(url: str, timeout: int = 30) -> Any:
    req = urllib.request.Request(url, headers=opaq_headers())
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def openaq_nearby_locations(lat: float, lon: float, radius_m: int, limit: int, pause: float = 0.25) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    base = "https://api.openaq.org/v3/locations"
    params = {
        "coordinates": f"{lat},{lon}",
        "radius": str(radius_m),
        "limit": str(limit),
        "sort": "distance",
        "order_by": "distance",
    }
    url = base + "?" + urllib.parse.urlencode(params)
    try:
        data = fetch_json(url)
        time.sleep(pause)
        results = data.get("results") if isinstance(data, dict) else []
        if isinstance(results, list):
            return results, None
        return [], "openaq_unexpected_results_shape"
    except Exception as e:
        return [], f"openaq_error: {type(e).__name__}: {e}"


def candidate_from_openaq(loc: Dict[str, Any], facility: Dict[str, Any], source_point: str) -> Optional[Dict[str, Any]]:
    coords = loc.get("coordinates") or {}
    lat = safe_float(coords.get("latitude") or coords.get("lat"))
    lon = safe_float(coords.get("longitude") or coords.get("lon"))
    if lat is None or lon is None:
        return None
    f_lat = safe_float(facility.get("Lat"))
    f_lon = safe_float(facility.get("Lon"))
    c_lat = safe_float(facility.get("Control_Lat"))
    c_lon = safe_float(facility.get("Control_Lon"))
    dist_fac = haversine_km(f_lat, f_lon, lat, lon) if f_lat is not None and f_lon is not None else None
    dist_ctl = haversine_km(c_lat, c_lon, lat, lon) if c_lat is not None and c_lon is not None else None
    pollutants = pollutant_names_from_location(loc)
    provider_text = " ".join(str(loc.get(k, "")) for k in ("provider", "owner", "source", "name", "locality", "timezone"))
    name = str(loc.get("name") or loc.get("locality") or loc.get("id") or "OpenAQ location")
    score = 0.0
    if dist_fac is not None:
        score += max(0.0, 40.0 - min(dist_fac, 40.0))
    if dist_ctl is not None:
        score += max(0.0, 20.0 - min(dist_ctl, 20.0))
    score += min(25.0, len(set(pollutants) & CORE_POLLUTANTS) * 4.0)
    if re.search(r"defra|aurn|uk-air|air quality england|environment", provider_text, re.I):
        score += 15.0
    return {
        "facility_id": facility_id(facility.get("Facility", "")),
        "facility": facility.get("Facility"),
        "location": facility.get("Location"),
        "candidate_source": "openaq_live",
        "candidate_status": "candidate_needs_review",
        "source_point": source_point,
        "candidate_name": name,
        "candidate_id": loc.get("id"),
        "candidate_lat": lat,
        "candidate_lon": lon,
        "distance_facility_km": round(dist_fac, 3) if dist_fac is not None else None,
        "distance_control_km": round(dist_ctl, 3) if dist_ctl is not None else None,
        "pollutants": ", ".join(pollutants),
        "provider_text": provider_text[:240],
        "score": round(score, 2),
        "raw_location_url": f"https://api.openaq.org/v3/locations/{loc.get('id')}" if loc.get("id") else None,
    }


def validated_overlay_rows(broad_rows: List[Dict[str, Any]], validated_rows: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    accepted, remaining = [], []
    for br in broad_rows:
        match = None
        for vr in validated_rows:
            if rows_match_facility(br.get("Facility", ""), vr.get("Facility", "")):
                match = vr
                break
        if match:
            row = {
                "facility_id": facility_id(br.get("Facility", "")),
                "facility": br.get("Facility"),
                "location": br.get("Location"),
                "overlay_source": "validated_defra_aurn_csv",
                "overlay_status": "validated",
                "defra_site_name": match.get("DEFRA_Site_Name"),
                "defra_site_code": match.get("DEFRA_Site_Code"),
                "defra_site_lat": safe_float(match.get("DEFRA_Site_Lat")),
                "defra_site_lon": safe_float(match.get("DEFRA_Site_Lon")),
                "defra_mapping_confidence": match.get("DEFRA_Mapping_Confidence"),
                "distance_facility_to_defra_km": safe_float(match.get("Distance_Facility_to_DEFRA_km")),
                "distance_control_to_defra_km": safe_float(match.get("Distance_Control_to_DEFRA_km")),
                "distance_receptor_to_defra_km": safe_float(match.get("Distance_Receptor_to_DEFRA_km")),
                "control_site": match.get("Control_Site") or br.get("Control_Site"),
                "control_lat": safe_float(match.get("Control_Lat") or br.get("Control_Lat")),
                "control_lon": safe_float(match.get("Control_Lon") or br.get("Control_Lon")),
                "receptor_site": match.get("Receptor_Site"),
                "receptor_role": match.get("Receptor_Role"),
            }
            accepted.append(row)
        else:
            remaining.append(br)
    return accepted, remaining


def build_html_page(out: Path, summary: Dict[str, Any], selected: List[Dict[str, Any]], remaining: List[Dict[str, Any]], candidates: List[Dict[str, Any]]) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    selected_rows = "".join(
        f"<tr><td>{r.get('facility')}</td><td>{r.get('defra_site_name') or r.get('candidate_name')}</td><td>{r.get('overlay_status') or r.get('candidate_status')}</td><td>{r.get('distance_facility_to_defra_km') or r.get('distance_facility_km') or ''}</td></tr>"
        for r in selected[:80]
    )
    rem_rows = "".join(f"<tr><td>{r.get('Facility')}</td><td>{r.get('Location')}</td><td>{r.get('Control_Site')}</td></tr>" for r in remaining[:80])
    cand_rows = "".join(
        f"<tr><td>{r.get('facility')}</td><td>{r.get('candidate_name')}</td><td>{r.get('distance_facility_km')}</td><td>{r.get('pollutants')}</td><td>{r.get('score')}</td></tr>"
        for r in sorted(candidates, key=lambda x: x.get('score', 0), reverse=True)[:120]
    )
    html = f"""<!doctype html>
<html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>AQ26 Incinerator Overlay Finder</title>
<style>
body{{margin:0;font-family:Inter,Arial,sans-serif;background:#f5f8fb;color:#102033}}header{{background:#fff;border-bottom:1px solid #dde5ee;padding:18px 24px}}main{{max-width:1180px;margin:auto;padding:28px}}.hero{{background:linear-gradient(135deg,#10324a,#0d7b8a);color:#fff;border-radius:24px;padding:28px;margin-bottom:24px;box-shadow:0 18px 50px rgba(16,50,74,.18)}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:16px}}.card{{background:#fff;border:1px solid #dde5ee;border-radius:18px;padding:18px;box-shadow:0 10px 30px rgba(16,50,74,.08)}}.num{{font-size:2rem;font-weight:800}}table{{width:100%;border-collapse:collapse;background:#fff;border-radius:14px;overflow:hidden;margin:16px 0 28px}}th,td{{border-bottom:1px solid #e5edf5;padding:10px;text-align:left;font-size:.92rem;vertical-align:top}}th{{background:#eaf2f8}}h2{{margin-top:34px}}code{{background:#eaf2f8;padding:2px 5px;border-radius:5px}}</style></head><body>
<header><strong>SCC Nexus · AQ26</strong> Incinerator facility overlay finder</header><main>
<section class='hero'><h1>England/Wales incinerator monitoring overlay</h1><p>Facility-led overlay status for validated DEFRA/AURN sites and candidate monitoring overlays. Newhaven remains the proof-of-quality focus while the remaining facilities are resolved.</p></section>
<section class='grid'>
<div class='card'><div class='num'>{summary.get('broad_facilities')}</div><div>Broad facilities</div></div>
<div class='card'><div class='num'>{summary.get('validated_overlays')}</div><div>Validated DEFRA/AURN overlays</div></div>
<div class='card'><div class='num'>{summary.get('remaining_without_validated_overlay')}</div><div>Remaining needing overlay</div></div>
<div class='card'><div class='num'>{summary.get('live_candidate_rows')}</div><div>Live candidate rows</div></div>
</section>
<h2>Validated / selected overlays</h2><table><tr><th>Facility</th><th>Overlay station</th><th>Status</th><th>Distance km</th></tr>{selected_rows}</table>
<h2>Remaining facilities needing overlay validation</h2><table><tr><th>Facility</th><th>Location</th><th>Current control site</th></tr>{rem_rows}</table>
<h2>Candidate monitoring overlays from live/API discovery</h2><table><tr><th>Facility</th><th>Candidate</th><th>Facility km</th><th>Pollutants</th><th>Score</th></tr>{cand_rows}</table>
<p>Full JSON/CSV outputs are available under <code>site_public/data/focus/overlays/</code>. Candidate overlays are not validated until reviewed.</p>
</main></body></html>"""
    out.write_text(html, encoding="utf-8")


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--broad-register", default="configs/aq26_incinerator_register/UK_Incinerators_with_Controls_Full_v3.csv")
    ap.add_argument("--validated-overlay", default="configs/aq26_incinerator_register/UK_Incinerators_with_DEFRA_Sites_v3_validated_Full.csv")
    ap.add_argument("--site-root", default="site_public")
    ap.add_argument("--output-dir", default="site_public/data/focus/overlays")
    ap.add_argument("--max-facilities", type=int, default=0, help="0 means all remaining facilities")
    ap.add_argument("--radius-km", type=float, default=50.0)
    ap.add_argument("--limit-per-query", type=int, default=50)
    ap.add_argument("--live-openaq", action="store_true")
    ap.add_argument("--write-page", action="store_true")
    ap.add_argument("--min-score", type=float, default=45.0)
    args = ap.parse_args(argv)

    broad_rows = read_csv_rows(Path(args.broad_register))
    validated_rows = read_csv_rows(Path(args.validated_overlay))
    accepted, remaining = validated_overlay_rows(broad_rows, validated_rows)
    if args.max_facilities and args.max_facilities > 0:
        remaining_to_query = remaining[: args.max_facilities]
    else:
        remaining_to_query = remaining

    candidates: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []
    if args.live_openaq:
        radius_m = int(args.radius_km * 1000)
        for fac in remaining_to_query:
            for label, lat_key, lon_key in (("facility", "Lat", "Lon"), ("control", "Control_Lat", "Control_Lon")):
                lat = safe_float(fac.get(lat_key)); lon = safe_float(fac.get(lon_key))
                if lat is None or lon is None:
                    errors.append({"facility": fac.get("Facility"), "source_point": label, "error": "missing_coordinates"})
                    continue
                rows, err = openaq_nearby_locations(lat, lon, radius_m, args.limit_per_query)
                if err:
                    errors.append({"facility": fac.get("Facility"), "source_point": label, "error": err})
                    continue
                for loc in rows:
                    cand = candidate_from_openaq(loc, fac, label)
                    if cand:
                        candidates.append(cand)

    # choose top candidate per remaining facility, but do not call it validated
    selected_candidates: List[Dict[str, Any]] = []
    by_fac: Dict[str, List[Dict[str, Any]]] = {}
    for c in candidates:
        by_fac.setdefault(c["facility_id"], []).append(c)
    for fid, rows in by_fac.items():
        best = sorted(rows, key=lambda x: x.get("score", 0), reverse=True)[0]
        if best.get("score", 0) >= args.min_score:
            selected_candidates.append(best)

    out_dir = Path(args.output_dir)
    site_root = Path(args.site_root)
    summary = {
        "generated_at_utc": utc_now(),
        "broad_facilities": len(broad_rows),
        "validated_overlays": len(accepted),
        "remaining_without_validated_overlay": len(remaining),
        "remaining_queried": len(remaining_to_query),
        "live_openaq_enabled": bool(args.live_openaq),
        "live_candidate_rows": len(candidates),
        "selected_candidate_overlays_needing_review": len(selected_candidates),
        "errors": len(errors),
        "note": "Candidate overlays are not validated; use for review queue only. Validated overlays come from the DEFRA/AURN overlay CSV.",
    }

    write_json(out_dir / "incinerator_overlay_summary.json", summary)
    write_json(out_dir / "validated_defra_overlays.json", accepted)
    write_json(out_dir / "remaining_overlay_queue.json", remaining)
    write_json(out_dir / "candidate_monitoring_overlays.json", candidates)
    write_json(out_dir / "selected_candidate_overlays_needing_review.json", selected_candidates)
    write_json(out_dir / "overlay_discovery_errors.json", errors)
    write_csv(out_dir / "validated_defra_overlays.csv", accepted)
    write_csv(out_dir / "remaining_overlay_queue.csv", remaining)
    write_csv(out_dir / "candidate_monitoring_overlays.csv", candidates)
    write_csv(out_dir / "selected_candidate_overlays_needing_review.csv", selected_candidates)

    if args.write_page:
        build_html_page(site_root / "incinerator-overlays.html", summary, accepted + selected_candidates, remaining, candidates)

    print(json.dumps({"ok": True, **summary}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
