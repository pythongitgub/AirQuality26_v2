#!/usr/bin/env python3
"""
AQ26 public redaction gate.

Fails deployment if protected/reviewer archive material is present on the public
surface. The unredacted surface is intentionally not scanned here.
"""

from pathlib import Path
import sys

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

errors = []

if not PUBLIC.exists():
    errors.append("site_public folder missing")
else:
    for path in sorted(PUBLIC.rglob("*")):
        if not path.is_file():
            continue

        lower_name = path.name.lower()
        lower_posix = path.as_posix().lower()

        if path.suffix.lower() in ARCHIVE_SUFFIXES and lower_posix.startswith("site_public/downloads/"):
            errors.append(f"non-public archive on public surface: {path.as_posix()}")
            continue

        if path.suffix.lower() in ARCHIVE_SUFFIXES and any(marker in lower_name for marker in PROTECTED_NAME_MARKERS):
            errors.append(f"protected archive filename on public surface: {path.as_posix()}")
            continue

        if path.name in {".htpasswd", ".htaccess"}:
            errors.append(f"auth file leaked to public build: {path.as_posix()}")

if errors:
    print("AQ26 public redaction gate failed:")
    for e in errors:
        print(f" - {e}")
    sys.exit(1)

print("AQ26 public redaction gate passed.")
