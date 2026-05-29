#!/usr/bin/env python3
from __future__ import annotations
import argparse
import re
from pathlib import Path

PATTERNS = [
    re.compile(r"<span[^>]*>\s*<small>\s*SCC\s+Nexus\s*(?:·|&middot;|\|)\s*AQ26\s*</small>\s*</span>", re.I),
    re.compile(r"<span[^>]*>\s*SCC\s+Nexus\s*(?:·|&middot;|\|)\s*AQ26\s*</span>", re.I),
    re.compile(r"<small>\s*SCC\s+Nexus\s*(?:·|&middot;|\|)\s*AQ26\s*</small>", re.I),
]

TEXT_MARKERS = [
    "SCC NEXUS · AQ26",
    "SCC Nexus · AQ26",
    "SCC Nexus | AQ26",
]

def clean_html(txt: str) -> str:
    for rx in PATTERNS:
        txt = rx.sub("", txt)
    for marker in TEXT_MARKERS:
        txt = txt.replace(marker, "")
    # remove empty brand text spans occasionally left by generators
    txt = re.sub(r"<span[^>]*class=[\"'][^\"']*brand-text[^\"']*[\"'][^>]*>\s*</span>", "", txt, flags=re.I)
    return txt

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--site-root", default="site_test")
    args = ap.parse_args()
    root = Path(args.site_root)
    changed = 0
    if not root.exists():
        print(f"site root missing: {root}")
        return 0
    for p in sorted(root.rglob("*.html")):
        old = p.read_text(encoding="utf-8", errors="replace")
        new = clean_html(old)
        if new != old:
            p.write_text(new, encoding="utf-8")
            changed += 1
            print("cleaned", p)
    print({"site_root": str(root), "html_files_cleaned": changed})
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
