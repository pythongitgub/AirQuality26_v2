#!/usr/bin/env python3
"""
AQ26 safe generated-output commit helper.

Purpose:
- Commit only lightweight weekly operational files back to GitHub.
- Never commit large evidence ZIP/PDF/download artefacts.
- Avoid failing the whole weekly deployment if the remote branch moved.
- Retry pull/rebase/push a few times, then warn and exit 0.

This script is intended to replace the fragile workflow block:

    git add site_public site_unredacted site_test outputs || true
    git commit ...
    git push

The heavy evidence bundle should be kept as:
- Hostinger deployed download
- GitHub Actions artifact
- Google Drive / Shared Drive later
not as source-controlled GitHub content.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path.cwd()

# Only these paths are allowed into the weekly operational commit.
# Keep this deliberately narrow.
ALLOW_PATTERNS = [
    "site_public/*.html",
    "site_public/data/**/*.json",
    "site_public/data/**/*.csv",
    "site_public/data/**/*.md",
    "site_public/downloads/*.sha256.txt",

    "site_unredacted/*.html",
    "site_unredacted/data/**/*.json",
    "site_unredacted/data/**/*.csv",
    "site_unredacted/data/**/*.md",
    "site_unredacted/downloads/*.sha256.txt",

    "site_test/*.html",
    "site_test/data/**/*.json",
    "site_test/data/**/*.csv",
    "site_test/data/**/*.md",
    "site_test/downloads/*.sha256.txt",

    "outputs/logs/**/*.json",
    "outputs/logs/**/*.txt",
    "outputs/evidence/*manifest*.json",
    "outputs/evidence/*.sha256.txt",
]

# These are explicitly removed from the staged commit, even if a broad add
# happens elsewhere in the workflow.
DENY_PATTERNS = [
    "outputs/evidence/*.zip",
    "outputs/evidence/*.pdf",
    "outputs/evidence/*.tar",
    "outputs/evidence/*.tar.gz",
    "outputs/evidence/*.7z",

    "site_public/downloads/*.zip",
    "site_public/downloads/*.pdf",
    "site_public/downloads/*.tar",
    "site_public/downloads/*.tar.gz",
    "site_public/downloads/*.7z",

    "site_unredacted/downloads/*.zip",
    "site_unredacted/downloads/*.pdf",
    "site_unredacted/downloads/*.tar",
    "site_unredacted/downloads/*.tar.gz",
    "site_unredacted/downloads/*.7z",

    "site_test/downloads/*.zip",
    "site_test/downloads/*.pdf",
    "site_test/downloads/*.tar",
    "site_test/downloads/*.tar.gz",
    "site_test/downloads/*.7z",
]


def run(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    print("+", " ".join(cmd), flush=True)
    return subprocess.run(cmd, text=True, check=check)


def git(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return run(["git", *args], check=check)


def main() -> int:
    git("config", "user.name", "github-actions[bot]")
    git("config", "user.email", "github-actions[bot]@users.noreply.github.com")

    branch = os.environ.get("GITHUB_REF_NAME", "main")
    remote = "origin"

    # Make sure we know the current remote tip.
    git("fetch", remote, branch, check=False)

    # Start with a clean index so earlier broad git add commands cannot leak
    # large artefacts into the commit.
    git("reset", check=False)

    for pattern in ALLOW_PATTERNS:
        git("add", pattern, check=False)

    for pattern in DENY_PATTERNS:
        git("reset", "--", pattern, check=False)

    # Refuse to commit anything over 95 MB as a final safety net.
    staged = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "-z"],
        capture_output=True,
        text=False,
        check=False,
    ).stdout.split(b"\0")

    too_large: list[tuple[str, int]] = []
    for raw in staged:
        if not raw:
            continue
        rel = raw.decode("utf-8", errors="replace")
        p = ROOT / rel
        if p.exists() and p.is_file():
            size = p.stat().st_size
            if size > 95 * 1024 * 1024:
                too_large.append((rel, size))
                git("reset", "--", rel, check=False)

    if too_large:
        print("Removed oversized files from staged commit:")
        for rel, size in too_large:
            print(f"  {rel} ({size / 1024 / 1024:.2f} MB)")

    if git("diff", "--cached", "--quiet", check=False).returncode == 0:
        print("No lightweight generated changes to commit.")
        return 0

    msg = "Build AQ26 weekly operational website files"
    git("commit", "-m", msg)

    # Rebase local generated commit onto latest remote. If another workflow or
    # manual edit landed while this run was building, this avoids non-fast-forward.
    for attempt in range(1, 4):
        print(f"Push attempt {attempt}/3")
        pull = git("pull", "--rebase", remote, branch, check=False)
        if pull.returncode != 0:
            print("Pull/rebase failed. Aborting rebase and retrying if possible.")
            git("rebase", "--abort", check=False)
            time.sleep(5 * attempt)
            continue

        push = git("push", remote, f"HEAD:{branch}", check=False)
        if push.returncode == 0:
            print("Generated lightweight AQ26 files pushed successfully.")
            return 0

        print("Push failed, likely because remote moved again. Retrying.")
        time.sleep(5 * attempt)

    print("")
    print("WARNING: Could not push generated lightweight files after retries.")
    print("The website deploy/email steps already ran before this bookkeeping step.")
    print("Leaving workflow successful so weekly production is not blocked by Git sync.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
