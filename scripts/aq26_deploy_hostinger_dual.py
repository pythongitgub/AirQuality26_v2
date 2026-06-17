#!/usr/bin/env python3
"""
AQ26 dual-surface Hostinger deploy helper.

Deploys site_public/ and site_unredacted/ to Hostinger by SSH, FTP, or auto fallback.
- Preserves .htaccess and .htpasswd on both surfaces, especially /unredacted/ auth.
- Defaults blank FTP port to 21 instead of passing an empty -p value to lftp.
- Falls back from FTP_* secrets to existing SSH/path secrets where sensible.
"""
from __future__ import annotations

import os
import shlex
import subprocess
import sys
from pathlib import Path

ROOT = Path.cwd()
PUBLIC_SRC = ROOT / "site_public"
UNREDACTED_SRC = ROOT / "site_unredacted"


def env_any(names: list[str], default: str = "") -> str:
    for name in names:
        value = os.environ.get(name, "")
        if value is not None and str(value).strip() != "":
            return str(value).strip()
    return default


def require(label: str, value: str) -> str:
    if not value:
        raise RuntimeError(f"Missing required deploy setting: {label}")
    return value


def log(msg: str) -> None:
    print(msg, flush=True)


def run(cmd: list[str], *, env: dict[str, str] | None = None) -> None:
    safe = []
    for c in cmd:
        s = str(c)
        # Do not print passwords if they accidentally appear in args.
        if os.environ.get("SSHPASS") and s == os.environ.get("SSHPASS"):
            s = "***"
        safe.append(shlex.quote(s))
    print("+", " ".join(safe), flush=True)
    merged = os.environ.copy()
    if env:
        merged.update(env)
    subprocess.run(cmd, check=True, text=True, env=merged)


def ensure_sources() -> None:
    missing = [str(p) for p in (PUBLIC_SRC, UNREDACTED_SRC) if not p.exists()]
    if missing:
        raise RuntimeError("Missing local build folders: " + ", ".join(missing))


def ssh_settings() -> tuple[list[str], str, str, dict[str, str]]:
    host = require("SCCAIRQUALITY_SSH_HOST", env_any(["SCCAIRQUALITY_SSH_HOST"]))
    port = require("SCCAIRQUALITY_SSH_PORT", env_any(["SCCAIRQUALITY_SSH_PORT"], "65002"))
    user = require("SCCAIRQUALITY_SSH_USERNAME", env_any(["SCCAIRQUALITY_SSH_USERNAME"]))
    password = require("SCCAIRQUALITY_SSH_PASSWORD", env_any(["SCCAIRQUALITY_SSH_PASSWORD"]))
    public_dir = require("AIRQUALITY_HOSTINGER_PUBLIC_HTML_DIR", env_any(["AIRQUALITY_HOSTINGER_PUBLIC_HTML_DIR"]))
    unredacted_dir = require("AIRQUALITY_HOSTINGER_PUBLIC_UNREDACTED_DIR", env_any(["AIRQUALITY_HOSTINGER_PUBLIC_UNREDACTED_DIR"]))

    base = f"{user}@{host}"
    ssh_cmd = [
        "sshpass", "-e", "ssh",
        "-p", port,
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=/dev/null",
        "-o", "ConnectTimeout=20",
        "-o", "ServerAliveInterval=10",
        "-o", "ServerAliveCountMax=2",
        base,
    ]
    env = {"SSHPASS": password}
    return ssh_cmd, public_dir, unredacted_dir, env


def deploy_ssh() -> None:
    log("Deploy strategy ssh/auto: trying SSH.")
    ensure_sources()
    ssh_cmd, public_dir, unredacted_dir, env = ssh_settings()

    run([*ssh_cmd, "echo SSH_OK && pwd && whoami"], env=env)
    run([*ssh_cmd, f"mkdir -p {shlex.quote(public_dir)} {shlex.quote(unredacted_dir)}"], env=env)

    host_part = ssh_cmd[-1]
    ssh_transport = " ".join(shlex.quote(x) for x in ssh_cmd[:-1])

    def rsync(src: Path, remote_dir: str, label: str) -> None:
        log(f"Uploading {label} by SSH/rsync -> {remote_dir}")
        run([
            "rsync", "-az", "--delete",
            "--exclude", ".htaccess",
            "--exclude", ".htpasswd",
            "-e", ssh_transport,
            str(src) + "/",
            f"{host_part}:{remote_dir.rstrip('/')}/",
        ], env=env)
        log(f"SSH deploy complete for {label}")

    rsync(PUBLIC_SRC, public_dir, "public")
    rsync(UNREDACTED_SRC, unredacted_dir, "unredacted")


def ftp_settings() -> tuple[str, str, str, str, str, str]:
    # Prefer explicit FTP secrets. Fall back to SSH/path secrets only to keep existing repos working.
    host = env_any(["SCCAIRQUALITY_FTP_HOST", "FTP_HOST", "SCCAIRQUALITY_SSH_HOST"])
    port = env_any(["SCCAIRQUALITY_FTP_PORT", "FTP_PORT"], "21") or "21"
    user = env_any(["SCCAIRQUALITY_FTP_USERNAME", "FTP_USERNAME", "SCCAIRQUALITY_SSH_USERNAME"])
    password = env_any(["SCCAIRQUALITY_FTP_PASSWORD", "FTP_PASSWORD", "SCCAIRQUALITY_SSH_PASSWORD"])
    public_dir = env_any(["SCCAIRQUALITY_FTP_PUBLIC_HTML_DIR", "FTP_PUBLIC_HTML_DIR", "AIRQUALITY_HOSTINGER_PUBLIC_HTML_DIR"])
    unredacted_dir = env_any(["SCCAIRQUALITY_FTP_UNREDACTED_DIR", "FTP_UNREDACTED_DIR", "AIRQUALITY_HOSTINGER_PUBLIC_UNREDACTED_DIR"])

    require("SCCAIRQUALITY_FTP_HOST or SCCAIRQUALITY_SSH_HOST", host)
    require("SCCAIRQUALITY_FTP_USERNAME or SCCAIRQUALITY_SSH_USERNAME", user)
    require("SCCAIRQUALITY_FTP_PASSWORD or SCCAIRQUALITY_SSH_PASSWORD", password)
    require("SCCAIRQUALITY_FTP_PUBLIC_HTML_DIR or AIRQUALITY_HOSTINGER_PUBLIC_HTML_DIR", public_dir)
    require("SCCAIRQUALITY_FTP_UNREDACTED_DIR or AIRQUALITY_HOSTINGER_PUBLIC_UNREDACTED_DIR", unredacted_dir)
    return host, port, user, password, public_dir, unredacted_dir


def lftp_quote(value: str) -> str:
    # lftp command language uses shell-like quoting.
    return shlex.quote(value)


def lftp_mirror(src: Path, remote_dir: str, label: str, host: str, port: str, user: str, password: str) -> None:
    remote = remote_dir.rstrip("/")
    log(f"Uploading {label} by FTP/lftp -> {remote}")
    cmd = "\n".join([
        "set net:timeout 20",
        "set net:max-retries 2",
        "set ftp:ssl-allow true",
        "set ssl:verify-certificate no",
        f"open -p {lftp_quote(port)} -u {lftp_quote(user)},{lftp_quote(password)} {lftp_quote(host)}",
        f"mkdir -p {lftp_quote(remote)}",
        f"mirror -R --delete --verbose --parallel=2 --exclude-glob .htaccess --exclude-glob .htpasswd {lftp_quote(str(src))} {lftp_quote(remote)}",
        "bye",
    ])
    print(f"+ lftp mirror {label} -> {remote}", flush=True)
    subprocess.run(["lftp", "-c", cmd], check=True, text=True)
    log(f"FTP deploy complete for {label}")


def deploy_ftp() -> None:
    log("Deploy strategy ftp/auto: trying FTP.")
    ensure_sources()
    host, port, user, password, public_dir, unredacted_dir = ftp_settings()
    lftp_mirror(PUBLIC_SRC, public_dir, "public", host, port, user, password)
    lftp_mirror(UNREDACTED_SRC, unredacted_dir, "unredacted", host, port, user, password)


def main() -> int:
    strategy = env_any(["DEPLOY_STRATEGY", "deploy_strategy"], "auto").lower()
    log(f"AQ26 deploy strategy: {strategy}")

    if strategy in {"build_only", "none", "no_deploy"}:
        log("Build-only mode selected; skipping Hostinger deployment.")
        return 0

    if strategy == "ssh":
        deploy_ssh()
        return 0

    if strategy == "ftp":
        deploy_ftp()
        return 0

    if strategy == "auto":
        try:
            deploy_ssh()
            return 0
        except Exception as exc:
            log(f"SSH deploy failed: {exc}")
            log("Trying FTP fallback.")
            deploy_ftp()
            return 0

    raise RuntimeError(f"Unknown DEPLOY_STRATEGY: {strategy}")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"AQ26 deploy failed: {exc}", file=sys.stderr)
        raise
