#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json
from datetime import datetime, timezone
from pathlib import Path

def sha256(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024*1024), b""):
            h.update(chunk)
    return h.hexdigest()

def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--max-mb", type=float, default=25.0)
    ap.add_argument("--root", action="append", default=["site_public","site_unredacted","site_test"])
    args=ap.parse_args()
    limit=int(args.max_mb*1024*1024)
    moved=[]
    for root_s in args.root:
        root=Path(root_s)
        if not root.exists():
            continue
        holding=root/"downloads"/"_large_files_removed_from_website"
        for p in list(root.rglob("*")):
            if not p.is_file():
                continue
            if p.name == ".htpasswd":
                continue
            if p.suffix.lower() in {".zip",".7z",".tar",".gz",".parquet"} and p.stat().st_size > limit:
                rel=p.relative_to(root)
                digest=sha256(p)
                meta={
                    "original_path": rel.as_posix(),
                    "removed_at_utc": datetime.now(timezone.utc).isoformat(),
                    "size_bytes": p.stat().st_size,
                    "size_mb": round(p.stat().st_size/1024/1024,3),
                    "sha256": digest,
                    "reason": f"Large evidence/data bundle over {args.max_mb} MB removed from publish folder. Store canonical copy in Google Drive/Shared Drive and expose metadata/link from website.",
                }
                holding.mkdir(parents=True, exist_ok=True)
                meta_path=p.with_suffix(p.suffix+".metadata.json")
                meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
                removed_path=holding/(rel.as_posix().replace("/","__")+".removed")
                removed_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
                size=p.stat().st_size
                p.unlink()
                moved.append((root.as_posix(), rel.as_posix(), size))
    print(f"Removed {len(moved)} large publish files over {args.max_mb} MB.")
    for root, rel, size in moved:
        print(f"{size/1024/1024:8.2f} MB  {root}/{rel}")
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
