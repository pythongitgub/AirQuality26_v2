#!/usr/bin/env python3
"""Deploy AQ26 public and unredacted static sites to Hostinger over SSH.
Uses tar over ssh so it does not require rsync on Hostinger.
Secrets/environment:
  SCCAIRQUALITY_SSH_HOST, SCCAIRQUALITY_SSH_PORT, SCCAIRQUALITY_SSH_USERNAME, SCCAIRQUALITY_SSH_PASSWORD
  AIRQUALITY_HOSTINGER_PUBLIC_HTML_DIR
  AIRQUALITY_HOSTINGER_PUBLIC_UNREDACTED_DIR
"""
from pathlib import Path
import os, subprocess, sys, tarfile, tempfile, shlex
ROOT=Path(__file__).resolve().parents[1]

def env(name, default=None):
    v=os.environ.get(name, default)
    if not v:
        print(f'Missing required env/secret: {name}', file=sys.stderr); sys.exit(2)
    return v
HOST=env('SCCAIRQUALITY_SSH_HOST'); PORT=env('SCCAIRQUALITY_SSH_PORT','65002'); USER=env('SCCAIRQUALITY_SSH_USERNAME'); PASS=env('SCCAIRQUALITY_SSH_PASSWORD')
PUBLIC_DIR=env('AIRQUALITY_HOSTINGER_PUBLIC_HTML_DIR'); UNRED_DIR=env('AIRQUALITY_HOSTINGER_PUBLIC_UNREDACTED_DIR')

def run(cmd, **kw):
    print('+', ' '.join(shlex.quote(str(c)) for c in cmd)); return subprocess.run(cmd, check=True, **kw)

def make_tar(src, dest, exclude_auth=False):
    with tarfile.open(dest,'w:gz') as tar:
        for p in Path(src).rglob('*'):
            if p.is_file():
                rel=p.relative_to(src)
                if exclude_auth and rel.name in ('.htaccess','.htpasswd'): continue
                tar.add(p, arcname=str(rel))

def upload(local_tar, remote_dir, label):
    base=f'{USER}@{HOST}'
    remote_tmp=f'/tmp/aq26_{label}.tgz'
    ssh_opts=['-p',PORT,'-o','StrictHostKeyChecking=no','-o','UserKnownHostsFile=/dev/null','-o','ConnectTimeout=30']
    scp_opts=['-P',PORT,'-o','StrictHostKeyChecking=no','-o','UserKnownHostsFile=/dev/null']
    envp=os.environ.copy(); envp['SSHPASS']=PASS
    run(['sshpass','-e','ssh',*ssh_opts,base,f"mkdir -p {shlex.quote(remote_dir)}"], env=envp)
    run(['sshpass','-e','scp',*scp_opts,str(local_tar),f'{base}:{remote_tmp}'], env=envp)
    # Extract without deleting .htaccess/.htpasswd. This overwrites site files but preserves auth.
    cmd=f"set -e; mkdir -p {shlex.quote(remote_dir)}; tar -xzf {remote_tmp} -C {shlex.quote(remote_dir)}; rm -f {remote_tmp}; find {shlex.quote(remote_dir)} -maxdepth 1 -type f | wc -l"
    run(['sshpass','-e','ssh',*ssh_opts,base,cmd], env=envp)

with tempfile.TemporaryDirectory() as td:
    td=Path(td); pub=td/'public.tgz'; unr=td/'unredacted.tgz'
    make_tar(ROOT/'site_public', pub)
    make_tar(ROOT/'site_unredacted', unr, exclude_auth=True)
    upload(pub, PUBLIC_DIR, 'public')
    upload(unr, UNRED_DIR, 'unredacted')
print('AQ26 deployment complete.')
