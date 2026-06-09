#!/usr/bin/env python3
from __future__ import annotations
import argparse, csv, json
from pathlib import Path
from collections import defaultdict

def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--root", action="append", default=[])
    ap.add_argument("--output-dir", default="outputs/aq26_size_audit")
    ap.add_argument("--top", type=int, default=200)
    args=ap.parse_args()
    roots=[Path(r) for r in args.root] or [Path("outputs"),Path("site_public"),Path("site_unredacted"),Path("site_test")]
    files=[]
    by_top=defaultdict(int)
    by_ext=defaultdict(int)
    for root in roots:
        if not root.exists():
            continue
        for p in root.rglob("*"):
            if p.is_file():
                size=p.stat().st_size
                rel=p.as_posix()
                files.append({"path":rel,"size_bytes":size,"size_mb":round(size/1024/1024,3),"extension":p.suffix.lower() or "[none]"})
                parts=p.parts
                key="/".join(parts[:2]) if len(parts)>=2 else parts[0]
                by_top[key]+=size
                by_ext[p.suffix.lower() or "[none]"]+=size
    files.sort(key=lambda r:r["size_bytes"], reverse=True)
    out=Path(args.output_dir); out.mkdir(parents=True, exist_ok=True)
    summary={
        "total_bytes": sum(r["size_bytes"] for r in files),
        "total_mb": round(sum(r["size_bytes"] for r in files)/1024/1024,3),
        "file_count": len(files),
        "top_folders": sorted([{"folder":k,"size_bytes":v,"size_mb":round(v/1024/1024,3)} for k,v in by_top.items()], key=lambda r:r["size_bytes"], reverse=True)[:100],
        "extensions": sorted([{"extension":k,"size_bytes":v,"size_mb":round(v/1024/1024,3)} for k,v in by_ext.items()], key=lambda r:r["size_bytes"], reverse=True),
        "largest_files": files[:args.top],
    }
    (out/"artifact_size_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    with (out/"largest_files.csv").open("w", newline="", encoding="utf-8") as f:
        w=csv.DictWriter(f, fieldnames=["path","size_bytes","size_mb","extension"]); w.writeheader(); w.writerows(files[:args.top])
    print(f"Total scanned: {summary['total_mb']} MB across {len(files)} files")
    print("Largest files:")
    for r in files[:30]:
        print(f"{r['size_mb']:9.3f} MB  {r['path']}")
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
