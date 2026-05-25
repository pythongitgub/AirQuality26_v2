#!/usr/bin/env python3
from __future__ import annotations
import argparse, datetime as dt, html, json, os, shutil, zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional

def load_json(p: Path) -> Dict[str, Any]:
    if not p.exists(): return {}
    try: return json.loads(p.read_text(encoding="utf-8"))
    except Exception: return {}

def write_json(p: Path, obj: Any) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

def esc(v): return html.escape("" if v is None else str(v))
def n(v):
    try: return int(v)
    except Exception: return 0

def latest_zip(root: Path) -> Optional[Path]:
    latest = root / "weeklyv2_reports" / "LATEST_ZIP.txt"
    if latest.exists():
        p = Path(latest.read_text(encoding="utf-8").strip())
        if p.exists(): return p
    zips = sorted((root / "weeklyv2_reports").glob("AQ26_WEEKLYV2_EVIDENCE_*.zip"))
    return zips[-1] if zips else None

def zip_ledger_status(zp: Optional[Path]) -> Dict[str, Any]:
    if not zp or not zp.exists(): return {"zip_entry_count":0,"ledger_rows":0,"ledger_present":False}
    with zipfile.ZipFile(zp, "r") as z:
        names=z.namelist(); led=[x for x in names if x.endswith("AQ26_FINAL_ZIP_LEDGER.csv")]
        rows=0
        if led:
            rows=max(0, len(z.read(led[-1]).decode("utf-8", errors="ignore").splitlines())-1)
        return {"zip_entry_count":len(names),"ledger_rows":rows,"ledger_present":bool(led)}

def summary(root: Path) -> Dict[str, Any]:
    latest=load_json(root/"00_weeklyv2"/"LATEST_WEEKLYV2.json") or load_json(root/"00_live_harvest"/"LATEST_HARVEST.json")
    gates=load_json(root/"12_scoring"/"evidence_readiness_gates.json")
    red=load_json(root/"99_integrity"/"redaction_audit.json")
    sat=load_json(root/"07_satellite_cdse"/"satellite_catalogue_metadata.json")
    drive=load_json(root/"08_gdrive_snapshot"/"gdrive_recursive_inventory.json")
    official=load_json(root/"06_official_filings"/"official_priority_summary.json")
    openaq=load_json(root/"04_ground_aq_providers"/"openaq_safety_manifest.json")
    cams=load_json(root/"09_cams"/"cams_readiness.json")
    cdse=load_json(root/"15_optional_sources"/"cdse_auth_readiness.json")
    sanit=load_json(root/"15_optional_sources"/"provider_sanitization_manifest.json")
    warn=load_json(root/"03_news_context"/"news_provider_warnings.json")
    zp=latest_zip(root); run_ts=latest.get("run_ts") or dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return {"run_ts":run_ts,"created_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),"date_window":latest.get("date_window",{}),"source_record_count":n(latest.get("source_record_count")),"ok_count":n(latest.get("ok_count")),"warning_count":n(latest.get("warning_count")),"error_count":n(latest.get("error_count")),"skipped_count":n(latest.get("skipped_count")),"redaction_leak_count":n(red.get("leak_count")),"redaction_ready":bool(gates.get("redaction_ready")),"external_submission_ready":bool(gates.get("external_submission_ready")),"satellite_product_count":n(sat.get("product_count")),"satellite_extraction_ready":bool(gates.get("satellite_extraction_ready")),"drive_file_count":n(drive.get("file_count")),"drive_inventory_truncated":bool(drive.get("drive_inventory_truncated")),"high_priority_filings":len(official.get("high",[]) or []),"medium_priority_filings":len(official.get("medium",[]) or []),"openaq_request_count":n(openaq.get("request_count")),"openaq_rate_limit_seen":bool(openaq.get("rate_limit_seen")),"cams_key_present":bool(cams.get("cams_key_present")),"cams_data_ready":bool(cams.get("cams_data_ready")),"cdse_download_ready":bool(cdse.get("cdse_download_ready") or gates.get("cdse_download_ready")),"cdse_sentinelhub_ready":bool(cdse.get("cdse_sentinelhub_ready") or gates.get("cdse_sentinelhub_client_credentials_ready")),"provider_sanitized_files":n(sanit.get("files_changed")),"news_warning_count":n(warn.get("warning_count")),"final_zip_name":zp.name if zp else "","final_zip_relpath":f"downloads/{zp.name}" if zp else "","final_zip_status":zip_ledger_status(zp),"github_repository":os.getenv("GITHUB_REPOSITORY_VALUE",os.getenv("GITHUB_REPOSITORY","")),"github_run_id":os.getenv("GITHUB_RUN_ID_VALUE",os.getenv("GITHUB_RUN_ID","")),"github_sha":os.getenv("GITHUB_SHA_VALUE",os.getenv("GITHUB_SHA",""))}

def old_history(root: Path) -> List[Dict[str, Any]]:
    rows=[]; hd=root/"website_history"
    for p in sorted(hd.glob("*.json")):
        if p.name.startswith("weekly_index"): continue
        j=load_json(p)
        if j.get("run_ts"): rows.append(j)
    prev=load_json(hd/"weekly_index.previous.json")
    if isinstance(prev.get("weeks"), list): rows += [x for x in prev["weeks"] if isinstance(x,dict) and x.get("run_ts")]
    by={}
    for r in rows: by[r["run_ts"]]=r
    return list(by.values())

def scaffold(weeks:int, existing:List[Dict[str,Any]]) -> List[Dict[str,Any]]:
    bywin={}
    for r in existing:
        w=r.get("date_window",{}); k=(w.get("start"),w.get("end"))
        if k[0] and k[1]: bywin[k]=r
    today=dt.datetime.now(dt.timezone.utc).date(); rows=[]
    for i in range(weeks):
        end=today-dt.timedelta(days=i*7); start=end-dt.timedelta(days=7); key=(start.isoformat(), end.isoformat())
        rows.append(bywin.get(key, {"run_ts":f"BACKFILL_SLOT_{key[0]}_{key[1]}","date_window":{"start":key[0],"end":key[1]},"backfill_status":"not_yet_harvested","source_record_count":0,"ok_count":0,"warning_count":0,"error_count":0,"satellite_product_count":0,"drive_file_count":0,"high_priority_filings":0,"medium_priority_filings":0,"external_submission_ready":False}))
    seen={r["run_ts"] for r in rows}; rows += [r for r in existing if r.get("run_ts") not in seen]
    return sorted(rows, key=lambda x:(x.get("date_window",{}).get("end",""),x.get("run_ts","")), reverse=True)

def copy_downloads(root: Path, site: Path):
    d=site/"downloads"; d.mkdir(parents=True, exist_ok=True); zp=latest_zip(root)
    if zp and zp.exists(): shutil.copy2(zp, d/zp.name)
    for p in sorted((root/"weeklyv2_reports").rglob("AQ26_WEEKLYV2_REPORT_*.*"))[-4:]:
        if p.suffix.lower() in {".pdf",".md"}: shutil.copy2(p, d/p.name)

def write_assets(site: Path):
    a=site/"assets"; a.mkdir(parents=True, exist_ok=True)
    a.joinpath("style.css").write_text("""
:root{--bg:#0b1220;--panel:#121a2b;--panel2:#17233a;--text:#edf3ff;--muted:#aab7cf;--line:#2b3b5c;--ok:#72e6a6;--warn:#ffd166;--bad:#ff6b6b;--accent:#7cc7ff}*{box-sizing:border-box}body{margin:0;font-family:Inter,Segoe UI,Roboto,Arial,sans-serif;background:var(--bg);color:var(--text)}a{color:var(--accent)}header{padding:28px 32px;background:linear-gradient(135deg,#0b1220,#173b66)}header h1{margin:0;font-size:32px}header p{max-width:1100px;color:var(--muted);line-height:1.45}nav{display:flex;gap:12px;flex-wrap:wrap;margin-top:18px}nav a{background:rgba(255,255,255,.08);padding:9px 12px;border-radius:999px;text-decoration:none}main{padding:28px 32px;max-width:1440px;margin:0 auto}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:16px}.card{background:var(--panel);border:1px solid var(--line);border-radius:18px;padding:18px}.card h3{margin:0 0 6px;color:var(--muted);font-size:13px;text-transform:uppercase;letter-spacing:.08em}.metric{font-size:34px;font-weight:800}.small{font-size:13px;color:var(--muted);line-height:1.45}.ok{color:var(--ok)}.warn{color:var(--warn)}.bad{color:var(--bad)}section{margin:24px 0}.section-title{font-size:22px;margin:0 0 12px}table{width:100%;border-collapse:collapse;background:var(--panel);border-radius:16px;overflow:hidden}th,td{padding:10px 12px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top;font-size:14px}th{background:var(--panel2);color:var(--muted)}.chart{height:390px;background:var(--panel);border:1px solid var(--line);border-radius:18px;padding:10px}.notice{border-left:4px solid var(--warn);padding:12px 14px;background:#2b250f;border-radius:10px;color:#ffe8a3}footer{padding:30px 32px;color:var(--muted);border-top:1px solid var(--line);margin-top:40px}input{width:100%;padding:12px;border-radius:12px;border:1px solid var(--line);background:#0f1829;color:var(--text);margin:0 0 12px}.badge{display:inline-block;padding:4px 8px;border-radius:999px;background:#213555;color:var(--muted)}
""", encoding="utf-8")
    a.joinpath("app.js").write_text("""
function arr(name){return AQ26.weeks.slice().reverse().map(x=>Number(x[name]||0));}
function labels(){return AQ26.weeks.slice().reverse().map(x=>((x.date_window||{}).end||x.run_ts||'').slice(0,10));}
if(typeof Plotly!=='undefined'&&typeof AQ26!=='undefined'){const l=labels();Plotly.newPlot('chart_records',[{x:l,y:arr('source_record_count'),type:'scatter',mode:'lines+markers',name:'Records'},{x:l,y:arr('ok_count'),type:'scatter',mode:'lines+markers',name:'OK'},{x:l,y:arr('warning_count'),type:'scatter',mode:'lines+markers',name:'Warnings'},{x:l,y:arr('error_count'),type:'scatter',mode:'lines+markers',name:'Errors'}],{title:'Weekly evidence records',paper_bgcolor:'rgba(0,0,0,0)',plot_bgcolor:'rgba(0,0,0,0)',font:{color:'#edf3ff'},xaxis:{gridcolor:'#2b3b5c'},yaxis:{gridcolor:'#2b3b5c'}},{responsive:true});Plotly.newPlot('chart_sources',[{x:l,y:arr('satellite_product_count'),type:'bar',name:'Satellite products'},{x:l,y:arr('drive_file_count'),type:'bar',name:'Drive files'},{x:l,y:arr('high_priority_filings'),type:'bar',name:'High filings'}],{title:'Evidence source coverage',barmode:'group',paper_bgcolor:'rgba(0,0,0,0)',plot_bgcolor:'rgba(0,0,0,0)',font:{color:'#edf3ff'},xaxis:{gridcolor:'#2b3b5c'},yaxis:{gridcolor:'#2b3b5c'}},{responsive:true});}
function filterTable(){const q=(document.getElementById('filter').value||'').toLowerCase();document.querySelectorAll('#tbl tbody tr').forEach(tr=>{tr.style.display=tr.innerText.toLowerCase().includes(q)?'':'none';});}
""", encoding="utf-8")

def metric(label,value,cls=''): return f'<div class="card"><h3>{esc(label)}</h3><div class="metric {cls}">{esc(value)}</div></div>'
def gate(label,value,invert=False):
    cls='bad' if (bool(value) and invert) or ((not bool(value)) and not invert) else 'ok'
    return f'<div class="card"><h3>{esc(label)}</h3><div class="metric {cls}">{esc(value)}</div></div>'

def layout(title, body):
    nav='<nav><a href="index.html">Overview</a><a href="archive.html">Weekly archive</a><a href="tables.html">Tables</a><a href="methods.html">Methods & gates</a></nav>'
    return '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+esc(title)+' - AQ26</title><link rel="stylesheet" href="assets/style.css"></head><body><header><h1>'+esc(title)+'</h1>'+nav+'</header><main>'+body+'</main><footer>AQ26 controlled-review dashboard.</footer><script src="assets/app.js"></script></body></html>'

def render(site: Path, s: Dict[str,Any], weeks: List[Dict[str,Any]]):
    data=json.dumps({'summary':s,'weeks':weeks}, ensure_ascii=False)
    cards=''.join([metric('Source records',s['source_record_count']),metric('OK',s['ok_count'],'ok'),metric('Warnings',s['warning_count'],'warn'),metric('Errors',s['error_count'],'bad' if s['error_count'] else 'ok'),metric('Satellite products',s['satellite_product_count']),metric('Drive files',s['drive_file_count'],'warn' if s['drive_inventory_truncated'] else ''),metric('Redaction leaks',s['redaction_leak_count'],'bad' if s['redaction_leak_count'] else 'ok'),metric('High-priority filings',s['high_priority_filings'])])
    gates=''.join([gate('Redaction ready',s['redaction_ready']),gate('CDSE OData/download ready',s['cdse_download_ready']),gate('CDSE Sentinel Hub ready',s['cdse_sentinelhub_ready']),gate('CAMS data ready',s['cams_data_ready']),gate('Satellite extraction ready',s['satellite_extraction_ready']),gate('Drive inventory truncated',s['drive_inventory_truncated'],True)])
    body=f'<div class="notice">External submission ready: <strong>{esc(s["external_submission_ready"])}</strong>. Controlled review and evidence triage only.</div><section><h2 class="section-title">Latest run</h2><div class="grid">{cards}</div></section><section><h2 class="section-title">Trend charts</h2><div class="grid"><div id="chart_records" class="chart"></div><div id="chart_sources" class="chart"></div></div></section><section><h2 class="section-title">Readiness snapshot</h2><div class="grid">{gates}</div></section><section><h2 class="section-title">Latest downloads</h2><p><a class="badge" href="{esc(s.get("final_zip_relpath"))}">Download latest evidence ZIP</a></p><p class="small">Run timestamp: {esc(s.get("run_ts"))} | GitHub run: {esc(s.get("github_run_id"))} | Commit: {esc(s.get("github_sha"))}</p></section><script>const AQ26={data};</script><script src="assets/app.js"></script>'
    intro='<p>Controlled-review weekly evidence dashboard for target/control air-quality monitoring around Newhaven Energy Recovery Facility. No external endorsement or causal attribution is claimed.</p>'
    site.joinpath('index.html').write_text(layout('AQ26 Weekly Evidence Dashboard', intro+body), encoding='utf-8')
    rows=[]
    for w in weeks:
        win=w.get('date_window',{}); status=w.get('backfill_status','harvested' if n(w.get('source_record_count')) else 'not_yet_harvested'); link=w.get('final_zip_relpath') or '#'
        rows.append(f"<tr><td>{esc(win.get('start'))}</td><td>{esc(win.get('end'))}</td><td>{esc(status)}</td><td>{esc(w.get('source_record_count'))}</td><td>{esc(w.get('ok_count'))}</td><td>{esc(w.get('warning_count'))}</td><td>{esc(w.get('error_count'))}</td><td><a href='{esc(link)}'>evidence</a></td></tr>")
    site.joinpath('archive.html').write_text(layout('Weekly archive',"<section><h2 class='section-title'>Clickable weekly history and backfill slots</h2><input id='filter' placeholder='Filter weeks...' oninput='filterTable()'><table id='tbl'><thead><tr><th>Start</th><th>End</th><th>Status</th><th>Records</th><th>OK</th><th>Warnings</th><th>Errors</th><th>Link</th></tr></thead><tbody>"+''.join(rows)+"</tbody></table></section>"), encoding='utf-8')
    table=''.join(f'<tr><th>{esc(k)}</th><td>{esc(v)}</td></tr>' for k,v in s.items() if not isinstance(v,(dict,list)))
    site.joinpath('tables.html').write_text(layout('Tables',"<section><h2 class='section-title'>Latest run summary table</h2><table>"+table+"</table></section>"), encoding='utf-8')
    methods='<section><h2 class="section-title">Scientific and governance boundaries</h2><div class="card"><p>This dashboard uses controlled-review language: screening signal, candidate anomaly, provenance evidence and readiness gate. It does not claim causal attribution, regulatory proof, health-burden attribution or endorsement.</p></div></section><section><h2 class="section-title">Method alignment</h2><div class="grid"><div class="card"><h3>Dominici</h3><p class="small">Causal language guarded; confounders and lag windows noted.</p></div><div class="card"><h3>Martin</h3><p class="small">Satellite catalogue and future satellite extraction aligned to ground validation.</p></div><div class="card"><h3>Brauer</h3><p class="small">Multi-source exposure screening, not health-burden attribution.</p></div><div class="card"><h3>Anenberg</h3><p class="small">NO2 and emissions-relevant trace gas context.</p></div><div class="card"><h3>Damoulas</h3><p class="small">Digital-twin readiness via target/control history and charts.</p></div></div></section>'
    site.joinpath('methods.html').write_text(layout('Methods & gates',methods), encoding='utf-8')

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--output-root', default='outputs'); ap.add_argument('--site-root', default='public_site'); ap.add_argument('--history-weeks', default='52'); args=ap.parse_args()
    root=Path(args.output_root); site=Path(args.site_root); shutil.rmtree(site, ignore_errors=True); site.mkdir(parents=True, exist_ok=True)
    s=summary(root); existing=old_history(root); by={x.get('run_ts'):x for x in existing if x.get('run_ts')}; by[s['run_ts']]=s; weeks=scaffold(int(args.history_weeks), list(by.values()))
    data=site/'data'; hist=data/'history'; hist.mkdir(parents=True, exist_ok=True); write_json(data/'latest_summary.json',s); write_json(data/'weekly_index.json',{'created_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'weeks':weeks}); write_json(hist/(s['run_ts']+'.json'),s)
    copy_downloads(root, site); write_assets(site); render(site,s,weeks); site.joinpath('sitemap.txt').write_text('index.html\narchive.html\ntables.html\nmethods.html\ndata/weekly_index.json\n', encoding='utf-8')
    print(json.dumps({'site_root':str(site),'history_weeks':len(weeks),'latest_run_ts':s['run_ts'],'latest_zip':s.get('final_zip_name'),'pages':['index.html','archive.html','tables.html','methods.html']}, indent=2))
if __name__ == '__main__': main()
