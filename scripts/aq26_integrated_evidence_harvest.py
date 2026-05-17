#!/usr/bin/env python3
"""
AQ26 integrated evidence harvest - Met Office coordinate fix version.

Key fixes:
- Met Office nearest endpoint now uses lat/lon, not latitude/longitude.
- GDELT calls are throttled to respect one request every 5 seconds.
- MET_OFFICE_LAND_OBSERVATIONS is used only if it is a full URL.
- Source URLs are redacted before being written.
"""

from __future__ import annotations
import argparse, csv, datetime as dt, hashlib, json, os, re, time, urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import requests, yaml

try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None

SOURCE_RECORDS: List[Dict[str, Any]] = []
RUN_TS = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
LAST_GDELT_CALL = 0.0

def now_utc(): return dt.datetime.now(dt.timezone.utc)
def uk(t=None): 
    t=t or now_utc()
    return t.astimezone(ZoneInfo("Europe/London")) if ZoneInfo else t
def mkdir(p): Path(p).mkdir(parents=True, exist_ok=True); return Path(p)
def sha_file(p):
    h=hashlib.sha256()
    with Path(p).open("rb") as f:
        for b in iter(lambda:f.read(1024*1024), b""): h.update(b)
    return h.hexdigest()
def slug(s): return re.sub(r"[^A-Za-z0-9_.-]+","_",str(s)).strip("_")[:100] or "item"
def env(*names):
    for n in names:
        v=os.getenv(n,"")
        if v: return v.strip()
    return ""
def redact(s):
    if not s: return s
    try:
        u=urllib.parse.urlsplit(s)
        if u.query:
            pairs=urllib.parse.parse_qsl(u.query, keep_blank_values=True)
            pairs=[(k, "***REDACTED***" if any(x in k.lower() for x in ["key","apikey","token","secret","password"]) else v) for k,v in pairs]
            s=urllib.parse.urlunsplit((u.scheme,u.netloc,u.path,urllib.parse.urlencode(pairs),u.fragment))
    except Exception: pass
    return re.sub(r"(?i)(apikey|api_key|token|password|client_secret)=([^&\s]+)", r"\1=***REDACTED***", s)
def safe_json(x):
    if isinstance(x, dict): return {k:safe_json(v) for k,v in x.items()}
    if isinstance(x, list): return [safe_json(v) for v in x]
    if isinstance(x, str): return redact(x)
    return x
def write_json(p,obj):
    p=Path(p); mkdir(p.parent); p.write_text(json.dumps(safe_json(obj),indent=2,ensure_ascii=False,default=str),encoding="utf-8"); return p
def write_bytes(p,b):
    p=Path(p); mkdir(p.parent); p.write_bytes(b); return p
def count(data):
    if isinstance(data, list): return len(data)
    if isinstance(data, dict):
        for k in ["articles","results","features","value","items","data","list"]:
            if isinstance(data.get(k), list): return len(data[k])
        if isinstance(data.get("result"), dict): return count(data["result"])
    return 0
def req(url, params=None, headers=None, timeout=30):
    try:
        r=requests.get(url,params=params,headers=headers,timeout=timeout)
        try: data=r.json()
        except Exception: data=None
        err="" if r.ok else (json.dumps(data)[:700] if data is not None else r.text[:700])
        return data,r.status_code,r.content,err
    except Exception as e:
        return None,None,json.dumps({"error":repr(e)}).encode(),repr(e)
def rec(name,typ,url,query,status,http,p,c,error="",notes=""):
    t=now_utc(); u=uk(t)
    item={"run_ts":RUN_TS,"source_name":name,"source_type":typ,"url":redact(url),"query":query,"status":status,"http_status":http,"retrieved_at_utc":t.isoformat(),"retrieved_at_uk":u.isoformat(),"date_uk":u.strftime("%d/%m/%Y"),"output_path":str(p).replace("\\","/") if p else "", "sha256":sha_file(p) if p and Path(p).exists() else "", "bytes":Path(p).stat().st_size if p and Path(p).exists() else 0, "record_count":int(c or 0),"error":redact(error or ""),"notes":notes}
    SOURCE_RECORDS.append(item); return item
def fullurl(url,params): return requests.Request("GET",url,params=params).prepare().url

def window(lookback,start,end):
    if start:
        s=dt.date.fromisoformat(start); e=dt.date.fromisoformat(end) if end else now_utc().date()
    else:
        e=now_utc().date(); s=e-dt.timedelta(days=int(lookback))
    return s.isoformat(), e.isoformat()

def harvest_news(cfg,out,start):
    global LAST_GDELT_CALL
    articles=[]
    raw=mkdir(out/"03_news_context"/"raw")
    newsapi=env("NEWS_API_KEY","NEWSAPI_KEY"); newsdata=env("NEWS_DATA_IO_KEY","NEWSDATA_IO_KEY")
    for q in cfg.get("news_queries",[]):
        if newsapi:
            url="https://newsapi.org/v2/everything"; params={"q":q,"language":"en","sortBy":"publishedAt","pageSize":50,"from":start,"apiKey":newsapi}
            data,hs,content,err=req(url,params); p=write_bytes(raw/f"newsapi_{slug(q)}_{RUN_TS}.json",content)
            rec("NewsAPI everything","news_api",fullurl(url,params),q,"ok" if hs and hs<400 else "error",hs,p,count(data),err)
            if isinstance(data,dict) and isinstance(data.get("articles"),list):
                for a in data["articles"]: a["_aq26_provider"]="NewsAPI"; a["_aq26_query"]=q; articles.append(a)
        if newsdata:
            url="https://newsdata.io/api/1/news"; params={"apikey":newsdata,"q":q,"language":"en","size":10}
            data,hs,content,err=req(url,params); p=write_bytes(raw/f"newsdata_{slug(q)}_{RUN_TS}.json",content)
            rec("NewsData.io news","news_api",fullurl(url,params),q,"ok" if hs and hs<400 else "error",hs,p,count(data),err)
            if isinstance(data,dict) and isinstance(data.get("results"),list):
                for a in data["results"]: a["_aq26_provider"]="NewsData.io"; a["_aq26_query"]=q; articles.append(a)
        # throttle GDELT
        elapsed=time.time()-LAST_GDELT_CALL
        if elapsed < 5.2: time.sleep(5.2-elapsed)
        url="https://api.gdeltproject.org/api/v2/doc/doc"; params={"query":q,"mode":"ArtList","format":"json","maxrecords":50,"sort":"HybridRel"}
        data,hs,content,err=req(url,params); LAST_GDELT_CALL=time.time()
        p=write_bytes(raw/f"gdelt_{slug(q)}_{RUN_TS}.json",content)
        rec("GDELT document API","news_api",fullurl(url,params),q,"ok" if hs and hs<400 else "error",hs,p,count(data),err)
    write_json(out/"03_news_context"/"news_articles.json",{"run_ts":RUN_TS,"count":len(articles),"articles":articles})

def harvest_aq_weather(cfg,out):
    raw=mkdir(out/"04_ground_aq_providers"/"raw")
    waqi=env("WAQI_TOKEN"); ow=env("OPENWEATHER_KEY","OW_KEY")
    for site in cfg.get("sites",[]):
        sid=site["id"]; lat=site["lat"]; lon=site["lon"]
        if waqi:
            url=f"https://api.waqi.info/feed/geo:{lat};{lon}/"; params={"token":waqi}
            data,hs,content,err=req(url,params); p=write_bytes(raw/f"waqi_{sid}_{RUN_TS}.json",content)
            rec("WAQI geospatial feed","ground_aq",fullurl(url,params),sid,"ok" if hs and hs<400 else "error",hs,p,count(data),err)
        if ow:
            url="https://api.openweathermap.org/data/2.5/weather"; params={"lat":lat,"lon":lon,"appid":ow,"units":"metric"}
            data,hs,content,err=req(url,params); p=write_bytes(out/"05_weather"/"raw"/f"openweather_current_{sid}_{RUN_TS}.json",content)
            rec("OpenWeather current weather","weather",fullurl(url,params),sid,"ok" if hs and hs<400 else "error",hs,p,count(data),err)
            url="https://api.openweathermap.org/data/2.5/air_pollution"; params={"lat":lat,"lon":lon,"appid":ow}
            data,hs,content,err=req(url,params); p=write_bytes(raw/f"openweather_airpollution_{sid}_{RUN_TS}.json",content)
            rec("OpenWeather air pollution","ground_aq",fullurl(url,params),sid,"ok" if hs and hs<400 else "error",hs,p,count(data),err)
    met=env("MET_OFFICE_API_KEY","METOFFICE_API_KEY","MET_OFFICE_KEY")
    if met:
        site=cfg.get("sites",[{"lat":50.796,"lon":0.055}])[0]
        url="https://data.hub.api.metoffice.gov.uk/observation-land/1/nearest"
        params={"lat":site.get("lat",50.796),"lon":site.get("lon",0.055)}
        data,hs,content,err=req(url,params,headers={"apikey":met})
        p=write_bytes(out/"05_metoffice_datahub_weather"/f"metoffice_land_observations_{RUN_TS}.json",content)
        rec("Met Office DataHub land observations","weather",fullurl(url,params),"newhaven_nearest","ok" if hs and hs<400 else "error",hs,p,count(data),err,notes="uses apikey header and lat/lon parameters")

def harvest_official(cfg,out):
    filings=[]; raw=mkdir(out/"06_official_filings"/"raw")
    terms=[t.lower() for t in cfg.get("thresholds",{}).get("anomaly",{}).get("official_relevance_terms",[])]
    for q in cfg.get("official_queries",[]):
        for source,url,params in [
            ("GOV.UK","https://www.gov.uk/api/search.json",{"q":q,"count":50}),
            ("data.gov.uk","https://ckan.publishing.service.gov.uk/api/3/action/package_search",{"q":q,"rows":50}),
        ]:
            data,hs,content,err=req(url,params); p=write_bytes(raw/f"{slug(source)}_{slug(q)}_{RUN_TS}.json",content)
            rec(source+" search","official_search",fullurl(url,params),q,"ok" if hs and hs<400 else "error",hs,p,count(data),err)
            if source=="GOV.UK" and isinstance(data,dict):
                for r in data.get("results",[]): filings.append({"source":source,"query":q,"title":r.get("title"),"url":urllib.parse.urljoin("https://www.gov.uk",r.get("link","")),"raw":r})
            if source=="data.gov.uk" and isinstance(data,dict) and isinstance(data.get("result"),dict):
                for r in data["result"].get("results",[]): filings.append({"source":source,"query":q,"title":r.get("title"),"url":r.get("url") or "", "raw":r})
    for item in cfg.get("watch_urls",[]):
        data,hs,content,err=req(item["url"]); p=write_bytes(raw/f"watch_{slug(item.get('name','watch'))}_{RUN_TS}.html",content)
        rec(item.get("name","Watch URL"),"official_watch_url",item["url"],item.get("name",""),"ok" if hs and hs<400 else "error",hs,p,1 if hs and hs<400 else 0,err)
        filings.append({"source":"watch_url","query":item.get("name"),"title":item.get("name"),"url":item["url"],"raw_path":str(p)})
    for f in filings:
        text=json.dumps(f,ensure_ascii=False).lower(); hits=[t for t in terms if t in text]
        f["aq26_relevance_hits"]=hits; f["aq26_relevance_class"]="confirmed_or_probable" if len(hits)>=2 else ("candidate_context" if hits else "weak_or_irrelevant")
    write_json(out/"06_official_filings"/"official_filing_index.json",{"run_ts":RUN_TS,"filing_count":len(filings),"filings":filings})
    write_json(out/"06_official_filings"/"new_or_changed_source_index.json",{"run_ts":RUN_TS,"items":[{"change_status":"seen_this_run","fingerprint":hashlib.sha256(json.dumps(safe_json(f),sort_keys=True,default=str).encode()).hexdigest(),"title":f.get("title"),"url":f.get("url"),"source":f.get("source"),"query":f.get("query"),"relevance_class":f.get("aq26_relevance_class")} for f in filings]})

def harvest_sat(cfg,out,start,end):
    raw=mkdir(out/"07_satellite_cdse"/"raw"); sat=cfg.get("satellite",{}); bbox=sat.get("bbox",[-0.15,50.68,0.35,50.95])
    meta={"run_ts":RUN_TS,"bbox":bbox,"start_date":start,"end_date":end,"odata":[],"product_count":0}
    base="https://catalogue.dataspace.copernicus.eu/odata/v1/Products"
    for prod in sat.get("collections",{}).get("odata_products",["L2__NO2___","L2__SO2___","L2__CO____","L2__HCHO__"]):
        flt=f"contains(Name,'S5P') and contains(Name,'{prod}') and ContentDate/Start ge {start}T00:00:00.000Z and ContentDate/Start le {end}T23:59:59.000Z"
        params={"$filter":flt,"$top":int(sat.get("max_records_per_product",50)),"$orderby":"ContentDate/Start desc"}
        data,hs,content,err=req(base,params); p=write_bytes(raw/f"copernicus_odata_{prod}_{RUN_TS}.json",content); c=count(data)
        meta["odata"].append({"product":prod,"http_status":hs,"count":c,"path":str(p),"bbox_context":bbox}); meta["product_count"]+=c
        rec("Copernicus Data Space OData product search","satellite_metadata",fullurl(base,params),prod,"ok" if hs and hs<400 else "error",hs,p,c,err,notes=f"bbox context={bbox}; catalogue only")
    write_json(out/"07_satellite_cdse"/"satellite_catalogue_metadata.json",meta)

def harvest_gdrive(out, folder_id):
    if os.getenv("AQ26_SYNC_GOOGLE_DRIVE","").lower() not in ("1","true","yes","y"):
        rec("Google Drive folder snapshot","gdrive","gdrive://disabled","","skipped",None,None,0,notes="sync disabled"); return
    folder_id=folder_id or os.getenv("GDRIVE_FOLDER_ID","")
    cred=env("GDRIVE_SERVICE_ACCOUNT","GDRIVE_SERVICE_ACCOUNT_JSON","GDRIVE_CREDENTIALS")
    if not folder_id or not cred:
        rec("Google Drive folder snapshot","gdrive",f"gdrive://{folder_id or 'missing'}","","skipped",None,None,0,notes="missing folder id or service account"); return
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        info=json.loads(cred); creds=service_account.Credentials.from_service_account_info(info,scopes=["https://www.googleapis.com/auth/drive.readonly"])
        svc=build("drive","v3",credentials=creds,cache_discovery=False)
        files=[]; token=None
        for _ in range(20):
            resp=svc.files().list(q=f"'{folder_id}' in parents and trashed=false",fields="nextPageToken, files(id,name,mimeType,modifiedTime,size,md5Checksum,webViewLink,parents)",pageSize=1000,pageToken=token,supportsAllDrives=True,includeItemsFromAllDrives=True).execute()
            files += resp.get("files",[]); token=resp.get("nextPageToken")
            if not token: break
        p=write_json(out/"08_gdrive_snapshot"/f"gdrive_folder_snapshot_{RUN_TS}.json",{"run_ts":RUN_TS,"folder_id":folder_id,"file_count":len(files),"files":files})
        rec("Google Drive folder snapshot","gdrive",f"gdrive://{folder_id}",folder_id,"ok",None,p,len(files),notes="metadata only")
    except Exception as e:
        p=write_json(out/"08_gdrive_snapshot"/f"gdrive_error_{RUN_TS}.json",{"error":repr(e)})
        rec("Google Drive folder snapshot","gdrive",f"gdrive://{folder_id}",folder_id,"error",None,p,0,repr(e))

def finish(out,cfg,start,end):
    mkdir(out/"source_history")
    with (out/"source_history"/"source_index.jsonl").open("a",encoding="utf-8") as f:
        for r in SOURCE_RECORDS: f.write(json.dumps(safe_json(r),ensure_ascii=False)+"\n")
    latest={"run_ts":RUN_TS,"project":cfg.get("project",{}).get("name","SCCNEXUS AirQuality26"),"controlled_use_boundary":cfg.get("project",{}).get("controlled_use_boundary",""),"date_window":{"start":start,"end":end},"source_record_count":len(SOURCE_RECORDS),"ok_count":sum(1 for r in SOURCE_RECORDS if r["status"]=="ok"),"error_count":sum(1 for r in SOURCE_RECORDS if r["status"]=="error"),"source_records":SOURCE_RECORDS}
    write_json(out/"00_live_harvest"/"LATEST_HARVEST.json",latest)
    run_dir=mkdir(out/"00_live_harvest"/f"AQ26_LIVE_HARVEST_{RUN_TS}")
    write_json(run_dir/f"AQ26_LIVE_HARVEST_MANIFEST_{RUN_TS}.json",latest)
    if SOURCE_RECORDS:
        with (run_dir/f"AQ26_LIVE_SOURCE_RECORDS_{RUN_TS}.csv").open("w",newline="",encoding="utf-8") as f:
            w=csv.DictWriter(f,fieldnames=list(SOURCE_RECORDS[0].keys())); w.writeheader(); w.writerows(SOURCE_RECORDS)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--config",default="configs/aq26_integrated_sources.yml")
    ap.add_argument("--output-root",default="outputs")
    ap.add_argument("--lookback-days",default="14")
    ap.add_argument("--backfill-start-date",default="")
    ap.add_argument("--backfill-end-date",default="")
    ap.add_argument("--download-official-files",default="false")
    ap.add_argument("--sync-google-drive",default="false")
    ap.add_argument("--gdrive-folder-id",default="")
    args=ap.parse_args()
    out=Path(args.output_root); mkdir(out)
    os.environ["AQ26_SYNC_GOOGLE_DRIVE"]=args.sync_google_drive
    cfg=yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    start,end=window(args.lookback_days,args.backfill_start_date.strip(),args.backfill_end_date.strip())
    harvest_news(cfg,out,start); harvest_aq_weather(cfg,out); harvest_official(cfg,out); harvest_sat(cfg,out,start,end); harvest_gdrive(out,args.gdrive_folder_id.strip()); finish(out,cfg,start,end)
    print(json.dumps({"run_ts":RUN_TS,"source_records":len(SOURCE_RECORDS),"ok":sum(1 for r in SOURCE_RECORDS if r["status"]=="ok"),"error":sum(1 for r in SOURCE_RECORDS if r["status"]=="error")},indent=2))
if __name__=="__main__": main()
