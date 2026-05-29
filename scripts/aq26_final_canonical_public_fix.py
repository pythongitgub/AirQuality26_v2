#!/usr/bin/env python3
"""
AQ26 final canonical public fix.

Purpose:
- stop legacy duplicate/fallback rows from making the public site say 86 facilities / 43 fallback cases
- rebuild the public tables from the canonical overlay status file
- keep the weekly alert, WEBM banner and legal wording intact
- keep unredacted auth files out of git

This is a post-build/public-polish step. It should run after the operational site builder and after
weekly alert injection, and before commit/deploy.
"""
from __future__ import annotations

import argparse
import csv
import html
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List


STATUS_PRIORITY = {
    "validated_existing_overlay": 0,
    "candidate_overlay_needs_review": 1,
    "no_candidate_selected_yet": 2,
    "": 9,
}
STATUS_LABEL = {
    "validated_existing_overlay": "Validated overlay",
    "candidate_overlay_needs_review": "Candidate under review",
    "no_candidate_selected_yet": "Fallback discovery needed",
}
PILL_CLASS = {
    "validated_existing_overlay": "validated",
    "candidate_overlay_needs_review": "candidate",
    "no_candidate_selected_yet": "missing",
}


def norm(x: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (x or "").lower())


def esc(x: Any) -> str:
    return html.escape("" if x is None else str(x), quote=True)


def safe_int(x: Any, default: int = 0) -> int:
    try:
        if x in (None, ""):
            return default
        return int(float(str(x).strip()))
    except Exception:
        return default


def read_csv(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return [dict(r) for r in csv.DictReader(f)]


def write_csv(path: Path, rows: List[Dict[str, Any]], fields: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def choose_better(current: Dict[str, str] | None, candidate: Dict[str, str]) -> Dict[str, str]:
    if current is None:
        return candidate
    cs = current.get("overlay_status", "")
    ns = candidate.get("overlay_status", "")
    cp = STATUS_PRIORITY.get(cs, 9)
    np = STATUS_PRIORITY.get(ns, 9)
    if np < cp:
        return candidate
    if np > cp:
        return current
    # Same status: keep the higher-scoring candidate row.
    if safe_int(candidate.get("best_candidate_score")) > safe_int(current.get("best_candidate_score")):
        return candidate
    # Prefer rows with an actual candidate site rather than blank placeholders.
    if candidate.get("best_candidate_site") and not current.get("best_candidate_site"):
        return candidate
    return current


def canonical_rows(repo: Path) -> List[Dict[str, str]]:
    root = repo / "site_public/data/focus/overlays_v3"
    status = read_csv(root / "facility_overlay_status.csv")
    if not status:
        status = read_csv(root / "facility_overlay_status_cumulative.csv")
    if not status:
        raise SystemExit("No overlay status CSV found under site_public/data/focus/overlays_v3")

    by_key: Dict[str, Dict[str, str]] = {}
    for r in status:
        fac = r.get("facility") or r.get("Facility") or r.get("facility_name") or ""
        key = r.get("facility_key") or norm(fac)
        if not key:
            continue
        rr = dict(r)
        rr["facility_key"] = key
        rr["facility"] = fac or key
        # Normalise blank / unknown status
        if rr.get("overlay_status") not in STATUS_PRIORITY:
            rr["overlay_status"] = rr.get("overlay_status") or "no_candidate_selected_yet"
        by_key[key] = choose_better(by_key.get(key), rr)

    rows = list(by_key.values())
    rows.sort(key=lambda r: (
        STATUS_PRIORITY.get(r.get("overlay_status", ""), 9),
        -safe_int(r.get("best_candidate_score")),
        r.get("facility", ""),
    ))
    return rows


def summary_from_rows(rows: List[Dict[str, str]]) -> Dict[str, Any]:
    c = Counter(r.get("overlay_status", "") for r in rows)
    total = len(rows)
    validated = c.get("validated_existing_overlay", 0)
    candidates = c.get("candidate_overlay_needs_review", 0)
    fallback = c.get("no_candidate_selected_yet", 0)
    coverage = round(((validated + candidates) * 100 / total), 1) if total else 0.0
    return {
        "total_facilities": total,
        "validated_overlays": validated,
        "candidate_overlays": candidates,
        "unresolved_facilities": fallback,
        "overlay_path_facilities": validated + candidates,
        "overlay_path_coverage_pct": coverage,
        "high_confidence_candidates": sum(1 for r in rows if r.get("best_candidate_class") == "high_confidence_official_candidate"),
        "unresolved_names": [r.get("facility") for r in rows if r.get("overlay_status") == "no_candidate_selected_yet"],
        "counts": {"validated": validated, "candidate": candidates, "missing": fallback},
    }


def status_pill(status: str) -> str:
    cls = PILL_CLASS.get(status, "missing")
    label = STATUS_LABEL.get(status, status or "Fallback discovery needed")
    return f"<span class='pill {cls}'>{esc(label)}</span>"


def table_rows(rows: List[Dict[str, str]], limit: int | None = None) -> str:
    out = []
    show = rows[:limit] if limit else rows
    for r in show:
        status = r.get("overlay_status", "")
        fac = r.get("facility", "")
        loc = r.get("location") or r.get("county") or r.get("postcode") or ""
        score = r.get("best_candidate_score") or ""
        out.append(
            "<tr data-facility-row data-status='{status}'>"
            "<td><b>{facility}</b><br><small>{location}</small></td>"
            "<td>{pill}</td>"
            "<td>{site}</td>"
            "<td>{score}</td>"
            "<td>{cls}</td>"
            "</tr>".format(
                status=esc(status),
                facility=esc(fac),
                location=esc(loc),
                pill=status_pill(status),
                site=esc(r.get("best_candidate_site") or "—"),
                score=esc(score if score else "—"),
                cls=esc(r.get("best_candidate_class") or "—"),
            )
        )
    return "\n".join(out)


def replace_table_body(text: str, rows: List[Dict[str, str]], page_name: str) -> str:
    limit = 18 if page_name == "index.html" else None
    new_body = table_rows(rows, limit=limit)
    # Replace every facility status table body on pages where these pages contain one.
    pattern = re.compile(r"(<table[^>]*>\s*<thead>\s*<tr>\s*<th>Facility</th>.*?</thead>\s*<tbody>)(.*?)(</tbody>)", re.I | re.S)
    return pattern.sub(lambda m: m.group(1) + new_body + m.group(3), text)


def fix_counts_text(text: str, s: Dict[str, Any]) -> str:
    total = str(s["total_facilities"])
    val = str(s["validated_overlays"])
    cand = str(s["candidate_overlays"])
    fall = str(s["unresolved_facilities"])
    coverage = str(s["overlay_path_coverage_pct"])

    replacements = [
        (r"\b86(?=\s*(?:incinerator / EfW facilities|facilities|England/Wales incinerator|facilities in register))", total),
        (r"\b43(?=\s*(?:fallback discovery cases|fallback cases|manual fallback discovery|Need non-OpenAQ/manual discovery))", fall),
        (r"\b50% of facilities\b", f"{coverage}% of facilities"),
        (r"overlay path for 50% of facilities", f"overlay path for {coverage}% of facilities"),
        (r"\b43 fallback discovery cases\b", f"{fall} fallback discovery cases"),
        (r"\b86 facilities in register\b", f"{total} facilities in register"),
    ]
    for pat, rep in replacements:
        text = re.sub(pat, rep, text)

    # Normalise common phrases.
    text = re.sub(r"(\bAQ26 register\s+)(?:\d+\s+)?8 validated monitoring overlays", r"\g<1>8 validated monitoring overlays", text)
    return text


def fix_embedded_data(text: str, s: Dict[str, Any]) -> str:
    # Replace common JSON count snippets used by Chart.js / AQ26_DATA.
    text = re.sub(r'("total"\s*:\s*)\d+', rf'\g<1>{s["total_facilities"]}', text)
    text = re.sub(r'("validated"\s*:\s*)\d+', rf'\g<1>{s["validated_overlays"]}', text)
    text = re.sub(r'("candidate"\s*:\s*)\d+', rf'\g<1>{s["candidate_overlays"]}', text)
    text = re.sub(r'("missing"\s*:\s*)\d+', rf'\g<1>{s["unresolved_facilities"]}', text)
    text = re.sub(r'("unresolved_facilities"\s*:\s*)\d+', rf'\g<1>{s["unresolved_facilities"]}', text)
    text = re.sub(r'("candidate_overlays"\s*:\s*)\d+', rf'\g<1>{s["candidate_overlays"]}', text)
    text = re.sub(r'("validated_overlays"\s*:\s*)\d+', rf'\g<1>{s["validated_overlays"]}', text)
    text = re.sub(r'("total_facilities"\s*:\s*)\d+', rf'\g<1>{s["total_facilities"]}', text)
    return text


def remove_extra_logo_text(text: str) -> str:
    # Remove duplicated text label beside full logo, leaving image link intact.
    text = re.sub(r"<span>\s*<small>\s*SCC\s*Nexus\s*·\s*AQ26\s*</small>\s*</span>", "", text, flags=re.I)
    text = re.sub(r"<span>\s*<small>\s*SCC\s*NEXUS\s*·\s*AQ26\s*</small>\s*</span>", "", text, flags=re.I)
    return text


def process_site(site: Path, rows: List[Dict[str, str]], s: Dict[str, Any]) -> List[str]:
    changed = []
    for page in ["index.html", "incinerators.html", "newhaven.html", "overlays.html", "comparisons.html", "weekly-update.html"]:
        p = site / page
        if not p.exists():
            continue
        txt = p.read_text(encoding="utf-8", errors="replace")
        new = remove_extra_logo_text(txt)
        new = fix_counts_text(new, s)
        new = fix_embedded_data(new, s)
        if page in {"index.html", "incinerators.html", "overlays.html"}:
            new = replace_table_body(new, rows, page)
        if new != txt:
            p.write_text(new, encoding="utf-8")
            changed.append(str(p))
    return changed


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--public-site", default="site_public")
    ap.add_argument("--unredacted-site", default="site_unredacted")
    ap.add_argument("--summary-out", default="site_public/data/focus/final_canonical_public_fix.json")
    args = ap.parse_args()

    repo = Path(args.repo_root).resolve()
    public = repo / args.public_site
    unred = repo / args.unredacted_site

    rows = canonical_rows(repo)
    s = summary_from_rows(rows)

    fields = ["facility_key","facility","location","overlay_status","best_candidate_site","best_candidate_score","best_candidate_class","suggested_action"]
    public_rows = [{k: r.get(k, "") for k in fields} for r in rows]
    write_csv(public / "data/focus/operational/public_facility_overlay_status.csv", public_rows, fields)
    write_json(public / "data/focus/operational/public_overlay_summary.json", s)
    write_json(public / "data/focus/operational/chart_data.json", {"total": s["total_facilities"], "counts": s["counts"]})
    write_json(repo / args.summary_out, {"ok": True, **s})

    changed = []
    if public.exists():
        changed += process_site(public, rows, s)
    if unred.exists():
        changed += process_site(unred, rows, s)

    # Safety validation.
    for p in [public / "index.html", public / "incinerators.html", public / "newhaven.html"]:
        if p.exists():
            txt = p.read_text(encoding="utf-8", errors="replace")
            bad = []
            if "86 facilities" in txt or ">86<" in txt:
                bad.append("86")
            if "43 fallback" in txt or ">43<" in txt:
                bad.append("43")
            if bad:
                raise SystemExit(f"Legacy count(s) still visible in {p}: {bad}")

    print(json.dumps({"ok": True, "changed": changed, **s}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
