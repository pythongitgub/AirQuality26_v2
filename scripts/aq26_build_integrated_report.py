#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,datetime as dt,hashlib,json,zipfile
from pathlib import Path
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer
except Exception: SimpleDocTemplate=None
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()
def load(p): return json.loads(Path(p).read_text(encoding='utf-8')) if Path(p).exists() else {}
def build_ledger(root):
    out=root/'99_integrity'/'AQ26_SHA256_LEDGER.csv'; out.parent.mkdir(parents=True,exist_ok=True); rows=[]
    for p in sorted(root.rglob('*')):
        if p.is_file() and p.name not in {'AQ26_SHA256_LEDGER.csv','AQ26_FINAL_ZIP_LEDGER.csv','LATEST_ZIP.txt'} and p.suffix.lower()!='.zip': rows.append({'path':str(p),'size_bytes':p.stat().st_size,'sha256':sha(p)})
    with out.open('w',newline='',encoding='utf-8') as f: w=csv.DictWriter(f,fieldnames=['path','size_bytes','sha256']); w.writeheader(); w.writerows(rows)
    return out
def pdf_from_md(md,pdf):
    if SimpleDocTemplate is None: pdf.write_bytes(b'%PDF-1.4
% reportlab unavailable
'); return
    styles=getSampleStyleSheet(); doc=SimpleDocTemplate(str(pdf),pagesize=A4); story=[]
    for line in md.read_text(encoding='utf-8').splitlines():
        if line.startswith('# '): story += [Paragraph(line[2:],styles['Title']),Spacer(1,8)]
        elif line.startswith('## '): story += [Paragraph(line[3:],styles['Heading2']),Spacer(1,6)]
        elif line.startswith('- '): story.append(Paragraph('• '+line[2:],styles['BodyText']))
        elif line.strip(): story += [Paragraph(line,styles['BodyText']),Spacer(1,4)]
        else: story.append(Spacer(1,4))
    doc.build(story)
def final_zip_ledger(zp,root):
    out=root/'99_integrity'/'AQ26_FINAL_ZIP_LEDGER.csv'; rows=[]
    with zipfile.ZipFile(zp,'r') as z:
        for info in z.infolist():
            if info.is_dir() or info.filename.endswith('AQ26_FINAL_ZIP_LEDGER.csv'): continue
            data=z.read(info.filename); rows.append({'zip_entry':info.filename,'size_bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
    with out.open('w',newline='',encoding='utf-8') as f: w=csv.DictWriter(f,fieldnames=['zip_entry','size_bytes','sha256']); w.writeheader(); w.writerows(rows)
    return out
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--output-root',default='outputs'); args=ap.parse_args(); root=Path(args.output_root); ts=dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ'); report=root/'weekly_reports'/f'AQ26_WEEKLY_{ts}'; report.mkdir(parents=True,exist_ok=True)
    latest=load(root/'00_live_harvest'/'LATEST_HARVEST.json'); alerts=load(root/'10_anomaly_alerts'/'anomaly_alerts.json'); filings=load(root/'06_official_filings'/'official_filing_index.json'); sat=load(root/'07_satellite_cdse'/'satellite_catalogue_metadata.json'); red=load(root/'99_integrity'/'redaction_audit.json'); scoring=load(root/'12_scoring'/'evidence_priority_scores.json'); readiness=load(root/'12_scoring'/'evidence_readiness_gates.json'); backfill=load(root/'11_backfill'/'missing_date_backfill_plan.json'); drive=load(root/'08_gdrive_snapshot'/'gdrive_recursive_inventory.json')
    md=report/f'AQ26_WEEKLY_INTEGRATED_REPORT_{ts}.md'
    md.write_text('
'.join(['# AQ26 Weekly Integrated Evidence Report','','## Controlled-use boundary','Automated controlled-review evidence harvest. No endorsement claimed by WHO, UNEP, EEA, C40 Cities or named experts. No causal attribution unless evidence gates support it.','','## Executive status',f"- Source records: `{latest.get('source_record_count',0)}`",f"- OK records: `{latest.get('ok_count',0)}`",f"- Error records: `{latest.get('error_count',0)}`",f"- Official filing candidates: `{filings.get('filing_count',0)}`",f"- High-priority filings: `{len(scoring.get('high_priority_filings',[]))}`",f"- Medium-priority filings: `{len(scoring.get('medium_priority_filings',[]))}`",f"- Satellite catalogue products: `{sat.get('product_count',0)}`",f"- Alerts: `{alerts.get('alert_count',0)}`",f"- Redaction leaks: `{red.get('leak_count','not yet scanned')}`",f"- Recursive Drive files inventoried: `{drive.get('file_count','not scanned')}`",f"- Backfill missing stream/date rows: `{backfill.get('missing_count','not planned')}`",'','## Evidence gates',f"- Met Office ready: `{readiness.get('metoffice_ready')}`",f"- Ground AQ ready: `{readiness.get('ground_aq_ready')}`",f"- Satellite catalogue ready: `{readiness.get('satellite_catalogue_ready')}`",f"- Satellite extraction ready: `{readiness.get('satellite_extraction_ready')}`",f"- Official filings ready: `{readiness.get('official_filings_ready')}`",f"- External submission ready: `{readiness.get('external_submission_ready')}`",'','## Specialist-method alignment','- Dominici-style causal epidemiology: guarded causal language, confounder notes and future exposure-response readiness.','- Martin-style satellite/ground fusion: Sentinel catalogue retained with target/control context; extraction remains next stage.','- Brauer/GBD-style integration: multi-source exposure-screening registry, not health-burden attribution yet.','- Anenberg-style NO2/emissions-health logic: NO2/SO2/CO/HCHO/O3/CH4/AER_AI families are prioritised.','- Damoulas-style digital twin readiness: target/control graph, completeness and scoring files prepare future spatiotemporal modelling.','','## Readiness','Controlled-review beta. Not external-submission ready until satellite extraction, official relevance review, ground AQ QA and weather/wind alignment gates pass.']),encoding='utf-8')
    pdf=report/f'AQ26_WEEKLY_INTEGRATED_REPORT_{ts}.pdf'; pdf_from_md(md,pdf); led=build_ledger(root)
    manifest={'run_ts':ts,'report_md':str(md),'report_pdf':str(pdf),'sha256_ledger':str(led),'redaction_audit':str(root/'99_integrity'/'redaction_audit.json'),'latest_harvest':str(root/'00_live_harvest'/'LATEST_HARVEST.json'),'source_history':str(root/'source_history'/'source_index.jsonl'),'scoring':str(root/'12_scoring'/'evidence_priority_scores.json'),'backfill_plan':str(root/'11_backfill'/'missing_date_backfill_plan.json'),'recursive_drive_inventory':str(root/'08_gdrive_snapshot'/'gdrive_recursive_inventory.json'),'controlled_use_boundary':'No endorsement claimed; no causal attribution unless evidence gates support it.'}
    (report/f'AQ26_WEEKLY_MASTER_MANIFEST_{ts}.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8'); led=build_ledger(root)
    zp=root/'weekly_reports'/f'AQ26_WEEKLY_INTEGRATED_EVIDENCE_{ts}.zip'; include=[root/'00_live_harvest',root/'03_news_context',root/'04_ground_aq_providers',root/'05_weather',root/'05_metoffice_datahub_weather',root/'06_official_filings',root/'07_satellite_cdse',root/'08_gdrive_snapshot',root/'10_anomaly_alerts',root/'11_backfill',root/'12_scoring',root/'99_integrity',root/'source_history',report]
    def write_zip():
        with zipfile.ZipFile(zp,'w',zipfile.ZIP_DEFLATED) as z:
            for b in include:
                if b.exists():
                    for p in sorted(b.rglob('*')):
                        if p.is_file() and p!=zp: z.write(p,arcname=str(p.relative_to(root.parent)))
    write_zip(); fzl=final_zip_ledger(zp,root); write_zip(); (root/'weekly_reports'/'LATEST_ZIP.txt').write_text(str(zp),encoding='utf-8'); print(json.dumps({'zip':str(zp),'zip_sha256':sha(zp),'pdf':str(pdf),'final_zip_ledger':str(fzl)},indent=2))
if __name__=='__main__': main()
