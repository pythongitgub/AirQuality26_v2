#!/usr/bin/env python3
"""AQ26 incinerator-focused backfill pack builder.

This script turns the incinerator register + overlay status into a structured
facility-led evidence/backfill pack. It optionally performs conservative live
OpenAQ probes where candidate location IDs are available, but it never treats
those probes as regulatory findings.
"""
from __future__ import annotations

import argparse, csv, json, os, time, urllib.parse, urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

NOTICE = "Exploratory AQ26 evidence backfill. Public outputs are redacted and do not make causal, health, legal or regulatory conclusions."


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def read_csv(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return [dict(r) for r in csv.DictReader(f)]


def write_csv(path: Path, rows: List[Dict[str, Any]], fieldnames: Optional[List[str]] = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        keys = []
        for r in rows:
            for k in r:
                if k not in keys:
                    keys.append(k)
        fieldnames = keys or ["empty"]
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fieldnames})


def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def norm(x: str) -> str:
    return "".join(ch for ch in (x or "").lower() if ch.isalnum())


def load_status(repo: Path) -> List[Dict[str, str]]:
    for p in [repo / "site_public/data/focus/overlays_v3/facility_overlay_status.csv", repo / "site_public/data/focus/overlays_v2/facility_overlay_status.csv"]:
        rows = read_csv(p)
        if rows:
            return rows
    return []


def load_candidates(repo: Path) -> List[Dict[str, str]]:
    for p in [
        repo / "site_public/data/focus/overlays_v3/selected_candidate_overlays_cumulative.csv",
        repo / "site_public/data/focus/overlays_v3/selected_candidate_overlays_needing_review.csv",
        repo / "site_public/data/focus/overlays_v2/selected_candidate_overlays_needing_review.csv",
    ]:
        rows = read_csv(p)
        if rows:
            return rows
    return []


def candidate_facility_key(r: Dict[str, str]) -> str:
    for k in ["facility_key", "facility", "Facility", "facility_name"]:
        if r.get(k):
            return norm(r.get(k, ""))
    return ""


def candidate_location_id(r: Dict[str, str]) -> str:
    for k in ["candidate_location_id", "location_id", "openaq_location_id", "id", "candidate_id"]:
        v = str(r.get(k, "")).strip()
        if v and v.isdigit():
            return v
    return ""


def select_facilities(rows: List[Dict[str, str]], scope: str, limit: int) -> List[Dict[str, str]]:
    if scope == "newhaven":
        out = [r for r in rows if "newhaven" in norm(r.get("facility", ""))]
    elif scope == "validated":
        out = [r for r in rows if r.get("overlay_status") == "validated_existing_overlay"]
    elif scope == "high_confidence":
        out = [r for r in rows if r.get("best_candidate_class") == "high_confidence_official_candidate" or r.get("overlay_status") == "validated_existing_overlay"]
    elif scope == "fallback":
        out = [r for r in rows if r.get("overlay_status") == "no_candidate_selected_yet"]
    else:
        out = rows[:]
    return out[:limit] if limit and limit > 0 else out


def week_windows(weeks: int) -> List[Dict[str, str]]:
    today = datetime.now(timezone.utc).date()
    # last complete Monday-to-Monday window ending today/week boundary-ish
    end = today - timedelta(days=today.weekday())
    windows = []
    for i in range(max(1, weeks)):
        e = end - timedelta(days=7*i)
        s = e - timedelta(days=7)
        windows.append({"week_start": s.isoformat(), "week_end": e.isoformat()})
    return list(reversed(windows))


def openaq_get(url: str, key: str, timeout: int = 30) -> Dict[str, Any]:
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "AQ26/1.0"})
    if key:
        req.add_header("X-API-Key", key)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return {"ok": True, "status": resp.status, "url": url, "json": json.loads(body)}
    except Exception as e:
        return {"ok": False, "url": url, "error": type(e).__name__ + ": " + str(e)}


def probe_location(location_id: str, key: str) -> List[Dict[str, Any]]:
    base = "https://api.openaq.org/v3"
    urls = [
        f"{base}/locations/{location_id}",
        f"{base}/locations/{location_id}/latest",
        f"{base}/latest?locations_id={urllib.parse.quote(location_id)}&limit=100",
    ]
    out = []
    for u in urls:
        res = openaq_get(u, key)
        rec = {"location_id": location_id, "url": u, "ok": res.get("ok"), "status": res.get("status", ""), "error": res.get("error", "")}
        data = res.get("json") if res.get("ok") else None
        if isinstance(data, dict):
            rec["top_keys"] = ",".join(list(data.keys())[:10])
            # avoid storing huge raw payloads publicly; unredacted can inspect diagnostics if needed.
            rec["results_count"] = len(data.get("results", [])) if isinstance(data.get("results"), list) else ""
        out.append(rec)
        time.sleep(0.3)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--site-root", default="site_public")
    ap.add_argument("--unredacted-site", default="site_unredacted")
    ap.add_argument("--scope", default="high_confidence", choices=["newhaven", "validated", "high_confidence", "fallback", "all"])
    ap.add_argument("--weeks", default="8")
    ap.add_argument("--limit-facilities", default="0")
    ap.add_argument("--live-openaq", action="store_true")
    ap.add_argument("--sleep-seconds", default="0.5")
    args = ap.parse_args()
    repo = Path(args.repo_root).resolve()
    site = repo / args.site_root
    unred = repo / args.unredacted_site
    out = site / "data/backfill/incinerators"
    out_un = unred / "data/backfill/incinerators"
    out.mkdir(parents=True, exist_ok=True); out_un.mkdir(parents=True, exist_ok=True)

    status_rows = load_status(repo)
    candidates = load_candidates(repo)
    cand_by_fac = defaultdict(list)
    for c in candidates:
        cand_by_fac[candidate_facility_key(c)].append(c)

    facilities = select_facilities(status_rows, args.scope, int(args.limit_facilities or 0))
    windows = week_windows(int(args.weeks or 8))
    diagnostics = []
    facility_records = []
    key = os.environ.get("OPENAQ_API_KEY", "")

    for f in facilities:
        fkey = f.get("facility_key") or norm(f.get("facility", ""))
        cands = cand_by_fac.get(norm(fkey), []) or cand_by_fac.get(norm(f.get("facility", "")), [])
        loc_ids = []
        for c in cands:
            lid = candidate_location_id(c)
            if lid and lid not in loc_ids:
                loc_ids.append(lid)
        if args.live_openaq:
            for lid in loc_ids[:2]:
                diagnostics.extend(probe_location(lid, key))
                time.sleep(float(args.sleep_seconds or 0.5))
        facility_records.append({
            "facility": f.get("facility"),
            "facility_key": fkey,
            "overlay_status": f.get("overlay_status"),
            "best_candidate_site": f.get("best_candidate_site"),
            "best_candidate_score": f.get("best_candidate_score"),
            "best_candidate_class": f.get("best_candidate_class"),
            "candidate_rows_available": len(cands),
            "openaq_location_ids_found": ";".join(loc_ids),
            "weeks_requested": len(windows),
            "backfill_readiness": "live_probe_attempted" if args.live_openaq and loc_ids else "metadata_ready",
            "public_note": NOTICE,
        })

    counts = Counter(r.get("overlay_status", "") for r in status_rows)
    score_bands = Counter()
    for r in status_rows:
        try:
            s = int(float(r.get("best_candidate_score") or 0))
        except Exception:
            s = 0
        if s >= 85: score_bands["A 85+"] += 1
        elif s >= 70: score_bands["B 70-84"] += 1
        elif s >= 55: score_bands["C 55-69"] += 1
        elif s > 0: score_bands["D <55"] += 1
        else: score_bands["Pending"] += 1

    summary = {
        "generated_utc": now_utc(),
        "scope": args.scope,
        "weeks": windows,
        "facilities_in_register": len(status_rows),
        "facilities_selected": len(facilities),
        "validated_overlays": counts.get("validated_existing_overlay", 0),
        "candidate_overlays": counts.get("candidate_overlay_needs_review", 0),
        "unresolved_facilities": counts.get("no_candidate_selected_yet", 0),
        "live_openaq": bool(args.live_openaq),
        "diagnostic_rows": len(diagnostics),
        "notice": NOTICE,
    }
    write_json(out / "focused_backfill_summary.json", summary)
    write_json(out_un / "focused_backfill_summary_unredacted.json", {**summary, "diagnostics_preview": diagnostics[:25]})
    write_csv(out / "facility_backfill_readiness.csv", facility_records)
    write_csv(out_un / "facility_backfill_readiness_unredacted.csv", facility_records)
    write_csv(out_un / "openaq_live_probe_diagnostics.csv", diagnostics)
    write_json(out / "charts/overlay_status_chart.json", dict(counts))
    write_json(out / "charts/candidate_score_bands.json", dict(score_bands))
    write_json(out / "charts/backfill_scope_summary.json", summary)
    # Also update weekly data input for alert page.
    write_json(site / "data/weekly/focused_backfill_status.json", {"status": "completed", **summary})
    print(json.dumps(summary, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
