#!/usr/bin/env python3
"""
AQ26 Hostinger deploy helper with explicit Hostinger SSH defaults/fallbacks.

Use:
  python scripts/aq26_deploy_hostinger.py --config configs/aq26_weekly_runtime.yml --dry-run false

Expected GitHub secrets for sccairquality.com:
  SCCAIRQUALITY_SSH_HOST=153.92.6.60
  SCCAIRQUALITY_SSH_PORT=65002
  SCCAIRQUALITY_SSH_USERNAME=u288464186
  SCCAIRQUALITY_SSH_PASSWORD=<your Hostinger SSH password>
  AIRQUALITY_HOSTINGER_PUBLIC_HTML_DIR=domains/sccairquality.com/public_html
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
        value = os.environ.get(name)
        if value is not None and str(value).strip() != "":
            return str(value).strip()
    return default


def load_config(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data if isinstance(data, dict) else {}


def clean_host(value: str) -> str:
    value = (value or "").strip()
    for prefix in ("https://", "http://", "ssh://", "sftp://"):
        value = value.replace(prefix, "")
    value = value.strip().strip("/")
    if "/" in value:
        value = value.split("/")[0]
    return value


def clean_remote_dir(value: str) -> str:
    value = (value or "").strip()
    for prefix in ("https://", "http://", "ssh://", "sftp://"):
        value = value.replace(prefix, "")
    value = value.rstrip("/")
    if not value:
        value = "domains/sccairquality.com/public_html"
    if "public_html" in value and not value.startswith("/") and not value.startswith("domains/"):
        value = value[value.index("public_html"):]
    return value


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


def connect_with_retries(host: str, port: int, username: str, password: str):
    last_error = None
    for attempt in range(1, 7):
        try:
            print(f"Connecting to Hostinger SSH/SFTP attempt {attempt}/6 on configured host/port.")
            sock = socket.create_connection((host, port), timeout=75)
            transport = paramiko.Transport(sock)
            transport.banner_timeout = 75
            transport.auth_timeout = 75
            transport.connect(username=username, password=password)
            sftp = paramiko.SFTPClient.from_transport(transport)
            print("Connected to Hostinger SFTP.")
            return transport, sftp
        except Exception as exc:
            last_error = exc
            print(f"SSH/SFTP attempt {attempt}/6 failed: {type(exc).__name__}: {exc}")
            time.sleep(min(20 * attempt, 90))
    raise RuntimeError(f"Unable to connect to Hostinger after retries: {last_error}") from last_error


def upload_tree(sftp: paramiko.SFTPClient, local_dir: Path, remote_dir: str, dry_run: bool) -> int:
    if not local_dir.exists():
        print(f"Skipping missing local folder: {local_dir}")
        return 0

    count = 0
    for path in sorted(local_dir.rglob("*")):
        if not path.is_file():
            continue
        if path.name == ".htpasswd":
            print(f"Skipping .htpasswd from repo upload: {path}")
            continue

        rel = path.relative_to(local_dir).as_posix()
        remote_path = posixpath.join(remote_dir, rel)

        if dry_run:
            print(f"DRY RUN: upload {path} -> {remote_path}")
        else:
            mkdir_p(sftp, posixpath.dirname(remote_path))
            sftp.put(str(path), remote_path)
        count += 1

    return count


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/aq26_weekly_runtime.yml")
    parser.add_argument("--dry-run", nargs="?", const="true", default="false")
    args = parser.parse_args()

    dry_run = parse_bool(args.dry_run)
    cfg = load_config(Path(args.config))

    host = clean_host(env_first(
        "SCCAIRQUALITY_SSH_HOST",
        "HOSTINGER_SSH_HOST",
        "SCCNEXUS_SSH_HOST",
        default=str(cfg.get("ssh_host", "") or cfg.get("hostinger_ssh_host", "153.92.6.60")),
    ))

    port_raw = env_first(
        "SCCAIRQUALITY_SSH_PORT",
        "HOSTINGER_SSH_PORT",
        "SCCNEXUS_SSH_PORT",
        default=str(cfg.get("ssh_port", "") or cfg.get("hostinger_ssh_port", "65002")),
    )

    username = env_first(
        "SCCAIRQUALITY_SSH_USERNAME",
        "HOSTINGER_SSH_USERNAME",
        "SCCNEXUS_SSH_USERNAME",
        default=str(cfg.get("ssh_username", "") or cfg.get("hostinger_ssh_username", "u288464186")),
    )

    password = env_first(
        "SCCAIRQUALITY_SSH_PASSWORD",
        "HOSTINGER_SSH_PASSWORD",
        "SCCNEXUS_SSH_PASSWORD",
        default=str(cfg.get("ssh_password", "") or cfg.get("hostinger_ssh_password", "")),
    )

    public_html = clean_remote_dir(env_first(
        "AIRQUALITY_HOSTINGER_PUBLIC_HTML_DIR",
        "HOSTINGER_PUBLIC_HTML_DIR",
        "SCCAIRQUALITY_PUBLIC_HTML_DIR",
        default=str(cfg.get("hostinger_public_html_dir", "") or cfg.get("public_html_dir", "domains/sccairquality.com/public_html")),
    ))

    try:
        port = int(str(port_raw).strip())
    except Exception:
        print(f"Invalid SSH port {port_raw!r}; using Hostinger default custom port 65002.")
        port = 65002

    print("AQ26 Hostinger deployment settings:")
    print(f"  host present: {bool(host)}")
    print(f"  port: {port}")
    print(f"  username present: {bool(username)}")
    print(f"  password present: {bool(password)}")
    print(f"  public_html present: {bool(public_html)}")
    print(f"  dry_run: {dry_run}")

    missing = []
    if not host:
        missing.append("SCCAIRQUALITY_SSH_HOST")
    if not username:
        missing.append("SCCAIRQUALITY_SSH_USERNAME")
    if not password:
        missing.append("SCCAIRQUALITY_SSH_PASSWORD")
    if missing:
        raise SystemExit("Missing required Hostinger SSH values: " + ", ".join(missing))

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
            print(f"DRY RUN complete. Would upload {total} files.")
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
