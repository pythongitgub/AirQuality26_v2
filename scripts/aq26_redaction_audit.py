#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, re, os
from pathlib import Path
PATTERNS = [
    re.compile(rb'(?i)(api[_-]?key|apikey|token|password|client_secret|secret)=([A-Za-z0-9_\-\.]{8,})'),
    re.compile(rb'(?i)bearer\s+[A-Za-z0-9_\-\.]{12,}'),
    re.compile(rb'(?i)authorization["\']?\s*[:=]\s*["\']?[A-Za-z0-9_\-\.]{12,}'),
]
ALLOW = [b'***REDACTED', b'SET_REDACTED', b'EMPTY']
TEXT_EXT = {'.json','.jsonl','.csv','.txt','.md','.html','.xml','.yml','.yaml','.log'}

def scan_file(p: Path):
    try: data=p.read_bytes()[:5_000_000]
    except Exception: return []
    hits=[]
    for pat in PATTERNS:
        for m in pat.finditer(data):
            ctx=data[max(0,m.start()-40):m.end()+40]
            if any(a in ctx for a in ALLOW): continue
            hits.append({'path':str(p),'offset':m.start(),'match_preview':ctx[:160].decode('utf-8','replace')})
    return hits

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--root',default='outputs'); ap.add_argument('--fail-on-leak',default='true')
    args=ap.parse_args(); root=Path(args.root); leaks=[]; files=0
    if root.exists():
        for p in root.rglob('*'):
            if p.is_file() and (p.suffix.lower() in TEXT_EXT or p.stat().st_size < 2_000_000):
                files+=1; leaks.extend(scan_file(p))
    out=root/'99_integrity'/'redaction_audit.json'; out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({'root':str(root),'files_scanned':files,'leak_count':len(leaks),'leaks':leaks[:200]}, indent=2), encoding='utf-8')
    print(out.read_text())
    if leaks and str(args.fail_on_leak).lower()=='true':
        raise SystemExit('Redaction audit failed: possible secret material detected in outputs')
if __name__=='__main__': main()
