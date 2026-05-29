#!/usr/bin/env python3
"""Remove generated text beside the AQ26 header logo.

Post-build polish for public, unredacted and /test staging HTML.
It keeps the logo image, hamburger/menu, weekly alert and moving banners.
"""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path
from typing import Dict, List

SIDE_TEXT_PATTERNS = [
    # Exact generated brand-label span from the operational builder.
    re.compile(r"\s*<span\s*>\s*<small\s*>\s*SCC\s+Nexus\s*·\s*AQ26\s*</small>\s*</span>", re.I),
    re.compile(r"\s*<span\s*>\s*<small\s*>\s*SCC\s+NEXUS\s*·\s*AQ26\s*</small>\s*</span>", re.I),
    # More tolerant version in case classes/attributes are later added.
    re.compile(r"\s*<span[^>]*>\s*<small[^>]*>\s*SCC\s+Nexus\s*·\s*AQ26\s*</small>\s*</span>", re.I),
    re.compile(r"\s*<span[^>]*>\s*<small[^>]*>\s*SCC\s+NEXUS\s*·\s*AQ26\s*</small>\s*</span>", re.I),
]

PLAIN_PATTERNS = [
    re.compile(r"SCC\s+Nexus\s*·\s*AQ26", re.I),
    re.compile(r"SCC\s+NEXUS\s*·\s*AQ26", re.I),
]


def clean_html(txt: str) -> tuple[str, int]:
    total = 0
    for rx in SIDE_TEXT_PATTERNS:
        txt, n = rx.subn("", txt)
        total += n
    # If the text was emitted without span markup, remove the text only.
    for rx in PLAIN_PATTERNS:
        txt, n = rx.subn("", txt)
        total += n
    # Tidy a common leftover empty brand span if only the text was removed.
    txt, n = re.subn(r"\s*<span\s*>\s*<small\s*>\s*</small>\s*</span>", "", txt, flags=re.I)
    total += n
    return txt, total


def iter_html(root: Path):
    if not root.exists():
        return
    for p in sorted(root.rglob("*.html")):
        if p.is_file():
            yield p


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--roots", nargs="+", default=["site_test"], help="HTML roots to polish")
    ap.add_argument("--summary", default="site_test/data/test_header_text_polish_summary.json")
    ap.add_argument("--fail-if-remaining", action="store_true")
    args = ap.parse_args()

    changed: List[Dict[str, object]] = []
    remaining: List[str] = []
    for root_s in args.roots:
        root = Path(root_s)
        for p in iter_html(root) or []:
            txt = p.read_text(encoding="utf-8", errors="replace")
            new, n = clean_html(txt)
            if new != txt:
                p.write_text(new, encoding="utf-8")
                changed.append({"path": p.as_posix(), "removals": n})
            check = p.read_text(encoding="utf-8", errors="replace")
            if re.search(r"SCC\s+Nexus\s*·\s*AQ26|SCC\s+NEXUS\s*·\s*AQ26", check, re.I):
                remaining.append(p.as_posix())

    summary = {
        "ok": not remaining,
        "changed_files": len(changed),
        "changed": changed,
        "remaining_matches": remaining,
    }
    out = Path(args.summary)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 2 if args.fail_if_remaining and remaining else 0

if __name__ == "__main__":
    raise SystemExit(main())
