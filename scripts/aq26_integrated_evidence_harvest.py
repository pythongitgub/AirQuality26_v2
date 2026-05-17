#!/usr/bin/env python3
from __future__ import annotations
import argparse, csv, datetime as dt, hashlib, json, os, re, urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import requests, yaml
try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None

SECRET_KEYS=["apikey","apiKey","api_key","key","token","access_token","password","client_secret","secret","authorization","bearer"]
SOURCE_RECORDS: List[Dict[str, Any]] = []
RUN_TS = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")

def now_utc(): return dt.datetime.now(dt.timezone.utc)
def uk_time(t=None):
    t=t or now_utc()
    return t.astimezone(ZoneInfo("Europe/London")) if ZoneInfo else t
def ensure(p: Path): p.mkdir(parents=True, exist_ok=True); return p
def sha256_file(p: Path):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda:f.read(1024*1024), b""): h.update(b)
    return h.hexdigest()
def slug(s): return re.sub(r"[^A-Za-z0-9_.-]+","_",str(s)).strip("_")[:120] or "item"
def env_first(*names):
    for n in names:
        v=os.getenv(n,"")
        if v: return v
    return ""
def redact_text(s: str) -> str:
    if not s: return s
    out=s
    try:
        u=urllib.parse.urlsplit(out)
        if u.query:
            pairs=urllib.parse.parse_qsl(u.query, keep_blank_values=True)
            pairs=[(k,"***REDACTED***" if any(x.lower() in k.lower() for x in SECRET_KEYS) else v) for k,v in pairs]
            out=urllib.parse.urlunsplit((u.scheme,u.netloc,u.path,urllib.parse.urlencode(pairs),u.fragment))
    except Exception: pass
    for pat in [r"(?i)(api[-_]?key\s*[=:]\s*)[A-Za-z0-9_\-.]{8,}",r"(?i)(token\s*[=:]\s*)[A-Za-z0-9_\-.]{8,}",r"(?i)(password\s*[=:]\s*)[^\s&\"']+",r"(?i)(client_secret\s*[=:]\s*)[^\s&\"']+",r"(?i)(Bearer\s+)[A-Za-z0-9_\-.]{12,}"]:
        out=re.sub(pat,r"\1***REDACTED***",out)
    return out
def safe(obj):
    if isinstance(obj,dict): return {k:safe(v) for k,v in obj.items()}
    if isinstance(obj,list): return [safe(x) for x in obj]
    if isinstance(obj,str): return redact_text(obj)
    return obj
def write_json(p: Path, obj: Any):
    ensure(p.parent); p.write_text(json.dumps(safe(obj),indent=2,ensure_ascii=False,default=str),encoding="utf-8"); return p
def write_bytes(p: Path, data: bytes):
    ensure(p.parent); p.write_bytes(data); return p
def count_records(data):
    if isinstance(data,list): return len(data)
    if isinstance(data,dict):
        for k in ["articles","results","features","value","items","records","data"]:
            if isinstance(data.get(k),list): return len(data[k])
        if isinstance(data.get("result"),dict) and isinstance(data["result"].get("results"),list): return len(data["result"]["results"])
    return 0
def rec(name, typ, url, query, status, http, path=None, count=0, error="", notes=""):
    t=now_utc(); ukt=uk_time(t)
    r={"run_ts":RUN_TS,"source_name":name,"source_type":typ,"url":redact_text(url),"query":query,"status":status,"http_status":http,"retrieved_at_utc":t.isoformat(),"retrieved_at_uk":ukt.isoformat(),"date_uk":ukt.strftime("%d/%m/%Y"),"output_path":str(path).replace("\\","/") if path else "","sha256":sha256_file(path) if path and path.exists() else "","bytes":path.stat().st_size if path and path.exists() else 0,"record_count":int(count or 0),"error":redact_text(error or ""),"notes":notes}
    SOURCE_RECORDS.append(r); return r
def get_json(url, params=None, headers=None, timeout=30):
    try:
        r=requests.get(url,params=params,headers=headers,timeout=timeout)
        try: data=r.json()
        except Exception: data=None
        return data,r.status_code,r.content,"" if r.ok else r.text[:500]
    except Exception as e:
        return None,None,json.dumps({"error":repr(e)}).encode(),repr(e)
def prepared(url, params=None):
    return requests.Request("GET",url,params=params).prepare().url

def date_window(days,start,end):
    if start:
        s=dt.date.fromisoformat(start); e=dt.date.fromisoformat(end) if end else now_utc().date()
    else:
        e=now_utc().date(); s=e-dt.timedelta(days=int(days))
    return s.isoformat(), e.isoformat()

def harvest_news(cfg,out,start):
    articles=[]
    newsapi=env_first("NEWS_API_KEY"); newsdata=env_first("NEWS_DATA_IO_KEY","NEWSDATA_IO_KEY")
    for q in cfg.get("news_queries",[]):
        if newsapi:
            url="https://newsapi.org/v2/everything"; params={"q":q,"language":"en","sortBy":"publishedAt","pageSize":50,"from":start,"apiKey":newsapi}
            data,hs,content,err=get_json(url,params=params); p=write_bytes(out/"03_news_context/raw"/f"newsapi_{slug(q)}_{RUN_TS}.json",content)
            rec("NewsAPI everything","news_api",prepared(url,params),q,"ok" if hs and hs<400 else "error",hs,p,count_records(data),err)
            for a in (data or {}).get("articles",[]) if isinstance(data,dict) else []: a.update({"_aq26_provider":"NewsAPI","_aq26_query":q}); articles.append(a)
        if newsdata:
            url="https://newsdata.io/api/1/news"; params={"apikey":newsdata,"q":q,"language":"en","size":10}
            data,hs,content,err=get_json(url,params=params); p=write_bytes(out/"03_news_context/raw"/f"newsdata_{slug(q)}_{RUN_TS}.json",content)
            rec("NewsData.io news","news_api",prepared(url,params),q,"ok" if hs and hs<400 else "error",hs,p,count_records(data),err)
            for a in (data or {}).get("results",[]) if isinstance(data,dict) else []: a.update({"_aq26_provider":"NewsData.io","_aq26_query":q}); articles.append(a)
        url="https://api.gdeltproject.org/api/v2/doc/doc"; params={"query":q,"mode":"ArtList","format":"json","maxrecords":50,"sort":"HybridRel"}
        data,hs,content,err=get_json(url,params=params); p=write_bytes(out/"03_news_context/raw"/f"gdelt_{slug(q)}_{RUN_TS}.json",content)
        rec("GDELT document API","news_api",prepared(url,params),q,"ok" if hs and hs<400 else "error",hs,p,count_records(data),err)
    write_json(out/"03_news_context/news_articles.json",{"run_ts":RUN_TS,"count":len(articles),"articles":articles})

def harvest_aq_weather(cfg,out):
    waqi=env_first("WAQI_TOKEN"); ow=env_first("OPENWEATHER_KEY","OW_KEY")
    calls=[]
    for site in cfg.get("sites",[]):
        lat,lon,sid=site["lat"],site["lon"],site["id"]
        if waqi:
            url=f"https://api.waqi.info/feed/geo:{lat};{lon}/"; params={"token":waqi}
            data,hs,content,err=get_json(url,params=params); p=write_bytes(out/"04_ground_aq_providers/raw"/f"waqi_{sid}_{RUN_TS}.json",content)
            calls.append(rec("WAQI geospatial feed","ground_aq",prepared(url,params),sid,"ok" if hs and hs<400 else "error",hs,p,count_records(data),err))
        if ow:
            for name,url,subdir in [("OpenWeather current weather","https://api.openweathermap.org/data/2.5/weather","05_weather/raw"),("OpenWeather air pollution","https://api.openweathermap.org/data/2.5/air_pollution","04_ground_aq_providers/raw")]:
                params={"lat":lat,"lon":lon,"appid":ow}
                if "weather" in url: params["units"]="metric"
                data,hs,content,err=get_json(url,params=params); p=write_bytes(out/subdir/f"{slug(name)}_{sid}_{RUN_TS}.json",content)
                rec(name,"weather" if "weather" in name.lower() else "ground_aq",prepared(url,params),sid,"ok" if hs and hs<400 else "error",hs,p,count_records(data),err)
    write_json(out/"04_ground_aq_providers/provider_calls.json",{"run_ts":RUN_TS,"calls":calls})
    met=env_first("MET_OFFICE_KEY","METOFFICE_API_KEY","MET_OFFICE_API_KEY"); endpoint=env_first("MET_OFFICE_LAND_OBSERVATIONS")
    if met or endpoint:
        site=cfg.get("sites",[{}])[0]
        url=endpoint if endpoint.startswith("http") else "https://data.hub.api.metoffice.gov.uk/observation-land/1/nearest"
        params={} if endpoint.startswith("http") else {"latitude":site.get("lat",50.796),"longitude":site.get("lon",0.055)}
        headers={"apikey":met} if met else {}
        data,hs,content,err=get_json(url,params=params,headers=headers); p=write_bytes(out/"05_metoffice_datahub_weather"/f"metoffice_land_observations_{RUN_TS}.json",content)
        rec("Met Office DataHub land observations","weather",prepared(url,params),"newhaven_nearest","ok" if hs and hs<400 else "error",hs,p,count_records(data),err)

def harvest_official(cfg,out):
    filings=[]
    terms=[t.lower() for t in cfg.get("thresholds",{}).get("anomaly",{}).get("official_relevance_terms",[])]
    for q in cfg.get("official_queries",[]):
        for source,url,params in [
            ("GOV.UK","https://www.gov.uk/api/search.json",{"q":q,"count":50}),
            ("data.gov.uk","https://ckan.publishing.service.gov.uk/api/3/action/package_search",{"q":q,"rows":50})
        ]:
            data,hs,content,err=get_json(url,params=params); p=write_bytes(out/"06_official_filings/raw"/f"{slug(source)}_{slug(q)}_{RUN_TS}.json",content)
            rec(f"{source} search","official_search",prepared(url,params),q,"ok" if hs and hs<400 else "error",hs,p,count_records(data),err)
            if source=="GOV.UK" and isinstance(data,dict):
                for r in data.get("results",[]): filings.append({"source":source,"query":q,"title":r.get("title"),"url":urllib.parse.urljoin("https://www.gov.uk",r.get("link","")),"raw":r})
            if source=="data.gov.uk" and isinstance(data,dict):
                for r in data.get("result",{}).get("results",[]): filings.append({"source":source,"query":q,"title":r.get("title"),"url":r.get("url") or "", "raw":r})
    for item in cfg.get("watch_urls",[]):
        url=item.get("url"); data,hs,content,err=get_json(url); p=write_bytes(out/"06_official_filings/raw"/f"watch_{slug(item.get('name'))}_{RUN_TS}.html",content)
        rec(item.get("name","Watch URL"),"official_watch_url",url,item.get("name",""),"ok" if hs and hs<400 else "error",hs,p,1 if hs and hs<400 else 0,err)
        filings.append({"source":"watch_url","query":item.get("name"),"title":item.get("name"),"url":url,"raw_path":str(p)})
    for f in filings:
        text=json.dumps(f,ensure_ascii=False).lower(); hits=[t for t in terms if t in text]
        f["aq26_relevance_hits"]=hits; f["aq26_relevance_class"]="confirmed_or_probable" if len(hits)>=2 else ("candidate_context" if hits else "weak_or_irrelevant")
    write_json(out/"06_official_filings/official_filing_index.json",{"run_ts":RUN_TS,"filing_count":len(filings),"filings":filings})
    items=[{"change_status":"seen_this_run","fingerprint":hashlib.sha256(json.dumps(safe(f),sort_keys=True,default=str).encode()).hexdigest(),"title":f.get("title"),"url":f.get("url"),"source":f.get("source"),"query":f.get("query"),"relevance_class":f.get("aq26_relevance_class")} for f in filings]
    write_json(out/"06_official_filings/new_or_changed_source_index.json",{"run_ts":RUN_TS,"items":items})

def harvest_satellite(cfg,out,start,end):
    sat=cfg.get("satellite",{}); bbox=sat.get("bbox"); raw=out/"07_satellite_cdse/raw"
    meta={"run_ts":RUN_TS,"bbox":bbox,"start_date":start,"end_date":end,"odata":[],"product_count":0}
    base="https://catalogue.dataspace.copernicus.eu/odata/v1/Products"
    for prod in sat.get("collections",{}).get("odata_products",[]):
        flt=f"contains(Name,'S5P') and contains(Name,'{prod}') and ContentDate/Start ge {start}T00:00:00.000Z and ContentDate/Start le {end}T23:59:59.000Z"
        params={"$filter":flt,"$top":int(sat.get("max_records_per_product",50)),"$orderby":"ContentDate/Start desc"}
        data,hs,content,err=get_json(base,params=params); p=write_bytes(raw/f"copernicus_odata_{prod}_{RUN_TS}.json",content)
        c=count_records(data); meta["product_count"]+=c; meta["odata"].append({"product":prod,"http_status":hs,"count":c,"path":str(p),"bbox_context":bbox})
        rec("Copernicus Data Space OData product search","satellite_metadata",prepared(base,params),prod,"ok" if hs and hs<400 else "error",hs,p,c,err,notes=f"bbox context={bbox}; catalogue metadata only, not pollutant extraction")
    write_json(out/"07_satellite_cdse/satellite_catalogue_metadata.json",meta)

def harvest_gdrive(out,folder_id):
    if os.getenv("AQ26_SYNC_GOOGLE_DRIVE","").lower() not in ("1","true","yes","y"):
        rec("Google Drive folder snapshot","gdrive","gdrive://disabled","","skipped",None,None,0,notes="sync_google_drive=false"); return
    folder_id=folder_id or os.getenv("GDRIVE_FOLDER_ID","")
    cred=env_first("GDRIVE_SERVICE_ACCOUNT_JSON","GDRIVE_CREDENTIALS","GDRIVE_SERVICE_ACCOUNT")
    if not folder_id or not cred:
        rec("Google Drive folder snapshot","gdrive",f"gdrive://{folder_id or 'missing'}","","skipped",None,None,0,notes="Missing folder id or service account JSON"); return
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        info=json.loads(cred); scopes=["https://www.googleapis.com/auth/drive.readonly"]
        creds=service_account.Credentials.from_service_account_info(info,scopes=scopes)
        service=build("drive","v3",credentials=creds,cache_discovery=False)
        files=[]; page=None
        q=f"'{folder_id}' in parents and trashed=false"; fields="nextPageToken, files(id,name,mimeType,modifiedTime,size,md5Checksum,webViewLink,parents)"
        for _ in range(20):
            resp=service.files().list(q=q,fields=fields,pageSize=1000,pageToken=page,supportsAllDrives=True,includeItemsFromAllDrives=True).execute()
            files += resp.get("files",[]); page=resp.get("nextPageToken")
            if not page: break
        p=write_json(out/"08_gdrive_snapshot"/f"gdrive_folder_snapshot_{RUN_TS}.json",{"run_ts":RUN_TS,"folder_id":folder_id,"file_count":len(files),"files":files})
        rec("Google Drive folder snapshot","gdrive",f"gdrive://{folder_id}",folder_id,"ok",None,p,len(files),notes="metadata-only Drive read")
    except Exception as e:
        p=write_json(out/"08_gdrive_snapshot"/f"gdrive_error_{RUN_TS}.json",{"error":repr(e),"folder_id":folder_id})
        rec("Google Drive folder snapshot","gdrive",f"gdrive://{folder_id}",folder_id,"error",None,p,0,repr(e))

def write_history(out):
    ensure(out/"source_history")
    with (out/"source_history/source_index.jsonl").open("a",encoding="utf-8") as f:
        for r in SOURCE_RECORDS: f.write(json.dumps(safe(r),ensure_ascii=False)+"\n")
def build_latest(out,cfg,start,end):
    latest={"run_ts":RUN_TS,"project":cfg.get("project",{}).get("name","SCCNEXUS AirQuality26"),"controlled_use_boundary":cfg.get("project",{}).get("controlled_use_boundary",""),"date_window":{"start":start,"end":end},"source_record_count":len(SOURCE_RECORDS),"ok_count":sum(1 for r in SOURCE_RECORDS if r["status"]=="ok"),"error_count":sum(1 for r in SOURCE_RECORDS if r["status"]=="error"),"source_records":SOURCE_RECORDS}
    write_json(out/"00_live_harvest/LATEST_HARVEST.json",latest)
    write_json(out/"00_live_harvest"/f"AQ26_LIVE_HARVEST_{RUN_TS}"/f"AQ26_LIVE_HARVEST_MANIFEST_{RUN_TS}.json",latest)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--config",default="configs/aq26_integrated_sources.yml"); ap.add_argument("--output-root",default="outputs")
    ap.add_argument("--lookback-days",default="14"); ap.add_argument("--backfill-start-date",default=""); ap.add_argument("--backfill-end-date",default="")
    ap.add_argument("--download-official-files",default="false"); ap.add_argument("--sync-google-drive",default="false"); ap.add_argument("--gdrive-folder-id",default="")
    args=ap.parse_args()
    out=Path(args.output_root); ensure(out); cfg=yaml.safe_load(Path(args.config).read_text())
    os.environ["AQ26_SYNC_GOOGLE_DRIVE"]=args.sync_google_drive
    start,end=date_window(args.lookback_days,args.backfill_start_date.strip(),args.backfill_end_date.strip())
    harvest_news(cfg,out,start); harvest_aq_weather(cfg,out); harvest_official(cfg,out); harvest_satellite(cfg,out,start,end); harvest_gdrive(out,args.gdrive_folder_id.strip())
    write_history(out); build_latest(out,cfg,start,end)
    print(json.dumps({"run_ts":RUN_TS,"source_records":len(SOURCE_RECORDS),"ok":sum(1 for r in SOURCE_RECORDS if r["status"]=="ok"),"error":sum(1 for r in SOURCE_RECORDS if r["status"]=="error")},indent=2))
if __name__=="__main__": main()
