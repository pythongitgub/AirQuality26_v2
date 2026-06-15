#!/usr/bin/env python3
"""Fail deployment if protected files leak into site_public."""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path.cwd()
PUBLIC = ROOT / "site_public"
errors: list[str] = []

if not PUBLIC.exists():
    errors.append("site_public folder missing")
else:
    forbidden_names = {
        ".htaccess",
        ".htpasswd",
        "AQ26_WEEKLY_EVIDENCE_BUNDLE.zip",
    }
    for p in PUBLIC.rglob("*"):
        if p.name in forbidden_names:
            errors.append(f"forbidden public file present: {p.relative_to(ROOT)}")
        # Public zip files are allowed only when they explicitly identify as redacted/public-safe.
        if p.is_file() and p.suffix.lower() == ".zip":
            lower_name = p.name.lower()
            if not any(token in lower_name for token in ("public", "redacted")):
                errors.append(f"non-public zip on public surface: {p.relative_to(ROOT)}")
        if p.is_file() and p.stat().st_size > 25 * 1024 * 1024 and "assets" not in p.parts:
            errors.append(f"large public file needs review: {p.relative_to(ROOT)} ({p.stat().st_size} bytes)")

if errors:
    print("AQ26 public redaction gate failed:")
    for e in errors:
        print(" -", e)
    sys.exit(1)

print("AQ26 public redaction gate passed.")
