#!/usr/bin/env python3
from __future__ import annotations
import argparse, ast, csv, hashlib, json, re, subprocess
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

CRITICAL_PATHS = [re.compile(r"(^|/)\.htpasswd$"), re.compile(r"AirQuality\.env$"), re.compile(r"(^|/)\.env$")]
SECRET_TEXT = [re.compile(r"AKIA[0-9A-Z]{16}"), re.compile(r"-----BEGIN (RSA|OPENSSH|EC|DSA) PRIVATE KEY-----"), re.compile(r"(PASSWORD|SECRET|TOKEN|API_KEY)\s*=\s*['\"][^'\"]{12,}", re.I)]
PUBLIC_LEAK = [re.compile(r"/home/runner/work/"), re.compile(r"SCCNEXUS_SSH_PASSWORD|SCC_UNREDACTED_PASSWORD|GDRIVE_SERVICE_ACCOUNT"), re.compile(r"\.htpasswd")]
REQUIRED = [
 '.github/workflows/aq26_operational_dual_site.yml', '.github/workflows/aq26_weekly_monday_backfill_alerts.yml',
 'scripts/aq26_build_operational_dual_site.py', 'scripts/aq26_build_weekly_alert_pages.py', 'scripts/aq26_apply_webm_banners.py',
 'website/assets/air_quality_web.svg', 'website/assets/logo_web.svg', 'website/assets/favicon.svg',
 'site_public/data/focus/overlays_v3/facility_overlay_status.csv', 'site_public/data/focus/overlays_v3/incinerator_overlay_summary.json']
PUBLIC_PAGES = ['index.html','incinerators.html','overlays.html','comparisons.html','methodology.html','downloads.html','weekly-update.html']
UNREDACTED_PAGES = ['index.html','evidence.html','candidates.html','diagnostics.html','weekly-update.html']

def now(): return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
def rel(repo,p): return p.relative_to(repo).as_posix()
def issue(issues,severity,code,path,msg,rec=''):
    issues.append({'severity':severity,'code':code,'path':path,'message':msg,'recommendation':rec})
def files(repo):
    for p in repo.rglob('*'):
        if '.git' in p.parts or '__pycache__' in p.parts: continue
        if p.is_file(): yield p

def run_git(repo,args):
    try:
        p=subprocess.run(['git',*args],cwd=repo,text=True,capture_output=True,timeout=30)
        return p.returncode,(p.stdout+p.stderr).strip()
    except Exception as e: return 999,str(e)

def check_yaml(repo,issues):
    try: import yaml
    except Exception:
        issue(issues,'warning','pyyaml_missing','requirements','PyYAML missing; workflow syntax check skipped','Install pyyaml in audit workflow')
        return
    for p in sorted((repo/'.github/workflows').glob('*.yml'))+sorted((repo/'.github/workflows').glob('*.yaml')):
        try: yaml.safe_load(p.read_text(encoding='utf-8'))
        except Exception as e: issue(issues,'critical','workflow_yaml_invalid',rel(repo,p),str(e),'Fix YAML before running Actions')

def check_python(repo,issues):
    for p in sorted((repo/'scripts').glob('*.py')):
        try: ast.parse(p.read_text(encoding='utf-8'))
        except Exception as e: issue(issues,'critical','python_syntax_invalid',rel(repo,p),str(e),'Fix script syntax')

def check_required(repo,issues):
    for f in REQUIRED:
        if not (repo/f).exists(): issue(issues,'error','required_file_missing',f,'Expected AQ26 operational file missing','Restore/apply patch before running')
    for f in PUBLIC_PAGES:
        p=repo/'site_public'/f
        if not p.exists() or p.stat().st_size<500: issue(issues,'warning','public_page_missing_or_small',str(p.relative_to(repo)),'Public page missing/small','Rebuild site')
    for f in UNREDACTED_PAGES:
        p=repo/'site_unredacted'/f
        if not p.exists() or p.stat().st_size<500: issue(issues,'warning','unredacted_page_missing_or_small',str(p.relative_to(repo)),'Unredacted page missing/small','Rebuild site')

def check_security(repo,issues):
    rc,out=run_git(repo,['ls-files'])
    if rc==0:
        for line in out.splitlines():
            if any(rx.search(line) for rx in CRITICAL_PATHS): issue(issues,'critical','sensitive_file_tracked',line,'Sensitive auth/env file is tracked by git','Remove from tracking; rotate exposed secret/password')
    for p in files(repo):
        r=rel(repo,p)
        if any(rx.search(r) for rx in CRITICAL_PATHS): issue(issues,'critical','sensitive_file_present',r,'Sensitive auth/env file present in working tree','Do not commit; generate only at deploy time')
        if p.suffix.lower() in {'.py','.yml','.yaml','.json','.html','.txt','.md','.env'} and p.stat().st_size<2_000_000:
            txt=p.read_text(encoding='utf-8',errors='ignore')
            if any(rx.search(txt) for rx in SECRET_TEXT): issue(issues,'critical','possible_secret_literal',r,'Possible secret/private key literal found','Remove and rotate if real')

def check_workflows(repo,issues):
    for p in (repo/'.github/workflows').glob('*.yml'):
        txt=p.read_text(encoding='utf-8',errors='ignore'); r=rel(repo,p)
        if 'site_unredacted' in txt and 'git add site_public site_unredacted' in txt and '.htpasswd' in txt:
            issue(issues,'critical','workflow_may_commit_htpasswd',r,'Workflow creates .htpasswd and git-adds site_unredacted','Create .htpasswd after commit or explicitly reset/ignore it')
        if 'rsync -avz --delete' in txt and 'site_public/' in txt and "--exclude" not in txt:
            issue(issues,'warning','public_rsync_delete_without_exclude',r,'Public rsync --delete may wipe protected folders','Add --exclude unredacted/***')

def check_html_assets(repo,issues):
    for site_name in ['site_public','site_unredacted']:
        site=repo/site_name
        if not site.exists(): continue
        for p in site.glob('*.html'):
            txt=p.read_text(encoding='utf-8',errors='ignore'); r=rel(repo,p)
            if 'assets/air_quality_web.svg' not in txt: issue(issues,'warning','header_logo_not_referenced',r,'Full header logo not referenced','Run brand/header enforcement')
            if 'favicon.svg' not in txt: issue(issues,'warning','favicon_not_referenced',r,'Favicon not referenced','Run favicon enforcement')
            if p.name in ['index.html','weekly-update.html'] and 'aq26-video-banner' not in txt: issue(issues,'warning','moving_banner_missing',r,'Moving banner container missing','Apply WEBM banners after build')
            if site_name=='site_public':
                for rx in PUBLIC_LEAK:
                    if rx.search(txt): issue(issues,'error','public_leak_pattern',r,f'Public page contains internal marker: {rx.pattern}','Move raw/internal diagnostics to unredacted only')

def check_assets(repo,issues):
    for n in range(1,7):
        p=repo/f'website/assets/banners/desktop_banner_{n}.webm'
        if not p.exists(): issue(issues,'warning','canonical_banner_missing',str(p.relative_to(repo)),'Expected WEBM banner missing','Add/copy uploaded banner assets')
    logo=repo/'website/assets/logo_web.svg'; fav=repo/'website/assets/favicon.svg'
    if logo.exists() and fav.exists() and hashlib.sha256(logo.read_bytes()).hexdigest()!=hashlib.sha256(fav.read_bytes()).hexdigest():
        issue(issues,'warning','favicon_not_logo_web','website/assets/favicon.svg','Canonical favicon differs from logo_web.svg','If attached logo_web.svg is intended favicon, copy it to favicon.svg')
    for site_name in ['site_public','site_unredacted']:
        for f in ['favicon.svg','assets/favicon.svg','assets/logo_web.svg','assets/air_quality_web.svg']:
            if not (repo/site_name/f).exists(): issue(issues,'warning','brand_asset_missing',f'{site_name}/{f}','Expected brand asset missing','Run brand/favicon enforcement')

def check_size_dupes(repo,issues):
    hashes=defaultdict(list)
    for p in files(repo):
        r=rel(repo,p); size=p.stat().st_size
        if size>20_000_000: issue(issues,'warning','large_file',r,f'Large file: {size/1024/1024:.1f} MB','Use artifacts/LFS/Drive for large generated outputs')
        if size<5_000_000 and p.suffix.lower() in {'.svg','.css','.js','.html','.json','.csv'}:
            try: hashes[hashlib.sha256(p.read_bytes()).hexdigest()].append(r)
            except Exception: pass
    for h,paths in hashes.items():
        if len(paths)>=4: issue(issues,'info','duplicate_content',paths[0],f'Same content appears in {len(paths)} files','Consider canonical source + build copy')

def write(repo,outdir,issues,fail):
    outdir.mkdir(parents=True,exist_ok=True); counts=Counter(i['severity'] for i in issues)
    summary={'generated_utc':now(),'ok':counts.get('critical',0)==0 and counts.get('error',0)==0,'counts':dict(counts),'issue_count':len(issues)}
    (outdir/'repo_housekeeping_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    (outdir/'repo_housekeeping_issues.json').write_text(json.dumps(issues,indent=2),encoding='utf-8')
    with (outdir/'repo_housekeeping_issues.csv').open('w',encoding='utf-8',newline='') as f:
        fields=['severity','code','path','message','recommendation']; w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(issues)
    md=['# AQ26 Repository Housekeeping Audit','',f"Generated: `{summary['generated_utc']}`",'', '| Severity | Count |','|---|---:|']
    for sev in ['critical','error','warning','info']: md.append(f'| {sev} | {counts.get(sev,0)} |')
    md+=['','## Issues','']
    for i in issues:
        md += [f"### {i['severity'].upper()} · {i['code']}", f"- Path: `{i['path']}`", f"- Observation: {i['message']}"]
        if i.get('recommendation'): md.append(f"- Recommendation: {i['recommendation']}")
        md.append('')
    (outdir/'repo_housekeeping_report.md').write_text('\n'.join(md),encoding='utf-8')
    print(json.dumps(summary,indent=2))
    return 2 if fail and counts.get('critical',0) else 0

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--repo-root',default='.'); ap.add_argument('--output-dir',default='outputs/housekeeping'); ap.add_argument('--fail-on-critical',action='store_true'); args=ap.parse_args()
    repo=Path(args.repo_root).resolve(); issues=[]
    check_required(repo,issues); check_yaml(repo,issues); check_python(repo,issues); check_security(repo,issues); check_workflows(repo,issues); check_html_assets(repo,issues); check_assets(repo,issues); check_size_dupes(repo,issues)
    return write(repo,repo/args.output_dir,issues,args.fail_on_critical)
if __name__=='__main__': raise SystemExit(main())
