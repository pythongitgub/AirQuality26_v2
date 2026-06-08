#!/usr/bin/env python3
"""
AQ26 Hostinger deploy helper.

Expected CLI:
  python scripts/aq26_deploy_hostinger.py --config configs/aq26_weekly_runtime.yml --dry-run false
  python scripts/aq26_deploy_hostinger.py --config configs/aq26_weekly_runtime.yml --dry-run true

This version is deliberately tolerant:
- accepts --dry-run true/false or --dry-run as a flag;
- uses SCCAIRQUALITY_* secrets first, then HOSTINGER/SCCNEXUS fallbacks;
- retries SSH connection several times because Hostinger/GitHub SSH can time out intermittently;
- uploads site_public to the configured public_html root;
- uploads site_unredacted to /unredacted;
- uploads site_test to /test.
"""

from __future__ import annotations

import argparse
import os
import posixpath
import socket
import time
from pathlib import Path

import paramiko
import yaml


def parse_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return True
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def env_first(*names: str, default: str = "") -> str:
    for name in names:
        val = os.environ.get(name)
        if val is not None and str(val).strip() != "":
            return str(val).strip()
    return default


def load_config(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data if isinstance(data, dict) else {}


def normalise_remote_dir(raw: str) -> str:
    raw = (raw or "").strip()
    if not raw:
        raw = "public_html"
    raw = raw.replace("sftp://", "").replace("ssh://", "")
    raw = raw.replace("https://", "").replace("http://", "")
    if "public_html" in raw and not raw.startswith("/"):
        raw = raw[raw.index("public_html") :]
    return raw.rstrip("/")


def mkdir_p(sftp: paramiko.SFTPClient, remote_dir: str) -> None:
    remote_dir = remote_dir.replace("\\", "/")
    if not remote_dir or remote_dir == ".":
        return
    absolute = remote_dir.startswith("/")
    parts = [p for p in remote_dir.split("/") if p]
    current = "/" if absolute else ""
    for part in parts:
        current = posixpath.join(current, part) if current else part
        try:
            sftp.stat(current)
        except IOError:
            sftp.mkdir(current)


def upload_file(sftp: paramiko.SFTPClient, local: Path, remote: str, dry_run: bool) -> None:
    remote = remote.replace("\\", "/")
    if dry_run:
        print(f"DRY RUN: upload {local} -> {remote}")
        return
    mkdir_p(sftp, posixpath.dirname(remote))
    sftp.put(str(local), remote)


def upload_tree(sftp: paramiko.SFTPClient, local_dir: Path, remote_dir: str, dry_run: bool) -> int:
    if not local_dir.exists():
        print(f"Skipping missing local folder: {local_dir}")
        return 0
    count = 0
    for path in sorted(local_dir.rglob("*")):
        if not path.is_file():
            continue
        if path.name == ".htpasswd":
            print(f"Skipping local .htpasswd file: {path}")
            continue
        rel = path.relative_to(local_dir).as_posix()
        upload_file(sftp, path, posixpath.join(remote_dir, rel), dry_run)
        count += 1
    return count


def connect_with_retries(host: str, port: int, username: str, password: str):
    last_error = None
    for attempt in range(1, 6):
        try:
            print(f"Connecting to Hostinger SSH/SFTP attempt {attempt}/5: {host}:{port}")
            sock = socket.create_connection((host, port), timeout=60)
            transport = paramiko.Transport(sock)
            transport.banner_timeout = 60
            transport.auth_timeout = 60
            transport.connect(username=username, password=password)
            sftp = paramiko.SFTPClient.from_transport(transport)
            print("Connected to Hostinger SFTP.")
            return transport, sftp
        except Exception as exc:
            last_error = exc
            print(f"SSH/SFTP attempt {attempt}/5 failed: {type(exc).__name__}: {exc}")
            time.sleep(10 * attempt)
    raise RuntimeError(f"Unable to connect to Hostinger after retries: {last_error}") from last_error


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/aq26_weekly_runtime.yml")
    parser.add_argument("--dry-run", nargs="?", const="true", default="false")
    args = parser.parse_args()

    dry_run = parse_bool(args.dry_run)
    cfg = load_config(Path(args.config))

    host = env_first("SCCAIRQUALITY_SSH_HOST", "HOSTINGER_SSH_HOST", "SCCNEXUS_SSH_HOST",
                     default=str(cfg.get("ssh_host", "") or cfg.get("hostinger_ssh_host", "")))
    port_raw = env_first("SCCAIRQUALITY_SSH_PORT", "HOSTINGER_SSH_PORT", "SCCNEXUS_SSH_PORT",
                         default=str(cfg.get("ssh_port", "") or cfg.get("hostinger_ssh_port", "22")))
    username = env_first("SCCAIRQUALITY_SSH_USERNAME", "HOSTINGER_SSH_USERNAME", "SCCNEXUS_SSH_USERNAME",
                         default=str(cfg.get("ssh_username", "") or cfg.get("hostinger_ssh_username", "")))
    password = env_first("SCCAIRQUALITY_SSH_PASSWORD", "HOSTINGER_SSH_PASSWORD", "SCCNEXUS_SSH_PASSWORD",
                         default=str(cfg.get("ssh_password", "") or cfg.get("hostinger_ssh_password", "")))
    public_html = env_first("AIRQUALITY_HOSTINGER_PUBLIC_HTML_DIR", "HOSTINGER_PUBLIC_HTML_DIR", "SCCAIRQUALITY_PUBLIC_HTML_DIR",
                            default=str(cfg.get("hostinger_public_html_dir", "") or cfg.get("public_html_dir", "public_html")))

    host = host.replace("https://", "").replace("http://", "").replace("ssh://", "").replace("sftp://", "").strip().strip("/")
    if "/" in host:
        host = host.split("/")[0]

    try:
        port = int(str(port_raw).strip())
    except Exception:
        print(f"Invalid SSH port value {port_raw!r}; falling back to 22.")
        port = 22

    public_html = normalise_remote_dir(public_html)

    print("AQ26 Hostinger deployment settings:")
    print(f"  host: {host or '[missing]'}")
    print(f"  port: {port}")
    print(f"  username present: {bool(username)}")
    print(f"  password present: {bool(password)}")
    print(f"  public_html: {public_html}")
    print(f"  dry_run: {dry_run}")

    missing = []
    if not host:
        missing.append("SCCAIRQUALITY_SSH_HOST")
    if not username:
        missing.append("SCCAIRQUALITY_SSH_USERNAME")
    if not password:
        missing.append("SCCAIRQUALITY_SSH_PASSWORD")
    if missing:
        raise SystemExit("Missing required SSH secrets/config: " + ", ".join(missing))

    if dry_run:
        print("Dry-run mode: will test connection and list intended uploads, but not write files.")

    transport = None
    sftp = None
    try:
        transport, sftp = connect_with_retries(host, port, username, password)
        mappings = [
            (Path("site_public"), public_html),
            (Path("site_unredacted"), posixpath.join(public_html, "unredacted")),
            (Path("site_test"), posixpath.join(public_html, "test")),
        ]
        total = 0
        for local_dir, remote_dir in mappings:
            print(f"Deploy mapping: {local_dir} -> {remote_dir}")
            total += upload_tree(sftp, local_dir, remote_dir, dry_run=dry_run)

        if dry_run:
            print(f"DRY RUN complete. Would upload {total} files to Hostinger.")
        else:
            print(f"Uploaded {total} files to Hostinger.")
    finally:
        if sftp is not None:
            sftp.close()
        if transport is not None:
            transport.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
