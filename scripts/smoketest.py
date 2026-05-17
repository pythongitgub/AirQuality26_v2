#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt, hashlib, json, os, re, urllib.parse
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
import requests

try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None

OUT = Path("outputs/01_secrets_smoketest")
OUT.mkdir(parents=True, exist_ok=True)

GROUPS = {
    "cdse": ["CDSE_ID", "CDSE_SECRET", "CDSE_USERNAME", "CDSE_PASSWORD"],
    "ground_aq": ["WAQI_TOKEN", "OPENWEATHER_KEY", "OPENWEATHER_API_KEY", "OW_KEY"],
    "news": ["NEWS_API_KEY", "NEWSAPI_KEY", "NEWS_DATA_IO_KEY", "NEWSDATA_IO_KEY", "NEWSDATA_KEY"],
    "metoffice": ["MET_OFFICE_API_KEY", "METOFFICE_API_KEY", "MET_OFFICE_KEY", "MET_OFFICE_LAND_OBSERVATIONS"],
    "gdrive": ["GDRIVE_SERVICE_ACCOUNT", "GDRIVE_SERVICE_ACCOUNT_JSON", "GDRIVE_CREDENTIALS", "GDRIVE_FOLDER_ID"],
    "email": ["SMTP_HOST", "SMTP_PORT", "SMTP_USERNAME", "SMTP_PASSWORD", "MAIL_FROM", "MAIL_TO"],
}

def now_utc(): return dt.datetime.now(dt.timezone.utc)
def now_uk(t=None):
    t = t or now_utc()
    return t.astimezone(ZoneInfo("Europe/London")) if ZoneInfo else t

def first(*names):
    for n in names:
        v = os.getenv(n, "")
        if v:
            return n, v.strip()
    return "", ""

def status(n):
    v=os.getenv(n,"")
    return {"name": n, "present": bool(v), "length": len(v), "sha256_prefix": hashlib.sha256(v.encode()).hexdigest()[:10] if v else ""}

def redact(s):
    if not s: return s
    try:
        u=urllib.parse.urlsplit(s)
        if u.query:
            pairs=urllib.parse.parse_qsl(u.query, keep_blank_values=True)
            pairs=[(k, "***REDACTED***" if any(x in k.lower() for x in ["key","token","secret","password","apikey"]) else v) for k,v in pairs]
            s=urllib.parse.urlunsplit((u.scheme,u.netloc,u.path,urllib.parse.urlencode(pairs),u.fragment))
    except Exception:
        pass
    for pat in [r"(?i)(apikey\s*[=:]\s*)[A-Za-z0-9_\-.]{8,}", r"(?i)(token\s*[=:]\s*)[A-Za-z0-9_\-.]{8,}", r"(?i)(Bearer\s+)[A-Za-z0-9_\-.]{12,}", r"(?i)(password\s*[=:]\s*)[^\s&\"']+"]:
        s=re.sub(pat, r"\1***REDACTED***", s)
    return s

def safe_url(url, params=None):
    if params:
        return redact(requests.Request("GET", url, params=params).prepare().url)
    return redact(url)

def count(data):
    if isinstance(data, list): return len(data)
    if isinstance(data, dict):
        for k in ["articles","results","features","value","items","data","list"]:
            if isinstance(data.get(k), list): return len(data[k])
        if isinstance(data.get("result"), dict): return count(data["result"])
    return 0

def get_json(provider, url, params=None, headers=None, timeout=25):
    started=now_utc()
    out={"provider": provider, "url": safe_url(url, params), "started_at_utc": started.isoformat(), "started_at_uk": now_uk(started).isoformat(), "ok": False, "http_status": None, "content_type": "", "bytes": 0, "json_parse_ok": False, "record_count_hint": 0, "error": ""}
    try:
        r=requests.get(url, params=params, headers=headers, timeout=timeout)
        out.update({"http_status": r.status_code, "content_type": r.headers.get("content-type",""), "bytes": len(r.content), "ok": bool(r.ok)})
        try:
            data=r.json(); out["json_parse_ok"]=True; out["record_count_hint"]=count(data)
            if not r.ok: out["error"]=redact(json.dumps(data)[:700])
        except Exception:
            if not r.ok: out["error"]=redact(r.text[:700])
    except Exception as e:
        out["error"]=redact(repr(e))
    finished=now_utc()
    out["finished_at_utc"]=finished.isoformat()
    out["duration_seconds"]=round((finished-started).total_seconds(),3)
    return out

def skipped(provider, reason): return {"provider": provider, "ok": False, "skipped": True, "reason": reason}

def test_waqi():
    n,k=first("WAQI_TOKEN")
    return skipped("WAQI","WAQI_TOKEN not present") if not k else get_json("WAQI Newhaven geospatial feed","https://api.waqi.info/feed/geo:50.796;0.055/",{"token":k})

def test_openweather():
    n,k=first("OPENWEATHER_KEY","OPENWEATHER_API_KEY","OW_KEY")
    if not k: return skipped("OpenWeather","OPENWEATHER_KEY / OPENWEATHER_API_KEY / OW_KEY not present")
    r=get_json(f"OpenWeather current weather using {n}","https://api.openweathermap.org/data/2.5/weather",{"lat":50.796,"lon":0.055,"appid":k,"units":"metric"})
    r["secret_name_tested"]=n
    return r

def test_newsapi():
    n,k=first("NEWS_API_KEY","NEWSAPI_KEY")
    if not k: return skipped("NewsAPI","NEWS_API_KEY / NEWSAPI_KEY not present")
    r=get_json(f"NewsAPI using {n}","https://newsapi.org/v2/everything",{"q":"Newhaven incinerator","language":"en","pageSize":1,"apiKey":k})
    r["secret_name_tested"]=n
    return r

def test_newsdata():
    n,k=first("NEWS_DATA_IO_KEY","NEWSDATA_IO_KEY","NEWSDATA_KEY")
    if not k: return skipped("NewsData.io","NEWS_DATA_IO_KEY / NEWSDATA_IO_KEY / NEWSDATA_KEY not present")
    r=get_json(f"NewsData.io using {n}","https://newsdata.io/api/1/news",{"apikey":k,"q":"Newhaven incinerator","language":"en","size":1})
    r["secret_name_tested"]=n
    return r

def test_metoffice():
    keys=[(n,os.getenv(n,"").strip()) for n in ["MET_OFFICE_API_KEY","METOFFICE_API_KEY","MET_OFFICE_KEY"] if os.getenv(n,"").strip()]
    configured=os.getenv("MET_OFFICE_LAND_OBSERVATIONS","").strip()
    endpoints=[("standard_nearest_lat_lon","https://data.hub.api.metoffice.gov.uk/observation-land/1/nearest",{"lat":50.796,"lon":0.055})]
    # Probe alternative accepted spelling too, but lat/lon is the one the API asked for in your manifest.
    endpoints.append(("standard_nearest_latitude_longitude","https://data.hub.api.metoffice.gov.uk/observation-land/1/nearest",{"latitude":50.796,"longitude":0.055}))
    if configured.startswith("http"):
        endpoints.append(("configured_MET_OFFICE_LAND_OBSERVATIONS",configured,{}))
    if not keys: return skipped("Met Office","No Met Office key secret present")
    attempts=[]
    for secret_name,key in keys:
        for endpoint_name,url,params in endpoints:
            for header_style,headers in [("apikey",{"apikey":key}),("x-api-key",{"x-api-key":key})]:
                r=get_json(f"Met Office {endpoint_name} using {secret_name} with {header_style} header",url,params,headers)
                r.update({"secret_name_tested":secret_name,"endpoint_name_tested":endpoint_name,"header_style":header_style})
                attempts.append(r)
                if r["ok"]:
                    return {"provider":"Met Office DataHub Land Observations","ok":True,"selected_secret":secret_name,"selected_endpoint":endpoint_name,"selected_header":header_style,"attempts":attempts}
    return {"provider":"Met Office DataHub Land Observations","ok":False,"attempts":attempts,"error":"All Met Office key/endpoint/header attempts failed."}

def test_cdse():
    return get_json("Copernicus Data Space OData catalogue metadata","https://catalogue.dataspace.copernicus.eu/odata/v1/Products",{"$filter":"contains(Name,'S5P') and contains(Name,'L2__NO2___')","$top":1,"$orderby":"ContentDate/Start desc"})

def test_gdrive():
    fid=os.getenv("GDRIVE_FOLDER_ID","").strip()
    cn,ct=first("GDRIVE_SERVICE_ACCOUNT","GDRIVE_SERVICE_ACCOUNT_JSON","GDRIVE_CREDENTIALS")
    if not fid: return skipped("Google Drive","GDRIVE_FOLDER_ID not present")
    if not ct: return skipped("Google Drive","No service account JSON secret present")
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        info=json.loads(ct)
        creds=service_account.Credentials.from_service_account_info(info, scopes=["https://www.googleapis.com/auth/drive.readonly"])
        svc=build("drive","v3",credentials=creds,cache_discovery=False)
        resp=svc.files().list(q=f"'{fid}' in parents and trashed=false",fields="files(id,name,mimeType,modifiedTime,size,md5Checksum)",pageSize=10,supportsAllDrives=True,includeItemsFromAllDrives=True).execute()
        files=resp.get("files",[])
        return {"provider":"Google Drive folder snapshot","ok":True,"secret_name_tested":cn,"service_account_email_present":bool(info.get("client_email")),"folder_id_sha256_prefix":hashlib.sha256(fid.encode()).hexdigest()[:10],"file_count_sample":len(files),"sample_names":[f.get("name") for f in files[:5]]}
    except Exception as e:
        return {"provider":"Google Drive folder snapshot","ok":False,"secret_name_tested":cn,"folder_id_sha256_prefix":hashlib.sha256(fid.encode()).hexdigest()[:10],"error":redact(repr(e))}

def main():
    started=now_utc()
    tests=[test_waqi(),test_openweather(),test_newsapi(),test_newsdata(),test_metoffice(),test_cdse(),test_gdrive()]
    manifest={"step":"01_secrets_smoketest","created_at_utc":started.isoformat(),"created_at_uk":now_uk(started).isoformat(),"date_uk":now_uk(started).strftime("%d/%m/%Y"),"repository":os.getenv("GITHUB_REPOSITORY",""),"github_run_id":os.getenv("GITHUB_RUN_ID",""),"github_sha":os.getenv("GITHUB_SHA",""),"controlled_use_boundary":"Secret smoke test only. Values are never printed.","secret_groups":{g:[status(n) for n in names] for g,names in GROUPS.items()},"test_summary":{"tests":len(tests),"ok":sum(1 for t in tests if t.get("ok")),"failed":sum(1 for t in tests if not t.get("ok") and not t.get("skipped")),"skipped":sum(1 for t in tests if t.get("skipped"))},"provider_tests":tests}
    p=OUT/"manifest.json"
    p.write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps({"manifest":str(p),"tests":len(tests),"ok":manifest["test_summary"]["ok"],"failed":manifest["test_summary"]["failed"],"skipped":manifest["test_summary"]["skipped"],"metoffice_ok":next((t.get("ok") for t in tests if str(t.get("provider","")).startswith("Met Office")),False)},indent=2))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
