#!/usr/bin/env python3
"""
AQ26 WeeklyV2 output sanitizer.

Purpose:
- Remove token-like/API-key-like URL parameters and provider tracking tokens from output files before redaction audit.
- Covers SerpAPI token= tracking params and OpenWeather appid= params.
- Writes a provenance manifest with before/after hashes for changed files.

This script edits text-like output files only. It does not alter environment secrets.
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

SENSITIVE_KEYS = {
    "token", "api_key", "apikey", "key", "client_secret", "password", "access_token",
    "appid", "app_id", "subscription-key", "subscription_key", "ocp-apim-subscription-key",
    "x-api-key", "authorization"
}

SENSITIVE_KEY_PATTERN = (
    r"token|api_key|apikey|key|client_secret|password|access_token|"
    r"appid|app_id|subscription-key|subscription_key|ocp-apim-subscription-key|x-api-key|authorization"
)

INLINE_PATTERNS = [
    # Query-string forms, including &appid= and ?appid=.
    (
        re.compile(rf"(?i)([?&](?:{SENSITIVE_KEY_PATTERN})=)([^&\s\"'<>]+)"),
        r"\1***REDACTED***",
    ),
    # Inline key=value forms.
    (
        re.compile(rf"(?i)(\b(?:{SENSITIVE_KEY_PATTERN})\s*=\s*)([^&\s\"'<>]+)"),
        r"\1***REDACTED***",
    ),
    # JSON fields.
    (
        re.compile(rf'(?i)("(?:{SENSITIVE_KEY_PATTERN})"\s*:\s*")([^"]+)(")'),
        r'\1***REDACTED***\3',
    ),
    # Bearer tokens.
    (
        re.compile(r"(?i)(Bearer\s+)[A-Za-z0-9_\-.]{8,}"),
        r"\1***REDACTED***",
    ),
]


def sha_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()


def sanitize_url_string(value: str) -> str:
    try:
        parsed = urllib.parse.urlsplit(value)
        if not parsed.scheme or not parsed.netloc or not parsed.query:
            return value
        pairs = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        changed = False
        redacted = []
        for key, val in pairs:
            if key.lower() in SENSITIVE_KEYS or any(term in key.lower() for term in ["token", "key", "secret", "password", "appid"]):
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

    for pattern, repl in INLINE_PATTERNS:
        out = pattern.sub(repl, out)

    # Plain URLs.
    url_pattern = re.compile(r"https?://[^\s\"'<>]+")
    out = url_pattern.sub(lambda m: sanitize_url_string(m.group(0)), out)

    # JSON escaped ampersands.
    if "\\u0026" in out:
        deescaped = out.replace("\\u0026", "&")
        for pattern, repl in INLINE_PATTERNS:
            deescaped = pattern.sub(repl, deescaped)
        deescaped = re.sub(r"https?://[^\s\"'<>]+", lambda m: sanitize_url_string(m.group(0)), deescaped)
        out = deescaped.replace("&", "\\u0026")

    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default="outputs")
    args = parser.parse_args()

    root = Path(args.root)
    root.mkdir(parents=True, exist_ok=True)

    changed_files: List[Dict] = []
    scanned = 0

    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in TEXT_EXTS:
            continue
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
                "redaction_scope": "token/api-key/appid-like output text",
            })

    manifest = {
        "created_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "purpose": "Sanitize provider output files before redaction audit, including SerpAPI token-like params and OpenWeather appid params.",
        "files_scanned": scanned,
        "files_changed": len(changed_files),
        "changed_files": changed_files,
        "notes": [
            "This does not alter environment secrets.",
            "It replaces token/API-key/appid-like output text with ***REDACTED*** before evidence packaging.",
            "Downstream SHA256 ledgers reflect sanitized files."
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
