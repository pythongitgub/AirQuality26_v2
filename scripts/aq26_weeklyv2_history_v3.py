
#!/usr/bin/env python3
"""
AQ26 WeeklyV2 Historical Backfill + Interactive Site Data V3

Purpose
- Canonicalise weekly_index.json so each date window has exactly one public row.
- Run controlled historical backfill batches by calling the existing AQ26 weekly scripts when present.
- Build chart-specific JSON feeds for interactive Plotly charts.
- Validate JSON/CSV/site data before deployment.

This script is intentionally conservative: it does not invent historical evidence. Missing weeks stay
not_yet_harvested until a source-specific run produces real records or a source is explicitly marked unavailable.
"""
from __future__ import annotations

import argparse, csv, datetime as dt, hashlib, json, os, re, shutil, subprocess, sys, traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

UTC = dt.timezone.utc
STATUS_RANK = {
    'harvested': 100,
    'partial_harvest': 90,
    'failed_validation': 80,
    'source_not_historically_available': 70,
    'pending_source_specific_backfill': 60,
    'not_yet_harvested': 10,
    'unknown': 0,
}
REQUIRED_SOURCE_FIELDS = ['source_name','source_type','status','retrieved_at_utc','retrieved_at_uk','date_uk','output_path','sha256']


def now_utc() -> str:
    return dt.datetime.now(UTC).isoformat()


def parse_date(s: Any) -> Optional[dt.date]:
    if not s: return None
    if isinstance(s, dt.date): return s
    t = str(s).strip()
    if not t: return None
    for fmt in ('%Y-%m-%d','%d/%m/%Y'):
        try: return dt.datetime.strptime(t[:10], fmt).date()
        except Exception: pass
    try: return dt.datetime.fromisoformat(t.replace('Z','+00:00')).date()
    except Exception: return None


def iso_date(d: dt.date) -> str:
    return d.isoformat()


def sha256_file(p: Path) -> str:
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024), b''):
            h.update(b)
    return h.hexdigest()


def load_json(p: Path) -> Any:
    with p.open('r', encoding='utf-8') as f:
        return json.load(f)


def write_json(p: Path, data: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + '.tmp')
    with tmp.open('w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False, sort_keys=False)
        f.write('\n')
    tmp.replace(p)


def safe_int(x: Any) -> int:
    try:
        if x is None or x == '': return 0
        return int(float(x))
    except Exception:
        return 0


def normalise_window(obj: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    dw = obj.get('date_window') or {}
    s = dw.get('start') or obj.get('start') or obj.get('window_start') or obj.get('date_from')
    e = dw.get('end') or obj.get('end') or obj.get('window_end') or obj.get('date_to')
    sd, ed = parse_date(s), parse_date(e)
    return (iso_date(sd) if sd else None, iso_date(ed) if ed else None)


def infer_status(row: Dict[str, Any]) -> str:
    st = row.get('backfill_status') or row.get('status')
    if st: return str(st)
    if safe_int(row.get('source_record_count')) > 0: return 'harvested'
    return 'not_yet_harvested'


def normalise_summary(row: Dict[str, Any], source_path: Optional[Path]=None) -> Optional[Dict[str, Any]]:
    s,e = normalise_window(row)
    if not s or not e: return None
    out = dict(row)
    out['date_window'] = {'start': s, 'end': e}
    out['backfill_status'] = infer_status(out)
    for k in ['source_record_count','ok_count','warning_count','error_count','skipped_count','redaction_leak_count',
              'satellite_product_count','drive_file_count','drive_folder_count','high_priority_filings','medium_priority_filings',
              'openaq_request_count','news_warning_count']:
        out[k] = safe_int(out.get(k))
    for k in ['external_submission_ready','redaction_ready','metoffice_ready','ground_aq_ready','openaq_ready','openaq_safety_ready',
              'satellite_catalogue_ready','satellite_extraction_ready','drive_ready','drive_inventory_truncated','cams_key_present',
              'cams_endpoint_configured','cams_data_ready','cdse_download_ready','cdse_sentinelhub_ready','gemini_summary_ready']:
        if k in out: out[k] = bool(out[k])
    # Keep the public weekly index compact; detailed records belong in source_records_latest.json.
    out.pop('source_records', None)
    if source_path:
        out.setdefault('_source_summary_path', str(source_path.as_posix()))
    out.setdefault('run_ts', row.get('run_ts') or (source_path.stem if source_path else f'WINDOW_{s}_{e}'))
    return out


def discover_summary_rows(output_root: Path, site_root: Path) -> List[Dict[str, Any]]:
    candidates: List[Path] = []
    patterns = [
        output_root/'website_history'/'**'/'*.json',
        output_root/'00_weeklyv2'/'LATEST_WEEKLYV2.json',
        site_root/'data'/'history'/'*.json',
        site_root/'data'/'latest_summary.json',
        site_root/'data'/'weekly_index.json',
    ]
    for pat in patterns:
        candidates.extend(Path().glob(str(pat)) if not pat.is_absolute() else output_root.anchor and pat.parent.glob(pat.name) if '**' not in str(pat) else pat.parent.parent.glob('**/*.json'))
    # simpler robust glob collection
    candidates=[]
    for root in [output_root/'website_history', output_root/'00_weeklyv2', site_root/'data'/'history', site_root/'data']:
        if root.exists():
            if root.name == 'data':
                for name in ['latest_summary.json','weekly_index.json']:
                    p=root/name
                    if p.exists(): candidates.append(p)
            else:
                candidates.extend(root.rglob('*.json'))
    rows=[]
    seen=set()
    for p in candidates:
        if p in seen: continue
        seen.add(p)
        try:
            data=load_json(p)
            if isinstance(data, dict) and 'weeks' in data and isinstance(data['weeks'], list):
                for w in data['weeks']:
                    nw=normalise_summary(w, p)
                    if nw: rows.append(nw)
            elif isinstance(data, dict):
                nw=normalise_summary(data, p)
                if nw: rows.append(nw)
        except Exception as exc:
            print(f'[warn] cannot read summary {p}: {exc}', file=sys.stderr)
    return rows


def make_week_slots(end_date: dt.date, weeks: int) -> List[Dict[str, Any]]:
    slots=[]
    # Monday-ending weekly windows: start Monday, end next Monday (exclusive-ish, matches public archive style)
    # For display we store inclusive-ish end as current convention uses date range labels.
    end = end_date
    for i in range(weeks):
        e = end - dt.timedelta(days=7*i)
        s = e - dt.timedelta(days=7)
        slots.append({
            'run_ts': f'BACKFILL_SLOT_{s.isoformat()}_{e.isoformat()}',
            'date_window': {'start': s.isoformat(), 'end': e.isoformat()},
            'backfill_status': 'not_yet_harvested',
            'source_record_count': 0, 'ok_count': 0, 'warning_count': 0, 'error_count': 0,
            'satellite_product_count': 0, 'drive_file_count': 0,
            'high_priority_filings': 0, 'medium_priority_filings': 0,
            'external_submission_ready': False, 'final_zip_relpath': '',
            'history_slot_integrity': {
                'date_validated': True,
                'evidence_status': 'pending',
                'notes': 'Placeholder only. Real historical evidence records must be generated by controlled source-specific backfill before scientific use.'
            }
        })
    return slots


def score_row(row: Dict[str, Any]) -> Tuple[int, int, str]:
    st = infer_status(row)
    status_rank = STATUS_RANK.get(st, 0)
    records = safe_int(row.get('source_record_count'))
    created = str(row.get('created_at_utc') or row.get('run_ts') or '')
    # penalise placeholder if recordless harvested by mistake
    if st == 'harvested' and records <= 0:
        status_rank = 5
    richness = sum(safe_int(row.get(k)) for k in ['satellite_product_count','drive_file_count','high_priority_filings','medium_priority_filings','openaq_request_count'])
    return (status_rank, records, richness, created)


def canonical_weekly_index(rows: List[Dict[str, Any]], end_date: dt.date, weeks: int) -> Dict[str, Any]:
    all_rows = [normalise_summary(x) or x for x in make_week_slots(end_date, weeks)] + rows
    by_window: Dict[Tuple[str,str], Dict[str, Any]] = {}
    for r in all_rows:
        s,e = normalise_window(r)
        if not s or not e: continue
        key=(s,e)
        if key not in by_window or score_row(r) > score_row(by_window[key]):
            by_window[key] = r
    out=[]
    for key,r in by_window.items():
        rr = normalise_summary(r) or dict(r)
        st = infer_status(rr)
        if safe_int(rr.get('source_record_count')) > 0 and st in ('not_yet_harvested','pending_source_specific_backfill'):
            st = 'partial_harvest'
        rr['backfill_status'] = st
        out.append(rr)
    out.sort(key=lambda x: ((x.get('date_window') or {}).get('end',''), (x.get('date_window') or {}).get('start','')), reverse=True)
    return {'created_at_utc': now_utc(), 'canonical_policy': {'unique_by': ['date_window.start','date_window.end'], 'status_preference': STATUS_RANK}, 'weeks': out}


def build_chart_feeds(site_root: Path, weekly_index: Dict[str, Any], latest_summary: Optional[Dict[str, Any]]=None, source_records: Optional[Dict[str, Any]]=None) -> None:
    charts = site_root/'data'/'charts'
    charts.mkdir(parents=True, exist_ok=True)
    weeks = weekly_index.get('weeks', [])
    # Chronological order for charts.
    cw = sorted(weeks, key=lambda x: ((x.get('date_window') or {}).get('end',''), (x.get('date_window') or {}).get('start','')))
    labels = [(w.get('date_window') or {}).get('end') or w.get('run_ts','') for w in cw]
    write_json(charts/'weekly_record_counts.json', {
        'created_at_utc': now_utc(),
        'labels': labels,
        'series': {
            'source_records': [safe_int(w.get('source_record_count')) for w in cw],
            'ok': [safe_int(w.get('ok_count')) for w in cw],
            'warnings': [safe_int(w.get('warning_count')) for w in cw],
            'errors': [safe_int(w.get('error_count')) for w in cw],
        },
        'weeks': [{'start': (w.get('date_window') or {}).get('start'), 'end': (w.get('date_window') or {}).get('end'), 'status': infer_status(w)} for w in cw]
    })
    write_json(charts/'source_coverage_by_week.json', {
        'created_at_utc': now_utc(),
        'labels': labels,
        'series': {
            'satellite_products': [safe_int(w.get('satellite_product_count')) for w in cw],
            'drive_files': [safe_int(w.get('drive_file_count')) for w in cw],
            'high_priority_filings': [safe_int(w.get('high_priority_filings')) for w in cw],
            'medium_priority_filings': [safe_int(w.get('medium_priority_filings')) for w in cw],
            'openaq_requests': [safe_int(w.get('openaq_request_count')) for w in cw],
        }
    })
    write_json(charts/'readiness_trend.json', {
        'created_at_utc': now_utc(), 'labels': labels,
        'series': {
            'external_submission_ready': [1 if w.get('external_submission_ready') else 0 for w in cw],
            'redaction_ready': [1 if w.get('redaction_ready') else 0 for w in cw],
            'satellite_extraction_ready': [1 if w.get('satellite_extraction_ready') else 0 for w in cw],
            'cams_data_ready': [1 if w.get('cams_data_ready') else 0 for w in cw],
            'drive_inventory_not_truncated': [0 if w.get('drive_inventory_truncated') else 1 for w in cw],
        }
    })
    # Source class table from latest source records.
    records = []
    if isinstance(source_records, dict): records = source_records.get('records') or []
    class_counts: Dict[str, Dict[str,int]] = {}
    for r in records:
        typ = str(r.get('source_type') or 'unknown')
        class_counts.setdefault(typ, {'total':0,'ok':0,'warning':0,'error':0,'record_count':0})
        class_counts[typ]['total'] += 1
        st=str(r.get('status') or '').lower()
        if st in class_counts[typ]: class_counts[typ][st] += 1
        elif 'warn' in st: class_counts[typ]['warning'] += 1
        elif 'err' in st or 'fail' in st: class_counts[typ]['error'] += 1
        class_counts[typ]['record_count'] += safe_int(r.get('record_count'))
    write_json(charts/'source_class_summary_latest.json', {'created_at_utc': now_utc(), 'classes': class_counts})
    # Empty but valid placeholders for future high-value charts.
    for name in ['pollutant_timeseries.json','facility_control_comparison.json','official_filings.json','satellite_products_by_week.json']:
        p=charts/name
        if not p.exists():
            write_json(p, {'created_at_utc': now_utc(), 'status': 'awaiting_source_specific_backfill', 'records': []})


def read_help(script: Path) -> str:
    try:
        p=subprocess.run([sys.executable, str(script), '--help'], capture_output=True, text=True, timeout=45)
        return (p.stdout or '') + (p.stderr or '')
    except Exception:
        return ''


def supported_args(help_text: str, requested: Dict[str,str]) -> List[str]:
    args=[]
    for flag,val in requested.items():
        if flag in help_text:
            args += [flag, val]
    return args


def run_existing_pipeline_for_window(repo_root: Path, output_root: Path, site_root: Path, start: str, end: str, dry_run: bool=False) -> int:
    env=os.environ.copy()
    env.update({
        'AQ26_BACKFILL_MODE': 'true',
        'AQ26_HISTORY_START_DATE': start,
        'AQ26_HISTORY_END_DATE': end,
        'AQ26_WINDOW_START_DATE': start,
        'AQ26_WINDOW_END_DATE': end,
        'AQ26_RUN_DATE_FROM': start,
        'AQ26_RUN_DATE_TO': end,
    })
    scripts=repo_root/'scripts'
    collect=scripts/'aq26_weeklyv2_collect.py'
    build_report=scripts/'aq26_weeklyv2_build_report.py'
    build_site=scripts/'aq26_weeklyv2_build_sccnexus_site.py'
    cmds=[]
    if collect.exists():
        h=read_help(collect)
        flags=supported_args(h, {'--start-date':start,'--end-date':end,'--date-from':start,'--date-to':end,'--history-start-date':start,'--history-end-date':end,'--output-root':str(output_root)})
        cmds.append([sys.executable, str(collect)] + flags)
    if build_report.exists():
        h=read_help(build_report)
        flags=supported_args(h, {'--start-date':start,'--end-date':end,'--date-from':start,'--date-to':end,'--history-start-date':start,'--history-end-date':end,'--output-root':str(output_root)})
        cmds.append([sys.executable, str(build_report)] + flags)
    if build_site.exists():
        h=read_help(build_site)
        flags=supported_args(h, {'--output-root':str(output_root),'--site-root':str(site_root),'--history-end-date':end})
        # Do not pass unsupported args; this fixes the malformed workflow problem too.
        cmds.append([sys.executable, str(build_site)] + flags)
    if not cmds:
        print('[backfill] No existing AQ26 weekly scripts found; canonical/chart/validation steps only.')
        return 0
    for cmd in cmds:
        print('[backfill] RUN', ' '.join(map(str,cmd)))
        if dry_run: continue
        p=subprocess.run(cmd, cwd=str(repo_root), env=env, text=True)
        if p.returncode:
            print(f'[backfill] Command failed with {p.returncode}: {cmd}', file=sys.stderr)
            return p.returncode
    return 0


def run_backfill_batch(args: argparse.Namespace) -> int:
    repo=Path(args.repo_root).resolve(); output=Path(args.output_root).resolve(); site=Path(args.site_root).resolve()
    end=parse_date(args.backfill_end_date) or dt.date.today()
    start=parse_date(args.backfill_start_date) or (end - dt.timedelta(days=7*args.history_weeks))
    windows=[]
    cur=start
    while cur < end:
        nxt=min(cur+dt.timedelta(days=7), end)
        windows.append((cur.isoformat(), nxt.isoformat()))
        cur=nxt
    if args.backfill_limit_windows:
        windows=windows[:args.backfill_limit_windows]
    print(f'[backfill] windows={len(windows)} range={start}..{end}')
    failures=[]
    for s,e in windows:
        rc=run_existing_pipeline_for_window(repo, output, site, s, e, dry_run=args.dry_run)
        if rc: failures.append((s,e,rc))
    if failures:
        print('[backfill] failures:', failures, file=sys.stderr)
        return 2
    return 0


def patch_site_assets(site_root: Path) -> None:
    assets=site_root/'assets'; assets.mkdir(parents=True, exist_ok=True)
    js=assets/'aq26_charts_v3.js'
    js.write_text(r"""
(function(){
  async function getJSON(url){ const r=await fetch(url,{cache:'no-store'}); if(!r.ok) throw new Error(url+' '+r.status); return await r.json(); }
  function plotLine(id, feed, title){
    const el=document.getElementById(id); if(!el || typeof Plotly==='undefined') return;
    const labels=feed.labels||[]; const series=feed.series||{};
    const traces=Object.keys(series).map(k=>({x:labels,y:series[k],type:'scatter',mode:'lines+markers',name:k.replaceAll('_',' ')}));
    Plotly.react(id,traces,{title,margin:{t:45,l:55,r:20,b:55},paper_bgcolor:'rgba(0,0,0,0)',plot_bgcolor:'rgba(0,0,0,0)',xaxis:{automargin:true},yaxis:{rangemode:'tozero',automargin:true}},{responsive:true});
  }
  function plotBar(id, feed, title){
    const el=document.getElementById(id); if(!el || typeof Plotly==='undefined') return;
    const labels=feed.labels||[]; const series=feed.series||{};
    const traces=Object.keys(series).map(k=>({x:labels,y:series[k],type:'bar',name:k.replaceAll('_',' ')}));
    Plotly.react(id,traces,{title,barmode:'group',margin:{t:45,l:55,r:20,b:70},paper_bgcolor:'rgba(0,0,0,0)',plot_bgcolor:'rgba(0,0,0,0)',xaxis:{automargin:true},yaxis:{rangemode:'tozero',automargin:true}},{responsive:true});
  }
  async function init(){
    try { plotLine('records-chart', await getJSON('data/charts/weekly_record_counts.json'), 'Weekly evidence records'); } catch(e){ console.warn(e); }
    try { plotBar('coverage-chart', await getJSON('data/charts/source_coverage_by_week.json'), 'Source coverage by week'); } catch(e){ console.warn(e); }
    try { plotLine('readiness-chart', await getJSON('data/charts/readiness_trend.json'), 'Readiness gates over time'); } catch(e){ console.warn(e); }
    try { plotBar('filings-chart', await getJSON('data/charts/source_coverage_by_week.json'), 'Official filings and source coverage'); } catch(e){ console.warn(e); }
  }
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
""", encoding='utf-8')
    # Append script to all html pages once.
    for html in site_root.glob('*.html'):
        txt=html.read_text(encoding='utf-8', errors='ignore')
        if 'aq26_charts_v3.js' not in txt:
            txt=txt.replace("<script src='assets/site.js'></script>", "<script src='assets/site.js'></script><script src='assets/aq26_charts_v3.js'></script>")
            txt=txt.replace('<script src="assets/site.js"></script>', '<script src="assets/site.js"></script><script src="assets/aq26_charts_v3.js"></script>')
            html.write_text(txt, encoding='utf-8')


def validate_site_data(site_root: Path, output_root: Path, strict: bool=False) -> Tuple[bool, List[str]]:
    issues=[]
    # JSON parse checks
    for p in list((site_root/'data').rglob('*.json')) + list((output_root/'website_history').rglob('*.json')):
        try: load_json(p)
        except Exception as exc: issues.append(f'JSON parse failed: {p}: {exc}')
    weekly_p=site_root/'data'/'weekly_index.json'
    if weekly_p.exists():
        w=load_json(weekly_p).get('weeks', [])
        keys=[]
        for row in w:
            s,e=normalise_window(row); keys.append((s,e))
            if infer_status(row)=='harvested' and safe_int(row.get('source_record_count'))<=0:
                issues.append(f'harvested row has zero records: {s}..{e}')
        dup={k for k in keys if keys.count(k)>1}
        for k in sorted(dup): issues.append(f'duplicate weekly window: {k[0]}..{k[1]}')
    srp=site_root/'data'/'source_records_latest.json'
    if srp.exists():
        data=load_json(srp); records=data.get('records', []) if isinstance(data,dict) else []
        for i,r in enumerate(records[:10000]):
            missing=[f for f in REQUIRED_SOURCE_FIELDS if f not in r]
            if missing: issues.append(f'source record {i} missing {missing}')
            u=str(r.get('url') or '') + ' ' + str(r.get('query') or '')
            if re.search(r'(api[_-]?key|token|secret|password)=([^*&\s]{8,})', u, flags=re.I) and 'REDACTED' not in u:
                issues.append(f'secret-like value in source record {i}')
    # CSV readability checks with Python csv; pandas optional.
    for p in output_root.rglob('*.csv'):
        try:
            with p.open('r', encoding='utf-8', errors='replace', newline='') as f:
                rdr=csv.reader(f)
                for j,row in enumerate(rdr):
                    if j>5000: break
        except Exception as exc:
            issues.append(f'CSV read failed: {p}: {exc}')
    # Download links existence basic check
    for html in site_root.glob('*.html'):
        txt=html.read_text(encoding='utf-8', errors='ignore')
        for href in re.findall(r"href=['\"]([^'\"]+)['\"]", txt):
            if href.startswith(('http','#','mailto:')): continue
            path=(site_root/href.split('#')[0].split('?')[0]).resolve()
            if not path.exists() and not href.endswith('.html'):
                # html extension links may be generated later, but missing downloads/data are blockers.
                if href.startswith(('downloads/','data/','assets/')):
                    issues.append(f'missing linked file from {html.name}: {href}')
    ok=not issues
    if strict and issues: ok=False
    return ok, issues


def command_build(args: argparse.Namespace) -> int:
    output=Path(args.output_root).resolve(); site=Path(args.site_root).resolve()
    rows=discover_summary_rows(output, site)
    end=parse_date(args.history_end_date) or dt.date.today()
    index=canonical_weekly_index(rows, end, args.history_weeks)
    write_json(site/'data'/'weekly_index.json', index)
    latest={}
    lp=site/'data'/'latest_summary.json'
    if lp.exists():
        try: latest=load_json(lp)
        except Exception: latest={}
    sr={}
    sp=site/'data'/'source_records_latest.json'
    if sp.exists():
        try: sr=load_json(sp)
        except Exception: sr={}
    build_chart_feeds(site, index, latest, sr)
    patch_site_assets(site)
    ok,issues=validate_site_data(site, output, strict=args.strict)
    report={'created_at_utc':now_utc(),'ok':ok,'issue_count':len(issues),'issues':issues[:500]}
    write_json(output/'99_integrity'/'AQ26_WEEKLYV2_SITE_V3_VALIDATION.json', report)
    for i in issues[:80]: print('[validate]', i)
    print(f'[done] weekly rows={len(index.get("weeks", []))} chart feeds written to {site/"data"/"charts"}')
    if args.strict and not ok: return 3
    return 0


def command_validate(args: argparse.Namespace) -> int:
    ok,issues=validate_site_data(Path(args.site_root).resolve(), Path(args.output_root).resolve(), strict=args.strict)
    for i in issues: print('[validate]', i)
    print('[validate] ok=', ok, 'issues=', len(issues))
    return 0 if ok or not args.strict else 3


def main(argv=None) -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument('--repo-root', default='.')
    ap.add_argument('--output-root', default='outputs')
    ap.add_argument('--site-root', default='site_public')
    ap.add_argument('--history-weeks', type=int, default=int(os.getenv('AQ26_HISTORY_WEEKS','104')))
    ap.add_argument('--history-end-date', default=os.getenv('AQ26_HISTORY_END_DATE') or dt.date.today().isoformat())
    ap.add_argument('--strict', action='store_true')
    sub=ap.add_subparsers(dest='cmd')
    sub.add_parser('build-site-data')
    sub.add_parser('validate')
    bp=sub.add_parser('backfill-batch')
    bp.add_argument('--backfill-start-date', default=os.getenv('AQ26_BACKFILL_START_DATE',''))
    bp.add_argument('--backfill-end-date', default=os.getenv('AQ26_BACKFILL_END_DATE',''))
    bp.add_argument('--backfill-limit-windows', type=int, default=int(os.getenv('AQ26_BACKFILL_LIMIT_WINDOWS','4')))
    bp.add_argument('--dry-run', action='store_true')
    args=ap.parse_args(argv)
    try:
        if args.cmd == 'backfill-batch': return run_backfill_batch(args)
        if args.cmd == 'validate': return command_validate(args)
        return command_build(args)
    except Exception:
        traceback.print_exc()
        return 99

if __name__ == '__main__':
    raise SystemExit(main())
