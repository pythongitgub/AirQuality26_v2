#!/usr/bin/env python3
from __future__ import annotations
import argparse, csv, datetime as dt, hashlib, json, os, shutil, zipfile
from pathlib import Path
import yaml
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors

def sha256_file(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()
def now_ts(): return dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
def load_json(p, default=None):
    try: return json.loads(Path(p).read_text(encoding='utf-8'))
    except Exception: return default if default is not None else {}
def mkdir(p): Path(p).mkdir(parents=True, exist_ok=True); return Path(p)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--config',default='configs/aq26_weekly_sources.yml')
    args=ap.parse_args(); cfg=yaml.safe_load(Path(args.config).read_text()) if Path(args.config).exists() else {}
    out=Path(cfg.get('output_root','outputs')); ts=now_ts(); report_dir=mkdir(out/'weekly_reports'/f'AQ26_WEEKLY_{ts}')
    live=load_json(out/'00_live_harvest'/'LATEST_HARVEST.json',{})
    red=load_json(out/'99_integrity'/'redaction_audit.json',{})
    ledger=out/'99_integrity'/'AQ26_SHA256_LEDGER.csv'
    official=load_json(out/'06_official_filings'/'official_filing_index.json',{})
    sat=load_json(out/'07_satellite_cdse'/'satellite_catalogue_metadata.json',{})
    news=load_json(out/'03_news_context'/'news_articles.json',{})
    # copy key manifests
    for p in [out/'00_live_harvest'/'LATEST_HARVEST.json', out/'99_integrity'/'redaction_audit.json', ledger, out/'06_official_filings'/'official_filing_index.json', out/'07_satellite_cdse'/'satellite_catalogue_metadata.json', out/'source_history'/'source_index.jsonl']:
        if Path(p).exists():
            dest=report_dir/'metadata'/Path(p).name; dest.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(p,dest)
    # Markdown report
    md = report_dir/'AQ26_WEEKLY_EXECUTIVE_REPORT.md'
    md.write_text(f"""# AQ26 Weekly Comprehensive Evidence Report\n\nRun timestamp: {ts}\n\n## Controlled-use boundary\n{cfg.get('controlled_use_boundary','No endorsement or causal claim is made.')}\n\n## Harvest summary\n- Source records: {live.get('source_record_count',0)}\n- OK records: {live.get('ok_count',0)}\n- Error records: {live.get('error_count',0)}\n- News articles: {news.get('count',0)}\n- Official filing candidates: {official.get('filing_count',0)}\n- Satellite products/catalogue count: {sat.get('product_count',0)}\n- Redaction audit leaks: {red.get('leak_count','unknown')}\n\n## Certification status\nThis is a controlled-review evidence harvest. It is not an endorsement by WHO, UNEP, EEA, C40 Cities, or any named expert. It does not establish causality without subsequent QA, source-apportionment, meteorological analysis and independent review.\n""", encoding='utf-8')
    # PDF report
    pdf=report_dir/'AQ26_WEEKLY_EXECUTIVE_REPORT.pdf'
    styles=getSampleStyleSheet(); story=[]
    story.append(Paragraph('AQ26 Weekly Comprehensive Evidence Report', styles['Title']))
    story.append(Paragraph(f'Run timestamp: {ts}', styles['Normal'])); story.append(Spacer(1,0.3*cm))
    story.append(Paragraph('Controlled-use boundary', styles['Heading2']))
    story.append(Paragraph((cfg.get('controlled_use_boundary') or 'No endorsement or causal claim is made.').replace('\n','<br/>'), styles['BodyText']))
    story.append(Spacer(1,0.3*cm))
    rows=[['Metric','Value'],['Source records',live.get('source_record_count',0)],['OK records',live.get('ok_count',0)],['Error records',live.get('error_count',0)],['News articles',news.get('count',0)],['Official filing candidates',official.get('filing_count',0)],['Satellite product/catalogue count',sat.get('product_count',0)],['Redaction leaks',red.get('leak_count','unknown')]]
    t=Table(rows, colWidths=[7*cm,7*cm]); t.setStyle(TableStyle([('GRID',(0,0),(-1,-1),0.25,colors.grey),('BACKGROUND',(0,0),(-1,0),colors.lightgrey)])); story.append(t)
    story.append(Spacer(1,0.3*cm))
    story.append(Paragraph('WHO / UNEP / EEA / C40 / expert-use caveat', styles['Heading2']))
    story.append(Paragraph('This pack supports specialist triage by documenting what was collected, when, from where, and with what integrity checks. It should be reviewed as a screening and provenance pack, not as proof of facility-level attribution.', styles['BodyText']))
    story.append(Paragraph('Priority review questions: station representativeness, meteorological alignment, source apportionment, control-site comparability, satellite resolution limits, pollutant averaging periods, uncertainty and confounders.', styles['BodyText']))
    SimpleDocTemplate(str(pdf), pagesize=A4, rightMargin=1.5*cm,leftMargin=1.5*cm,topMargin=1.5*cm,bottomMargin=1.5*cm).build(story)
    # Readiness gates
    gates={
        'automation_ready': True,
        'provenance_ready': bool(live.get('source_record_count',0) and ledger.exists()),
        'redaction_ready': red.get('leak_count',999)==0,
        'official_filing_ready': official.get('filing_count',0)>0,
        'satellite_catalogue_ready': 'product_count' in sat,
        'external_submission_ready': False,
        'reason_external_submission_false': 'Controlled-review beta until source relevance, scientific QA, weather/wind validation, satellite diagnostics and independent review gates pass.'
    }
    (report_dir/'evidence_readiness_gates.json').write_text(json.dumps(gates,indent=2),encoding='utf-8')
    # master manifest
    manifest={'run_ts':ts,'project':cfg.get('project_name','AQ26'),'report_dir':str(report_dir),'controlled_use_boundary':cfg.get('controlled_use_boundary'), 'harvest_summary':live, 'redaction_audit':red, 'readiness_gates':gates, 'artifacts':[]}
    for p in sorted(report_dir.rglob('*')):
        if p.is_file(): manifest['artifacts'].append({'path':str(p),'size_bytes':p.stat().st_size,'sha256':sha256_file(p)})
    mf=report_dir/f'AQ26_WEEKLY_MASTER_MANIFEST_{ts}.json'; mf.write_text(json.dumps(manifest,indent=2,default=str),encoding='utf-8')
    zip_path=out/'weekly_reports'/f'AQ26_WEEKLY_COMPREHENSIVE_REPORT_{ts}.zip'
    with zipfile.ZipFile(zip_path,'w',zipfile.ZIP_DEFLATED) as z:
        for p in report_dir.rglob('*'):
            if p.is_file(): z.write(p, p.relative_to(report_dir.parent))
    (report_dir/'ZIP_SHA256.txt').write_text(f'{sha256_file(zip_path)}  {zip_path.name}\n',encoding='utf-8')
    print(json.dumps({'report_dir':str(report_dir),'pdf':str(pdf),'zip':str(zip_path),'zip_sha256':sha256_file(zip_path)}, indent=2))
if __name__=='__main__': main()
