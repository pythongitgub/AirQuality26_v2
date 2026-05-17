#!/usr/bin/env python3
import argparse, json, datetime as dt
from pathlib import Path

TERMS = ["enforcement","breach","permit","variation","emission","exceedance","complaint","plume","incident","dioxin","particulate","nitrogen dioxide","sulphur dioxide","sulfur dioxide","fire","shutdown","notice"]

def load(p):
    p=Path(p)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--output-root",default="outputs"); args=ap.parse_args()
    root=Path(args.output_root); alerts=[]
    news=load(root/"03_news_context/news_articles.json")
    for a in news.get("articles",[]):
        text=json.dumps(a,ensure_ascii=False).lower(); hits=[t for t in TERMS if t in text]
        if hits: alerts.append({"kind":"news_attention","severity":"review","hits":hits,"title":a.get("title"),"provider":a.get("_aq26_provider"),"query":a.get("_aq26_query"),"url":a.get("url") or a.get("link")})
    filings=load(root/"06_official_filings/official_filing_index.json")
    for f in filings.get("filings",[]):
        cls=f.get("aq26_relevance_class")
        if cls in ("confirmed_or_probable","candidate_context"):
            alerts.append({"kind":"official_candidate","severity":"review" if cls=="confirmed_or_probable" else "info","title":f.get("title"),"source":f.get("source"),"url":f.get("url"),"query":f.get("query"),"relevance_class":cls,"hits":f.get("aq26_relevance_hits",[])})
    sat=load(root/"07_satellite_cdse/satellite_catalogue_metadata.json")
    if sat.get("product_count",0)==0: alerts.append({"kind":"satellite_zero_products","severity":"warning","message":"No satellite catalogue products found","bbox":sat.get("bbox")})
    elif sat: alerts.append({"kind":"satellite_products_found","severity":"info","product_count":sat.get("product_count"),"bbox":sat.get("bbox")})
    latest=load(root/"00_live_harvest/LATEST_HARVEST.json")
    for r in latest.get("source_records",[]):
        if r.get("status")=="error": alerts.append({"kind":"source_error","severity":"warning","source_name":r.get("source_name"),"source_type":r.get("source_type"),"query":r.get("query"),"error":r.get("error")})
    p=root/"10_anomaly_alerts/anomaly_alerts.json"; p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps({"created_at_utc":dt.datetime.now(dt.timezone.utc).isoformat(),"alert_count":len(alerts),"alerts":alerts},indent=2,ensure_ascii=False),encoding="utf-8")
    print(f"alerts={len(alerts)}")
if __name__=="__main__": main()
