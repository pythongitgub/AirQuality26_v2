#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from datetime import datetime, timezone

ASSET_EXTS = {".png",".jpg",".jpeg",".gif",".svg",".webp",".avif",".mp4",".webm",".mov",".ico"}

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", action="append", default=["site_public", "site_unredacted", "site_test"])
    ap.add_argument("--output-dir", default="outputs/aq26_size_audit")
    args = ap.parse_args()

    rows = []
    for root_str in args.root:
        root = Path(root_str)
        if not root.exists():
            continue
        for p in root.rglob("*"):
            if not p.is_file() or p.suffix.lower() not in ASSET_EXTS:
                continue
            rows.append({
                "root": root_str,
                "path": p.as_posix(),
                "filename": p.name,
                "extension": p.suffix.lower(),
                "size_bytes": p.stat().st_size,
                "size_mb": round(p.stat().st_size / 1024 / 1024, 3),
                "recommendation": "optimise_or_deduplicate" if p.stat().st_size > 512*1024 else "ok",
            })
    rows.sort(key=lambda r: r["size_bytes"], reverse=True)
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    with (out / "asset_catalogue.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["root","path","filename","extension","size_bytes","size_mb","recommendation"])
        writer.writeheader()
        writer.writerows(rows)
    (out / "asset_catalogue_summary.json").write_text(json.dumps({
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "asset_count": len(rows),
        "total_asset_mb": round(sum(r["size_bytes"] for r in rows)/1024/1024, 3),
        "largest_assets": rows[:25],
    }, indent=2), encoding="utf-8")
    print(f"Catalogued {len(rows)} visual/media assets.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
