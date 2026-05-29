#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

SIDE_TEXT_PATTERNS = [
    r"\s*<span>\s*<small>\s*SCC\s+Nexus\s*·\s*AQ26\s*</small>\s*</span>",
    r"\s*<span>\s*<small>\s*SCC\s+NEXUS\s*·\s*AQ26\s*</small>\s*</span>",
    r"\s*<small>\s*SCC\s+Nexus\s*·\s*AQ26\s*</small>",
    r"\s*<small>\s*SCC\s+NEXUS\s*·\s*AQ26\s*</small>",
    r"\s*SCC\s+Nexus\s*·\s*AQ26\s*",
    r"\s*SCC\s+NEXUS\s*·\s*AQ26\s*",
]

# Extra safety: remove empty text span directly after brand image/link if left behind.
EMPTY_SPAN_AFTER_BRAND = re.compile(
    r"(<a[^>]*class=[\"'][^\"']*brand[^\"']*[\"'][^>]*>.*?</a>)\s*<span>\s*</span>",
    flags=re.I | re.S,
)


def clean_text(txt: str) -> tuple[str, int]:
    total = 0
    for pat in SIDE_TEXT_PATTERNS:
        txt, n = re.subn(pat, " ", txt, flags=re.I | re.S)
        total += n
    txt, n = EMPTY_SPAN_AFTER_BRAND.subn(r"\1", txt)
    total += n
    # collapse over-wide spaces between header children, but leave page text alone enough.
    txt = re.sub(r">\s{2,}<", ">\n<", txt)
    return txt, total


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--roots", nargs="+", default=["site_test"], help="Site roots to clean")
    ap.add_argument("--summary", default="site_test/data/header_text_polish_summary.json")
    ap.add_argument("--fail-if-found", action="store_true")
    args = ap.parse_args()

    changed_files: list[dict[str, Any]] = []
    remaining: list[str] = []

    for root_s in args.roots:
        root = Path(root_s)
        if not root.exists():
            continue
        for p in sorted(root.rglob("*.html")):
            txt = p.read_text(encoding="utf-8", errors="replace")
            cleaned, n = clean_text(txt)
            if cleaned != txt:
                p.write_text(cleaned, encoding="utf-8")
                changed_files.append({"path": str(p), "replacements": n})
            after = p.read_text(encoding="utf-8", errors="replace")
            if re.search(r"SCC\s+Nexus\s*·\s*AQ26|SCC\s+NEXUS\s*·\s*AQ26", after, flags=re.I):
                remaining.append(str(p))

    summary = {"ok": not remaining, "changed_files": changed_files, "remaining_files": remaining}
    out = Path(args.summary)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    if args.fail_if_found and remaining:
        return 2
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
