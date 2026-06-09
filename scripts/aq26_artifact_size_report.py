#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from datetime import datetime, timezone

def sha256_file(path: Path, max_bytes: int = 64 * 1024 * 1024) -> str | None:
    """Return SHA256 for files up to max_bytes; skip huge files to keep weekly audit quick."""
    try:
        if path.stat().st_size > max_bytes:
            return None
        h = hashlib.sha256()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return None

def classify(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".zip", ".7z", ".tar", ".gz", ".tgz"}:
        return "archive"
    if suffix in {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".avif"}:
        return "image"
    if suffix in {".mp4", ".webm", ".mov"}:
        return "video"
    if suffix in {".json", ".csv", ".parquet", ".geojson"}:
        return "data"
    if suffix in {".pdf", ".md", ".html", ".txt"}:
        return "report_or_page"
    return "other"

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", action="append", default=[])
    ap.add_argument("--output-dir", default="outputs/aq26_size_audit")
    ap.add_argument("--top-n", type=int, default=250)
    args = ap.parse_args()

    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    rows = []
    totals = {}
    for root_str in args.root:
        root = Path(root_str)
        if not root.exists():
            continue
        for p in root.rglob("*"):
            if not p.is_file():
                continue
            try:
                size = p.stat().st_size
            except OSError:
                continue
            kind = classify(p)
            rows.append({
                "root": root_str,
                "path": p.as_posix(),
                "size_bytes": size,
                "size_mb": round(size / 1024 / 1024, 3),
                "kind": kind,
                "sha256_if_small": sha256_file(p),
            })
            totals[kind] = totals.get(kind, 0) + size

    rows.sort(key=lambda r: r["size_bytes"], reverse=True)
    with (out / "artifact_largest_files.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["root","path","size_bytes","size_mb","kind","sha256_if_small"])
        writer.writeheader()
        writer.writerows(rows[: args.top_n])

    summary = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "root_count": len(args.root),
        "file_count": len(rows),
        "total_bytes": sum(r["size_bytes"] for r in rows),
        "total_mb": round(sum(r["size_bytes"] for r in rows) / 1024 / 1024, 3),
        "by_kind_mb": {k: round(v / 1024 / 1024, 3) for k, v in sorted(totals.items())},
        "largest_files": rows[:25],
    }
    (out / "artifact_size_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2)[:4000])
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
