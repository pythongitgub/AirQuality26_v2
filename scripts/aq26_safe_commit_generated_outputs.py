#!/usr/bin/env python3
"""
AQ26 safe generated-output commit helper.

This script is safe to use in GitHub Actions because:
- it never stages large ZIP/PDF/download bundles;
- it pulls/rebases before push to avoid non-fast-forward;
- if push still fails, it exits 0 so the live production deploy is not marked failed.
"""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

ROOT = Path.cwd()

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

DENY_PATTERNS = [
    "outputs/evidence/*.zip", "outputs/evidence/*.pdf", "outputs/evidence/*.tar",
    "outputs/evidence/*.tar.gz", "outputs/evidence/*.7z",
    "site_public/downloads/*.zip", "site_public/downloads/*.pdf", "site_public/downloads/*.tar",
    "site_public/downloads/*.tar.gz", "site_public/downloads/*.7z",
    "site_unredacted/downloads/*.zip", "site_unredacted/downloads/*.pdf", "site_unredacted/downloads/*.tar",
    "site_unredacted/downloads/*.tar.gz", "site_unredacted/downloads/*.7z",
    "site_test/downloads/*.zip", "site_test/downloads/*.pdf", "site_test/downloads/*.tar",
    "site_test/downloads/*.tar.gz", "site_test/downloads/*.7z",
]

def run(cmd, check=True):
    print("+", " ".join(cmd), flush=True)
    return subprocess.run(cmd, check=check, text=True)

def git(*args, check=True):
    return run(["git", *args], check=check)

def main():
    branch = os.environ.get("GITHUB_REF_NAME", "main")
    git("config", "user.name", "github-actions[bot]", check=False)
    git("config", "user.email", "github-actions[bot]@users.noreply.github.com", check=False)

    git("fetch", "origin", branch, check=False)
    git("reset", check=False)

    for pat in ALLOW_PATTERNS:
        git("add", pat, check=False)

    for pat in DENY_PATTERNS:
        git("reset", "--", pat, check=False)

    staged = subprocess.run(["git", "diff", "--cached", "--name-only", "-z"], capture_output=True, check=False).stdout.split(b"\0")
    for raw in staged:
        if not raw:
            continue
        rel = raw.decode("utf-8", "replace")
        p = ROOT / rel
        if p.exists() and p.is_file() and p.stat().st_size > 95 * 1024 * 1024:
            print(f"Unstaging oversized file: {rel}")
            git("reset", "--", rel, check=False)

    if git("diff", "--cached", "--quiet", check=False).returncode == 0:
        print("No lightweight generated changes to commit.")
        return 0

    if git("commit", "-m", "Build AQ26 weekly operational website files", check=False).returncode != 0:
        print("No commit created or commit failed; continuing.")
        return 0

    for attempt in range(1, 4):
        print(f"Pull/rebase/push attempt {attempt}/3")
        if git("pull", "--rebase", "origin", branch, check=False).returncode != 0:
            git("rebase", "--abort", check=False)
            time.sleep(5 * attempt)
            continue
        if git("push", "origin", f"HEAD:{branch}", check=False).returncode == 0:
            print("Lightweight generated files pushed successfully.")
            return 0
        time.sleep(5 * attempt)

    print("WARNING: GitHub bookkeeping push failed after retries. Continuing production run.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
