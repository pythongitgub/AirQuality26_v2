#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
from datetime import datetime, timezone
from pathlib import Path

KEEP_FILES = {
    "aq26-weekly-production-lean-only.yml",
    "aq26-hostinger-ssh-preflight.yml",
}

OLD_MARKERS = [
    "name: AQ26 Weekly Production Evidence, Website, Drive and Deploy",
    "aq26-weekly-production-output",
    "outputs/**\nsite_public/**\nsite_unredacted/**\nsite_test/**",
    "path: outputs/**",
]

def looks_like_old_weekly_workflow(path: Path) -> bool:
    if path.name in KEEP_FILES:
        return False
    if path.suffix.lower() not in {".yml", ".yaml"}:
        return False
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return False
    if any(marker in text for marker in OLD_MARKERS):
        return True
    # Conservative extra catch: same displayed workflow name in any YAML.
    if "AQ26 Weekly Production Evidence" in text and "Drive and Deploy" in text:
        return True
    return False

def main() -> int:
    parser = argparse.ArgumentParser(description="Disable old AQ26 weekly workflows that still upload huge artifacts.")
    parser.add_argument("--apply", action="store_true", help="Actually move files. Without this flag only prints what would move.")
    parser.add_argument("--workflows", default=".github/workflows")
    parser.add_argument("--disabled-dir", default="docs/disabled_workflows")
    args = parser.parse_args()

    workflows = Path(args.workflows)
    disabled_root = Path(args.disabled_dir)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    moved = []

    for path in sorted(workflows.glob("*")):
        if looks_like_old_weekly_workflow(path):
            dest = disabled_root / f"{path.stem}.disabled-{stamp}{path.suffix}.txt"
            moved.append((path, dest))
            print(f"OLD WEEKLY WORKFLOW: {path} -> {dest}")

    if not moved:
        print("No old AQ26 weekly workflows found.")
        return 0

    if not args.apply:
        print("\nDry run only. Re-run with --apply to move these files.")
        return 0

    disabled_root.mkdir(parents=True, exist_ok=True)
    for src, dest in moved:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dest))

    print(f"\nMoved {len(moved)} old weekly workflow(s).")
    print("Commit the changes, then run the workflow named: AQ26 Weekly Production LEAN REVIEW PACK")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
