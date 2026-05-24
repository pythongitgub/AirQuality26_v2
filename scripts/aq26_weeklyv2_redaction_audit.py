#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from pathlib import Path

# Fail closed on any token/API-key/appid-like output. REDACTED placeholders are allowed.
PATTERNS = [
    r"(?i)(apiKey=)(?!%2A%2A%2AREDACTED%2A%2A%2A|\*\*\*REDACTED\*\*\*)[A-Za-z0-9_\-\.]{8,}",
    r"(?i)(apikey=)(?!%2A%2A%2AREDACTED%2A%2A%2A|\*\*\*REDACTED\*\*\*)[A-Za-z0-9_\-\.]{8,}",
    r"(?i)(api_key=)(?!%2A%2A%2AREDACTED%2A%2A%2A|\*\*\*REDACTED\*\*\*)[A-Za-z0-9_\-\.]{8,}",
    r"(?i)(token=)(?!%2A%2A%2AREDACTED%2A%2A%2A|\*\*\*REDACTED\*\*\*)[A-Za-z0-9_\-\.]{8,}",
    r"(?i)(appid=)(?!%2A%2A%2AREDACTED%2A%2A%2A|\*\*\*REDACTED\*\*\*)[A-Za-z0-9_\-\.]{8,}",
    r"(?i)(app_id=)(?!%2A%2A%2AREDACTED%2A%2A%2A|\*\*\*REDACTED\*\*\*)[A-Za-z0-9_\-\.]{8,}",
    r"(?i)(access_token=)(?!%2A%2A%2AREDACTED%2A%2A%2A|\*\*\*REDACTED\*\*\*)[A-Za-z0-9_\-\.]{8,}",
    r"(?i)(client_secret=)(?!%2A%2A%2AREDACTED%2A%2A%2A|\*\*\*REDACTED\*\*\*)[^&\s\"']{6,}",
    r"(?i)(password=)(?!%2A%2A%2AREDACTED%2A%2A%2A|\*\*\*REDACTED\*\*\*)[^&\s\"']{6,}",
    r"(?i)(Bearer\s+)(?!\*\*\*REDACTED\*\*\*)[A-Za-z0-9_\-\.]{12,}",
    r'(?i)"(apiKey|apikey|api_key|token|appid|app_id|access_token|client_secret|password)"\s*:\s*"(?!\*\*\*REDACTED\*\*\*)[^"]{8,}"',
]

EXTS = {".json", ".jsonl", ".csv", ".txt", ".md", ".html", ".xml", ".yml", ".yaml", ".log"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default="outputs")
    parser.add_argument("--fail-on-leak", default="true")
    args = parser.parse_args()

    root = Path(args.root)
    leaks = []
    scanned = 0

    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in EXTS:
            continue
        scanned += 1
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pat in PATTERNS:
            m = re.search(pat, text)
            if m:
                leaks.append({
                    "path": str(path).replace("\\", "/"),
                    "pattern": pat,
                    "match_preview": m.group(0)[:24] + "***",
                })
                break

    out = root / "99_integrity" / "redaction_audit.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    result = {
        "created_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "files_scanned": scanned,
        "leak_count": len(leaks),
        "leaks": leaks,
    }
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))

    if leaks and args.fail_on_leak.lower() in ("1", "true", "yes", "y"):
        raise SystemExit("Redaction audit failed")


if __name__ == "__main__":
    main()
