#!/usr/bin/env python3
"""Deploy clean AQ26 site folders to Hostinger.

The deployment fails if the public root is not populated after extraction. This
prevents a misleading green Action when the wrong Hostinger directory is used.
"""
from __future__ import annotations

import argparse
import crypt
import os
import shlex
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def env_first(*names: str, default: str = "") -> str:
    for name in names:
        value = os.environ.get(name)
        if value and str(value).strip():
            return str(value).strip()
    return default


def run(cmd: list[str], *, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    print("+", " ".join(shlex.quote(str(c)) for c in cmd), flush=True)
    return subprocess.run(cmd, check=True, env=env, text=True)


def clean_host(value: str) -> str:
    value = (value or "").strip()
    for prefix in ["https://", "http://", "ssh://", "sftp://"]:
        if value.startswith(prefix):
            value = value[len(prefix):]
    return value.split("/")[0].strip()


def clean_remote(value: str) -> str:
    value = (value or "").strip().rstrip("/")
    return value or "domains/sccairquality.com/public_html"


def make_tar(src: Path, dest: Path) -> None:
    if not src.exists():
        raise SystemExit(f"Missing build folder: {src}")
    with tarfile.open(dest, "w:gz") as tar:
        added = 0
        for p in src.rglob("*"):
            if p.is_file():
                rel = p.relative_to(src)
                if rel.name in {".htpasswd", ".env"}:
                    continue
                tar.add(p, arcname=str(rel))
                added += 1
    if added == 0:
        raise SystemExit(f"Refusing to deploy empty tar from {src}")
    print(f"Packed {added} files from {src}", flush=True)


def ssh_base(host: str, port: str, user: str, password: str):
    env = os.environ.copy()
    env["SSHPASS"] = password
    opts = ["-p", str(port), "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null", "-o", "ConnectTimeout=35", "-o", "ServerAliveInterval=10", "-o", "ServerAliveCountMax=3"]
    return env, opts, f"{user}@{host}"


def upload_tar(tar_path: Path, remote_dir: str, label: str, host: str, port: str, user: str, password: str, *, clean_public: bool = False, min_files: int = 1) -> None:
    env, opts, target = ssh_base(host, port, user, password)
    remote_tmp = f"/tmp/aq26_{label}.tgz"
    scp_opts = ["-P", str(port), "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null", "-o", "ConnectTimeout=35"]
    run(["sshpass", "-e", "ssh", *opts, target, f"mkdir -p {shlex.quote(remote_dir)}"], env=env)
    run(["sshpass", "-e", "scp", *scp_opts, str(tar_path), f"{target}:{remote_tmp}"], env=env)
    if clean_public:
        clean_cmd = (
            f"set -e; mkdir -p {shlex.quote(remote_dir)}; "
            f"find {shlex.quote(remote_dir)} -mindepth 1 -maxdepth 1 ! -name '.well-known' ! -name 'unredacted' -exec rm -rf {{}} +; "
            f"rm -rf {shlex.quote(remote_dir)}/git-test {shlex.quote(remote_dir)}/.git {shlex.quote(remote_dir)}/test; "
            f"rm -f {shlex.quote(remote_dir)}/downloads/AQ26_WEEKLY_EVIDENCE_BUNDLE.zip {shlex.quote(remote_dir)}/downloads/latest-evidence.zip; "
            f"tar -xzf {remote_tmp} -C {shlex.quote(remote_dir)}; rm -f {remote_tmp}; "
            f"count=$(find {shlex.quote(remote_dir)} -maxdepth 2 -type f | wc -l); echo AQ26_PUBLIC_FILE_COUNT=$count; "
            f"test $count -ge {int(min_files)}; test -f {shlex.quote(remote_dir)}/index.html; test -f {shlex.quote(remote_dir)}/sitemap.xml; test -f {shlex.quote(remote_dir)}/assets/aq26-logo.svg"
        )
    else:
        clean_cmd = (
            f"set -e; mkdir -p {shlex.quote(remote_dir)}; "
            f"find {shlex.quote(remote_dir)} -mindepth 1 -maxdepth 1 ! -name '.htaccess' -exec rm -rf {{}} +; "
            f"rm -f {shlex.quote(remote_dir)}/.htpasswd; "
            f"tar -xzf {remote_tmp} -C {shlex.quote(remote_dir)}; rm -f {remote_tmp}; "
            f"count=$(find {shlex.quote(remote_dir)} -maxdepth 2 -type f | wc -l); echo AQ26_UNREDACTED_FILE_COUNT=$count; "
            f"test $count -ge {int(min_files)}; test -f {shlex.quote(remote_dir)}/index.html"
        )
    run(["sshpass", "-e", "ssh", *opts, target, clean_cmd], env=env)


def install_unredacted_auth(remote_public: str, host: str, port: str, user: str, password: str, unredacted_password: str, auth_user: str) -> None:
    if not unredacted_password:
        print("SCC_UNREDACTED_PASSWORD not set; preserving .htaccess but not changing remote .htpasswd.", flush=True)
        return
    env, opts, target = ssh_base(host, port, user, password)
    auth_dir = "/home/u288464186/.aq26_auth"
    htpasswd = auth_dir + "/.htpasswd"
    hashed = crypt.crypt(unredacted_password, crypt.mksalt(crypt.METHOD_SHA512))
    local = Path(tempfile.mkdtemp()) / ".htpasswd"
    local.write_text(f"{auth_user}:{hashed}\n", encoding="utf-8")
    scp_opts = ["-P", str(port), "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null"]
    run(["sshpass", "-e", "ssh", *opts, target, f"mkdir -p {auth_dir} && chmod 700 {auth_dir}"], env=env)
    run(["sshpass", "-e", "scp", *scp_opts, str(local), f"{target}:{htpasswd}"], env=env)
    run(["sshpass", "-e", "ssh", *opts, target, f"chmod 600 {htpasswd}"], env=env)
    htaccess = f'''AuthType Basic
AuthName "AQ26 Protected Evidence"
AuthBasicProvider file
AuthUserFile {htpasswd}
Require valid-user
Options -Indexes
<FilesMatch "^\\.ht">
  Require all denied
</FilesMatch>
Header set X-Robots-Tag "noindex, nofollow, noarchive"
'''
    tmp = Path(tempfile.mkdtemp()) / ".htaccess"
    tmp.write_text(htaccess, encoding="utf-8")
    remote_unredacted = remote_public.rstrip("/") + "/unredacted"
    run(["sshpass", "-e", "scp", *scp_opts, str(tmp), f"{target}:{remote_unredacted}/.htaccess"], env=env)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", nargs="?", const="true", default="false")
    args = ap.parse_args()
    dry = str(args.dry_run).lower() in {"1", "true", "yes", "y"}
    host = clean_host(env_first("SCCAIRQUALITY_SSH_HOST", "HOSTINGER_SSH_HOST"))
    port = env_first("SCCAIRQUALITY_SSH_PORT", "HOSTINGER_SSH_PORT", default="65002")
    user = env_first("SCCAIRQUALITY_SSH_USERNAME", "HOSTINGER_SSH_USERNAME")
    password = env_first("SCCAIRQUALITY_SSH_PASSWORD", "HOSTINGER_SSH_PASSWORD")
    public_dir = clean_remote(env_first("AIRQUALITY_HOSTINGER_PUBLIC_HTML_DIR", "HOSTINGER_PUBLIC_HTML_DIR", default="domains/sccairquality.com/public_html"))
    unred_pass = env_first("SCC_UNREDACTED_PASSWORD", "AQ26_UNREDACTED_PASSWORD")
    auth_user = env_first("SCC_UNREDACTED_USERNAME", "AQ26_UNREDACTED_USERNAME", default="aq26")
    missing = [name for name, val in [("SCCAIRQUALITY_SSH_HOST", host), ("SCCAIRQUALITY_SSH_USERNAME", user), ("SCCAIRQUALITY_SSH_PASSWORD", password), ("AIRQUALITY_HOSTINGER_PUBLIC_HTML_DIR", public_dir)] if not val]
    if missing:
        raise SystemExit("Missing required secrets/env: " + ", ".join(missing))
    print("AQ26 canonical deploy settings:", flush=True)
    print(f"  host present: {bool(host)}", flush=True)
    print(f"  port: {port}", flush=True)
    print(f"  username present: {bool(user)}", flush=True)
    print(f"  public_html: {public_dir}", flush=True)
    print(f"  unredacted password present: {bool(unred_pass)}", flush=True)
    print(f"  dry_run: {dry}", flush=True)
    if dry:
        print("Dry run only; not uploading.", flush=True)
        return 0
    with tempfile.TemporaryDirectory() as td:
        temp = Path(td)
        pub = temp / "public.tgz"
        unr = temp / "unredacted.tgz"
        make_tar(ROOT / "site_public", pub)
        make_tar(ROOT / "site_unredacted", unr)
        upload_tar(pub, public_dir, "public", host, port, user, password, clean_public=True, min_files=25)
        upload_tar(unr, public_dir.rstrip("/") + "/unredacted", "unredacted", host, port, user, password, clean_public=False, min_files=10)
        install_unredacted_auth(public_dir, host, port, user, password, unred_pass, auth_user)
    print("AQ26 canonical deployment complete.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
