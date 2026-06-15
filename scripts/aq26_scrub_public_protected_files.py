#!/usr/bin/env python3
"""
AQ26 public-site scrubber.

Purpose:
- Keep protected/unredacted evidence bundles out of site_public.
- Preserve public pages and public-safe data.
- Leave site_unredacted untouched.

Run after the AQ26 evidence builder and before artifact upload/deployment.
"""
from __future__ import annotations

from pathlib import Path
import shutil

ROOT = Path.cwd()
PUBLIC = ROOT / "site_public"
DOWNLOADS = PUBLIC / "downloads"

# Files/patterns that must never be shipped from the public surface.
PROTECTED_PATTERNS = [
    "AQ26_WEEKLY_EVIDENCE_BUNDLE.zip",
    "*UNREDACTED*.zip",
    "*unredacted*.zip",
    "*reviewer*.zip",
    "*reviewer_notes*",
    "*source_index_unredacted*",
    ".htaccess",
    ".htpasswd",
]

removed: list[str] = []

if PUBLIC.exists():
    for pattern in PROTECTED_PATTERNS:
        for path in PUBLIC.rglob(pattern):
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink(missing_ok=True)
            removed.append(str(path.relative_to(ROOT)))

DOWNLOADS.mkdir(parents=True, exist_ok=True)
(DOWNLOADS / "README_PUBLIC_DOWNLOADS.txt").write_text(
    "Public downloads are deliberately limited to redacted/public-safe material.\n"
    "Protected reviewer bundles are available only in /unredacted/ behind HTTP Basic Auth.\n",
    encoding="utf-8",
)

print("AQ26 public protected-file scrub complete.")
if removed:
    print("Removed from public surface:")
    for item in removed:
        print(f" - {item}")
else:
    print("No protected public files found.")
