#!/usr/bin/env python3
from __future__ import annotations

import argparse, json, re
from pathlib import Path
from typing import Any, Dict

def read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}

def load_counts(site: Path) -> Dict[str, int]:
    candidates = [
        site / "data/weekly/latest_alert.json",
        site / "data/focus/overlays_v3/incinerator_overlay_summary.json",
    ]
    data: Dict[str, Any] = {}
    for p in candidates:
        data = read_json(p)
        if data:
            break
    total = int(data.get("total_facilities") or data.get("broad_facilities") or 46)
    validated = int(data.get("validated_overlays") or 8)
    candidate = int(data.get("candidate_overlays") or data.get("candidate_facilities_cumulative") or 35)
    unresolved = int(data.get("unresolved_facilities") or data.get("no_candidate_selected_yet") or 3)
    return {
        "total": total,
        "validated": validated,
        "candidate": candidate,
        "unresolved": unresolved,
        "overlay_path": validated + candidate,
    }

def replace_first_stat_value(html: str, label: str, value: int) -> str:
    # Generated AQ26 stat cards are: <div class='label'>Facilities</div><div class='value'>86</div>
    # This replaces the value immediately following the requested label only.
    pattern = re.compile(
        rf"(<div class=(['\"])label\2>\s*{re.escape(label)}\s*</div>\s*<div class=(['\"])value\3>)(.*?)(</div>)",
        flags=re.I | re.S,
    )
    return pattern.sub(lambda m: f"{m.group(1)}{value}{m.group(5)}", html)

def fix_html_file(path: Path, counts: Dict[str, int]) -> bool:
    if not path.exists():
        return False
    old = path.read_text(encoding="utf-8", errors="replace")
    new = old

    # Remove redundant generated brand text beside the full SCC Nexus Air Quality logo.
    new = re.sub(r"<span>\s*<small>\s*SCC\s+Nexus\s*[·\-]\s*AQ26\s*</small>\s*</span>", "", new, flags=re.I)
    new = re.sub(r"<span>\s*<small>\s*SCC\s+NEXUS\s*[·\-]\s*AQ26\s*</small>\s*</span>", "", new, flags=re.I)

    # Correct legacy stat-card counts left by older operational pages.
    new = replace_first_stat_value(new, "Facilities", counts["total"])
    new = replace_first_stat_value(new, "Validated overlays", counts["validated"])
    new = replace_first_stat_value(new, "Candidates", counts["candidate"])
    new = replace_first_stat_value(new, "Fallback cases", counts["unresolved"])

    # Common older wording variants.
    new = replace_first_stat_value(new, "Validated", counts["validated"])
    new = replace_first_stat_value(new, "Under review", counts["candidate"])
    new = replace_first_stat_value(new, "Fallback", counts["unresolved"])

    # Replace explicit visible legacy phrases if present.
    new = re.sub(r"\b86\s+facilities\s+in\s+register\b", f"{counts['total']} facilities in register", new, flags=re.I)
    new = re.sub(r"\b86\s+incinerator\s*/\s*EfW\s+facilities\b", f"{counts['total']} incinerator / EfW facilities", new, flags=re.I)
    new = re.sub(r"\bonly\s+86\s+facilities\s+in\s+register\b", f"{counts['total']} facilities in register", new, flags=re.I)

    # Correct embedded JS data totals when generated as JSON.
    new = re.sub(r'("total"\s*:\s*)86\b', rf'\g<1>{counts["total"]}', new)
    new = re.sub(r'("missing"\s*:\s*)43\b', rf'\g<1>{counts["unresolved"]}', new)

    # Ensure favicon references prefer root ICO/SVG cache-busted paths.
    if "</head>" in new and 'href="/favicon.ico' not in new:
        refs = (
            '<link rel="icon" href="/favicon.ico?v=aq26-count-final" sizes="any">\n'
            '<link rel="icon" href="/favicon.svg?v=aq26-count-final" type="image/svg+xml">\n'
        )
        new = new.replace("</head>", refs + "</head>")

    if new != old:
        path.write_text(new, encoding="utf-8")
        return True
    return False

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--public-site", default="site_public")
    ap.add_argument("--unredacted-site", default="site_unredacted")
    ap.add_argument("--summary", default="site_public/data/weekly/count_stat_card_final_fix_status.json")
    args = ap.parse_args()

    public = Path(args.public_site)
    unredacted = Path(args.unredacted_site)
    counts = load_counts(public)

    changed = []
    for site in [public, unredacted]:
        if not site.exists():
            continue
        for path in sorted(site.glob("*.html")):
            if fix_html_file(path, counts):
                changed.append(str(path))

    summary = {"ok": True, "counts": counts, "changed_files": changed, "changed_count": len(changed)}
    out = Path(args.summary)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
