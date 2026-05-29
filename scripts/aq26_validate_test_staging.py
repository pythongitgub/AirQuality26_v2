#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, re
from pathlib import Path

def contains(path: Path, *needles: str) -> bool:
    if not path.exists():
        return False
    txt = path.read_text(encoding="utf-8", errors="replace")
    return any(n in txt for n in needles)

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--test-site", default="site_test")
    ap.add_argument("--include-unredacted", action="store_true")
    ap.add_argument("--summary", default="site_test/data/test_staging_validation_summary.json")
    args = ap.parse_args()

    root = Path(args.test_site)
    problems = []

    required = ["index.html", "incinerators.html", "newhaven.html", "weekly-update.html", "test-index.html"]
    for name in required:
        p = root / name
        if not p.exists() or p.stat().st_size < 500:
            problems.append(f"{p}: missing or too small")

    if not contains(root / "index.html", "AQ26_WEEKLY_ALERT_START", "aq26-alert"):
        problems.append("site_test/index.html: missing weekly alert marker")
    if not contains(root / "index.html", "aq26-video-banner"):
        problems.append("site_test/index.html: missing moving video banner marker")

    # Header side text should be gone.
    side_rx = re.compile(r"SCC\s+Nexus\s*·\s*AQ26|SCC\s+NEXUS\s*·\s*AQ26", re.I)
    for p in list(root.glob("*.html")) + list((root / "unredacted").glob("*.html") if (root / "unredacted").exists() else []):
        txt = p.read_text(encoding="utf-8", errors="replace")
        if side_rx.search(txt):
            problems.append(f"{p}: header side text still present")

    # No password hash files in staging artifact.
    for base in [Path("site_public"), Path("site_unredacted"), root]:
        if base.exists():
            for p in base.rglob(".htpasswd"):
                problems.append(f"{p}: .htpasswd present before commit/deploy")

    if args.include_unredacted:
        for name in ["index.html", "weekly-update.html"]:
            p = root / "unredacted" / name
            if not p.exists() or p.stat().st_size < 500:
                problems.append(f"{p}: missing or too small")

    out = {"ok": not problems, "problems": problems, "test_site": str(root)}
    summary = Path(args.summary)
    summary.parent.mkdir(parents=True, exist_ok=True)
    summary.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))
    return 1 if problems else 0

if __name__ == "__main__":
    raise SystemExit(main())
