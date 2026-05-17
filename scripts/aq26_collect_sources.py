#!/usr/bin/env python3
from __future__ import annotations
import argparse, csv, datetime as dt, hashlib, json, os, re, sys, time, urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests, yaml

SECRET_KEYS = re.compile(r"(?i)(api[_-]?key|apikey|token|password|secret|client_secret|authorization|bearer|key)=([^&\s]+)")
SUSPECT = re.compile(r"(?i)(api[_-]?key|apikey|token|password|client_secret|bearer\s+[a-z0-9._\-]+)")
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "AQ26-weekly-evidence-harvest/1.0 (controlled-review; provenance; no endorsement claims)"})


def now_utc(): return dt.datetime.now(dt.timezone.utc)
def iso_utc(): return now_utc().isoformat()
def uk_time(ts=None):
    try:
        from zoneinfo import ZoneInfo
        return (ts or now_utc()).astimezone(ZoneInfo("Europe/London"))
    except Exception:
        return ts or now_utc()
def run_ts(): return now_utc().strftime("%Y%m%dT%H%M%SZ")
def sha256_bytes(b: bytes) -> str: return hashlib.sha256(b).hexdigest()
def sha256_file(p: Path) -> str:
    h=hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024), b''): h.update(chunk)
    return h.hexdigest()
def mkdir(p): Path(p).mkdir(parents=True, exist_ok=True); return Path(p)

def redact_value(v: Any) -> Any:
    if v is None: return v
    s = str(v)
    if len(s) <= 4: return "***" if s else s
    return f"***REDACTED_len_{len(s)}"

def redact_url(url: str) -> str:
    try:
        parts = urllib.parse.urlsplit(url)
        q = urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
        red = []
        for k,v in q:
            if re.search(r"(?i)(api|key|token|secret|password|auth)", k): red.append((k, redact_value(v)))
            else: red.append((k,v))
        return urllib.parse.urlunsplit((parts.scheme, parts.netloc, parts.path, urllib.parse.urlencode(red), parts.fragment))
    except Exception:
        return SECRET_KEYS.sub(lambda m: f"{m.group(1)}=***REDACTED***", url)

def safe_text(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: (redact_value(v) if re.search(r"(?i)(api|key|token|secret|password|auth)", str(k)) else safe_text(v)) for k,v in obj.items()}
    if isinstance(obj, list): return [safe_text(x) for x in obj]
    if isinstance(obj, str):
        return SECRET_KEYS.sub(lambda m: f"{m.group(1)}=***REDACTED***", obj)
    return obj

def write_json(path: Path, obj: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(safe_text(obj), indent=2, ensure_ascii=False, default=str), encoding='utf-8')
    return path

def fetch_json(url: str, *, params: Optional[dict]=None, headers: Optional[dict]=None, timeout=30, method='GET', json_body=None) -> tuple[dict, int, bytes, str]:
    r = SESSION.request(method, url, params=params, headers=headers, json=json_body, timeout=timeout)
    body = r.content
    try: data = r.json()
    except Exception: data = {"_text": body[:5000].decode('utf-8','replace')}
    return data, r.status_code, body, r.headers.get('content-type','')

def source_record(source_name, source_type, url, query, status, http_status, output_path, body: bytes|None, record_count=0, error='', notes='', extra=None):
    t = now_utc(); uk=uk_time(t)
    rec = {
        "run_ts": RUN_TS, "source_name": source_name, "source_type": source_type,
        "url": redact_url(url or ''), "query": query, "status": status, "http_status": http_status,
        "retrieved_at_utc": t.isoformat(), "retrieved_at_uk": uk.isoformat(), "date_uk": uk.strftime('%d/%m/%Y'),
        "output_path": str(output_path) if output_path else '',
        "sha256": sha256_file(Path(output_path)) if output_path and Path(output_path).exists() else (sha256_bytes(body) if body else ''),
        "bytes": int(Path(output_path).stat().st_size) if output_path and Path(output_path).exists() else (len(body) if body else 0),
        "record_count": int(record_count or 0), "error": str(error or ''), "notes": notes or ''
    }
    if extra: rec.update(safe_text(extra))
    RECORDS.append(rec)
    with SOURCE_JSONL.open('a', encoding='utf-8') as f: f.write(json.dumps(rec, ensure_ascii=False, default=str) + '\n')
    return rec

def count_records(obj: Any) -> int:
    if isinstance(obj, dict):
        for k in ['articles','results','features','value','items','filings','data','records']:
            if isinstance(obj.get(k), list): return len(obj[k])
        return 1 if obj else 0
    if isinstance(obj, list): return len(obj)
    return 0

def get_secret(*names):
    for n in names:
        v=os.getenv(n)
        if v: return v
    return ''

def harvest_news(cfg, lookback):
    outdir = mkdir(OUT/'03_news_context'/'raw')
    all_articles=[]
    start = (now_utc() - dt.timedelta(days=lookback)).strftime('%Y-%m-%d')
    for term in cfg.get('search_terms', []):
        if key:=get_secret('NEWS_API_KEY','NEWSAPI_KEY'):
            url='https://newsapi.org/v2/everything'; params={'q':term,'language':'en','sortBy':'publishedAt','pageSize':50,'from':start,'apiKey':key}
            try:
                data, code, body, ctype = fetch_json(url, params=params)
                p=write_json(outdir/f"newsapi_{slug(term)}_{RUN_TS}.json", data)
                all_articles += data.get('articles',[]) if isinstance(data,dict) else []
                source_record('NewsAPI everything','news_api', requests.Request('GET',url,params=params).prepare().url, term, 'ok' if code<400 else 'error', code, p, body, count_records(data))
            except Exception as e: source_record('NewsAPI everything','news_api',url,term,'error',None,None,None,0,repr(e))
        if key:=get_secret('NEWS_DATA_IO_KEY','NEWSDATA_IO_KEY'):
            url='https://newsdata.io/api/1/news'; params={'apikey':key,'q':term,'language':'en','size':10}
            try:
                data, code, body, ctype = fetch_json(url, params=params)
                p=write_json(outdir/f"newsdata_{slug(term)}_{RUN_TS}.json", data)
                all_articles += data.get('results',[]) if isinstance(data,dict) else []
                source_record('NewsData.io news','news_api', requests.Request('GET',url,params=params).prepare().url, term, 'ok' if code<400 else 'error', code, p, body, count_records(data))
            except Exception as e: source_record('NewsData.io news','news_api',url,term,'error',None,None,None,0,repr(e))
        # GDELT, no key, rate limited but useful
        url='https://api.gdeltproject.org/api/v2/doc/doc'; params={'query':term,'mode':'ArtList','format':'json','maxrecords':50,'sort':'HybridRel','startdatetime':(now_utc()-dt.timedelta(days=lookback)).strftime('%Y%m%d%H%M%S')}
        try:
            time.sleep(0.25)
            data, code, body, ctype = fetch_json(url, params=params, timeout=20)
            p=write_json(outdir/f"gdelt_{slug(term)}_{RUN_TS}.json", data)
            all_articles += data.get('articles',[]) if isinstance(data,dict) else []
            source_record('GDELT document API','news_api', requests.Request('GET',url,params=params).prepare().url, term, 'ok' if code<400 else 'error', code, p, body, count_records(data))
        except Exception as e: source_record('GDELT document API','news_api',url,term,'error',None,None,None,0,repr(e))
    p=write_json(OUT/'03_news_context'/'news_articles.json', {"run_ts":RUN_TS,"count":len(all_articles),"articles":all_articles})
    source_record('Combined news articles','news_combined',str(p),'all terms','ok',None,p,None,len(all_articles))

def harvest_ground_weather(cfg):
    rawdir=mkdir(OUT/'04_ground_aq_providers'/'raw')
    calls=[]
    for site in cfg.get('sites',[]):
        lat,lon=site['lat'],site['lon']
        if token:=get_secret('WAQI_TOKEN'):
            url=f'https://api.waqi.info/feed/geo:{lat};{lon}/'; params={'token':token}
            try:
                data,code,body,ctype=fetch_json(url, params=params)
                p=write_json(rawdir/f"waqi_{site['id']}.json", data)
                source_record('WAQI geo feed','ground_aq',requests.Request('GET',url,params=params).prepare().url,site['id'],'ok' if code<400 else 'error',code,p,body,count_records(data), extra={'site_id':site['id']})
                calls.append({'provider':'waqi','site_id':site['id'],'status':code,'path':str(p),'sha256':sha256_file(p)})
            except Exception as e: source_record('WAQI geo feed','ground_aq',url,site['id'],'error',None,None,None,0,repr(e), extra={'site_id':site['id']})
        if key:=get_secret('OPENWEATHER_KEY','OW_KEY'):
            for endpoint, name in [('https://api.openweathermap.org/data/2.5/weather','weather_current'),('https://api.openweathermap.org/data/2.5/air_pollution','air_pollution_current')]:
                params={'lat':lat,'lon':lon,'appid':key,'units':'metric'}
                try:
                    data,code,body,ctype=fetch_json(endpoint, params=params)
                    p=write_json(rawdir/f"openweather_{name}_{site['id']}.json", data)
                    source_record(f'OpenWeather {name}','weather_or_aq',requests.Request('GET',endpoint,params=params).prepare().url,site['id'],'ok' if code<400 else 'error',code,p,body,count_records(data), extra={'site_id':site['id']})
                except Exception as e: source_record(f'OpenWeather {name}','weather_or_aq',endpoint,site['id'],'error',None,None,None,0,repr(e), extra={'site_id':site['id']})
    write_json(OUT/'04_ground_aq_providers'/'provider_calls.json', {'run_ts':RUN_TS,'calls':calls})

    # Met Office configured endpoint: intentionally flexible because DataHub subscriptions differ.
    met_key=get_secret('METOFFICE_API_KEY','MET_OFFICE_KEY')
    met_endpoint=get_secret('MET_OFFICE_LAND_OBSERVATIONS')
    if met_key and met_endpoint:
        url=met_endpoint.strip()
        headers={'apikey':met_key}
        try:
            data,code,body,ctype=fetch_json(url, headers=headers, timeout=30)
            p=write_json(OUT/'05_metoffice_datahub_weather'/'metoffice_land_observations.json', data)
            source_record('Met Office DataHub configured endpoint','weather',url,'configured endpoint','ok' if code<400 else 'error',code,p,body,count_records(data))
        except Exception as e: source_record('Met Office DataHub configured endpoint','weather',url,'configured endpoint','error',None,None,None,0,repr(e))

def harvest_official(cfg, download=False):
    outdir=mkdir(OUT/'06_official_filings')
    filings=[]
    for term in cfg.get('search_terms',[]):
        # GOV.UK content API search
        url='https://www.gov.uk/api/search.json'; params={'q':term,'count':50,'order':'-public_timestamp'}
        try:
            data,code,body,ctype=fetch_json(url, params=params)
            p=write_json(outdir/'raw'/f"govuk_{slug(term)}_{RUN_TS}.json", data)
            for r in data.get('results',[]) if isinstance(data,dict) else []:
                filings.append({'source':'GOV.UK','query':term,'title':r.get('title'),'url':urllib.parse.urljoin('https://www.gov.uk', r.get('link','')),'raw':safe_text(r)})
            source_record('GOV.UK search API','official_search',requests.Request('GET',url,params=params).prepare().url,term,'ok' if code<400 else 'error',code,p,body,count_records(data))
        except Exception as e: source_record('GOV.UK search API','official_search',url,term,'error',None,None,None,0,repr(e))
        # data.gov.uk CKAN
        url='https://ckan.publishing.service.gov.uk/api/3/action/package_search'; params={'q':term,'rows':50}
        try:
            data,code,body,ctype=fetch_json(url, params=params)
            p=write_json(outdir/'raw'/f"datagovuk_{slug(term)}_{RUN_TS}.json", data)
            results=((data.get('result') or {}).get('results') or []) if isinstance(data,dict) else []
            for r in results:
                filings.append({'source':'data.gov.uk','query':term,'title':r.get('title') or r.get('name'),'url':r.get('url') or '', 'raw':safe_text(r)})
            source_record('data.gov.uk CKAN package_search','official_search',requests.Request('GET',url,params=params).prepare().url,term,'ok' if code<400 else 'error',code,p,body,len(results))
        except Exception as e: source_record('data.gov.uk CKAN package_search','official_search',url,term,'error',None,None,None,0,repr(e))
    for url in cfg.get('official_watch_urls',[]):
        try:
            r=SESSION.get(url,timeout=25)
            body=r.content
            p=outdir/'watch_pages'/f"watch_{slug(url)}_{RUN_TS}.html"; p.parent.mkdir(parents=True,exist_ok=True); p.write_bytes(body)
            filings.append({'source':'watch_url','query':'official_watch_urls','title':url,'url':url,'raw':{'status':r.status_code,'content_type':r.headers.get('content-type')}})
            source_record('Official watch URL','official_watch',url,url,'ok' if r.status_code<400 else 'error',r.status_code,p,body,1)
        except Exception as e: source_record('Official watch URL','official_watch',url,url,'error',None,None,None,0,repr(e))
    # relevance scoring (deterministic, transparent)
    important=re.compile(r'(?i)(newhaven|veolia|incinerator|energy recovery|environment agency|annual monitoring|BV8067IL|permit|emissions|pollutant|waste)')
    for f in filings:
        text=' '.join(str(f.get(k,'')) for k in ['title','url','query'])
        f['relevance_score']=sum(1 for _ in important.finditer(text))
        f['relevance_class']='candidate_relevant' if f['relevance_score']>=2 else ('requires_review' if f['relevance_score']==1 else 'likely_irrelevant')
    write_json(outdir/'official_filing_index.json', {'run_ts':RUN_TS,'filing_count':len(filings),'filings':filings})
    changed=[]
    hist_dir=mkdir(OUT/'source_history')
    for f in filings:
        fp=hashlib.sha256((f.get('source','')+'|'+f.get('title','')+'|'+f.get('url','')).encode()).hexdigest()
        changed.append({'change_status':'seen_this_run','fingerprint':fp,**{k:f.get(k) for k in ['title','url','source','query','relevance_score','relevance_class']}})
    write_json(outdir/'new_or_changed_source_index.json', {'run_ts':RUN_TS,'items':changed})

def harvest_satellite(cfg, lookback):
    sat=cfg.get('satellite',{}); bbox=cfg.get('aoi',{}).get('bbox')
    outdir=mkdir(OUT/'07_satellite_cdse'/'raw')
    # STAC search with real bbox/date window and fallbacks
    for days in sat.get('fallback_windows_days',[lookback,30,90]):
        start=(now_utc()-dt.timedelta(days=int(days))).strftime('%Y-%m-%dT%H:%M:%SZ')
        end=now_utc().strftime('%Y-%m-%dT%H:%M:%SZ')
        body={'bbox':bbox,'datetime':f'{start}/{end}','limit':50,'collections':sat.get('collections',['SENTINEL-5P'])}
        url=sat.get('stac_url')
        try:
            data,code,raw,ctype=fetch_json(url, method='POST', json_body=body, timeout=35)
            p=write_json(outdir/f"copernicus_stac_{days}d_{RUN_TS}.json", {'request':body,'response':data})
            cnt=count_records(data)
            source_record('Copernicus Data Space STAC search','satellite_metadata',url,json.dumps(body),'ok' if code<400 else 'error',code,p,raw,cnt,notes=f'fallback_window_days={days}')
            if cnt: break
        except Exception as e: source_record('Copernicus Data Space STAC search','satellite_metadata',url,json.dumps(body),'error',None,None,None,0,repr(e),notes=f'fallback_window_days={days}')
    # OData product name searches, catalogue only (safe without auth for search in most cases)
    odata=sat.get('odata_url')
    products=[]
    for prod in sat.get('products',[]):
        start=(now_utc()-dt.timedelta(days=lookback)).strftime('%Y-%m-%dT%H:%M:%S.000Z')
        filt=f"contains(Name,'{prod}') and ContentDate/Start ge {start}"
        params={'$filter':filt,'$top':'50','$orderby':'ContentDate/Start desc'}
        try:
            data,code,raw,ctype=fetch_json(odata, params=params, timeout=35)
            p=write_json(outdir/f"copernicus_odata_{prod}_{RUN_TS}.json", data)
            cnt=count_records(data); products += data.get('value',[]) if isinstance(data,dict) else []
            source_record('Copernicus Data Space OData product search','satellite_metadata',requests.Request('GET',odata,params=params).prepare().url,prod,'ok' if code<400 else 'error',code,p,raw,cnt)
        except Exception as e: source_record('Copernicus Data Space OData product search','satellite_metadata',odata,prod,'error',None,None,None,0,repr(e))
    write_json(OUT/'07_satellite_cdse'/'satellite_catalogue_metadata.json', {'run_ts':RUN_TS,'bbox':bbox,'product_count':len(products),'products':safe_text(products[:200])})

def build_ledger():
    rows=[]
    for p in sorted(OUT.rglob('*')):
        if p.is_file(): rows.append({'path':str(p),'size_bytes':p.stat().st_size,'sha256':sha256_file(p),'modified_utc':dt.datetime.fromtimestamp(p.stat().st_mtime,dt.timezone.utc).isoformat()})
    ledger=mkdir(OUT/'99_integrity')/'AQ26_SHA256_LEDGER.csv'
    with ledger.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f, fieldnames=['path','size_bytes','sha256','modified_utc']); w.writeheader(); w.writerows(rows)
    write_json(OUT/'99_integrity'/'AQ26_SHA256_LEDGER.json', {'run_ts':RUN_TS,'count':len(rows),'files':rows})

def slug(s): return re.sub(r'[^A-Za-z0-9_.-]+','_',str(s))[:90].strip('_') or 'item'

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--config',default='configs/aq26_weekly_sources.yml'); ap.add_argument('--lookback-days',type=int,default=None); ap.add_argument('--download-official-files',default='false')
    args=ap.parse_args(); cfg=yaml.safe_load(Path(args.config).read_text())
    global RUN_TS, OUT, RECORDS, SOURCE_JSONL
    RUN_TS=run_ts(); OUT=Path(cfg.get('output_root','outputs')); RECORDS=[]; SOURCE_JSONL=mkdir(OUT/'source_history')/'source_index.jsonl'
    lookback=args.lookback_days or int(cfg.get('lookback_days_default',14))
    mkdir(OUT/'00_live_harvest'/f'AQ26_LIVE_HARVEST_{RUN_TS}')
    harvest_news(cfg, lookback)
    harvest_ground_weather(cfg)
    harvest_official(cfg, str(args.download_official_files).lower()=='true')
    harvest_satellite(cfg, lookback)
    summary={
        'run_ts':RUN_TS,'project':cfg.get('project_name'),'controlled_use_boundary':cfg.get('controlled_use_boundary'),
        'lookback_days':lookback,'output_root':str(OUT),'source_record_count':len(RECORDS),'ok_count':sum(r['status']=='ok' for r in RECORDS),'error_count':sum(r['status']=='error' for r in RECORDS),
        'source_records':RECORDS,
        'secrets_status':{k:('SET_REDACTED_len_'+str(len(os.getenv(k,''))) if os.getenv(k) else 'EMPTY') for k in ['WAQI_TOKEN','OPENWEATHER_KEY','OW_KEY','NEWS_API_KEY','NEWS_DATA_IO_KEY','METOFFICE_API_KEY','MET_OFFICE_KEY','MET_OFFICE_LAND_OBSERVATIONS','OPENAQ_API_KEY','CDSE_ID','CDSE_SECRET','CDSE_USERNAME','CDSE_PASSWORD']}
    }
    write_json(OUT/'00_live_harvest'/'LATEST_HARVEST.json', summary)
    live_dir=OUT/'00_live_harvest'/f'AQ26_LIVE_HARVEST_{RUN_TS}'
    write_json(live_dir/f'AQ26_LIVE_HARVEST_MANIFEST_{RUN_TS}.json', summary)
    build_ledger()
    print(json.dumps({'run_ts':RUN_TS,'source_records':len(RECORDS),'ok':summary['ok_count'],'error':summary['error_count']}, indent=2))
if __name__=='__main__': main()
