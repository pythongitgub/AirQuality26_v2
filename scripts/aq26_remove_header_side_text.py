#!/usr/bin/env python3
from __future__ import annotations
import argparse, re
from pathlib import Path

PATTERNS = [
    re.compile(r"<span>\s*<small>\s*SCC\s+Nexus\s*·\s*AQ26\s*</small>\s*</span>", re.I),
    re.compile(r"<span>\s*<small>\s*SCC\s+NEXUS\s*·\s*AQ26\s*</small>\s*</span>", re.I),
    re.compile(r"<small>\s*SCC\s+Nexus\s*·\s*AQ26\s*</small>", re.I),
    re.compile(r"<small>\s*SCC\s+NEXUS\s*·\s*AQ26\s*</small>", re.I),
    re.compile(r"\s*SCC\s+Nexus\s*·\s*AQ26\s*", re.I),
]

def clean_html(text: str) -> str:
    original = text
    for pat in PATTERNS:
        text = pat.sub("", text)
    # Remove empty spans left behind near brand blocks.
    text = re.sub(r"<span>\s*</span>", "", text, flags=re.I)
    # Keep spacing tidy but avoid aggressive minification.
    if text != original:
        text = re.sub(r"\n{3,}", "\n\n", text)
    return text

def process_site(root: Path) -> tuple[int, int]:
    changed = 0
    scanned = 0
    if not root.exists():
        return scanned, changed
    for p in sorted(root.rglob("*.html")):
        if not p.is_file():
            continue
        scanned += 1
        txt = p.read_text(encoding="utf-8", errors="replace")
        new = clean_html(txt)
        if new != txt:
            p.write_text(new, encoding="utf-8")
            changed += 1
            print(f"cleaned {p}")
    return scanned, changed

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--site-root", default="site_test")
    ap.add_argument("--also", nargs="*", default=[])
    args = ap.parse_args()
    roots = [Path(args.site_root), *[Path(x) for x in args.also]]
    total_scanned = total_changed = 0
    for root in roots:
        scanned, changed = process_site(root)
        total_scanned += scanned
        total_changed += changed
    print({"html_files_scanned": total_scanned, "html_files_changed": total_changed})
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
