#!/usr/bin/env python3
"""Deploy clean AQ26 site folders to Hostinger and remove stale unsafe web-root material.

Requires sshpass in the GitHub runner.
"""
from __future__ import annotations
import argparse, crypt, os, shlex, subprocess, sys, tarfile, tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def env_first(*names, default=''):
    for n in names:
        v=os.environ.get(n)
        if v and str(v).strip(): return str(v).strip()
    return default

def run(cmd, *, env=None):
    print('+', ' '.join(shlex.quote(str(c)) for c in cmd))
    return subprocess.run(cmd, check=True, env=env)

def clean_host(v):
    v=(v or '').strip()
    for p in ['https://','http://','ssh://','sftp://']:
        if v.startswith(p): v=v[len(p):]
    return v.split('/')[0].strip()

def clean_remote(v):
    v=(v or '').strip().rstrip('/')
    return v or 'domains/sccairquality.com/public_html'

def make_tar(src: Path, dest: Path):
    with tarfile.open(dest, 'w:gz') as tar:
        for p in src.rglob('*'):
            if p.is_file():
                rel=p.relative_to(src)
                if rel.name == '.htpasswd':
                    continue
                tar.add(p, arcname=str(rel))

def ssh_base(host, port, user, password):
    env=os.environ.copy(); env['SSHPASS']=password
    opts=['-p',str(port),'-o','StrictHostKeyChecking=no','-o','UserKnownHostsFile=/dev/null','-o','ConnectTimeout=35','-o','ServerAliveInterval=10','-o','ServerAliveCountMax=3']
    return env, opts, f'{user}@{host}'

def upload_tar(tar_path: Path, remote_dir: str, label: str, host, port, user, password, clean_public=False):
    env, opts, target=ssh_base(host, port, user, password)
    remote_tmp=f'/tmp/aq26_{label}.tgz'
    scp_opts=['-P',str(port),'-o','StrictHostKeyChecking=no','-o','UserKnownHostsFile=/dev/null','-o','ConnectTimeout=35']
    run(['sshpass','-e','ssh',*opts,target,f'mkdir -p {shlex.quote(remote_dir)}'], env=env)
    run(['sshpass','-e','scp',*scp_opts,str(tar_path),f'{target}:{remote_tmp}'], env=env)
    if clean_public:
        # Clean only the AQ26 site target. Preserve server-created logs and parent folders, but remove unsafe stale site output.
        clean_cmd=(
            f"set -e; mkdir -p {shlex.quote(remote_dir)}; "
            f"find {shlex.quote(remote_dir)} -mindepth 1 -maxdepth 1 "
            f"! -name '.well-known' ! -name 'unredacted' -exec rm -rf {{}} +; "
            f"rm -rf {shlex.quote(remote_dir)}/git-test {shlex.quote(remote_dir)}/.git {shlex.quote(remote_dir)}/test; "
            f"tar -xzf {remote_tmp} -C {shlex.quote(remote_dir)}; rm -f {remote_tmp}; "
            f"find {shlex.quote(remote_dir)} -maxdepth 2 -type f | wc -l"
        )
    else:
        clean_cmd=(
            f"set -e; mkdir -p {shlex.quote(remote_dir)}; "
            f"find {shlex.quote(remote_dir)} -mindepth 1 -maxdepth 1 ! -name '.htaccess' -exec rm -rf {{}} +; "
            f"tar -xzf {remote_tmp} -C {shlex.quote(remote_dir)}; rm -f {remote_tmp}; "
            f"find {shlex.quote(remote_dir)} -maxdepth 2 -type f | wc -l"
        )
    run(['sshpass','-e','ssh',*opts,target,clean_cmd], env=env)

def install_unredacted_auth(remote_public: str, host, port, user, password, unredacted_password: str, auth_user: str):
    if not unredacted_password:
        print('SCC_UNREDACTED_PASSWORD not set; preserving/generated .htaccess but not changing remote .htpasswd.')
        return
    env, opts, target=ssh_base(host, port, user, password)
    auth_dir='/home/u288464186/.aq26_auth'
    htpasswd=auth_dir+'/.htpasswd'
    # crypt.mksalt is available on ubuntu. apr1 is not guaranteed; sha512 works with Apache mod_authn_file on Hostinger in most setups.
    hashed=crypt.crypt(unredacted_password, crypt.mksalt(crypt.METHOD_SHA512))
    local=Path(tempfile.mkdtemp())/'.htpasswd'
    local.write_text(f'{auth_user}:{hashed}\n', encoding='utf-8')
    scp_opts=['-P',str(port),'-o','StrictHostKeyChecking=no','-o','UserKnownHostsFile=/dev/null']
    run(['sshpass','-e','ssh',*opts,target,f'mkdir -p {auth_dir} && chmod 700 {auth_dir}'], env=env)
    run(['sshpass','-e','scp',*scp_opts,str(local),f'{target}:{htpasswd}'], env=env)
    run(['sshpass','-e','ssh',*opts,target,f'chmod 600 {htpasswd}'], env=env)
    htaccess=f'''AuthType Basic\nAuthName "AQ26 Protected Evidence"\nAuthBasicProvider file\nAuthUserFile {htpasswd}\nRequire valid-user\nOptions -Indexes\n<FilesMatch "^\\.ht">\n  Require all denied\n</FilesMatch>\nHeader set X-Robots-Tag "noindex, nofollow, noarchive"\n'''
    tmp=Path(tempfile.mkdtemp())/'.htaccess'
    tmp.write_text(htaccess, encoding='utf-8')
    remote_unred=remote_public.rstrip('/')+'/unredacted'
    run(['sshpass','-e','scp',*scp_opts,str(tmp),f'{target}:{remote_unred}/.htaccess'], env=env)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--dry-run', nargs='?', const='true', default='false')
    args=ap.parse_args()
    dry=str(args.dry_run).lower() in {'1','true','yes','y'}
    host=clean_host(env_first('SCCAIRQUALITY_SSH_HOST','HOSTINGER_SSH_HOST'))
    port=env_first('SCCAIRQUALITY_SSH_PORT','HOSTINGER_SSH_PORT', default='65002')
    user=env_first('SCCAIRQUALITY_SSH_USERNAME','HOSTINGER_SSH_USERNAME')
    password=env_first('SCCAIRQUALITY_SSH_PASSWORD','HOSTINGER_SSH_PASSWORD')
    public_dir=clean_remote(env_first('AIRQUALITY_HOSTINGER_PUBLIC_HTML_DIR','HOSTINGER_PUBLIC_HTML_DIR', default='domains/sccairquality.com/public_html'))
    unred_pass=env_first('SCC_UNREDACTED_PASSWORD','AQ26_UNREDACTED_PASSWORD')
    auth_user=env_first('SCC_UNREDACTED_USERNAME','AQ26_UNREDACTED_USERNAME', default='aq26')
    missing=[name for name,val in [('SCCAIRQUALITY_SSH_HOST',host),('SCCAIRQUALITY_SSH_USERNAME',user),('SCCAIRQUALITY_SSH_PASSWORD',password),('AIRQUALITY_HOSTINGER_PUBLIC_HTML_DIR',public_dir)] if not val]
    if missing:
        raise SystemExit('Missing required secrets/env: '+', '.join(missing))
    print('AQ26 canonical deploy settings:')
    print(f'  host present: {bool(host)}')
    print(f'  port: {port}')
    print(f'  username present: {bool(user)}')
    print(f'  public_html: {public_dir}')
    print(f'  unredacted password present: {bool(unred_pass)}')
    print(f'  dry_run: {dry}')
    if dry:
        print('Dry run only; not uploading.')
        return 0
    with tempfile.TemporaryDirectory() as td:
        td=Path(td)
        pub=td/'public.tgz'; unr=td/'unredacted.tgz'
        make_tar(ROOT/'site_public', pub)
        make_tar(ROOT/'site_unredacted', unr)
        upload_tar(pub, public_dir, 'public', host, port, user, password, clean_public=True)
        upload_tar(unr, public_dir.rstrip('/')+'/unredacted', 'unredacted', host, port, user, password, clean_public=False)
        install_unredacted_auth(public_dir, host, port, user, password, unred_pass, auth_user)
    print('AQ26 canonical deployment complete.')
    return 0
if __name__ == '__main__':
    sys.exit(main())
