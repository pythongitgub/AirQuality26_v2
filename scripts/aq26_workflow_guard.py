#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--mode', choices=['warn','fail'], default='warn')
    ap.add_argument('--allowed', nargs='*', default=['weekly-production.yml'])
    args = ap.parse_args()
    wf_dir = Path('.github/workflows')
    active = sorted(p.name for p in wf_dir.glob('*.yml')) + sorted(p.name for p in wf_dir.glob('*.yaml'))
    allowed = set(args.allowed)
    extras = [x for x in active if x not in allowed]
    payload = {'active_workflows': active, 'allowed': sorted(allowed), 'extra_active_workflows': extras}
    print(json.dumps(payload, indent=2))
    if extras and args.mode == 'fail':
        print('Extra active workflows found. Disable or move them before production.', file=sys.stderr)
        return 1
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
