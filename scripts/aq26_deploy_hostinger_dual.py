#!/usr/bin/env python3
"""AQ26 dual Hostinger deploy with SSH timeout handling and FTP fallback.

Deploys site_public to the public web root and site_unredacted to /unredacted.
Does not upload .htaccess or .htpasswd, so existing Basic Auth remains intact.
"""
from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path.cwd()
PUBLIC_SRC = ROOT / "site_public"
UNREDACTED_SRC = ROOT / "site_unredacted"


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def run(cmd: list[str], *, check: bool = True, env_override: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    printable = " ".join(shlex.quote(str(c)) for c in cmd)
    print(f"+ {printable}", flush=True)
    merged = os.environ.copy()
    if env_override:
        merged.update(env_override)
    return subprocess.run(cmd, check=check, env=merged, text=True)


def require_dirs() -> None:
    missing = [str(p) for p in (PUBLIC_SRC, UNREDACTED_SRC) if not p.is_dir()]
    if missing:
        raise SystemExit("Missing built site directories: " + ", ".join(missing))


def ssh_base_options() -> tuple[list[str], dict[str, str] | None, tempfile.TemporaryDirectory[str] | None]:
    host = env("SCCAIRQUALITY_SSH_HOST")
    port = env("SCCAIRQUALITY_SSH_PORT", "22")
    user = env("SCCAIRQUALITY_SSH_USERNAME")
    password = env("SCCAIRQUALITY_SSH_PASSWORD")
    private_key = env("SCCAIRQUALITY_SSH_PRIVATE_KEY")

    if not host or not user:
        raise RuntimeError("SSH host/username secrets are missing")

    base = [
        "-p", port,
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=/dev/null",
        "-o", "ConnectTimeout=20",
        "-o", "ServerAliveInterval=10",
        "-o", "ServerAliveCountMax=2",
    ]

    tmp: tempfile.TemporaryDirectory[str] | None = None
    envp: dict[str, str] | None = None

    if private_key:
        tmp = tempfile.TemporaryDirectory()
        key_path = Path(tmp.name) / "aq26_hostinger_key"
        key_path.write_text(private_key + "\n", encoding="utf-8")
        key_path.chmod(0o600)
        base.extend(["-i", str(key_path), "-o", "BatchMode=yes"])
    elif password:
        base = ["sshpass", "-e", "ssh", *base]
        envp = {"SSHPASS": password}
        return base + [f"{user}@{host}"], envp, tmp
    else:
        raise RuntimeError("Neither SCCAIRQUALITY_SSH_PASSWORD nor SCCAIRQUALITY_SSH_PRIVATE_KEY is set")

    return ["ssh", *base, f"{user}@{host}"], envp, tmp


def scp_base_options(tmp: tempfile.TemporaryDirectory[str] | None) -> tuple[list[str], dict[str, str] | None]:
    host = env("SCCAIRQUALITY_SSH_HOST")
    port = env("SCCAIRQUALITY_SSH_PORT", "22")
    user = env("SCCAIRQUALITY_SSH_USERNAME")
    password = env("SCCAIRQUALITY_SSH_PASSWORD")
    private_key = env("SCCAIRQUALITY_SSH_PRIVATE_KEY")

    opts = [
        "-P", port,
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=/dev/null",
        "-o", "ConnectTimeout=20",
    ]
    envp = None
    if private_key:
        if not tmp:
            raise RuntimeError("Temporary key directory missing")
        opts.extend(["-i", str(Path(tmp.name) / "aq26_hostinger_key"), "-o", "BatchMode=yes"])
        return ["scp", *opts], envp
    if password:
        envp = {"SSHPASS": password}
        return ["sshpass", "-e", "scp", *opts], envp
    raise RuntimeError("No SSH authentication available")


def ssh_preflight() -> tuple[list[str], dict[str, str] | None, tempfile.TemporaryDirectory[str] | None]:
    ssh_cmd, envp, tmp = ssh_base_options()
    run([*ssh_cmd, "echo SSH_OK && pwd && whoami"], env_override=envp)
    return ssh_cmd, envp, tmp


def upload_ssh_one(src: Path, remote_dir: str, label: str, ssh_cmd: list[str], envp: dict[str, str] | None, tmp: tempfile.TemporaryDirectory[str] | None) -> None:
    if not remote_dir:
        raise RuntimeError(f"Missing remote directory for {label}")
    run([*ssh_cmd, f"mkdir -p {shlex.quote(remote_dir)}"], env_override=envp)

    scp_cmd, scp_env = scp_base_options(tmp)
    host = env("SCCAIRQUALITY_SSH_HOST")
    user = env("SCCAIRQUALITY_SSH_USERNAME")

    # Upload a tarball then extract remotely. This is more reliable than hundreds of small scp calls.
    with tempfile.TemporaryDirectory() as td:
        tar_path = Path(td) / f"{label}.tar.gz"
        run([
            "tar", "--exclude=.htaccess", "--exclude=.htpasswd", "-czf", str(tar_path), "-C", str(src), "."
        ])
        remote_tar = f"{remote_dir.rstrip('/')}/.aq26_{label}.tar.gz"
        run([*scp_cmd, str(tar_path), f"{user}@{host}:{remote_tar}"], env_override=scp_env)
        run([*ssh_cmd, f"cd {shlex.quote(remote_dir)} && tar -xzf .aq26_{label}.tar.gz && rm -f .aq26_{label}.tar.gz"], env_override=envp)
    print(f"SSH deploy complete for {label}: {remote_dir}")


def deploy_ssh() -> None:
    ssh_cmd, envp, tmp = ssh_preflight()
    try:
        upload_ssh_one(PUBLIC_SRC, env("AIRQUALITY_HOSTINGER_PUBLIC_HTML_DIR"), "public", ssh_cmd, envp, tmp)
        upload_ssh_one(UNREDACTED_SRC, env("AIRQUALITY_HOSTINGER_PUBLIC_UNREDACTED_DIR"), "unredacted", ssh_cmd, envp, tmp)
    finally:
        if tmp:
            tmp.cleanup()


def ftp_required() -> tuple[str, str, str, str, str, str]:
    host = env("SCCAIRQUALITY_FTP_HOST") or env("SCCAIRQUALITY_SSH_HOST")
    port = env("SCCAIRQUALITY_FTP_PORT", "21")
    user = env("SCCAIRQUALITY_FTP_USERNAME") or env("SCCAIRQUALITY_SSH_USERNAME")
    password = env("SCCAIRQUALITY_FTP_PASSWORD") or env("SCCAIRQUALITY_SSH_PASSWORD")
    public_dir = env("SCCAIRQUALITY_FTP_PUBLIC_HTML_DIR") or env("AIRQUALITY_HOSTINGER_PUBLIC_HTML_DIR")
    unredacted_dir = env("SCCAIRQUALITY_FTP_UNREDACTED_DIR") or env("AIRQUALITY_HOSTINGER_PUBLIC_UNREDACTED_DIR")
    missing = [name for name, val in {
        "SCCAIRQUALITY_FTP_HOST or SCCAIRQUALITY_SSH_HOST": host,
        "SCCAIRQUALITY_FTP_USERNAME or SCCAIRQUALITY_SSH_USERNAME": user,
        "SCCAIRQUALITY_FTP_PASSWORD or SCCAIRQUALITY_SSH_PASSWORD": password,
        "SCCAIRQUALITY_FTP_PUBLIC_HTML_DIR or AIRQUALITY_HOSTINGER_PUBLIC_HTML_DIR": public_dir,
        "SCCAIRQUALITY_FTP_UNREDACTED_DIR or AIRQUALITY_HOSTINGER_PUBLIC_UNREDACTED_DIR": unredacted_dir,
    }.items() if not val]
    if missing:
        raise RuntimeError("FTP deploy missing: " + ", ".join(missing))
    return host, port, user, password, public_dir, unredacted_dir


def lftp_mirror(src: Path, remote_dir: str, label: str, host: str, port: str, user: str, password: str) -> None:
    # lftp's mirror -R uploads recursively. Exclude auth files so password protection survives.
    cmd = f"""
set net:timeout 20
set net:max-retries 2
set ftp:ssl-allow true
set ssl:verify-certificate no
open -p {shlex.quote(port)} -u {shlex.quote(user)},{shlex.quote(password)} {shlex.quote(host)}
mkdir -p {shlex.quote(remote_dir)}
mirror -R --verbose --parallel=2 --exclude-glob .htaccess --exclude-glob .htpasswd {shlex.quote(str(src))} {shlex.quote(remote_dir)}
bye
""".strip()
    print(f"+ lftp mirror {label} -> {remote_dir}", flush=True)
    subprocess.run(["lftp", "-c", cmd], check=True, text=True)
    print(f"FTP deploy complete for {label}: {remote_dir}")


def deploy_ftp() -> None:
    host, port, user, password, public_dir, unredacted_dir = ftp_required()
    lftp_mirror(PUBLIC_SRC, public_dir, "public", host, port, user, password)
    lftp_mirror(UNREDACTED_SRC, unredacted_dir, "unredacted", host, port, user, password)


def main() -> int:
    require_dirs()
    strategy = env("AQ26_DEPLOY_STRATEGY", "auto").lower()
    if strategy == "build_only":
        print("Build-only selected; skipping deploy.")
        return 0
    if strategy == "ssh":
        deploy_ssh()
        return 0
    if strategy == "ftp":
        deploy_ftp()
        return 0
    if strategy != "auto":
        raise SystemExit(f"Unknown AQ26_DEPLOY_STRATEGY: {strategy}")

    try:
        print("Deploy strategy auto: trying SSH first.")
        deploy_ssh()
        return 0
    except Exception as exc:
        print(f"SSH deploy failed: {exc}", file=sys.stderr)
        print("Trying FTP fallback.")
        deploy_ftp()
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
