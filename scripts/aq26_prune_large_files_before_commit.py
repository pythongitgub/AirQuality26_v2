#!/usr/bin/env python3
"""Remove/unstage large generated AQ26 artefacts before committing back to GitHub.

GitHub rejects normal git pushes containing files over 100 MB. AQ26 weekly evidence
bundles should be deployed to Hostinger and/or uploaded as GitHub Actions artifacts,
not committed into the source repository.
"""
from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path

DEFAULT_PATTERNS = [
    "outputs/evidence/*.zip",
    "outputs/evidence/*.pdf",
    "outputs/evidence/*.sha256.txt",
    "site_public/downloads/*.zip",
    "site_public/downloads/*.pdf",
    "site_public/downloads/*.sha256.txt",
    "site_unredacted/downloads/*.zip",
    "site_unredacted/downloads/*.pdf",
    "site_unredacted/downloads/*.sha256.txt",
    "site_test/downloads/*.zip",
    "site_test/downloads/*.pdf",
    "site_test/downloads/*.sha256.txt",
]


def run(cmd: list[str], check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, text=True, capture_output=True, check=check)


def git_unstage(path: Path) -> None:
    run(["git", "reset", "--", str(path)])


def git_remove_cached(path: Path) -> None:
    run(["git", "rm", "--cached", "--ignore-unmatch", str(path)])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--max-mb", type=float, default=95.0)
    parser.add_argument("--delete-working-copy", action="store_true", help="Delete matching files from working tree as well as unstaging them")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    max_bytes = int(args.max_mb * 1024 * 1024)
    removed: list[Path] = []

    for pattern in DEFAULT_PATTERNS:
        for p in root.glob(pattern):
            if not p.is_file():
                continue
            size = p.stat().st_size
            # Always unstage generated archives/reports in these locations. They are runtime artefacts.
            rel = p.relative_to(root)
            git_unstage(rel)
            git_remove_cached(rel)
            if size >= max_bytes or args.delete_working_copy:
                try:
                    p.unlink()
                except FileNotFoundError:
                    pass
            removed.append(rel)

    # Last-resort scan: unstage any staged file over the limit.
    staged = run(["git", "diff", "--cached", "--name-only"]).stdout.splitlines()
    for name in staged:
        p = root / name
        if p.is_file() and p.stat().st_size >= max_bytes:
            rel = p.relative_to(root)
            git_unstage(rel)
            git_remove_cached(rel)
            removed.append(rel)

    if removed:
        print("AQ26 large/generated artefacts excluded from repository commit:")
        for rel in sorted(set(map(str, removed))):
            print(f" - {rel}")
    else:
        print("AQ26 large/generated artefact check: nothing to exclude.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
