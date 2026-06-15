#!/usr/bin/env python3
"""
AQ26 public protected-file scrub.

Purpose:
  The public site must never contain protected evidence bundles or reviewer
  archives. This script runs after the evidence builder and before deployment.

Policy:
  - Remove all archive files from site_public/downloads.
  - Remove obviously protected archive files anywhere under site_public.
  - Never touch site_unredacted.
"""

from pathlib import Path

PUBLIC = Path("site_public")

ARCHIVE_SUFFIXES = {
    ".zip", ".7z", ".rar", ".tar", ".gz", ".tgz", ".bz2", ".xz"
}

PROTECTED_NAME_MARKERS = {
    "unredacted",
    "protected",
    "reviewer",
    "private",
    "evidence_bundle",
    "weekly_evidence_bundle",
    "latest-evidence",
    "latest_evidence",
    "aq26_weekly_evidence_bundle",
}

removed = []

def should_remove(path: Path) -> bool:
    lower_name = path.name.lower()
    lower_posix = path.as_posix().lower()

    if path.suffix.lower() in ARCHIVE_SUFFIXES and lower_posix.startswith("site_public/downloads/"):
        return True

    if path.suffix.lower() in ARCHIVE_SUFFIXES and any(marker in lower_name for marker in PROTECTED_NAME_MARKERS):
        return True

    return False

if PUBLIC.exists():
    for path in sorted(PUBLIC.rglob("*")):
        if path.is_file() and should_remove(path):
            path.unlink()
            removed.append(path.as_posix())

print("AQ26 public protected-file scrub complete.")
if removed:
    print("Removed from public surface:")
    for item in removed:
        print(f" - {item}")
else:
    print("No protected public archive files found.")
