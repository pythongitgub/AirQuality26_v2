#!/usr/bin/env python3
from __future__ import annotations
import argparse, datetime as dt, json, re
from pathlib import Path

def load(p): return json.loads(Path(p).read_text(encoding='utf-8')) if Path(p).exists() else {}
def write(p,obj): p=Path(p); p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(obj,indent=2,ensure_ascii=False,default=str),encoding='utf-8')
def parse_date(v):
    if not v: return None
    try: return dt.datetime.fromisoformat(str(v).replace('Z','+00:00')).date()
    except Exception: pass
    m=re.search(r'(\d{4})-(\d{2})-(\d{2})',str(v))
    return dt.date(int(m.group(1)),int(m.group(2)),int(m.group(3))) if m else None
def daterange(s,e):
    while s<=e: yield s; s+=dt.timedelta(days=1)
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--output-root',default='outputs'); ap.add_argument('--lookback-days',default='14'); ap.add_argument('--backfill-start-date',default=''); ap.add_argument('--backfill-end-date',default=''); args=ap.parse_args()
    root=Path(args.output_root); latest=load(root/'00_live_harvest'/'LATEST_HARVEST.json'); drive=load(root/'08_gdrive_snapshot'/'gdrive_recursive_inventory.json')
    end=dt.date.fromisoformat(args.backfill_end_date) if args.backfill_end_date else dt.datetime.now(dt.timezone.utc).date(); start=dt.date.fromisoformat(args.backfill_start_date) if args.backfill_start_date else end-dt.timedelta(days=int(args.lookback_days))
    streams=['news_api','ground_aq','weather','official_search','official_watch_url','satellite_metadata','gdrive']
    observed={s:set() for s in streams}
    for r in latest.get('source_records',[]):
        st=r.get('source_type'); d=parse_date(r.get('retrieved_at_utc')) or parse_date(r.get('date_uk'))
        if st in observed and d: observed[st].add(d.isoformat())
    missing=[]
    for st,seen in observed.items():
        for day in daterange(start,end):
            if day.isoformat() not in seen: missing.append({'date':day.isoformat(),'stream':st,'priority':'high' if st in ['weather','ground_aq','official_search','satellite_metadata'] else 'medium','reason':'No source record retrieved on this date in current latest harvest','recommended_action':'Backfill or confirm source has no daily historical endpoint'})
    files=drive.get('files',[]) if isinstance(drive,dict) else []
    likely=[f.get('path') for f in files if isinstance(f.get('path'),str) and any(t in f.get('path','').lower() for t in ['airquality','newhaven','openaq','defra','incinerator','satellite'])][:500]
    result={'created_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'window':{'start':start.isoformat(),'end':end.isoformat()},'expected_streams':streams,'observed_by_stream':{k:sorted(v) for k,v in observed.items()},'missing_count':len(missing),'missing':missing[:5000],'drive_summary':{'recursive_inventory_status':drive.get('status','missing') if isinstance(drive,dict) else 'missing','drive_file_count':len(files),'drive_folder_count':drive.get('folder_count',0) if isinstance(drive,dict) else 0,'likely_airquality_paths':likely},'notes':['Gap planner only; daily gaps may be expected for catalogue/watch sources.']}
    write(root/'11_backfill'/'missing_date_backfill_plan.json',result); print(json.dumps({'missing_count':len(missing),'drive_file_count':len(files)},indent=2))
if __name__=='__main__': main()
