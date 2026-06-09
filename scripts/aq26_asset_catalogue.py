#!/usr/bin/env python3
from __future__ import annotations
import csv, hashlib, json
from pathlib import Path

EXTS = {".png",".jpg",".jpeg",".webp",".gif",".svg",".mp4",".webm",".mov",".avif",".ico"}
roots = [Path("site_public"), Path("site_unredacted"), Path("site_test")]
rows=[]
for root in roots:
    if not root.exists():
        continue
    for p in root.rglob("*"):
        if p.is_file() and p.suffix.lower() in EXTS:
            data = p.read_bytes()
            rows.append({
                "path": p.as_posix(),
                "root": root.as_posix(),
                "name": p.name,
                "extension": p.suffix.lower(),
                "size_bytes": len(data),
                "size_mb": round(len(data)/1024/1024, 3),
                "sha256": hashlib.sha256(data).hexdigest(),
            })
rows.sort(key=lambda r: r["size_bytes"], reverse=True)
json_path = Path("outputs/aq26_asset_catalogue.json")
csv_path = Path("outputs/aq26_asset_catalogue.csv")
json_path.parent.mkdir(parents=True, exist_ok=True)
json_path.write_text(json.dumps(rows, indent=2), encoding="utf-8")
with csv_path.open("w", newline="", encoding="utf-8") as f:
    w=csv.DictWriter(f, fieldnames=["path","root","name","extension","size_bytes","size_mb","sha256"])
    w.writeheader()
    w.writerows(rows)
print(f"Wrote {json_path} and {csv_path} with {len(rows)} assets.")
for r in rows[:20]:
    print(f"{r['size_mb']:8.3f} MB  {r['path']}")
