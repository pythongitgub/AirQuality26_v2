#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, re
from pathlib import Path
from datetime import datetime, timezone

BRAND_TEXT_PATTERNS = [
    re.compile(r"<span>\s*<small>\s*SCC\s+Nexus\s*·\s*AQ26\s*</small>\s*</span>", re.I),
    re.compile(r"<span>\s*<small>\s*SCC\s+NEXUS\s*·\s*AQ26\s*</small>\s*</span>", re.I),
    re.compile(r"<span>\s*<small>\s*SCC\s+Nexus\s*&middot;\s*AQ26\s*</small>\s*</span>", re.I),
]

def read_json(path: Path) -> dict:
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
    except Exception:
        pass
    return {}

def first_summary(repo: Path, public: Path) -> dict:
    candidates = [
        public / "data/weekly/latest_alert.json",
        repo / "site_public/data/weekly/latest_alert.json",
        public / "data/backfill/incinerators/focused_backfill_summary.json",
        repo / "site_public/data/backfill/incinerators/focused_backfill_summary.json",
        public / "data/focus/overlays_v3/incinerator_overlay_summary.json",
        repo / "site_public/data/focus/overlays_v3/incinerator_overlay_summary.json",
    ]
    data = {}
    for p in candidates:
        data = read_json(p)
        if data:
            break
    total = int(data.get("total_facilities") or data.get("facilities_in_register") or data.get("broad_facilities") or 46)
    validated = int(data.get("validated_overlays") or 8)
    candidate = int(data.get("candidate_overlays") or data.get("candidate_facilities_cumulative") or 35)
    unresolved = int(data.get("unresolved_facilities") or data.get("no_candidate_selected_yet") or 3)
    return {
        "total": total,
        "validated": validated,
        "candidate": candidate,
        "unresolved": unresolved,
        "source": str(p) if data else "defaults",
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

def update_html(text: str, summary: dict) -> tuple[str, list[str]]:
    changes = []
    old = text

    for rx in BRAND_TEXT_PATTERNS:
        text2 = rx.sub("", text)
        if text2 != text:
            changes.append("removed_extra_brand_text")
            text = text2

    # Correct generated JS chart payloads from legacy duplicated register merges.
    replacements = [
        (r'"total"\s*:\s*\d+', f'"total": {summary["total"]}', "fixed_js_total"),
        (r'"validated"\s*:\s*\d+', f'"validated": {summary["validated"]}', "fixed_js_validated"),
        (r'"candidate"\s*:\s*\d+', f'"candidate": {summary["candidate"]}', "fixed_js_candidate"),
        (r'"missing"\s*:\s*\d+', f'"missing": {summary["unresolved"]}', "fixed_js_missing"),
    ]
    for pat, rep, label in replacements:
        text2 = re.sub(pat, rep, text)
        if text2 != text:
            changes.append(label)
            text = text2

    # Correct public ticker text/counts. These are visible to users.
    ticker_repls = [
        (r"<span><b>\d+</b>\s*facilities in register</span>", f"<span><b>{summary['total']}</b> facilities in register</span>", "fixed_ticker_total"),
        (r"<span><b>\d+</b>\s*validated overlays</span>", f"<span><b>{summary['validated']}</b> validated overlays</span>", "fixed_ticker_validated"),
        (r"<span><b>\d+</b>\s*candidate overlays under review</span>", f"<span><b>{summary['candidate']}</b> candidate overlays under review</span>", "fixed_ticker_candidate"),
        (r"<span><b>\d+</b>\s*fallback discovery cases</span>", f"<span><b>{summary['unresolved']}</b> fallback discovery cases</span>", "fixed_ticker_fallback"),
        (r"<span><b>\d+</b>\s*manual fallback discovery</span>", f"<span><b>{summary['unresolved']}</b> manual fallback discovery</span>", "fixed_ticker_manual_fallback"),
    ]
    for pat, rep, label in ticker_repls:
        text2 = re.sub(pat, rep, text, flags=re.I)
        if text2 != text:
            changes.append(label)
            text = text2

    # Clean accidental plain-text leakage from ticker extraction/legacy fragments.
    text2 = re.sub(r"\b86\s+facilities in register\b", f"{summary['total']} facilities in register", text, flags=re.I)
    if text2 != text:
        changes.append("fixed_plain_86_facilities")
        text = text2

    # Make favicon cache busting explicit if a page still has old versions.
    if "favicon.ico" not in text:
        text = text.replace("</head>", '<link rel="icon" href="/favicon.ico?v=aq26-public-sanity" sizes="any">\n</head>')
        changes.append("added_favicon_ico")
    if "assets/favicon.svg" not in text and "favicon.svg" not in text:
        text = text.replace("</head>", '<link rel="icon" href="/favicon.svg?v=aq26-public-sanity" type="image/svg+xml">\n</head>')
        changes.append("added_favicon_svg")

    return text, changes

def process_site(site: Path, summary: dict) -> dict:
    changed = []
    for p in sorted(site.glob("*.html")):
        txt = p.read_text(encoding="utf-8", errors="replace")
        new, changes = update_html(txt, summary)
        if new != txt:
            p.write_text(new, encoding="utf-8")
            changed.append({"path": str(p), "changes": sorted(set(changes))})
    return {"site": str(site), "changed_count": len(changed), "changed": changed}

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--public-site", default="site_public")
    ap.add_argument("--unredacted-site", default="site_unredacted")
    ap.add_argument("--summary", default="site_public/data/weekly/public_sanity_fix_status.json")
    args = ap.parse_args()

    repo = Path(args.repo_root).resolve()
    public = repo / args.public_site
    unred = repo / args.unredacted_site
    summary = first_summary(repo, public)

    report = {
        "ok": True,
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "counts_used": summary,
        "public": process_site(public, summary) if public.exists() else {"missing": str(public)},
        "unredacted": process_site(unred, summary) if unred.exists() else {"missing": str(unred)},
    }
    out = repo / args.summary
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
