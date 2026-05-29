#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, re
from pathlib import Path

PATTERNS = [
    re.compile(r"<span>\s*<small>\s*SCC\s+Nexus\s*·\s*AQ26\s*</small>\s*</span>", re.I),
    re.compile(r"<span[^>]*>\s*<small[^>]*>\s*SCC\s+Nexus\s*·\s*AQ26\s*</small>\s*</span>", re.I),
    re.compile(r"<small[^>]*>\s*SCC\s+Nexus\s*·\s*AQ26\s*</small>", re.I),
    re.compile(r"\s*SCC\s+Nexus\s*·\s*AQ26\s*", re.I),
    re.compile(r"\s*SCC\s+NEXUS\s*·\s*AQ26\s*", re.I),
]

def clean_text(txt: str) -> tuple[str, int]:
    total = 0
    for rx in PATTERNS:
        txt, n = rx.subn("", txt)
        total += n
    # Clean empty spans left in a brand link.
    txt, n = re.subn(r"<span>\s*</span>", "", txt, flags=re.I)
    total += n
    # Preserve layout by removing repeated whitespace between image and nav/menu areas.
    txt, n = re.subn(r"(<img[^>]+>)\s+</a>", r"\1</a>", txt, flags=re.I)
    total += n
    return txt, total

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--roots", nargs="+", default=["site_test", "site_test/unredacted", "site_public", "site_unredacted"])
    ap.add_argument("--summary", default="site_test/data/test_header_text_polish_summary.json")
    args = ap.parse_args()

    changed = []
    remaining = []
    for root_s in args.roots:
        root = Path(root_s)
        if not root.exists():
            continue
        for p in sorted(root.rglob("*.html")):
            old = p.read_text(encoding="utf-8", errors="replace")
            new, count = clean_text(old)
            if new != old:
                p.write_text(new, encoding="utf-8")
            if re.search(r"SCC\s+Nexus\s*·\s*AQ26|SCC\s+NEXUS\s*·\s*AQ26", new, flags=re.I):
                remaining.append(str(p))
            changed.append({"path": str(p), "replacements": count})
    out = {"ok": not remaining, "files_checked": len(changed), "changed": changed, "remaining_files": remaining}
    summary = Path(args.summary)
    summary.parent.mkdir(parents=True, exist_ok=True)
    summary.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))
    return 1 if remaining else 0

if __name__ == "__main__":
    raise SystemExit(main())
