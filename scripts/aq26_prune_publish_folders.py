#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from datetime import datetime, timezone

DEFAULT_ROOTS = ["site_public", "site_unredacted", "site_test"]

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def main() -> int:
    ap = argparse.ArgumentParser(description="Remove oversized publish-folder archives before deploy/artifact upload.")
    ap.add_argument("--max-mb", type=float, default=25)
    ap.add_argument("--root", action="append", default=[])
    ap.add_argument("--keep-file", action="store_true", help="Write metadata but do not remove the large file.")
    args = ap.parse_args()

    roots = [Path(r) for r in (args.root or DEFAULT_ROOTS)]
    max_bytes = int(args.max_mb * 1024 * 1024)
    removed = []

    for root in roots:
        if not root.exists():
            continue
        for p in root.rglob("*"):
            if not p.is_file():
                continue
            if p.suffix.lower() not in {".zip", ".7z", ".tar", ".gz", ".tgz"}:
                continue
            size = p.stat().st_size
            if size <= max_bytes:
                continue
            meta = {
                "created_utc": datetime.now(timezone.utc).isoformat(),
                "original_path": p.as_posix(),
                "original_filename": p.name,
                "size_bytes": size,
                "size_mb": round(size / 1024 / 1024, 3),
                "sha256": sha256_file(p),
                "reason": f"Removed from publish tree because it exceeds {args.max_mb} MB. Store full evidence in GitHub artifact/Google Shared Drive instead.",
            }
            meta_path = p.with_suffix(p.suffix + ".metadata.json")
            meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
            if not args.keep_file:
                p.unlink()
            removed.append(meta)

    report_dir = Path("outputs/aq26_size_audit")
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "publish_prune_report.json").write_text(json.dumps({
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "max_mb": args.max_mb,
        "removed_count": len(removed),
        "removed": removed,
    }, indent=2), encoding="utf-8")

    print(f"Pruned {len(removed)} oversized archive(s) from publish folders.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
