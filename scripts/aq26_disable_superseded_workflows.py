#!/usr/bin/env python3
from __future__ import annotations
import shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; WF=ROOT/'.github'/'workflows'; DISABLED=ROOT/'.github'/'workflows_disabled'
KEEP={'aq26-canonical-site-deploy.yml','aq26-weekly-production.yml','aq26_weekly_v2.yml','aq26-hostinger-ssh-preflight.yml','aq26-retire-superseded-workflows.yml','README_AQ26_ACTIVE_WORKFLOW_MAP.md'}
def main():
    DISABLED.mkdir(parents=True,exist_ok=True); moved=[]
    for p in sorted(WF.glob('*.yml')):
        if p.name in KEEP: continue
        dest=DISABLED/(p.name+'.disabled'); shutil.move(str(p),str(dest)); moved.append((str(p.relative_to(ROOT)),str(dest.relative_to(ROOT))))
    report=ROOT/'outputs'/'AQ26_DISABLED_WORKFLOWS.txt'; report.parent.mkdir(parents=True,exist_ok=True); report.write_text('\n'.join(f'{a} -> {b}' for a,b in moved) or 'No workflows moved.\n',encoding='utf-8')
    print(f'Moved {len(moved)} superseded workflows. Report: {report}'); return 0
if __name__=='__main__': raise SystemExit(main())
