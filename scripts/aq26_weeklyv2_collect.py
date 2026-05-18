#!/usr/bin/env python3
from __future__ import annotations
import argparse, csv, datetime as dt, hashlib, json, os, re, time, urllib.parse
from pathlib import Path
from typing import Any, Dict, List
import requests, yaml
try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo=None
RUN_TS=dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ'); RECORDS=[]; OPENAQ_REQUESTS=0; CAMS_REQUESTS=0; LAST_OPENAQ=LAST_CAMS=LAST_GDELT=0.0
def now_utc(): return dt.datetime.now(dt.timezone.utc)
def uk_time(t=None):
    t=t or now_utc(); return t.astimezone(ZoneInfo('Europe/London')) if ZoneInfo else t
def mkdir(p): p=Path(p); p.mkdir(parents=True, exist_ok=True); return p
def sha_file(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024), b''): h.update(b)
    return h.hexdigest()
def env_first(*names):
    for n in names:
        v=os.getenv(n,'')
        if v: return v.strip()
    return ''
def slug(s): return re.sub(r'[^A-Za-z0-9_.-]+','_',str(s)).strip('_')[:120] or 'item'
def redact(s):
    if not s: return s
    try:
        u=urllib.parse.urlsplit(s)
        if u.query:
            pairs=urllib.parse.parse_qsl(u.query, keep_blank_values=True); red=[]
            for k,v in pairs: red.append((k,'***REDACTED***' if any(x in k.lower() for x in ['key','apikey','token','secret','password']) else v))
            s=urllib.parse.urlunsplit((u.scheme,u.netloc,u.path,urllib.parse.urlencode(red),u.fragment))
    except Exception: pass
    s=re.sub(r'(?i)(apikey|api_key|token|password|client_secret)=([^&\s]+)', r'\1=***REDACTED***', s)
    s=re.sub(r'(?i)(Bearer\s+)[A-Za-z0-9_\-.]{12,}', r'\1***REDACTED***', s)
    return s
def safe_json(x):
    if isinstance(x,dict): return {k:safe_json(v) for k,v in x.items()}
    if isinstance(x,list): return [safe_json(v) for v in x]
    if isinstance(x,str): return redact(x)
    return x
def write_json(p,obj): p=Path(p); mkdir(p.parent); p.write_text(json.dumps(safe_json(obj),indent=2,ensure_ascii=False,default=str),encoding='utf-8'); return p
def write_bytes(p,b): p=Path(p); mkdir(p.parent); p.write_bytes(b); return p
def full_url(url,params=None): return requests.Request('GET',url,params=params).prepare().url if params else url
def count_records(data):
    if isinstance(data,list): return len(data)
    if isinstance(data,dict):
        for k in ['articles','results','features','value','items','data','list']:
            if isinstance(data.get(k),list): return len(data[k])
        if isinstance(data.get('result'),dict): return count_records(data['result'])
    return 0
def add_record(name,typ,url,query,status,http_status,path=None,record_count=0,error='',notes=''):
    t=now_utc(); u=uk_time(t); row={'run_ts':RUN_TS,'source_name':name,'source_type':typ,'url':redact(url or ''),'query':query or '','status':status,'http_status':http_status,'retrieved_at_utc':t.isoformat(),'retrieved_at_uk':u.isoformat(),'date_uk':u.strftime('%d/%m/%Y'),'output_path':str(path).replace('\\','/') if path else '','sha256':sha_file(path) if path and Path(path).exists() else '','bytes':Path(path).stat().st_size if path and Path(path).exists() else 0,'record_count':int(record_count or 0),'error':redact(error or ''),'notes':notes or ''}
    RECORDS.append(row); return row
def request_get(url,params=None,headers=None,timeout=30):
    try:
        r=requests.get(url,params=params,headers=headers,timeout=timeout)
        try: data=r.json()
        except Exception: data=None
        err='' if r.ok else (json.dumps(data)[:700] if data is not None else r.text[:700])
        return data,r.status_code,r.content,err,dict(r.headers)
    except Exception as e: return None,None,json.dumps({'error':repr(e)}).encode(),repr(e),{}
def date_window(days):
    end=now_utc().date(); start=end-dt.timedelta(days=int(days)); return start.isoformat(), end.isoformat()
def metoffice_coord(v): return f'{float(v):.2f}'
def harvest_news(cfg,out,start_date):
    global LAST_GDELT
    raw=mkdir(out/'03_news_context'/'raw'); articles=[]; newsapi=env_first('NEWS_API_KEY'); newsdata=env_first('NEWS_DATA_IO_KEY')
    for q in cfg.get('news_queries',[]):
        if newsapi:
            url='https://newsapi.org/v2/everything'; params={'q':q,'language':'en','sortBy':'publishedAt','pageSize':50,'from':start_date,'apiKey':newsapi}
            data,hs,content,err,_=request_get(url,params=params); p=write_bytes(raw/f'newsapi_{slug(q)}_{RUN_TS}.json',content)
            add_record('NewsAPI everything','news_api',full_url(url,params),q,'ok' if hs and hs<400 else 'error',hs,p,count_records(data),err)
            if isinstance(data,dict) and isinstance(data.get('articles'),list):
                for item in data['articles']: item['_aq26_provider']='NewsAPI'; item['_aq26_query']=q; articles.append(item)
        if newsdata:
            url='https://newsdata.io/api/1/news'; params={'apikey':newsdata,'q':q,'language':'en','size':10}
            data,hs,content,err,_=request_get(url,params=params); p=write_bytes(raw/f'newsdata_{slug(q)}_{RUN_TS}.json',content)
            add_record('NewsData.io news','news_api',full_url(url,params),q,'ok' if hs and hs<400 else 'error',hs,p,count_records(data),err)
            if isinstance(data,dict) and isinstance(data.get('results'),list):
                for item in data['results']: item['_aq26_provider']='NewsData.io'; item['_aq26_query']=q; articles.append(item)
        elapsed=time.time()-LAST_GDELT
        if elapsed<12: time.sleep(12-elapsed)
        url='https://api.gdeltproject.org/api/v2/doc/doc'; params={'query':q,'mode':'ArtList','format':'json','maxrecords':50,'sort':'HybridRel'}
        data,hs,content,err,_=request_get(url,params=params,timeout=35); LAST_GDELT=time.time()
        if hs==429: time.sleep(20); data,hs,content,err,_=request_get(url,params=params,timeout=35); LAST_GDELT=time.time()
        p=write_bytes(raw/f'gdelt_{slug(q)}_{RUN_TS}.json',content); add_record('GDELT document API','news_api',full_url(url,params),q,'ok' if hs and hs<400 else 'error',hs,p,count_records(data),err)
    write_json(out/'03_news_context'/'news_articles.json',{'run_ts':RUN_TS,'count':len(articles),'articles':articles})
def harvest_ground_weather(cfg,out):
    raw=mkdir(out/'04_ground_aq_providers'/'raw'); waqi=env_first('WAQI_TOKEN'); ow=env_first('OPENWEATHER_KEY','OW_KEY'); met=env_first('MET_OFFICE_API_KEY','METOFFICE_API_KEY','MET_OFFICE_KEY')
    for site in cfg.get('sites',[]):
        sid,lat,lon=site['id'],site['lat'],site['lon']
        if waqi:
            url=f'https://api.waqi.info/feed/geo:{lat};{lon}/'; params={'token':waqi}; data,hs,content,err,_=request_get(url,params=params); p=write_bytes(raw/f'waqi_{sid}_{RUN_TS}.json',content); add_record('WAQI geospatial feed','ground_aq',full_url(url,params),sid,'ok' if hs and hs<400 else 'error',hs,p,count_records(data),err)
        if ow:
            url='https://api.openweathermap.org/data/2.5/weather'; params={'lat':lat,'lon':lon,'appid':ow,'units':'metric'}; data,hs,content,err,_=request_get(url,params=params); p=write_bytes(out/'05_weather'/'raw'/f'openweather_current_{sid}_{RUN_TS}.json',content); add_record('OpenWeather current weather','weather',full_url(url,params),sid,'ok' if hs and hs<400 else 'error',hs,p,count_records(data),err)
            url='https://api.openweathermap.org/data/2.5/air_pollution'; params={'lat':lat,'lon':lon,'appid':ow}; data,hs,content,err,_=request_get(url,params=params); p=write_bytes(raw/f'openweather_airpollution_{sid}_{RUN_TS}.json',content); add_record('OpenWeather air pollution','ground_aq',full_url(url,params),sid,'ok' if hs and hs<400 else 'error',hs,p,count_records(data),err)
    if met:
        focus=cfg.get('sites',[{'lat':50.796,'lon':0.055}])[0]; url='https://data.hub.api.metoffice.gov.uk/observation-land/1/nearest'; params={'lat':metoffice_coord(focus.get('lat',50.796)),'lon':metoffice_coord(focus.get('lon',0.055))}
        data,hs,content,err,_=request_get(url,params=params,headers={'apikey':met}); p=write_bytes(out/'05_metoffice_datahub_weather'/f'metoffice_land_observations_{RUN_TS}.json',content); add_record('Met Office DataHub land observations','weather',full_url(url,params),'newhaven_nearest','ok' if hs and hs<400 else 'error',hs,p,count_records(data),err,notes='apikey header; lat/lon rounded to 2dp')
def harvest_openaq(cfg,out):
    global OPENAQ_REQUESTS,LAST_OPENAQ
    if os.getenv('AQ26_OPENAQ_ENABLED','true').lower() not in ('1','true','yes','y'): add_record('OpenAQ controlled harvest','ground_aq','openaq://disabled','','skipped',None,None,0,notes='disabled by workflow input'); return
    ocfg=cfg.get('openaq',{})
    if not ocfg.get('enabled',True): add_record('OpenAQ controlled harvest','ground_aq','openaq://disabled','','skipped',None,None,0,notes='disabled in config'); return
    key=env_first('OPENAQ_API_KEY')
    if not key: add_record('OpenAQ controlled harvest','ground_aq','https://api.openaq.org','','skipped',None,None,0,notes='OPENAQ_API_KEY missing'); return
    base=ocfg.get('base_url','https://api.openaq.org').rstrip('/'); max_req=int(ocfg.get('max_requests_per_run',8)); min_wait=float(ocfg.get('min_seconds_between_requests',8)); headers={'X-API-Key':key,'User-Agent':ocfg.get('user_agent','AQ26-WeeklyV2-controlled-review/1.0'),'Accept':'application/json'}; raw=mkdir(out/'04_ground_aq_providers'/'openaq_raw'); stopped=False
    for site in cfg.get('sites',[]):
        if OPENAQ_REQUESTS>=max_req or stopped: break
        elapsed=time.time()-LAST_OPENAQ
        if elapsed<min_wait: time.sleep(min_wait-elapsed)
        url=f'{base}/v3/locations'; params={'coordinates':f"{site['lat']},{site['lon']}",'radius':int(ocfg.get('radius_m',25000)),'limit':int(ocfg.get('limit',100))}
        data,hs,content,err,hdrs=request_get(url,params=params,headers=headers,timeout=35); OPENAQ_REQUESTS+=1; LAST_OPENAQ=time.time(); p=write_bytes(raw/f"openaq_locations_{site['id']}_{RUN_TS}.json",content)
        add_record('OpenAQ v3 locations radius search','ground_aq',full_url(url,params),site['id'],'ok' if hs and hs<400 else 'error',hs,p,count_records(data),err,notes=f'strict cap {OPENAQ_REQUESTS}/{max_req}; no pagination')
        if hs in (401,403): stopped=True; add_record('OpenAQ safety stop','ground_aq',base,'auth_stop','skipped',hs,None,0,notes='OpenAQ returned auth/forbidden; stopped to protect key')
        if hs==429: stopped=True; add_record('OpenAQ safety stop','ground_aq',base,'rate_limit_stop','skipped',hs,None,0,notes=f"OpenAQ 429; stopped. Retry-After={hdrs.get('Retry-After','')}")
def harvest_cams(cfg,out,start_date,end_date):
    if os.getenv('AQ26_CAMS_ENABLED','true').lower() not in ('1','true','yes','y'): add_record('CAMS controlled harvest','atmospheric_model','cams://disabled','','skipped',None,None,0,notes='disabled by workflow input'); return
    key=env_first('CAMS_API_KEY'); base_url=env_first('CAMS_BASE_URL'); cams_cfg=cfg.get('cams',{})
    if not key: add_record('CAMS controlled harvest','atmospheric_model','cams://missing-key','','skipped',None,None,0,notes='CAMS_API_KEY missing'); return
    if not base_url:
        p=write_json(out/'09_cams'/'cams_readiness.json',{'run_ts':RUN_TS,'status':'ready_key_present_no_endpoint','message':'CAMS_API_KEY is present. Add CAMS_BASE_URL secret for a specific HTTP endpoint, or add cdsapi/ecmwf client workflow later.','variables_requested':cams_cfg.get('variables',[]),'date_window':{'start':start_date,'end':end_date}})
        add_record('CAMS readiness','atmospheric_model','cams://configured-key-no-endpoint','readiness','ok',None,p,1,notes='No arbitrary CAMS call attempted'); return
    params={'start':start_date,'end':end_date,'apikey':key}; data,hs,content,err,_=request_get(base_url,params=params,timeout=45); p=write_bytes(out/'09_cams'/f'cams_response_{RUN_TS}.json',content); add_record('CAMS configured endpoint','atmospheric_model',full_url(base_url,params),'configured_endpoint','ok' if hs and hs<400 else 'error',hs,p,count_records(data),err,notes='CAMS_BASE_URL configured by secret')
def harvest_official(cfg,out):
    raw=mkdir(out/'06_official_filings'/'raw'); filings=[]
    for q in cfg.get('official_queries',[]):
        for source,url,params in [('GOV.UK','https://www.gov.uk/api/search.json',{'q':q,'count':50}),('data.gov.uk','https://ckan.publishing.service.gov.uk/api/3/action/package_search',{'q':q,'rows':50})]:
            data,hs,content,err,_=request_get(url,params=params); p=write_bytes(raw/f'{slug(source)}_{slug(q)}_{RUN_TS}.json',content); add_record(f'{source} search','official_search',full_url(url,params),q,'ok' if hs and hs<400 else 'error',hs,p,count_records(data),err)
            if source=='GOV.UK' and isinstance(data,dict):
                for row in data.get('results',[]): filings.append({'source':source,'query':q,'title':row.get('title'),'url':urllib.parse.urljoin('https://www.gov.uk',row.get('link','')),'raw':row})
            if source=='data.gov.uk' and isinstance(data,dict) and isinstance(data.get('result'),dict):
                for row in data['result'].get('results',[]): filings.append({'source':source,'query':q,'title':row.get('title'),'url':row.get('url') or '','raw':row})
    for item in cfg.get('watch_urls',[]):
        data,hs,content,err,_=request_get(item['url']); p=write_bytes(raw/f"watch_{slug(item.get('name','watch'))}_{RUN_TS}.html",content); add_record(item.get('name','Watch URL'),'official_watch_url',item['url'],item.get('name',''),'ok' if hs and hs<400 else 'error',hs,p,1 if hs and hs<400 else 0,err); filings.append({'source':'watch_url','query':item.get('name'),'title':item.get('name'),'url':item['url'],'raw_path':str(p)})
    high=[x.lower() for x in cfg.get('scoring',{}).get('high_terms',[])]; poll=[x.lower() for x in cfg.get('scoring',{}).get('pollutant_terms',[])]
    for f in filings:
        txt=json.dumps(f,ensure_ascii=False).lower(); hh=[x for x in high if x in txt]; pp=[x for x in poll if x in txt]; score=len(hh)*5+len(pp)*2; f['aq26_score']=score; f['aq26_priority']='high' if score>=10 else ('medium' if score>=4 else ('low' if score else 'weak_or_irrelevant')); f['aq26_high_hits']=hh; f['aq26_pollutant_hits']=pp
    write_json(out/'06_official_filings'/'official_filing_index.json',{'run_ts':RUN_TS,'filing_count':len(filings),'filings':filings}); write_json(out/'06_official_filings'/'official_priority_summary.json',{'run_ts':RUN_TS,'high':[f for f in filings if f.get('aq26_priority')=='high'][:100],'medium':[f for f in filings if f.get('aq26_priority')=='medium'][:150],'counts':{k:sum(1 for f in filings if f.get('aq26_priority')==k) for k in ['high','medium','low','weak_or_irrelevant']}})
def harvest_satellite(cfg,out,start_date,end_date):
    raw=mkdir(out/'07_satellite_cdse'/'raw'); scfg=cfg.get('satellite',{}); bbox=scfg.get('bbox',[-0.15,50.68,0.35,50.95]); meta={'run_ts':RUN_TS,'bbox':bbox,'start_date':start_date,'end_date':end_date,'odata':[],'product_count':0,'extraction_ready':False}; base='https://catalogue.dataspace.copernicus.eu/odata/v1/Products'
    for product in scfg.get('odata_products',[]):
        flt=f"contains(Name,'S5P') and contains(Name,'{product}') and ContentDate/Start ge {start_date}T00:00:00.000Z and ContentDate/Start le {end_date}T23:59:59.000Z"; params={'$filter':flt,'$top':int(scfg.get('max_records_per_product',50)),'$orderby':'ContentDate/Start desc'}; data,hs,content,err,_=request_get(base,params=params,timeout=35); p=write_bytes(raw/f'copernicus_odata_{product}_{RUN_TS}.json',content); c=count_records(data); meta['odata'].append({'product':product,'http_status':hs,'count':c,'path':str(p),'bbox_context':bbox}); meta['product_count']+=c; add_record('Copernicus Data Space OData product search','satellite_metadata',full_url(base,params),product,'ok' if hs and hs<400 else 'error',hs,p,c,err,notes='catalogue only; not pollutant extraction')
    write_json(out/'07_satellite_cdse'/'satellite_catalogue_metadata.json',meta); write_json(out/'07_satellite_cdse'/'satellite_extraction_plan.json',{'run_ts':RUN_TS,'status':'planned_not_executed','products':scfg.get('odata_products',[]),'next_stage':'download selected products, extract variables, apply QA flags, align with wind sector and ground/control sites'})
def harvest_gdrive(out):
    if os.getenv('AQ26_SYNC_GOOGLE_DRIVE','true').lower() not in ('1','true','yes','y'): add_record('Google Drive inventory','gdrive','gdrive://disabled','','skipped',None,None,0); return
    folder_id=env_first('GDRIVE_FOLDER_ID'); cred=env_first('GDRIVE_SERVICE_ACCOUNT','GDRIVE_SERVICE_ACCOUNT_JSON','GDRIVE_CREDENTIALS')
    if not folder_id or not cred: add_record('Google Drive inventory','gdrive','gdrive://missing','','skipped',None,None,0,notes='missing folder id or service account'); return
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        info=json.loads(cred); creds=service_account.Credentials.from_service_account_info(info,scopes=['https://www.googleapis.com/auth/drive.readonly']); svc=build('drive','v3',credentials=creds,cache_discovery=False); files=[]; queue=[(folder_id,'ROOT',0)]; seen=set(); max_files=5000 if os.getenv('AQ26_RECURSIVE_DRIVE_SCAN','true').lower() in ('1','true','yes','y') else 1000
        while queue and len(files)<max_files:
            fid,path_prefix,depth=queue.pop(0)
            if fid in seen or depth>7: continue
            seen.add(fid); token=None
            while True:
                resp=svc.files().list(q=f"'{fid}' in parents and trashed=false",fields='nextPageToken, files(id,name,mimeType,modifiedTime,createdTime,size,md5Checksum,webViewLink,parents,shortcutDetails)',pageSize=1000,pageToken=token,supportsAllDrives=True,includeItemsFromAllDrives=True).execute()
                for item in resp.get('files',[]):
                    path=f"{path_prefix}/{item.get('name','')}"; is_folder=item.get('mimeType')=='application/vnd.google-apps.folder'; is_shortcut=item.get('mimeType')=='application/vnd.google-apps.shortcut'; files.append({'path':path,'id_hash':hashlib.sha256(item.get('id','').encode()).hexdigest()[:12],'name':item.get('name'),'mimeType':item.get('mimeType'),'modifiedTime':item.get('modifiedTime'),'createdTime':item.get('createdTime'),'size':item.get('size'),'md5Checksum':item.get('md5Checksum'),'webViewLink':item.get('webViewLink'),'depth':depth+1,'is_folder':is_folder,'is_shortcut':is_shortcut})
                    if is_folder: queue.append((item['id'],path,depth+1))
                    if is_shortcut:
                        sd=item.get('shortcutDetails') or {}
                        if sd.get('targetId') and sd.get('targetMimeType')=='application/vnd.google-apps.folder': queue.append((sd['targetId'],path+' -> shortcut_target',depth+1))
                    if len(files)>=max_files: break
                token=resp.get('nextPageToken')
                if not token or len(files)>=max_files: break
        p=write_json(out/'08_gdrive_snapshot'/'gdrive_recursive_inventory.json',{'run_ts':RUN_TS,'file_count':len(files),'files':files,'max_files':max_files}); add_record('Google Drive recursive inventory','gdrive',f'gdrive://{folder_id}','recursive','ok',None,p,len(files),notes='metadata only; file IDs hashed')
    except Exception as e:
        p=write_json(out/'08_gdrive_snapshot'/'gdrive_error.json',{'error':repr(e)}); add_record('Google Drive recursive inventory','gdrive',f'gdrive://{folder_id}','recursive','error',None,p,0,repr(e))
def build_backfill_and_gates(cfg,out,start_date,end_date):
    expected=['news_api','ground_aq','weather','official_search','official_watch_url','satellite_metadata','gdrive','atmospheric_model']; observed={k:any(r.get('source_type')==k and r.get('status')=='ok' for r in RECORDS) for k in expected}; gates={'automation_ready':True,'provenance_ready':True,'redaction_ready':None,'metoffice_ready':any(r['source_name']=='Met Office DataHub land observations' and r['status']=='ok' for r in RECORDS),'ground_aq_ready':observed['ground_aq'],'openaq_ready':any(r['source_name'].startswith('OpenAQ') and r['status']=='ok' for r in RECORDS),'cams_ready':any(r['source_type']=='atmospheric_model' and r['status']=='ok' for r in RECORDS),'satellite_catalogue_ready':observed['satellite_metadata'],'satellite_extraction_ready':False,'official_filings_ready':observed['official_search'],'drive_ready':observed['gdrive'],'external_submission_ready':False,'blocking_reasons':['External submission remains false until satellite pollutant extraction, official document review, ground QA, wind-sector analysis and uncertainty gates pass.']}; missing=[{'stream':k,'status':'missing_or_failed','priority':'high' if k in ['ground_aq','weather','satellite_metadata'] else 'medium'} for k,v in observed.items() if not v]; write_json(out/'11_backfill'/'missing_date_backfill_plan.json',{'run_ts':RUN_TS,'window':{'start':start_date,'end':end_date},'missing_count':len(missing),'missing':missing}); write_json(out/'12_scoring'/'evidence_readiness_gates.json',gates); write_json(out/'12_scoring'/'evidence_priority_scores.json',{'run_ts':RUN_TS,'methods_alignment':{'dominici':'Causal language guarded; exposure/confounder/backfill readiness only.','martin':'Satellite catalogue supports remote-sensing context; extraction and ground-fusion next.','brauer':'Multi-source exposure-screening registry; no health-burden attribution yet.','anenberg':'NO2/SO2/CO/HCHO/O3/CH4/AER_AI trace-gas families prioritised.','damoulas':'Target/control graph, Drive inventory, gaps and alerts support digital-twin readiness.'}})
def finish(out,cfg,start_date,end_date):
    mkdir(out/'source_history')
    with (out/'source_history'/'source_index.jsonl').open('a',encoding='utf-8') as f:
        for r in RECORDS: f.write(json.dumps(safe_json(r),ensure_ascii=False)+'\n')
    latest={'run_ts':RUN_TS,'date_window':{'start':start_date,'end':end_date},'project':cfg.get('project',{}).get('name','SCCNEXUS AirQuality26 WeeklyV2'),'controlled_use_boundary':cfg.get('project',{}).get('controlled_use_boundary',''),'source_record_count':len(RECORDS),'ok_count':sum(1 for r in RECORDS if r['status']=='ok'),'error_count':sum(1 for r in RECORDS if r['status']=='error'),'skipped_count':sum(1 for r in RECORDS if r['status']=='skipped'),'source_records':RECORDS}; write_json(out/'00_weeklyv2'/'LATEST_WEEKLYV2.json',latest); write_json(out/'00_live_harvest'/'LATEST_HARVEST.json',latest); run_dir=mkdir(out/'00_weeklyv2'/f'AQ26_WEEKLYV2_{RUN_TS}'); write_json(run_dir/f'AQ26_WEEKLYV2_MANIFEST_{RUN_TS}.json',latest)
    if RECORDS:
        with (run_dir/f'AQ26_WEEKLYV2_SOURCE_RECORDS_{RUN_TS}.csv').open('w',newline='',encoding='utf-8') as f:
            w=csv.DictWriter(f,fieldnames=list(RECORDS[0].keys())); w.writeheader(); w.writerows(RECORDS)
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--config',default='configs/aq26_weekly_v2_sources.yml'); ap.add_argument('--output-root',default='outputs'); ap.add_argument('--lookback-days',default='14'); args=ap.parse_args(); out=Path(args.output_root); mkdir(out); cfg=yaml.safe_load(Path(args.config).read_text(encoding='utf-8')); start_date,end_date=date_window(int(args.lookback_days)); harvest_news(cfg,out,start_date); harvest_ground_weather(cfg,out); harvest_openaq(cfg,out); harvest_cams(cfg,out,start_date,end_date); harvest_official(cfg,out); harvest_satellite(cfg,out,start_date,end_date); harvest_gdrive(out); build_backfill_and_gates(cfg,out,start_date,end_date); finish(out,cfg,start_date,end_date); print(json.dumps({'run_ts':RUN_TS,'records':len(RECORDS),'ok':sum(1 for r in RECORDS if r['status']=='ok'),'errors':sum(1 for r in RECORDS if r['status']=='error'),'skipped':sum(1 for r in RECORDS if r['status']=='skipped')},indent=2))
if __name__=='__main__': main()
