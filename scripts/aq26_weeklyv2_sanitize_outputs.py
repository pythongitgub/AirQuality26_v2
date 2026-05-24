#!/usr/bin/env python3
"""
AQ26 WeeklyV2 output sanitizer.

Purpose:
- Remove token-like URL parameters and tracking tokens from provider JSON/HTML/CSV/MD outputs before redaction audit.
- Fixes SerpAPI result URLs that contain benign but secret-looking `token=` query strings.
- Does not hide the fact that sanitisation occurred: writes a provenance manifest.

This script is intentionally broad but conservative:
- It edits text-like files only.
- It preserves files in place after replacing token-like values with ***REDACTED***.
- It records SHA256 before/after for each changed file.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import urllib.parse
from pathlib import Path
from typing import Dict, List

TEXT_EXTS = {".json", ".jsonl", ".csv", ".txt", ".md", ".html", ".xml", ".yml", ".yaml", ".log"}

# These are output-only sanitisation patterns. They do not alter environment secrets.
INLINE_PATTERNS = [
    # Query-string or inline key/value forms.
    (re.compile(r"(?i)([?&](?:token|api_key|apikey|key|client_secret|password|access_token|authuser)=)([^&\s\"'<>]+)"), r"\1***REDACTED***"),
    (re.compile(r"(?i)(\b(?:token|api_key|apikey|key|client_secret|password|access_token)\s*=\s*)([^&\s\"'<>]+)"), r"\1***REDACTED***"),
    # JSON fields named token/key/password variants.
    (re.compile(r'(?i)("(?:token|api_key|apikey|key|client_secret|password|access_token)"\s*:\s*")([^"]+)(")'), r'\1***REDACTED***\3'),
    # Bearer tokens.
    (re.compile(r"(?i)(Bearer\s+)[A-Za-z0-9_\-.]{8,}"), r"\1***REDACTED***"),
]


def sha_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


def sanitize_url_string(value: str) -> str:
    """Redact sensitive query parameters inside a URL-like string."""
    try:
        parsed = urllib.parse.urlsplit(value)
        if not parsed.scheme or not parsed.netloc:
            return value
        if not parsed.query:
            return value
        pairs = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        changed = False
        redacted = []
        for key, val in pairs:
            if any(term in key.lower() for term in ["token", "api_key", "apikey", "key", "secret", "password", "access_token"]):
                redacted.append((key, "***REDACTED***"))
                changed = True
            else:
                redacted.append((key, val))
        if changed:
            return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urllib.parse.urlencode(redacted), parsed.fragment))
        return value
    except Exception:
        return value


def sanitize_text(text: str) -> str:
    out = text

    # First handle normal inline forms.
    for pattern, repl in INLINE_PATTERNS:
        out = pattern.sub(repl, out)

    # Then handle JSON escaped URLs and plain URLs more generally.
    # This catches SerpAPI organic result URLs with tracking token parameters.
    url_pattern = re.compile(r"https?://[^\s\"'<>]+")
    out = url_pattern.sub(lambda m: sanitize_url_string(m.group(0)), out)

    # Also catch escaped JSON url strings where ampersands may be escaped as \u0026
    if "\\u0026" in out:
        deescaped = out.replace("\\u0026", "&")
        for pattern, repl in INLINE_PATTERNS:
            deescaped = pattern.sub(repl, deescaped)
        out = deescaped.replace("&", "\\u0026")

    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default="outputs")
    args = parser.parse_args()

    root = Path(args.root)
    changed_files: List[Dict] = []
    scanned = 0

    if not root.exists():
        root.mkdir(parents=True, exist_ok=True)

    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in TEXT_EXTS:
            continue

        # Avoid repeatedly sanitising old sanitisation manifests, but allow all other outputs.
        if path.name == "provider_sanitization_manifest.json":
            continue

        scanned += 1
        try:
            before = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        after = sanitize_text(before)
        if after != before:
            before_sha = sha_text(before)
            after_sha = sha_text(after)
            path.write_text(after, encoding="utf-8")
            changed_files.append({
                "path": str(path).replace("\\", "/"),
                "before_sha256": before_sha,
                "after_sha256": after_sha,
                "bytes_before": len(before.encode("utf-8", errors="ignore")),
                "bytes_after": len(after.encode("utf-8", errors="ignore")),
            })

    manifest = {
        "created_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "purpose": "Sanitize provider output files before redaction audit; particularly SerpAPI result URLs containing token-like tracking parameters.",
        "files_scanned": scanned,
        "files_changed": len(changed_files),
        "changed_files": changed_files,
        "notes": [
            "This does not alter environment secrets.",
            "It replaces token-like output text with ***REDACTED*** before evidence packaging.",
            "If files_changed is non-zero, downstream SHA256 ledgers reflect the sanitized files."
        ],
    }

    out = root / "15_optional_sources" / "provider_sanitization_manifest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps({
        "files_scanned": scanned,
        "files_changed": len(changed_files),
        "manifest": str(out),
    }, indent=2))


if __name__ == "__main__":
    main()
