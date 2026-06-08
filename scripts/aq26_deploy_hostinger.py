#!/usr/bin/env python3
"""Deploy AQ26 public/unredacted/test folders to Hostinger over SFTP.

Required secrets:
- SCCAIRQUALITY_SSH_HOST
- SCCAIRQUALITY_SSH_USERNAME
- SCCAIRQUALITY_SSH_PASSWORD
- SCCAIRQUALITY_SSH_PORT, optional, defaults to 22
- AIRQUALITY_HOSTINGER_PUBLIC_HTML_DIR or HOSTINGER_PUBLIC_HTML_DIR
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path, PurePosixPath

import paramiko
import yaml


def load_yaml(path: str | Path) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {}


def as_bool(value: str | bool | None, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def mkdir_p_sftp(sftp: paramiko.SFTPClient, remote_dir: str) -> None:
    parts = PurePosixPath(remote_dir).parts
    current = ""
    for part in parts:
        if part == "/":
            current = "/"
            continue
        current = str(PurePosixPath(current) / part)
        try:
            sftp.stat(current)
        except FileNotFoundError:
            sftp.mkdir(current)


def upload_tree(sftp: paramiko.SFTPClient, local_root: Path, remote_root: str, dry_run: bool) -> int:
    if not local_root.exists():
        raise SystemExit(f"Local deploy folder missing: {local_root}")
    count = 0
    for local_file in sorted(local_root.rglob("*")):
        if not local_file.is_file():
            continue
        rel = local_file.relative_to(local_root)
        remote_file = str(PurePosixPath(remote_root) / PurePosixPath(*rel.parts))
        remote_dir = str(PurePosixPath(remote_file).parent)
        if dry_run:
            print(f"DRY RUN: upload {local_file} -> {remote_file}")
        else:
            mkdir_p_sftp(sftp, remote_dir)
            sftp.put(str(local_file), remote_file)
        count += 1
    return count


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/aq26_weekly_runtime.yml")
    parser.add_argument("--dry-run", default=os.getenv("DRY_RUN", "true"))
    args = parser.parse_args()

    dry_run = as_bool(args.dry_run, True)
    runtime = load_yaml(args.config)
    paths = runtime.get("paths", {})
    hostinger = runtime.get("hostinger", {})

    public = Path(paths.get("public_site", "site_public"))
    unredacted = Path(paths.get("unredacted_site", "site_unredacted"))
    test = Path(paths.get("test_site", "site_test"))

    host = os.getenv("SCCAIRQUALITY_SSH_HOST", "").strip()
    user = os.getenv("SCCAIRQUALITY_SSH_USERNAME", "").strip()
    password = os.getenv("SCCAIRQUALITY_SSH_PASSWORD", "")
    port = int(os.getenv("SCCAIRQUALITY_SSH_PORT", "22") or "22")
    public_html = os.getenv("AIRQUALITY_HOSTINGER_PUBLIC_HTML_DIR", "").strip() or os.getenv("HOSTINGER_PUBLIC_HTML_DIR", "").strip()

    if not public_html:
        raise SystemExit("Missing AIRQUALITY_HOSTINGER_PUBLIC_HTML_DIR or HOSTINGER_PUBLIC_HTML_DIR secret.")
    if not host or not user or not password:
        raise SystemExit("Missing Hostinger SSH secrets: host, username or password.")

    remote_public = str(PurePosixPath(public_html) / hostinger.get("public_subdir", ""))
    remote_unredacted = str(PurePosixPath(public_html) / hostinger.get("unredacted_subdir", "unredacted"))
    remote_test = str(PurePosixPath(public_html) / hostinger.get("test_subdir", "test"))

    if dry_run:
        print("Hostinger dry run enabled. No files will be uploaded.")
        class DummySFTP:
            pass
        sftp = None
        total = 0
        total += upload_tree(sftp, public, remote_public, True)  # type: ignore[arg-type]
        total += upload_tree(sftp, unredacted, remote_unredacted, True)  # type: ignore[arg-type]
        total += upload_tree(sftp, test, remote_test, True)  # type: ignore[arg-type]
        print(f"DRY RUN: would upload {total} files.")
        return

    transport = paramiko.Transport((host, port))
    transport.connect(username=user, password=password)
    try:
        sftp = paramiko.SFTPClient.from_transport(transport)
        total = 0
        total += upload_tree(sftp, public, remote_public, False)
        total += upload_tree(sftp, unredacted, remote_unredacted, False)
        total += upload_tree(sftp, test, remote_test, False)
        print(f"Uploaded {total} files to Hostinger.")
    finally:
        transport.close()


if __name__ == "__main__":
    main()
