#!/usr/bin/env python3
from __future__ import annotations
import argparse, datetime as dt, json
from pathlib import Path
HIGH=['bv8067','bv8067il','newhaven energy recovery facility','veolia newhaven','annual monitoring report','environment agency','permit variation','enforcement notice','emissions monitoring','incinerator annual monitoring']
POLL=['pm2.5','pm10','no2','nitrogen dioxide','so2','sulphur dioxide','sulfur dioxide','co','carbon monoxide','ozone','o3','hcho','formaldehyde','ch4','methane','aerosol','dioxin','furan','mercury','cadmium','heavy metals']
CTX=['newhaven','veolia','incinerator','energy recovery','waste','permit','emission']
def load(p): return json.loads(Path(p).read_text(encoding='utf-8')) if Path(p).exists() else {}
def write(p,obj): p=Path(p); p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(obj,indent=2,ensure_ascii=False,default=str),encoding='utf-8')
def classify(text):
    low=text.lower(); hh=[t for t in HIGH if t in low]; ph=[t for t in POLL if t in low]; ch=[t for t in CTX if t in low]; score=len(hh)*5+len(ph)*2+len(ch)
    level='high' if score>=12 or len(hh)>=2 else 'medium' if score>=5 or len(ch)>=2 else 'low' if score>0 else 'irrelevant_or_weak'
    return {'score':score,'level':level,'high_hits':hh,'pollutant_hits':ph,'context_hits':ch}
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--output-root',default='outputs'); args=ap.parse_args(); root=Path(args.output_root)
    filings=load(root/'06_official_filings'/'official_filing_index.json'); scored=[]
    for item in filings.get('filings',[]): scored.append({'title':item.get('title'),'url':item.get('url'),'source':item.get('source'),'query':item.get('query'),**classify(json.dumps(item,ensure_ascii=False))})
    scored.sort(key=lambda x:x['score'], reverse=True)
    news=load(root/'03_news_context'/'news_articles.json'); scored_news=[]
    for item in news.get('articles',[]): scored_news.append({'title':item.get('title') or item.get('name'),'url':item.get('url') or item.get('link'),'provider':item.get('_aq26_provider'),'query':item.get('_aq26_query'),**classify(json.dumps(item,ensure_ascii=False))})
    scored_news.sort(key=lambda x:x['score'], reverse=True)
    latest=load(root/'00_live_harvest'/'LATEST_HARVEST.json'); red=load(root/'99_integrity'/'redaction_audit.json'); sat=load(root/'07_satellite_cdse'/'satellite_catalogue_metadata.json')
    readiness={'created_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'automation_ready':True,'provenance_ready':(root/'source_history'/'source_index.jsonl').exists(),'redaction_ready':red.get('leak_count',999)==0,'metoffice_ready':any(r.get('source_name')=='Met Office DataHub land observations' and r.get('status')=='ok' for r in latest.get('source_records',[])),'official_filings_ready':any(r['level'] in ['high','medium'] for r in scored),'satellite_catalogue_ready':sat.get('product_count',0)>0,'satellite_extraction_ready':False,'ground_aq_ready':any(r.get('source_type')=='ground_aq' and r.get('status')=='ok' for r in latest.get('source_records',[])),'external_submission_ready':False,'blocking_reasons':['Satellite pollutant extraction and QA are not implemented yet.','Official filing candidates require human/legal relevance review before external use.','Health interpretation requires correct averaging-period comparators and exposure context.']}
    output={'created_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'filing_count':len(scored),'news_count':len(scored_news),'high_priority_filings':[x for x in scored if x['level']=='high'][:100],'medium_priority_filings':[x for x in scored if x['level']=='medium'][:150],'high_priority_news':[x for x in scored_news if x['level']=='high'][:100],'medium_priority_news':[x for x in scored_news if x['level']=='medium'][:150],'source_errors':[r for r in latest.get('source_records',[]) if r.get('status')=='error'],'readiness_gates':readiness,'methods_alignment':{'dominici':'Guarded causal language, confounder notes and exposure-window readiness.','martin':'Satellite catalogue coverage tracked; extraction and ground fusion remain next.','brauer':'Multi-source exposure-screening registry, not burden estimation yet.','anenberg':'NO2/SO2/CO/HCHO/O3/CH4/AER_AI families prioritised.','damoulas':'Target/control graph, completeness and scoring prepare spatiotemporal modelling.'}}
    write(root/'12_scoring'/'evidence_priority_scores.json',output); write(root/'12_scoring'/'evidence_readiness_gates.json',readiness); print(json.dumps({'high_priority_filings':len(output['high_priority_filings']),'medium_priority_filings':len(output['medium_priority_filings']),'metoffice_ready':readiness['metoffice_ready'],'external_submission_ready':False},indent=2))
if __name__=='__main__': main()
